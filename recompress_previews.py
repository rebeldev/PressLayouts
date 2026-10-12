"""One-time recompress of stored layout preview PNGs.

Shrinks press_layouts.records.preview_png in place without changing format:
- Width-clamp to --max-width (default 880) with LANCZOS (stored ~1650px PNGs
  oversample the few-hundred-px preview panel, so this stays crisp on screen).
- Re-encode as PNG with optimize=True (lossless).

Usage (dry run first):
    python recompress_previews.py --mode live --dry-run
    python recompress_previews.py --mode live --apply
    python recompress_previews.py --mode test --apply --limit 25

Run VACUUM ANALYZE afterwards (DB Maintenance -> Optimize Database) so
Postgres reclaims TOAST space. Requires Pillow and psycopg2 or psycopg.
"""

import argparse
import io
import json
import os
import sys

DEFAULT_MAX_WIDTH = 880

LIVE_CONFIG = r"L:\press_layouts_db.json"
TEST_CONFIG = r"L:\working\press_layouts_db.json"


def load_config(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid config JSON: {path}")
    data.setdefault("host", "gghqsv-primasv")
    data.setdefault("port", 5432)
    data.setdefault("database", "press_layouts")
    data.setdefault("schema", "press_layouts")
    data.setdefault("user", "press_layouts")
    data.setdefault("password", "press_layouts")
    data.setdefault("sslmode", "prefer")
    return data


def import_driver():
    try:
        import psycopg2  # type: ignore

        return psycopg2, "psycopg2"
    except Exception:
        pass
    try:
        import psycopg  # type: ignore

        return psycopg, "psycopg"
    except Exception:
        raise RuntimeError("PostgreSQL driver not found (need psycopg2 or psycopg).")


def pg_ident(value):
    text = str(value or "").strip().strip('"')
    if not text or not all(ch.isalnum() or ch == "_" for ch in text):
        raise RuntimeError(f"Unsafe schema identifier: {value!r}")
    return f'"{text}"'


def connect(config, driver_name, driver):
    kwargs = {
        "host": config.get("host"),
        "port": int(config.get("port") or 5432),
        "dbname": config.get("database"),
        "user": config.get("user"),
        "password": config.get("password"),
    }
    if driver_name == "psycopg2":
        import psycopg2.extensions as ext  # type: ignore

        conn = driver.connect(**kwargs)
        try:
            conn.autocommit = False
        except Exception:
            pass
        return conn
    conn = driver.connect(
        host=kwargs["host"],
        port=kwargs["port"],
        dbname=kwargs["dbname"],
        user=kwargs["user"],
        password=kwargs["password"],
        autocommit=False,
    )
    return conn


def recompress_blob(blob, max_width):
    """Return (new_bytes, old_w, old_h, new_w, new_h). Lossless PNG -> PNG."""
    from PIL import Image

    with Image.open(io.BytesIO(bytes(blob))) as img:
        img = img.copy()
        old_w, old_h = img.size
        if img.mode == "P":
            img = img.convert("RGB")
        elif img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")
        if old_w > max_width:
            new_h = max(1, int(old_h * (max_width / float(old_w))))
            img = img.resize((max_width, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True, compress_level=6)
        new_w, new_h = img.size
        return buf.getvalue(), old_w, old_h, new_w, new_h


def main(argv=None):
    ap = argparse.ArgumentParser(description="Recompress stored preview_png blobs (lossless).")
    ap.add_argument("--mode", choices=["live", "test"], default="live")
    ap.add_argument("--config", default=None, help="Override DB config JSON path.")
    ap.add_argument("--max-width", type=int, default=DEFAULT_MAX_WIDTH)
    ap.add_argument("--limit", type=int, default=0, help="Only process first N rows (0 = all).")
    ap.add_argument("--batch-commit", type=int, default=50)
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True)
    group.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    apply = bool(args.apply)
    max_width = max(200, int(args.max_width or DEFAULT_MAX_WIDTH))
    config_path = args.config or (LIVE_CONFIG if args.mode == "live" else TEST_CONFIG)
    config = load_config(config_path)
    driver, driver_name = import_driver()
    schema = pg_ident(config.get("schema"))

    conn = connect(config, driver_name, driver)
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, record_type, file_name, octet_length(preview_png), preview_png "
            f"FROM {schema}.records WHERE preview_png IS NOT NULL ORDER BY id"
        )
        rows = cur.fetchall() or []
        cur.close()
    except Exception:
        conn.close()
        raise

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    total_old = 0
    total_new = 0
    shrunk = 0
    skipped = 0
    failed = []
    pending_updates = []

    for row in rows:
        rid, rtype, fname = row[0], row[1], row[2]
        old_len = int(row[3] or 0)
        blob = row[4]
        total_old += old_len
        try:
            raw = blob.tobytes() if isinstance(blob, memoryview) else bytes(blob)
        except Exception:
            raw = blob
        try:
            new_bytes, ow, oh, nw, nh = recompress_blob(raw, max_width)
        except Exception as exc:
            failed.append(f"{rtype}/{fname}: decode failed ({exc})")
            total_new += old_len
            continue
        if len(new_bytes) >= old_len and (ow, oh) == (nw, nh):
            # optimize=True alone rarely grows output, but never store larger bytes
            skipped += 1
            total_new += old_len
            continue
        if len(new_bytes) >= old_len:
            skipped += 1
            total_new += old_len
            continue
        shrunk += 1
        total_new += len(new_bytes)
        pending_updates.append((rid, rtype, fname, old_len, len(new_bytes), ow, oh, nw, nh, new_bytes))

    saved = total_old - total_new
    print(f"Config : {config_path} ({config.get('database')}.{config.get('schema')})")
    print(f"Rows with previews : {len(rows)}")
    print(f"Would shrink        : {shrunk}, unchanged: {skipped}, failed: {len(failed)}")
    print(f"Size  : {total_old / 1048576:.1f} MB -> {total_new / 1048576:.1f} MB "
          f"(save {saved / 1048576:.1f} MB, {100.0 * saved / max(1, total_old):.0f}%)")
    for item in pending_updates[:15]:
        print(f"  - {item[1]}/{item[2]}: {item[3] // 1024} KB -> {item[4] // 1024} KB "
              f"({item[5]}x{item[6]} -> {item[7]}x{item[8]})")
    if len(pending_updates) > 15:
        print(f"  ... and {len(pending_updates) - 15} more")
    for err in failed[:15]:
        print(f"  ! {err}")

    if not apply:
        print("\nDry run only -- no rows were changed. Re-run with --apply to write.")
        conn.close()
        return 0

    try:
        cur = conn.cursor()
        for i, item in enumerate(pending_updates, start=1):
            rid, _rtype, _fname = item[0], item[1], item[2]
            payload = item[9]
            if driver_name == "psycopg2":
                from psycopg2 import Binary  # type: ignore

                payload = Binary(payload)
            cur.execute(
                f"UPDATE {schema}.records SET preview_png = %s, updated_at = NOW() WHERE id = %s",
                (payload, rid),
            )
            if i % max(1, int(args.batch_commit or 50)) == 0:
                conn.commit()
        conn.commit()
        cur.close()
    finally:
        conn.close()

    print(f"\nUpdated {len(pending_updates)} preview(s).")
    print("Next step: DB Maintenance -> Optimize Database (VACUUM ANALYZE) to reclaim space.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
