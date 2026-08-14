import email
import getpass
import glob
import importlib
import importlib.util
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import tkinterdnd2 as tkdnd

from datetime import datetime
from tkinter import ttk, filedialog, messagebox


# =============================================================================
# Runtime setup and shared paths
# Application-wide dependency checks, icon handling, shared executable paths, and database selection startup helpers.
# =============================================================================

_RUNTIME_DEPENDENCY_CHECK_COMPLETE = False
WINDOW_ICON_FILENAME = "l:\\icon.ico"

def _window_icon_path() -> str:
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        base_dir = os.getcwd()
    return os.path.join(base_dir, WINDOW_ICON_FILENAME)

def set_window_icon(win):
    if win is None:
        return
    icon_path = _window_icon_path()
    if not os.path.exists(icon_path):
        return
    try:
        win.iconbitmap(default=icon_path)
        return
    except Exception:
        pass
    try:
        win.iconbitmap(icon_path)
    except Exception:
        pass


def _runtime_module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(str(module_name or "").strip()) is not None
    except Exception:
        return False



def ensure_runtime_dependencies(parent=None, force=False, prompt_user=True):
    global _RUNTIME_DEPENDENCY_CHECK_COMPLETE
    _RUNTIME_DEPENDENCY_CHECK_COMPLETE = True
    return True


MAIN_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_ROOT_DIR = "L:\\"
SHARED_WORKING_ROOT_DIR = "L:\\working"
SHARED_CHANGELOG_PATH = os.path.join(SHARED_ROOT_DIR, "changelog.json")
SHARED_LIVE_DB_CONFIG_PATH = os.path.join(SHARED_ROOT_DIR, "press_layouts_db.json")
SHARED_TEST_DB_CONFIG_PATH = os.path.join(SHARED_WORKING_ROOT_DIR, "press_layouts_db.json")
SHARED_EXE_PATH = os.path.join(SHARED_ROOT_DIR, "press_layout.exe")
SHARED_EXE_FALLBACK_PATH = os.path.join(SHARED_ROOT_DIR, "press_layouts.exe")
SHARED_LAUNCHER_EXE_PATH = os.path.join(SHARED_ROOT_DIR, "PressLayouts", "launcher", "press_layouts_launcher.exe")
SHARED_LAUNCHER_EXE_FALLBACK_PATH = os.path.join(SHARED_ROOT_DIR, "press_layouts_launcher.exe")

def _shared_launcher_executable_candidates():
    candidates = []
    for value in (SHARED_LAUNCHER_EXE_PATH, SHARED_LAUNCHER_EXE_FALLBACK_PATH):
        path = str(value or "").strip()
        if path and path not in candidates:
            candidates.append(path)
    return candidates

def _resolve_shared_launcher_executable_path():
    candidates = _shared_launcher_executable_candidates()
    for candidate in candidates:
        try:
            if os.path.exists(candidate):
                return candidate
        except Exception:
            pass
    return candidates[0] if candidates else ""

def _shared_executable_candidates():
    candidates = []
    for value in (SHARED_EXE_PATH, SHARED_EXE_FALLBACK_PATH):
        path = str(value or "").strip()
        if path and path not in candidates:
            candidates.append(path)
    return candidates

SELECTED_DB_CONFIG_PATH = SHARED_LIVE_DB_CONFIG_PATH
SELECTED_DB_CONFIG_LABEL = "Live"

def _set_selected_db_config_path(path, label=None):
    global SELECTED_DB_CONFIG_PATH, SELECTED_DB_CONFIG_LABEL
    SELECTED_DB_CONFIG_PATH = str(path or SHARED_LIVE_DB_CONFIG_PATH)
    SELECTED_DB_CONFIG_LABEL = str(label or "Live").strip() or "Live"
    return SELECTED_DB_CONFIG_PATH

def get_selected_db_config_path():
    return str(SELECTED_DB_CONFIG_PATH or SHARED_LIVE_DB_CONFIG_PATH)

def get_selected_db_config_label():
    return str(SELECTED_DB_CONFIG_LABEL or "Live")


_DB_MODE_PREFERENCE_FILENAME = "db_mode.json"


def _db_mode_preference_file_path():
    """Return the per-user file used to remember the selected Live/Test database mode."""
    base = (
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("APPDATA")
        or os.path.expanduser("~")
    )
    folder = os.path.join(base, "Press Layout")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        folder = MAIN_DIR
    return os.path.join(folder, _DB_MODE_PREFERENCE_FILENAME)


def _normalize_db_config_label(value):
    """Normalize a database mode label to either Live or Test."""
    text = str(value or "").strip().lower()
    return "Test" if text == "test" else "Live"


def _db_config_path_for_label(label):
    """Return the configured database JSON path for a normalized Live/Test label."""
    normalized = _normalize_db_config_label(label)
    return SHARED_TEST_DB_CONFIG_PATH if normalized == "Test" else SHARED_LIVE_DB_CONFIG_PATH


def _save_selected_db_config_preference(label=None):
    """Persist the selected database mode so the next launch starts in the same mode."""
    normalized = _normalize_db_config_label(label or get_selected_db_config_label())
    payload = {
        "mode": normalized,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        path = _db_mode_preference_file_path()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        return path
    except Exception:
        return None


def _load_selected_db_config_preference():
    """Load the remembered Live/Test mode, defaulting safely to Live."""
    mode = "Live"
    try:
        path = _db_mode_preference_file_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                mode = _normalize_db_config_label(data.get("mode"))
    except Exception:
        mode = "Live"
    return mode


def load_persisted_db_config_selection():
    """Apply the remembered Live/Test database selection without showing a startup dialog."""
    mode = _load_selected_db_config_preference()
    _set_selected_db_config_path(_db_config_path_for_label(mode), mode)
    return True


def _reset_database_backend_after_config_switch():
    """Force the next database operation to use the newly selected config and reload launcher caches."""
    global _DB_BOOTSTRAPPED
    try:
        _DB_BOOTSTRAPPED = False
    except Exception:
        pass
    for cache_name in ("_TEMPLATE_CACHE", "_REGULAR_CACHE", "_LAYOUT_CACHE"):
        cache = globals().get(cache_name)
        if isinstance(cache, dict):
            cache["signature"] = None
            cache["rows"] = []
    try:
        _PREVIEW_IMAGE_CACHE.clear()
    except Exception:
        pass
    try:
        _TRANSLATION_CACHE["product"] = {"entries": None, "lookup": {}}
        _TRANSLATION_CACHE["section"] = {"entries": None, "lookup": {}}
    except Exception:
        pass
    try:
        _db_close_pool()
    except Exception:
        pass


def _db_mode_label_text():
    return f"Database: {get_selected_db_config_label().upper()}"


def _db_mode_label_style():
    return "DatabaseModeTest.TLabel" if get_selected_db_config_label().strip().lower() == "test" else "DatabaseModeLive.TLabel"


def _update_db_mode_label_widget(label_widget):
    if label_widget is None:
        return
    try:
        label_widget.configure(text=_db_mode_label_text(), style=_db_mode_label_style())
    except Exception:
        pass


def toggle_database_config_from_launcher(label_widget=None, refresh_callback=None, clear_preview_callback=None):
    """Toggle Live/Test from the main launcher label and remember the choice for future launches."""
    current = _normalize_db_config_label(get_selected_db_config_label())
    new_mode = "Test" if current == "Live" else "Live"
    _set_selected_db_config_path(_db_config_path_for_label(new_mode), new_mode)
    _save_selected_db_config_preference(new_mode)
    _reset_database_backend_after_config_switch()
    _update_db_mode_label_widget(label_widget)

    if callable(clear_preview_callback):
        try:
            clear_preview_callback()
        except Exception:
            pass
    if callable(refresh_callback):
        try:
            refresh_callback(False)
        except TypeError:
            try:
                refresh_callback()
            except Exception:
                pass
        except Exception as exc:
            try:
                messagebox.showerror("Database Switch Failed", str(exc))
            except Exception:
                pass
    return new_mode

def prompt_admin_db_config_selection():
    """Compatibility wrapper: startup now loads the persisted Live/Test selection without prompting."""
    return load_persisted_db_config_selection()


# =============================================================================
# Press configuration constants
# Directory placeholders and Press 1/Press 2 format definitions used by the layout builders.
# =============================================================================

LAYOUTS_DIR = "__DB_LAYOUTS__"
TEMPLATE_DIR = "__DB_TEMPLATES__"
REGULAR_DIR = "__DB_REGULAR__"
FORMAT_MIN_PAGES = {
    "Broadsheet": 2,
    "Tab": 4,
    "8 up": 8,
}
BASE_COMMON = {
    "swatch_cols": 2,
    "midline_thickness": 4,
    "midline_color": "#444444",
    "cell_pad": 0,
    "unit_padding": (6, 6, 6, 6),
    "unit_padx": 6,
    "unit_pady": 6,
    "folder_padx": 24,
    "folder_padding": (8, 8, 8, 8),
    "enable_hscroll": False,
}
PRESS_1_BASE = {
    **BASE_COMMON,
    "press_name": "Press 1",
    "left_labels": ["E1", "D1", "C1", "B1-Lower", "B1-Upper", "A1"],
    "right_labels": ["F1", "G1-Lower", "G1-Upper", "E2", "D2", "C2"],
    "only_k_labels": {"E1", "B1-Lower", "B1-Upper", "G1-Lower", "G1-Upper", "E2"},
    "folder_label": "Folder - 1",
}
PRESS_1_BROADSHEET = {
    **PRESS_1_BASE,
    "format_name": "Broadsheet",
    "grid_rows": 2,
    "grid_cols": 2,
    "autosize": True,
}
PRESS_1_TAB = {
    **PRESS_1_BASE,
    "format_name": "Tab",
    "grid_rows": 2,
    "grid_cols": 4,
    "autosize": True,
    "unit_padding": (4, 4, 4, 4),
    "unit_padx": 3,
    "folder_padx": 10,
    "cell_font": (None, 10),
    "cell_width": 3,
}
PRESS_1_8UP = {
    **PRESS_1_BASE,
    "format_name": "8 up",
    "grid_rows": 2,
    "grid_cols": 8,
    "enable_hscroll": True,
    "full_width": True,
    "scroll_height_hint": 360,
}
PRESS_2_BASE = {
    **BASE_COMMON,
    "press_name": "Press 2",
    "left_labels": ["E2", "D2", "C2", "B2-Lower", "B2-Upper", "A2"],
    "right_labels": ["F2", "G2-Lower", "G2-Upper"],
    "only_k_labels": {"E2", "B2-Lower", "B2-Upper", "G2-Lower", "G2-Upper"},
    "folder_label": "Folder - 2",
}
PRESS_2_BROADSHEET = {
    **PRESS_2_BASE,
    "format_name": "Broadsheet",
    "grid_rows": 2,
    "grid_cols": 2,
    "autosize": True,
}
PRESS_2_TAB = {
    **PRESS_2_BASE,
    "format_name": "Tab",
    "grid_rows": 2,
    "grid_cols": 4,
    "autosize": True,
    "unit_padding": (4, 4, 4, 4),
    "unit_padx": 3,
    "folder_padx": 10,
    "cell_font": (None, 10),
    "cell_width": 3,
}
PRESS_2_8UP = {
    **PRESS_2_BASE,
    "format_name": "8 up",
    "grid_rows": 2,
    "grid_cols": 8,
    "enable_hscroll": True,
    "full_width": True,
    "scroll_height_hint": 360,
}
CONFIG_MAP = {
    ("Press 1", "Broadsheet"): PRESS_1_BROADSHEET,
    ("Press 1", "Tab"): PRESS_1_TAB,
    ("Press 1", "8 up"): PRESS_1_8UP,
    ("Press 2", "Broadsheet"): PRESS_2_BROADSHEET,
    ("Press 2", "Tab"): PRESS_2_TAB,
    ("Press 2", "8 up"): PRESS_2_8UP,
}

# =============================================================================
# General utility helpers
# Reusable file, JSON, username, admin, date, naming, validation, imposition, and focus-order helpers.
# =============================================================================

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
def safe_read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
def safe_write_json(path, data):
    ensure_dir(os.path.dirname(path))
    to_write = data
    if isinstance(data, dict) and _path_is_tracked_layout_json(path):
        to_write = stamp_layout_change_metadata(data, path=path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_write, f, indent=2)
def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, "_")
    return name.strip()
def normalize_publication_name(value: str) -> str:
    return str(value or "").strip().upper()


def _tracked_layout_roots():
    return [
        os.path.abspath(LAYOUTS_DIR),
        os.path.abspath(TEMPLATE_DIR),
        os.path.abspath(REGULAR_DIR),
    ]


def _path_is_tracked_layout_json(path: str) -> bool:
    try:
        abs_path = os.path.abspath(str(path or ""))
    except Exception:
        return False
    if not abs_path.lower().endswith('.json'):
        return False
    for root in _tracked_layout_roots():
        try:
            common = os.path.commonpath([abs_path, root])
        except Exception:
            common = ""
        if common == root:
            return True
    return False


def get_windows_username() -> str:
    """Best-effort current Windows/user login name for change stamping."""
    candidates = [
        os.environ.get('USERNAME'),
        os.environ.get('USER'),
    ]
    try:
        candidates.append(os.getlogin())
    except Exception:
        pass
    try:
        candidates.append(getpass.getuser())
    except Exception:
        pass
    for value in candidates:
        text = str(value or '').strip()
        if text:
            return text
    return 'Unknown'

def is_admin(username=None) -> bool:
    """Return True when the effective login should see admin-only launcher actions."""
    effective_username = username if username is not None else get_windows_username()
    return str(effective_username or '').strip().lower() == 'mbradbury'


_TRANSLATION_CACHE = {
    "product": {"entries": None, "lookup": {}},
    "section": {"entries": None, "lookup": {}},
}


def _load_product_translations():
    cache = _TRANSLATION_CACHE["product"]
    if cache["entries"] is not None:
        return [dict(entry) for entry in cache["entries"]]
    try:
        with _db_cursor() as (cur, config):
            schema = _db_pg_ident(config.get('schema'))
            cur.execute(f'SELECT incoming, output FROM {schema}.product_translations ORDER BY incoming')
            entries = [{"incoming": r["incoming"], "output": r["output"]} for r in _db_fetchall(cur)]
            cache["entries"] = entries
            cache["lookup"] = {
                str(entry.get("incoming") or "").strip().lower(): str(entry.get("output") or "").strip()
                for entry in entries
            }
            return [dict(entry) for entry in entries]
    except Exception:
        return []

def _save_product_translations(translations):
    try:
        with _db_cursor() as (cur, config):
            schema = _db_pg_ident(config.get('schema'))
            cur.execute(f'DELETE FROM {schema}.product_translations')
            for entry in translations:
                incoming = entry.get("incoming", "").strip()
                if incoming:
                    cur.execute(
                        f'INSERT INTO {schema}.product_translations (incoming, output) VALUES (%s, %s)',
                        (incoming, entry.get("output", "").strip()),
                    )
        _TRANSLATION_CACHE["product"] = {"entries": None, "lookup": {}}
        return True
    except Exception:
        return False

def _apply_product_translation(product_name):
    lower_in = product_name.strip().lower()
    _load_product_translations()
    translated = _TRANSLATION_CACHE["product"]["lookup"].get(lower_in, "")
    return translated or product_name

def _load_section_translations():
    cache = _TRANSLATION_CACHE["section"]
    if cache["entries"] is not None:
        return [dict(entry) for entry in cache["entries"]]
    try:
        with _db_cursor() as (cur, config):
            schema = _db_pg_ident(config.get('schema'))
            cur.execute(f'SELECT incoming, output FROM {schema}.section_translations ORDER BY incoming')
            entries = [{"incoming": r["incoming"], "output": r["output"]} for r in _db_fetchall(cur)]
            cache["entries"] = entries
            cache["lookup"] = {
                str(entry.get("incoming") or "").strip().lower(): str(entry.get("output") or "").strip()
                for entry in entries
            }
            return [dict(entry) for entry in entries]
    except Exception:
        return []

def _save_section_translations(translations):
    try:
        with _db_cursor() as (cur, config):
            schema = _db_pg_ident(config.get('schema'))
            cur.execute(f'DELETE FROM {schema}.section_translations')
            for entry in translations:
                incoming = entry.get("incoming", "").strip()
                if incoming:
                    cur.execute(
                        f'INSERT INTO {schema}.section_translations (incoming, output) VALUES (%s, %s)',
                        (incoming, entry.get("output", "").strip()),
                    )
        _TRANSLATION_CACHE["section"] = {"entries": None, "lookup": {}}
        return True
    except Exception:
        return False

def _apply_section_translation(section_name):
    lower_in = str(section_name or "").strip().lower()
    _load_section_translations()
    translated = _TRANSLATION_CACHE["section"]["lookup"].get(lower_in, "")
    return translated or section_name

def stamp_layout_change_metadata(data, path=None):
    if not isinstance(data, dict):
        return data
    if path and not _path_is_tracked_layout_json(path):
        return data
    stamped = dict(data)
    now = datetime.now().isoformat(timespec='seconds')
    stamped['last_changed_by'] = get_windows_username()
    stamped['saved_at'] = now
    return stamped
def list_json_files(folder):
    """Return list of (display_name, full_path) for .json files in folder."""
    ensure_dir(folder)
    paths = sorted(glob.glob(os.path.join(folder, "*.json")))
    results = []
    for p in paths:
        data = safe_read_json(p)
        stem = os.path.splitext(os.path.basename(p))[0]
        disp = stem
        if data and isinstance(data, dict):
            disp = data.get("name") or stem
        results.append((disp, p))
    return results
def min_pages_for_format(fmt: str) -> int:
    return FORMAT_MIN_PAGES.get(fmt, 1)
def is_valid_page_count(value: str, multiple: int) -> bool:
    try:
        n = int(str(value).strip())
        return n >= multiple and (n % multiple == 0)
    except Exception:
        return False
def parse_issue_date_flexible(text: str, today=None):
    """
    Parse many date inputs into datetime.
    - Supports: MMDD, MDD, MMDDYY, MDDYY, MMDDYYYY
    - Supports: M/D, M/D/YY, M/D/YYYY, M-D, M.D
    - Supports: YYYY-MM-DD, YYYY/MM/DD
    - Supports: Month names like "May 28", "May 28 26", "May 28 2026"
    - If year missing: assumes current year
    """
    if not text:
        return None
    if today is None:
        today = datetime.now()

    t = text.strip()
    if not t:
        return None

    default_year = today.year

    # Month-name formats
    if any(ch.isalpha() for ch in t):
        cleaned = re.sub(r"[,\-]+", " ", t).strip()
        has_year = re.search(r"\b(\d{4}|\d{2})\b", cleaned) is not None
        candidates = [cleaned] if has_year else [f"{cleaned} {default_year}"]

        patterns = [
            "%b %d %Y", "%B %d %Y",
            "%b %d %y", "%B %d %y",
            "%d %b %Y", "%d %B %Y",
            "%d %b %y", "%d %B %y",
        ]
        for s in candidates:
            for fmt in patterns:
                try:
                    dt = datetime.strptime(s, fmt)
                    if dt.year < 1970:
                        dt = dt.replace(year=dt.year + 100)
                    return dt
                except Exception:
                    pass
        return None

    # digits-only / digits-extracted
    digits = re.sub(r"\D", "", t)
    if digits:
        try:
            if len(digits) == 4:  # MMDD
                mm, dd = int(digits[0:2]), int(digits[2:4])
                return datetime(default_year, mm, dd)
            if len(digits) == 3:  # MDD
                mm, dd = int(digits[0:1]), int(digits[1:3])
                return datetime(default_year, mm, dd)
            if len(digits) == 6:  # MMDDYY
                mm, dd = int(digits[0:2]), int(digits[2:4])
                yy = int(digits[4:6])
                year = 2000 + yy if yy <= 69 else 1900 + yy
                return datetime(year, mm, dd)
            if len(digits) == 5:  # MDDYY
                mm, dd = int(digits[0:1]), int(digits[1:3])
                yy = int(digits[3:5])
                year = 2000 + yy if yy <= 69 else 1900 + yy
                return datetime(year, mm, dd)
            if len(digits) == 8:  # MMDDYYYY
                mm, dd, yyyy = int(digits[0:2]), int(digits[2:4]), int(digits[4:8])
                return datetime(yyyy, mm, dd)
        except Exception:
            pass

    # Separated numeric formats
    parts = re.split(r"[\/\.\-\s]+", t)
    parts = [p for p in parts if p]
    try:
        if len(parts) == 2:  # M/D (no year)
            mm, dd = int(parts[0]), int(parts[1])
            return datetime(default_year, mm, dd)
        if len(parts) == 3:
            if len(parts[0]) == 4:  # YYYY-MM-DD
                yyyy, mm, dd = int(parts[0]), int(parts[1]), int(parts[2])
                return datetime(yyyy, mm, dd)
            mm, dd = int(parts[0]), int(parts[1])
            y = parts[2]
            if len(y) == 2:
                yy = int(y)
                yyyy = 2000 + yy if yy <= 69 else 1900 + yy
            else:
                yyyy = int(y)
            return datetime(yyyy, mm, dd)
    except Exception:
        return None

    return None
def normalize_issue_date_mmddyyyy(text: str) -> str:
    """Return mm/dd/yyyy if parseable, else original text."""
    dt = parse_issue_date_flexible(text)
    if not dt:
        return text
    return dt.strftime("%m/%d/%Y")

def tomorrow_issue_date_mmddyyyy() -> str:
    """Return tomorrow's date in mm/dd/YYYY format."""
    from datetime import timedelta
    return (datetime.now() + timedelta(days=1)).strftime("%m/%d/%Y")
def parse_saved_at(text: str):
    """Parse ISO saved_at into datetime."""
    if not text:
        return None
    t = str(text).strip()
    try:
        return datetime.fromisoformat(t)
    except Exception:
        return None
def fmt_dt_for_display(dt: datetime) -> str:
    return dt.strftime("%m/%d/%Y %H:%M:%S") if dt else ""
def fmt_issue_for_display(issue_text: str) -> str:
    dt = parse_issue_date_flexible(issue_text)
    return dt.strftime("%m/%d/%Y") if dt else (issue_text or "")
def build_layout_filename_suggestion(ctx) -> str:
    raw_date = ctx["issue_entry"].get().strip() if ctx.get("issue_entry") else ""
    raw_product = normalize_publication_name(ctx["product_entry"].get()) if ctx.get("product_entry") else ""

    dt = parse_issue_date_flexible(raw_date)
    date_part = dt.strftime("%m%d%Y") if dt else "00000000"
    product_part = raw_product if raw_product else "Layout"
    return sanitize_filename(f"{date_part} - {product_part}.json").strip()


def _section_name_for_filename(ctx, section_index: int) -> str:
    try:
        raw_name = (ctx.get("section_name_vars", [])[section_index - 1].get() or "").strip()
    except Exception:
        raw_name = ""
    if raw_name:
        return str(raw_name).upper()
    if bool(ctx.get("template_mode", False)):
        return f"S{section_index}"
    return chr(ord("A") + section_index - 1)


def build_regular_filename_suggestion(ctx) -> str:
    press_name = ctx.get("press_name", "")
    press_num = "1" if "1" in press_name else "2"
    prefix = f"P{press_num}"
    publication = normalize_publication_name(ctx["product_entry"].get()) if ctx.get("product_entry") else ""
    publication = publication or "Publication"

    try:
        section_count = int(ctx["section_count_var"].get())
    except Exception:
        section_count = 1
    section_count = max(1, min(4, section_count))

    page_counts = compute_section_page_counts_from_ctx(ctx, section_count=section_count)
    section_segments = []
    for section_index in range(1, section_count + 1):
        section_pages = page_counts[section_index - 1] if section_index - 1 < len(page_counts) else 0
        if int(section_pages or 0) <= 0:
            continue
        section_name = _section_name_for_filename(ctx, section_index)
        section_segments.append(f"{section_name}{int(section_pages)}")

    filename_parts = [prefix, publication]
    if section_segments:
        filename_parts.append("-".join(section_segments))

    name = sanitize_filename(" ".join(part for part in filename_parts if part).strip())
    if not name.lower().endswith(".json"):
        name += ".json"
    return name


def build_save_filename_suggestion(ctx) -> str:
    if ctx.get("template_mode"):
        return build_filename_suggestion(ctx)
    if _ctx_is_regular_mode(ctx):
        return build_regular_filename_suggestion(ctx)
    return build_layout_filename_suggestion(ctx)
def safe_int(value):
    try:
        return int(str(value).strip())
    except Exception:
        return None
def unit_row_has_numbers(unit_dict, row_index: int) -> bool:
    entries_2d = unit_dict["entries"]
    if row_index < 0 or row_index >= len(entries_2d):
        return False
    for cell in entries_2d[row_index]:
        if safe_int(cell.get()) is not None:
            return True
    return False
def unit_dinky_suffix(unit_dict) -> str:
    # ds if only TOP row has numbers; os if only BOTTOM row has numbers
    top_has = unit_row_has_numbers(unit_dict, 0)
    bottom_has = unit_row_has_numbers(unit_dict, 1)
    if top_has and not bottom_has:
        return "ds"
    if bottom_has and not top_has:
        return "os"
    return ""
def parse_section_id(text: str):
    if text is None:
        return None
    t = text.strip().upper()
    if not t:
        return None
    if t.startswith("S") and len(t) >= 2 and t[1:].isdigit():
        n = int(t[1:])
        return n if 1 <= n <= 4 else None
    if t.isdigit():
        n = int(t)
        return n if 1 <= n <= 4 else None
    if t in ("A", "B", "C", "D"):
        return ord(t) - ord("A") + 1
    return None
def abbrev_unit_label(label: str) -> str:
    if not label:
        return ""
    s = label.replace("-Lower", "L").replace("-Upper", "U")
    s = s.replace("-", "").replace(" ", "")
    return s
def unit_min_page_number(unit_dict):
    mins = None
    for row in unit_dict["entries"]:
        for cell in row:
            v = safe_int(cell.get())
            if v is None:
                continue
            if mins is None or v < mins:
                mins = v
    return mins


def unit_row_numbers(unit_dict, row_index: int):
    values = []
    entries_2d = unit_dict.get("entries", [])
    if row_index < 0 or row_index >= len(entries_2d):
        return values
    for cell in entries_2d[row_index]:
        value = cell.get() if hasattr(cell, "get") else cell
        parsed = safe_int(value)
        if parsed is not None:
            values.append(parsed)
    return values


def unit_top_row_numbers(unit_dict):
    return unit_row_numbers(unit_dict, 0)


def unit_bottom_row_numbers(unit_dict):
    return unit_row_numbers(unit_dict, 1)


def unit_top_row_min_page_number(unit_dict):
    values = unit_top_row_numbers(unit_dict)
    return min(values) if values else None


def unit_top_row_max_page_number(unit_dict):
    values = unit_top_row_numbers(unit_dict)
    return max(values) if values else None


def unit_bottom_row_min_page_number(unit_dict):
    values = unit_bottom_row_numbers(unit_dict)
    return min(values) if values else None


def _section_units_in_imposition_walk_order(section_units, press_name):
    preferred_labels = get_unit_order(section_units, press_name)
    unit_map = {str(u.get("label") or ""): u for u in section_units}
    ordered = [unit_map[label] for label in preferred_labels if label in unit_map]
    seen_labels = set(preferred_labels)
    extras = sorted(
        [u for u in section_units if str(u.get("label") or "") not in seen_labels],
        key=lambda u: str(u.get("label") or "")
    )
    ordered.extend(extras)
    return ordered


def unit_effective_imposition_sort_value(unit_dict, section_units, press_name):
    """Return the page-like value used to sort units for imposition names.

    Full units and DS dinkies sort by their real top-row minimum.
    OS dinkies infer a virtual top row so they sort between the units that
    physically surround them on the former/web walk order.
    """
    top_min = unit_top_row_min_page_number(unit_dict)
    if top_min is not None:
        return float(top_min)

    if unit_dinky_suffix(unit_dict) == "os":
        ordered_units = _section_units_in_imposition_walk_order(section_units, press_name)
        try:
            idx = ordered_units.index(unit_dict)
        except ValueError:
            idx = -1

        prev_top_max = None
        next_top_min = None

        if idx >= 0:
            for j in range(idx - 1, -1, -1):
                val = unit_top_row_max_page_number(ordered_units[j])
                if val is not None:
                    prev_top_max = val
                    break

            for j in range(idx + 1, len(ordered_units)):
                val = unit_top_row_min_page_number(ordered_units[j])
                if val is not None:
                    next_top_min = val
                    break

        if prev_top_max is not None and next_top_min is not None:
            candidate = float(prev_top_max) + 0.1
            if candidate < float(next_top_min):
                return candidate
            return (float(prev_top_max) + float(next_top_min)) / 2.0

        if prev_top_max is not None:
            return float(prev_top_max) + 0.1

        if next_top_min is not None:
            return float(next_top_min) - 0.1

    bottom_min = unit_bottom_row_min_page_number(unit_dict)
    if bottom_min is not None:
        return float(bottom_min)

    actual_min = unit_min_page_number(unit_dict)
    if actual_min is not None:
        return float(actual_min)

    return float("inf")


def unit_page_entry_count(unit_dict) -> int:
    total = 0
    for row in unit_dict.get("entries", []):
        for cell in row:
            value = cell.get() if hasattr(cell, "get") else cell
            if safe_int(value) is not None:
                total += 1
    return total


def resolve_unit_section_id_for_ctx(unit_dict, ctx, section_count=None):
    if section_count is None:
        try:
            section_count = int(ctx.get("section_count_var").get())
        except Exception:
            section_count = 1
    section_count = max(1, min(4, int(section_count)))

    section_entry = unit_dict.get("section_entry")
    sec_text = (section_entry.get() or "").strip().upper() if section_entry is not None else ""
    sec_id = None

    sn_vars = ctx.get("section_name_vars")
    if sn_vars:
        try:
            for i in range(section_count):
                name = (sn_vars[i].get() or "").strip().upper()
                if name and sec_text == name:
                    sec_id = i + 1
                    break
        except Exception:
            sec_id = None

    if sec_id is None:
        sec_id = parse_section_id(sec_text)

    if sec_id is None or not (1 <= sec_id <= section_count):
        return None
    return sec_id


def compute_section_page_counts_from_ctx(ctx, section_count=None):
    if section_count is None:
        try:
            section_count = int(ctx.get("section_count_var").get())
        except Exception:
            section_count = 1
    section_count = max(1, min(4, int(section_count)))
    counts = [0] * section_count

    for unit_dict in ctx.get("units", []):
        sec_id = resolve_unit_section_id_for_ctx(unit_dict, ctx, section_count=section_count)
        if sec_id is None:
            continue
        counts[sec_id - 1] += unit_page_entry_count(unit_dict)
    return counts

def build_filename_suggestion(ctx) -> str:
    press_name = ctx.get("press_name", "")
    press_num = "1" if "1" in press_name else "2"
    prefix = f"P{press_num}"

    try:
        section_count = int(ctx["section_count_var"].get())
    except Exception:
        section_count = 1
    section_count = max(1, min(4, section_count))

    pages = compute_section_page_counts_from_ctx(ctx, section_count=section_count)
    units_by_section = {i: [] for i in range(1, section_count + 1)}
    for u in ctx["units"]:
        sec_id = resolve_unit_section_id_for_ctx(u, ctx, section_count=section_count)
        if sec_id is None:
            continue
        units_by_section[sec_id].append(u)

    segments = []
    for sec_idx in range(1, section_count + 1):
        sec_pages = pages[sec_idx - 1] if sec_idx - 1 < len(pages) else 0
        sec_units = units_by_section.get(sec_idx, [])
        ordered_labels = get_unit_order(sec_units, press_name)
        order_index = {label: idx for idx, label in enumerate(ordered_labels)}

        def sort_key(u):
            label = str(u.get("label") or "")
            return (
                unit_effective_imposition_sort_value(u, sec_units, press_name),
                order_index.get(label, 10**6),
                label,
            )

        sec_units_sorted = sorted(sec_units, key=sort_key)
        units_part = "".join(
            f"{abbrev_unit_label(u['label'])}{unit_dinky_suffix(u)}"
            for u in sec_units_sorted
        )
        segments.append(f"{sec_pages}{units_part}")

    name = prefix + " " + " ".join(segments)
    name = sanitize_filename(name).strip()
    if not name.lower().endswith(".json"):
        name += ".json"
    return name
def build_imposition_text(ctx) -> str:
    return os.path.splitext(build_filename_suggestion(ctx))[0]
def build_focus_order(issue_entry, product_entry, units, grid_rows, grid_cols, press_name, extra_widgets=None):
    unit_map = {u["label"]: u for u in units}
    press_num = "1" if "1" in press_name else "2"

    preferred_labels = [
        f"F{press_num}",
        f"G{press_num}-Lower",
        f"G{press_num}-Upper",
        "E2", "D2", "C2",
        "E1", "D1", "C1",
        f"B{press_num}-Lower",
        f"B{press_num}-Upper",
        f"A{press_num}",
    ]
    unit_order = [lab for lab in preferred_labels if lab in unit_map]

    focus_widgets = [issue_entry, product_entry]
    if extra_widgets:
        focus_widgets.extend(extra_widgets)

    for lab in unit_order:
        focus_widgets.append(unit_map[lab]["section_entry"])

    # Grid cells tab left-to-right for every row so Tab always advances visually to the right.
    for r in range(max(0, grid_rows)):
        for lab in unit_order:
            row_entries = unit_map[lab]["entries"][r]
            for c in range(min(grid_cols, len(row_entries))):
                focus_widgets.append(row_entries[c])

    return focus_widgets


def set_custom_tab_order(widgets):
    widgets = [w for w in widgets if w is not None]
    seen = set()
    ordered = []
    for w in widgets:
        key = str(w)
        if key not in seen:
            ordered.append(w)
            seen.add(key)
    if not ordered:
        return

    n = len(ordered)
    next_map = {ordered[i]: ordered[(i + 1) % n] for i in range(n)}
    prev_map = {ordered[i]: ordered[(i - 1) % n] for i in range(n)}
    grid_widgets = [w for w in ordered if getattr(w, "_press_grid_cell", False)]

    def _goto(target):
        target.focus_set()
        try:
            target.selection_range(0, "end")
        except Exception:
            pass
        return "break"

    def _ordered_grid_widgets():
        widgets_in_order = []
        for widget in grid_widgets:
            try:
                if not widget.winfo_exists() or not widget.winfo_viewable():
                    continue
                widgets_in_order.append(widget)
            except Exception:
                continue
        widgets_in_order.sort(key=lambda widget: (int(widget.winfo_rooty()), int(widget.winfo_rootx()), str(widget)))
        return widgets_in_order

    def _grid_tab_target(current_widget, reverse=False):
        widgets_in_order = _ordered_grid_widgets()
        if len(widgets_in_order) < 2:
            return None
        try:
            idx = widgets_in_order.index(current_widget)
        except ValueError:
            return None
        if reverse:
            return widgets_in_order[(idx - 1) % len(widgets_in_order)]
        return widgets_in_order[(idx + 1) % len(widgets_in_order)]

    def _on_tab(event, default_target, reverse=False):
        widget = event.widget
        if getattr(widget, "_press_grid_cell", False):
            target = _grid_tab_target(widget, reverse=reverse)
            if target is not None:
                return _goto(target)
        return _goto(default_target)

    for w in ordered:
        nxt = next_map[w]
        prv = prev_map[w]
        try:
            w.configure(takefocus=True)
        except Exception:
            pass
        w.bind("<Tab>", lambda e, _n=nxt: _on_tab(e, _n, reverse=False))
        w.bind("<Shift-Tab>", lambda e, _p=prv: _on_tab(e, _p, reverse=True))
        w.bind("<ISO_Left_Tab>", lambda e, _p=prv: _on_tab(e, _p, reverse=True))
def get_unit_order(units, press_name):
    unit_map = {u["label"]: u for u in units}
    press_num = "1" if "1" in press_name else "2"
    preferred_labels = [
        f"F{press_num}",
        f"G{press_num}-Lower",
        f"G{press_num}-Upper",
        "E2", "D2", "C2",
        "E1", "D1", "C1",
        f"B{press_num}-Lower",
        f"B{press_num}-Upper",
        f"A{press_num}",
    ]
    return [lab for lab in preferred_labels if lab in unit_map]
def enable_arrow_navigation(focus_list, units, press_name):
    focus_list = [w for w in focus_list if w is not None]
    if len(focus_list) < 2:
        return

    n = len(focus_list)
    next_map = {focus_list[i]: focus_list[(i + 1) % n] for i in range(n)}
    prev_map = {focus_list[i]: focus_list[(i - 1) % n] for i in range(n)}

    unit_order = get_unit_order(units, press_name)
    unit_map = {u["label"]: u for u in units}
    unit_index = {lab: i for i, lab in enumerate(unit_order)}

    grid_lookup = {}
    for u in units:
        entries_2d = u["entries"]
        for r, row in enumerate(entries_2d):
            for c, cell in enumerate(row):
                grid_lookup[cell] = (u["label"], entries_2d, r, c)

    def _goto(w):
        w.focus_set()
        try:
            w.selection_range(0, "end")
        except Exception:
            pass
        return "break"

    def grid_left(w):
        lab, entries_2d, r, c = grid_lookup[w]
        if c - 1 >= 0:
            return _goto(entries_2d[r][c - 1])
        if lab in unit_index and unit_order:
            prev_lab = unit_order[(unit_index[lab] - 1) % len(unit_order)]
            prev_entries = unit_map[prev_lab]["entries"]
            return _goto(prev_entries[r][len(prev_entries[r]) - 1])
        return _goto(prev_map[w])

    def grid_right(w):
        lab, entries_2d, r, c = grid_lookup[w]
        if c + 1 < len(entries_2d[r]):
            return _goto(entries_2d[r][c + 1])
        if lab in unit_index and unit_order:
            next_lab = unit_order[(unit_index[lab] + 1) % len(unit_order)]
            next_entries = unit_map[next_lab]["entries"]
            return _goto(next_entries[r][0])
        return _goto(next_map[w])

    def grid_up(w):
        lab, entries_2d, r, c = grid_lookup[w]
        rows = len(entries_2d)
        target_r = (r - 1) % rows
        if c < len(entries_2d[target_r]):
            return _goto(entries_2d[target_r][c])
        return _goto(prev_map[w])

    def grid_down(w):
        lab, entries_2d, r, c = grid_lookup[w]
        rows = len(entries_2d)
        target_r = (r + 1) % rows
        if c < len(entries_2d[target_r]):
            return _goto(entries_2d[target_r][c])
        return _goto(next_map[w])

    def on_left(event):
        w = event.widget
        if w in grid_lookup:
            return grid_left(w)
        if isinstance(w, (tk.Entry, ttk.Entry)):
            return
        return _goto(prev_map[w])

    def on_right(event):
        w = event.widget
        if w in grid_lookup:
            return grid_right(w)
        if isinstance(w, (tk.Entry, ttk.Entry)):
            return
        return _goto(next_map[w])

    def on_up(event):
        w = event.widget
        if w in grid_lookup:
            return grid_up(w)
        if isinstance(w, (tk.Entry, ttk.Entry)):
            return
        return _goto(prev_map[w])

    def on_down(event):
        w = event.widget
        if w in grid_lookup:
            return grid_down(w)
        if isinstance(w, (tk.Entry, ttk.Entry)):
            return
        return _goto(next_map[w])

    for w in focus_list:
        try:
            w.configure(takefocus=True)
        except Exception:
            pass
        w.bind("<KeyPress-Left>", on_left)
        w.bind("<KeyPress-Right>", on_right)
        w.bind("<KeyPress-Up>", on_up)
        w.bind("<KeyPress-Down>", on_down)
        w.bind("<KP_Left>", on_left)
        w.bind("<KP_Right>", on_right)
        w.bind("<KP_Up>", on_up)
        w.bind("<KP_Down>", on_down)

# =============================================================================
# Editor widget and navigation helpers
# Reusable Tk widgets for press units, overlays, color swatches, scroll areas, sizing, tab order, and arrow-key navigation.
# =============================================================================

def overlay_render_cell(overlay: tk.Canvas, text: str, circled: bool):
    """Render the cell's text and optional red circle on top."""
    overlay.delete("all")

    overlay.update_idletasks()
    w = overlay.winfo_width()
    h = overlay.winfo_height()

    # draw text in the middle
    overlay.create_text(
        w // 2,
        h // 2,
        text=text,
        fill="black",
        font=(None, 11),
        tags=("txt",)
    )

    # draw red circle if selected
    if circled:
        pad = 3
        overlay.create_oval(
            pad, pad, max(pad + 1, w - pad), max(pad + 1, h - pad),
            outline="red", width=2, tags=("circle",)
        )
def _contrast_text_color(hex_color: str) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "black" if luminance > 150 else "white"
def overlay_show(overlay: tk.Canvas):
    if not getattr(overlay, "_shown", False):
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay._shown = True
def overlay_hide(overlay: tk.Canvas):
    if getattr(overlay, "_shown", False):
        overlay.place_forget()
        overlay._shown = False
def overlay_set_circle(overlay: tk.Canvas, on: bool):
    overlay.delete("circle")
    overlay._circle_id = None
    if on:
        overlay.update_idletasks()
        w = overlay.winfo_width()
        h = overlay.winfo_height()
        pad = 3
        overlay._circle_id = overlay.create_oval(
            pad, pad, max(pad+1, w - pad), max(pad+1, h - pad),
            outline="red", width=2, tags=("circle",)
        )
def make_press_area(parent, enable_hscroll=False, height_hint=320):
    outer = ttk.Frame(parent)
    outer.pack(fill="both", expand=True)

    if not enable_hscroll:
        inner = ttk.Frame(outer)
        inner.pack(fill="both", expand=True)
        return outer, inner, None

    canvas = tk.Canvas(outer, highlightthickness=0, height=height_hint)
    canvas.pack(side="top", fill="both", expand=True)

    xscroll = ttk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
    xscroll.pack(side="bottom", fill="x")
    canvas.configure(xscrollcommand=xscroll.set)

    inner = ttk.Frame(canvas)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_inner_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(event):
        canvas.itemconfigure(window_id, height=event.height)

    inner.bind("<Configure>", _on_inner_configure)
    canvas.bind("<Configure>", _on_canvas_configure)
    return outer, inner, canvas
def apply_window_sizing(win, config):
    autosize = config.get("autosize", False)
    full_width = config.get("full_width", False)

    win.update_idletasks()
    req_w = win.winfo_reqwidth()
    req_h = win.winfo_reqheight()
    scr_w = win.winfo_screenwidth()
    scr_h = win.winfo_screenheight()

    margin_w = config.get("screen_margin_w", 40)
    margin_h = config.get("screen_margin_h", 120)

    max_w = max(400, scr_w - margin_w)
    max_h = max(300, scr_h - margin_h)

    if full_width:
        w = scr_w
        h = min(req_h, max_h)
        win.geometry(f"{w}x{h}+0+0")
        return

    if autosize:
        w = min(req_w, max_w)
        h = min(req_h, max_h)
        x = max(0, (scr_w - w) // 2)
        y = max(0, (scr_h - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")


def _grid_entry_allows_only_numbers(proposed_value: str) -> bool:
    proposed = str(proposed_value or "").strip()
    return proposed == "" or proposed.isdigit()

def create_press_unit(
    parent,
    unit_label,
    use_cmyk=True,
    grid_rows=2,
    grid_cols=2,
    swatch_cols=2,
    cell_pad=0,
    midline_thickness=4,
    midline_color="#444444",
    unit_padding=(6, 6, 6, 6),
    cell_font=None,
    cell_width=None,
    swatch_size=(4, 1),
    section_choices=None,
):
    unit_frame = ttk.Frame(parent, style="Unit.TFrame", padding=unit_padding)

    section_var = tk.StringVar()
    section_entry = ttk.Combobox(
        unit_frame,
        width=8,
        justify="center",
        font=(None, 10),
        textvariable=section_var,
        values=section_choices or [""],
        state="readonly",
    )
    section_entry.pack(pady=(0, 6))

    box_frame = ttk.Frame(unit_frame, style="Box.TFrame")
    box_frame.pack(fill="both", expand=True)

    # Defaults
    if cell_font is None or cell_width is None:
        total_cells = grid_rows * grid_cols
        if grid_cols >= 8:
            default_font = (None, 9)
            default_width = 2
        elif grid_cols == 4:
            default_font = (None, 11)
            default_width = 4
        elif total_cells >= 16:
            default_font = (None, 9)
            default_width = 3
        else:
            default_font = (None, 11)
            default_width = 4
        cell_font = cell_font or default_font
        cell_width = cell_width or default_width

    # Divider insertion logic
    use_v_sep = (grid_cols % 2 == 0 and grid_cols > 1)
    use_h_sep = (grid_rows % 2 == 0 and grid_rows > 1)
    mid_col = grid_cols // 2
    mid_row = grid_rows // 2
    total_grid_cols = grid_cols + (1 if use_v_sep else 0)
    total_grid_rows = grid_rows + (1 if use_h_sep else 0)

    def map_col(c):
        return c + 1 if (use_v_sep and c >= mid_col) else c

    def map_row(r):
        return r + 1 if (use_h_sep and r >= mid_row) else r

    for r in range(total_grid_rows):
        if use_h_sep and r == mid_row:
            box_frame.rowconfigure(r, weight=0, minsize=midline_thickness)
        else:
            box_frame.rowconfigure(r, weight=1)

    for c in range(total_grid_cols):
        if use_v_sep and c == mid_col:
            box_frame.columnconfigure(c, weight=0, minsize=midline_thickness)
        else:
            box_frame.columnconfigure(c, weight=1)

    # ---- IMPORTANT: correct entries + overlays (aligned) ----
    grid_entries = []
    cell_overlays = []

    for r in range(grid_rows):
        row_entries = []
        row_overlays = []
        for c in range(grid_cols):
            cell_container = ttk.Frame(box_frame)
            cell_container.grid(row=map_row(r), column=map_col(c), sticky="nsew", padx=cell_pad, pady=cell_pad)

            validate_numbers_cmd = unit_frame.register(_grid_entry_allows_only_numbers)
            cell_entry = ttk.Entry(
                cell_container,
                justify="center",
                font=cell_font,
                width=cell_width,
                validate="key",
                validatecommand=(validate_numbers_cmd, "%P"),
            )
            cell_entry._press_grid_cell = True
            cell_entry.pack(fill="both", expand=True)

            overlay = tk.Canvas(cell_container, highlightthickness=0, bg="#ffffff", takefocus=False)
            overlay.place_forget()
            overlay._shown = False
            overlay._circle_id = None

            row_entries.append(cell_entry)
            row_overlays.append(overlay)

        grid_entries.append(row_entries)
        cell_overlays.append(row_overlays)

    # Divider visuals
    if use_v_sep:
        if use_h_sep:
            tk.Frame(box_frame, bg=midline_color).grid(row=0, column=mid_col, rowspan=mid_row, sticky="nsew")
            tk.Frame(box_frame, bg=midline_color).grid(
                row=mid_row + 1, column=mid_col,
                rowspan=total_grid_rows - (mid_row + 1),
                sticky="nsew"
            )
        else:
            tk.Frame(box_frame, bg=midline_color).grid(row=0, column=mid_col, rowspan=total_grid_rows, sticky="nsew")

    if use_h_sep:
        if use_v_sep:
            tk.Frame(box_frame, bg=midline_color).grid(row=mid_row, column=0, columnspan=mid_col, sticky="nsew")
            tk.Frame(box_frame, bg=midline_color).grid(
                row=mid_row, column=mid_col + 1,
                columnspan=total_grid_cols - (mid_col + 1),
                sticky="nsew"
            )
            tk.Frame(box_frame, bg=midline_color).grid(row=mid_row, column=mid_col, sticky="nsew")
        else:
            tk.Frame(box_frame, bg=midline_color).grid(row=mid_row, column=0, columnspan=total_grid_cols, sticky="nsew")

    ttk.Label(unit_frame, text=unit_label, font=(None, 10, "bold")).pack(pady=(6, 0))

    # Color swatches
    color_frame = ttk.Frame(unit_frame)
    color_frame.pack(pady=(6, 0), fill="x")

    if use_cmyk:
        colors = [("K", "#7f7f7f"), ("Y", "#fff176"), ("M", "#f48fb1"), ("C", "#90caf9")]
    else:
        colors = [("K", "#7f7f7f")]

    sw_w, sw_h = swatch_size
    unit_bg = ttk.Style(unit_frame).lookup("Unit.TFrame", "background") or "#f0f0f0"

    for key, color in colors:
        row_frame = tk.Frame(color_frame, bg=unit_bg, height=24)
        row_frame.pack(fill="x", pady=1)
        row_frame.pack_propagate(False)

        swatch_container = tk.Frame(row_frame, bg=unit_bg)
        swatch_container.place(relx=0.5, rely=0.5, anchor="center")

        text_color = _contrast_text_color(color)

        for i in range(swatch_cols):
            swatch = tk.Label(
                swatch_container,
                text=key,
                fg=text_color,
                bg=color,
                font=(None, 9, "bold"),
                relief="solid",
                borderwidth=1,
                width=sw_w,
                height=sw_h,
            )
            swatch.pack(side="left")
            if i != swatch_cols - 1:
                tk.Frame(swatch_container, bg=midline_color, width=midline_thickness, height=18).pack(side="left", padx=1)

    return unit_frame, section_entry, grid_entries, cell_overlays

# =============================================================================
# Preview image cache and capture helpers
# Preview image pathing, cache signatures, loading, resizing, screen capture fallback, and preview image saves.
# =============================================================================

_PREVIEW_IMAGE_CACHE = {}


def _preview_file_signature(path: str):
    if not path:
        return None
    try:
        stat = os.stat(path)
    except Exception:
        return None
    return (
        int(getattr(stat, "st_mtime_ns", int(float(getattr(stat, "st_mtime", 0.0)) * 1000000000))),
        int(getattr(stat, "st_ctime_ns", int(float(getattr(stat, "st_ctime", 0.0)) * 1000000000))),
        int(getattr(stat, "st_size", 0)),
    )


def _preview_file_signature_for_json(json_path: str):
    parsed = _db_parse_virtual_path(json_path) if callable(_db_parse_virtual_path) else None
    if parsed and parsed.get('file_name'):
        row = _db_read_record(parsed['record_type'], parsed['file_name']) if callable(_db_read_record) else None
        if row:
            updated_at = row.get('updated_at')
            if updated_at is not None:
                return ('db', str(updated_at))
        return None
    return _preview_file_signature(preview_image_path_for_json(json_path))


def _clear_preview_image_cache_entry(json_path: str):
    path = preview_image_path_for_json(json_path)
    if not path:
        return
    try:
        _PREVIEW_IMAGE_CACHE.pop(path, None)
    except Exception:
        pass


def _store_preview_image_in_cache(json_path: str, image):
    path = preview_image_path_for_json(json_path)
    if not path or image is None:
        return
    signature = _preview_file_signature(path)
    if signature is None:
        return
    try:
        cached_image = image.copy()
    except Exception:
        cached_image = image
    _PREVIEW_IMAGE_CACHE[path] = {
        "signature": signature,
        "image": cached_image,
    }


def preview_image_path_for_json(json_path: str) -> str:
    base, _ = os.path.splitext(str(json_path or ""))
    return base + ".preview.png"


def remove_preview_image_for_json(json_path: str):
    path = preview_image_path_for_json(json_path)
    _clear_preview_image_cache_entry(json_path)
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def load_preview_image_for_json(json_path: str):
    try:
        from PIL import Image
    except Exception:
        return None
    path = preview_image_path_for_json(json_path)
    if not path:
        return None
    signature = _preview_file_signature(path)
    if signature is None:
        _clear_preview_image_cache_entry(json_path)
        return None
    cached = _PREVIEW_IMAGE_CACHE.get(path)
    if isinstance(cached, dict) and cached.get("signature") == signature and cached.get("image") is not None:
        try:
            return cached["image"].copy()
        except Exception:
            return cached.get("image")
    try:
        with Image.open(path) as img:
            loaded = img.copy()
        _PREVIEW_IMAGE_CACHE[path] = {
            "signature": signature,
            "image": loaded.copy(),
        }
        return loaded
    except Exception:
        _PREVIEW_IMAGE_CACHE.pop(path, None)
        return None


def _resize_preview_image_helper(image, scale=0.75):
    try:
        from PIL import Image
    except Exception as e:
        raise RuntimeError(f"Pillow is required for previews: {e}")
    if image is None:
        return None
    try:
        scale = float(scale)
    except Exception:
        scale = 0.75
    scale = max(0.1, min(1.0, scale))
    width, height = image.size
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    if new_size == image.size:
        return image
    return image.resize(new_size, Image.LANCZOS)


def _capture_window_image_for_preview(win):
    try:
        from PIL import ImageGrab
    except Exception as e:
        raise RuntimeError(f"Pillow ImageGrab is required for previews: {e}")

    try:
        win.update_idletasks()
        win.lift()
        try:
            win.attributes("-topmost", True)
            win.update()
            win.attributes("-topmost", False)
        except Exception:
            pass
    except Exception:
        pass

    try:
        left = int(win.winfo_rootx())
        top = int(win.winfo_rooty())
        width = max(1, int(win.winfo_width()))
        height = max(1, int(win.winfo_height()))
    except Exception:
        raise RuntimeError("Could not determine preview window bounds.")

    bbox = (left, top, left + width, top + height)
    image = None
    try:
        image = ImageGrab.grab(bbox=bbox, all_screens=True)
    except Exception:
        image = None

    if image is None and os.name == 'nt':
        try:
            import ctypes
            from ctypes import wintypes
            from PIL import Image

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            hwnd = wintypes.HWND(int(win.winfo_id()))

            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

            rect_raw = RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect_raw)):
                raise RuntimeError("GetWindowRect failed")
            width = max(1, rect_raw.right - rect_raw.left)
            height = max(1, rect_raw.bottom - rect_raw.top)

            hwnd_dc = user32.GetWindowDC(hwnd)
            mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
            bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
            old_obj = gdi32.SelectObject(mem_dc, bitmap)

            PW_RENDERFULLCONTENT = 0x00000002
            result = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
            if result != 1:
                result = user32.PrintWindow(hwnd, mem_dc, 0)
            if result != 1:
                raise RuntimeError("PrintWindow failed")

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD),
                    ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD),
                ]

            class BITMAPINFO(ctypes.Structure):
                _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = width
            bmi.bmiHeader.biHeight = -height
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = 0

            buffer_len = width * height * 4
            buffer = ctypes.create_string_buffer(buffer_len)
            rows = gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(bmi), 0)
            if rows == 0:
                raise RuntimeError("GetDIBits failed")
            image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1).convert("RGB")

            gdi32.SelectObject(mem_dc, old_obj)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hwnd_dc)
        except Exception:
            image = None

    if image is None:
        raise RuntimeError("Could not capture layout preview image.")
    return image


def save_window_preview_image(win, json_path: str, scale=0.75):
    if not win or not json_path:
        return None
    image = None
    try:
        builder = getattr(win, "build_preview_image", None)
        if callable(builder):
            image = builder(scale=scale)
    except Exception:
        image = None
    if image is None:
        try:
            print_builder = getattr(win, "build_print_image", None)
            if callable(print_builder):
                image = print_builder()
                if image is not None:
                    image = image.crop((0, 0, image.width, max(1, int(image.height * 0.5))))
                    image = _resize_preview_image_helper(image, scale=scale)
        except Exception:
            image = None
    if image is None:
        image = _capture_window_image_for_preview(win)
        image = _resize_preview_image_helper(image, scale=scale)
    out_path = preview_image_path_for_json(json_path)
    ensure_dir(os.path.dirname(out_path))
    image.save(out_path, format="PNG")
    try:
        _store_preview_image_in_cache(json_path, image)
    except Exception:
        pass
    return out_path

# =============================================================================
# Window and treeview state memory
# Per-user window geometry, monitor placement, tree expansion, selection, sort order, scroll position, and column width persistence.
# =============================================================================

WINDOW_STATE_DIRNAME = "Press Layout"
WINDOW_STATE_FILENAME = "window_state.json"
WINDOW_DEBUG_FILENAME = "window_state_debug.log"


def user_config_dir() -> str:
    base = (
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("APPDATA")
        or os.path.expanduser("~")
    )
    path = os.path.join(base, WINDOW_STATE_DIRNAME)
    ensure_dir(path)
    return path


def window_state_file_path() -> str:
    return os.path.join(user_config_dir(), WINDOW_STATE_FILENAME)


def window_debug_file_path() -> str:
    return os.path.join(user_config_dir(), WINDOW_DEBUG_FILENAME)


def append_window_debug_log(event_type: str, state_key: str, payload=None):
    try:
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "event": str(event_type or ""),
            "state_key": str(state_key or ""),
            "payload": payload if isinstance(payload, dict) else {"value": payload},
        }
        ensure_dir(user_config_dir())
        with open(window_debug_file_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


_WINDOW_STATE_CACHE = {
    "signature": None,
    "state": {},
}
_WINDOW_STATE_CACHE_LOCK = threading.RLock()


def _window_state_file_signature():
    try:
        stat = os.stat(window_state_file_path())
    except Exception:
        return None
    return (
        int(getattr(stat, "st_mtime_ns", int(float(getattr(stat, "st_mtime", 0.0)) * 1000000000))),
        int(getattr(stat, "st_size", 0)),
    )


def _clone_window_state(state_map):
    try:
        return json.loads(json.dumps(state_map if isinstance(state_map, dict) else {}))
    except Exception:
        return dict(state_map) if isinstance(state_map, dict) else {}


def load_window_state_map():
    with _WINDOW_STATE_CACHE_LOCK:
        signature = _window_state_file_signature()
        if signature != _WINDOW_STATE_CACHE.get("signature"):
            data = safe_read_json(window_state_file_path())
            _WINDOW_STATE_CACHE["state"] = data if isinstance(data, dict) else {}
            _WINDOW_STATE_CACHE["signature"] = signature
        return _clone_window_state(_WINDOW_STATE_CACHE.get("state", {}))


def save_window_state_map(state_map):
    if not isinstance(state_map, dict):
        return
    with _WINDOW_STATE_CACHE_LOCK:
        path = window_state_file_path()
        safe_write_json(path, state_map)
        _WINDOW_STATE_CACHE["state"] = _clone_window_state(state_map)
        _WINDOW_STATE_CACHE["signature"] = _window_state_file_signature()


def load_treeview_state(state_key: str, tree_key: str):
    state_map = load_window_state_map()
    window_state = state_map.get(state_key)
    if not isinstance(window_state, dict):
        return None
    treeview_state = window_state.get("treeview_state")
    if not isinstance(treeview_state, dict):
        return None
    state = treeview_state.get(tree_key)
    return dict(state) if isinstance(state, dict) else None


def save_treeview_state(state_key: str, tree_key: str, updates=None, replace=False):
    updates = updates if isinstance(updates, dict) else {}
    state_map = load_window_state_map()
    window_state = state_map.get(state_key)
    if not isinstance(window_state, dict):
        window_state = {}
    treeview_state = window_state.get("treeview_state")
    if not isinstance(treeview_state, dict):
        treeview_state = {}
    existing = treeview_state.get(tree_key)
    merged = {} if replace or not isinstance(existing, dict) else dict(existing)
    merged.update(updates)
    treeview_state[tree_key] = merged
    window_state["treeview_state"] = treeview_state
    state_map[state_key] = window_state
    save_window_state_map(state_map)
    return merged


def capture_treeview_group_state(tree):
    open_iids = set()

    def _walk(parent=""):
        try:
            children = tree.get_children(parent)
        except Exception:
            children = ()
        for iid in children:
            try:
                child_ids = tree.get_children(iid)
            except Exception:
                child_ids = ()
            if child_ids:
                try:
                    if bool(tree.item(iid, "open")):
                        open_iids.add(str(iid))
                except Exception:
                    pass
                _walk(iid)

    _walk("")
    return sorted(open_iids)


def capture_treeview_column_widths(tree, columns=None):
    widths = {}
    for col in tuple(columns or ()):
        try:
            widths[str(col)] = int(tree.column(col, "width"))
        except Exception:
            continue
    return widths


def capture_treeview_runtime_state(tree, columns=None):
    state = {
        "open_iids": capture_treeview_group_state(tree),
        "selected_iids": [str(iid) for iid in tree.selection()],
        "focus_iid": str(tree.focus() or "").strip() or None,
    }
    try:
        state["yview"] = [float(value) for value in tree.yview()]
    except Exception:
        pass
    widths = capture_treeview_column_widths(tree, columns=columns)
    if widths:
        state["column_widths"] = widths
    return state


def get_treeview_reload_state(tree, state_key: str, tree_key: str, columns=None):
    try:
        has_runtime_items = bool(tree.get_children(""))
    except Exception:
        has_runtime_items = False
    if has_runtime_items:
        return capture_treeview_runtime_state(tree, columns=columns), True
    saved_state = load_treeview_state(state_key, tree_key)
    if isinstance(saved_state, dict):
        return dict(saved_state), True
    return {}, False


def apply_treeview_column_width_state(tree, columns, state_key: str, tree_key: str):
    state = load_treeview_state(state_key, tree_key)
    column_widths = state.get("column_widths") if isinstance(state, dict) else None
    if not isinstance(column_widths, dict):
        return
    for col in tuple(columns or ()):
        if str(col) not in column_widths:
            continue
        try:
            width = int(column_widths.get(str(col), 0) or 0)
        except Exception:
            width = 0
        if width <= 0:
            continue
        try:
            tree.column(col, width=width)
        except Exception:
            pass


def load_treeview_sort_state(state_key: str, tree_key: str, default_col: str):
    state = load_treeview_state(state_key, tree_key)
    saved = state.get("sort") if isinstance(state, dict) else None
    if not isinstance(saved, dict):
        return {"col": default_col, "desc": False}
    col = str(saved.get("col") or default_col).strip() or default_col
    desc = bool(saved.get("desc", False))
    return {"col": col, "desc": desc}


def save_treeview_sort_state(state_key: str, tree_key: str, sort_state):
    if not isinstance(sort_state, dict):
        return
    save_treeview_state(
        state_key,
        tree_key,
        {
            "sort": {
                "col": str(sort_state.get("col") or "").strip(),
                "desc": bool(sort_state.get("desc", False)),
            }
        },
    )


def open_treeview_item_ancestors(tree, iid):
    current = str(iid or "").strip()
    while current:
        try:
            parent = tree.parent(current)
        except Exception:
            break
        if not parent:
            break
        try:
            tree.item(parent, open=True)
        except Exception:
            pass
        current = parent


def bind_treeview_state_memory(win, state_key: str, tree_key: str, tree, columns=None):
    bound_key = f"{state_key}::{tree_key}"
    if getattr(tree, "_treeview_state_memory_key", None) == bound_key:
        return
    tree._treeview_state_memory_key = bound_key
    pending = {"id": None}
    columns = tuple(columns or ())

    def _save_now():
        try:
            if not tree.winfo_exists():
                return
        except Exception:
            return
        save_treeview_state(
            state_key,
            tree_key,
            capture_treeview_runtime_state(tree, columns=columns),
        )

    def _commit():
        pending["id"] = None
        _save_now()

    def _schedule(_event=None):
        try:
            if pending["id"] is not None:
                tree.after_cancel(pending["id"])
            pending["id"] = tree.after(150, _commit)
        except Exception:
            pass

    def _on_destroy(event=None):
        try:
            if event is not None and event.widget is not tree:
                return
        except Exception:
            pass
        _save_now()

    try:
        tree.bind("<<TreeviewSelect>>", _schedule, add="+")
        tree.bind("<<TreeviewOpen>>", _schedule, add="+")
        tree.bind("<<TreeviewClose>>", _schedule, add="+")
        tree.bind("<ButtonRelease-1>", _schedule, add="+")
        tree.bind("<KeyRelease>", _schedule, add="+")
        tree.bind("<Destroy>", _on_destroy, add="+")
    except Exception:
        pass
    return _save_now


def parse_geometry_string(geometry: str):
    if not geometry:
        return None
    text = str(geometry).strip()
    # Tk can report a negative X position as '+-1166+265' when a window is on
    # a monitor left of the primary display. Normalize those forms first.
    text = text.replace('+-', '-').replace('-+', '-').replace('++', '+')
    m = re.match(r'^(\d+)x(\d+)([+-]\d+)([+-]\d+)$', text)
    if not m:
        return None
    try:
        return {
            "width": int(m.group(1)),
            "height": int(m.group(2)),
            "x": int(m.group(3)),
            "y": int(m.group(4)),
        }
    except Exception:
        return None


def _monitor_rects_win32():
    if os.name != 'nt':
        return []
    try:
        import ctypes
        from ctypes import wintypes

        MONITORINFOF_PRIMARY = 1

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        user32 = ctypes.windll.user32
        monitors = []
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )

        def _callback(hmonitor, _hdc, _lprc, _lparam):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                work = info.rcWork
                monitors.append({
                    "left": int(work.left),
                    "top": int(work.top),
                    "right": int(work.right),
                    "bottom": int(work.bottom),
                    "primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
                })
            return 1

        user32.EnumDisplayMonitors(0, 0, callback_type(_callback), 0)
        return monitors
    except Exception as exc:
        append_window_debug_log("monitor_enum_error", "", {"error": str(exc)})
        return []


def _monitor_signature(monitor):
    return {
        "left": int(monitor["left"]),
        "top": int(monitor["top"]),
        "right": int(monitor["right"]),
        "bottom": int(monitor["bottom"]),
        "primary": bool(monitor.get("primary", False)),
    }


def _monitor_width(monitor):
    return max(1, int(monitor["right"]) - int(monitor["left"]))


def _monitor_height(monitor):
    return max(1, int(monitor["bottom"]) - int(monitor["top"]))


def _rect_intersection_area(a, b):
    left = max(a["left"], b["left"])
    top = max(a["top"], b["top"])
    right = min(a["right"], b["right"])
    bottom = min(a["bottom"], b["bottom"])
    if right <= left or bottom <= top:
        return 0
    return (right - left) * (bottom - top)


def _find_best_monitor_for_rect(rect, monitors):
    if not monitors:
        return None
    best = None
    best_area = -1
    for monitor in monitors:
        area = _rect_intersection_area(rect, monitor)
        if area > best_area:
            best_area = area
            best = monitor
    if best is not None and best_area > 0:
        return best
    center_x = (rect["left"] + rect["right"]) / 2.0
    center_y = (rect["top"] + rect["bottom"]) / 2.0
    best = monitors[0]
    best_dist = None
    for monitor in monitors:
        mon_center_x = (monitor["left"] + monitor["right"]) / 2.0
        mon_center_y = (monitor["top"] + monitor["bottom"]) / 2.0
        dist = (center_x - mon_center_x) ** 2 + (center_y - mon_center_y) ** 2
        if best_dist is None or dist < best_dist:
            best = monitor
            best_dist = dist
    return best


def _match_saved_monitor(saved_monitor, monitors):
    if not saved_monitor or not monitors:
        return None
    for monitor in monitors:
        if all(int(monitor.get(key, 0)) == int(saved_monitor.get(key, 0)) for key in ("left", "top", "right", "bottom")):
            return monitor
    saved_width = int(saved_monitor.get("right", 0)) - int(saved_monitor.get("left", 0))
    saved_height = int(saved_monitor.get("bottom", 0)) - int(saved_monitor.get("top", 0))
    same_shape = [m for m in monitors if _monitor_width(m) == saved_width and _monitor_height(m) == saved_height]
    if same_shape:
        saved_left = int(saved_monitor.get("left", 0))
        saved_top = int(saved_monitor.get("top", 0))
        same_shape.sort(key=lambda m: abs(int(m["left"]) - saved_left) + abs(int(m["top"]) - saved_top))
        return same_shape[0]
    primary = [m for m in monitors if bool(m.get("primary", False))]
    return primary[0] if primary else monitors[0]


def _capture_window_state(win):
    parsed = parse_geometry_string(win.geometry())
    if not parsed:
        return None
    state = dict(parsed)
    monitors = _monitor_rects_win32()
    if monitors:
        rect = {
            "left": parsed["x"],
            "top": parsed["y"],
            "right": parsed["x"] + parsed["width"],
            "bottom": parsed["y"] + parsed["height"],
        }
        monitor = _find_best_monitor_for_rect(rect, monitors)
        if monitor:
            state["monitor"] = _monitor_signature(monitor)
            state["rel_x"] = parsed["x"] - int(monitor["left"])
            state["rel_y"] = parsed["y"] - int(monitor["top"])
            state["rel_x_ratio"] = state["rel_x"] / max(1, _monitor_width(monitor) - parsed["width"])
            state["rel_y_ratio"] = state["rel_y"] / max(1, _monitor_height(monitor) - parsed["height"])
    return state


def normalize_window_state_for_display(win, state):
    if not isinstance(state, dict):
        return None
    try:
        parsed = {
            "width": max(160, int(state.get("width", 0))),
            "height": max(120, int(state.get("height", 0))),
            "x": int(state.get("x", 0)),
            "y": int(state.get("y", 0)),
        }
    except Exception:
        return None
    monitors = _monitor_rects_win32()
    if monitors:
        saved_monitor = state.get("monitor") if isinstance(state.get("monitor"), dict) else None
        target_monitor = _match_saved_monitor(saved_monitor, monitors)
        if target_monitor is None:
            rect = {
                "left": parsed["x"],
                "top": parsed["y"],
                "right": parsed["x"] + parsed["width"],
                "bottom": parsed["y"] + parsed["height"],
            }
            target_monitor = _find_best_monitor_for_rect(rect, monitors)
        if target_monitor is None:
            target_monitor = monitors[0]
        parsed["width"] = min(parsed["width"], _monitor_width(target_monitor))
        parsed["height"] = min(parsed["height"], _monitor_height(target_monitor))
        available_x = max(0, _monitor_width(target_monitor) - parsed["width"])
        available_y = max(0, _monitor_height(target_monitor) - parsed["height"])
        rel_x = state.get("rel_x")
        rel_y = state.get("rel_y")
        rel_x_ratio = state.get("rel_x_ratio")
        rel_y_ratio = state.get("rel_y_ratio")
        if rel_x is None and rel_x_ratio is not None:
            rel_x = int(round(float(rel_x_ratio) * available_x))
        if rel_y is None and rel_y_ratio is not None:
            rel_y = int(round(float(rel_y_ratio) * available_y))
        if rel_x is None:
            rel_x = parsed["x"] - int(target_monitor["left"])
        if rel_y is None:
            rel_y = parsed["y"] - int(target_monitor["top"])
        rel_x = max(0, min(int(rel_x), available_x))
        rel_y = max(0, min(int(rel_y), available_y))
        parsed["x"] = int(target_monitor["left"]) + rel_x
        parsed["y"] = int(target_monitor["top"]) + rel_y
        return parsed
    return parsed


def restore_window_geometry(win, state_key: str, default_geometry=None, minsize=None):
    if minsize:
        try:
            win.minsize(int(minsize[0]), int(minsize[1]))
        except Exception:
            pass

    hidden_for_restore = False
    try:
        hidden_for_restore = str(win.state()) == "withdrawn"
        if not hidden_for_restore:
            win.withdraw()
            hidden_for_restore = True
    except Exception:
        hidden_for_restore = False

    if default_geometry:
        try:
            win.geometry(default_geometry)
        except Exception:
            pass

    def _finish_show():
        try:
            win.update_idletasks()
        except Exception:
            pass
        if hidden_for_restore:
            try:
                win.deiconify()
            except Exception:
                pass

    def _apply_saved_geometry():
        state_map = load_window_state_map()
        saved = state_map.get(state_key)
        if saved:
            normalized = normalize_window_state_for_display(win, saved)
            if normalized:
                try:
                    # Instead of forcing the saved width/height, keep the window
                    # sized to its requested content size but position it at the
                    # saved x,y so the last saved position is respected.
                    try:
                        win.update_idletasks()
                    except Exception:
                        pass
                    req_w = win.winfo_reqwidth() if hasattr(win, 'winfo_reqwidth') else normalized["width"]
                    req_h = win.winfo_reqheight() if hasattr(win, 'winfo_reqheight') else normalized["height"]
                    # clamp to current screen size to avoid off-screen sizing
                    try:
                        screen_w = win.winfo_screenwidth()
                        screen_h = win.winfo_screenheight()
                    except Exception:
                        screen_w = normalized.get("width", req_w)
                        screen_h = normalized.get("height", req_h)
                    w = min(req_w, max(100, screen_w))
                    h = min(req_h, max(100, screen_h))
                    win.geometry(f'{w}x{h}+{normalized["x"]}+{normalized["y"]}')
                except Exception:
                    pass
        _finish_show()

    try:
        win.after_idle(_apply_saved_geometry)
    except Exception:
        _apply_saved_geometry()

def track_window_geometry(win, state_key: str):
    if getattr(win, "_window_state_tracking_key", None) == state_key:
        return
    win._window_state_tracking_key = state_key
    pending = {"id": None}

    def _save_now():
        try:
            if not win.winfo_exists() or str(win.state()) in ("iconic", "withdrawn"):
                return
            state = _capture_window_state(win)
            append_window_debug_log("save_attempt", state_key, {"geometry": win.geometry(), "state": state, "monitors": _monitor_rects_win32()})
            if not state:
                append_window_debug_log("save_parse_failed", state_key, {"geometry": win.geometry()})
                return
            state_map = load_window_state_map()
            existing_state = state_map.get(state_key)
            merged_state = dict(existing_state) if isinstance(existing_state, dict) else {}
            merged_state.update(state)
            state_map[state_key] = merged_state
            save_window_state_map(state_map)
            append_window_debug_log("save_applied", state_key, {"state": state})
        except Exception as exc:
            append_window_debug_log("save_error", state_key, {"error": str(exc)})

    def _commit():
        pending["id"] = None
        _save_now()

    def _schedule(_event=None):
        try:
            if pending["id"] is not None:
                win.after_cancel(pending["id"])
            pending["id"] = win.after(250, _commit)
        except Exception:
            pass

    def _on_destroy(event=None):
        try:
            if event is not None and event.widget is not win:
                return
        except Exception:
            pass
        _save_now()

    try:
        win.bind("<Configure>", _schedule, add="+")
        win.bind("<Map>", _schedule, add="+")
        win.bind("<Destroy>", _on_destroy, add="+")
        win.after(300, _save_now)
    except Exception:
        pass


def remember_window_geometry(win, state_key: str, default_geometry=None, minsize=None):
    append_window_debug_log("remember_window_geometry", state_key, {"default_geometry": default_geometry, "minsize": list(minsize) if minsize else None})
    restore_window_geometry(win, state_key, default_geometry=default_geometry, minsize=minsize)
    track_window_geometry(win, state_key)
    return state_key

# =============================================================================
# Save, validation, and persistence helpers
# Editor data normalization, required-field validation, layout/template/regular saves, and preview maintenance.
# =============================================================================

def _set_widget_value(widget, value):
    """Set Entry/Combobox-like widget text safely."""
    value = "" if value is None else str(value).strip()
    try:
        widget.set(value)
        return
    except Exception:
        pass
    try:
        widget.delete(0, "end")
        widget.insert(0, value)
    except Exception:
        pass

def _normalize_template_data(data):
    """Canonicalize template section names/assignments to S1..S4 style."""
    if not isinstance(data, dict):
        return data
    normalized = dict(data)
    try:
        section_count = max(1, min(4, int(normalized.get("section_count", 1))))
    except Exception:
        section_count = 1
    source_names = normalized.get("section_names") or []
    canonical_names = [f"S{i+1}" for i in range(section_count)]
    alias_to_canonical = {}
    for i in range(section_count):
        canonical = canonical_names[i]
        alias_to_canonical[canonical.upper()] = canonical
        alias_to_canonical[str(i + 1)] = canonical
        alias_to_canonical[chr(ord('A') + i)] = canonical
        try:
            existing_name = (source_names[i] or "").strip().upper()
        except Exception:
            existing_name = ""
        if existing_name:
            alias_to_canonical[existing_name] = canonical
    normalized["section_names"] = canonical_names
    normalized_units = []
    for unit in normalized.get("units", []):
        if not isinstance(unit, dict):
            normalized_units.append(unit)
            continue
        updated = dict(unit)
        section_text = str(updated.get("section", "") or "").strip()
        if section_text:
            canonical = alias_to_canonical.get(section_text.upper())
            if canonical is None:
                section_id = parse_section_id(section_text)
                if section_id is not None and 1 <= section_id <= section_count:
                    canonical = f"S{section_id}"
            updated["section"] = canonical or section_text
        else:
            updated["section"] = ""
        normalized_units.append(updated)

    # Templates should be page-number independent.  When a layout is saved as a
    # template, remap every populated section to 1..N based on that section's
    # actual page order.  Examples: 3-16 becomes 1-14, and 1-12 plus 29-40
    # becomes 1-24.
    pages_by_section = {f"S{i+1}": set() for i in range(section_count)}
    for unit in normalized_units:
        if not isinstance(unit, dict):
            continue
        section_name = str(unit.get("section") or "").strip().upper()
        if section_name not in pages_by_section:
            continue
        for row in (unit.get("grid") or []):
            if not isinstance(row, list):
                continue
            for cell_value in row:
                try:
                    page_number = int(str(cell_value or "").strip())
                except Exception:
                    continue
                pages_by_section[section_name].add(page_number)

    page_maps = {}
    normalized_section_pages = []
    source_pages = normalized.get("section_pages") if isinstance(normalized.get("section_pages"), list) else []
    for i in range(section_count):
        section_name = f"S{i+1}"
        ordered_pages = sorted(pages_by_section.get(section_name, set()))
        page_maps[section_name] = {page_number: str(idx + 1) for idx, page_number in enumerate(ordered_pages)}
        if ordered_pages:
            normalized_section_pages.append(len(ordered_pages))
        else:
            try:
                normalized_section_pages.append(int(source_pages[i]))
            except Exception:
                normalized_section_pages.append(0)

    for unit in normalized_units:
        if not isinstance(unit, dict):
            continue
        section_name = str(unit.get("section") or "").strip().upper()
        remap = page_maps.get(section_name) or {}
        if not remap:
            continue
        grid = unit.get("grid") or []
        if not isinstance(grid, list):
            continue
        for row in grid:
            if not isinstance(row, list):
                continue
            for cell_index, cell_value in enumerate(row):
                try:
                    page_number = int(str(cell_value or "").strip())
                except Exception:
                    continue
                if page_number in remap:
                    row[cell_index] = remap[page_number]

    normalized["section_pages"] = normalized_section_pages
    normalized["units"] = normalized_units
    return normalized

def _save_preview_image_for_window(win, json_path, scale=0.75):
    if not win or not json_path:
        return
    try:
        win.update_idletasks()
    except Exception:
        pass
    try:
        builder = getattr(win, "build_preview_image", None)
        if callable(builder):
            image = builder(scale=scale)
            if image is not None:
                out_path = preview_image_path_for_json(json_path)
                ensure_dir(os.path.dirname(out_path))
                image.save(out_path, format="PNG")
                return
    except Exception:
        pass
    try:
        save_window_preview_image(win, json_path, scale=scale)
    except Exception:
        pass


def _save_preview_for_current_window(win, json_path):
    _save_preview_image_for_window(win, json_path, scale=0.75)


def _save_preview_for_saved_template(ctx, template_path):
    if not template_path:
        return
    try:
        data = safe_read_json(template_path)
        if not isinstance(data, dict):
            return
        press = data.get("press") or ""
        fmt = data.get("format") or ""
        cfg = CONFIG_MAP.get((press, fmt))
        if not cfg:
            return
        image = render_layout_preview_image_from_data(
            data,
            dict(cfg),
            scale=0.75,
            title_base=f"{press} - {fmt}",
            template_mode=True,
        )
        if image is None:
            return
        out_path = preview_image_path_for_json(template_path)
        ensure_dir(os.path.dirname(out_path))
        image.save(out_path, format="PNG")
    except Exception:
        pass


def _unit_has_assigned_pages(unit_ctx) -> bool:
    for row in unit_ctx.get("entries", []):
        for cell in row:
            try:
                if (cell.get() or "").strip():
                    return True
            except Exception:
                continue
    return False


def _ctx_is_regular_mode(ctx) -> bool:
    if bool(ctx.get("regular_mode", False)):
        return True
    default_dir = str(ctx.get("default_dir") or "").strip()
    if not default_dir:
        return False
    try:
        return os.path.abspath(default_dir) == os.path.abspath(REGULAR_DIR)
    except Exception:
        return False


def _ctx_file_type_name(ctx) -> str:
    if bool(ctx.get("template_mode", False)):
        return "template"
    if _ctx_is_regular_mode(ctx):
        return "regular"
    return "layout"


def _normalize_ctx_publication_entry(ctx):
    product_entry = ctx.get("product_entry")
    if not product_entry:
        return ""
    try:
        raw_value = product_entry.get()
    except Exception:
        raw_value = ""
    normalized = normalize_publication_name(raw_value)
    try:
        current_value = product_entry.get()
    except Exception:
        current_value = raw_value
    if current_value != normalized:
        try:
            product_entry.state(["!disabled"])
        except Exception:
            pass
        try:
            product_entry.delete(0, "end")
            product_entry.insert(0, normalized)
        except Exception:
            pass
        if bool(ctx.get("template_mode", False)):
            try:
                product_entry.state(["disabled"])
            except Exception:
                pass
    return normalized


def _normalize_ctx_issue_date_entry(ctx):
    issue_entry = ctx.get("issue_entry")
    if not issue_entry:
        return ""
    try:
        raw_value = (issue_entry.get() or "").strip()
    except Exception:
        raw_value = ""
    if not raw_value:
        return ""
    dt = parse_issue_date_flexible(raw_value)
    if not dt:
        return raw_value
    normalized = dt.strftime("%m/%d/%Y")
    try:
        current_value = (issue_entry.get() or "").strip()
    except Exception:
        current_value = raw_value
    if current_value != normalized:
        try:
            issue_entry.state(["!disabled"])
        except Exception:
            pass
        try:
            issue_entry.delete(0, "end")
            issue_entry.insert(0, normalized)
        except Exception:
            pass
        if bool(ctx.get("template_mode", False)) or _ctx_is_regular_mode(ctx):
            try:
                issue_entry.state(["disabled"])
            except Exception:
                pass
    return normalized


def _invalid_grid_cells_from_data(data):
    invalid = []
    for unit in (data.get("units", []) or []):
        label = str(unit.get("label") or "Unit")
        grid = unit.get("grid", []) or []
        for row_index, row in enumerate(grid, start=1):
            row_values = row if isinstance(row, list) else []
            for col_index, cell in enumerate(row_values, start=1):
                value = str(cell or "").strip()
                if value and (not value.isdigit()):
                    invalid.append((label, row_index, col_index, value))
    return invalid


def _units_missing_sections_from_data(data):
    offenders = []
    for unit in (data.get("units", []) or []):
        label = str(unit.get("label") or "Unit")
        section_value = str(unit.get("section") or "").strip()
        if section_value:
            continue
        has_values = False
        for row in (unit.get("grid", []) or []):
            row_values = row if isinstance(row, list) else []
            for cell in row_values:
                if str(cell or "").strip():
                    has_values = True
                    break
            if has_values:
                break
        if has_values:
            offenders.append(label)
    return offenders


def validate_layout_data_for_mode(data, template_mode=False, regular_mode=False):
    if not isinstance(data, dict):
        return ["Could not read layout data."]

    errors = []
    file_type = "template" if template_mode else ("regular" if regular_mode else "layout")

    raw_issue = str(data.get("issue_date") or "").strip()
    raw_product = str(data.get("product") or "").strip()

    if not template_mode:
        normalized_product = normalize_publication_name(raw_product)
        data["product"] = normalized_product
        if not normalized_product:
            errors.append(f"{file_type.capitalize()}s require a publication name.")

        if raw_issue:
            dt = parse_issue_date_flexible(raw_issue)
            if not dt:
                errors.append("Issue Date must be a valid date.")
            else:
                data["issue_date"] = dt.strftime("%m/%d/%Y")
        elif not regular_mode:
            errors.append("Layouts require an issue date.")
    else:
        data["issue_date"] = raw_issue
        data["product"] = normalize_publication_name(raw_product)

    invalid_cells = _invalid_grid_cells_from_data(data)
    if invalid_cells:
        preview_items = [f"{label} r{row} c{col} ({value})" for label, row, col, value in invalid_cells[:12]]
        suffix = "" if len(invalid_cells) <= 12 else f" and {len(invalid_cells) - 12} more"
        errors.append("Grid cells may only contain numbers. Invalid cells: " + ", ".join(preview_items) + suffix + ".")

    missing_sections = _units_missing_sections_from_data(data)
    if missing_sections:
        errors.append("All units with pages assigned must be assigned a section before saving. Units missing a section: " + ", ".join(missing_sections) + ".")

    return errors


def validate_layout_ctx_before_save(ctx, parent=None):
    if not bool(ctx.get("template_mode", False)):
        _normalize_ctx_publication_entry(ctx)
    if not bool(ctx.get("template_mode", False)) and not _ctx_is_regular_mode(ctx):
        _normalize_ctx_issue_date_entry(ctx)

    data = collect_layout_data(ctx)
    errors = validate_layout_data_for_mode(
        data,
        template_mode=bool(ctx.get("template_mode", False)),
        regular_mode=_ctx_is_regular_mode(ctx),
    )
    if errors:
        file_type = _ctx_file_type_name(ctx).capitalize()
        messagebox.showerror(
            f"Invalid {file_type}",
            f"Please fix the following before saving the {file_type.lower()}:\n\n" + "\n".join(f"• {item}" for item in errors),
            parent=parent,
        )
        return False, data
    return True, data



def collect_layout_data(ctx):
    now = datetime.now().isoformat(timespec="seconds")
    data = {
        "version": 1,
        "name": ctx.get("layout_name") or "",
        "press": ctx["press_name"],
        "format": ctx["format_name"],
        "saved_at": now,
        "last_changed_by": get_windows_username(),
        "issue_date": ctx["issue_entry"].get().strip() if ctx.get("issue_entry") else "",
        "product": normalize_publication_name(ctx["product_entry"].get()) if ctx.get("product_entry") else "",
        "section_count": 1,
        "section_pages": [0],
        "section_names": [],
        "units": []
    }

    if ctx.get("section_count_var"):
        try:
            section_count = int(ctx["section_count_var"].get())
        except Exception:
            section_count = 1
        section_count = max(1, min(4, section_count))
        data["section_count"] = section_count
        data["section_pages"] = compute_section_page_counts_from_ctx(ctx, section_count=section_count)
        names = []
        for i in range(section_count):
            try:
                names.append((ctx.get("section_name_vars", [])[i].get() or "").strip())
            except Exception:
                names.append("")
        data["section_names"] = names

    for u in ctx["units"]:
        section = u["section_entry"].get().strip()
        grid = []
        for row in u["entries"]:
            grid.append([cell.get().strip() for cell in row])
        data["units"].append({"label": u["label"], "section": section, "grid": grid})

    if not ctx.get("template_mode", False):
        try:
            starter_format_var = ctx.get("starter_format_var")
            starter_format = (starter_format_var.get() or "").strip() if starter_format_var else ""
        except Exception:
            starter_format = ""
        if starter_format:
            data["starter_format"] = starter_format
        data["color_cells"] = [
            {"unit": unit, "r": int(r), "c": int(c)}
            for (unit, r, c) in sorted(ctx.get("color_cells", set()))
        ]
    return data
def populate_layout_from_data(ctx, data):
    regular_mode = _ctx_is_regular_mode(ctx)
    if ctx.get("issue_entry"):
        ctx["issue_entry"].state(["!disabled"])
        ctx["issue_entry"].delete(0, "end")
        ctx["issue_entry"].insert(0, data.get("issue_date", ""))
        if ctx.get("template_mode") or regular_mode:
            ctx["issue_entry"].state(["disabled"])

    if ctx.get("product_entry"):
        ctx["product_entry"].state(["!disabled"])
        ctx["product_entry"].delete(0, "end")
        ctx["product_entry"].insert(0, normalize_publication_name(data.get("product", "")))
        if ctx.get("template_mode"):
            ctx["product_entry"].state(["disabled"])

    if ctx.get("section_count_var") and ctx.get("section_page_vars"):
        section_count = data.get("section_count", 1)
        try:
            section_count = max(1, min(4, int(section_count)))
        except Exception:
            section_count = 1
        ctx["section_count_var"].set(str(section_count))

        section_pages = data.get("section_pages", [])
        for i in range(4):
            if i < section_count and i < len(section_pages):
                ctx["section_page_vars"][i].set(str(max(1, int(section_pages[i]))))
            elif i < section_count:
                ctx["section_page_vars"][i].set(str(min_pages_for_format(ctx.get("format_name", ""))))
            else:
                ctx["section_page_vars"][i].set("")

        if ctx.get("_update_section_page_states"):
            ctx["_update_section_page_states"](section_count)

    # Load section names (if present) and apply to header name fields
    section_names = data.get("section_names") or []
    if ctx.get("section_name_vars"):
        try:
            for i in range(4):
                if i < section_count and i < len(section_names) and section_names[i] is not None:
                    ctx["section_name_vars"][i].set(str(section_names[i]))
                elif i < section_count:
                    # defaults: template mode uses S1.., layout uses A..D
                    if ctx.get("template_mode"):
                        ctx["section_name_vars"][i].set(f"S{i+1}")
                    else:
                        ctx["section_name_vars"][i].set(chr(ord('A') + i))
                else:
                    ctx["section_name_vars"][i].set("")
        except Exception:
            pass

    unit_map = {u["label"]: u for u in ctx["units"]}
    for udata in data.get("units", []):
        label = udata.get("label")
        if label not in unit_map:
            continue
        u = unit_map[label]
        _set_widget_value(u["section_entry"], udata.get("section", ""))

        grid = udata.get("grid", [])
        for r, row in enumerate(grid):
            if r >= len(u["entries"]):
                break
            for c, val in enumerate(row):
                if c >= len(u["entries"][r]):
                    break
                cell = u["entries"][r][c]
                cell.delete(0, "end")
                cell.insert(0, val)

    if ctx.get("_capture_unit_section_assignments"):
        try:
            ctx["_capture_unit_section_assignments"]()
        except Exception:
            pass
    if ctx.get("_refresh_unit_section_choices"):
        try:
            ctx["_refresh_unit_section_choices"]()
        except Exception:
            pass
    if ctx.get("_refresh_section_page_counts"):
        try:
            ctx["_refresh_section_page_counts"]()
        except Exception:
            pass

    # ---- load per-cell color selection (layouts only) ----
    if not ctx.get("template_mode", False):
        ctx["color_cells"] = set()
        raw = data.get("color_cells", [])
        for item in raw:
            try:
                unit = str(item.get("unit"))
                r = int(item.get("r"))
                c = int(item.get("c"))
                ctx["color_cells"].add((unit, r, c))
            except Exception:
                pass

def do_save(win, ctx):
    default_dir = ctx.get("default_dir", LAYOUTS_DIR)
    ensure_dir(default_dir)

    prior_file_path = ctx.get("file_path")
    if not prior_file_path:
        suggested = build_save_filename_suggestion(ctx)
        ctx["file_path"] = os.path.join(default_dir, suggested)

    ok, data = validate_layout_ctx_before_save(ctx, parent=win)
    if not ok:
        if not prior_file_path:
            ctx["file_path"] = ""
        return False
    try:
        if ctx.get("template_mode", False):
            data = _normalize_template_data(data)
        if not data.get("name"):
            data["name"] = os.path.splitext(os.path.basename(ctx["file_path"]))[0]
        safe_write_json(ctx["file_path"], data)
        _save_preview_for_current_window(win, ctx["file_path"])
        ctx["layout_name"] = data["name"]
        win.title(f"{ctx['title_base']}  —  {os.path.basename(ctx['file_path'])}")

        # If saving a layout (not template mode) and imposition doesn't match existing template, ask to save as template
        if (not ctx.get("template_mode", False)) and ctx.get("prompt_save_template", True):
            if not _template_exists_for_imposition(ctx):
                template_suggestion = build_filename_suggestion(ctx)
                if messagebox.askyesno(
                    "Save as Template",
                    f"This layout has a new imposition that doesn't match any existing template.\n\n"
                    f"Would you like to save it as a template?\n\n"
                    f"Template name: {template_suggestion}",
                    parent=win
                ):
                    save_template_from_layout(ctx)

        return True
    except Exception as e:
        messagebox.showerror("Save Failed", str(e))
        return False
def do_save_as(win, ctx):
    ok, data = validate_layout_ctx_before_save(ctx, parent=win)
    if not ok:
        return False
    default_dir = ctx.get("default_dir", LAYOUTS_DIR)
    ensure_dir(default_dir)

    suggested = build_save_filename_suggestion(ctx)

    path = filedialog.asksaveasfilename(
        parent=win,
        initialdir=default_dir,
        initialfile=suggested,
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")]
    )
    if not path:
        return False

    try:
        if ctx.get("template_mode", False):
            data = _normalize_template_data(data)
        data = dict(data)
        for _copy_key in ("_db_record_id", "_db_record_type", "_file_path", "_layout_name"):
            data.pop(_copy_key, None)
        # Save As is a copy operation: the new record should carry the new
        # record/template name, even when the source already had a name.
        data["name"] = os.path.splitext(os.path.basename(path))[0]
        safe_write_json(path, data)
        _save_preview_for_current_window(win, path)
        ctx["file_path"] = path
        ctx["layout_name"] = data["name"]
        win.title(f"{ctx['title_base']}  —  {os.path.basename(path)}")

        # If saving a layout (not template mode) and imposition doesn't match existing template, ask to save as template
        if (not ctx.get("template_mode", False)) and ctx.get("prompt_save_template", True):
            if not _template_exists_for_imposition(ctx):
                template_suggestion = build_filename_suggestion(ctx)
                if messagebox.askyesno(
                    "Save as Template",
                    f"This layout has a new imposition that doesn't match any existing template.\n\n"
                    f"Would you like to save it as a template?\n\n"
                    f"Template name: {template_suggestion}",
                    parent=win
                ):
                    save_template_from_layout(ctx)

        return True
    except Exception as e:
        messagebox.showerror("Save As Failed", str(e))
        return False

def _normalize_imposition_name(value: str) -> str:
    """Normalize template/imposition names for reliable comparisons."""
    stem = os.path.splitext(str(value or "").strip())[0]
    stem = re.sub(r"\s+", " ", stem).strip().lower()
    return stem


def _imposition_name_matches(existing_name: str, target_name: str) -> bool:
    """Treat exact names and save_template_from_layout uniqueness suffixes as a match."""
    existing = _normalize_imposition_name(existing_name)
    target = _normalize_imposition_name(target_name)
    if not existing or not target:
        return False
    if existing == target:
        return True
    return bool(re.fullmatch(rf"{re.escape(target)}_\d+", existing))


def _template_imposition_signature_from_data(data):
    """Return a page-number-independent template/imposition signature.

    Section count, unit labels, unit section assignments, and occupied grid-cell
    positions define the imposition. The actual page numbers and section page
    totals are intentionally ignored so the same structure still matches when a
    layout uses a different page run.
    """
    normalized = _normalize_template_data(data if isinstance(data, dict) else {})
    try:
        section_count = max(1, min(4, int(normalized.get("section_count", 1))))
    except Exception:
        section_count = 1
    unit_signatures = []
    for unit in (normalized.get("units", []) or []):
        if not isinstance(unit, dict):
            continue
        label = str(unit.get("label") or "").strip()
        section = str(unit.get("section") or "").strip().upper()
        grid = unit.get("grid", []) or []
        occupancy = []
        for row in grid:
            row_values = row if isinstance(row, list) else []
            occupancy.append(tuple(bool(str(cell or "").strip()) for cell in row_values))
        unit_signatures.append((label, section, tuple(occupancy)))
    unit_signatures.sort(key=lambda item: item[0].lower())
    return (section_count, tuple(unit_signatures))


def _template_exists_for_imposition(ctx) -> bool:
    """Check if a template with the same imposition already exists.

    This needs to work for both the legacy filesystem-backed template folder and
    the PostgreSQL-backed virtual template collection. The prompt shown to the
    user is about imposition matching, so the primary comparison is the
    generated imposition/template name. As a fallback, we also do a structural
    match against the template JSON in case a template was renamed manually. The
    structural comparison deliberately ignores page numbers and section page
    totals so a template still counts as the same imposition when only page
    numbers are different.
    """
    ensure_dir(TEMPLATE_DIR)
    press = ctx.get("press_name", "")
    fmt = ctx.get("format_name", "")

    current_data = _normalize_template_data(collect_layout_data(ctx))
    current_data.pop("issue_date", None)
    current_data.pop("product", None)
    current_data.pop("color_cells", None)

    target_imposition_name = build_imposition_text(ctx)
    current_signature = _template_imposition_signature_from_data(current_data)

    template_candidates = []
    try:
        cached_rows, _changed = get_cached_templates(force=False)
    except Exception:
        cached_rows = []
    for row in cached_rows or []:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "").strip()
        if not path:
            continue
        row_press = str(row.get("press") or "")
        row_fmt = str(row.get("format") or "")
        if row_press and row_press != press:
            continue
        if row_fmt and row_fmt != fmt:
            continue
        template_candidates.append({
            "path": path,
            "name": str(row.get("name") or "").strip(),
        })

    if not template_candidates:
        for tmpl_path in sorted(glob.glob(os.path.join(TEMPLATE_DIR, "*.json"))):
            template_candidates.append({
                "path": tmpl_path,
                "name": os.path.splitext(os.path.basename(tmpl_path))[0],
            })

    for candidate in template_candidates:
        tmpl_path = candidate.get("path") or ""
        tmpl_data = safe_read_json(tmpl_path)
        if not isinstance(tmpl_data, dict):
            continue

        if tmpl_data.get("press") != press or tmpl_data.get("format") != fmt:
            continue

        template_stem = os.path.splitext(os.path.basename(tmpl_path))[0]
        template_name = tmpl_data.get("name") or candidate.get("name") or template_stem
        if _imposition_name_matches(template_name, target_imposition_name) or _imposition_name_matches(template_stem, target_imposition_name):
            return True

        if _template_imposition_signature_from_data(tmpl_data) == current_signature:
            return True

    return False
def save_regular_from_layout(ctx, parent=None):
    """Save the current layout as a regular using the regular suggested filename."""
    try:
        ensure_dir(REGULAR_DIR)

        data = collect_layout_data(ctx)
        data["issue_date"] = ""

        errors = validate_layout_data_for_mode(
            data,
            template_mode=False,
            regular_mode=True,
        )
        if errors:
            messagebox.showerror(
                "Save as Regular Failed",
                "Please fix the following before saving as a regular:\n\n" + "\n".join(f"• {item}" for item in errors),
                parent=parent,
            )
            return False, None

        regular_filename = build_regular_filename_suggestion(ctx)
        regular_path = os.path.join(REGULAR_DIR, regular_filename)

        if os.path.exists(regular_path):
            base, ext = os.path.splitext(regular_filename)
            counter = 1
            while os.path.exists(os.path.join(REGULAR_DIR, f"{base}_{counter}{ext}")):
                counter += 1
            regular_filename = f"{base}_{counter}{ext}"
            regular_path = os.path.join(REGULAR_DIR, regular_filename)

        data["name"] = os.path.splitext(regular_filename)[0]
        safe_write_json(regular_path, data)
        try:
            if parent is not None:
                _save_preview_for_current_window(parent, regular_path)
        except Exception:
            pass
        messagebox.showinfo("Regular Saved", f"Regular saved as:\n{regular_filename}", parent=parent)
        return True, regular_path
    except Exception as e:
        messagebox.showerror("Save as Regular Failed", f"Could not save regular:\n{str(e)}", parent=parent)
        return False, None


def save_template_from_layout(ctx):
    """Save the current layout as a template (without issue_date, product, color_cells)."""
    try:
        ensure_dir(TEMPLATE_DIR)

        # Collect data but strip layout-specific fields
        data = collect_layout_data(ctx)
        data = _normalize_template_data(data)

        # Remove layout-specific fields
        data.pop("issue_date", None)
        data.pop("product", None)
        data.pop("color_cells", None)

        # Generate template filename
        template_filename = build_filename_suggestion(ctx)
        template_path = os.path.join(TEMPLATE_DIR, template_filename)

        # Make filename unique if it exists
        if os.path.exists(template_path):
            base, ext = os.path.splitext(template_filename)
            counter = 1
            while os.path.exists(os.path.join(TEMPLATE_DIR, f"{base}_{counter}{ext}")):
                counter += 1
            template_filename = f"{base}_{counter}{ext}"
            template_path = os.path.join(TEMPLATE_DIR, template_filename)

        # Use template filename as template name
        data["name"] = os.path.splitext(template_filename)[0]

        safe_write_json(template_path, data)
        _save_preview_for_saved_template(ctx, template_path)
        messagebox.showinfo("Template Saved", f"Template saved as:\n{template_filename}")
    except Exception as e:
        messagebox.showerror("Save Template Failed", f"Could not save template:\n{str(e)}")


# Expose this single-file module under the original module name so intra-project imports keep working.
import sys as _single_file_sys
_single_file_sys.modules.setdefault('press_layout_core', _single_file_sys.modules[__name__])

import calendar
ensure_runtime_dependencies(prompt_user=True)
from PIL import Image

helpers_mod = sys.modules[__name__]


# =============================================================================
# Tree sorting and launcher UI constants
# Shared display constants and grouped treeview sorting helpers used by the launcher and editor lists.
# =============================================================================

SORT_ASCENDING_INDICATOR = " ▲"
SORT_DESCENDING_INDICATOR = " ▼"


def _treeview_sort_heading_text(base_title, sort_state, col):
    active_col = sort_state.get("col")
    if active_col != col:
        return base_title
    return f'{base_title}{SORT_DESCENDING_INDICATOR if sort_state.get("desc") else SORT_ASCENDING_INDICATOR}'


def _last_changed_by_display(value):
    text = str(value or "").strip()
    return text if text else "Unknown"


# =============================================================================
# Layout editor, rendering, starter-sheet, and print workflow
# Calendar picker, editor construction, layout rendering, starter-sheet rendering, print helpers, and editor actions.
# =============================================================================

def _shift_calendar_month(year, month, delta):
    month_index = (int(year) * 12 + (int(month) - 1)) + int(delta)
    new_year, zero_based_month = divmod(month_index, 12)
    return new_year, zero_based_month + 1


def ask_issue_date_with_calendar(parent, initial_text="", anchor_widget=None, title="Select Issue Date"):
    """Open a simple mouse-friendly calendar date picker and return mm/dd/YYYY or None."""
    try:
        initial_dt = parse_issue_date_flexible(initial_text)
    except Exception:
        initial_dt = None
    if initial_dt is None:
        initial_dt = datetime.now()

    state = {
        "display_year": int(initial_dt.year),
        "display_month": int(initial_dt.month),
        "selected": initial_dt.strftime("%m/%d/%Y"),
    }
    result = {"value": None}

    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title(title)
    try:
        dialog.transient(parent)
    except Exception:
        pass
    dialog.resizable(False, False)

    outer = ttk.Frame(dialog, padding=10)
    outer.grid(row=0, column=0, sticky="nsew")
    outer.columnconfigure(0, weight=1)

    header = ttk.Frame(outer)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(1, weight=1)

    month_title_var = tk.StringVar(value="")
    days_frame = ttk.Frame(outer)
    days_frame.grid(row=2, column=0, sticky="nsew", pady=(8, 6))

    def close_dialog(value=None):
        result["value"] = value
        try:
            dialog.destroy()
        except Exception:
            pass

    def select_date(day_value):
        close_dialog(f'{state["display_month"]:02d}/{int(day_value):02d}/{state["display_year"]:04d}')

    def render_month():
        for child in days_frame.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

        month_title_var.set(f'{calendar.month_name[state["display_month"]]} {state["display_year"]}')
        weekday_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        for col, weekday_name in enumerate(weekday_names):
            ttk.Label(days_frame, text=weekday_name, anchor="center", font=(None, 10, "bold"), width=4).grid(row=0, column=col, padx=1, pady=(0, 4))

        selected_dt = None
        try:
            selected_dt = parse_issue_date_flexible(state.get("selected"))
        except Exception:
            selected_dt = None

        cal = calendar.Calendar(firstweekday=6)
        month_rows = cal.monthdayscalendar(state["display_year"], state["display_month"])
        while len(month_rows) < 6:
            month_rows.append([0] * 7)

        for row_index, row_values in enumerate(month_rows, start=1):
            for col_index, day_value in enumerate(row_values):
                if day_value <= 0:
                    ttk.Label(days_frame, text="", width=4).grid(row=row_index, column=col_index, padx=1, pady=1)
                    continue

                is_selected = bool(
                    selected_dt
                    and int(selected_dt.year) == int(state["display_year"])
                    and int(selected_dt.month) == int(state["display_month"])
                    and int(selected_dt.day) == int(day_value)
                )
                button = tk.Button(
                    days_frame,
                    text=str(day_value),
                    width=4,
                    relief=("sunken" if is_selected else "raised"),
                    bd=2 if is_selected else 1,
                    command=lambda d=day_value: select_date(d),
                )
                button.grid(row=row_index, column=col_index, padx=1, pady=1, sticky="nsew")

    def move_month(delta):
        state["display_year"], state["display_month"] = _shift_calendar_month(state["display_year"], state["display_month"], delta)
        render_month()

    ttk.Button(header, text="◀", width=4, command=lambda: move_month(-1)).grid(row=0, column=0, sticky="w")
    ttk.Label(header, textvariable=month_title_var, anchor="center", font=(None, 11, "bold")).grid(row=0, column=1, sticky="ew", padx=6)
    ttk.Button(header, text="▶", width=4, command=lambda: move_month(1)).grid(row=0, column=2, sticky="e")

    action_frame = ttk.Frame(outer)
    action_frame.grid(row=3, column=0, sticky="e", pady=(6, 0))
    ttk.Button(action_frame, text="Today", width=10, command=lambda: close_dialog(datetime.now().strftime("%m/%d/%Y"))).pack(side="left", padx=(0, 8))
    ttk.Button(action_frame, text="Cancel", width=10, command=lambda: close_dialog(None)).pack(side="left")

    dialog.bind("<Escape>", lambda e: close_dialog(None), add="+")
    dialog.protocol("WM_DELETE_WINDOW", lambda: close_dialog(None))

    render_month()

    try:
        dialog.update_idletasks()
        if anchor_widget is not None:
            x = int(anchor_widget.winfo_rootx())
            y = int(anchor_widget.winfo_rooty()) + int(anchor_widget.winfo_height()) + 4
            dialog.geometry(f'+{x}+{y}')
    except Exception:
        pass

    try:
        dialog.grab_set()
    except Exception:
        pass
    parent.wait_window(dialog)
    return result.get("value")



class _StaticValue:
    """Tiny headless adapter that mimics Tk Variables / Entries through .get()."""
    def __init__(self, value=""):
        self._value = "" if value is None else str(value)

    def get(self):
        return self._value


def _layout_data_to_headless_ctx(data, config=None, title_base=""):
    data = data if isinstance(data, dict) else {}
    config = config if isinstance(config, dict) else {}
    fmt = str(data.get("format") or config.get("format_name") or "")
    try:
        section_count = max(1, min(4, int(data.get("section_count", 1))))
    except Exception:
        section_count = 1

    minimum_pages = min_pages_for_format(fmt)
    raw_section_pages = data.get("section_pages", []) or []
    section_page_vars = []
    for idx in range(4):
        value = ""
        if idx < section_count:
            try:
                value = str(max(1, int(raw_section_pages[idx])))
            except Exception:
                value = str(minimum_pages)
        section_page_vars.append(_StaticValue(value))

    raw_section_names = data.get("section_names", []) or []
    section_name_vars = []
    for idx in range(4):
        value = ""
        if idx < section_count:
            try:
                value = str(raw_section_names[idx] or "")
            except Exception:
                value = ""
        section_name_vars.append(_StaticValue(value))

    units = []
    for unit in data.get("units", []) or []:
        if not isinstance(unit, dict):
            continue
        label = str(unit.get("label") or "")
        section_text = str(unit.get("section") or "")
        grid_entries = []
        for row in unit.get("grid", []) or []:
            row = row if isinstance(row, list) else []
            grid_entries.append([_StaticValue("" if value is None else str(value).strip()) for value in row])
        units.append({
            "label": label,
            "section_entry": _StaticValue(section_text),
            "entries": grid_entries,
        })

    color_cells = set()
    for item in data.get("color_cells", []) or []:
        if not isinstance(item, dict):
            continue
        try:
            unit_label = str(item.get("unit") or "")
            row_index = int(item.get("r"))
            col_index = int(item.get("c"))
        except Exception:
            continue
        if unit_label:
            color_cells.add((unit_label, row_index, col_index))

    return {
        "title_base": title_base,
        "press_name": str(data.get("press") or config.get("press_name") or ""),
        "format_name": fmt,
        "issue_entry": _StaticValue(data.get("issue_date", "")),
        "product_entry": _StaticValue(data.get("product", "")),
        "starter_format_var": _StaticValue(data.get("starter_format", "")),
        "section_count_var": _StaticValue(section_count),
        "section_page_vars": section_page_vars,
        "section_name_vars": section_name_vars,
        "units": units,
        "color_cells": color_cells,
    }


def _desired_starter_format_for_publication(publication_name):
    normalized_name = normalize_publication_name(publication_name or "")
    name_upper = normalized_name.upper()
    if "NYT" in name_upper:
        return "NYT"
    if "USAT" in name_upper and not re.search(r'\bCO\b', name_upper):
        return "USAT"
    return None


def _build_filename_suggestion_from_layout_data(data, template_mode=False, regular_mode=False, default_dir=None, config=None):
    ctx = _layout_data_to_headless_ctx(data, config=config, title_base="")
    ctx["template_mode"] = bool(template_mode)
    ctx["regular_mode"] = bool(regular_mode)
    if default_dir:
        ctx["default_dir"] = default_dir
    ctx["layout_name"] = str((data or {}).get("name") or "").strip()
    return build_save_filename_suggestion(ctx)


def _normalize_layout_data_for_touch(data, path, template_mode=False, regular_mode=False, default_dir=None, config=None):
    ctx = _layout_data_to_headless_ctx(data, config=config, title_base="")
    ctx["template_mode"] = bool(template_mode)
    ctx["regular_mode"] = bool(regular_mode)
    if default_dir:
        ctx["default_dir"] = default_dir
    ctx["layout_name"] = str((data or {}).get("name") or os.path.splitext(os.path.basename(path))[0]).strip()

    normalized = collect_layout_data(ctx)
    # Preserve starter_format during touch/cleanup operations, but allow Touch ALL
    # to enforce publication-specific starter rules when the product name clearly
    # matches NYT or a non-CO USAT layout.
    if not template_mode:
        try:
            existing_starter_format = str((data or {}).get("starter_format") or "").strip()
        except Exception:
            existing_starter_format = ""
        desired_starter_format = _desired_starter_format_for_publication((data or {}).get("product") or normalized.get("product") or "")
        if desired_starter_format:
            normalized["starter_format"] = desired_starter_format
        elif existing_starter_format:
            normalized["starter_format"] = existing_starter_format
    if template_mode:
        normalized = helpers_mod._normalize_template_data(normalized)
        normalized.pop("issue_date", None)
        normalized.pop("product", None)
        normalized.pop("color_cells", None)
    return normalized, ctx


def _unique_cleanup_target_path(target_path, current_path=None):
    target_path = os.path.abspath(str(target_path or ""))
    current_path = os.path.abspath(str(current_path or "")) if current_path else ""
    if not target_path:
        return target_path
    if (not os.path.exists(target_path)) or (current_path and os.path.normcase(target_path) == os.path.normcase(current_path)):
        return target_path
    base, ext = os.path.splitext(target_path)
    counter = 1
    while True:
        candidate = f"{base}_{counter}{ext}"
        if (not os.path.exists(candidate)) or (current_path and os.path.normcase(candidate) == os.path.normcase(current_path)):
            return candidate
        counter += 1


def touch_cleanup_json_path(path, template_mode=False, regular_mode=False, default_dir=None, prompt_save_template=None):
    try:
        data = safe_read_json(path)
        if not isinstance(data, dict):
            return f"{os.path.basename(path)}: Could not read JSON data.", path, path

        errors = validate_layout_data_for_mode(
            data,
            template_mode=bool(template_mode),
            regular_mode=bool(regular_mode),
        )
        if errors:
            return f"{os.path.basename(path)}: " + " | ".join(errors), path, path

        prepared_data, ctx = _normalize_layout_data_for_touch(
            data,
            path,
            template_mode=template_mode,
            regular_mode=regular_mode,
            default_dir=default_dir,
        )
        prepared_data["saved_at"] = datetime.now().isoformat(timespec="seconds")
        prepared_data["last_changed_by"] = get_windows_username()

        original_path = path
        final_path = path

        if template_mode:
            target_filename = build_filename_suggestion(ctx)
            target_filename = sanitize_filename(target_filename).strip()
            if not target_filename.lower().endswith('.json'):
                target_filename += '.json'
            desired_path = os.path.join(os.path.dirname(path), target_filename)
            final_path = _unique_cleanup_target_path(desired_path, current_path=path)
            prepared_data["name"] = os.path.splitext(os.path.basename(final_path))[0]
            if os.path.normcase(os.path.abspath(final_path)) != os.path.normcase(os.path.abspath(path)):
                os.replace(path, final_path)
                remove_preview_image_for_json(path)
                path = final_path
        else:
            if not prepared_data.get("name"):
                prepared_data["name"] = os.path.splitext(os.path.basename(path))[0]

        safe_write_json(path, prepared_data)
        try:
            regenerate_preview_image_for_json_path(
                path,
                template_mode=template_mode,
                default_dir=default_dir,
                prompt_save_template=prompt_save_template,
                scale=0.75,
            )
        except Exception as exc:
            return f"{os.path.basename(path)}: {exc}", original_path, path
        return None, original_path, path
    except Exception as exc:
        return f"{os.path.basename(path)}: {exc}", path, path

def _render_load_starter_font(size, bold=False):
    try:
        from PIL import ImageFont
    except Exception:
        return None
    font_names = []
    if bold:
        font_names.extend(["arialbd.ttf", "Arial Bold.ttf", "ARIALBD.TTF", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"])
    font_names.extend(["arial.ttf", "Arial.ttf", "ARIAL.TTF", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"])
    search_paths = [
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/liberation2",
        "/usr/share/fonts/truetype/liberation",
    ]
    for folder in search_paths:
        for name in font_names:
            try:
                candidate = os.path.join(folder, name)
                if os.path.exists(candidate):
                    return ImageFont.truetype(candidate, size=size)
            except Exception:
                pass
    for name in font_names:
        try:
            return ImageFont.truetype(name, size=size)
        except Exception:
            pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _render_measure_text(draw, text, font):
    text = text or ""
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top
    except Exception:
        return draw.textsize(text, font=font)


def _render_measure_text_bounds(draw, text, font):
    text = text or ""
    try:
        return draw.textbbox((0, 0), text, font=font)
    except Exception:
        width, height = draw.textsize(text, font=font)
        return 0, 0, width, height


def _render_draw_centered_text(draw, box, text, font, fill="black"):
    x0, y0, x1, y1 = box
    left, top, right, bottom = _render_measure_text_bounds(draw, text, font)
    tw = right - left
    th = bottom - top
    tx = x0 + max(0, ((x1 - x0) - tw) / 2) - left
    ty = y0 + max(0, ((y1 - y0) - th) / 2) - top
    draw.text((tx, ty), text or "", fill=fill, font=font)


def _render_draw_centered_text_heavy(draw, box, text, font, fill="black", offset=1):
    x0, y0, x1, y1 = box
    left, top, right, bottom = _render_measure_text_bounds(draw, text, font)
    tw = right - left
    th = bottom - top
    tx = x0 + max(0, ((x1 - x0) - tw) / 2) - left
    ty = y0 + max(0, ((y1 - y0) - th) / 2) - top
    for dx, dy in ((0, 0), (offset, 0), (0, offset), (offset, offset)):
        draw.text((tx + dx, ty + dy), text or "", fill=fill, font=font)


def _render_wrap_text_to_width(draw, text, font, max_width):
    words = str(text or "").split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _render_measure_text(draw, candidate, font)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _visible_print_labels_for_render(ctx, units, left_labels, right_labels):
    unit_map = {u["label"]: u for u in units}
    left_order = [lab for lab in left_labels if lab in unit_map]
    right_order = []
    special_group = {"E2", "D2", "C2"}
    special_used = False
    if ctx.get("press_name") == "Press 1":
        for lab in special_group:
            unit = unit_map.get(lab)
            if unit is not None and unit_min_page_number(unit) is not None:
                special_used = True
                break
    for lab in right_labels:
        unit = unit_map.get(lab)
        if unit is None:
            continue
        if ctx.get("press_name") == "Press 1" and lab in special_group and not special_used:
            continue
        right_order.append(lab)
    return left_order, right_order, unit_map


def render_layout_print_image_from_data(data, config, title_base="", template_mode=False):
    try:
        from PIL import Image as PILImage, ImageDraw
    except Exception:
        raise RuntimeError("Pillow is required for printing. Please install pillow (pip install pillow).")

    data = data if isinstance(data, dict) else {}
    config = dict(config or {})
    ctx = _layout_data_to_headless_ctx(data, config=config, title_base=title_base)
    units = ctx.get("units", [])
    grid_cols = int(config.get("grid_cols", 0) or 0)
    swatch_cols = int(config.get("swatch_cols", 1) or 1)
    unit_padx = int(config.get("unit_padx", 6) or 6)
    folder_padx = int(config.get("folder_padx", 24) or 24)
    folder_label = str(config.get("folder_label") or "Folder")
    midline_thickness = int(config.get("midline_thickness", 4) or 4)
    midline_color = str(config.get("midline_color") or "#444444")
    only_k_labels = set(config.get("only_k_labels", set()) or set())
    left_labels = list(config.get("left_labels", []) or [])
    right_labels = list(config.get("right_labels", []) or [])

    img_w, img_h = 2200, 1940
    img = PILImage.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(img)

    if grid_cols >= 8:
        title_sz, header_sz, text_sz, unit_sz, section_sz, cell_sz = 50, 42, 24, 24, 30, 18
    elif grid_cols >= 4:
        title_sz, header_sz, text_sz, unit_sz, section_sz, cell_sz = 56, 44, 26, 24, 32, 22
    else:
        title_sz, header_sz, text_sz, unit_sz, section_sz, cell_sz = 60, 46, 28, 24, 34, 38

    title_font = _render_load_starter_font(title_sz, bold=True)
    header_font = _render_load_starter_font(header_sz, bold=True)
    text_font = _render_load_starter_font(text_sz, bold=False)
    small_font = _render_load_starter_font(max(18, text_sz - 4), bold=False)
    sections_print_font = _render_load_starter_font(max(36, (max(18, text_sz - 4)) * 2), bold=True)
    unit_font = _render_load_starter_font(unit_sz, bold=True)
    section_font = _render_load_starter_font(section_sz, bold=True)
    cell_font_render = _render_load_starter_font(cell_sz, bold=True)
    color_cell_font_render = _render_load_starter_font(cell_sz + 2, bold=True)
    legend_font = _render_load_starter_font(header_sz, bold=True)
    legend_symbol_font = _render_load_starter_font(header_sz, bold=True)
    legend_list_font = _render_load_starter_font(header_sz, bold=True)

    margin_x = 55
    header_top = 26
    header_h = 180
    footer_h = 150
    grid_top = header_top + header_h + 14
    footer_y = img_h - footer_h - 30

    raw_issue = (data.get("issue_date") or "").strip()
    issue_text = raw_issue
    if not template_mode:
        try:
            dt = parse_issue_date_flexible(raw_issue)
            if dt:
                issue_text = dt.strftime("%m/%d/%Y")
        except Exception:
            pass
    product_text = (data.get("product") or "").strip()

    label_top = header_top
    fallback_title = title_base or ("Template Layout" if template_mode else "Press Layout")
    _render_draw_centered_text(draw, (margin_x, label_top, img_w - margin_x, label_top + 60), product_text or fallback_title, title_font)
    draw.text((margin_x, label_top + 66), f"Issue Date: {issue_text}", fill="black", font=sections_print_font)

    try:
        count = max(1, min(4, int(data.get("section_count", 1))))
    except Exception:
        count = 1
    section_display_lookup = {}
    section_names = data.get("section_names", []) or []
    for idx in range(count):
        try:
            section_name = str(section_names[idx] or "").strip().upper()
        except Exception:
            section_name = ""
        if not section_name:
            section_name = chr(ord("A") + idx)
        section_display_lookup[section_name] = idx

    color_page_refs = []
    seen_color_refs = set()
    legend_circle_diameter = 54
    show_bold_color_marks = ((ctx.get("format_name") or "").strip().lower() == "broadsheet")

    values = []
    total_page_count = 0
    section_pages = data.get("section_pages", []) or []
    for idx in range(count):
        value = ""
        try:
            value = str(section_pages[idx]).strip()
        except Exception:
            value = ""
        if value:
            values.append(value)
            try:
                total_page_count += int(value)
            except Exception:
                pass
    sections_text = ' / '.join(values)
    if sections_text:
        draw.text((margin_x, label_top + 118), f"Pages: {sections_text}", fill="black", font=sections_print_font)

    draw.line((margin_x, grid_top - 18, img_w - margin_x, grid_top - 18), fill="#444444", width=3)
    left_order, right_order, unit_map = _visible_print_labels_for_render(ctx, units, left_labels, right_labels)
    total_units = len(left_order) + len(right_order)
    if total_units <= 0:
        draw.text((margin_x, grid_top + 20), 'No units to print.', fill='black', font=text_font)
        return img

    gap = max(10, int(unit_padx * 2.4))
    folder_gap = max(gap + 8, int(folder_padx * 1.5))
    folder_w = 150 if grid_cols <= 4 else 175
    left_gaps = max(0, len(left_order) - 1) * gap
    right_gaps = max(0, len(right_order) - 1) * gap
    usable_w = img_w - (2 * margin_x) - left_gaps - right_gaps - (2 * folder_gap) - folder_w
    unit_w = max(115, int(usable_w / max(1, total_units)))
    unit_h = footer_y - grid_top - 12
    unit_label_h = 26
    section_h = max(24, section_sz + 8)

    x_positions = {}
    x = margin_x
    for lab in left_order:
        x_positions[lab] = x
        x += unit_w + gap
    folder_x0 = x + folder_gap
    folder_x1 = folder_x0 + folder_w
    x = folder_x1 + folder_gap
    for lab in right_order:
        x_positions[lab] = x
        x += unit_w + gap

    folder_mid = (folder_x0 + folder_x1) / 2.0
    folder_arrow_w = min(64, max(42, int(folder_w * 0.36)))
    arrow_center_y = grid_top + 95
    for offset in (0, 84, 168):
        cy = arrow_center_y + offset
        draw.polygon([
            (folder_mid - folder_arrow_w / 2, cy - 24),
            (folder_mid + folder_arrow_w / 2, cy - 24),
            (folder_mid, cy + 28),
        ], fill='#666666', outline='#666666')
    left_triangle_center_y = arrow_center_y + 84
    left_triangle_left = folder_x0 - 18
    draw.polygon([
        (left_triangle_left, left_triangle_center_y - 24),
        (left_triangle_left + folder_arrow_w, left_triangle_center_y - 24),
        (left_triangle_left + folder_arrow_w / 2, left_triangle_center_y + 28),
    ], fill='#666666', outline='#666666')
    folder_label_top = arrow_center_y + 168 + 36
    _render_draw_centered_text(draw, (folder_x0, folder_label_top, folder_x1, folder_label_top + unit_label_h), folder_label, unit_font)

    for lab in left_order + right_order:
        unit = unit_map[lab]
        x0 = x_positions[lab]
        x1 = x0 + unit_w
        y0 = grid_top
        y1 = y0 + unit_h

        section_text = (unit.get('section_entry').get() or '').strip().upper() if unit.get('section_entry') else ''
        section_label_space = section_h + 6
        if section_text:
            _render_draw_centered_text(draw, (x0, y0, x1, y0 + section_h), section_text, section_font)

        box_top = y0 + section_label_space
        entries = unit.get('entries', [])
        rows = len(entries)
        cols = len(entries[0]) if rows else 0
        if rows <= 0 or cols <= 0:
            continue

        cell_w = (x1 - x0) / cols
        orig_box_h = max(1, y1 - box_top)
        desired_box_h = int(rows * cell_w * 1.05)
        box_h = min(orig_box_h, desired_box_h)
        min_box_h = max(24, int(unit_label_h + section_h + 8))
        box_h = max(min_box_h, box_h)
        y1 = box_top + box_h
        draw.rectangle((x0, box_top, x1, y1), outline='black', width=2, fill='white')
        cell_h = box_h / rows
        mid_col = cols // 2
        mid_row = rows // 2
        for row_index in range(1, rows):
            yy = box_top + (row_index * cell_h)
            width = midline_thickness if (rows % 2 == 0 and row_index == mid_row) else 1
            color = midline_color if width > 1 else '#888888'
            draw.line((x0, yy, x1, yy), fill=color, width=width)
        for col_index in range(1, cols):
            xx = x0 + (col_index * cell_w)
            width = midline_thickness if (cols % 2 == 0 and col_index == mid_col) else 1
            color = midline_color if width > 1 else '#888888'
            draw.line((xx, box_top, xx, y1), fill=color, width=width)

        for row_index in range(rows):
            for col_index in range(cols):
                cx0 = x0 + (col_index * cell_w)
                cy0 = box_top + (row_index * cell_h)
                cx1 = x0 + ((col_index + 1) * cell_w)
                cy1 = box_top + ((row_index + 1) * cell_h)
                try:
                    value = (entries[row_index][col_index].get() or '').strip()
                except Exception:
                    value = ''
                is_color_page = (lab, row_index, col_index) in ctx.get('color_cells', set())
                if value:
                    if is_color_page and show_bold_color_marks:
                        _render_draw_centered_text_heavy(draw, (cx0 + 2, cy0 + 2, cx1 - 2, cy1 - 2), value, color_cell_font_render, fill='black', offset=1)
                    else:
                        _render_draw_centered_text(draw, (cx0 + 2, cy0 + 2, cx1 - 2, cy1 - 2), value, cell_font_render)
                if is_color_page:
                    pad = max(5, int(min(cell_w, cell_h) * 0.11))
                    circle_diameter = max(10, int(min(cell_w, cell_h) - (2 * pad)))
                    legend_circle_diameter = circle_diameter
                    circle_width = 6 if show_bold_color_marks else 3
                    draw.ellipse((cx0 + pad, cy0 + pad, cx1 - pad, cy1 - pad), outline='red', width=circle_width)
                    section_ref = section_text.strip().upper()
                    page_ref = str(value or '').strip()
                    if section_ref and page_ref:
                        ref_text = f'{section_ref}{page_ref}'
                        if ref_text not in seen_color_refs:
                            seen_color_refs.add(ref_text)
                            try:
                                page_num = int(page_ref)
                            except Exception:
                                page_num = 10 ** 9
                            color_page_refs.append((section_display_lookup.get(section_ref, 999), section_ref, page_num, ref_text))

        label_top = y1 + 6
        _render_draw_centered_text(draw, (x0, label_top, x1, label_top + unit_label_h), lab, unit_font)
        try:
            use_cmyk = lab not in only_k_labels
        except Exception:
            use_cmyk = True
        colors = [('K', '#7f7f7f'), ('Y', '#fff176'), ('M', '#f48fb1'), ('C', '#90caf9')] if use_cmyk else [('K', '#7f7f7f')]
        sw_cols = swatch_cols if swatch_cols and swatch_cols > 0 else 1
        sw_h = max(28, int(cell_h * 0.95))
        sw_spacing = 8
        sw_start_y = label_top + unit_label_h + 8
        for ci, (key, color) in enumerate(colors):
            row_count = sw_cols
            sw_w = max(18, int(min((unit_w * 0.9) / max(1, row_count), cell_w * 0.9)))
            row_total_w = row_count * sw_w + (row_count - 1) * sw_spacing
            row_x = x0 + (unit_w - row_total_w) / 2.0
            row_y = sw_start_y + ci * (sw_h + sw_spacing)
            for item_index in range(sw_cols):
                sx0 = row_x + item_index * (sw_w + sw_spacing)
                sx1 = sx0 + sw_w
                sy1 = row_y + sw_h
                draw.rectangle((sx0, row_y, sx1, sy1), fill=color, outline='#333333')
                try:
                    rcol = int(color.lstrip('#')[0:2], 16)
                    gcol = int(color.lstrip('#')[2:4], 16)
                    bcol = int(color.lstrip('#')[4:6], 16)
                    luminance = 0.299 * rcol + 0.587 * gcol + 0.114 * bcol
                    text_fill = 'black' if luminance > 150 else 'white'
                except Exception:
                    text_fill = 'black'
                _render_draw_centered_text(draw, (sx0, row_y, sx1, sy1), key, small_font, fill=text_fill)

    color_pages_count, plates_count = _layout_color_and_plate_counts_from_data(data)
    color_pages_text = str(color_pages_count)
    plates_text = str(plates_count)
    footer_line_y = footer_y - 14
    draw.line((margin_x, footer_line_y, img_w - margin_x, footer_line_y), fill='#444444', width=3)
    draw.text((margin_x, footer_y), f"Color Pages: {color_pages_text}", fill='black', font=header_font)
    draw.text((margin_x + 480, footer_y), f"Plates: {plates_text}", fill='black', font=header_font)
    draw.text((margin_x + 900, footer_y), f"Total Pages: {total_page_count}", fill='black', font=header_font)

    legend_circle_diameter = max(42, int(legend_circle_diameter))
    legend_y = footer_line_y - 190
    legend_circle_box = (
        margin_x,
        legend_y,
        margin_x + legend_circle_diameter,
        legend_y + legend_circle_diameter,
    )
    draw.ellipse(legend_circle_box, outline='red', width=6)
    _render_draw_centered_text_heavy(draw, legend_circle_box, '#', legend_symbol_font, fill='black', offset=1)
    draw.text((margin_x + legend_circle_diameter + 24, legend_y), '= color page', fill='black', font=legend_font)

    color_page_refs_sorted = [item[3] for item in sorted(color_page_refs, key=lambda item: (item[0], item[2], item[3]))]
    refs_text = 'Color pages list: ' + (', '.join(color_page_refs_sorted) if color_page_refs_sorted else 'None')
    list_y = legend_y + legend_circle_diameter + 26
    max_text_width = max(260, img_w - (2 * margin_x))
    wrapped_lines = _render_wrap_text_to_width(draw, refs_text, legend_list_font, max_text_width)
    line_h = max(44, _render_measure_text(draw, 'Ag', legend_list_font)[1] + 10)
    for line_index, line_text in enumerate(wrapped_lines):
        draw.text((margin_x, list_y + (line_index * line_h)), line_text, fill='black', font=legend_list_font)
    return img


def render_layout_preview_image_from_data(data, config, scale=0.75, title_base='', template_mode=False):
    img = render_layout_print_image_from_data(data, config, title_base=title_base, template_mode=template_mode)
    if img is None:
        return None
    try:
        scale = float(scale)
    except Exception:
        scale = 0.75
    scale = max(0.1, min(1.0, scale))
    preview_img = img.crop((0, 0, img.width, max(1, int(img.height * 0.5))))
    if scale != 1.0:
        width, height = preview_img.size
        preview_img = preview_img.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS)
    return preview_img




def _starter_sheet_fields_from_layout_data(data):
    data = data if isinstance(data, dict) else {}
    raw_issue = str(data.get("issue_date") or "").strip()
    dt = parse_issue_date_flexible(raw_issue)
    issue_text = dt.strftime("%m/%d/%Y") if dt else raw_issue
    total_pages = 0
    raw_pages = data.get("section_pages") or []
    if isinstance(raw_pages, list):
        for value in raw_pages[:4]:
            try:
                total_pages += int(str(value or '').strip())
            except Exception:
                pass
    try:
        color_pages, plates = _layout_color_and_plate_counts_from_data(data)
    except Exception:
        color_pages, plates = 0, 0
    return {
        "publication": normalize_publication_name(data.get("product") or ""),
        "issue_date": issue_text,
        "color_pages": str(color_pages or "").strip(),
        "plates": str(plates or "").strip(),
        "total_pages": str(total_pages),
    }


def make_starter_sheet_image_from_data(data, format_name=None):
    data = data if isinstance(data, dict) else {}
    fields = _starter_sheet_fields_from_layout_data(data)
    if not format_name:
        format_name = (
            str(data.get('starter_format') or '').strip()
            or _desired_starter_format_for_publication(data.get('product'))
            or 'Standard'
        )
    try:
        from PIL import Image, ImageDraw
    except Exception:
        raise RuntimeError("Pillow is required for starter sheet printing. Please install pillow (pip install pillow).")

    publication = str(fields.get("publication", "") or "").strip()
    issue_date = str(fields.get("issue_date", "") or "").strip()
    color_pages = str(fields.get("color_pages", "") or "").strip()
    plates = str(fields.get("plates", "") or "").strip()
    total_pages = str(fields.get("total_pages", "") or "").strip()
    fmt_key = (format_name or "Standard").strip().upper()
    if fmt_key not in {"STANDARD", "USAT", "NYT"}:
        fmt_key = "STANDARD"

    # Render exactly for 8.5 x 11 landscape at 300 DPI.
    page_w, page_h = 3300, 2550
    margin = 75
    gap = 36
    img = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(img)

    common_fields = [
        {"label": "Issue Date", "value": issue_date, "handwritten": False},
        {"label": "Color Pages", "value": color_pages, "handwritten": False},
        {"label": "Number of Plates", "value": plates, "handwritten": False},
        {"label": "Total Pages", "value": total_pages, "handwritten": False},
        {"label": "Last Image", "value": "", "handwritten": True},
        {"label": "Last Plate", "value": "", "handwritten": True},
    ]
    color_change_fields = [
        {"label": "Color Addition", "value": "", "handwritten": True},
        {"label": "Color Drop", "value": "", "handwritten": True},
    ]
    extra_fields_map = {
        "STANDARD": [],
        "USAT": [
            {"label": "First Image", "value": "", "handwritten": True},
        ],
        "NYT": [
            {"label": "Kills", "value": "", "handwritten": True},
            {"label": "PS (Postscripts)", "value": "", "handwritten": True},
            {"label": "Closed", "value": "", "handwritten": True},
        ],
    }
    extra_fields = extra_fields_map.get(fmt_key, [])

    def _measure(draw_obj, text, font):
        content = text or ""
        try:
            left, top, right, bottom = draw_obj.textbbox((0, 0), content, font=font)
            return max(0, right - left), max(0, bottom - top)
        except Exception:
            return draw_obj.textsize(content, font=font)

    def _wrap_lines(text, font, max_width, max_lines=2):
        content = str(text or "").strip()
        if not content:
            return [""]
        words = content.split()
        if len(words) <= 1:
            return [content]
        lines = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if _measure(draw, candidate, font)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        while len(lines) > max_lines:
            lines[-2] = f"{lines[-2]} {lines[-1]}".strip()
            lines.pop()
        return lines

    def _fit_text_lines(text, max_width, max_height, max_size, min_size=28, bold=False, max_lines=2):
        content = str(text or "").strip()
        if not content:
            return [""], _render_load_starter_font(max_size, bold=bold)
        for size in range(int(max_size), int(min_size) - 1, -2):
            font = _render_load_starter_font(size, bold=bold)
            lines = _wrap_lines(content, font, max_width, max_lines=max_lines)
            sizes = [_measure(draw, line, font) for line in lines]
            widths = [w for w, _h in sizes] or [0]
            heights = [h for _w, h in sizes] or [0]
            line_gap = max(10, int(size * 0.18))
            total_h = sum(heights) + line_gap * max(0, len(lines) - 1)
            if max(widths) <= max_width and total_h <= max_height:
                return lines, font
        font = _render_load_starter_font(min_size, bold=bold)
        return _wrap_lines(content, font, max_width, max_lines=max_lines), font

    def _draw_centered_lines(lines, font, box, fill="black"):
        x0, y0, x1, y1 = [int(v) for v in box]
        lines = list(lines or [""])
        sizes = [_measure(draw, line, font) for line in lines]
        heights = [h for _w, h in sizes] or [0]
        font_size = getattr(font, "size", 48)
        line_gap = max(10, int(font_size * 0.18))
        total_h = sum(heights) + line_gap * max(0, len(lines) - 1)
        y = y0 + max(0, int(((y1 - y0) - total_h) / 2))
        for line, (width, height) in zip(lines, sizes):
            x = x0 + max(0, int(((x1 - x0) - width) / 2))
            draw.text((x, y), line or "", fill=fill, font=font)
            y += height + line_gap

    def _draw_field_block(box, label, value="", handwritten=False, label_max_size=56, value_max_size=88):
        x0, y0, x1, y1 = [int(v) for v in box]
        radius = 26
        border = 6
        label_band_h = max(104, int((y1 - y0) * 0.28))
        draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, outline="black", width=border)
        draw.rounded_rectangle((x0 + border, y0 + border, x1 - border, y0 + label_band_h), radius=max(8, radius - 8), fill="#f2f2f2")
        draw.line((x0 + border, y0 + label_band_h, x1 - border, y0 + label_band_h), fill="black", width=4)

        label_lines, label_font = _fit_text_lines(
            label,
            max_width=max(100, (x1 - x0) - 70),
            max_height=max(40, label_band_h - 26),
            max_size=label_max_size,
            min_size=26,
            bold=True,
            max_lines=2,
        )
        _draw_centered_lines(label_lines, label_font, (x0 + 24, y0 + 10, x1 - 24, y0 + label_band_h - 10))

        content_box = (x0 + 34, y0 + label_band_h + 18, x1 - 34, y1 - 30)
        if handwritten:
            line_y = y1 - 78
            draw.line((content_box[0] + 8, line_y, content_box[2] - 8, line_y), fill="black", width=5)
        else:
            value_lines, value_font = _fit_text_lines(
                value,
                max_width=max(100, content_box[2] - content_box[0]),
                max_height=max(40, content_box[3] - content_box[1]),
                max_size=value_max_size,
                min_size=32,
                bold=True,
                max_lines=2,
            )
            _draw_centered_lines(value_lines, value_font, content_box)

    publication_box = (margin, 70, page_w - margin, 310)
    _draw_field_block(
        publication_box,
        "Publication",
        publication,
        handwritten=False,
        label_max_size=62,
        value_max_size=116,
    )

    common_top = 360
    common_field_h = 300
    common_rows = 3
    common_cols = 2
    common_field_w = int((page_w - (2 * margin) - gap) / common_cols)

    common_fields_for_draw = list(common_fields)
    for index, field in enumerate(common_fields_for_draw):
        row = index // common_cols
        col = index % common_cols
        x0 = margin + col * (common_field_w + gap)
        y0 = common_top + row * (common_field_h + gap)
        x1 = x0 + common_field_w
        y1 = y0 + common_field_h
        _draw_field_block(
            (x0, y0, x1, y1),
            field.get("label", ""),
            field.get("value", ""),
            handwritten=bool(field.get("handwritten")),
            label_max_size=58,
            value_max_size=88,
        )

    color_change_top = common_top + common_rows * (common_field_h + gap)
    for index, field in enumerate(color_change_fields):
        col = index % common_cols
        x0 = margin + col * (common_field_w + gap)
        y0 = color_change_top
        x1 = x0 + common_field_w
        y1 = y0 + common_field_h
        _draw_field_block(
            (x0, y0, x1, y1),
            field.get("label", ""),
            field.get("value", ""),
            handwritten=True,
            label_max_size=58,
            value_max_size=88,
        )

    extras_top = color_change_top + common_field_h + gap + 10
    if fmt_key == "USAT" and extra_fields:
        field = extra_fields[0]
        extra_box = (margin, extras_top, margin + common_field_w, extras_top + common_field_h)
        _draw_field_block(
            extra_box,
            field.get("label", ""),
            field.get("value", ""),
            handwritten=True,
            label_max_size=58,
            value_max_size=88,
        )
    elif fmt_key == "NYT" and extra_fields:
        draw.line((margin, extras_top + 78, page_w - margin, extras_top + 78), fill="black", width=4)
        nyt_top = extras_top + 110
        nyt_row1_y0 = nyt_top
        nyt_row1_y1 = nyt_row1_y0 + common_field_h
        nyt_row2_y0 = nyt_row1_y1 + gap
        nyt_row2_y1 = nyt_row2_y0 + common_field_h
        nyt_positions = [
            (margin, nyt_row1_y0, margin + common_field_w, nyt_row1_y1),
            (margin + common_field_w + gap, nyt_row1_y0, page_w - margin, nyt_row1_y1),
            (margin, nyt_row2_y0, page_w - margin, nyt_row2_y1),
        ]
        nyt_label_sizes = [46, 46, 50]
        nyt_value_sizes = [80, 80, 84]
        for field, box, label_size, value_size in zip(extra_fields, nyt_positions, nyt_label_sizes, nyt_value_sizes):
            _draw_field_block(
                box,
                field.get("label", ""),
                field.get("value", ""),
                handwritten=True,
                label_max_size=label_size,
                value_max_size=value_size,
            )
    return img



def get_default_printer_name():
    try:
        import win32print
    except Exception as e:
        raise RuntimeError(f"Missing win32print dependency: {e}")
    try:
        printer_name = win32print.GetDefaultPrinter()
    except Exception as e:
        raise RuntimeError(f"Could not get the default printer: {e}")
    printer_name = str(printer_name or '').strip()
    if not printer_name:
        raise RuntimeError("No default printer is configured on this system.")
    return printer_name


def direct_print_image_file(img_path, printer_name=None, copies=1, orientation="Landscape", margins_inches=None, align_top=False, position_adjust_inches=None, trim_whitespace=True):
    printer_name = str(printer_name or '').strip() or get_default_printer_name()
    try:
        import win32ui
        import win32con
        import win32print
        from PIL import Image, ImageWin, ImageChops
        import traceback
    except Exception as e:
        raise RuntimeError(f"Missing dependency: {e}. If win32print/win32ui/win32con are missing, install pywin32.")

    dc = None
    printer_handle = None
    try:
        img = Image.open(img_path)
        img.load()
        if img.mode == 'RGBA' or (hasattr(img, 'getbands') and 'A' in img.getbands()):
            rgba = img.convert('RGBA')
            white_bg = Image.new('RGB', rgba.size, 'white')
            white_bg.paste(rgba, mask=rgba.getchannel('A'))
            img = white_bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Trim white outer padding so the print fills the page more tightly
        # while still respecting the requested printer margins.
        if bool(trim_whitespace):
            try:
                bg = Image.new('RGB', img.size, 'white')
                diff = ImageChops.difference(img, bg)
                bbox = diff.getbbox()
                if bbox:
                    pad = 4
                    left = max(0, int(bbox[0]) - pad)
                    top = max(0, int(bbox[1]) - pad)
                    right = min(int(img.size[0]), int(bbox[2]) + pad)
                    bottom = min(int(img.size[1]), int(bbox[3]) + pad)
                    if right > left and bottom > top:
                        img = img.crop((left, top, right, bottom))
            except Exception:
                pass

        orientation_text = str(orientation or 'Landscape').strip().title()
        if orientation_text not in ('Landscape', 'Portrait'):
            orientation_text = 'Landscape'

        # Force every landscape print job to rotate 90 degrees so the
        # physical print comes out in landscape on this pressroom setup.
        if orientation_text == 'Landscape':
            img = img.transpose(Image.ROTATE_90)
        elif orientation_text == 'Portrait' and img.width > img.height:
            img = img.transpose(Image.ROTATE_90)

        margins_inches = margins_inches or {"left": 0.15, "top": 0.15, "right": 0.15, "bottom": 0.15}

        # Force the printer DEVMODE orientation to match the requested output.
        devmode = None
        try:
            printer_handle = win32print.OpenPrinter(printer_name)
            printer_info = win32print.GetPrinter(printer_handle, 2)
            if isinstance(printer_info, dict):
                devmode = printer_info.get('pDevMode')
            if devmode is not None:
                requested_orientation = 1 if orientation_text == 'Landscape' else 2
                for attr in ('Orientation', 'dmOrientation'):
                    try:
                        setattr(devmode, attr, requested_orientation)
                        break
                    except Exception:
                        pass
                for attr in ('Fields', 'dmFields'):
                    try:
                        setattr(devmode, attr, int(getattr(devmode, attr)) | int(win32con.DM_ORIENTATION))
                        break
                    except Exception:
                        pass
        except Exception:
            devmode = None

        dc = win32ui.CreateDC()
        created_dc = False
        if devmode is not None:
            for create_args in (
                ("WINSPOOL", printer_name, None, devmode),
                (None, printer_name, None, devmode),
            ):
                try:
                    dc.CreateDC(*create_args)
                    created_dc = True
                    break
                except Exception:
                    continue
        if not created_dc:
            dc.CreatePrinterDC(printer_name)

        printable_area = (dc.GetDeviceCaps(win32con.HORZRES), dc.GetDeviceCaps(win32con.VERTRES))
        offset_x = dc.GetDeviceCaps(win32con.PHYSICALOFFSETX)
        offset_y = dc.GetDeviceCaps(win32con.PHYSICALOFFSETY)
        dpi_x = max(1, dc.GetDeviceCaps(win32con.LOGPIXELSX))
        dpi_y = max(1, dc.GetDeviceCaps(win32con.LOGPIXELSY))

        # Keep the already-rotated image orientation stable.
        if orientation_text == 'Portrait' and printable_area[0] > printable_area[1] and img.width > img.height:
            img = img.transpose(Image.ROTATE_90)

        left_margin = max(0, int(round(float(margins_inches.get("left", 0.15)) * dpi_x)))
        top_margin = max(0, int(round(float(margins_inches.get("top", 0.15)) * dpi_y)))
        right_margin = max(0, int(round(float(margins_inches.get("right", 0.15)) * dpi_x)))
        bottom_margin = max(0, int(round(float(margins_inches.get("bottom", 0.15)) * dpi_y)))
        safe_w = max(1, printable_area[0] - left_margin - right_margin)
        safe_h = max(1, printable_area[1] - top_margin - bottom_margin)
        scale = min(safe_w / float(img.size[0]), safe_h / float(img.size[1]))
        scaled = img.resize((max(1, int(img.size[0] * scale)), max(1, int(img.size[1] * scale))), Image.LANCZOS)
        dib = ImageWin.Dib(scaled)
        # Starter sheets are rendered landscape and then rotated on the shared
        # landscape print path. On paper, the physical top/bottom axis maps to the
        # rotated image X axis, while the physical left/right axis maps to Y.
        # So for align_top=True we must anchor X to the top margin while keeping Y
        # centered so the printed sheet is top-aligned and still centered horizontally.
        if align_top and orientation_text == 'Landscape':
            x = int(offset_x + left_margin)
            y = int(offset_y + top_margin + ((safe_h - scaled.size[1]) / 2))
        else:
            x = int(offset_x + left_margin + ((safe_w - scaled.size[0]) / 2))
            y = int(offset_y + top_margin) if align_top else int(offset_y + top_margin + ((safe_h - scaled.size[1]) / 2))

        position_adjust_inches = position_adjust_inches if isinstance(position_adjust_inches, dict) else {}
        adjust_x = max(0, int(round(float(position_adjust_inches.get("x", 0.0)) * dpi_x)))
        adjust_y = max(0, int(round(float(position_adjust_inches.get("y", 0.0)) * dpi_y)))
        min_x = int(offset_x + left_margin)
        min_y = int(offset_y + top_margin)
        max_x = int(offset_x + left_margin + max(0, safe_w - scaled.size[0]))
        max_y = int(offset_y + top_margin + max(0, safe_h - scaled.size[1]))
        x = max(min_x, min(max_x, int(x + adjust_x)))
        y = max(min_y, min(max_y, int(y + adjust_y)))

        dc.StartDoc(img_path)
        for _ in range(max(1, int(copies or 1))):
            dc.StartPage()
            dib.draw(dc.GetHandleOutput(), (x, y, x + scaled.size[0], y + scaled.size[1]))
            dc.EndPage()
        dc.EndDoc()
        return True
    except Exception as e:
        try:
            err = traceback.format_exc()
        except Exception:
            err = str(e)
        raise RuntimeError(err)
    finally:
        try:
            if dc is not None:
                dc.DeleteDC()
        except Exception:
            pass
        try:
            if printer_handle is not None:
                win32print.ClosePrinter(printer_handle)
        except Exception:
            pass


def _print_layout_data_to_default_printer(data, copies=5):
    data = data if isinstance(data, dict) else {}
    press_name = data.get('press') or ''
    format_name = data.get('format') or ''
    cfg = CONFIG_MAP.get((press_name, format_name))
    if not isinstance(cfg, dict):
        raise RuntimeError(f"No config found for {press_name} - {format_name}.")
    img = render_layout_print_image_from_data(data, dict(cfg), title_base=f"{press_name} - {format_name}", template_mode=False)
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    try:
        img.save(path, format='PNG', dpi=(300, 300))
        return direct_print_image_file(path, copies=max(1, int(copies or 1)), orientation='Landscape', align_top=False)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def _print_starter_sheet_data_to_default_printer(data, copies=1, printer_name=None):
    data = data if isinstance(data, dict) else {}
    img = make_starter_sheet_image_from_data(data)
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    try:
        img.save(path, format='PNG', dpi=(300, 300))
        starter_sheet_margins = {"left": 0.05, "top": 0.05, "right": 0.05, "bottom": 0.375}
        return direct_print_image_file(
            path,
            printer_name=printer_name,
            copies=max(1, int(copies or 1)),
            orientation='Landscape',
            margins_inches=starter_sheet_margins,
            align_top=True,
            trim_whitespace=True,
        )
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
def build_press_layout(win, title="Press Layout", config=None, load_path=None, load_as_copy=False, initial_data=None):
    config = config or {}

    def _unit_has_any_pages(unit_data):
        for row in unit_data.get("grid", []) or []:
            for cell in row:
                if str(cell or "").strip():
                    return True
        return False

    def _blank_grid(rows, cols):
        return [["" for _ in range(cols)] for _ in range(rows)]

    def _converted_press_data(data, old_press, new_press):
        data = json.loads(json.dumps(data or {}))
        if old_press == new_press:
            data["press"] = new_press
            return data
        press_map = {
            ("Press 1", "Press 2"): {
                "E1": "E2", "D1": "D2", "C1": "C2",
                "B1-Lower": "B2-Lower", "B1-Upper": "B2-Upper", "A1": "A2",
                "F1": "F2", "G1-Lower": "G2-Lower", "G1-Upper": "G2-Upper",
            },
            ("Press 2", "Press 1"): {
                "E2": "E1", "D2": "D1", "C2": "C1",
                "B2-Lower": "B1-Lower", "B2-Upper": "B1-Upper", "A2": "A1",
                "F2": "F1", "G2-Lower": "G1-Lower", "G2-Upper": "G1-Upper",
            },
        }.get((old_press, new_press), {})
        target_cfg = CONFIG_MAP.get((new_press, data.get("format") or config.get("format_name") or "Broadsheet"), {})
        target_labels = list(target_cfg.get("left_labels", [])) + list(target_cfg.get("right_labels", []))
        rows = int(target_cfg.get("grid_rows", 2) or 2)
        cols = int(target_cfg.get("grid_cols", 2) or 2)
        source_units = {str(u.get("label") or ""): u for u in (data.get("units", []) or [])}
        converted_units = []
        for label in target_labels:
            source_label = next((k for k, v in press_map.items() if v == label), None)
            unit = dict(source_units.get(source_label) or {"label": label, "section": "", "grid": _blank_grid(rows, cols)})
            unit["label"] = label
            converted_units.append(unit)
        color_items = []
        for item in data.get("color_cells", []) or []:
            new_label = press_map.get(str(item.get("unit") or ""))
            if not new_label:
                continue
            new_item = dict(item)
            new_item["unit"] = new_label
            color_items.append(new_item)
        data["units"] = converted_units
        data["color_cells"] = color_items
        data["press"] = new_press
        return data

    def _format_reset_data(data, new_format):
        data = json.loads(json.dumps(data or {}))
        press_name = data.get("press") or config.get("press_name") or "Press 1"
        target_cfg = CONFIG_MAP.get((press_name, new_format), {})
        target_labels = list(target_cfg.get("left_labels", [])) + list(target_cfg.get("right_labels", []))
        rows = int(target_cfg.get("grid_rows", 2) or 2)
        cols = int(target_cfg.get("grid_cols", 2) or 2)
        data["units"] = [{"label": label, "section": "", "grid": _blank_grid(rows, cols)} for label in target_labels]
        data["color_cells"] = []
        data["format"] = new_format
        return data

    style = ttk.Style(win)
    style.configure("Unit.TFrame", background="#f0f0f0", relief="solid", borderwidth=1)
    style.configure("Box.TFrame", background="#ffffff", relief="solid", borderwidth=1)
    style.configure("SlideToggle.TCheckbutton",
                    indicatoron=False,
                    relief="flat",
                    padding=(8, 4),
                    background="#d9d9d9",
                    foreground="#000000")
    style.map("SlideToggle.TCheckbutton",
              background=[("selected", "#4caf50"), ("!selected", "#e0e0e0")],
              foreground=[("selected", "#ffffff"), ("!selected", "#000000")])

    title_base = title
    win.title(title_base)

    template_mode = bool(config.get("template_mode", False))
    regular_mode = bool(config.get("regular_mode", False))
    window_state_key = "template_layout_window" if template_mode else ("regular_layout_window" if regular_mode else "layout_window")
    has_saved_window_state = bool(load_window_state_map().get(window_state_key))

    header_frame = ttk.Frame(win, padding=(16, 12, 16, 8))
    header_frame.pack(fill="x")

    ttk.Label(header_frame, text="Issue Date:", font=(None, 12, "bold")).grid(row=0, column=0, sticky="w")
    issue_entry = ttk.Entry(header_frame, width=16, font=(None, 12))
    issue_entry.grid(row=0, column=1, sticky="w", padx=(8, 32))

    product_entry = ttk.Entry(header_frame, font=(None, 14), width=35, justify="center")
    product_entry.grid(row=0, column=3, columnspan=2, sticky="w", padx=(8, 12))

    # Imposition next to product
    imposition_var = tk.StringVar(value="")
    imposition_frame = ttk.Frame(header_frame)
    imposition_frame.grid(row=0, column=5, sticky="ew", padx=(0, 12))
    ttk.Label(imposition_frame, text="Imposition:", font=(None, 11, "bold")).pack(side="left", padx=(0, 6))
    imposition_entry = ttk.Entry(
        imposition_frame,
        textvariable=imposition_var,
        font=(None, 11),
        width=28,
        justify="center",
        state="readonly",
        takefocus=False
    )
    imposition_entry.pack(side="left", fill="x", expand=True)

    editor_setup_frame = ttk.Frame(header_frame)
    editor_setup_frame.grid(row=0, column=6, sticky="e")
    ttk.Label(editor_setup_frame, text="Press:", font=(None, 11, "bold")).pack(side="left", padx=(0, 6))
    press_selector_var = tk.StringVar(value=config.get("press_name", "Press 1") or "Press 1")
    ttk.Combobox(editor_setup_frame, textvariable=press_selector_var, values=["Press 1", "Press 2"], state="readonly", width=10).pack(side="left", padx=(0, 12))
    ttk.Label(editor_setup_frame, text="Format:", font=(None, 11, "bold")).pack(side="left", padx=(0, 6))
    format_selector_var = tk.StringVar(value=config.get("format_name", "Broadsheet") or "Broadsheet")
    ttk.Combobox(editor_setup_frame, textvariable=format_selector_var, values=["Broadsheet", "Tab", "8 up"], state="readonly", width=12).pack(side="left")

    header_frame.columnconfigure(2, weight=1)
    header_frame.columnconfigure(3, weight=1)
    header_frame.columnconfigure(4, weight=1)
    header_frame.columnconfigure(5, weight=1)

    controls_outer_frame = ttk.Frame(win, padding=(16, 0, 16, 12))
    controls_center_frame = ttk.Frame(controls_outer_frame)
    controls_center_frame.pack(anchor="center")
    btn_frame = ttk.Frame(controls_center_frame)

    # template mode disables issue/product; regular mode disables issue date only
    if template_mode or regular_mode:
        issue_entry.state(["disabled"])
    if template_mode:
        product_entry.state(["disabled"])

    # Sections
    section_count_var = tk.StringVar(value=str(config.get("section_count", 1)))
    section_page_vars = []
    section_page_entries = []

    ttk.Label(header_frame, text="Sections:", font=(None, 12, "bold")).grid(row=1, column=0, sticky="w", pady=6)
    ttk.Label(header_frame, text="Names:", font=(None, 12, "bold")).grid(row=2, column=0, sticky="w", pady=6)
    ttk.Label(header_frame, text="Pages:", font=(None, 12, "bold")).grid(row=3, column=0, sticky="w", pady=6)
    sections_frame = ttk.Frame(header_frame)
    sections_frame.grid(row=1, column=1, sticky="w", padx=(8, 32))
    section_count_radios = []
    for idx in range(4):
        radio = ttk.Radiobutton(
            sections_frame,
            text=str(idx + 1),
            value=str(idx + 1),
            variable=section_count_var,
            width=3,
        )
        radio.grid(row=0, column=idx, sticky="w", padx=(0 if idx == 0 else 6, 0))
        section_count_radios.append(radio)

    section_detail_frame = ttk.Frame(header_frame)
    section_detail_frame.grid(row=2, column=1, rowspan=2, columnspan=5, sticky="w", padx=(8, 0), pady=(0, 6))

    format_name = config.get("format_name", "")
    page_increment = min_pages_for_format(format_name)
    max_pages = page_increment * 10

    initial_pages = config.get("section_pages", [0] * 4)
    # Section names (editable labels for S1..S4)
    initial_names = config.get("section_names")
    # determine initial enabled section count (from config/var)
    try:
        init_count = max(1, min(4, int(section_count_var.get())))
    except Exception:
        init_count = 1

    if initial_names is None:
        if template_mode:
            base_names = [f"S{i+1}" for i in range(4)]
        else:
            base_names = ["A", "B", "C", "D"]
        initial_names = [base_names[i] if i < init_count else "" for i in range(4)]

    section_name_vars = []
    section_name_entries = []

    def _current_section_choices():
        choices = [""]
        try:
            count = max(1, min(4, int(section_count_var.get())))
        except Exception:
            count = 1
        for i in range(count):
            try:
                name = (section_name_vars[i].get() or "").strip().upper()
            except Exception:
                name = ""
            if not name:
                name = "S" + str(i + 1) if template_mode else chr(ord("A") + i)
            choices.append(name)
        return choices

    unit_section_assignments = {}

    def _section_display_name(section_id, names_snapshot=None):
        try:
            sid = int(section_id)
        except Exception:
            return ""
        if sid < 1 or sid > 4:
            return ""
        try:
            count = max(1, min(4, int(section_count_var.get())))
        except Exception:
            count = 1
        if sid > count:
            return ""
        try:
            if names_snapshot is not None:
                name = (names_snapshot[sid - 1] or "").strip().upper()
            else:
                name = (section_name_vars[sid - 1].get() or "").strip().upper()
        except Exception:
            name = ""
        if not name:
            name = f"S{sid}" if template_mode else chr(ord("A") + sid - 1)
        return name

    def _resolve_section_assignment_id(text, names_snapshot=None):
        raw = (text or "").strip().upper()
        if not raw:
            return None
        try:
            count = max(1, min(4, int(section_count_var.get())))
        except Exception:
            count = 1
        # Always prefer the displayed section names (or the provided snapshot)
        # before falling back to canonical parsing. This makes section renames
        # bulletproof even when users rename sections to letter-based names such
        # as A/B/C/D that would otherwise collide with canonical section ids.
        for idx in range(count):
            display = _section_display_name(idx + 1, names_snapshot=names_snapshot)
            if raw == display:
                return idx + 1
        parsed = parse_section_id(raw)
        if parsed is not None and 1 <= parsed <= count:
            return parsed
        return None

    def _set_unit_section_value(entry_widget, value):
        value = "" if value is None else str(value).strip().upper()
        try:
            entry_widget.set(value)
            return
        except Exception:
            pass
        try:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, value)
        except Exception:
            pass

    def _capture_unit_section_assignments(names_snapshot=None):
        for u in units:
            try:
                cur = (u["section_entry"].get() or "").strip()
            except Exception:
                cur = ""
            unit_section_assignments[u["label"]] = _resolve_section_assignment_id(cur, names_snapshot=names_snapshot)

    def _record_unit_section_assignment(unit_dict):
        try:
            raw = (unit_dict["section_entry"].get() or "").strip()
        except Exception:
            raw = ""
        unit_section_assignments[unit_dict["label"]] = _resolve_section_assignment_id(raw)

    def _refresh_unit_section_choices():
        choices = _current_section_choices()
        try:
            count = max(1, min(4, int(section_count_var.get())))
        except Exception:
            count = 1
        for u in units:
            try:
                section_entry = u["section_entry"]
                section_entry.configure(values=choices)
                assigned_id = unit_section_assignments.get(u["label"])
                if assigned_id is None:
                    assigned_id = _resolve_section_assignment_id(section_entry.get())
                    unit_section_assignments[u["label"]] = assigned_id
                if assigned_id is not None and 1 <= assigned_id <= count:
                    _set_unit_section_value(section_entry, _section_display_name(assigned_id))
                else:
                    cur = (section_entry.get() or "").strip().upper()
                    if cur and cur not in choices:
                        _set_unit_section_value(section_entry, "")
                        unit_section_assignments[u["label"]] = None
            except Exception:
                pass

    for idx in range(4):
        name_value = str(initial_names[idx] if idx < len(initial_names) else "")
        nvar = tk.StringVar(value=name_value)
        section_name_vars.append(nvar)
        entry = ttk.Entry(section_detail_frame, textvariable=nvar, width=6, justify="center", font=(None, 10))
        entry.grid(row=0, column=idx, sticky="w", padx=(0 if idx == 0 else 6, 0))
        section_name_entries.append(entry)

    section_page_labels = []
    for idx in range(4):
        page_value = str(initial_pages[idx] if idx < len(initial_pages) else 0)
        var = tk.StringVar(value=page_value)
        section_page_vars.append(var)
        lbl = ttk.Label(section_detail_frame, textvariable=var, width=6, anchor="center")
        lbl.grid(row=1, column=idx, sticky="w", padx=(0 if idx == 0 else 6, 0), pady=(18, 0))
        section_page_labels.append(lbl)

    def _refresh_section_page_counts():
        try:
            count = max(1, min(4, int(section_count_var.get())))
        except Exception:
            count = 1

        # Recompute directly from the live editor context so section name edits
        # immediately reflect in the page-count labels and do not depend on any
        # cached unit-to-section mapping state.
        try:
            counts = compute_section_page_counts_from_ctx(ctx, section_count=count)
        except Exception:
            counts = [0] * count

        for idx in range(4):
            if idx < count:
                value = counts[idx] if idx < len(counts) else 0
                section_page_vars[idx].set(str(value))
            else:
                section_page_vars[idx].set("")

    def _update_section_page_states(count):
        for idx, _label in enumerate(section_page_labels):
            if idx < count:
                try:
                    section_name_entries[idx].state(["!disabled"])
                except Exception:
                    pass
                try:
                    cur = (section_name_vars[idx].get() or "").strip()
                    if cur == "":
                        if template_mode:
                            section_name_vars[idx].set(f"S{idx+1}")
                        else:
                            section_name_vars[idx].set(chr(ord('A') + idx))
                except Exception:
                    pass
            else:
                section_page_vars[idx].set("")
                try:
                    section_name_entries[idx].state(["disabled"])
                    section_name_vars[idx].set("")
                except Exception:
                    pass
        for _label, _section_id in list(unit_section_assignments.items()):
            try:
                if _section_id is not None and int(_section_id) > count:
                    unit_section_assignments[_label] = None
            except Exception:
                pass
        _refresh_unit_section_choices()
        _refresh_section_page_counts()

    # Press area
    press_area_frame = ttk.Frame(win, padding=(16, 0, 16, 12))
    press_area_frame.pack(fill="both", expand=True)
    controls_outer_frame.pack(fill="x")

    enable_hscroll = config.get("enable_hscroll", False)
    _, press_frame, _canvas = make_press_area(press_area_frame, enable_hscroll=enable_hscroll,
                                              height_hint=config.get("scroll_height_hint", 340))

    left_labels = config.get("left_labels", [])
    right_labels = config.get("right_labels", [])
    only_k_labels = set(config.get("only_k_labels", set()))
    folder_label = config.get("folder_label", "Folder")

    grid_rows = config.get("grid_rows", 2)
    grid_cols = config.get("grid_cols", 2)

    swatch_cols = config.get("swatch_cols", 2)
    cell_pad = config.get("cell_pad", 0)

    midline_thickness = config.get("midline_thickness", 4)
    midline_color = config.get("midline_color", "#444444")

    unit_padding = config.get("unit_padding", (6, 6, 6, 6))
    unit_padx = config.get("unit_padx", 6)
    unit_pady = config.get("unit_pady", 6)
    folder_padx = config.get("folder_padx", 24)
    folder_padding = config.get("folder_padding", (8, 8, 8, 8))

    cell_font = config.get("cell_font", None)
    cell_width = config.get("cell_width", None)

    units = []

    # Left bank
    for idx, label in enumerate(left_labels):
        use_cmyk = label not in only_k_labels
        unit_frame, section_entry, grid_entries, cell_overlays = create_press_unit(
            press_frame,
            label,
            use_cmyk=use_cmyk,
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            swatch_cols=swatch_cols,
            cell_pad=cell_pad,
            midline_thickness=midline_thickness,
            midline_color=midline_color,
            unit_padding=unit_padding,
            cell_font=cell_font,
            cell_width=cell_width,
            section_choices=_current_section_choices(),
        )
        unit_frame.grid(row=0, column=idx, padx=unit_padx, pady=unit_pady, sticky="n")
        units.append({
            "label": label,
            "frame": unit_frame,
            "section_entry": section_entry,
            "entries": grid_entries,
            "overlays": cell_overlays,
            "color_capable": bool(use_cmyk),
        })

    # Folder
    folder_frame = ttk.Frame(press_frame, padding=folder_padding)
    folder_frame.grid(row=0, column=len(left_labels), padx=folder_padx, sticky="n")

    arrow_canvas = tk.Canvas(folder_frame, width=140, height=170, highlightthickness=0, background=win.cget("bg"))
    arrow_canvas.pack(pady=(0, 8))
    arrow_canvas.create_polygon(55, 14, 85, 14, 70, 44, fill="#666666", outline="#666666")
    arrow_canvas.create_polygon(55, 64, 85, 64, 70, 94, fill="#666666", outline="#666666")
    arrow_canvas.create_polygon(55, 114, 85, 114, 70, 144, fill="#666666", outline="#666666")
    arrow_canvas.create_polygon(15, 64, 45, 64, 30, 94, fill="#666666", outline="#666666")
    ttk.Label(folder_frame, text=folder_label, font=(None, 12, "bold")).pack()

    # Right bank
    for idx, label in enumerate(right_labels):
        use_cmyk = label not in only_k_labels
        unit_frame, section_entry, grid_entries, cell_overlays = create_press_unit(
            press_frame,
            label,
            use_cmyk=use_cmyk,
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            swatch_cols=swatch_cols,
            cell_pad=cell_pad,
            midline_thickness=midline_thickness,
            midline_color=midline_color,
            unit_padding=unit_padding,
            cell_font=cell_font,
            cell_width=cell_width,
            section_choices=_current_section_choices(),
        )
        unit_frame.grid(row=0, column=len(left_labels) + 1 + idx, padx=unit_padx, pady=unit_pady, sticky="n")
        units.append({
            "label": label,
            "frame": unit_frame,
            "section_entry": section_entry,
            "entries": grid_entries,
            "overlays": cell_overlays,
            "color_capable": bool(use_cmyk),
        })

    # Context
    # count vars (defined before ctx so ctx can reference them)
    color_pages_var = tk.StringVar(value="0")
    plates_var = tk.StringVar(value="0")
    ctx = {
        "title_base": title_base,
        "press_name": config.get("press_name", ""),
        "format_name": format_name,
        "template_mode": template_mode,
        "regular_mode": regular_mode,
        "default_dir": config.get("default_dir", TEMPLATE_DIR if template_mode else (REGULAR_DIR if regular_mode else LAYOUTS_DIR)),
        "issue_entry": issue_entry,
        "product_entry": product_entry,
        "section_count_var": section_count_var,
        "section_page_vars": section_page_vars,
        "_update_section_page_states": _update_section_page_states,
        "imposition_var": imposition_var,
        "section_name_vars": section_name_vars,
        "section_name_entries": section_name_entries,
        "_refresh_unit_section_choices": _refresh_unit_section_choices,
        "_refresh_section_page_counts": _refresh_section_page_counts,
        "_capture_unit_section_assignments": _capture_unit_section_assignments,
        "imposition_entry": imposition_entry,
        "color_pages_var": color_pages_var,
        "plates_var": plates_var,
        "grid_cols": grid_cols,
        "press_selector_var": press_selector_var,
        "format_selector_var": format_selector_var,
        "units": units,
        "file_path": None,
        "layout_name": None,
        "template_mode": template_mode,
        "default_dir": config.get("default_dir", TEMPLATE_DIR if template_mode else LAYOUTS_DIR),
        "prompt_save_template": bool(config.get("prompt_save_template", not template_mode)),
        "color_cells": set(),  # per-cell storage
    }
    try:
        win._press_layout_ctx = ctx
    except Exception:
        pass

    # Propagate section name changes to unit section entries.
    try:
        section_name_prev = [v.get().strip().upper() for v in section_name_vars]
    except Exception:
        section_name_prev = ["", "", "", ""]

    # Uppercase enforcement for section name entries (via key release, preserving cursor)
    def _make_section_uppercase_trace(i):
        def _on_section_input(event=None):
            try:
                entry = section_name_entries[i]
                current = entry.get()
                upper = current.upper()
                if current != upper:
                    try:
                        cursor_pos = entry.index("insert")
                    except Exception:
                        cursor_pos = None
                    entry.delete(0, "end")
                    entry.insert(0, upper)
                    if cursor_pos is not None:
                        try:
                            entry.icursor(min(cursor_pos, len(upper)))
                        except Exception:
                            pass
            except Exception:
                pass
        return _on_section_input

    for i in range(len(section_name_entries)):
        try:
            section_name_entries[i].bind('<KeyRelease>', _make_section_uppercase_trace(i))
        except Exception:
            pass

    def _make_name_trace(i):
        def _on_name_change(*_):
            try:
                previous_names = list(section_name_prev)
                # Capture the stable assignment ids using the names before this edit.
                _capture_unit_section_assignments(names_snapshot=previous_names)

                new = (section_name_vars[i].get() or "").strip().upper()
                old = previous_names[i]

                # Ignore the transient blank while the user replaces a name.
                if new == "":
                    return

                if new == old:
                    section_name_prev[i] = new
                    _refresh_unit_section_choices()
                    return

                section_name_prev[i] = new
                _refresh_unit_section_choices()
                _refresh_section_page_counts()
            except Exception:
                pass
        return _on_name_change

    for i in range(len(section_name_vars)):
        try:
            section_name_vars[i].trace_add("write", _make_name_trace(i))
        except Exception:
            pass

    # ---- Color Select toggle (layouts only) ----
    color_select_var = tk.BooleanVar(value=False)
    color_toggle = None
    all_color_btn = None
    all_bw_btn = None
    if not template_mode:
        color_toggle = ttk.Checkbutton(
            btn_frame,
            style="SlideToggle.TCheckbutton",
            text="Color Select",
            variable=color_select_var,
            takefocus=False
        )
        color_toggle.pack(side="left", padx=(0, 8))

    starter_format_var = tk.StringVar(value="Standard")
    ctx["starter_format_var"] = starter_format_var

    def _persist_starter_format_to_file():
        if template_mode:
            return
        path = ctx.get("file_path")
        if not path:
            return
        try:
            data = safe_read_json(path)
            if not isinstance(data, dict):
                return
            data["starter_format"] = starter_format_var.get().strip() or "Standard"
            safe_write_json(path, data)
        except Exception:
            pass

    def _set_publication_entry_text(value):
        normalized = normalize_publication_name(value)
        try:
            current = product_entry.get()
        except Exception:
            current = ""
        if current == normalized:
            return normalized
        try:
            cursor_index = product_entry.index("insert")
        except Exception:
            cursor_index = None
        try:
            sel_start = product_entry.index("sel.first")
            sel_end = product_entry.index("sel.last")
        except Exception:
            sel_start = None
            sel_end = None
        try:
            product_entry.delete(0, "end")
            product_entry.insert(0, normalized)
            if sel_start is not None and sel_end is not None:
                product_entry.selection_range(min(sel_start, len(normalized)), min(sel_end, len(normalized)))
            elif cursor_index is not None:
                product_entry.icursor(min(cursor_index, len(normalized)))
        except Exception:
            pass
        return normalized

    def _normalize_publication_entry(event=None):
        if template_mode:
            return normalize_publication_name(product_entry.get())
        return _set_publication_entry_text(product_entry.get())

    def _prompt_update_starter_before_save():
        if template_mode:
            return
        publication_name = _normalize_publication_entry()
        current_starter = (starter_format_var.get() or "Standard").strip() or "Standard"
        current_upper = current_starter.upper()
        desired = _desired_starter_format_for_publication(publication_name)
        if not desired or current_upper == desired:
            return
        if desired == "NYT":
            reason_text = "The publication name contains NYT"
        else:
            reason_text = "The publication name contains USAT and does not contain the word CO"
        if messagebox.askyesno(
            "Update Starter Format?",
            f"{reason_text}, but Starter is set to {current_starter}.\n\nWould you like to change Starter to {desired} before saving?",
            parent=win,
        ):
            starter_format_var.set(desired)

    def do_save_with_starter():
        _prompt_update_starter_before_save()
        ok = do_save(win, ctx)
        if ok:
            _persist_starter_format_to_file()
            try:
                _reset_dirty_tracking(False)
            except Exception:
                try:
                    ctx["dirty"] = False
                except Exception:
                    pass
        return ok

    def do_save_as_with_starter():
        _prompt_update_starter_before_save()
        ok = do_save_as(win, ctx)
        if ok:
            _persist_starter_format_to_file()
            try:
                _reset_dirty_tracking(False)
            except Exception:
                try:
                    ctx["dirty"] = False
                except Exception:
                    pass
        return ok


    def do_save_as_regular_with_starter():
        if template_mode or regular_mode:
            return False
        _prompt_update_starter_before_save()
        ok, _path = save_regular_from_layout(ctx, parent=win)
        if ok:
            try:
                _reset_dirty_tracking(False)
            except Exception:
                try:
                    ctx["dirty"] = False
                except Exception:
                    pass
        return ok
    def _starter_sheet_fields():
        try:
            update_color_and_plate_counts()
        except Exception:
            pass
        raw_issue = issue_entry.get().strip()
        dt = parse_issue_date_flexible(raw_issue)
        issue_text = dt.strftime("%m/%d/%Y") if dt else raw_issue
        total_pages = 0
        try:
            section_count = max(1, min(4, int(section_count_var.get())))
        except Exception:
            try:
                section_count = len(section_page_vars)
            except Exception:
                section_count = 0
        for idx in range(max(0, min(int(section_count or 0), len(section_page_vars)))):
            try:
                page_value = (section_page_vars[idx].get() or "").strip()
            except Exception:
                page_value = ""
            if not page_value:
                continue
            try:
                total_pages += int(page_value)
            except Exception:
                pass
        return {
            "publication": normalize_publication_name(product_entry.get().strip()),
            "issue_date": issue_text,
            "color_pages": (ctx.get("color_pages_var", color_pages_var).get() or "").strip(),
            "plates": (ctx.get("plates_var", plates_var).get() or "").strip(),
            "total_pages": str(total_pages),
        }

    def _render_load_starter_font(size, bold=False):
        try:
            from PIL import ImageFont
        except Exception:
            return None
        font_names = []
        if bold:
            font_names.extend(["arialbd.ttf", "Arial Bold.ttf", "ARIALBD.TTF", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"])
        font_names.extend(["arial.ttf", "Arial.ttf", "ARIAL.TTF", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"])
        search_paths = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"), "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation2", "/usr/share/fonts/truetype/liberation"]
        for folder in search_paths:
            for name in font_names:
                try:
                    candidate = os.path.join(folder, name)
                    if os.path.exists(candidate):
                        return ImageFont.truetype(candidate, size=size)
                except Exception:
                    pass
        for name in font_names:
            try:
                return ImageFont.truetype(name, size=size)
            except Exception:
                pass
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    def _draw_line(draw, xy, width=4):
        draw.line(xy, fill="black", width=width)

    def _draw_text(draw, xy, text, font):
        draw.text(xy, text or "", fill="black", font=font)


    def _make_starter_sheet_image(format_name, fields):
        data = collect_layout_data(ctx)
        data = data if isinstance(data, dict) else {}
        if format_name:
            data["starter_format"] = str(format_name or "").strip()
        return make_starter_sheet_image_from_data(data, format_name=format_name)

    def _show_print_dialog(dialog_title="Print", default_copies=1):
        try:
            import win32print
        except Exception as e:
            raise RuntimeError(f"Missing win32print dependency: {e}")
        try:
            printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
        except Exception as e:
            raise RuntimeError(f"Could not enumerate printers: {e}")
        printer_names = [info[2] for info in printers if info and len(info) >= 3 and info[2]]
        if not printer_names:
            raise RuntimeError("No printers were found on this system.")
        try:
            default_printer = win32print.GetDefaultPrinter()
        except Exception:
            default_printer = None
        if default_printer not in printer_names:
            default_printer = printer_names[0]

        result = {}
        dialog = tk.Toplevel(win)
        set_window_icon(dialog)
        dialog.title(dialog_title or "Print")
        dialog.transient(win)
        dialog.resizable(False, False)
        remember_window_geometry(dialog, "print_dialog", default_geometry="620x150", minsize=(560, 150))
        dialog.grab_set()

        printer_var = tk.StringVar(value=default_printer)
        copies_var = tk.IntVar(value=max(1, int(default_copies or 1)))

        ttk.Label(dialog, text="Printer:").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        printer_combo = ttk.Combobox(dialog, textvariable=printer_var, values=printer_names, state="readonly", width=50)
        printer_combo.grid(row=0, column=1, sticky="ew", padx=12, pady=(12, 4))
        printer_combo.focus_set()

        ttk.Label(dialog, text="Copies:").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        copies_spin = ttk.Spinbox(dialog, from_=1, to=999, textvariable=copies_var, width=8)
        copies_spin.grid(row=1, column=1, sticky="w", padx=12, pady=4)
        copies_spin.bind('<FocusIn>', lambda e: e.widget.select_range(0, 'end'))

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(8, 12), padx=12, sticky="e")

        def _on_print():
            result['printer'] = printer_var.get()
            try:
                result['copies'] = max(1, int(copies_var.get()))
            except Exception:
                result['copies'] = 1
            dialog.destroy()

        def _on_cancel():
            dialog.destroy()

        ttk.Button(button_frame, text="Print", command=_on_print, width=10).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="Cancel", command=_on_cancel, width=10).pack(side="left")
        dialog.protocol("WM_DELETE_WINDOW", _on_cancel)
        dialog.columnconfigure(1, weight=1)
        win.wait_window(dialog)
        if 'printer' not in result:
            return None
        return result['printer'], result['copies']

    def _show_starter_printer_dialog():
        return _show_print_dialog("Print", default_copies=1)

    def _direct_print_image(img_path, printer_name, copies, orientation="Landscape", margins_inches=None, align_top=False, position_adjust_inches=None):
        return direct_print_image_file(
            img_path,
            printer_name=printer_name,
            copies=copies,
            orientation=orientation,
            margins_inches=margins_inches,
            align_top=align_top,
            position_adjust_inches=position_adjust_inches,
        )

    def print_starter_sheet():
        if template_mode:
            return
        format_name = starter_format_var.get().strip() or "Standard"
        try:
            selection = _show_print_dialog("Print", default_copies=1) if os.name == 'nt' else None
            if not selection:
                return
            printer_name, copies = selection
            data = collect_layout_data(ctx)
            data = data if isinstance(data, dict) else {}
            data["starter_format"] = format_name
            _print_starter_sheet_data_to_default_printer(data, copies=copies, printer_name=printer_name)
        except Exception as e:
            messagebox.showerror("Starter Sheet", str(e))

    def _measure_text(draw, text, font):
        text = text or ""
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            return right - left, bottom - top
        except Exception:
            return draw.textsize(text, font=font)

    def _measure_text_bounds(draw, text, font):
        text = text or ""
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            return left, top, right, bottom
        except Exception:
            width, height = draw.textsize(text, font=font)
            return 0, 0, width, height

    def _draw_centered_text(draw, box, text, font, fill="black"):
        x0, y0, x1, y1 = box
        left, top, right, bottom = _measure_text_bounds(draw, text, font)
        tw = right - left
        th = bottom - top
        tx = x0 + max(0, ((x1 - x0) - tw) / 2) - left
        ty = y0 + max(0, ((y1 - y0) - th) / 2) - top
        draw.text((tx, ty), text or "", fill=fill, font=font)

    def _draw_centered_text_heavy(draw, box, text, font, fill="black", offset=1):
        x0, y0, x1, y1 = box
        left, top, right, bottom = _measure_text_bounds(draw, text, font)
        tw = right - left
        th = bottom - top
        tx = x0 + max(0, ((x1 - x0) - tw) / 2) - left
        ty = y0 + max(0, ((y1 - y0) - th) / 2) - top
        for dx, dy in ((0, 0), (offset, 0), (0, offset), (offset, offset)):
            draw.text((tx + dx, ty + dy), text or "", fill=fill, font=font)

    def _wrap_text_to_width(draw, text, font, max_width):
        words = str(text or "").split()
        if not words:
            return [""]
        lines = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if _measure_text(draw, candidate, font)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _visible_print_labels():
        unit_map = {u["label"]: u for u in units}
        left_order = [lab for lab in left_labels if lab in unit_map]
        right_order = []
        special_group = {"E2", "D2", "C2"}
        special_used = False
        if ctx.get("press_name") == "Press 1":
            for lab in special_group:
                unit = unit_map.get(lab)
                if unit is not None and unit_min_page_number(unit) is not None:
                    special_used = True
                    break
        for lab in right_labels:
            unit = unit_map.get(lab)
            if unit is None:
                continue
            if ctx.get("press_name") == "Press 1" and lab in special_group and not special_used:
                continue
            right_order.append(lab)
        return left_order, right_order, unit_map

    def _make_layout_print_image():
        data = collect_layout_data(ctx)
        return render_layout_print_image_from_data(
            data,
            config,
            title_base=title_base,
            template_mode=template_mode,
        )

    def _make_layout_preview_image(scale=0.75):
        img = _make_layout_print_image()
        if img is None:
            return None
        try:
            scale = float(scale)
        except Exception:
            scale = 0.75
        scale = max(0.1, min(1.0, scale))
        preview_img = img.crop((0, 0, img.width, max(1, int(img.height * 0.5))))
        if scale != 1.0:
            width, height = preview_img.size
            preview_img = preview_img.resize(
                (max(1, int(width * scale)), max(1, int(height * scale))),
                Image.LANCZOS,
            )
        return preview_img

    # Save buttons
    def print_layout(win, ctx):
        try:
            from PIL import Image
        except Exception:
            messagebox.showerror("Print Failed", "Pillow is required for printing. Please install pillow (pip install pillow).")
            return
        try:
            img = _make_layout_print_image()
            import tempfile, os
            fd, path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            img.save(path, format="PNG", dpi=(300, 300))
            direct_print_error = {"message": None}
            def _show_printer_dialog():
                try:
                    return _show_print_dialog("Print", default_copies=5)
                except Exception as e:
                    direct_print_error['message'] = str(e)
                    return None
            printed = False
            if os.name == 'nt':
                try:
                    printer_selection = _show_printer_dialog()
                    if printer_selection:
                        printer_name, copies = printer_selection
                        printed = _direct_print_image(path, printer_name, copies, orientation="Landscape", align_top=False)
                except Exception as e:
                    direct_print_error['message'] = str(e)
                    printed = False
            if not printed:
                if os.name == 'nt' and direct_print_error['message']:
                    messagebox.showwarning("Print Failed", f"Direct print failed:\n{direct_print_error['message']}\n\nOpening image preview instead.")
                try:
                    os.startfile(path)
                except Exception:
                    messagebox.showinfo("Print", f"Saved preview to:\n{path}\nPlease open this file and print to your printer in landscape mode.")
        except Exception as e:
            messagebox.showerror("Print Failed", str(e))

    if not template_mode:
        all_color_btn = ttk.Button(btn_frame, text="All Color", command=lambda: select_all_color_pages(), width=10, takefocus=False)
        all_color_btn.pack(side="left", padx=(0, 8))
        all_bw_btn = ttk.Button(btn_frame, text="All b/w", command=lambda: clear_all_color_pages(), width=10, takefocus=False)
        all_bw_btn.pack(side="left", padx=(0, 12))
        ttk.Label(btn_frame, text="Starter:").pack(side="left", padx=(0, 6))
        starter_combo = ttk.Combobox(btn_frame, textvariable=starter_format_var, values=["Standard", "NYT", "USAT"], state="readonly", width=10)
        starter_combo.pack(side="left", padx=(0, 8))
        starter_combo.bind("<<ComboboxSelected>>", lambda e: _mark_dirty_var())
        ttk.Button(btn_frame, text="Print Starter", command=print_starter_sheet, width=12, takefocus=False).pack(side="left", padx=(0, 12))
    ttk.Button(btn_frame, text="Print", command=lambda: print_layout(win, ctx), width=10, takefocus=False).pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="Save", command=do_save_with_starter, width=10, takefocus=False).pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="Save As", command=do_save_as_with_starter, width=10, takefocus=False).pack(side="left")
    if not template_mode and not regular_mode:
        ttk.Button(btn_frame, text="Save as Regular", command=do_save_as_regular_with_starter, width=14, takefocus=False).pack(side="left", padx=(8, 0))
    btn_frame.pack(side="left")

    # Expose print functions for external callers (launcher use)
    try:
        win.print_layout = lambda: print_layout(win, ctx)
        win.print_starter = lambda: print_starter_sheet()
        win.build_print_image = _make_layout_print_image
        win.build_preview_image = _make_layout_preview_image
    except Exception:
        pass

    # Color / Plate counters (placed beside the bottom controls)
    stats_frame = ttk.Frame(controls_center_frame)
    stats_frame.pack(side="left", padx=(18, 0))
    ttk.Label(stats_frame, text="Color Pages:", font=(None, 10)).pack(side="left")
    ttk.Label(stats_frame, textvariable=color_pages_var, font=(None, 10, "bold")).pack(side="left", padx=(4, 12))
    ttk.Label(stats_frame, text="Plates:", font=(None, 10)).pack(side="left")
    ttk.Label(stats_frame, textvariable=plates_var, font=(None, 10, "bold")).pack(side="left", padx=(4, 0))

    # Live imposition updater
    ctx["_imposition_updating"] = False

    def update_imposition(*_):
        if ctx["_imposition_updating"]:
            return
        ctx["_imposition_updating"] = True
        try:
            try:
                _refresh_section_page_counts()
            except Exception:
                pass
            imposition_var.set(build_imposition_text(ctx))
        finally:
            ctx["_imposition_updating"] = False

    # ---- Issue Date normalize on FocusOut (Tab/Click away) ----
    def on_issue_date_focus_out(event=None):
        if template_mode:
            return
        raw = issue_entry.get().strip()
        dt = parse_issue_date_flexible(raw)
        if dt:
            normalized = dt.strftime("%m/%d/%Y")
            if normalized != raw:
                issue_entry.delete(0, "end")
                issue_entry.insert(0, normalized)
        update_imposition()

    def _set_issue_date_value(value, mark_dirty=True):
        if template_mode:
            return
        normalized = (value or "").strip()
        if normalized:
            try:
                parsed = parse_issue_date_flexible(normalized)
            except Exception:
                parsed = None
            if parsed is not None:
                normalized = parsed.strftime("%m/%d/%Y")
        previous = issue_entry.get().strip()
        if normalized == previous:
            update_imposition()
            return
        try:
            issue_entry.state(["!disabled"])
        except Exception:
            pass
        issue_entry.delete(0, "end")
        issue_entry.insert(0, normalized)
        if mark_dirty:
            try:
                ctx["dirty"] = True
            except Exception:
                pass
        update_imposition()

    def _open_issue_date_picker(event=None):
        if template_mode:
            return
        selected_value = ask_issue_date_with_calendar(
            win,
            initial_text=issue_entry.get().strip(),
            anchor_widget=issue_entry,
            title="Select Issue Date",
        )
        if selected_value:
            _set_issue_date_value(selected_value, mark_dirty=True)
        try:
            issue_entry.focus_set()
            issue_entry.selection_range(0, "end")
            issue_entry.icursor("end")
        except Exception:
            pass
        return "break"

    issue_entry.bind("<FocusOut>", on_issue_date_focus_out)
    issue_entry.bind("<Return>", lambda e: (on_issue_date_focus_out(), "break"))
    issue_entry.bind("<KeyRelease>", lambda e: update_imposition())
    issue_entry.bind("<Button-1>", _open_issue_date_picker)

    def _on_publication_key_release(event=None):
        try:
            current = product_entry.get()
        except Exception:
            return
        uppered = str(current or "").upper()
        if uppered != current:
            try:
                cursor_index = product_entry.index("insert")
                sel_start = product_entry.index("sel.first")
                sel_end = product_entry.index("sel.last")
            except Exception:
                cursor_index, sel_start, sel_end = None, None, None
            try:
                product_entry.delete(0, "end")
                product_entry.insert(0, uppered)
                if sel_start is not None and sel_end is not None:
                    product_entry.selection_range(min(sel_start, len(uppered)), min(sel_end, len(uppered)))
                elif cursor_index is not None:
                    product_entry.icursor(min(cursor_index, len(uppered)))
            except Exception:
                pass
        update_imposition()

    def _on_publication_focus_out(event=None):
        _normalize_publication_entry()
        update_imposition()

    product_entry.bind("<KeyRelease>", _on_publication_key_release)
    product_entry.bind("<FocusOut>", _on_publication_focus_out)

    selector_busy = {"press": False, "format": False}

    def _collect_live_layout_state():
        state = collect_layout_data(ctx)
        state["starter_format"] = (starter_format_var.get() or "Standard").strip() or "Standard"
        state["_file_path"] = ctx.get("file_path")
        state["_layout_name"] = ctx.get("layout_name")
        return state

    def _reopen_layout(new_press, new_format, data):
        next_cfg = dict(CONFIG_MAP[(new_press, new_format)])
        next_cfg["section_count"] = max(1, min(4, int(data.get("section_count", 1) or 1)))
        next_cfg["section_pages"] = list(data.get("section_pages") or [0] * next_cfg["section_count"])
        next_cfg["section_names"] = list(data.get("section_names") or [])
        next_cfg["template_mode"] = template_mode
        next_cfg["default_dir"] = ctx.get("default_dir", TEMPLATE_DIR if template_mode else LAYOUTS_DIR)
        next_cfg["prompt_save_template"] = bool(ctx.get("prompt_save_template", not template_mode))
        for child in list(win.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        build_press_layout(win, title=f"{new_press} - {new_format}", config=next_cfg, initial_data=data)

    def _on_press_selector_changed(*_):
        if selector_busy["press"]:
            return
        old_press = ctx.get("press_name") or config.get("press_name") or "Press 1"
        new_press = (press_selector_var.get() or "").strip() or old_press
        if new_press == old_press:
            return
        data = _collect_live_layout_state()
        if old_press == "Press 1" and new_press == "Press 2":
            blocked = []
            for label in ["E2", "D2", "C2"]:
                unit = next((u for u in data.get("units", []) if str(u.get("label") or "") == label), None)
                if unit and _unit_has_any_pages(unit):
                    blocked.append(label)
            if blocked:
                msg = "Pages assigned to {} units can't be converted to Press 2 and would be removed if converting the press.\n\nClick OK to continue or Cancel to keep the current press.".format(', '.join(blocked))
                if not messagebox.askokcancel("Convert Press", msg, parent=win):
                    selector_busy["press"] = True
                    press_selector_var.set(old_press)
                    selector_busy["press"] = False
                    return
        converted = _converted_press_data(data, old_press, new_press)
        converted["format"] = data.get("format") or config.get("format_name") or "Broadsheet"
        _reopen_layout(new_press, converted["format"], converted)

    def _on_format_selector_changed(*_):
        if selector_busy["format"]:
            return
        old_format = ctx.get("format_name") or config.get("format_name") or "Broadsheet"
        new_format = (format_selector_var.get() or "").strip() or old_format
        if new_format == old_format:
            return
        data = _collect_live_layout_state()
        if any(_unit_has_any_pages(unit) for unit in data.get("units", [])):
            msg = "Changing the format will reset all units back to no section and pages.\n\nClick OK to continue or Cancel to keep the current format."
            if not messagebox.askokcancel("Change Format", msg, parent=win):
                selector_busy["format"] = True
                format_selector_var.set(old_format)
                selector_busy["format"] = False
                return
        data["press"] = ctx.get("press_name") or config.get("press_name") or "Press 1"
        converted = _format_reset_data(data, new_format)
        _reopen_layout(converted["press"], new_format, converted)

    press_selector_var.trace_add("write", _on_press_selector_changed)
    format_selector_var.trace_add("write", _on_format_selector_changed)

    # ---- Section count handler w/ recursion guard ----
    _busy = {"busy": False}
    def _on_section_count_changed(event=None):
        if _busy["busy"]:
            return
        _busy["busy"] = True
        try:
            try:
                count = int(section_count_var.get())
            except Exception:
                count = 1
            count = max(1, min(4, count))
            section_count_var.set(str(count))
            _update_section_page_states(count)
            update_imposition()
            refresh_color_overlays()
        finally:
            _busy["busy"] = False

    section_count_var.trace_add("write", lambda *_: _on_section_count_changed())


    # ---- Per-cell color selection logic ----
    def toggle_color_cell(unit_dict, r, c):
        if template_mode:
            return
        if not color_select_var.get():
            return
        if not unit_dict.get("color_capable"):
            return

        key = (unit_dict["label"], r, c)
        overlay = unit_dict["overlays"][r][c]

        if key in ctx["color_cells"]:
            ctx["color_cells"].remove(key)
            overlay_set_circle(overlay, False)
        else:
            ctx["color_cells"].add(key)
            overlay_set_circle(overlay, True)
        # update counts after toggling
        try:
            update_color_and_plate_counts()
        except Exception:
            pass

    def refresh_cell_overlay(unit_dict, r, c):
        overlay = unit_dict["overlays"][r][c]
        entry = unit_dict["entries"][r][c]
        key = (unit_dict["label"], r, c)
        circled = key in ctx["color_cells"]
        selecting = (not template_mode) and color_select_var.get() and unit_dict.get("color_capable", False)
        is_focused = entry == entry.focus_get()

        if is_focused and not color_select_var.get():
            overlay_hide(overlay)
            return

        if circled or selecting:
            overlay_show(overlay)
            overlay_render_cell(overlay, entry.get(), circled)
        else:
            overlay_hide(overlay)
            overlay.delete("all")

    def _iter_color_capable_page_cells(include_blank=False):
        for u in ctx.get("units", []):
            if not u.get("color_capable", False):
                continue
            entries = u.get("entries", [])
            for r, row in enumerate(entries):
                for c, cell in enumerate(row):
                    try:
                        value = (cell.get() or "").strip()
                    except Exception:
                        value = ""
                    if include_blank or value != "":
                        yield u, r, c, value

    def select_all_color_pages():
        if template_mode:
            return
        ctx["color_cells"] = {
            (u["label"], r, c)
            for u, r, c, _value in _iter_color_capable_page_cells(include_blank=False)
        }
        refresh_color_overlays()
        try:
            ctx["dirty"] = True
        except Exception:
            pass

    def clear_all_color_pages():
        if template_mode:
            return
        if ctx.get("color_cells"):
            ctx["color_cells"] = set()
            refresh_color_overlays()
            try:
                ctx["dirty"] = True
            except Exception:
                pass

    def refresh_color_overlays():
        for u in ctx["units"]:
            overlays = u.get("overlays", [])
            for r in range(len(overlays)):
                for c in range(len(overlays[r])):
                    refresh_cell_overlay(u, r, c)
        # update counts after overlays refreshed
        try:
            update_color_and_plate_counts()
        except Exception:
            pass

    def update_color_and_plate_counts():
        # Color pages = number of marked color cells
        try:
            cp = len(ctx.get("color_cells", set()))
            ctx.get("color_pages_var", color_pages_var).set(str(cp))
        except Exception:
            pass

        # Plates: for each unit, for each side (left/right split at vertical center),
        # if any cell on that side is color -> 4 plates, else 1 plate.
        plates = 0
        for u in ctx.get("units", []):
            entries = u.get("entries", [])
            if not entries:
                continue
            rows = len(entries)
            cols_unit = len(entries[0]) if rows > 0 else 0
            mid_unit = cols_unit // 2

            for side in (0, 1):
                if side == 0:
                    cols_range = range(0, mid_unit)
                else:
                    cols_range = range(mid_unit, cols_unit)

                has_color = False
                has_pages = False
                for r in range(rows):
                    for c in cols_range:
                        if (u["label"], r, c) in ctx.get("color_cells", set()):
                            has_color = True
                            break
                        try:
                            val = u["entries"][r][c].get().strip()
                            if val != "":
                                has_pages = True
                        except Exception:
                            pass
                    if has_color:
                        break

                if has_color:
                    plates += 4
                elif has_pages:
                    plates += 1
                else:
                    plates += 0

        try:
            ctx.get("plates_var", plates_var).set(str(plates))
        except Exception:
            pass

    # bind overlay clicks and entry redraws
    for u in ctx["units"]:
        overlays = u["overlays"]
        entries = u["entries"]
        section_entry = u.get("section_entry")
        if section_entry is not None:
            section_entry.bind("<KeyRelease>", lambda e, _u=u: (_record_unit_section_assignment(_u), _refresh_section_page_counts(), update_imposition()))
            section_entry.bind("<<ComboboxSelected>>", lambda e, _u=u: (_record_unit_section_assignment(_u), _refresh_section_page_counts(), update_imposition()))
            section_entry.bind("<FocusOut>", lambda e, _u=u: (_record_unit_section_assignment(_u), _refresh_section_page_counts(), update_imposition()))
        for r in range(len(overlays)):
            for c in range(len(overlays[r])):
                ov = overlays[r][c]
                entry = entries[r][c]

                def on_overlay_click(event, _u=u, _r=r, _c=c):
                    if not color_select_var.get():
                        target = _u["entries"][_r][_c]
                        target.focus_set()
                        try:
                            target.selection_range(0, "end")
                        except Exception:
                            pass
                        return "break"
                    toggle_color_cell(_u, _r, _c)

                ov.bind("<Button-1>", on_overlay_click)
                entry.bind("<FocusIn>", lambda e, _ov=ov: overlay_hide(_ov) if not color_select_var.get() else None)
                entry.bind("<FocusOut>", lambda e, _u=u, _r=r, _c=c: (refresh_cell_overlay(_u, _r, _c), _refresh_section_page_counts(), update_imposition()))
                entry.bind("<KeyRelease>", lambda e, _u=u, _r=r, _c=c: (refresh_cell_overlay(_u, _r, _c), _refresh_section_page_counts(), update_imposition()))

    if color_toggle is not None:
        color_toggle.configure(command=refresh_color_overlays)

    # ---- Load file (open vs copy) ----
    if initial_data is not None:
        data = json.loads(json.dumps(initial_data))
        populate_layout_from_data(ctx, data)
        _capture_unit_section_assignments()
        _refresh_unit_section_choices()
        _refresh_section_page_counts()
        if not template_mode:
            starter_format_var.set(data.get("starter_format") or "Standard")
        ctx["file_path"] = data.get("_file_path")
        ctx["layout_name"] = data.get("_layout_name")
        if ctx.get("file_path"):
            win.title(f"{title_base}  —  {os.path.basename(ctx['file_path'])}")
        else:
            win.title(title_base)
    elif load_path:
        data = safe_read_json(load_path)
        if data:
            populate_layout_from_data(ctx, data)
            if load_as_copy and not template_mode:
                try:
                    load_path_abs = os.path.abspath(load_path)
                    template_dir_abs = os.path.abspath(TEMPLATE_DIR)
                    is_template_copy = os.path.commonpath([load_path_abs, template_dir_abs]) == template_dir_abs
                except Exception:
                    is_template_copy = False
                if is_template_copy:
                    try:
                        section_count_for_names = max(1, min(4, int(section_count_var.get())))
                    except Exception:
                        section_count_for_names = 1
                    for i in range(4):
                        if i < section_count_for_names:
                            section_name_vars[i].set(chr(ord("A") + i))
                        else:
                            section_name_vars[i].set("")
            _capture_unit_section_assignments()
            _refresh_unit_section_choices()
            _refresh_section_page_counts()
            if not template_mode:
                starter_format_var.set(data.get("starter_format") or "Standard")

            if load_as_copy:
                if not template_mode:
                    if config.get("copy_blank_issue_product", False):
                        try:
                            issue_entry.state(["!disabled"])
                        except Exception:
                            pass
                        try:
                            issue_entry.delete(0, "end")
                        except Exception:
                            pass
                        try:
                            product_entry.state(["!disabled"])
                        except Exception:
                            pass
                        try:
                            product_entry.delete(0, "end")
                        except Exception:
                            pass
                    elif config.get("copy_blank_issue_only", False):
                        try:
                            issue_entry.state(["!disabled"])
                        except Exception:
                            pass
                        try:
                            issue_entry.delete(0, "end")
                        except Exception:
                            pass
                    elif config.get("copy_issue_date_tomorrow", False):
                        try:
                            issue_entry.state(["!disabled"])
                        except Exception:
                            pass
                        try:
                            issue_entry.delete(0, "end")
                            issue_entry.insert(0, tomorrow_issue_date_mmddyyyy())
                        except Exception:
                            pass
                ctx["file_path"] = None
                ctx["layout_name"] = None
                source_name = data.get("name") or os.path.splitext(os.path.basename(load_path))[0]
                win.title(f"{title_base}  —  Clone of {source_name}")
            else:
                ctx["file_path"] = load_path
                ctx["layout_name"] = data.get("name") or os.path.splitext(os.path.basename(load_path))[0]
                win.title(f"{title_base}  —  {os.path.basename(load_path)}")

    _capture_unit_section_assignments()
    # initial refreshes
    _normalize_publication_entry()
    update_imposition()
    refresh_color_overlays()

    # --- change tracking (dirty flag) ---------------------------------
    _dirty_state = {
        "baseline": None,
        "pause_depth": 0,
    }

    def _build_dirty_snapshot():
        data = collect_layout_data(ctx)
        return {
            "press": data.get("press", ""),
            "format": data.get("format", ""),
            "issue_date": data.get("issue_date", ""),
            "product": data.get("product", ""),
            "section_count": data.get("section_count", 1),
            "section_pages": list(data.get("section_pages", []) or []),
            "section_names": list(data.get("section_names", []) or []),
            "units": list(data.get("units", []) or []),
            "color_cells": list(data.get("color_cells", []) or []),
            "starter_format": (starter_format_var.get() or "Standard").strip() or "Standard",
        }

    def _sync_dirty_state():
        try:
            if _dirty_state["pause_depth"] > 0:
                return
            baseline = _dirty_state.get("baseline")
            if baseline is None:
                ctx["dirty"] = False
                return
            ctx["dirty"] = (_build_dirty_snapshot() != baseline)
        except Exception:
            pass

    def _reset_dirty_tracking(mark_dirty=False):
        try:
            _dirty_state["baseline"] = _build_dirty_snapshot()
            ctx["dirty"] = bool(mark_dirty)
            if mark_dirty:
                try:
                    baseline = json.loads(json.dumps(_dirty_state["baseline"]))
                    baseline["_seed"] = "baseline"
                    _dirty_state["baseline"] = baseline
                except Exception:
                    pass
        except Exception:
            try:
                ctx["dirty"] = bool(mark_dirty)
            except Exception:
                pass

    def _mark_dirty_event(event=None):
        _sync_dirty_state()

    def _mark_dirty_var(*_):
        _sync_dirty_state()


    _reset_dirty_tracking(bool(initial_data is not None))

    # ---- tab order + arrows ----
    focus_list = build_focus_order(
        issue_entry=issue_entry,
        product_entry=product_entry,
        units=units,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        press_name=config.get("press_name", ""),
        extra_widgets=section_count_radios + section_name_entries
    )
    set_custom_tab_order(focus_list)
    enable_arrow_navigation(focus_list, units, config.get("press_name", ""))

    def _focus_issue_entry_for_quick_replace():
        try:
            issue_entry.focus_set()
        except Exception:
            return
        try:
            issue_entry.selection_range(0, "end")
        except Exception:
            pass
        try:
            issue_entry.icursor("end")
        except Exception:
            pass

    if load_as_copy and (not template_mode) and config.get("copy_issue_date_tomorrow", False):
        win.after(50, _focus_issue_entry_for_quick_replace)
    else:
        win.after(50, issue_entry.focus_set)
    if not has_saved_window_state:
        apply_window_sizing(win, config)
    remember_window_geometry(
        win,
        window_state_key,
    )
    # Bind change events to mark the layout as dirty
    try:
        issue_entry.bind("<KeyRelease>", _mark_dirty_event)
        product_entry.bind("<KeyRelease>", _mark_dirty_event, add="+")
        for sv in section_name_vars:
            try:
                sv.trace_add("write", _mark_dirty_var)
            except Exception:
                pass
        try:
            section_count_var.trace_add("write", _mark_dirty_var)
        except Exception:
            pass
        if color_toggle is not None:
            try:
                color_select_var.trace_add("write", _mark_dirty_var)
            except Exception:
                pass
        for u in units:
            try:
                if u.get("section_entry") is not None:
                    u["section_entry"].bind("<KeyRelease>", _mark_dirty_event)
            except Exception:
                pass
            try:
                for r, row in enumerate(u.get("entries", [])):
                    for c, cell in enumerate(row):
                        try:
                            cell.bind("<KeyRelease>", _mark_dirty_event)
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass

    # Prompt to save on close if dirty
    def _on_close_request():
        try:
            _sync_dirty_state()
        except Exception:
            pass
        try:
            dirty = bool(ctx.get("dirty"))
        except Exception:
            dirty = False
        if not dirty:
            try:
                win.destroy()
            except Exception:
                pass
            return
        # Ask user: Yes=Save, No=Discard, Cancel=Keep
        res = messagebox.askyesnocancel(title="Save Changes?", message="You have unsaved changes. Save before closing?")
        if res is None:
            return
        if res is True:
            ok = do_save_with_starter()
            if ok:
                try:
                    win.destroy()
                except Exception:
                    pass
            return
        # res is False -> discard and close
        try:
            win.destroy()
        except Exception:
            pass

    try:
        win.protocol("WM_DELETE_WINDOW", _on_close_request)
    except Exception:
        pass
    return units

# =============================================================================
# Launcher, macros, changelog, and single-instance control
# Launcher UI, monthly macros, changelog/update prompts, database maintenance dialogs, and one-instance activation behavior.
# =============================================================================

WINDOW_SIZE_STATE_FILE = os.path.join(os.path.expanduser("~"), ".press_layout_launcher_sizes.json")


def _parse_geometry_parts(geometry_text):
    try:
        m = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", str(geometry_text or "").strip())
        if not m:
            return None
        return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    except Exception:
        return None


def _load_window_size_state():
    try:
        if not os.path.exists(WINDOW_SIZE_STATE_FILE):
            return {}
        with open(WINDOW_SIZE_STATE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_window_size_state(data):
    try:
        with open(WINDOW_SIZE_STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


def _apply_saved_window_size(win, state_key):
    try:
        win.update_idletasks()
        parts = _parse_geometry_parts(win.geometry())
        if not parts:
            return
        _cur_w, _cur_h, cur_x, cur_y = parts
        saved = _load_window_size_state().get(state_key)
        if not (isinstance(saved, dict) and saved.get("width") and saved.get("height")):
            return
        width = max(100, int(saved.get("width")))
        height = max(100, int(saved.get("height")))
        win.geometry(f"{width}x{height}{cur_x:+d}{cur_y:+d}")
    except Exception:
        pass


def _bind_window_size_memory(win, state_key):
    _apply_saved_window_size(win, state_key)
    pending = {"id": None}

    def _persist_size():
        pending["id"] = None
        try:
            width = int(win.winfo_width())
            height = int(win.winfo_height())
        except Exception:
            return
        if width <= 1 or height <= 1:
            return
        data = _load_window_size_state()
        data[state_key] = {"width": width, "height": height}
        _save_window_size_state(data)

    def _schedule(event=None):
        try:
            if pending["id"] is not None:
                win.after_cancel(pending["id"])
        except Exception:
            pass
        try:
            pending["id"] = win.after(150, _persist_size)
        except Exception:
            pass

    try:
        win.bind("<Configure>", _schedule, add="+")
    except Exception:
        pass


def _fit_image_to_box(image, max_width, max_height):
    try:
        from PIL import Image
    except Exception as e:
        raise RuntimeError(f"Pillow is required for previews: {e}")
    if image is None:
        return None
    try:
        max_width = max(1, int(max_width))
        max_height = max(1, int(max_height))
    except Exception:
        return image
    width, height = image.size
    if width <= 0 or height <= 0:
        return image
    scale = min(max_width / float(width), max_height / float(height))
    if scale <= 0:
        return image
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    if new_size == image.size:
        return image
    return image.resize(new_size, Image.LANCZOS)


def _render_preview_panel_image(preview_label, preview_state):
    image = preview_state.get("pil_image")
    if image is None:
        return
    try:
        available_width = max(100, int(preview_label.winfo_width()) - 12)
    except Exception:
        available_width = image.size[0]
    try:
        available_height = max(100, int(preview_label.winfo_height()) - 12)
    except Exception:
        available_height = image.size[1]
    scaled = _fit_image_to_box(image, available_width, available_height)
    try:
        from PIL import ImageTk
    except Exception as e:
        raise RuntimeError(f"Pillow is required for previews: {e}")
    photo = ImageTk.PhotoImage(scaled)
    preview_label.configure(image=photo, text="")
    preview_label.image = photo
    preview_state["photo"] = photo


def _apply_saved_preview_pane_height(win, state_key, paned, preview_box, default_height=240, min_height=160, bind_state=None):
    bind_state = bind_state if isinstance(bind_state, dict) else {}

    def _apply(attempt=0):
        try:
            bind_state["applying"] = True
            win.update_idletasks()
            total_h = max(1, int(paned.winfo_height()))
            data = _load_window_size_state().get(state_key, {})
            target = int(data.get("preview_height", default_height))
            target = max(min_height, min(target, max(min_height, total_h - 120)))
            sash_y = max(80, total_h - target)
            paned.sash_place(0, 0, sash_y)
        except Exception:
            pass
        finally:
            try:
                bind_state["last_requested_height"] = target
            except Exception:
                pass
            try:
                bind_state["applying"] = False
            except Exception:
                pass
        try:
            if attempt < 5:
                # Re-apply a few times while the window settles so the saved split wins
                # over early geometry/configure events during startup.
                win.after(120, lambda: _apply(attempt + 1))
            else:
                bind_state["armed"] = True
        except Exception:
            bind_state["armed"] = True

    try:
        bind_state["armed"] = False
        win.after(80, lambda: _apply(0))
    except Exception:
        _apply(5)


def _bind_preview_pane_memory(win, state_key, paned, preview_box, default_height=240):
    state = {"pending": None, "armed": False, "applying": False, "last_saved_height": None, "last_requested_height": None}
    _apply_saved_preview_pane_height(win, state_key, paned, preview_box, default_height=default_height, bind_state=state)

    def _persist_preview_height(force=False):
        state["pending"] = None
        try:
            if (state.get("applying") or not state.get("armed")) and not force:
                return
            win.update_idletasks()
            height = int(preview_box.winfo_height())
            total_h = int(paned.winfo_height())
        except Exception:
            return
        if height <= 1 or total_h <= 1:
            return
        max_allowed = max(default_height, total_h - 120)
        min_allowed = min(160, max_allowed)
        if height < min_allowed or height > max_allowed:
            return
        if (not force) and state.get("last_saved_height") == height:
            return
        data = _load_window_size_state()
        entry = data.get(state_key)
        if not isinstance(entry, dict):
            entry = {}
            data[state_key] = entry
        entry["preview_height"] = height
        _save_window_size_state(data)
        state["last_saved_height"] = height

    def _schedule(event=None, delay=220):
        try:
            if state.get("applying") or not state.get("armed"):
                return
            if state["pending"] is not None:
                win.after_cancel(state["pending"])
        except Exception:
            pass
        try:
            state["pending"] = win.after(delay, _persist_preview_height)
        except Exception:
            pass

    def _persist_on_close(event=None):
        try:
            _persist_preview_height(force=True)
        except Exception:
            pass

    try:
        callbacks = getattr(win, "_preview_pane_persist_callbacks", None)
        if not isinstance(callbacks, list):
            callbacks = []
            setattr(win, "_preview_pane_persist_callbacks", callbacks)
        callbacks.append(_persist_on_close)
    except Exception:
        pass

    try:
        preview_box.bind("<Configure>", lambda event: _schedule(event, delay=300), add="+")
        paned.bind("<ButtonRelease-1>", lambda event: _schedule(event, delay=120), add="+")
        win.bind("<Unmap>", _persist_on_close, add="+")
        win.bind("<Destroy>", _persist_on_close, add="+")
    except Exception:
        pass
    return _persist_on_close


def _persist_bound_preview_panes(win):
    callbacks = getattr(win, "_preview_pane_persist_callbacks", [])
    for callback in list(callbacks):
        try:
            callback()
        except Exception:
            pass


_TEMPLATE_CACHE = {"signature": None, "rows": []}
_REGULAR_CACHE = {"signature": None, "rows": []}
_LAYOUT_CACHE = {"signature": None, "rows": []}


def _json_dir_entries(folder):
    ensure_dir(folder)
    entries = []
    try:
        with os.scandir(folder) as iterator:
            for entry in iterator:
                try:
                    if not entry.is_file():
                        continue
                except Exception:
                    continue
                if not str(entry.name or "").lower().endswith(".json"):
                    continue
                try:
                    stat = entry.stat()
                except Exception:
                    stat = None
                if stat is not None:
                    mtime_ns = int(getattr(stat, "st_mtime_ns", int(float(getattr(stat, "st_mtime", 0.0)) * 1000000000)))
                    ctime_ns = int(getattr(stat, "st_ctime_ns", int(float(getattr(stat, "st_ctime", 0.0)) * 1000000000)))
                    size = int(getattr(stat, "st_size", 0))
                    fs_saved_dt = datetime.fromtimestamp(float(getattr(stat, "st_mtime", 0.0)))
                    fs_saved_disp = fs_saved_dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    mtime_ns = 0
                    ctime_ns = 0
                    size = 0
                    fs_saved_dt = None
                    fs_saved_disp = ""
                entries.append({
                    "name": entry.name,
                    "path": entry.path,
                    "mtime_ns": mtime_ns,
                    "ctime_ns": ctime_ns,
                    "size": size,
                    "fs_saved_dt": fs_saved_dt,
                    "fs_saved_disp": fs_saved_disp,
                })
    except Exception:
        return []
    entries.sort(key=lambda item: str(item.get("name") or "").lower())
    return entries


def _dir_signature(entries):
    return tuple(
        (
            str(item.get("name") or "").lower(),
            int(item.get("mtime_ns", 0) or 0),
            int(item.get("ctime_ns", 0) or 0),
            int(item.get("size", 0) or 0),
        )
        for item in entries
    )


def _clone_rows(rows):
    return [dict(row) for row in (rows or [])]



def _rebuild_template_cache(entries=None):
    if entries is None:
        entries = _json_dir_entries(TEMPLATE_DIR)
    rows = []
    for item in entries:
        path = item.get("path") or ""
        stem = os.path.splitext(os.path.basename(path))[0]
        db_row = item.get("db_row") if isinstance(item, dict) else None
        data = (db_row or {}).get("data") if isinstance(db_row, dict) else None
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = None
        if not isinstance(data, dict):
            data = safe_read_json(path)
        valid = isinstance(data, dict)
        name = stem
        press = ""
        fmt = ""
        section_count = None
        section_pages = []
        if valid:
            name = data.get("name") or stem
            press = data.get("press") or ""
            fmt = data.get("format") or ""
            try:
                section_count = max(1, min(4, int(data.get("section_count", 1))))
            except Exception:
                section_count = 1
            for page in (data.get("section_pages", []) or []):
                try:
                    section_pages.append(int(page))
                except Exception:
                    section_pages.append(page)
        rows.append({
            "path": path,
            "name": name,
            "press": press,
            "format": fmt,
            "section_count": section_count,
            "section_pages": section_pages,
            "saved_dt": item.get("fs_saved_dt"),
            "saved_disp": item.get("fs_saved_disp") or "",
            "last_changed_by": _last_changed_by_display(data.get("last_changed_by", "")) if valid else "Unknown",
            "valid": valid,
        })
    _TEMPLATE_CACHE["signature"] = _dir_signature(entries)
    _TEMPLATE_CACHE["rows"] = rows
    return _clone_rows(rows)

def get_cached_templates(force=False):
    entries = _json_dir_entries(TEMPLATE_DIR)
    signature = _dir_signature(entries)
    changed = force or signature != _TEMPLATE_CACHE.get("signature")
    rows = _rebuild_template_cache(entries) if changed else _clone_rows(_TEMPLATE_CACHE.get("rows", []))
    return rows, changed


def list_matching_templates(press_name, format_name, section_count=None, section_pages=None):
    """
    Templates live in TEMPLATE_DIR and are matched by cached JSON metadata.
    In the New Layout launcher, we additionally filter by section_count & section_pages.
    """
    rows, _changed = get_cached_templates(force=False)
    results = []
    for row in rows:
        stem = os.path.splitext(os.path.basename(row.get("path") or ""))[0]
        if not row.get("valid", False):
            results.append((row.get("name") or stem, row.get("path")))
            continue
        if row.get("press") != press_name or row.get("format") != format_name:
            continue
        if section_count is not None:
            file_section_count = row.get("section_count")
            file_section_pages = row.get("section_pages", [])
            if file_section_count != section_count:
                continue
            if len(file_section_pages) < section_count:
                continue
            mismatch = False
            for i in range(section_count):
                try:
                    page_value = int(file_section_pages[i])
                except Exception:
                    page_value = file_section_pages[i]
                if page_value != section_pages[i]:
                    mismatch = True
                    break
            if mismatch:
                continue
        results.append((row.get("name") or stem, row.get("path")))
    return results


def _coerce_section_pages_for_display(data):
    try:
        section_count = max(1, min(4, int((data or {}).get("section_count", 1))))
    except Exception:
        section_count = 1
    raw_pages = (data or {}).get("section_pages", []) or []
    pages = []
    for idx in range(min(4, max(section_count, len(raw_pages)))):
        try:
            value = int(raw_pages[idx])
        except Exception:
            value = 0
        if value > 0:
            pages.append(value)
    return pages


def _format_section_pages_for_display(data):
    pages = _coerce_section_pages_for_display(data)
    return " / ".join(str(value) for value in pages)






def _rebuild_regular_cache(entries=None):
    if entries is None:
        entries = _json_dir_entries(REGULAR_DIR)
    rows = []
    for item in entries:
        path = item.get("path") or ""
        db_row = item.get("db_row") if isinstance(item, dict) else None
        data = (db_row or {}).get("data") if isinstance(db_row, dict) else None
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = None
        if not isinstance(data, dict):
            data = safe_read_json(path) or {}
        press = data.get("press", "") or ""
        fmt = data.get("format", "") or ""
        issue = data.get("issue_date", "") or ""
        product = data.get("product", "") or ""
        saved_at = data.get("saved_at", "") or ""
        issue_dt = parse_issue_date_flexible(issue)
        saved_dt = parse_saved_at(saved_at) or item.get("fs_saved_dt")
        try:
            color_pages, plates = _layout_color_and_plate_counts_from_data(data)
        except Exception:
            color_pages, plates = 0, 0
        section_pages_values = _coerce_section_pages_for_display(data)
        rows.append({
            "path": path,
            "name": data.get("name") or os.path.splitext(os.path.basename(path))[0],
            "issue_dt": issue_dt,
            "issue_disp": fmt_issue_for_display(issue),
            "product": product,
            "press": press,
            "format": fmt,
            "pages_disp": _format_section_pages_for_display(data),
            "section_pages_sort": tuple(section_pages_values + [0] * (4 - len(section_pages_values))),
            "saved_dt": saved_dt,
            "saved_disp": fmt_dt_for_display(saved_dt),
            "color_pages": color_pages,
            "plates": plates,
            "last_changed_by": _last_changed_by_display(data.get("last_changed_by", "")),
        })
    _REGULAR_CACHE["signature"] = _dir_signature(entries)
    _REGULAR_CACHE["rows"] = rows
    return _clone_rows(rows)

def get_cached_regular_rows(force=False):
    entries = _json_dir_entries(REGULAR_DIR)
    signature = _dir_signature(entries)
    changed = force or signature != _REGULAR_CACHE.get("signature")
    rows = _rebuild_regular_cache(entries) if changed else _clone_rows(_REGULAR_CACHE.get("rows", []))
    return rows, changed


def _rebuild_layout_cache(entries=None):
    if entries is None:
        entries = _json_dir_entries(LAYOUTS_DIR)
    rows = []
    for item in entries:
        path = item.get("path") or ""
        db_row = item.get("db_row") if isinstance(item, dict) else None
        data = (db_row or {}).get("data") if isinstance(db_row, dict) else None
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = None
        if not isinstance(data, dict):
            data = safe_read_json(path) or {}
        press = data.get("press", "") or ""
        fmt = data.get("format", "") or ""
        issue = data.get("issue_date", "") or ""
        product = data.get("product", "") or ""
        saved_at = data.get("saved_at", "") or ""
        issue_dt = parse_issue_date_flexible(issue)
        saved_dt = parse_saved_at(saved_at) or item.get("fs_saved_dt")
        try:
            color_pages, plates = _layout_color_and_plate_counts_from_data(data)
        except Exception:
            color_pages, plates = 0, 0
        section_pages_values = _coerce_section_pages_for_display(data)
        rows.append({
            "path": path,
            "issue_dt": issue_dt,
            "issue_disp": fmt_issue_for_display(issue),
            "product": product,
            "press": press,
            "format": fmt,
            "pages_disp": _format_section_pages_for_display(data),
            "section_pages_sort": tuple(section_pages_values + [0] * (4 - len(section_pages_values))),
            "saved_dt": saved_dt,
            "saved_disp": fmt_dt_for_display(saved_dt),
            "color_pages": color_pages,
            "plates": plates,
            "last_changed_by": _last_changed_by_display(data.get("last_changed_by", "")),
        })
    _LAYOUT_CACHE["signature"] = _dir_signature(entries)
    _LAYOUT_CACHE["rows"] = rows
    return _clone_rows(rows)

def get_cached_layout_rows(force=False):
    entries = _json_dir_entries(LAYOUTS_DIR)
    signature = _dir_signature(entries)
    changed = force or signature != _LAYOUT_CACHE.get("signature")
    rows = _rebuild_layout_cache(entries) if changed else _clone_rows(_LAYOUT_CACHE.get("rows", []))
    return rows, changed


CACHE_WATCH_INTERVAL_MS = 5 * 1000
MAIN_LAUNCHER_REFRESH_INTERVAL_MS = 15 * 1000


def _bind_cache_watcher(win, getter, on_change, interval_ms=CACHE_WATCH_INTERVAL_MS):
    state = {"after_id": None}
    def _tick():
        state["after_id"] = None
        try:
            if not win.winfo_exists():
                return
        except Exception:
            return
        try:
            _rows, changed = getter(force=False)
            if changed:
                on_change()
        except Exception:
            pass
        try:
            state["after_id"] = win.after(interval_ms, _tick)
        except Exception:
            state["after_id"] = None
    try:
        state["after_id"] = win.after(interval_ms, _tick)
    except Exception:
        state["after_id"] = None
    return state


def _cancel_cache_watcher(win, watcher_state):
    after_id = watcher_state.get("after_id") if isinstance(watcher_state, dict) else None
    if after_id is None:
        return
    try:
        win.after_cancel(after_id)
    except Exception:
        pass
    try:
        watcher_state["after_id"] = None
    except Exception:
        pass


def regenerate_preview_image_for_json_path(
    json_path,
    template_mode=False,
    default_dir=None,
    prompt_save_template=None,
    scale=0.75,
):
    """Regenerate and save a preview image directly from layout JSON without opening an editor window."""
    data = safe_read_json(json_path)
    if not data:
        raise RuntimeError(f"Could not read: {json_path}")
    press = data.get("press")
    fmt = data.get("format")
    if not press or not fmt:
        raise RuntimeError("JSON missing 'press' or 'format'.")
    base_cfg = CONFIG_MAP.get((press, fmt))
    if not base_cfg:
        raise RuntimeError(f"No config found for {press} - {fmt}")
    image = render_layout_preview_image_from_data(
        data,
        dict(base_cfg),
        scale=scale,
        title_base=f"{press} - {fmt}",
        template_mode=bool(template_mode),
    )
    if image is None:
        raise RuntimeError(f"Could not build preview for: {json_path}")
    out_path = preview_image_path_for_json(json_path)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        ensure_dir(out_dir)
    image.save(out_path, format="PNG")
    return out_path


def open_json_in_layout(
    root,
    json_path,
    template_mode=False,
    load_as_copy=False,
    copy_blank_issue_product=False,
    copy_blank_issue_only=False,
    default_dir=None,
    prompt_save_template=None,
    copy_issue_date_tomorrow=False,
):
    data = safe_read_json(json_path)
    if not data:
        messagebox.showerror("Open Failed", f"Could not read: {json_path}")
        return
    press = data.get("press")
    fmt = data.get("format")
    if not press or not fmt:
        messagebox.showerror("Open Failed", "JSON missing 'press' or 'format'.")
        return
    base_cfg = CONFIG_MAP.get((press, fmt))
    if not base_cfg:
        messagebox.showerror("Open Failed", f"No config found for {press} - {fmt}")
        return
    cfg = dict(base_cfg)
    cfg["section_count"] = data.get("section_count", 1)
    cfg["section_pages"] = data.get("section_pages", [min_pages_for_format(fmt)])
    cfg["template_mode"] = bool(template_mode)
    cfg["regular_mode"] = (not bool(template_mode)) and bool(default_dir) and os.path.abspath(default_dir) == os.path.abspath(REGULAR_DIR)
    cfg["copy_blank_issue_product"] = bool(copy_blank_issue_product)
    cfg["copy_blank_issue_only"] = bool(copy_blank_issue_only)
    cfg["copy_issue_date_tomorrow"] = bool(copy_issue_date_tomorrow)
    if default_dir:
        cfg["default_dir"] = default_dir
    if prompt_save_template is not None:
        cfg["prompt_save_template"] = bool(prompt_save_template)
    title = f"{press} - {fmt}"
    win = tk.Toplevel(root)
    set_window_icon(win)
    win.withdraw()
    build_press_layout(
        win,
        title=title,
        config=cfg,
        load_path=json_path,
        load_as_copy=bool(load_as_copy),
    )
    return win


def _window_rect(win):
    try:
        win.update_idletasks()
    except Exception:
        pass
    try:
        left = int(win.winfo_rootx())
        top = int(win.winfo_rooty())
        width = int(win.winfo_width())
        height = int(win.winfo_height())
    except Exception:
        return None
    return {
        "left": left,
        "top": top,
        "right": left + max(1, width),
        "bottom": top + max(1, height),
    }


def _clear_preview_panel(preview_label, preview_state, empty_text="Select an item to preview"):
    try:
        preview_label.configure(image="", text=empty_text)
    except Exception:
        pass
    try:
        preview_label.image = None
    except Exception:
        pass
    preview_state["photo"] = None
    preview_state["pil_image"] = None
    preview_state["win"] = None
    preview_state["path"] = None


def _set_preview_panel(preview_label, preview_state, image):
    if image is None:
        _clear_preview_panel(preview_label, preview_state)
        return
    preview_state["pil_image"] = image
    preview_state["win"] = None
    _render_preview_panel_image(preview_label, preview_state)


def open_json_preview(root, json_path, template_mode=False):
    image = load_preview_image_for_json(json_path)
    preview_title = None
    if image is not None:
        try:
            data = safe_read_json(json_path) or {}
            press = data.get("press") or ""
            fmt = data.get("format") or ""
            preview_title = "Preview"
        except Exception:
            preview_title = "Preview"
        return image, preview_title

    data = safe_read_json(json_path)
    if not data:
        messagebox.showerror("Open Failed", f"Could not read: {json_path}")
        return None, None
    press = data.get("press")
    fmt = data.get("format")
    if not press or not fmt:
        messagebox.showerror("Open Failed", "JSON missing 'press' or 'format'.")
        return None, None
    base_cfg = CONFIG_MAP.get((press, fmt))
    if not base_cfg:
        messagebox.showerror("Open Failed", f"No config found for {press} - {fmt}")
        return None, None

    image = render_layout_preview_image_from_data(
        data,
        dict(base_cfg),
        scale=0.75,
        title_base=f"{press} - {fmt}",
        template_mode=bool(template_mode),
    )
    if image is None:
        return None, None
    try:
        out_path = preview_image_path_for_json(json_path)
        ensure_dir(os.path.dirname(out_path))
        image.save(out_path, format="PNG")
    except Exception:
        pass
    return image, "Preview"


def open_new_template(parent):
    """Open a new blank layout in template mode."""
    # Create a simple dialog to select Press and Format
    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title("New Template")
    dialog.transient(parent)
    dialog.grab_set()
    remember_window_geometry(dialog, "new_template_dialog", default_geometry="400x150", minsize=(400, 150))

    frame = ttk.Frame(dialog, padding=16)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", pady=8, padx=(0, 8))
    press_var = tk.StringVar(value="Press 1")
    press_combo = ttk.Combobox(frame, textvariable=press_var, values=["Press 1", "Press 2"], state="readonly", width=20)
    press_combo.grid(row=0, column=1, sticky="ew", padx=(0, 0))

    ttk.Label(frame, text="Format:", font=(None, 11, "bold")).grid(row=1, column=0, sticky="w", pady=8, padx=(0, 8))
    format_var = tk.StringVar(value="Broadsheet")
    format_combo = ttk.Combobox(frame, textvariable=format_var, values=["Broadsheet", "Tab", "8 up"], state="readonly", width=20)
    format_combo.grid(row=1, column=1, sticky="ew", padx=(0, 0))

    frame.columnconfigure(1, weight=1)

    result = {"ok": False}

    def on_ok():
        result["ok"] = True
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=2, column=0, columnspan=2, pady=(16, 0), sticky="ew")
    btn_frame.columnconfigure(0, weight=1)

    ttk.Button(btn_frame, text="Create", command=on_ok, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="Cancel", command=on_cancel, width=12).pack(side="left")

    dialog.wait_window(dialog)

    if not result["ok"]:
        return

    press = press_var.get()
    fmt = format_var.get()
    base_cfg = CONFIG_MAP.get((press, fmt))
    if not base_cfg:
        messagebox.showerror("Not Configured", f"{press} - {fmt} is not configured yet.")
        return

    cfg = dict(base_cfg)
    cfg["section_count"] = 1
    cfg["section_pages"] = [min_pages_for_format(fmt)]
    cfg["template_mode"] = True

    win = tk.Toplevel(parent)
    set_window_icon(win)
    win.withdraw()
    build_press_layout(
        win,
        title=f"{press} - {fmt}",
        config=cfg,
        load_path=None,
        load_as_copy=False,
    )


def open_new_regular(parent):
    """Open a new blank regular publication layout."""
    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title("New Regular")
    dialog.transient(parent)
    dialog.grab_set()
    remember_window_geometry(dialog, "new_regular_dialog", default_geometry="400x150", minsize=(400, 150))

    frame = ttk.Frame(dialog, padding=16)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", pady=8, padx=(0, 8))
    press_var = tk.StringVar(value="Press 1")
    ttk.Combobox(frame, textvariable=press_var, values=["Press 1", "Press 2"], state="readonly", width=20).grid(row=0, column=1, sticky="ew")

    ttk.Label(frame, text="Format:", font=(None, 11, "bold")).grid(row=1, column=0, sticky="w", pady=8, padx=(0, 8))
    format_var = tk.StringVar(value="Broadsheet")
    ttk.Combobox(frame, textvariable=format_var, values=["Broadsheet", "Tab", "8 up"], state="readonly", width=20).grid(row=1, column=1, sticky="ew")
    frame.columnconfigure(1, weight=1)
    result = {"ok": False}

    def on_ok():
        result["ok"] = True
        dialog.destroy()

    ttk.Button(frame, text="Create", command=on_ok, width=12).grid(row=2, column=0, pady=(16, 0), sticky="w")
    ttk.Button(frame, text="Cancel", command=dialog.destroy, width=12).grid(row=2, column=1, pady=(16, 0), sticky="w")

    dialog.wait_window(dialog)
    if not result["ok"]:
        return

    press = press_var.get()
    fmt = format_var.get()
    base_cfg = CONFIG_MAP.get((press, fmt))
    if not base_cfg:
        messagebox.showerror("Not Configured", f"{press} - {fmt} is not configured yet.")
        return
    cfg = dict(base_cfg)
    cfg["section_count"] = 1
    cfg["section_pages"] = [min_pages_for_format(fmt)]
    cfg["template_mode"] = False
    cfg["regular_mode"] = True
    cfg["default_dir"] = REGULAR_DIR
    cfg["prompt_save_template"] = False

    win = tk.Toplevel(parent)
    set_window_icon(win)
    win.withdraw()
    build_press_layout(win, title=f"{press} - {fmt}", config=cfg, load_path=None, load_as_copy=False)


def build_new_layout_launcher(parent):
    root = tk.Toplevel(parent)
    set_window_icon(root)
    root.title("New Layout")
    root.geometry("1180x760")
    root.minsize(1040, 680)
    remember_window_geometry(root, "new_layout_launcher", default_geometry="1180x760", minsize=(1040, 680))
    _bind_window_size_memory(root, "new_layout_launcher")

    paned = tk.PanedWindow(root, orient="vertical", sashrelief="raised", sashwidth=8, bd=0, showhandle=False)
    paned.pack(fill="both", expand=True)
    frame = ttk.Frame(paned, padding=(16, 16, 16, 4))
    paned.add(frame, stretch="always", minsize=220)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)

    new_layout_saved_state = load_window_state_map().get("new_layout_launcher")
    if not isinstance(new_layout_saved_state, dict):
        new_layout_saved_state = {}
    saved_mode_value = str(new_layout_saved_state.get("mode") or "").strip().lower()
    if saved_mode_value in {"regular", "from_regular", "from regular", "regulars"}:
        initial_regular_mode = True
    elif saved_mode_value in {"standard", "guided", "template", "templates"}:
        initial_regular_mode = False
    else:
        initial_regular_mode = bool(new_layout_saved_state.get("regular_mode", False))

    mode_state = {"regular": initial_regular_mode}
    preview_state = {"win": None, "path": None, "after_id": None, "request_id": 0, "photo": None, "pil_image": None}
    launcher_template_sort_state = load_treeview_sort_state("new_layout_launcher", "templates_tree", "name")
    launcher_regular_sort_state = load_treeview_sort_state("new_layout_launcher", "regular_tree", "product")
    template_rows_by_iid = {}
    regular_rows = {}
    launcher_template_group_by_iid = {}
    launcher_regular_group_by_iid = {}

    def save_new_layout_mode_preference():
        try:
            state_map = load_window_state_map()
            window_state = state_map.get("new_layout_launcher")
            if not isinstance(window_state, dict):
                window_state = {}
            window_state["mode"] = "regular" if mode_state.get("regular") else "standard"
            window_state["regular_mode"] = bool(mode_state.get("regular"))
            state_map["new_layout_launcher"] = window_state
            save_window_state_map(state_map)
        except Exception:
            pass

    mode_bar = ttk.Frame(frame)
    mode_bar.grid(row=0, column=0, columnspan=12, sticky="ew", pady=(0, 8))
    mode_bar.columnconfigure(1, weight=1)
    mode_button = ttk.Button(mode_bar, text="From Regular", width=16)
    mode_button.grid(row=0, column=0, sticky="w")
    mode_note_var = tk.StringVar(value="Guided mode: filter templates, then pick one or create a blank layout from a specific press / format / section setup.")
    ttk.Label(mode_bar, textvariable=mode_note_var).grid(row=0, column=1, sticky="w", padx=(12, 0))

    search_frame = ttk.Frame(frame)
    search_frame.grid(row=1, column=0, columnspan=12, sticky="ew", pady=(0, 4))
    search_frame.columnconfigure(1, weight=1)
    ttk.Label(search_frame, text="Search:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 8))
    new_layout_search_var = tk.StringVar(value="")
    ttk.Entry(search_frame, textvariable=new_layout_search_var).grid(row=0, column=1, sticky="ew")

    filter_frame = ttk.Frame(frame)
    filter_frame.grid(row=2, column=0, columnspan=12, sticky="ew", pady=(4, 8))
    ttk.Label(filter_frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 8))
    press_var = tk.StringVar(value="All")
    press_combo = ttk.Combobox(filter_frame, textvariable=press_var, values=["All", "Press 1", "Press 2"], state="readonly", width=12)
    press_combo.grid(row=0, column=1, sticky="w", padx=(0, 12))
    ttk.Label(filter_frame, text="Format:", font=(None, 11, "bold")).grid(row=0, column=2, sticky="w", padx=(0, 8))
    format_var = tk.StringVar(value="All")
    format_combo = ttk.Combobox(filter_frame, textvariable=format_var, values=["All", "Broadsheet", "Tab", "8 up"], state="readonly", width=12)
    format_combo.grid(row=0, column=3, sticky="w", padx=(0, 12))
    section_label = ttk.Label(filter_frame, text="Sections:", font=(None, 11, "bold"))
    section_label.grid(row=0, column=4, sticky="w", padx=(0, 8))
    section_count_var = tk.StringVar(value="All")
    section_count_combo = ttk.Combobox(filter_frame, textvariable=section_count_var, values=["All", "1", "2", "3", "4"], state="readonly", width=8)
    section_count_combo.grid(row=0, column=5, sticky="w", padx=(0, 12))
    ttk.Label(filter_frame, text="Pages:", font=(None, 11, "bold")).grid(row=0, column=6, sticky="w", padx=(0, 8))
    pages_filter_var = tk.StringVar(value="All")
    pages_filter_combo = ttk.Combobox(filter_frame, textvariable=pages_filter_var, values=["All"], state="readonly", width=14)
    pages_filter_combo.grid(row=0, column=7, sticky="w", padx=(0, 0))

    template_container = ttk.Frame(frame)
    template_container.grid(row=3, column=0, columnspan=12, sticky="nsew", pady=(8, 0))
    template_container.columnconfigure(0, weight=1)
    template_container.rowconfigure(1, weight=1)
    ttk.Label(template_container, text="Templates:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="nw")
    template_search_var = new_layout_search_var
    templates_frame = ttk.Frame(template_container)
    templates_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
    templates_frame.rowconfigure(0, weight=1)
    templates_frame.columnconfigure(0, weight=1)
    template_columns = ("sections", "pages", "changed_by", "saved")
    templates_tree = ttk.Treeview(templates_frame, columns=template_columns, show="tree headings", selectmode="browse")
    templates_tree.grid(row=0, column=0, sticky="nsew")
    templates_scroll = ttk.Scrollbar(templates_frame, orient="vertical", command=templates_tree.yview)
    templates_scroll.grid(row=0, column=1, sticky="ns")
    templates_tree.configure(yscrollcommand=templates_scroll.set)
    launcher_template_heading_titles = {"sections": "Sections", "pages": "Pages", "changed_by": "Last Changed By", "saved": "Last Saved"}
    templates_tree.heading("#0", text="Template Name")
    templates_tree.column("#0", width=300, anchor="w")
    for key, title, width, anchor in [("sections", launcher_template_heading_titles["sections"], 80, "center"), ("pages", launcher_template_heading_titles["pages"], 130, "center"), ("changed_by", launcher_template_heading_titles["changed_by"], 140, "center"), ("saved", launcher_template_heading_titles["saved"], 170, "center")]:
        templates_tree.heading(key, text=title)
        templates_tree.column(key, width=width, anchor=anchor)
    try:
        templates_tree.tag_configure("group_row", font=(None, 10, "bold"), foreground="#1f1f1f")
        templates_tree.tag_configure("subgroup_row", font=(None, 10, "bold"), foreground="#444444")
    except Exception:
        pass
    apply_treeview_column_width_state(templates_tree, ("#0",) + tuple(template_columns), "new_layout_launcher", "templates_tree")
    bind_treeview_state_memory(root, "new_layout_launcher", "templates_tree", templates_tree, columns=("#0",) + tuple(template_columns))

    regular_container = ttk.Frame(frame)
    regular_container.columnconfigure(0, weight=1)
    regular_container.rowconfigure(1, weight=1)
    ttk.Label(regular_container, text="Regular Layouts:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="nw")
    regular_search_var = new_layout_search_var
    regular_frame = ttk.Frame(regular_container)
    regular_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
    regular_frame.rowconfigure(0, weight=1)
    regular_frame.columnconfigure(0, weight=1)
    regular_columns = ("pages", "color_pages", "plates", "changed_by", "saved")
    regular_tree = ttk.Treeview(regular_frame, columns=regular_columns, show="tree headings", selectmode="browse")
    regular_tree.grid(row=0, column=0, sticky="nsew")
    regular_scroll = ttk.Scrollbar(regular_frame, orient="vertical", command=regular_tree.yview)
    regular_scroll.grid(row=0, column=1, sticky="ns")
    regular_tree.configure(yscrollcommand=regular_scroll.set)
    launcher_regular_heading_titles = {"pages": "Pages", "color_pages": "Color Pages", "plates": "Plates", "changed_by": "Last Changed By", "saved": "Last Saved"}
    regular_tree.heading("#0", text="Product")
    regular_tree.column("#0", width=260, anchor="w")
    for key, title, width, anchor in [("pages", launcher_regular_heading_titles["pages"], 120, "center"), ("color_pages", launcher_regular_heading_titles["color_pages"], 95, "center"), ("plates", launcher_regular_heading_titles["plates"], 70, "center"), ("changed_by", launcher_regular_heading_titles["changed_by"], 140, "center"), ("saved", launcher_regular_heading_titles["saved"], 170, "center")]:
        regular_tree.heading(key, text=title)
        regular_tree.column(key, width=width, anchor=anchor)
    try:
        regular_tree.tag_configure("group_row", font=(None, 10, "bold"), foreground="#1f1f1f")
        regular_tree.tag_configure("subgroup_row", font=(None, 10, "bold"), foreground="#444444")
    except Exception:
        pass
    apply_treeview_column_width_state(regular_tree, ("#0",) + tuple(regular_columns), "new_layout_launcher", "regular_tree")
    bind_treeview_state_memory(root, "new_layout_launcher", "regular_tree", regular_tree, columns=("#0",) + tuple(regular_columns))
    btn_row = ttk.Frame(frame)
    btn_row.grid(row=4, column=0, columnspan=12, pady=(12, 0), sticky="w")
    action_button = ttk.Button(btn_row, text="New / Open", width=14)
    action_button.pack(side="left", padx=(0, 8))
    refresh_button = ttk.Button(btn_row, text="Refresh Templates", width=16)
    refresh_button.pack(side="left")

    preview_box = ttk.LabelFrame(paned, text="Preview", padding=(8, 4, 8, 8))
    preview_box.columnconfigure(0, weight=1)
    preview_label = ttk.Label(preview_box, text="Select a template to preview", anchor="center", justify="center")
    preview_label.grid(row=0, column=0, sticky="nsew")
    preview_box.rowconfigure(0, weight=1)
    preview_label.bind("<Configure>", lambda e: _render_preview_panel_image(preview_label, preview_state), add="+")
    paned.add(preview_box, minsize=160)
    _bind_preview_pane_memory(root, "new_layout_launcher", paned, preview_box, default_height=240)

    def current_empty_text():
        return "Select a regular layout to preview" if mode_state["regular"] else "Select a template to preview"
    def cancel_pending_preview():
        after_id = preview_state.get("after_id")
        preview_state["after_id"] = None
        if after_id is not None:
            try:
                root.after_cancel(after_id)
            except Exception:
                pass
    def close_preview():
        cancel_pending_preview()
        _clear_preview_panel(preview_label, preview_state, empty_text=current_empty_text())
    def _launcher_is_active():
        try:
            focused = root.focus_displayof()
            return bool(focused) and focused.winfo_toplevel() == root
        except Exception:
            return False
    def selected_template_path():
        sel = templates_tree.selection()
        candidate = sel[0] if sel else templates_tree.focus()
        if candidate in template_rows_by_iid:
            return candidate
        focused = templates_tree.focus()
        return focused if focused in template_rows_by_iid else None
    def selected_regular_path():
        sel = regular_tree.selection()
        candidate = sel[0] if sel else regular_tree.focus()
        if candidate in regular_rows:
            return candidate
        focused = regular_tree.focus()
        return focused if focused in regular_rows else None
    def current_preview_path():
        return selected_regular_path() if mode_state["regular"] else selected_template_path()
    def show_preview(path):
        cancel_pending_preview()
        preview_state["request_id"] = int(preview_state.get("request_id", 0)) + 1
        request_id = preview_state["request_id"]
        if not path:
            close_preview()
            return
        def _do_show(_path=path, _request_id=request_id):
            preview_state["after_id"] = None
            if _request_id != preview_state.get("request_id"):
                return
            if current_preview_path() != _path:
                return
            current_sig = _preview_file_signature_for_json(_path)
            if preview_state.get("path") == _path and preview_state.get("photo") is not None and preview_state.get("preview_file_sig") == current_sig:
                return
            close_preview()
            image, _preview_title = open_json_preview(root, _path, template_mode=(not mode_state["regular"]))
            if image is None:
                _clear_preview_panel(preview_label, preview_state, empty_text=current_empty_text())
                return
            _set_preview_panel(preview_label, preview_state, image)
            preview_state["path"] = _path
            preview_state["preview_file_sig"] = current_sig
        preview_state["after_id"] = root.after_idle(_do_show)
    def _active_section_count():
        value = (section_count_var.get() or "All").strip()
        if value == "All":
            return None
        try:
            return max(1, min(4, int(value)))
        except Exception:
            return None
    def _active_pages_filter():
        value = (pages_filter_var.get() or "All").strip()
        return None if value == "All" else value
    def _page_display_sort_key(value):
        text = str(value or "")
        numbers = []
        for part in re.findall(r"\d+", text):
            try:
                numbers.append(int(part))
            except Exception:
                pass
        return (numbers, text.lower())
    def _update_new_layout_pages_filter_values(rows):
        values = ["All"] + sorted({str(row.get("pages_disp") or "").strip() for row in rows if str(row.get("pages_disp") or "").strip()}, key=_page_display_sort_key)
        pages_filter_combo.configure(values=values)
        if pages_filter_var.get() not in values:
            pages_filter_var.set("All")
    def update_launcher_template_sort_headings():
        templates_tree.heading("#0", text=_treeview_sort_heading_text("Template Name", launcher_template_sort_state, "name"), command=lambda: sort_launcher_templates_by("name"))
        for col in template_columns:
            templates_tree.heading(col, text=_treeview_sort_heading_text(launcher_template_heading_titles[col], launcher_template_sort_state, col), command=lambda _c=col: sort_launcher_templates_by(_c))
    def sort_launcher_template_rows(rows):
        col = launcher_template_sort_state.get("col")
        if not col:
            return rows
        def keyfunc(r):
            if col == "sections":
                return (int(r.get("section_count") or 0), tuple(r.get("section_pages_sort", (0, 0, 0, 0))), (r.get("name") or "").lower())
            if col == "pages":
                return (tuple(r.get("section_pages_sort", (0, 0, 0, 0))), int(r.get("section_count") or 0), (r.get("name") or "").lower())
            if col == "changed_by":
                return ((r.get("last_changed_by") or "").lower(), (r.get("name") or "").lower())
            if col == "saved":
                return (r.get("saved_dt") or datetime.min, (r.get("name") or "").lower())
            return (r.get("name") or "").lower()
        return sorted(rows, key=keyfunc, reverse=launcher_template_sort_state["desc"])
    def sort_launcher_regular_rows(rows):
        col = launcher_regular_sort_state.get("col")
        if not col:
            return rows
        def keyfunc(r):
            if col == "product":
                return ((r.get("product") or "").lower(), tuple(r.get("section_pages_sort", (0, 0, 0, 0))), r.get("saved_dt") or datetime.min)
            if col == "pages":
                return tuple(r.get("section_pages_sort", (0, 0, 0, 0)))
            if col == "color_pages":
                return int(r.get("color_pages", 0) or 0)
            if col == "plates":
                return int(r.get("plates", 0) or 0)
            if col == "changed_by":
                return ((r.get("last_changed_by") or "").lower(), (r.get("product") or "").lower())
            if col == "saved":
                return r.get("saved_dt") or datetime.min
            return ((r.get("product") or "").lower(), tuple(r.get("section_pages_sort", (0, 0, 0, 0))), r.get("saved_dt") or datetime.min)
        return sorted(rows, key=keyfunc, reverse=launcher_regular_sort_state["desc"])
    def update_launcher_regular_sort_headings():
        regular_tree.heading("#0", text=_treeview_sort_heading_text("Product", launcher_regular_sort_state, "product"), command=lambda: sort_launcher_regular_by("product"))
        for col in regular_columns:
            regular_tree.heading(col, text=_treeview_sort_heading_text(launcher_regular_heading_titles[col], launcher_regular_sort_state, col), command=lambda _c=col: sort_launcher_regular_by(_c))
    def sort_launcher_templates_by(col):
        if launcher_template_sort_state["col"] == col:
            launcher_template_sort_state["desc"] = not launcher_template_sort_state["desc"]
        else:
            launcher_template_sort_state["col"] = col
            launcher_template_sort_state["desc"] = False
        save_treeview_sort_state("new_layout_launcher", "templates_tree", launcher_template_sort_state)
        refresh_templates()
    def sort_launcher_regular_by(col):
        if launcher_regular_sort_state["col"] == col:
            launcher_regular_sort_state["desc"] = not launcher_regular_sort_state["desc"]
        else:
            launcher_regular_sort_state["col"] = col
            launcher_regular_sort_state["desc"] = False
        save_treeview_sort_state("new_layout_launcher", "regular_tree", launcher_regular_sort_state)
        refresh_regulars()
    def _matches_template_filters_base(row):
        search_text = (template_search_var.get() or "").strip().lower()
        press_filter = (press_var.get() or "All").strip()
        format_filter = (format_var.get() or "All").strip()
        active_count = _active_section_count()
        if search_text:
            searchable = " ".join([
                row.get("name", ""),
                row.get("press", ""),
                row.get("format", ""),
                str(row.get("section_count") or ""),
                row.get("pages_disp", ""),
                row.get("last_changed_by", ""),
                row.get("saved_disp", ""),
            ]).lower()
            if search_text not in searchable:
                return False
        if press_filter != "All" and row.get("press", "") != press_filter:
            return False
        if format_filter != "All" and row.get("format", "") != format_filter:
            return False
        if active_count is not None and int(row.get("section_count") or 0) != active_count:
            return False
        return True
    def _matches_template_filters(row):
        if not _matches_template_filters_base(row):
            return False
        pages_filter = _active_pages_filter()
        if pages_filter is not None and row.get("pages_disp", "") != pages_filter:
            return False
        return True
    def _matches_regular_filters_base(row):
        search_text = (regular_search_var.get() or "").strip().lower()
        press_filter = (press_var.get() or "All").strip()
        format_filter = (format_var.get() or "All").strip()
        if search_text:
            searchable = " ".join([row.get("product", ""), row.get("press", ""), row.get("format", ""), row.get("pages_disp", ""), str(row.get("color_pages", "")), str(row.get("plates", "")), row.get("saved_disp", "")]).lower()
            if search_text not in searchable:
                return False
        if press_filter != "All" and row.get("press", "") != press_filter:
            return False
        if format_filter != "All" and row.get("format", "") != format_filter:
            return False
        return True
    def _matches_regular_filters(row):
        if not _matches_regular_filters_base(row):
            return False
        pages_filter = _active_pages_filter()
        if pages_filter is not None and row.get("pages_disp", "") != pages_filter:
            return False
        return True
    def refresh_templates(*_):
        if mode_state["regular"]:
            return
        tree_state, has_saved_state = get_treeview_reload_state(templates_tree, "new_layout_launcher", "templates_tree", columns=("#0",) + tuple(template_columns))
        selected = selected_template_path()
        saved_selected = [str(iid) for iid in (tree_state.get("selected_iids") or [])]
        saved_focus = str(tree_state.get("focus_iid") or "").strip() or None
        saved_yview = tree_state.get("yview") if isinstance(tree_state.get("yview"), list) else None
        open_iids = set(str(iid) for iid in (tree_state.get("open_iids") or []))
        template_rows_by_iid.clear()
        launcher_template_group_by_iid.clear()
        templates_tree.delete(*templates_tree.get_children())
        cached_rows, _changed = get_cached_templates(force=False)
        candidate_rows = []
        rows = []
        for cached in cached_rows:
            if not bool(cached.get("valid", False)):
                continue
            row = {"path": cached.get("path"), "name": cached.get("name") or os.path.splitext(os.path.basename(cached.get("path") or ""))[0], "press": cached.get("press") or "", "format": cached.get("format") or "", "section_count": int(cached.get("section_count") or 0), "section_pages_sort": tuple(([int(v) for v in (cached.get("section_pages") or []) if str(v).strip() != "" and int(v) > 0] + [0, 0, 0, 0])[:4]), "pages_disp": _format_section_pages_for_display({"section_pages": cached.get("section_pages") or [], "section_count": cached.get("section_count") or 0}), "last_changed_by": cached.get("last_changed_by") or "Unknown", "saved_dt": cached.get("saved_dt"), "saved_disp": cached.get("saved_disp") or ""}
            if _matches_template_filters_base(row):
                candidate_rows.append(row)
            if _matches_template_filters(row):
                rows.append(row)
        _update_new_layout_pages_filter_values(candidate_rows)
        rows = sort_launcher_template_rows(rows)
        press_order = ["Press 1", "Press 2"]
        format_order = ["Broadsheet", "Tab", "8 up"]
        grouped = {}
        for row in rows:
            press_name = str(row.get("press") or "").strip() or "Unknown Press"
            format_name = str(row.get("format") or "").strip() or "Unknown Format"
            grouped.setdefault(press_name, {}).setdefault(format_name, []).append(row)
        def press_sort_key(value):
            return (press_order.index(value), value.lower()) if value in press_order else (len(press_order), value.lower())
        def format_sort_key(value):
            return (format_order.index(value), value.lower()) if value in format_order else (len(format_order), value.lower())
        press_reverse = bool(launcher_template_sort_state.get("col") == "press" and launcher_template_sort_state.get("desc"))
        format_reverse = bool(launcher_template_sort_state.get("col") == "format" and launcher_template_sort_state.get("desc"))
        for press_name in sorted(grouped.keys(), key=press_sort_key, reverse=press_reverse):
            press_iid = f"__new_layout_template_press__::{press_name}"
            format_groups = grouped.get(press_name, {})
            press_count = sum(len(items) for items in format_groups.values())
            press_open = True if not has_saved_state else (press_iid in open_iids)
            templates_tree.insert("", "end", iid=press_iid, text=f"{press_name} ({press_count})", values=("", "", "", ""), open=press_open, tags=("group_row",))
            launcher_template_group_by_iid[press_iid] = ("press", press_name)
            for format_name in sorted(format_groups.keys(), key=format_sort_key, reverse=format_reverse):
                format_iid = f"__new_layout_template_format__::{press_name}::{format_name}"
                format_count = len(format_groups.get(format_name, []))
                format_open = True if not has_saved_state else (format_iid in open_iids)
                templates_tree.insert(press_iid, "end", iid=format_iid, text=f"{format_name} ({format_count})", values=("", "", "", ""), open=format_open, tags=("subgroup_row",))
                launcher_template_group_by_iid[format_iid] = ("format", press_name, format_name)
                for row in format_groups.get(format_name, []):
                    iid = row["path"]
                    template_rows_by_iid[iid] = row
                    templates_tree.insert(format_iid, "end", iid=iid, text=row.get("name", ""), values=(row.get("section_count", ""), row.get("pages_disp", ""), row.get("last_changed_by", "Unknown"), row.get("saved_disp", "")))
        update_launcher_template_sort_headings()
        known_iids = set(template_rows_by_iid).union(launcher_template_group_by_iid)
        restore_selection = [iid for iid in saved_selected if iid in known_iids]
        if not restore_selection and selected and selected in template_rows_by_iid:
            restore_selection = [selected]
        for iid in restore_selection:
            open_treeview_item_ancestors(templates_tree, iid)
        if restore_selection:
            templates_tree.selection_set(restore_selection)
        focus_target = saved_focus if saved_focus in known_iids else (restore_selection[0] if restore_selection else None)
        if focus_target:
            open_treeview_item_ancestors(templates_tree, focus_target)
            templates_tree.focus(focus_target)
        if saved_yview and len(saved_yview) > 0:
            try:
                templates_tree.yview_moveto(float(saved_yview[0]))
            except Exception:
                pass
        if not restore_selection:
            close_preview()
    def refresh_regulars(*_):
        if not mode_state["regular"]:
            return
        tree_state, has_saved_state = get_treeview_reload_state(regular_tree, "new_layout_launcher", "regular_tree", columns=("#0",) + tuple(regular_columns))
        selected = selected_regular_path()
        saved_selected = [str(iid) for iid in (tree_state.get("selected_iids") or [])]
        saved_focus = str(tree_state.get("focus_iid") or "").strip() or None
        saved_yview = tree_state.get("yview") if isinstance(tree_state.get("yview"), list) else None
        open_iids = set(str(iid) for iid in (tree_state.get("open_iids") or []))
        rows, _changed = get_cached_regular_rows(force=False)
        candidate_rows = [row for row in rows if _matches_regular_filters_base(row)]
        _update_new_layout_pages_filter_values(candidate_rows)
        rows = [row for row in candidate_rows if _matches_regular_filters(row)]
        rows = sort_launcher_regular_rows(rows)
        regular_tree.delete(*regular_tree.get_children())
        regular_rows.clear()
        launcher_regular_group_by_iid.clear()
        press_order = ["Press 1", "Press 2"]
        format_order = ["Broadsheet", "Tab", "8 up"]
        grouped = {}
        for row in rows:
            press_name = str(row.get("press") or "").strip() or "Unknown Press"
            format_name = str(row.get("format") or "").strip() or "Unknown Format"
            grouped.setdefault(press_name, {}).setdefault(format_name, []).append(row)
        def press_sort_key(value):
            return (press_order.index(value), value.lower()) if value in press_order else (len(press_order), value.lower())
        def format_sort_key(value):
            return (format_order.index(value), value.lower()) if value in format_order else (len(format_order), value.lower())
        press_reverse = bool(launcher_regular_sort_state.get("col") == "press" and launcher_regular_sort_state.get("desc"))
        format_reverse = bool(launcher_regular_sort_state.get("col") == "format" and launcher_regular_sort_state.get("desc"))
        for press_name in sorted(grouped.keys(), key=press_sort_key, reverse=press_reverse):
            press_iid = f"__new_layout_regular_press__::{press_name}"
            format_groups = grouped.get(press_name, {})
            press_count = sum(len(items) for items in format_groups.values())
            press_open = True if not has_saved_state else (press_iid in open_iids)
            regular_tree.insert("", "end", iid=press_iid, text=f"{press_name} ({press_count})", values=("", "", "", "", ""), open=press_open, tags=("group_row",))
            launcher_regular_group_by_iid[press_iid] = ("press", press_name)
            for format_name in sorted(format_groups.keys(), key=format_sort_key, reverse=format_reverse):
                format_iid = f"__new_layout_regular_format__::{press_name}::{format_name}"
                format_count = len(format_groups.get(format_name, []))
                format_open = True if not has_saved_state else (format_iid in open_iids)
                regular_tree.insert(press_iid, "end", iid=format_iid, text=f"{format_name} ({format_count})", values=("", "", "", "", ""), open=format_open, tags=("subgroup_row",))
                launcher_regular_group_by_iid[format_iid] = ("format", press_name, format_name)
                for row in format_groups.get(format_name, []):
                    iid = row.get("path")
                    regular_rows[iid] = row
                    regular_tree.insert(format_iid, "end", iid=iid, text=row.get("product", ""), values=(row.get("pages_disp", ""), row.get("color_pages", 0), row.get("plates", 0), row.get("last_changed_by", "Unknown"), row.get("saved_disp", "")))
        update_launcher_regular_sort_headings()
        known_iids = set(regular_rows).union(launcher_regular_group_by_iid)
        restore_selection = [iid for iid in saved_selected if iid in known_iids]
        if not restore_selection and selected and selected in regular_rows:
            restore_selection = [selected]
        for iid in restore_selection:
            open_treeview_item_ancestors(regular_tree, iid)
        if restore_selection:
            regular_tree.selection_set(restore_selection)
        focus_target = saved_focus if saved_focus in known_iids else (restore_selection[0] if restore_selection else None)
        if focus_target:
            open_treeview_item_ancestors(regular_tree, focus_target)
            regular_tree.focus(focus_target)
        if saved_yview and len(saved_yview) > 0:
            try:
                regular_tree.yview_moveto(float(saved_yview[0]))
            except Exception:
                pass
        if not restore_selection:
            close_preview()
    def update_mode_widgets():
        if mode_state["regular"]:
            section_label.grid_remove()
            section_count_combo.grid_remove()
            template_container.grid_remove()
            regular_container.grid(row=3, column=0, columnspan=12, sticky="nsew", pady=(8, 0))
            action_button.configure(text="Clone Regular")
            refresh_button.configure(text="Refresh Regulars", command=refresh_regulars)
            mode_button.configure(text="Standard Mode")
            mode_note_var.set("Regular mode: filter regular layouts, then clone the selected regular into a new layout dated tomorrow.")
        else:
            regular_container.grid_remove()
            section_label.grid()
            section_count_combo.grid()
            template_container.grid()
            action_button.configure(text="New / Open")
            refresh_button.configure(text="Refresh Templates", command=refresh_templates)
            mode_button.configure(text="From Regular")
            mode_note_var.set("Guided mode: filter templates, then pick one or create a blank layout from a specific press / format / section setup.")
        close_preview()
        refresh_regulars()
        refresh_templates()
    def toggle_mode():
        mode_state["regular"] = not mode_state["regular"]
        save_new_layout_mode_preference()
        update_mode_widgets()
    def _create_blank_or_template_layout():
        template_path = selected_template_path()
        if template_path:
            data = safe_read_json(template_path)
            if not isinstance(data, dict):
                messagebox.showerror("Open Failed", f"Could not read: {template_path}")
                return
            press = data.get("press")
            fmt = data.get("format")
            base_cfg = CONFIG_MAP.get((press, fmt))
            if not base_cfg:
                messagebox.showerror("Open Failed", f"No config found for {press} - {fmt}")
                return
            cfg = dict(base_cfg)
            cfg["section_count"] = data.get("section_count", 1)
            cfg["section_pages"] = data.get("section_pages", [0])
            cfg["template_mode"] = False
            close_preview()
            win = tk.Toplevel(parent)
            set_window_icon(win)
            build_press_layout(win, title=f"{press} - {fmt}", config=cfg, load_path=template_path, load_as_copy=True)
            root.destroy()
            return
        press = (press_var.get() or "All").strip()
        fmt = (format_var.get() or "All").strip()
        count = _active_section_count()
        if press == "All":
            press = "Press 1"
        if fmt == "All":
            fmt = "Broadsheet"
        if count is None:
            count = 1
        base_cfg = CONFIG_MAP.get((press, fmt))
        if not base_cfg:
            messagebox.showwarning("Not Configured", f"{press} - {fmt} is not configured yet.")
            return
        cfg = dict(base_cfg)
        cfg["section_count"] = count
        cfg["section_pages"] = [0] * count
        cfg["template_mode"] = False
        close_preview()
        win = tk.Toplevel(parent)
        set_window_icon(win)
        build_press_layout(win, title=f"{press} - {fmt}", config=cfg, load_path=None, load_as_copy=True)
        root.destroy()
    def on_new_or_open():
        if mode_state["regular"]:
            path = selected_regular_path()
            if not path:
                messagebox.showinfo("Select a Regular Layout", "Select a regular layout to clone into a new layout.")
                return
            close_preview()
            open_json_in_layout(parent, path, template_mode=False, load_as_copy=True, copy_issue_date_tomorrow=True)
            root.destroy()
            return
        _create_blank_or_template_layout()

    new_layout_search_var.trace_add("write", lambda *_: (refresh_templates(), refresh_regulars()))
    press_var.trace_add("write", lambda *_: (refresh_templates(), refresh_regulars()))
    format_var.trace_add("write", lambda *_: (refresh_templates(), refresh_regulars()))
    section_count_var.trace_add("write", lambda *_: refresh_templates())
    pages_filter_var.trace_add("write", lambda *_: (refresh_templates(), refresh_regulars()))
    def _on_new_layout_template_select(event=None):
        if mode_state["regular"]:
            close_preview()
        else:
            show_preview(selected_template_path())

    def _on_new_layout_regular_select(event=None):
        if mode_state["regular"]:
            show_preview(selected_regular_path())

    def _on_new_layout_template_double_click(event=None):
        item_id = templates_tree.identify_row(event.y) if event is not None else templates_tree.focus()
        if item_id in launcher_template_group_by_iid:
            try:
                templates_tree.item(item_id, open=(not bool(templates_tree.item(item_id, "open"))))
            except Exception:
                pass
            return "break"
        on_new_or_open()
        return "break"

    def _on_new_layout_regular_double_click(event=None):
        item_id = regular_tree.identify_row(event.y) if event is not None else regular_tree.focus()
        if item_id in launcher_regular_group_by_iid:
            try:
                regular_tree.item(item_id, open=(not bool(regular_tree.item(item_id, "open"))))
            except Exception:
                pass
            return "break"
        on_new_or_open()
        return "break"

    templates_tree.bind("<<TreeviewSelect>>", _on_new_layout_template_select)
    regular_tree.bind("<<TreeviewSelect>>", _on_new_layout_regular_select)
    templates_tree.bind("<Double-Button-1>", _on_new_layout_template_double_click)
    regular_tree.bind("<Double-Button-1>", _on_new_layout_regular_double_click)
    action_button.configure(command=on_new_or_open)
    mode_button.configure(command=toggle_mode)

    def _persist_new_layout_mode_on_destroy(event=None):
        try:
            if event is not None and event.widget is not root:
                return
        except Exception:
            pass
        save_new_layout_mode_preference()

    try:
        root.bind("<Destroy>", _persist_new_layout_mode_on_destroy, add="+")
    except Exception:
        pass
    update_launcher_template_sort_headings()
    update_launcher_regular_sort_headings()
    def _check_preview_freshness():
        path = preview_state.get("path")
        if not path:
            return
        current_sig = _preview_file_signature_for_json(path)
        if preview_state.get("preview_file_sig") != current_sig:
            preview_state["photo"] = None
            show_preview(path)
    def _on_cache_change():
        refresh_templates()
        refresh_regulars()
        _check_preview_freshness()
    template_cache_watcher = _bind_cache_watcher(root, get_cached_templates, _on_cache_change)
    regular_cache_watcher = _bind_cache_watcher(root, get_cached_regular_rows, _on_cache_change)
    update_mode_widgets()
    root.bind("<FocusIn>", lambda e: show_preview(current_preview_path()), add="+")
    root.protocol("WM_DELETE_WINDOW", lambda: (_persist_bound_preview_panes(root), _cancel_cache_watcher(root, template_cache_watcher), _cancel_cache_watcher(root, regular_cache_watcher), close_preview(), root.destroy()))
    return root
def build_template_editor_launcher(parent):
    root = tk.Toplevel(parent)
    set_window_icon(root)
    root.title("Template Editor")
    root.geometry("900x700")
    root.minsize(820, 620)
    remember_window_geometry(root, "template_editor_launcher", default_geometry="900x700", minsize=(820, 620))
    _bind_window_size_memory(root, "template_editor_launcher")
    allow_launcher_maintenance_actions = is_admin()
    paned = tk.PanedWindow(root, orient="vertical", sashrelief="raised", sashwidth=8, bd=0, showhandle=False)
    paned.pack(fill="both", expand=True)
    frame = ttk.Frame(paned, padding=16)
    paned.add(frame, stretch="always", minsize=220)
    # The list/tree row must own the vertical resize weight so dragging the
    # preview sash grows and shrinks the treeview, matching the main launcher
    # and the regular editor.
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(0, weight=1)

    filter_frame = ttk.Frame(frame)
    filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    filter_frame.columnconfigure(1, weight=1)
    ttk.Label(filter_frame, text="Filter:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")
    search_var = tk.StringVar(value="")
    search_entry = ttk.Entry(filter_frame, textvariable=search_var)
    search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
    ttk.Label(filter_frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=2, sticky="w")
    press_var = tk.StringVar(value="All")
    press_combo = ttk.Combobox(filter_frame, textvariable=press_var, values=["All", "Press 1", "Press 2"], state="readonly", width=12)
    press_combo.grid(row=0, column=3, sticky="w", padx=(8, 8))
    ttk.Label(filter_frame, text="Format:", font=(None, 11, "bold")).grid(row=0, column=4, sticky="w")
    format_var = tk.StringVar(value="All")
    format_combo = ttk.Combobox(filter_frame, textvariable=format_var, values=["All", "Broadsheet", "Tab", "8 up"], state="readonly", width=12)
    format_combo.grid(row=0, column=5, sticky="w", padx=(8, 8))
    ttk.Label(filter_frame, text="Pages:", font=(None, 11, "bold")).grid(row=0, column=6, sticky="w")
    pages_filter_var = tk.StringVar(value="All")
    pages_filter_combo = ttk.Combobox(filter_frame, textvariable=pages_filter_var, values=["All"], state="readonly", width=14)
    pages_filter_combo.grid(row=0, column=7, sticky="w", padx=(8, 0))
    search_var.trace_add("write", lambda *_: refresh())
    press_var.trace_add("write", lambda *_: refresh())
    format_var.trace_add("write", lambda *_: refresh())
    pages_filter_var.trace_add("write", lambda *_: refresh())

    list_frame = ttk.Frame(frame)
    list_frame.grid(row=1, column=0, sticky="nsew")
    list_frame.rowconfigure(0, weight=1)
    list_frame.columnconfigure(0, weight=1)

    columns = ("sections", "pages", "changed_by", "saved")
    tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", selectmode="browse")
    tree.grid(row=0, column=0, sticky="nsew")
    vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    vsb.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=vsb.set)

    template_heading_titles = {
        "sections": "Sections",
        "pages": "Pages",
        "changed_by": "Last Changed By",
        "saved": "Last Saved",
    }
    tree.heading("#0", text="Template Name")
    for key, title in template_heading_titles.items():
        tree.heading(key, text=title)
    tree.column("#0", width=280, anchor="w")
    tree.column("sections", width=80, anchor="center")
    tree.column("pages", width=130, anchor="center")
    tree.column("changed_by", width=140, anchor="center")
    tree.column("saved", width=170, anchor="center")
    try:
        tree.tag_configure("group_row", font=(None, 10, "bold"), foreground="#1f1f1f")
        tree.tag_configure("subgroup_row", font=(None, 10, "bold"), foreground="#444444")
    except Exception:
        pass
    apply_treeview_column_width_state(tree, ("#0", "sections", "pages", "changed_by", "saved"), "template_editor_launcher", "template_tree")
    bind_treeview_state_memory(root, "template_editor_launcher", "template_tree", tree, columns=("#0", "sections", "pages", "changed_by", "saved"))

    template_rows = []
    row_by_iid = {}
    group_by_iid = {}
    sort_state = load_treeview_sort_state("template_editor_launcher", "template_tree", "name")
    preview_state = {"win": None, "path": None, "after_id": None, "request_id": 0, "photo": None, "pil_image": None}
    def cancel_pending_preview():
        after_id = preview_state.get("after_id")
        preview_state["after_id"] = None
        if after_id is not None:
            try:
                root.after_cancel(after_id)
            except Exception:
                pass
    def close_preview():
        cancel_pending_preview()
        _clear_preview_panel(preview_label, preview_state, empty_text="Select a template to preview")
    def _launcher_is_active():
        try:
            focused = root.focus_displayof()
            return bool(focused) and focused.winfo_toplevel() == root
        except Exception:
            return False
    def _current_preview_path():
        return selected_path()
    def show_preview(path):
        cancel_pending_preview()
        preview_state["request_id"] = int(preview_state.get("request_id", 0)) + 1
        request_id = preview_state["request_id"]
        if not path:
            close_preview()
            return
        def _do_show(_path=path, _request_id=request_id):
            preview_state["after_id"] = None
            if _request_id != preview_state.get("request_id"):
                return
            if _current_preview_path() != _path:
                return
            current_sig = _preview_file_signature_for_json(_path)
            if preview_state.get("path") == _path and preview_state.get("photo") is not None and preview_state.get("preview_file_sig") == current_sig:
                return
            close_preview()
            image, preview_title = open_json_preview(root, _path, template_mode=True)
            if image is None:
                _clear_preview_panel(preview_label, preview_state, empty_text="Select a template to preview")
                return
            _set_preview_panel(preview_label, preview_state, image)
            preview_state["path"] = _path
            preview_state["preview_file_sig"] = current_sig
        preview_state["after_id"] = root.after_idle(_do_show)
    def _on_launcher_focus_in(event=None):
        show_preview(_current_preview_path())
    def _on_launcher_focus_out(event=None):
        def _close_if_really_inactive():
            if _launcher_is_active():
                return
            preview_state["request_id"] = int(preview_state.get("request_id", 0)) + 1
            close_preview()
        root.after_idle(_close_if_really_inactive)

    def sort_rows(rows):
        col = sort_state.get("col")
        if not col:
            return rows

        def keyfunc(r):
            if col == "sections":
                return (int(r.get("section_count") or 0), tuple(r.get("section_pages_sort", (0, 0, 0, 0))), (r.get("name") or "").lower())
            if col == "pages":
                return (tuple(r.get("section_pages_sort", (0, 0, 0, 0))), int(r.get("section_count") or 0), (r.get("name") or "").lower())
            if col == "saved":
                return (r["saved_dt"] or datetime.min, (r.get("name") or "").lower())
            if col == "changed_by":
                return ((r.get("last_changed_by") or "").lower(), (r.get("name") or "").lower())
            return (r["name"] or "").lower()

        return sorted(rows, key=keyfunc, reverse=sort_state["desc"])

    def load_rows(rows):
        tree_state, has_saved_state = get_treeview_reload_state(tree, "template_editor_launcher", "template_tree", columns=("#0", "sections", "pages", "changed_by", "saved"))
        saved_selected = [str(iid) for iid in (tree_state.get("selected_iids") or [])]
        saved_focus = str(tree_state.get("focus_iid") or "").strip() or None
        saved_yview = tree_state.get("yview") if isinstance(tree_state.get("yview"), list) else None
        open_iids = set(str(iid) for iid in (tree_state.get("open_iids") or []))
        tree.delete(*tree.get_children())
        row_by_iid.clear()
        group_by_iid.clear()

        press_order = ["Press 1", "Press 2"]
        format_order = ["Broadsheet", "Tab", "8 up"]
        press_groups = {}
        for row in rows:
            press_name = str(row.get("press") or "").strip() or "Unknown Press"
            format_name = str(row.get("format") or "").strip() or "Unknown Format"
            press_groups.setdefault(press_name, {}).setdefault(format_name, []).append(row)

        def press_sort_key(value):
            return (press_order.index(value), value.lower()) if value in press_order else (len(press_order), value.lower())

        def format_sort_key(value):
            return (format_order.index(value), value.lower()) if value in format_order else (len(format_order), value.lower())

        press_reverse = bool(sort_state.get("col") == "press" and sort_state.get("desc"))
        format_reverse = bool(sort_state.get("col") == "format" and sort_state.get("desc"))

        for press_name in sorted(press_groups.keys(), key=press_sort_key, reverse=press_reverse):
            press_iid = f"__template_press__::{press_name}"
            format_groups = press_groups.get(press_name, {})
            press_count = sum(len(items) for items in format_groups.values())
            press_open = True if not has_saved_state else (press_iid in open_iids)
            tree.insert("", "end", iid=press_iid, text=f"{press_name} ({press_count})", values=("", "", "", "", ""), open=press_open, tags=("group_row",))
            group_by_iid[press_iid] = ("press", press_name)
            for format_name in sorted(format_groups.keys(), key=format_sort_key, reverse=format_reverse):
                format_iid = f"__template_format__::{press_name}::{format_name}"
                format_count = len(format_groups.get(format_name, []))
                format_open = True if not has_saved_state else (format_iid in open_iids)
                tree.insert(press_iid, "end", iid=format_iid, text=f"{format_name} ({format_count})", values=("", "", "", "", ""), open=format_open, tags=("subgroup_row",))
                group_by_iid[format_iid] = ("format", press_name, format_name)
                for row in format_groups.get(format_name, []):
                    iid = row["path"]
                    tree.insert(format_iid, "end", iid=iid, text=row.get("name", ""), values=(row.get("section_count", ""), row.get("pages_disp", ""), row.get("last_changed_by", "Unknown"), row.get("saved_disp", "")))
                    row_by_iid[iid] = row
        known_iids = set(row_by_iid).union(group_by_iid)
        restore_selection = [iid for iid in saved_selected if iid in known_iids]
        for iid in restore_selection:
            open_treeview_item_ancestors(tree, iid)
        if restore_selection:
            tree.selection_set(restore_selection)
        focus_target = saved_focus if saved_focus in known_iids else (restore_selection[0] if restore_selection else None)
        if focus_target:
            open_treeview_item_ancestors(tree, focus_target)
            tree.focus(focus_target)
        if saved_yview and len(saved_yview) > 0:
            try:
                tree.yview_moveto(float(saved_yview[0]))
            except Exception:
                pass

    def _matches_template_filter_no_pages(row):
        search_text = (search_var.get() or "").strip().lower()
        press_filter = (press_var.get() or "All").strip()
        format_filter = (format_var.get() or "All").strip()
        if search_text:
            searchable = " ".join([row.get("name", ""), row.get("press", ""), row.get("format", ""), row.get("pages_disp", ""), row.get("last_changed_by", "")]).lower()
            if search_text not in searchable:
                return False
        if press_filter != "All" and row.get("press", "") != press_filter:
            return False
        if format_filter != "All" and row.get("format", "") != format_filter:
            return False
        return True

    def _matches_template_filter(row):
        if not _matches_template_filter_no_pages(row):
            return False
        pages_filter = (pages_filter_var.get() or "All").strip()
        if pages_filter != "All" and row.get("pages_disp", "") != pages_filter:
            return False
        return True

    def _pages_display_sort_key(value):
        text = str(value or "")
        numbers = []
        for part in re.findall(r"\d+", text):
            try:
                numbers.append(int(part))
            except Exception:
                pass
        return (numbers, text.lower())

    def _update_template_pages_filter_values(rows):
        page_values = sorted({str(row.get("pages_disp") or "").strip() for row in rows if str(row.get("pages_disp") or "").strip()}, key=_pages_display_sort_key)
        values = ["All"] + page_values
        try:
            pages_filter_combo.configure(values=values)
        except Exception:
            pass
        if (pages_filter_var.get() or "All") not in values:
            pages_filter_var.set("All")

    def update_sort_headings():
        tree.heading("#0", text=_treeview_sort_heading_text("Template Name", sort_state, "name"), command=lambda: sort_by("name"))
        tree.heading("sections", text=_treeview_sort_heading_text(template_heading_titles["sections"], sort_state, "sections"), command=lambda: sort_by("sections"))
        tree.heading("pages", text=_treeview_sort_heading_text(template_heading_titles["pages"], sort_state, "pages"), command=lambda: sort_by("pages"))
        tree.heading("changed_by", text=_treeview_sort_heading_text(template_heading_titles["changed_by"], sort_state, "changed_by"), command=lambda: sort_by("changed_by"))
        tree.heading("saved", text=_treeview_sort_heading_text(template_heading_titles["saved"], sort_state, "saved"), command=lambda: sort_by("saved"))

    def refresh():
        template_rows.clear()
        cached_rows, _changed = get_cached_templates(force=False)
        all_rows = []
        for cached in cached_rows:
            row = {
                "path": cached.get("path"),
                "name": cached.get("name") or os.path.splitext(os.path.basename(cached.get("path") or ""))[0],
                "press": cached.get("press") or "",
                "format": cached.get("format") or "",
                "section_count": int(cached.get("section_count") or 0),
                "section_pages_sort": tuple(([int(v) for v in (cached.get("section_pages") or []) if str(v).strip() != "" and int(v) > 0] + [0, 0, 0, 0])[:4]),
                "pages_disp": _format_section_pages_for_display({"section_pages": cached.get("section_pages") or [], "section_count": cached.get("section_count") or 0}),
                "saved_dt": cached.get("saved_dt"),
                "saved_disp": cached.get("saved_disp") or "",
                "last_changed_by": cached.get("last_changed_by") or "Unknown",
            }
            all_rows.append(row)
        _update_template_pages_filter_values([row for row in all_rows if _matches_template_filter_no_pages(row)])
        for row in all_rows:
            if _matches_template_filter(row):
                template_rows.append(row)
        load_rows(sort_rows(list(template_rows)))
        update_sort_headings()

    def sort_by(col):
        if sort_state["col"] == col:
            sort_state["desc"] = not sort_state["desc"]
        else:
            sort_state["col"] = col
            sort_state["desc"] = False
        save_treeview_sort_state("template_editor_launcher", "template_tree", sort_state)
        refresh()

    update_sort_headings()

    def selected_path():
        sel = tree.selection()
        candidate = sel[0] if sel else tree.focus()
        if candidate in row_by_iid:
            return candidate
        focused = tree.focus()
        return focused if focused in row_by_iid else None

    def open_selected():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Template", "Select a template to open.")
            return
        close_preview()
        open_json_in_layout(parent, path, template_mode=True)
        close_preview()
        root.destroy()

    def new_template():
        close_preview()
        open_new_template(parent)
        root.destroy()

    def regenerate_selected_preview():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Template", "Select a template to regenerate its preview.")
            return
        close_preview()
        try:
            regenerate_preview_image_for_json_path(path, template_mode=True, scale=0.75)
            show_preview(path)
        except Exception as exc:
            messagebox.showerror("Regen Preview Failed", str(exc), parent=root)

    def delete_selected():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Template", "Select a template to delete.")
            return
        name = os.path.basename(path)
        if not messagebox.askyesno(
            "Delete Template",
            f"Delete template file?\n\n{name}",
            parent=root,
        ):
            return
        try:
            if preview_state.get("path") == path:
                close_preview()
            remove_preview_image_for_json(path)
            os.remove(path)
        except Exception as exc:
            messagebox.showerror("Delete Template", f"Could not delete template:\n{exc}", parent=root)
            return
        refresh()

    def _on_template_tree_select(event=None):
        show_preview(selected_path())

    def _on_template_tree_double_click(event=None):
        item_id = tree.identify_row(event.y) if event is not None else tree.focus()
        if item_id in group_by_iid:
            try:
                tree.item(item_id, open=(not bool(tree.item(item_id, "open"))))
            except Exception:
                pass
            return "break"
        open_selected()
        return "break"

    tree.bind("<<TreeviewSelect>>", _on_template_tree_select)
    tree.bind("<Double-Button-1>", _on_template_tree_double_click)
    btns = ttk.Frame(frame)
    btns.grid(row=2, column=0, pady=12, sticky="ew")
    btns.columnconfigure(0, weight=1)
    left_btns = ttk.Frame(btns)
    left_btns.grid(row=0, column=0, sticky="w")
    right_btns = ttk.Frame(btns)
    right_btns.grid(row=0, column=1, sticky="e")
    ttk.Button(left_btns, text="New Template", command=new_template, width=14).pack(side="left", padx=(0, 8))
    ttk.Button(left_btns, text="Open Template", command=open_selected, width=14).pack(side="left", padx=(0, 8))
    ttk.Button(left_btns, text="Delete", command=delete_selected, width=10).pack(side="left", padx=(0, 8))
    ttk.Button(right_btns, text="Refresh", command=refresh, width=10).pack(side="right")
    preview_box = ttk.LabelFrame(paned, text="Preview", padding=8)
    preview_box.columnconfigure(0, weight=1)
    preview_label = ttk.Label(preview_box, text="Select a template to preview", anchor="center", justify="center")
    preview_label.grid(row=0, column=0, sticky="nsew")
    preview_box.rowconfigure(0, weight=1)
    preview_label.bind("<Configure>", lambda e: _render_preview_panel_image(preview_label, preview_state), add="+")
    paned.add(preview_box, minsize=160)
    _bind_preview_pane_memory(root, "template_editor_launcher", paned, preview_box, default_height=240)
    refresh()
    def _check_preview_freshness():
        path = preview_state.get("path")
        if not path:
            return
        current_sig = _preview_file_signature_for_json(path)
        if preview_state.get("preview_file_sig") != current_sig:
            preview_state["photo"] = None
            show_preview(path)
    def _on_cache_change():
        refresh()
        _check_preview_freshness()
    template_cache_watcher = _bind_cache_watcher(root, get_cached_templates, _on_cache_change)
    root.bind("<FocusIn>", _on_launcher_focus_in, add="+")
    root.protocol("WM_DELETE_WINDOW", lambda: (_persist_bound_preview_panes(root), _cancel_cache_watcher(root, template_cache_watcher), close_preview(), root.destroy()))
    return root

def _layout_color_and_plate_counts_from_data(data):
    if not isinstance(data, dict):
        return 0, 0

    color_cells = set()
    for item in data.get("color_cells", []):
        if not isinstance(item, dict):
            continue
        try:
            unit = str(item.get("unit") or "")
            r = int(item.get("r"))
            c = int(item.get("c"))
        except Exception:
            continue
        if unit:
            color_cells.add((unit, r, c))

    color_pages = len(color_cells)
    plates = 0

    for unit in data.get("units", []):
        if not isinstance(unit, dict):
            continue
        label = str(unit.get("label") or "")
        grid = unit.get("grid", []) or []
        if not isinstance(grid, list) or not grid:
            continue

        cols_unit = max((len(row) for row in grid if isinstance(row, list)), default=0)
        if cols_unit <= 0:
            continue

        mid_unit = cols_unit // 2
        for side in (0, 1):
            cols_range = range(0, mid_unit) if side == 0 else range(mid_unit, cols_unit)
            has_color = False
            has_pages = False

            for r, row in enumerate(grid):
                row = row if isinstance(row, list) else []
                for c in cols_range:
                    if (label, r, c) in color_cells:
                        has_color = True
                        break
                    value = row[c] if c < len(row) else ""
                    if str(value or "").strip():
                        has_pages = True
                if has_color:
                    break

            if has_color:
                plates += 4
            elif has_pages:
                plates += 1

    return color_pages, plates


def build_regular_editor_launcher(parent):
    root = tk.Toplevel(parent)
    set_window_icon(root)
    root.title("Regular Editor")
    root.geometry("980x720")
    root.minsize(900, 640)
    remember_window_geometry(root, "regular_editor_launcher", default_geometry="980x720", minsize=(900, 640))
    _bind_window_size_memory(root, "regular_editor_launcher")
    allow_launcher_maintenance_actions = is_admin()

    paned = tk.PanedWindow(root, orient="vertical", sashrelief="raised", sashwidth=8, bd=0, showhandle=False)
    paned.pack(fill="both", expand=True)
    frame = ttk.Frame(paned, padding=16)
    paned.add(frame, stretch="always", minsize=220)
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(0, weight=1)

    filter_frame = ttk.Frame(frame)
    filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    filter_frame.columnconfigure(1, weight=1)
    ttk.Label(filter_frame, text="Filter:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")
    search_var = tk.StringVar(value="")
    ttk.Entry(filter_frame, textvariable=search_var).grid(row=0, column=1, sticky="ew", padx=(8, 12))
    ttk.Label(filter_frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=2, sticky="w")
    press_var = tk.StringVar(value="All")
    ttk.Combobox(filter_frame, textvariable=press_var, values=["All", "Press 1", "Press 2"], state="readonly", width=12).grid(row=0, column=3, sticky="w", padx=(8, 12))
    ttk.Label(filter_frame, text="Format:", font=(None, 11, "bold")).grid(row=0, column=4, sticky="w")
    format_var = tk.StringVar(value="All")
    ttk.Combobox(filter_frame, textvariable=format_var, values=["All", "Broadsheet", "Tab", "8 up"], state="readonly", width=12).grid(row=0, column=5, sticky="w")

    list_frame = ttk.Frame(frame)
    list_frame.grid(row=1, column=0, sticky="nsew")
    list_frame.rowconfigure(0, weight=1)
    list_frame.columnconfigure(0, weight=1)
    columns = ("pages", "color_pages", "plates", "changed_by", "saved")
    tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", selectmode="browse")
    tree.grid(row=0, column=0, sticky="nsew")
    vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    vsb.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=vsb.set)
    regular_heading_titles = {
        "pages": "Pages",
        "color_pages": "Color Pages",
        "plates": "Plates",
        "changed_by": "Last Changed By",
        "saved": "Last Saved",
    }
    tree.heading("#0", text="Product")
    for key, title, width, anchor in [("pages", regular_heading_titles["pages"], 120, "center"), ("color_pages", regular_heading_titles["color_pages"], 95, "center"), ("plates", regular_heading_titles["plates"], 70, "center"), ("saved", regular_heading_titles["saved"], 170, "center")]:
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor=anchor)
    tree.column("#0", width=260, anchor="w")
    try:
        tree.tag_configure("group_row", font=(None, 10, "bold"), foreground="#1f1f1f")
        tree.tag_configure("subgroup_row", font=(None, 10, "bold"), foreground="#444444")
    except Exception:
        pass
    apply_treeview_column_width_state(tree, ("#0",) + tuple(columns), "regular_editor_launcher", "regular_tree")
    bind_treeview_state_memory(root, "regular_editor_launcher", "regular_tree", tree, columns=("#0",) + tuple(columns))

    group_by_iid = {}
    sort_state = load_treeview_sort_state("regular_editor_launcher", "regular_tree", "product")
    preview_state = {"win": None, "path": None, "after_id": None, "request_id": 0, "photo": None, "pil_image": None}
    def cancel_pending_preview():
        after_id = preview_state.get("after_id")
        preview_state["after_id"] = None
        if after_id is not None:
            try:
                root.after_cancel(after_id)
            except Exception:
                pass
    def close_preview():
        cancel_pending_preview()
        _clear_preview_panel(preview_label, preview_state, empty_text="Select a regular layout to preview")
    def selected_path():
        sel = tree.selection()
        candidate = sel[0] if sel else tree.focus()
        group_prefixes = ("__regular_press__::", "__regular_format__::")
        if candidate and str(candidate).startswith(group_prefixes):
            candidate = None
        if candidate:
            return candidate
        focused = tree.focus()
        return None if str(focused).startswith(group_prefixes) else focused
    def show_preview(path):
        cancel_pending_preview()
        preview_state["request_id"] = int(preview_state.get("request_id", 0)) + 1
        request_id = preview_state["request_id"]
        if not path:
            close_preview()
            return
        def _do_show(_path=path, _request_id=request_id):
            preview_state["after_id"] = None
            if _request_id != preview_state.get("request_id") or selected_path() != _path:
                return
            current_sig = _preview_file_signature_for_json(_path)
            if preview_state.get("path") == _path and preview_state.get("photo") is not None and preview_state.get("preview_file_sig") == current_sig:
                return
            image, _pt = open_json_preview(root, _path, template_mode=False)
            if image is None:
                close_preview()
                return
            _set_preview_panel(preview_label, preview_state, image)
            preview_state["path"] = _path
            preview_state["preview_file_sig"] = current_sig
        preview_state["after_id"] = root.after_idle(_do_show)
    def sort_rows(rows):
        col = sort_state.get("col")
        if not col:
            return rows
        def keyfunc(r):
            if col == "pages":
                return tuple(r.get("section_pages_sort", (0,0,0,0)))
            if col == "color_pages":
                return int(r.get("color_pages", 0) or 0)
            if col == "plates":
                return int(r.get("plates", 0) or 0)
            if col == "saved":
                return r.get("saved_dt") or datetime.min
            if col == "changed_by":
                return (r.get("last_changed_by") or "").lower()
            return (r.get("product") or "").lower()
        return sorted(rows, key=keyfunc, reverse=sort_state["desc"])
    def matches(row):
        search_text = (search_var.get() or "").strip().lower()
        if search_text:
            hay = " ".join([row.get("product", ""), row.get("press", ""), row.get("format", ""), row.get("pages_disp", ""), str(row.get("color_pages", "")), str(row.get("plates", "")), row.get("last_changed_by", "")]).lower()
            if search_text not in hay:
                return False
        if (press_var.get() or "All") != "All" and row.get("press") != press_var.get():
            return False
        if (format_var.get() or "All") != "All" and row.get("format") != format_var.get():
            return False
        return True
    def update_sort_headings():
        tree.heading("#0", text=_treeview_sort_heading_text("Product", sort_state, "product"), command=lambda: sort_by("product"))
        for col in columns:
            tree.heading(col, text=_treeview_sort_heading_text(regular_heading_titles[col], sort_state, col), command=lambda _c=col: sort_by(_c))

    def refresh():
        tree_state, has_saved_state = get_treeview_reload_state(tree, "regular_editor_launcher", "regular_tree", columns=("#0",) + tuple(columns))
        saved_selected = [str(iid) for iid in (tree_state.get("selected_iids") or [])]
        saved_focus = str(tree_state.get("focus_iid") or "").strip() or None
        saved_yview = tree_state.get("yview") if isinstance(tree_state.get("yview"), list) else None
        open_iids = set(str(iid) for iid in (tree_state.get("open_iids") or []))
        rows, _changed = get_cached_regular_rows(force=False)
        rows = sort_rows([row for row in rows if matches(row)])
        tree.delete(*tree.get_children())
        group_by_iid.clear()

        press_order = ["Press 1", "Press 2"]
        format_order = ["Broadsheet", "Tab", "8 up"]
        press_groups = {}
        for row in rows:
            press_name = str(row.get("press") or "").strip() or "Unknown Press"
            format_name = str(row.get("format") or "").strip() or "Unknown Format"
            press_groups.setdefault(press_name, {}).setdefault(format_name, []).append(row)

        def press_sort_key(value):
            return (press_order.index(value), value.lower()) if value in press_order else (len(press_order), value.lower())

        def format_sort_key(value):
            return (format_order.index(value), value.lower()) if value in format_order else (len(format_order), value.lower())

        press_reverse = bool(sort_state.get("col") == "press" and sort_state.get("desc"))
        format_reverse = bool(sort_state.get("col") == "format" and sort_state.get("desc"))

        for press_name in sorted(press_groups.keys(), key=press_sort_key, reverse=press_reverse):
            press_iid = f"__regular_press__::{press_name}"
            format_groups = press_groups.get(press_name, {})
            press_count = sum(len(items) for items in format_groups.values())
            press_open = True if not has_saved_state else (press_iid in open_iids)
            tree.insert("", "end", iid=press_iid, text=f"{press_name} ({press_count})", values=("", "", "", "", ""), open=press_open, tags=("group_row",))
            group_by_iid[press_iid] = ("press", press_name)
            for format_name in sorted(format_groups.keys(), key=format_sort_key, reverse=format_reverse):
                format_iid = f"__regular_format__::{press_name}::{format_name}"
                format_count = len(format_groups.get(format_name, []))
                format_open = True if not has_saved_state else (format_iid in open_iids)
                tree.insert(press_iid, "end", iid=format_iid, text=f"{format_name} ({format_count})", values=("", "", "", "", ""), open=format_open, tags=("subgroup_row",))
                group_by_iid[format_iid] = ("format", press_name, format_name)
                for row in format_groups.get(format_name, []):
                    tree.insert(format_iid, "end", iid=row["path"], text=row.get("product", ""), values=(row.get("pages_disp", ""), row.get("color_pages", 0), row.get("plates", 0), row.get("last_changed_by", "Unknown"), row.get("saved_disp", "")))
        update_sort_headings()
        known_iids = set(group_by_iid)
        known_iids.update(tree.get_children())
        for parent_iid in tuple(group_by_iid):
            try:
                known_iids.update(tree.get_children(parent_iid))
            except Exception:
                pass
        restore_selection = [iid for iid in saved_selected if iid in known_iids or tree.exists(iid)]
        for iid in restore_selection:
            open_treeview_item_ancestors(tree, iid)
        if restore_selection:
            tree.selection_set(restore_selection)
        focus_target = saved_focus if (saved_focus and tree.exists(saved_focus)) else (restore_selection[0] if restore_selection else None)
        if focus_target:
            open_treeview_item_ancestors(tree, focus_target)
            tree.focus(focus_target)
        if saved_yview and len(saved_yview) > 0:
            try:
                tree.yview_moveto(float(saved_yview[0]))
            except Exception:
                pass
    def sort_by(col):
        if sort_state["col"] == col:
            sort_state["desc"] = not sort_state["desc"]
        else:
            sort_state["col"] = col
            sort_state["desc"] = False
        save_treeview_sort_state("regular_editor_launcher", "regular_tree", sort_state)
        refresh()
    update_sort_headings()
    search_var.trace_add("write", lambda *_: refresh())
    press_var.trace_add("write", lambda *_: refresh())
    format_var.trace_add("write", lambda *_: refresh())
    def open_selected():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Regular Layout", "Select a regular layout to open.")
            return
        close_preview()
        open_json_in_layout(parent, path, template_mode=False, default_dir=REGULAR_DIR, prompt_save_template=False)
        root.destroy()
    def new_regular():
        close_preview()
        open_new_regular(parent)
        root.destroy()
    def regenerate_selected_preview():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Regular Layout", "Select a regular layout to regenerate its preview.")
            return
        try:
            regenerate_preview_image_for_json_path(
                path,
                template_mode=False,
                default_dir=REGULAR_DIR,
                prompt_save_template=False,
                scale=0.75,
            )
            show_preview(path)
        except Exception as exc:
            messagebox.showerror("Regen Preview Failed", str(exc), parent=root)
    def delete_selected():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Regular Layout", "Select a regular layout to delete.")
            return
        name = os.path.basename(path)
        if not messagebox.askyesno("Delete Regular Layout", f"Delete regular layout file? {name}", parent=root):
            return
        try:
            if preview_state.get("path") == path:
                close_preview()
            remove_preview_image_for_json(path)
            os.remove(path)
        except Exception as exc:
            messagebox.showerror("Delete Regular Layout", f"Could not delete regular layout: {exc}", parent=root)
            return
        refresh()
    def _on_regular_tree_select(event=None):
        show_preview(selected_path())

    def _on_regular_tree_double_click(event=None):
        item_id = tree.identify_row(event.y) if event is not None else tree.focus()
        if item_id in group_by_iid:
            try:
                tree.item(item_id, open=(not bool(tree.item(item_id, "open"))))
            except Exception:
                pass
            return "break"
        open_selected()
        return "break"

    tree.bind("<<TreeviewSelect>>", _on_regular_tree_select)
    tree.bind("<Double-Button-1>", _on_regular_tree_double_click)
    btns = ttk.Frame(frame)
    btns.grid(row=2, column=0, pady=12, sticky="ew")
    btns.columnconfigure(0, weight=1)
    left = ttk.Frame(btns)
    left.grid(row=0, column=0, sticky="w")
    right = ttk.Frame(btns)
    right.grid(row=0, column=1, sticky="e")
    ttk.Button(left, text="New Regular", command=new_regular, width=14).pack(side="left", padx=(0, 8))
    ttk.Button(left, text="Open Regular", command=open_selected, width=14).pack(side="left", padx=(0, 8))
    ttk.Button(left, text="Delete", command=delete_selected, width=10).pack(side="left", padx=(0, 8))
    ttk.Button(right, text="Refresh", command=refresh, width=10).pack(side="right")
    preview_box = ttk.LabelFrame(paned, text="Preview", padding=8)
    preview_box.columnconfigure(0, weight=1)
    preview_label = ttk.Label(preview_box, text="Select a regular layout to preview", anchor="center", justify="center")
    preview_label.grid(row=0, column=0, sticky="nsew")
    preview_box.rowconfigure(0, weight=1)
    preview_label.bind("<Configure>", lambda e: _render_preview_panel_image(preview_label, preview_state), add="+")
    paned.add(preview_box, minsize=160)
    _bind_preview_pane_memory(root, "regular_editor_launcher", paned, preview_box, default_height=240)
    refresh()
    def _check_preview_freshness():
        path = preview_state.get("path")
        if not path:
            return
        current_sig = _preview_file_signature_for_json(path)
        if preview_state.get("preview_file_sig") != current_sig:
            preview_state["photo"] = None
            show_preview(path)
    def _on_cache_change():
        refresh()
        _check_preview_freshness()
    regular_cache_watcher = _bind_cache_watcher(root, get_cached_regular_rows, _on_cache_change)
    root.protocol("WM_DELETE_WINDOW", lambda: (_persist_bound_preview_panes(root), _cancel_cache_watcher(root, regular_cache_watcher), close_preview(), root.destroy()))
    return root


CHANGELOG_PATH = SHARED_CHANGELOG_PATH
DEFAULT_CHANGELOG_DATA = {
    "current_version": "1.0.1",
    "versions": [
        {
            "version": "1.0.1",
            "released": "2026-06-12",
            "summary": "Adds launcher version loading from changelog.json and a clickable changelog history view.",
            "changes": [
                {
                    "category": "Added",
                    "items": [
                        "The main launcher now pulls its version number from changelog.json.",
                        "Clicking the version label opens the changelog history dialog."
                    ]
                },
                {
                    "category": "Changed",
                    "items": [
                        "Updated changelog storage to keep multiple versions in one file.",
                        "Added a compact changelog view with collapsible version sections."
                    ]
                }
            ]
        },
        {
            "version": "1.0.0",
            "released": "2026-06-11",
            "summary": "Initial release of the Press Layout launcher.",
            "changes": [
                {
                    "category": "Added",
                    "items": [
                        "Initial consolidated launcher UI for Press Layouts.",
                        "Layout browsing, filtering, and preview support."
                    ]
                }
            ]
        }
    ]
}

CHANGELOG_CATEGORY_COLORS = {
    "added": "#2e7d32",
    "changed": "#1565c0",
    "fixed": "#ef6c00",
    "removed": "#c62828",
    "improved": "#6a1b9a",
    "changes": "#444444",
}

def load_changelog_data():
    data = safe_read_json(CHANGELOG_PATH)
    if isinstance(data, dict):
        return data
    return json.loads(json.dumps(DEFAULT_CHANGELOG_DATA))

def get_changelog_versions(changelog_data=None):
    data = changelog_data if isinstance(changelog_data, dict) else load_changelog_data()
    versions = data.get("versions") if isinstance(data, dict) else None
    if isinstance(versions, list):
        cleaned = [entry for entry in versions if isinstance(entry, dict)]
        if cleaned:
            return cleaned
    if isinstance(data, dict):
        return [{
            "version": data.get("version", DEFAULT_CHANGELOG_DATA["versions"][0]["version"]),
            "released": data.get("released", ""),
            "summary": data.get("summary", ""),
            "changes": data.get("changes", data.get("entries", [])),
        }]
    return json.loads(json.dumps(DEFAULT_CHANGELOG_DATA["versions"]))

def get_current_changelog_entry(changelog_data=None):
    data = changelog_data if isinstance(changelog_data, dict) else load_changelog_data()
    versions = get_changelog_versions(data)
    if not versions:
        return {"version": DEFAULT_CHANGELOG_DATA["versions"][0]["version"]}
    current_version = str(data.get("current_version") or "").strip() if isinstance(data, dict) else ""
    current_compare = current_version[1:] if current_version.lower().startswith("v") else current_version
    if current_compare:
        for entry in versions:
            version_value = str(entry.get("version") or "").strip()
            version_compare = version_value[1:] if version_value.lower().startswith("v") else version_value
            if version_compare == current_compare:
                return entry
    return versions[0]

def get_version_label(changelog_data=None):
    entry = get_current_changelog_entry(changelog_data)
    version = str(entry.get("version") or DEFAULT_CHANGELOG_DATA["versions"][0]["version"]).strip()
    if not version:
        version = DEFAULT_CHANGELOG_DATA["versions"][0]["version"]
    if not version.lower().startswith("v"):
        version = f"v{version}"
    return version

CHANGELOG_CHECK_INTERVAL_MS = 1 * 60 * 1000

def _normalize_version_text(version_value):
    text = str(version_value or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    return text.strip()

def _format_version_label(version_value):
    version_text = _normalize_version_text(version_value)
    return f"v{version_text}" if version_text else "v0.0.0"

def _version_sort_key(version_value):
    normalized = _normalize_version_text(version_value)
    if not normalized:
        return tuple()
    key = []
    for part in re.split(r"([0-9]+)", normalized):
        if not part:
            continue
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return tuple(key)

def _is_version_newer(candidate_version, baseline_version):
    candidate = _normalize_version_text(candidate_version)
    baseline = _normalize_version_text(baseline_version)
    if not candidate or not baseline or candidate == baseline:
        return False
    return _version_sort_key(candidate) > _version_sort_key(baseline)

def _get_changelog_current_version_value(changelog_data=None):
    data = changelog_data if isinstance(changelog_data, dict) else load_changelog_data()
    current_version = _normalize_version_text(data.get("current_version")) if isinstance(data, dict) else ""
    if current_version:
        return current_version
    entry = get_current_changelog_entry(data)
    return _normalize_version_text(entry.get("version"))


LAUNCHER_MANAGED_ENV_VAR = "PRESS_LAYOUTS_MANAGED_BY_LAUNCHER"
LAUNCHER_SHARED_CHANGELOG_ENV_VAR = "PRESS_LAYOUTS_SHARED_CHANGELOG_PATH"
LAUNCHER_RESTART_EXIT_CODE = 42


def _launcher_managed_restart_enabled():
    return str(os.environ.get(LAUNCHER_MANAGED_ENV_VAR, "")).strip() == "1"


def _launcher_restart_available():
    launcher_path = str(_resolve_shared_launcher_executable_path() or "").strip()
    if not launcher_path:
        return False
    try:
        return os.path.exists(launcher_path)
    except Exception:
        return False


def _relaunch_press_layout_from_launcher():
    launcher_path = str(_resolve_shared_launcher_executable_path() or "").strip()
    if not launcher_path:
        raise RuntimeError("The Press Layouts launcher path is not configured.")
    if not os.path.exists(launcher_path):
        raise RuntimeError(f"The Press Layouts launcher was not found at:\n\n{launcher_path}")
    popen_kwargs = {}
    launch_dir = os.path.dirname(launcher_path)
    if launch_dir:
        popen_kwargs["cwd"] = launch_dir
    if os.name == "nt":
        creationflags = 0
        creationflags |= int(getattr(subprocess, "DETACHED_PROCESS", 0) or 0)
        creationflags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) or 0)
        if creationflags:
            popen_kwargs["creationflags"] = creationflags
    subprocess.Popen([launcher_path], **popen_kwargs)
    return launcher_path


def _shutdown_root_for_restart(root=None):
    if root is None:
        return
    try:
        _persist_bound_preview_panes(root)
    except Exception:
        pass
    try:
        root.update_idletasks()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass


def restart_press_layout_program(root=None):
    """
    Restart Press Layouts by relaunching the shared launcher when it is available.

    This keeps update-driven restarts and database-restore restarts on the same
    launcher-managed path, so the latest shared build is reopened instead of
    relying only on an exit code or asking the user to launch it manually.
    """
    restart_error = None
    try:
        _relaunch_press_layout_from_launcher()
    except Exception as exc:
        restart_error = exc
    else:
        _shutdown_root_for_restart(root)
        return True

    if _launcher_managed_restart_enabled():
        _shutdown_root_for_restart(root)
        raise SystemExit(LAUNCHER_RESTART_EXIT_CODE)

    raise RuntimeError(f"Could not relaunch Press Layouts from the launcher.\n\n{restart_error}")

def show_restart_required_dialog(parent, running_version, latest_version):
    force_restart_seconds = 10 * 60

    def _raise_restart_dialog(target_dialog, force_focus=False):
        if target_dialog is None:
            return
        try:
            if not target_dialog.winfo_exists():
                return
        except Exception:
            return
        try:
            target_dialog.deiconify()
        except Exception:
            pass
        try:
            target_dialog.attributes("-topmost", True)
        except Exception:
            pass
        try:
            target_dialog.lift()
        except Exception:
            pass
        if force_focus:
            try:
                target_dialog.focus_force()
            except Exception:
                pass

    existing = getattr(parent, "_restart_required_dialog", None)
    try:
        if existing is not None and existing.winfo_exists():
            _raise_restart_dialog(existing, force_focus=True)
            return existing
    except Exception:
        pass

    dialog = tk.Toplevel()
    set_window_icon(dialog)
    parent._restart_required_dialog = dialog
    dialog.title("Update Available")
    dialog.attributes("-topmost", True)
    try:
        dialog.grab_set()
    except Exception:
        pass
    dialog.resizable(False, False)
    remember_window_geometry(dialog, "restart_required_dialog", default_geometry="520x270", minsize=(520, 270))

    body = ttk.Frame(dialog, padding=16)
    body.pack(fill="both", expand=True)
    body.columnconfigure(0, weight=1)

    ttk.Label(body, text="A newer version of Press Layouts is available.", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")
    restart_cta = (
        "Please save your work and choose Restart to relaunch Press Layouts from the launcher."
        if (_launcher_restart_available() or _launcher_managed_restart_enabled())
        else "Please save your work and close Press Layouts. Reopen it from the launcher to load the latest version."
    )
    message = (
        f"You are using {_format_version_label(running_version)}, but {_format_version_label(latest_version)} is now available.\n\n"
        f"{restart_cta}"
    )
    ttk.Label(body, text=message, justify="left", wraplength=460).grid(row=1, column=0, sticky="w", pady=(10, 0))

    countdown_var = tk.StringVar(value="")
    countdown_label = ttk.Label(body, textvariable=countdown_var, justify="left", wraplength=460, foreground="#c62828")
    countdown_label.grid(row=2, column=0, sticky="w", pady=(12, 0))

    button_row = ttk.Frame(body)
    button_row.grid(row=3, column=0, sticky="e", pady=(18, 0))

    timer_state = {
        "after_id": None,
        "remaining": force_restart_seconds,
        "acknowledged": False,
        "restart_started": False,
    }

    def _format_countdown(seconds_remaining):
        try:
            total_seconds = max(0, int(seconds_remaining))
        except Exception:
            total_seconds = 0
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes}:{seconds:02d}"

    def _set_button_state(state):
        for button in (restart_button, cancel_button):
            try:
                button.configure(state=state)
            except Exception:
                pass

    def _cancel_restart_timer():
        after_id = timer_state.get("after_id")
        timer_state["after_id"] = None
        if after_id is not None:
            try:
                dialog.after_cancel(after_id)
            except Exception:
                pass

    def _close_dialog():
        timer_state["acknowledged"] = True
        _cancel_restart_timer()
        try:
            dialog.attributes("-topmost", False)
        except Exception:
            pass
        try:
            dialog.grab_release()
        except Exception:
            pass
        try:
            dialog.destroy()
        except Exception:
            pass
        if getattr(parent, "_restart_required_dialog", None) is dialog:
            parent._restart_required_dialog = None

    def _restart_now():
        if timer_state.get("restart_started"):
            return
        timer_state["acknowledged"] = True
        timer_state["restart_started"] = True
        _cancel_restart_timer()
        _close_dialog()
        try:
            restart_press_layout_program(parent)
        except Exception as exc:
            messagebox.showerror("Restart Failed", f"Could not restart Press Layouts.\n\n{exc}")

    def _force_restart_now():
        if timer_state.get("acknowledged") or timer_state.get("restart_started"):
            return
        timer_state["restart_started"] = True
        _cancel_restart_timer()
        countdown_var.set("Restarting Press Layouts now...")
        _set_button_state("disabled")
        try:
            dialog.update_idletasks()
        except Exception:
            pass
        try:
            restart_press_layout_program(parent)
        except Exception as exc:
            timer_state["restart_started"] = False
            countdown_var.set("Automatic restart failed. Please restart Press Layouts manually.")
            _set_button_state("normal")
            messagebox.showerror("Restart Failed", f"Could not restart Press Layouts.\n\n{exc}")

    def _countdown_tick():
        timer_state["after_id"] = None
        if timer_state.get("acknowledged") or timer_state.get("restart_started"):
            return
        try:
            if not dialog.winfo_exists():
                return
        except Exception:
            return
        remaining = max(0, int(timer_state.get("remaining", 0)))
        countdown_var.set(
            "If this dialog is not acknowledged, Press Layouts will restart automatically in "
            f"{_format_countdown(remaining)}."
        )
        if remaining <= 0:
            _force_restart_now()
            return
        timer_state["remaining"] = remaining - 1
        try:
            timer_state["after_id"] = dialog.after(1000, _countdown_tick)
        except Exception:
            timer_state["after_id"] = None

    restart_button_text = "Restart" if (_launcher_restart_available() or _launcher_managed_restart_enabled()) else "Close"
    restart_button = ttk.Button(button_row, text=restart_button_text, command=_restart_now, width=12)
    restart_button.pack(side="left", padx=(0, 8))
    cancel_button = ttk.Button(button_row, text="Cancel", command=_close_dialog, width=12)
    cancel_button.pack(side="left")

    dialog.protocol("WM_DELETE_WINDOW", _close_dialog)
    dialog.bind("<Escape>", lambda _event: _close_dialog())
    dialog.bind("<Map>", lambda _event: dialog.after_idle(lambda: _raise_restart_dialog(dialog, force_focus=False)), add="+")
    dialog.bind("<Visibility>", lambda _event: dialog.after_idle(lambda: _raise_restart_dialog(dialog, force_focus=False)), add="+")
    _countdown_tick()
    _raise_restart_dialog(dialog, force_focus=True)
    return dialog
def check_for_required_restart(parent, running_version):
    latest_version = _get_changelog_current_version_value()
    if _is_version_newer(latest_version, running_version):
        show_restart_required_dialog(parent, running_version, latest_version)
        return True, latest_version
    return False, latest_version

def _normalize_change_sections(entry):
    sections = entry.get("changes") if isinstance(entry, dict) else None
    if not isinstance(sections, list) or not sections:
        sections = entry.get("entries") if isinstance(entry, dict) else None
    if not isinstance(sections, list):
        return []
    normalized = []
    for section in sections:
        if isinstance(section, dict):
            title = str(section.get("category") or section.get("title") or "Changes").strip() or "Changes"
            items = section.get("items") if isinstance(section.get("items"), list) else None
            if items is None:
                details = str(section.get("details") or "").strip()
                items = [details] if details else []
            normalized.append({"title": title, "items": [str(item).strip() for item in items if str(item).strip()]})
        else:
            item_text = str(section).strip()
            if item_text:
                normalized.append({"title": "Changes", "items": [item_text]})
    return normalized

def _category_tag_name(title):
    slug = re.sub(r"[^a-z0-9]+", "_", str(title or "").lower()).strip("_")
    return f"category_{slug or "changes"}"

def _item_tag_name(title):
    slug = re.sub(r"[^a-z0-9]+", "_", str(title or "").lower()).strip("_")
    return f"item_{slug or "changes"}"

def _category_color(title):
    key = re.sub(r"[^a-z0-9]+", "", str(title or "").lower())
    return CHANGELOG_CATEGORY_COLORS.get(key, "#444444")

def _configure_changelog_tree_tags(tree):
    tree.tag_configure("version", font=(None, 10, "bold"))
    tree.tag_configure("summary", foreground="#333333")
    tree.tag_configure("item", foreground="#222222")
    for category_name in ["Added", "Changed", "Fixed", "Removed", "Improved", "Changes"]:
        color = _category_color(category_name)
        tree.tag_configure(_category_tag_name(category_name), foreground=color, font=(None, 10, "bold"))
        tree.tag_configure(_item_tag_name(category_name), foreground=color)

def show_changelog_dialog(parent):
    existing = getattr(parent, "_changelog_dialog", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return existing
    except Exception:
        pass

    changelog_data = load_changelog_data()
    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    parent._changelog_dialog = dialog
    dialog.title(f"Changelog - {get_version_label(changelog_data)}")
    try:
        dialog.transient(parent)
    except Exception:
        pass
    dialog.geometry("760x560")
    dialog.minsize(620, 420)
    remember_window_geometry(dialog, "changelog_dialog", default_geometry="760x560", minsize=(620, 420))
    _bind_window_size_memory(dialog, "changelog_dialog")

    outer = ttk.Frame(dialog, padding=12)
    outer.pack(fill="both", expand=True)
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(1, weight=1)

    header = ttk.Frame(outer)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)
    ttk.Label(header, text=f"Press Layouts {get_version_label(changelog_data)}", font=(None, 12, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(header, text="Expand or collapse each version to scan the history quickly.", foreground="#555555").grid(row=1, column=0, sticky="w", pady=(4, 0))

    body_frame = ttk.Frame(outer)
    body_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 10))
    body_frame.columnconfigure(0, weight=1)
    body_frame.rowconfigure(0, weight=1)

    canvas = tk.Canvas(body_frame, highlightthickness=0, borderwidth=0)
    canvas.grid(row=0, column=0, sticky="nsew")
    vsb = ttk.Scrollbar(body_frame, orient="vertical", command=canvas.yview)
    vsb.grid(row=0, column=1, sticky="ns")
    canvas.configure(yscrollcommand=vsb.set)

    content = ttk.Frame(canvas)
    content.columnconfigure(0, weight=1)
    canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")

    version_widgets = {}
    versions = get_changelog_versions(changelog_data)

    def _version_key(entry, index):
        version_label = str(entry.get("version") or "").strip() or "0.0.0"
        if not version_label.lower().startswith("v"):
            version_label = f"v{version_label}"
        released = str(entry.get("released") or "").strip()
        return f"{version_label}|{released}|{index}"

    version_states = {
        _version_key(entry, index): (index == 0)
        for index, entry in enumerate(versions)
    }

    def _current_wraplength():
        try:
            width = int(canvas.winfo_width())
        except Exception:
            width = 0
        return max(280, width - 60 if width > 0 else 700)

    def _apply_version_state(version_key):
        info = version_widgets.get(version_key)
        if not info:
            return
        is_open = bool(version_states.get(version_key, False))
        arrow = "▾" if is_open else "▸"
        info["button"].configure(text=f"{arrow}  {info['title']}")
        if is_open:
            info["body"].grid()
        else:
            info["body"].grid_remove()

    def _toggle_version(version_key):
        version_states[version_key] = not bool(version_states.get(version_key, False))
        _apply_version_state(version_key)
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass

    def _set_all_versions(open_state):
        for version_key in list(version_widgets.keys()):
            version_states[version_key] = bool(open_state)
            _apply_version_state(version_key)
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass

    def _add_wrapped_label(parent_frame, text, row_index, *, foreground="#222222", font=None, indent=0, pady=(0, 2)):
        lbl = ttk.Label(
            parent_frame,
            text=text,
            foreground=foreground,
            font=font,
            justify="left",
            anchor="w",
            wraplength=_current_wraplength(),
        )
        lbl.grid(row=row_index, column=0, sticky="ew", padx=(indent, 0), pady=pady)
        return lbl

    if not versions:
        ttk.Label(content, text="No changelog entries found.", foreground="#333333", justify="left", anchor="w", wraplength=700).grid(row=0, column=0, sticky="ew")
    else:
        for index, entry in enumerate(versions):
            version_label = str(entry.get("version") or "").strip() or "0.0.0"
            if not version_label.lower().startswith("v"):
                version_label = f"v{version_label}"
            released = str(entry.get("released") or "").strip()
            title_text = f"Press Layouts {version_label}"
            if released:
                title_text += f"  •  {released}"
            version_key = _version_key(entry, index)

            card = ttk.Frame(content, padding=(0, 0, 0, 10))
            card.grid(row=index, column=0, sticky="ew")
            card.columnconfigure(0, weight=1)

            header_button = ttk.Button(card, text=title_text, command=(lambda key=version_key: _toggle_version(key)))
            header_button.grid(row=0, column=0, sticky="ew")

            details = ttk.Frame(card, padding=(24, 8, 0, 0))
            details.grid(row=1, column=0, sticky="ew")
            details.columnconfigure(0, weight=1)

            wrap_labels = []
            next_row = 0
            summary = str(entry.get("summary") or "").strip()
            if summary:
                wrap_labels.append(_add_wrapped_label(details, summary, next_row, foreground="#333333", pady=(0, 8)))
                next_row += 1

            for section in _normalize_change_sections(entry):
                title = section.get("title") or "Changes"
                items = section.get("items") or []
                color = _category_color(title)
                section_label = ttk.Label(details, text=title, foreground=color, font=(None, 10, "bold"), justify="left", anchor="w")
                section_label.grid(row=next_row, column=0, sticky="ew", pady=(0, 4))
                next_row += 1
                for item in items:
                    wrap_labels.append(_add_wrapped_label(details, f"• {item}", next_row, indent=0, pady=(0, 2)))
                    next_row += 1

            version_widgets[version_key] = {
                "button": header_button,
                "body": details,
                "title": title_text,
                "wrap_labels": wrap_labels,
            }
            _apply_version_state(version_key)

    def _update_wrap_lengths(_event=None):
        wraplength = _current_wraplength()
        try:
            canvas.itemconfigure(canvas_window, width=max(1, canvas.winfo_width()))
        except Exception:
            pass
        for info in version_widgets.values():
            for lbl in info.get("wrap_labels", []):
                try:
                    lbl.configure(wraplength=wraplength)
                except Exception:
                    pass
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass

    def _on_mousewheel(event):
        try:
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"
        except Exception:
            pass
        return None

    def _cleanup_dialog():
        try:
            if getattr(parent, "_changelog_dialog", None) is dialog:
                parent._changelog_dialog = None
        except Exception:
            pass
        try:
            dialog.destroy()
        except Exception:
            pass

    content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", _update_wrap_lengths)
    canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")
    _update_wrap_lengths()

    button_row = ttk.Frame(outer)
    button_row.grid(row=2, column=0, sticky="e")
    ttk.Button(button_row, text="Expand All", command=lambda: _set_all_versions(True)).pack(side="left", padx=(0, 8))
    ttk.Button(button_row, text="Collapse All", command=lambda: _set_all_versions(False)).pack(side="left", padx=(0, 8))
    ttk.Button(button_row, text="Close", command=_cleanup_dialog, width=10).pack(side="right")

    dialog.bind("<Escape>", lambda _event: _cleanup_dialog())
    dialog.protocol("WM_DELETE_WINDOW", _cleanup_dialog)
    try:
        dialog.focus_set()
    except Exception:
        pass
    return dialog





def _launcher_user_can_open_macros(username):
    return str(username or '').strip().lower() in {'jsaalsaa', 'mbradbury'}

SUNDAY_SINGLE_REGULAR_MONTHLY_MACROS = {
    'aug_comics_monthly': {
        'title': 'AUG COMICS Monthly',
        'regular_name': 'AUG COMICS',
        'state_prefix': 'aug_comics_monthly',
    },
    'gre_comics_monthly': {
        'title': 'GRE COMICS Monthly',
        'regular_name': 'GRE COMICS',
        'state_prefix': 'gre_comics_monthly',
    },
    'ral_comics_monthly': {
        'title': 'RAL COMICS Monthly',
        'regular_name': 'RAL COMICS',
        'state_prefix': 'ral_comics_monthly',
    },
    'usat_co_comics_monthly': {
        'title': 'USAT CO COMICS Monthly',
        'regular_name': 'USAT CO COMICS',
        'state_prefix': 'usat_co_comics_monthly',
    },
}


def _show_month_year_picker(parent, initial_year=None, initial_month=None, title="Select Month / Year"):
    now = datetime.now()
    try:
        initial_year = int(initial_year if initial_year is not None else now.year)
    except Exception:
        initial_year = now.year
    try:
        initial_month = int(initial_month if initial_month is not None else now.month)
    except Exception:
        initial_month = now.month
    initial_month = max(1, min(12, initial_month))

    result = {"value": None}
    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title(title)
    try:
        dialog.transient(parent)
    except Exception:
        pass
    dialog.resizable(False, False)
    remember_window_geometry(dialog, "macro_month_year_picker", default_geometry="320x150", minsize=(320, 150))

    outer = ttk.Frame(dialog, padding=12)
    outer.grid(row=0, column=0, sticky="nsew")
    outer.columnconfigure(1, weight=1)

    ttk.Label(outer, text="Month:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
    month_names = [calendar.month_name[i] for i in range(1, 13)]
    month_var = tk.StringVar(value=month_names[initial_month - 1])
    month_combo = ttk.Combobox(outer, textvariable=month_var, values=month_names, state="readonly", width=16)
    month_combo.grid(row=0, column=1, sticky="ew", pady=(0, 8))

    ttk.Label(outer, text="Year:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
    year_var = tk.StringVar(value=str(initial_year))
    year_spin = tk.Spinbox(outer, from_=2000, to=2100, textvariable=year_var, width=10)
    year_spin.grid(row=1, column=1, sticky="w", pady=(0, 8))

    button_row = ttk.Frame(outer)
    button_row.grid(row=2, column=0, columnspan=2, sticky="e", pady=(6, 0))

    def close_dialog(value=None):
        result["value"] = value
        try:
            dialog.destroy()
        except Exception:
            pass

    def confirm():
        try:
            picked_year = int(str(year_var.get() or '').strip())
        except Exception:
            messagebox.showerror("Invalid Year", "Please enter a valid 4-digit year.", parent=dialog)
            return
        picked_month_name = str(month_var.get() or '').strip()
        if picked_month_name not in month_names:
            messagebox.showerror("Invalid Month", "Please select a month.", parent=dialog)
            return
        close_dialog((picked_year, month_names.index(picked_month_name) + 1))

    ttk.Button(button_row, text="Cancel", command=lambda: close_dialog(None), width=10).pack(side="right")
    ttk.Button(button_row, text="OK", command=confirm, width=10).pack(side="right", padx=(0, 8))

    dialog.bind("<Return>", lambda _event: confirm())
    dialog.bind("<Escape>", lambda _event: close_dialog(None))
    dialog.protocol("WM_DELETE_WINDOW", lambda: close_dialog(None))
    dialog.grab_set()
    try:
        month_combo.focus_set()
    except Exception:
        pass
    parent.wait_window(dialog)
    return result["value"]


def _macro_normalize_match_text(value):
    return re.sub(r'\s+', ' ', normalize_publication_name(value or '')).strip()


def _find_macro_regular_source(target_name):
    target = _macro_normalize_match_text(target_name)
    rows, _changed = get_cached_regular_rows(force=False)
    product_matches = [row for row in rows if _macro_normalize_match_text(row.get('product')) == target]
    name_matches = [row for row in rows if _macro_normalize_match_text(row.get('name')) == target]
    if len(product_matches) == 1:
        return product_matches[0], None
    if len(product_matches) > 1:
        items = [os.path.basename(str(row.get('path') or '')) for row in product_matches]
        return None, f"Multiple regulars matched {target_name}: {', '.join(items)}"
    if len(name_matches) == 1:
        return name_matches[0], None
    if len(name_matches) > 1:
        items = [os.path.basename(str(row.get('path') or '')) for row in name_matches]
        return None, f"Multiple regulars matched {target_name}: {', '.join(items)}"
    return None, f"Could not find a regular named {target_name}."


def _build_usat_month_issue_plan(year, month):
    plan = []
    try:
        year = int(year)
        month = int(month)
        _first_weekday, last_day = calendar.monthrange(year, month)
    except Exception:
        return plan
    monday_thursday_names = ["USAT A&B", "USAT C&D"]
    friday_names = ["USAT A&D", "USAT B&C"]
    for day in range(1, last_day + 1):
        current_dt = datetime(year, month, day)
        weekday = current_dt.weekday()
        if weekday >= 5:
            continue
        macro_names = friday_names if weekday == 4 else monday_thursday_names
        plan.append({
            'date': current_dt.strftime('%m/%d/%Y'),
            'weekday': weekday,
            'regular_names': list(macro_names),
        })
    return plan


def _build_gre_homefinder_month_issue_plan(year, month):
    plan = []
    try:
        year = int(year)
        month = int(month)
        _first_weekday, last_day = calendar.monthrange(year, month)
    except Exception:
        return plan
    sunday_names = ["GRE Homefinder"]
    for day in range(1, last_day + 1):
        current_dt = datetime(year, month, day)
        weekday = current_dt.weekday()
        if weekday != 6:
            continue
        plan.append({
            'date': current_dt.strftime('%m/%d/%Y'),
            'weekday': weekday,
            'regular_names': list(sunday_names),
        })
    return plan



def _build_single_regular_sunday_month_issue_plan(year, month, regular_name):
    plan = []
    try:
        year = int(year)
        month = int(month)
        _first_weekday, last_day = calendar.monthrange(year, month)
    except Exception:
        return plan
    sunday_names = [str(regular_name or '').strip()]
    sunday_names = [name for name in sunday_names if name]
    for day in range(1, last_day + 1):
        current_dt = datetime(year, month, day)
        weekday = current_dt.weekday()
        if weekday != 6:
            continue
        plan.append({
            'date': current_dt.strftime('%m/%d/%Y'),
            'weekday': weekday,
            'regular_names': list(sunday_names),
        })
    return plan

def _macro_target_layout_exists(target_path):
    try:
        return safe_read_json(target_path) is not None
    except Exception:
        pass
    try:
        return os.path.exists(target_path)
    except Exception:
        return False


def _resolve_usat_monthly_generation_plan(year, month):
    required_regulars = ["USAT A&B", "USAT C&D", "USAT A&D", "USAT B&C"]
    source_bundle = {}
    errors = []
    for regular_name in required_regulars:
        row, error_text = _find_macro_regular_source(regular_name)
        if row is None:
            errors.append(error_text)
            continue
        source_data = safe_read_json(row.get('path'))
        if not isinstance(source_data, dict):
            errors.append(f"Could not read the regular layout for {regular_name}.")
            continue
        source_bundle[regular_name] = {
            'row': row,
            'data': source_data,
        }

    month_issue_plan = _build_usat_month_issue_plan(year, month)
    if not month_issue_plan:
        errors.append("No weekday issues were found for that month.")
        return [], errors

    generation_plan = []
    for issue in month_issue_plan:
        issue_date = issue['date']
        for regular_name in issue['regular_names']:
            bundle = source_bundle.get(regular_name)
            if not isinstance(bundle, dict):
                continue
            source_data = json.loads(json.dumps(bundle.get('data') or {}, default=str))
            for transient_key in ('_db_record_id', '_db_record_type', '_file_path', '_layout_name'):
                source_data.pop(transient_key, None)
            source_data['issue_date'] = issue_date
            press_name = source_data.get('press') or ''
            format_name = source_data.get('format') or ''
            cfg = CONFIG_MAP.get((press_name, format_name))
            file_name = _build_filename_suggestion_from_layout_data(
                source_data,
                template_mode=False,
                regular_mode=False,
                default_dir=LAYOUTS_DIR,
                config=(dict(cfg) if isinstance(cfg, dict) else None),
            )
            file_name = str(file_name or '').strip() or f"{sanitize_filename(regular_name)} {issue_date.replace('/', '-')}.json"
            if not file_name.lower().endswith('.json'):
                file_name += '.json'
            target_path = os.path.join(LAYOUTS_DIR, file_name)
            generation_plan.append({
                'issue_date': issue_date,
                'weekday': issue.get('weekday'),
                'regular_name': regular_name,
                'source_path': bundle['row'].get('path'),
                'source_data': source_data,
                'target_path': target_path,
                'target_name': os.path.basename(file_name),
                'exists': _macro_target_layout_exists(target_path),
            })
    return generation_plan, errors


def _resolve_gre_homefinder_monthly_generation_plan(year, month):
    required_regulars = ["GRE Homefinder"]
    source_bundle = {}
    errors = []
    for regular_name in required_regulars:
        row, error_text = _find_macro_regular_source(regular_name)
        if row is None:
            errors.append(error_text)
            continue
        source_data = safe_read_json(row.get('path'))
        if not isinstance(source_data, dict):
            errors.append(f"Could not read the regular layout for {regular_name}.")
            continue
        source_bundle[regular_name] = {
            'row': row,
            'data': source_data,
        }

    month_issue_plan = _build_gre_homefinder_month_issue_plan(year, month)
    if not month_issue_plan:
        errors.append("No Sunday issues were found for that month.")
        return [], errors

    generation_plan = []
    for issue in month_issue_plan:
        issue_date = issue['date']
        for regular_name in issue['regular_names']:
            bundle = source_bundle.get(regular_name)
            if not isinstance(bundle, dict):
                continue
            source_data = json.loads(json.dumps(bundle.get('data') or {}, default=str))
            for transient_key in ('_db_record_id', '_db_record_type', '_file_path', '_layout_name'):
                source_data.pop(transient_key, None)
            source_data['issue_date'] = issue_date
            press_name = source_data.get('press') or ''
            format_name = source_data.get('format') or ''
            cfg = CONFIG_MAP.get((press_name, format_name))
            file_name = _build_filename_suggestion_from_layout_data(
                source_data,
                template_mode=False,
                regular_mode=False,
                default_dir=LAYOUTS_DIR,
                config=(dict(cfg) if isinstance(cfg, dict) else None),
            )
            file_name = str(file_name or '').strip() or f"{sanitize_filename(regular_name)} {issue_date.replace('/', '-')}.json"
            if not file_name.lower().endswith('.json'):
                file_name += '.json'
            target_path = os.path.join(LAYOUTS_DIR, file_name)
            generation_plan.append({
                'issue_date': issue_date,
                'weekday': issue.get('weekday'),
                'regular_name': regular_name,
                'source_path': bundle['row'].get('path'),
                'source_data': source_data,
                'target_path': target_path,
                'target_name': os.path.basename(file_name),
                'exists': _macro_target_layout_exists(target_path),
            })
    return generation_plan, errors



def _resolve_single_regular_sunday_monthly_generation_plan(year, month, regular_name):
    regular_name = str(regular_name or '').strip()
    if not regular_name:
        return [], ['No regular name was provided for this macro.']
    required_regulars = [regular_name]
    source_bundle = {}
    errors = []
    for regular_name in required_regulars:
        row, error_text = _find_macro_regular_source(regular_name)
        if row is None:
            errors.append(error_text)
            continue
        source_data = safe_read_json(row.get('path'))
        if not isinstance(source_data, dict):
            errors.append(f"Could not read the regular layout for {regular_name}.")
            continue
        source_bundle[regular_name] = {
            'row': row,
            'data': source_data,
        }

    month_issue_plan = _build_single_regular_sunday_month_issue_plan(year, month, regular_name)
    if not month_issue_plan:
        errors.append('No Sunday issues were found for that month.')
        return [], errors

    generation_plan = []
    for issue in month_issue_plan:
        issue_date = issue['date']
        for regular_name in issue['regular_names']:
            bundle = source_bundle.get(regular_name)
            if not isinstance(bundle, dict):
                continue
            source_data = json.loads(json.dumps(bundle.get('data') or {}, default=str))
            for transient_key in ('_db_record_id', '_db_record_type', '_file_path', '_layout_name'):
                source_data.pop(transient_key, None)
            source_data['issue_date'] = issue_date
            press_name = source_data.get('press') or ''
            format_name = source_data.get('format') or ''
            cfg = CONFIG_MAP.get((press_name, format_name))
            file_name = _build_filename_suggestion_from_layout_data(
                source_data,
                template_mode=False,
                regular_mode=False,
                default_dir=LAYOUTS_DIR,
                config=(dict(cfg) if isinstance(cfg, dict) else None),
            )
            file_name = str(file_name or '').strip() or f"{sanitize_filename(regular_name)} {issue_date.replace('/', '-')}.json"
            if not file_name.lower().endswith('.json'):
                file_name += '.json'
            target_path = os.path.join(LAYOUTS_DIR, file_name)
            generation_plan.append({
                'issue_date': issue_date,
                'weekday': issue.get('weekday'),
                'regular_name': regular_name,
                'source_path': bundle['row'].get('path'),
                'source_data': source_data,
                'target_path': target_path,
                'target_name': os.path.basename(file_name),
                'exists': _macro_target_layout_exists(target_path),
            })
    return generation_plan, errors

def _ensure_dialog_fits_contents(dialog, min_width=0, min_height=0, extra_width=0, extra_height=0):
    if dialog is None:
        return
    try:
        dialog.update_idletasks()
    except Exception:
        return
    try:
        req_width = int(dialog.winfo_reqwidth()) + int(extra_width or 0)
    except Exception:
        req_width = int(min_width or 0)
    try:
        req_height = int(dialog.winfo_reqheight()) + int(extra_height or 0)
    except Exception:
        req_height = int(min_height or 0)
    req_width = max(int(min_width or 0), req_width)
    req_height = max(int(min_height or 0), req_height)
    try:
        dialog.minsize(req_width, req_height)
    except Exception:
        pass
    try:
        cur_width = int(dialog.winfo_width())
        cur_height = int(dialog.winfo_height())
    except Exception:
        cur_width = 0
        cur_height = 0
    if cur_width >= req_width and cur_height >= req_height:
        return
    new_width = max(cur_width, req_width)
    new_height = max(cur_height, req_height)
    try:
        x = int(dialog.winfo_x())
        y = int(dialog.winfo_y())
        dialog.geometry(f"{new_width}x{new_height}{x:+d}{y:+d}")
    except Exception:
        try:
            dialog.geometry(f"{new_width}x{new_height}")
        except Exception:
            pass
    try:
        dialog.update_idletasks()
    except Exception:
        pass

def _show_usat_monthly_confirmation(parent, year, month, generation_plan):
    result = {'confirmed': False, 'overwrite_mode': 'skip', 'print_layouts': False, 'print_starter_sheets': False}
    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title("Confirm USAT Monthly")
    try:
        dialog.transient(parent)
    except Exception:
        pass
    dialog.resizable(False, False)
    remember_window_geometry(dialog, "usat_monthly_confirmation_dialog", default_geometry="520x430", minsize=(520, 430))

    total_layouts = len(generation_plan)
    unique_dates = sorted({str(item.get('issue_date') or '') for item in generation_plan if item.get('issue_date')})
    friday_dates = sorted({str(item.get('issue_date') or '') for item in generation_plan if int(item.get('weekday', -1)) == 4})
    friday_count = len(friday_dates)
    monday_thursday_count = max(0, len(unique_dates) - friday_count)
    existing_count = sum(1 for item in generation_plan if item.get('exists'))
    new_count = max(0, total_layouts - existing_count)

    outer = ttk.Frame(dialog, padding=12)
    outer.grid(row=0, column=0, sticky="nsew")
    outer.columnconfigure(0, weight=1)

    month_name = calendar.month_name[int(month)]
    summary_lines = [
        f"Month / Year: {month_name} {int(year)}",
        f"Issue dates to generate: {len(unique_dates)}",
        f"Layouts to process: {total_layouts}",
        f"  • Monday-Thursday issues: {monday_thursday_count} date(s) using USAT A&B and USAT C&D",
        f"  • Friday issues: {friday_count} date(s) using USAT A&D and USAT B&C",
        f"Existing target layouts found: {existing_count}",
        f"New target layouts: {new_count}",
    ]
    if unique_dates:
        summary_lines.append(f"Date range: {unique_dates[0]} to {unique_dates[-1]}")

    ttk.Label(outer, text="Please review the macro summary before continuing.", font=(None, 11, "bold")).grid(row=0, column=0, sticky='w')
    ttk.Label(outer, text="\n".join(summary_lines), justify='left').grid(row=1, column=0, sticky='w', pady=(8, 10))

    options_frame = ttk.LabelFrame(outer, text="If a target layout already exists")
    options_frame.grid(row=2, column=0, sticky='ew', pady=(0, 10))
    overwrite_var = tk.StringVar(value='skip')
    ttk.Radiobutton(options_frame, text="Skip existing layouts", value='skip', variable=overwrite_var).pack(anchor='w', padx=10, pady=(8, 4))
    ttk.Radiobutton(options_frame, text="Overwrite existing layouts", value='overwrite', variable=overwrite_var).pack(anchor='w', padx=10, pady=(0, 8))

    print_layouts_var = tk.BooleanVar(value=False)
    print_starters_var = tk.BooleanVar(value=False)
    print_frame = ttk.LabelFrame(outer, text="Print generated output")
    print_frame.grid(row=3, column=0, sticky='ew', pady=(0, 10))
    ttk.Checkbutton(
        print_frame,
        text="Print generated layouts (5 copies each)",
        variable=print_layouts_var,
    ).pack(anchor='w', padx=10, pady=(8, 2))
    ttk.Checkbutton(
        print_frame,
        text="Print generated starter sheets (1 copy each)",
        variable=print_starters_var,
    ).pack(anchor='w', padx=10, pady=(0, 2))
    ttk.Label(
        print_frame,
        text="Select either option, or both, to choose which generated output is printed to the default printer.",
        justify='left',
    ).pack(anchor='w', padx=30, pady=(0, 8))

    preview_names = [str(item.get('target_name') or '') for item in generation_plan[:8] if item.get('target_name')]
    if preview_names:
        preview_frame = ttk.LabelFrame(outer, text="Example output filenames")
        preview_frame.grid(row=4, column=0, sticky='ew', pady=(0, 10))
        ttk.Label(preview_frame, text="\n".join(f"• {name}" for name in preview_names), justify='left').pack(anchor='w', padx=10, pady=8)

    button_row = ttk.Frame(outer)
    button_row.grid(row=5, column=0, sticky='e')

    def close_dialog(confirm=False):
        result['confirmed'] = bool(confirm)
        result['overwrite_mode'] = str(overwrite_var.get() or 'skip').strip().lower()
        result['print_layouts'] = bool(print_layouts_var.get())
        result['print_starter_sheets'] = bool(print_starters_var.get())
        try:
            dialog.destroy()
        except Exception:
            pass

    ttk.Button(button_row, text="Cancel", command=lambda: close_dialog(False), width=10).pack(side='right')
    ttk.Button(button_row, text="Run", command=lambda: close_dialog(True), width=10).pack(side='right', padx=(0, 8))

    _ensure_dialog_fits_contents(dialog, min_width=540, min_height=500, extra_width=12, extra_height=12)

    dialog.bind('<Return>', lambda _event: close_dialog(True))
    dialog.bind('<Escape>', lambda _event: close_dialog(False))
    dialog.protocol('WM_DELETE_WINDOW', lambda: close_dialog(False))
    dialog.grab_set()
    parent.wait_window(dialog)
    return result


def _show_gre_homefinder_monthly_confirmation(parent, year, month, generation_plan, macro_title='GRE Homefinder Monthly', regular_name='GRE Homefinder', state_key='gre_homefinder_monthly_confirmation_dialog'):
    result = {'confirmed': False, 'overwrite_mode': 'skip', 'print_layouts': False, 'print_starter_sheets': False}
    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title(f"Confirm {macro_title}")
    try:
        dialog.transient(parent)
    except Exception:
        pass
    dialog.resizable(False, False)
    remember_window_geometry(dialog, state_key, default_geometry="520x430", minsize=(520, 430))

    total_layouts = len(generation_plan)
    unique_dates = sorted({str(item.get('issue_date') or '') for item in generation_plan if item.get('issue_date')})
    sunday_count = len(unique_dates)
    existing_count = sum(1 for item in generation_plan if item.get('exists'))
    new_count = max(0, total_layouts - existing_count)

    outer = ttk.Frame(dialog, padding=12)
    outer.grid(row=0, column=0, sticky="nsew")
    outer.columnconfigure(0, weight=1)

    month_name = calendar.month_name[int(month)]
    summary_lines = [
        f"Month / Year: {month_name} {int(year)}",
        f"Sunday issue dates to generate: {sunday_count}",
        f"Layouts to process: {total_layouts}",
        f"  • Sunday issues: {sunday_count} date(s) using {regular_name}",
        f"Existing target layouts found: {existing_count}",
        f"New target layouts: {new_count}",
    ]
    if unique_dates:
        summary_lines.append(f"Date range: {unique_dates[0]} to {unique_dates[-1]}")

    ttk.Label(outer, text="Please review the macro summary before continuing.", font=(None, 11, "bold")).grid(row=0, column=0, sticky='w')
    ttk.Label(outer, text="\n".join(summary_lines), justify='left').grid(row=1, column=0, sticky='w', pady=(8, 10))

    options_frame = ttk.LabelFrame(outer, text="If a target layout already exists")
    options_frame.grid(row=2, column=0, sticky='ew', pady=(0, 10))
    overwrite_var = tk.StringVar(value='skip')
    ttk.Radiobutton(options_frame, text="Skip existing layouts", value='skip', variable=overwrite_var).pack(anchor='w', padx=10, pady=(8, 4))
    ttk.Radiobutton(options_frame, text="Overwrite existing layouts", value='overwrite', variable=overwrite_var).pack(anchor='w', padx=10, pady=(0, 8))

    print_layouts_var = tk.BooleanVar(value=False)
    print_starters_var = tk.BooleanVar(value=False)
    print_frame = ttk.LabelFrame(outer, text="Print generated output")
    print_frame.grid(row=3, column=0, sticky='ew', pady=(0, 10))
    ttk.Checkbutton(
        print_frame,
        text="Print generated layouts (5 copies each)",
        variable=print_layouts_var,
    ).pack(anchor='w', padx=10, pady=(8, 2))
    ttk.Checkbutton(
        print_frame,
        text="Print generated starter sheets (1 copy each)",
        variable=print_starters_var,
    ).pack(anchor='w', padx=10, pady=(0, 2))
    ttk.Label(
        print_frame,
        text="Select either option, or both, to choose which generated output is printed to the default printer.",
        justify='left',
    ).pack(anchor='w', padx=30, pady=(0, 8))

    preview_names = [str(item.get('target_name') or '') for item in generation_plan[:8] if item.get('target_name')]
    if preview_names:
        preview_frame = ttk.LabelFrame(outer, text="Example output filenames")
        preview_frame.grid(row=4, column=0, sticky='ew', pady=(0, 10))
        ttk.Label(preview_frame, text="\n".join(f"• {name}" for name in preview_names), justify='left').pack(anchor='w', padx=10, pady=8)

    button_row = ttk.Frame(outer)
    button_row.grid(row=5, column=0, sticky='e')

    def close_dialog(confirm=False):
        result['confirmed'] = bool(confirm)
        result['overwrite_mode'] = str(overwrite_var.get() or 'skip').strip().lower()
        result['print_layouts'] = bool(print_layouts_var.get())
        result['print_starter_sheets'] = bool(print_starters_var.get())
        try:
            dialog.destroy()
        except Exception:
            pass

    ttk.Button(button_row, text="Cancel", command=lambda: close_dialog(False), width=10).pack(side='right')
    ttk.Button(button_row, text="Run", command=lambda: close_dialog(True), width=10).pack(side='right', padx=(0, 8))

    _ensure_dialog_fits_contents(dialog, min_width=540, min_height=500, extra_width=12, extra_height=12)

    dialog.bind('<Return>', lambda _event: close_dialog(True))
    dialog.bind('<Escape>', lambda _event: close_dialog(False))
    dialog.protocol('WM_DELETE_WINDOW', lambda: close_dialog(False))
    dialog.grab_set()
    parent.wait_window(dialog)
    return result


def _create_usat_monthly_progress_window(parent, total_steps):
    progress = {
        'dialog': None,
        'label_var': tk.StringVar(value='Preparing macro run...'),
        'detail_var': tk.StringVar(value=''),
        'count_var': tk.StringVar(value=f"0 / {max(1, int(total_steps or 1))}"),
        'bar': None,
        'cancelled': False,
        'total_steps': max(1, int(total_steps or 1)),
    }
    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title("USAT Monthly Progress")
    try:
        dialog.transient(parent)
    except Exception:
        pass
    dialog.resizable(False, False)
    remember_window_geometry(dialog, "usat_monthly_progress_dialog", default_geometry="420x150", minsize=(420, 150))
    progress['dialog'] = dialog

    outer = ttk.Frame(dialog, padding=12)
    outer.grid(row=0, column=0, sticky='nsew')
    outer.columnconfigure(0, weight=1)

    ttk.Label(outer, textvariable=progress['label_var'], font=(None, 11, 'bold')).grid(row=0, column=0, sticky='w')
    ttk.Label(outer, textvariable=progress['detail_var'], justify='left').grid(row=1, column=0, sticky='w', pady=(8, 8))
    bar = ttk.Progressbar(outer, orient='horizontal', mode='determinate', maximum=progress['total_steps'])
    bar.grid(row=2, column=0, sticky='ew')
    progress['bar'] = bar
    ttk.Label(outer, textvariable=progress['count_var']).grid(row=3, column=0, sticky='e', pady=(8, 0))

    def _cancel_close():
        progress['cancelled'] = True
    dialog.protocol('WM_DELETE_WINDOW', _cancel_close)
    dialog.update_idletasks()
    return progress


def _create_gre_homefinder_monthly_progress_window(parent, total_steps, macro_title='GRE Homefinder Monthly', state_key='gre_homefinder_monthly_progress_dialog'):
    progress = {
        'dialog': None,
        'label_var': tk.StringVar(value='Preparing macro run...'),
        'detail_var': tk.StringVar(value=''),
        'count_var': tk.StringVar(value=f"0 / {max(1, int(total_steps or 1))}"),
        'bar': None,
        'cancelled': False,
        'total_steps': max(1, int(total_steps or 1)),
    }
    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title(f"{macro_title} Progress")
    try:
        dialog.transient(parent)
    except Exception:
        pass
    dialog.resizable(False, False)
    remember_window_geometry(dialog, state_key, default_geometry="420x150", minsize=(420, 150))
    progress['dialog'] = dialog

    outer = ttk.Frame(dialog, padding=12)
    outer.grid(row=0, column=0, sticky='nsew')
    ttk.Label(outer, textvariable=progress['label_var'], font=(None, 11, 'bold')).grid(row=0, column=0, sticky='w')
    ttk.Label(outer, textvariable=progress['detail_var'], justify='left').grid(row=1, column=0, sticky='w', pady=(8, 8))
    bar = ttk.Progressbar(outer, mode='determinate', maximum=max(1, int(total_steps or 1)))
    bar.grid(row=2, column=0, sticky='ew')
    progress['bar'] = bar
    ttk.Label(outer, textvariable=progress['count_var']).grid(row=3, column=0, sticky='e', pady=(8, 0))

    def _cancel():
        progress['cancelled'] = True

    dialog.protocol('WM_DELETE_WINDOW', _cancel)
    return progress


def _update_usat_monthly_progress(progress_state, current_step, label_text=None, detail_text=None):
    if not isinstance(progress_state, dict):
        return
    dialog = progress_state.get('dialog')
    if dialog is None:
        return
    try:
        if label_text is not None:
            progress_state['label_var'].set(str(label_text))
        if detail_text is not None:
            progress_state['detail_var'].set(str(detail_text))
        bar = progress_state.get('bar')
        if bar is not None:
            bar.configure(value=max(0, min(int(current_step), int(progress_state.get('total_steps', 1)))))
        progress_state['count_var'].set(f"{max(0, int(current_step))} / {int(progress_state.get('total_steps', 1))}")
        dialog.update_idletasks()
        dialog.update()
    except Exception:
        pass


def _close_usat_monthly_progress_window(progress_state):
    if not isinstance(progress_state, dict):
        return
    dialog = progress_state.get('dialog')
    if dialog is None:
        return
    try:
        dialog.destroy()
    except Exception:
        pass
    progress_state['dialog'] = None


def _show_usat_monthly_report_dialog(parent, month_label, report_data):
    report_data = report_data if isinstance(report_data, dict) else {}
    created = [str(item) for item in (report_data.get('created') or []) if str(item)]
    overwritten = [str(item) for item in (report_data.get('overwritten') or []) if str(item)]
    skipped = [str(item) for item in (report_data.get('skipped') or []) if str(item)]
    preview_failures = [str(item) for item in (report_data.get('preview_failures') or []) if str(item)]
    printed_layouts = [str(item) for item in (report_data.get('printed_layouts') or []) if str(item)]
    printed_starters = [str(item) for item in (report_data.get('printed_starters') or []) if str(item)]
    print_failures = [str(item) for item in (report_data.get('print_failures') or []) if str(item)]
    processed_dates = sorted({str(item) for item in (report_data.get('processed_dates') or []) if str(item)})

    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title("USAT Monthly Report")
    try:
        dialog.transient(parent)
    except Exception:
        pass
    dialog.resizable(True, True)
    dialog.geometry("760x560")
    dialog.minsize(680, 460)
    remember_window_geometry(dialog, "usat_monthly_report_dialog", default_geometry="760x560", minsize=(680, 460))

    outer = ttk.Frame(dialog, padding=12)
    outer.grid(row=0, column=0, sticky='nsew')
    dialog.rowconfigure(0, weight=1)
    dialog.columnconfigure(0, weight=1)
    outer.rowconfigure(1, weight=1)
    outer.columnconfigure(0, weight=1)

    summary_lines = [
        f"Month / Year: {month_label}",
        f"Issue dates processed: {len(processed_dates)}",
        f"Layouts created: {len(created)}",
        f"Layouts overwritten: {len(overwritten)}",
        f"Layouts skipped: {len(skipped)}",
        f"Layouts printed: {len(printed_layouts)}",
        f"Starter sheets printed: {len(printed_starters)}",
    ]
    if preview_failures:
        summary_lines.append(f"Preview failures: {len(preview_failures)}")
    if print_failures:
        summary_lines.append(f"Print failures: {len(print_failures)}")
    ttk.Label(outer, text="USAT Monthly Run Report", font=(None, 11, 'bold')).grid(row=0, column=0, sticky='w')
    ttk.Label(outer, text="\n".join(summary_lines), justify='left').grid(row=0, column=0, sticky='e')

    text_frame = ttk.Frame(outer)
    text_frame.grid(row=1, column=0, sticky='nsew', pady=(12, 12))
    text_frame.rowconfigure(0, weight=1)
    text_frame.columnconfigure(0, weight=1)

    report_box = tk.Text(text_frame, wrap='word', state='normal')
    report_box.grid(row=0, column=0, sticky='nsew')
    scroll = ttk.Scrollbar(text_frame, orient='vertical', command=report_box.yview)
    scroll.grid(row=0, column=1, sticky='ns')
    report_box.configure(yscrollcommand=scroll.set)

    section_lines = []
    if processed_dates:
        section_lines.append("Issue Dates Processed")
        section_lines.append("-" * 60)
        section_lines.extend(f"• {item}" for item in processed_dates)
        section_lines.append("")
    for heading, values in [
        ("Created Layouts", created),
        ("Overwritten Layouts", overwritten),
        ("Skipped Layouts", skipped),
        ("Printed Layouts", printed_layouts),
        ("Printed Starter Sheets", printed_starters),
        ("Print Failures", print_failures),
        ("Preview Failures", preview_failures),
    ]:
        section_lines.append(heading)
        section_lines.append("-" * 60)
        if values:
            section_lines.extend(f"• {item}" for item in values)
        else:
            section_lines.append("(none)")
        section_lines.append("")

    report_box.insert('1.0', "\n".join(section_lines).strip() + "\n")
    report_box.configure(state='disabled')

    button_row = ttk.Frame(outer)
    button_row.grid(row=2, column=0, sticky='e')
    ttk.Button(button_row, text='Close', command=dialog.destroy, width=10).pack(side='right')

    dialog.bind('<Escape>', lambda _event: dialog.destroy())
    dialog.protocol('WM_DELETE_WINDOW', dialog.destroy)
    return dialog


def _show_gre_homefinder_monthly_report_dialog(parent, month_label, report_data, macro_title='GRE Homefinder Monthly', state_key='gre_homefinder_monthly_report_dialog'):
    report_data = report_data if isinstance(report_data, dict) else {}
    created = [str(item) for item in (report_data.get('created') or []) if str(item)]
    overwritten = [str(item) for item in (report_data.get('overwritten') or []) if str(item)]
    skipped = [str(item) for item in (report_data.get('skipped') or []) if str(item)]
    preview_failures = [str(item) for item in (report_data.get('preview_failures') or []) if str(item)]
    printed_layouts = [str(item) for item in (report_data.get('printed_layouts') or []) if str(item)]
    printed_starters = [str(item) for item in (report_data.get('printed_starters') or []) if str(item)]
    print_failures = [str(item) for item in (report_data.get('print_failures') or []) if str(item)]
    processed_dates = sorted({str(item) for item in (report_data.get('processed_dates') or []) if str(item)})

    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title(f"{macro_title} Report")
    try:
        dialog.transient(parent)
    except Exception:
        pass
    dialog.resizable(True, True)
    dialog.geometry("760x560")
    dialog.minsize(680, 460)
    remember_window_geometry(dialog, state_key, default_geometry="760x560", minsize=(680, 460))

    outer = ttk.Frame(dialog, padding=12)
    outer.grid(row=0, column=0, sticky='nsew')
    dialog.rowconfigure(0, weight=1)
    dialog.columnconfigure(0, weight=1)
    outer.rowconfigure(1, weight=1)
    outer.columnconfigure(0, weight=1)

    summary_lines = [
        f"Month / Year: {month_label}",
        f"Issue dates processed: {len(processed_dates)}",
        f"Layouts created: {len(created)}",
        f"Layouts overwritten: {len(overwritten)}",
        f"Layouts skipped: {len(skipped)}",
        f"Layouts printed: {len(printed_layouts)}",
        f"Starter sheets printed: {len(printed_starters)}",
    ]
    if preview_failures:
        summary_lines.append(f"Preview failures: {len(preview_failures)}")
    if print_failures:
        summary_lines.append(f"Print failures: {len(print_failures)}")
    ttk.Label(outer, text=f"{macro_title} Run Report", font=(None, 11, 'bold')).grid(row=0, column=0, sticky='w')
    ttk.Label(outer, text="\n".join(summary_lines), justify='left').grid(row=0, column=0, sticky='e')

    text_frame = ttk.Frame(outer)
    text_frame.grid(row=1, column=0, sticky='nsew', pady=(12, 12))
    text_frame.rowconfigure(0, weight=1)
    text_frame.columnconfigure(0, weight=1)

    report_box = tk.Text(text_frame, wrap='word', state='normal')
    report_box.grid(row=0, column=0, sticky='nsew')
    scroll = ttk.Scrollbar(text_frame, orient='vertical', command=report_box.yview)
    scroll.grid(row=0, column=1, sticky='ns')
    report_box.configure(yscrollcommand=scroll.set)

    section_lines = []
    if processed_dates:
        section_lines.append("Issue Dates Processed")
        section_lines.append("-" * 60)
        section_lines.extend(f"• {item}" for item in processed_dates)
        section_lines.append("")
    for heading, values in [
        ("Created Layouts", created),
        ("Overwritten Layouts", overwritten),
        ("Skipped Layouts", skipped),
        ("Printed Layouts", printed_layouts),
        ("Printed Starter Sheets", printed_starters),
        ("Print Failures", print_failures),
        ("Preview Failures", preview_failures),
    ]:
        section_lines.append(heading)
        section_lines.append("-" * 60)
        if values:
            section_lines.extend(f"• {item}" for item in values)
        else:
            section_lines.append("(none)")
        section_lines.append("")

    report_box.insert('1.0', "\n".join(section_lines).strip() + "\n")
    report_box.configure(state='disabled')

    button_row = ttk.Frame(outer)
    button_row.grid(row=2, column=0, sticky='e')
    ttk.Button(button_row, text='Close', command=dialog.destroy, width=10).pack(side='right')

    dialog.bind('<Escape>', lambda _event: dialog.destroy())
    dialog.protocol('WM_DELETE_WINDOW', dialog.destroy)
    return dialog


def _generate_usat_monthly_layouts(parent, year, month, generation_plan, overwrite_mode='skip', print_layouts=False, print_starter_sheets=False):
    overwrite_mode = str(overwrite_mode or 'skip').strip().lower()
    total_steps = len(generation_plan)
    progress_state = _create_usat_monthly_progress_window(parent, total_steps)
    created = []
    overwritten = []
    skipped = []
    preview_failures = []
    printed_layouts = []
    printed_starters = []
    print_failures = []
    processed_dates = set()

    try:
        for index, item in enumerate(generation_plan, start=1):
            target_path = item.get('target_path')
            target_name = str(item.get('target_name') or os.path.basename(str(target_path or '')))
            issue_date = str(item.get('issue_date') or '')
            regular_name = str(item.get('regular_name') or '')
            processed_dates.add(issue_date)
            _update_usat_monthly_progress(
                progress_state,
                index - 1,
                label_text="Generating USAT monthly layouts...",
                detail_text=f"{issue_date} — {regular_name}\n{target_name}",
            )
            if progress_state.get('cancelled'):
                skipped.append(f"{target_name} (cancelled)")
                continue

            target_exists = _macro_target_layout_exists(target_path)
            if target_exists and overwrite_mode != 'overwrite':
                skipped.append(target_name)
                _update_usat_monthly_progress(
                    progress_state,
                    index,
                    label_text="Skipping existing layout...",
                    detail_text=f"{issue_date} — {regular_name}\n{target_name}",
                )
                continue

            data = json.loads(json.dumps(item.get('source_data') or {}, default=str))
            for transient_key in ('_db_record_id', '_db_record_type', '_file_path', '_layout_name'):
                data.pop(transient_key, None)
            data['issue_date'] = issue_date
            data['saved_at'] = datetime.now().isoformat(timespec='seconds')
            data['last_changed_by'] = get_windows_username()
            data['name'] = os.path.splitext(target_name)[0]

            safe_write_json(target_path, data)
            if target_exists:
                overwritten.append(target_name)
            else:
                created.append(target_name)

            if print_layouts or print_starter_sheets:
                if print_layouts and print_starter_sheets:
                    print_status_label = "Printing generated layouts and starter sheets..."
                elif print_layouts:
                    print_status_label = "Printing generated layouts..."
                else:
                    print_status_label = "Printing generated starter sheets..."
                _update_usat_monthly_progress(
                    progress_state,
                    index - 1,
                    label_text=print_status_label,
                    detail_text=f"{issue_date} — {regular_name}\n{target_name}",
                )
                if print_layouts:
                    try:
                        _print_layout_data_to_default_printer(data, copies=5)
                        printed_layouts.append(f"{target_name} (5 copies)")
                    except Exception as exc:
                        print_failures.append(f"Layout: {target_name} — {exc}")
                if print_starter_sheets:
                    try:
                        _print_starter_sheet_data_to_default_printer(data, copies=1)
                        printed_starters.append(f"{target_name} (1 copy)")
                    except Exception as exc:
                        print_failures.append(f"Starter: {target_name} — {exc}")

            try:
                regenerate_preview_image_for_json_path(
                    target_path,
                    template_mode=False,
                    default_dir=LAYOUTS_DIR,
                    prompt_save_template=False,
                    scale=0.75,
                )
            except Exception:
                preview_failures.append(target_name)

            _update_usat_monthly_progress(
                progress_state,
                index,
                label_text="Generating USAT monthly layouts...",
                detail_text=f"{issue_date} — {regular_name}\n{target_name}",
            )
    finally:
        _close_usat_monthly_progress_window(progress_state)

    month_label = f"{calendar.month_name[int(month)]} {int(year)}"
    report_data = {
        'created': created,
        'overwritten': overwritten,
        'skipped': skipped,
        'preview_failures': preview_failures,
        'printed_layouts': printed_layouts,
        'printed_starters': printed_starters,
        'print_failures': print_failures,
        'processed_dates': sorted(processed_dates),
    }
    _show_usat_monthly_report_dialog(parent, month_label, report_data)
    return True


def _generate_gre_homefinder_monthly_layouts(parent, year, month, generation_plan, overwrite_mode='skip', print_layouts=False, print_starter_sheets=False, macro_title='GRE Homefinder Monthly', state_prefix='gre_homefinder_monthly'):
    overwrite_mode = str(overwrite_mode or 'skip').strip().lower()
    total_steps = len(generation_plan)
    progress_state = _create_gre_homefinder_monthly_progress_window(parent, total_steps, macro_title=macro_title, state_key=f'{state_prefix}_progress_dialog')
    created = []
    overwritten = []
    skipped = []
    preview_failures = []
    printed_layouts = []
    printed_starters = []
    print_failures = []
    processed_dates = set()

    try:
        for index, item in enumerate(generation_plan, start=1):
            target_path = item.get('target_path')
            target_name = str(item.get('target_name') or os.path.basename(str(target_path or '')))
            issue_date = str(item.get('issue_date') or '')
            regular_name = str(item.get('regular_name') or '')
            processed_dates.add(issue_date)
            _update_usat_monthly_progress(
                progress_state,
                index - 1,
                label_text=f"Generating {macro_title} layouts...",
                detail_text=f"{issue_date} — {regular_name}\n{target_name}",
            )
            if progress_state.get('cancelled'):
                skipped.append(f"{target_name} (cancelled)")
                continue

            target_exists = _macro_target_layout_exists(target_path)
            if target_exists and overwrite_mode != 'overwrite':
                skipped.append(target_name)
                _update_usat_monthly_progress(
                    progress_state,
                    index,
                    label_text="Skipping existing layout...",
                    detail_text=f"{issue_date} — {regular_name}\n{target_name}",
                )
                continue

            data = json.loads(json.dumps(item.get('source_data') or {}, default=str))
            for transient_key in ('_db_record_id', '_db_record_type', '_file_path', '_layout_name'):
                data.pop(transient_key, None)
            data['issue_date'] = issue_date
            data['saved_at'] = datetime.now().isoformat(timespec='seconds')
            data['last_changed_by'] = get_windows_username()
            data['name'] = os.path.splitext(target_name)[0]

            safe_write_json(target_path, data)
            if target_exists:
                overwritten.append(target_name)
            else:
                created.append(target_name)

            if print_layouts or print_starter_sheets:
                if print_layouts and print_starter_sheets:
                    print_status_label = "Printing generated layouts and starter sheets..."
                elif print_layouts:
                    print_status_label = "Printing generated layouts..."
                else:
                    print_status_label = "Printing generated starter sheets..."
                _update_usat_monthly_progress(
                    progress_state,
                    index - 1,
                    label_text=print_status_label,
                    detail_text=f"{issue_date} — {regular_name}\n{target_name}",
                )
                if print_layouts:
                    try:
                        _print_layout_data_to_default_printer(data, copies=5)
                        printed_layouts.append(f"{target_name} (5 copies)")
                    except Exception as exc:
                        print_failures.append(f"Layout: {target_name} — {exc}")
                if print_starter_sheets:
                    try:
                        _print_starter_sheet_data_to_default_printer(data, copies=1)
                        printed_starters.append(f"{target_name} (1 copy)")
                    except Exception as exc:
                        print_failures.append(f"Starter: {target_name} — {exc}")

            try:
                regenerate_preview_image_for_json_path(
                    target_path,
                    template_mode=False,
                    default_dir=LAYOUTS_DIR,
                    prompt_save_template=False,
                    scale=0.75,
                )
            except Exception:
                preview_failures.append(target_name)

            _update_usat_monthly_progress(
                progress_state,
                index,
                label_text="Generating GRE Homefinder monthly layouts...",
                detail_text=f"{issue_date} — {regular_name}\n{target_name}",
            )
    finally:
        _close_usat_monthly_progress_window(progress_state)

    month_label = f"{calendar.month_name[int(month)]} {int(year)}"
    report_data = {
        'created': created,
        'overwritten': overwritten,
        'skipped': skipped,
        'preview_failures': preview_failures,
        'printed_layouts': printed_layouts,
        'printed_starters': printed_starters,
        'print_failures': print_failures,
        'processed_dates': sorted(processed_dates),
    }
    _show_gre_homefinder_monthly_report_dialog(parent, month_label, report_data, macro_title=macro_title, state_key=f'{state_prefix}_report_dialog')
    return True




def _run_single_regular_sunday_monthly_macro(parent, macro_key):
    macro_settings = SUNDAY_SINGLE_REGULAR_MONTHLY_MACROS.get(str(macro_key or '').strip().lower())
    if not isinstance(macro_settings, dict):
        return False
    macro_title = str(macro_settings.get('title') or 'Sunday Monthly Macro').strip() or 'Sunday Monthly Macro'
    regular_name = str(macro_settings.get('regular_name') or '').strip()
    state_prefix = str(macro_settings.get('state_prefix') or str(macro_key or '').strip().lower() or 'sunday_monthly_macro').strip()

    picked = _show_month_year_picker(parent, title=macro_title)
    if not picked:
        return False
    year, month = picked
    generation_plan, errors = _resolve_single_regular_sunday_monthly_generation_plan(year, month, regular_name)
    if errors:
        messagebox.showerror(macro_title, '\n'.join(error_text for error_text in errors if error_text), parent=parent)
        return False
    confirmation = _show_gre_homefinder_monthly_confirmation(
        parent,
        year,
        month,
        generation_plan,
        macro_title=macro_title,
        regular_name=regular_name,
        state_key=f'{state_prefix}_confirmation_dialog',
    )
    if not confirmation.get('confirmed'):
        return False
    return _generate_gre_homefinder_monthly_layouts(
        parent,
        year,
        month,
        generation_plan,
        overwrite_mode=confirmation.get('overwrite_mode'),
        print_layouts=confirmation.get('print_layouts'),
        print_starter_sheets=confirmation.get('print_starter_sheets'),
        macro_title=macro_title,
        state_prefix=state_prefix,
    )

def _run_launcher_macro(parent, macro_key):
    key = str(macro_key or '').strip().lower()
    if key == 'usat_monthly':
        picked = _show_month_year_picker(parent, title="USAT Monthly")
        if not picked:
            return False
        year, month = picked
        generation_plan, errors = _resolve_usat_monthly_generation_plan(year, month)
        if errors:
            messagebox.showerror("USAT Monthly", "\n".join(error_text for error_text in errors if error_text), parent=parent)
            return False
        confirmation = _show_usat_monthly_confirmation(parent, year, month, generation_plan)
        if not confirmation.get('confirmed'):
            return False
        return _generate_usat_monthly_layouts(
            parent,
            year,
            month,
            generation_plan,
            overwrite_mode=confirmation.get('overwrite_mode'),
            print_layouts=confirmation.get('print_layouts'),
            print_starter_sheets=confirmation.get('print_starter_sheets'),
        )
    if key == 'gre_homefinder_monthly':
        picked = _show_month_year_picker(parent, title="GRE Homefinder Monthly")
        if not picked:
            return False
        year, month = picked
        generation_plan, errors = _resolve_gre_homefinder_monthly_generation_plan(year, month)
        if errors:
            messagebox.showerror("GRE Homefinder Monthly", "\n".join(error_text for error_text in errors if error_text), parent=parent)
            return False
        confirmation = _show_gre_homefinder_monthly_confirmation(parent, year, month, generation_plan)
        if not confirmation.get('confirmed'):
            return False
        return _generate_gre_homefinder_monthly_layouts(
            parent,
            year,
            month,
            generation_plan,
            overwrite_mode=confirmation.get('overwrite_mode'),
            print_layouts=confirmation.get('print_layouts'),
            print_starter_sheets=confirmation.get('print_starter_sheets'),
        )
    if key in SUNDAY_SINGLE_REGULAR_MONTHLY_MACROS:
        return _run_single_regular_sunday_monthly_macro(parent, key)
    messagebox.showerror("Macros", f"Unknown macro: {macro_key}", parent=parent)
    return False


def show_launcher_macro_dialog(parent, launcher_username=None):
    if not _launcher_user_can_open_macros(launcher_username or get_windows_username()):
        return None
    existing = getattr(parent, '_launcher_macro_dialog', None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return existing
    except Exception:
        pass

    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title("Macros")
    try:
        dialog.transient(parent)
    except Exception:
        pass
    dialog.resizable(False, False)
    remember_window_geometry(dialog, "launcher_macro_dialog", default_geometry="460x360", minsize=(460, 360))
    parent._launcher_macro_dialog = dialog

    def _cleanup_dialog():
        try:
            parent._launcher_macro_dialog = None
        except Exception:
            pass
        try:
            dialog.destroy()
        except Exception:
            pass

    outer = ttk.Frame(dialog, padding=12)
    outer.grid(row=0, column=0, sticky="nsew")
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(1, weight=1)

    ttk.Label(outer, text="Available Macros", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")

    macros = [
        ("usat_monthly", "USAT monthly", "Generate USAT layouts for every Monday-Friday issue date in the selected month, show a confirmation summary, choose overwrite or skip for existing layouts, select layout and starter-sheet printing independently, and then display a progress window and end-of-run report."),
        ("gre_homefinder_monthly", "GRE Homefinder Monthly", "Generate GRE Homefinder layouts for every Sunday issue date in the selected month, show a confirmation summary, select layout and starter-sheet printing independently, choose overwrite or skip for existing layouts, and then display a progress window and end-of-run report."),
        ("aug_comics_monthly", "AUG COMICS Monthly", "Generate AUG COMICS layouts for every Sunday issue date in the selected month, show a confirmation summary, select layout and starter-sheet printing independently, choose overwrite or skip for existing layouts, and then display a progress window and end-of-run report."),
        ("gre_comics_monthly", "GRE COMICS Monthly", "Generate GRE COMICS layouts for every Sunday issue date in the selected month, show a confirmation summary, select layout and starter-sheet printing independently, choose overwrite or skip for existing layouts, and then display a progress window and end-of-run report."),
        ("ral_comics_monthly", "RAL COMICS Monthly", "Generate RAL COMICS layouts for every Sunday issue date in the selected month, show a confirmation summary, select layout and starter-sheet printing independently, choose overwrite or skip for existing layouts, and then display a progress window and end-of-run report."),
        ("usat_co_comics_monthly", "USAT CO COMICS Monthly", "Generate USAT CO COMICS layouts for every Sunday issue date in the selected month, show a confirmation summary, select layout and starter-sheet printing independently, choose overwrite or skip for existing layouts, and then display a progress window and end-of-run report."),
    ]
    macro_list = tk.Listbox(outer, exportselection=False, height=max(4, len(macros)))
    macro_list.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
    for _macro_key, macro_label, _description in macros:
        macro_list.insert('end', macro_label)
    if macros:
        macro_list.selection_set(0)
        macro_list.activate(0)

    description_var = tk.StringVar(value=macros[0][2] if macros else '')
    ttk.Label(outer, textvariable=description_var, wraplength=360, justify='left').grid(row=2, column=0, sticky='w')

    def selected_macro_key():
        selection = macro_list.curselection()
        if not selection:
            return None
        index = int(selection[0])
        if index < 0 or index >= len(macros):
            return None
        return macros[index][0]

    def refresh_description(_event=None):
        selection = macro_list.curselection()
        if not selection:
            description_var.set('')
            return
        index = int(selection[0])
        if 0 <= index < len(macros):
            description_var.set(macros[index][2])

    def run_selected_macro(_event=None):
        macro_key = selected_macro_key()
        if not macro_key:
            messagebox.showinfo("Macros", "Please select a macro to run.", parent=dialog)
            return
        _run_launcher_macro(dialog, macro_key)

    button_row = ttk.Frame(outer)
    button_row.grid(row=3, column=0, sticky='e', pady=(10, 0))
    ttk.Button(button_row, text='Close', command=_cleanup_dialog, width=10).pack(side='right')
    ttk.Button(button_row, text='Run', command=run_selected_macro, width=10).pack(side='right', padx=(0, 8))

    macro_list.bind('<<ListboxSelect>>', refresh_description)
    macro_list.bind('<Double-Button-1>', run_selected_macro)
    dialog.bind('<Return>', run_selected_macro)
    dialog.bind('<Escape>', lambda _event: _cleanup_dialog())
    dialog.protocol('WM_DELETE_WINDOW', _cleanup_dialog)
    refresh_description()
    try:
        macro_list.focus_set()
    except Exception:
        pass
    return dialog


_SINGLE_INSTANCE_HOST = "127.0.0.1"
_SINGLE_INSTANCE_PORT = 47657
_SINGLE_INSTANCE_AUTH_TOKEN = "PRESS_LAYOUTS_SINGLE_INSTANCE_V2"
_SINGLE_INSTANCE_MUTEX_NAME = r"Local\PressLayoutsMainLauncherSingleton"
_SINGLE_INSTANCE_ALERT_TITLE = "Press Layouts Already Running"
_SINGLE_INSTANCE_ALERT_MESSAGE = "Press Layouts is already open. Only one main launcher instance can run at a time."
_SINGLE_INSTANCE_SERVER_SOCKET = None
_SINGLE_INSTANCE_MUTEX_HANDLE = None
_SINGLE_INSTANCE_ACTIVE_WINDOW = None
_SINGLE_INSTANCE_PENDING_ALERTS = 0
_SINGLE_INSTANCE_STATE_LOCK = threading.Lock()


def show_single_instance_warning_dialog(parent):
    def _raise_single_instance_dialog(target_dialog, force_focus=False):
        if target_dialog is None:
            return
        try:
            if not target_dialog.winfo_exists():
                return
        except Exception:
            return
        try:
            target_dialog.deiconify()
        except Exception:
            pass
        try:
            target_dialog.attributes("-topmost", True)
        except Exception:
            pass
        try:
            target_dialog.lift()
        except Exception:
            pass
        if force_focus:
            try:
                target_dialog.focus_force()
            except Exception:
                pass

    existing = getattr(parent, "_single_instance_warning_dialog", None)
    try:
        if existing is not None and existing.winfo_exists():
            _raise_single_instance_dialog(existing, force_focus=True)
            return existing
    except Exception:
        pass

    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    parent._single_instance_warning_dialog = dialog
    dialog.title(_SINGLE_INSTANCE_ALERT_TITLE)
    try:
        dialog.transient(parent)
    except Exception:
        pass
    dialog.resizable(False, False)
    remember_window_geometry(dialog, "single_instance_warning_dialog", default_geometry="460x180", minsize=(460, 180))

    body = ttk.Frame(dialog, padding=16)
    body.pack(fill="both", expand=True)
    body.columnconfigure(0, weight=1)

    ttk.Label(body, text=_SINGLE_INSTANCE_ALERT_TITLE, font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(body, text=_SINGLE_INSTANCE_ALERT_MESSAGE, justify="left", wraplength=400).grid(row=1, column=0, sticky="w", pady=(10, 0))

    button_row = ttk.Frame(body)
    button_row.grid(row=2, column=0, sticky="e", pady=(18, 0))

    def _close_dialog():
        try:
            dialog.attributes("-topmost", False)
        except Exception:
            pass
        try:
            dialog.destroy()
        except Exception:
            pass
        if getattr(parent, "_single_instance_warning_dialog", None) is dialog:
            parent._single_instance_warning_dialog = None

    ttk.Button(button_row, text="OK", command=_close_dialog, width=12).pack(side="left")

    dialog.protocol("WM_DELETE_WINDOW", _close_dialog)
    dialog.bind("<Escape>", lambda _event: _close_dialog())
    dialog.bind("<Map>", lambda _event: dialog.after_idle(lambda: _raise_single_instance_dialog(dialog, force_focus=False)), add="+")
    dialog.bind("<Visibility>", lambda _event: dialog.after_idle(lambda: _raise_single_instance_dialog(dialog, force_focus=False)), add="+")
    _raise_single_instance_dialog(dialog, force_focus=True)
    return dialog


def _single_instance_raise_window(win, show_message=False):
    if win is None:
        return False
    try:
        if not win.winfo_exists():
            return False
    except Exception:
        return False

    def _show_on_ui_thread():
        try:
            win.deiconify()
        except Exception:
            pass
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass
        try:
            win.lift()
        except Exception:
            pass
        try:
            win.focus_force()
        except Exception:
            pass
        try:
            win.after(500, lambda: win.attributes("-topmost", False))
        except Exception:
            pass
        if show_message:
            try:
                show_single_instance_warning_dialog(win)
            except Exception:
                try:
                    messagebox.showwarning(_SINGLE_INSTANCE_ALERT_TITLE, _SINGLE_INSTANCE_ALERT_MESSAGE, parent=win)
                except Exception:
                    try:
                        messagebox.showwarning(_SINGLE_INSTANCE_ALERT_TITLE, _SINGLE_INSTANCE_ALERT_MESSAGE)
                    except Exception:
                        pass

    try:
        win.after(0, _show_on_ui_thread)
        return True
    except Exception:
        return False



def _single_instance_handle_activation_request():
    global _SINGLE_INSTANCE_PENDING_ALERTS
    with _SINGLE_INSTANCE_STATE_LOCK:
        win = _SINGLE_INSTANCE_ACTIVE_WINDOW
        if _single_instance_raise_window(win, show_message=True):
            return True
        _SINGLE_INSTANCE_PENDING_ALERTS = int(_SINGLE_INSTANCE_PENDING_ALERTS or 0) + 1
        return False



def _single_instance_server_loop(server_socket):
    while True:
        try:
            conn, _addr = server_socket.accept()
        except OSError:
            break
        try:
            with conn:
                payload = b""
                try:
                    payload = conn.recv(1024)
                except Exception:
                    payload = b""
                command = payload.decode('utf-8', errors='ignore').strip()
                if command == f"{_SINGLE_INSTANCE_AUTH_TOKEN}:ACTIVATE":
                    _single_instance_handle_activation_request()
                    try:
                        conn.sendall(b"OK")
                    except Exception:
                        pass
                else:
                    try:
                        conn.sendall(b"OK")
                    except Exception:
                        pass
        except Exception:
            continue
    try:
        server_socket.close()
    except Exception:
        pass



def _signal_existing_single_instance_activate(timeout=0.35, attempts=8, pause_seconds=0.15):
    import time
    timeout = max(0.1, float(timeout or 0.35))
    attempts = max(1, int(attempts or 1))
    pause_seconds = max(0.0, float(pause_seconds or 0.0))
    for attempt_index in range(attempts):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(timeout)
        except Exception:
            pass
        try:
            sock.connect((_SINGLE_INSTANCE_HOST, int(_SINGLE_INSTANCE_PORT)))
            sock.sendall(f"{_SINGLE_INSTANCE_AUTH_TOKEN}:ACTIVATE".encode('utf-8'))
            try:
                response = sock.recv(32)
            except Exception:
                response = b""
            return response == b"OK" or response == b""
        except Exception:
            if attempt_index + 1 < attempts and pause_seconds > 0:
                time.sleep(pause_seconds)
        finally:
            try:
                sock.close()
            except Exception:
                pass
    return False



def _try_acquire_single_instance_mutex():
    if os.name != 'nt':
        return True, None
    try:
        import ctypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        create_mutex.restype = ctypes.c_void_p
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int
        handle = create_mutex(None, 0, _SINGLE_INSTANCE_MUTEX_NAME)
        if not handle:
            return True, None
        already_exists = int(ctypes.get_last_error() or 0) == 183
        if already_exists:
            try:
                close_handle(handle)
            except Exception:
                pass
            return False, None
        return True, handle
    except Exception:
        return True, None



def _release_single_instance_mutex_handle(handle):
    if not handle or os.name != 'nt':
        return
    try:
        import ctypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int
        close_handle(handle)
    except Exception:
        pass



def ensure_single_main_launcher_instance():
    global _SINGLE_INSTANCE_SERVER_SOCKET, _SINGLE_INSTANCE_MUTEX_HANDLE
    with _SINGLE_INSTANCE_STATE_LOCK:
        if _SINGLE_INSTANCE_SERVER_SOCKET is not None:
            return True
    owns_mutex, mutex_handle = _try_acquire_single_instance_mutex()
    if not owns_mutex:
        _signal_existing_single_instance_activate()
        return False

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            try:
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except Exception:
                pass
        elif os.name != 'nt':
            try:
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except Exception:
                pass
        server_socket.bind((_SINGLE_INSTANCE_HOST, int(_SINGLE_INSTANCE_PORT)))
        server_socket.listen(5)
    except OSError:
        try:
            server_socket.close()
        except Exception:
            pass
        _release_single_instance_mutex_handle(mutex_handle)
        _signal_existing_single_instance_activate()
        return False

    with _SINGLE_INSTANCE_STATE_LOCK:
        _SINGLE_INSTANCE_SERVER_SOCKET = server_socket
        _SINGLE_INSTANCE_MUTEX_HANDLE = mutex_handle
    listener = threading.Thread(target=_single_instance_server_loop, args=(server_socket,), name='PressLayoutsSingleInstance', daemon=True)
    listener.start()
    return True



def release_single_main_launcher_instance():
    global _SINGLE_INSTANCE_SERVER_SOCKET, _SINGLE_INSTANCE_MUTEX_HANDLE, _SINGLE_INSTANCE_ACTIVE_WINDOW, _SINGLE_INSTANCE_PENDING_ALERTS
    server_socket = None
    mutex_handle = None
    with _SINGLE_INSTANCE_STATE_LOCK:
        server_socket = _SINGLE_INSTANCE_SERVER_SOCKET
        _SINGLE_INSTANCE_SERVER_SOCKET = None
        mutex_handle = _SINGLE_INSTANCE_MUTEX_HANDLE
        _SINGLE_INSTANCE_MUTEX_HANDLE = None
        _SINGLE_INSTANCE_ACTIVE_WINDOW = None
        _SINGLE_INSTANCE_PENDING_ALERTS = 0
    if server_socket is not None:
        try:
            server_socket.close()
        except Exception:
            pass
    _release_single_instance_mutex_handle(mutex_handle)



def register_single_instance_window(win):
    global _SINGLE_INSTANCE_ACTIVE_WINDOW, _SINGLE_INSTANCE_PENDING_ALERTS
    if win is None:
        return
    pending_count = 0
    with _SINGLE_INSTANCE_STATE_LOCK:
        _SINGLE_INSTANCE_ACTIVE_WINDOW = win
        pending_count = int(_SINGLE_INSTANCE_PENDING_ALERTS or 0)
        _SINGLE_INSTANCE_PENDING_ALERTS = 0
    try:
        if not getattr(win, '_single_instance_destroy_bound', False):
            def _on_destroy(event):
                try:
                    if event.widget is not win:
                        return
                except Exception:
                    pass
                unregister_single_instance_window(win)
            win.bind('<Destroy>', _on_destroy, add='+')
            win._single_instance_destroy_bound = True
    except Exception:
        pass
    if pending_count > 0:
        _single_instance_raise_window(win, show_message=True)



def unregister_single_instance_window(win):
    global _SINGLE_INSTANCE_ACTIVE_WINDOW
    with _SINGLE_INSTANCE_STATE_LOCK:
        if _SINGLE_INSTANCE_ACTIVE_WINDOW is win:
            _SINGLE_INSTANCE_ACTIVE_WINDOW = None



_CFB_FREESECT = 0xFFFFFFFF
_CFB_ENDOFCHAIN = 0xFFFFFFFE
_CFB_FATSECT = 0xFFFFFFFD
_CFB_DIFSECT = 0xFFFFFFFC


def _read_msg_streams(msg_path):
    """Parse an Outlook .msg (OLE2 compound file) and return {stream_name: bytes}."""
    with open(msg_path, 'rb') as fh:
        data = fh.read()
    if data[:8] != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        return {}
    sector_shift = struct.unpack('<H', data[0x1E:0x20])[0]
    sector_size = 1 << sector_shift
    mini_shift = struct.unpack('<H', data[0x20:0x22])[0]
    mini_size = 1 << mini_shift
    first_dir = struct.unpack('<I', data[0x30:0x34])[0]
    mini_cutoff = struct.unpack('<I', data[0x38:0x3C])[0]
    first_minifat = struct.unpack('<I', data[0x3C:0x40])[0]
    num_minifat = struct.unpack('<I', data[0x40:0x44])[0]

    def _sector_offset(sid):
        return (sid + 1) * sector_size

    difat = list(struct.unpack('<109I', data[0x4C:0x4C + 109 * 4]))
    fat_sectors = [sid for sid in difat if sid != _CFB_FREESECT]
    fat = []
    for fsid in fat_sectors:
        fat += list(struct.unpack('<%dI' % (sector_size // 4), data[_sector_offset(fsid):_sector_offset(fsid) + sector_size]))

    entries = []
    dir_sector = first_dir
    seen = set()
    while dir_sector != _CFB_ENDOFCHAIN and dir_sector not in seen:
        seen.add(dir_sector)
        base = _sector_offset(dir_sector)
        for off in range(0, sector_size, 128):
            entry = data[base + off:base + off + 128]
            if len(entry) < 128:
                break
            obj_type = entry[0x42]
            if obj_type not in (2, 5):
                continue
            name_len = struct.unpack('<H', entry[0x40:0x42])[0]
            name = entry[:max(0, name_len - 2)].decode('utf-16-le', errors='replace') if name_len >= 2 else ""
            entries.append({
                'type': obj_type,
                'name': name,
                'sector': struct.unpack('<I', entry[0x74:0x78])[0],
                'size': struct.unpack('<Q', entry[0x78:0x80])[0],
            })
        dir_sector = fat[dir_sector]

    root = None
    streams = {}
    for entry in entries:
        if entry['type'] == 5:
            root = entry
        elif entry['type'] == 2:
            streams[entry['name']] = entry

    def _read_regular(entry):
        out = b''
        cur = entry['sector']
        chain_seen = set()
        remaining = entry['size']
        while cur != _CFB_ENDOFCHAIN and cur not in chain_seen and remaining > 0 and cur < len(fat):
            chain_seen.add(cur)
            out += data[_sector_offset(cur):_sector_offset(cur) + sector_size]
            remaining -= sector_size
            cur = fat[cur]
        return out[:entry['size']]

    def _read_stream(name):
        entry = streams.get(name)
        if entry is None:
            return b''
        if entry['size'] >= mini_cutoff or root is None:
            return _read_regular(entry)
        mini_stream = _read_regular(root)
        minifat = []
        for m in range(num_minifat):
            minifat += list(struct.unpack('<%dI' % (sector_size // 4), data[_sector_offset(first_minifat + m):_sector_offset(first_minifat + m) + sector_size]))
        out = b''
        cur = entry['sector']
        chain_seen = set()
        remaining = entry['size']
        while cur != _CFB_ENDOFCHAIN and cur not in chain_seen and remaining > 0 and cur < len(minifat):
            chain_seen.add(cur)
            out += mini_stream[cur * mini_size:cur * mini_size + mini_size]
            remaining -= mini_size
            nxt = minifat[cur]
            cur = nxt if nxt not in (_CFB_FREESECT, _CFB_FATSECT, _CFB_DIFSECT) else _CFB_ENDOFCHAIN
        return out[:entry['size']]

    return {name: _read_stream(name) for name in streams}


def _extract_msg_body_text(msg_path):
    """Return the plain-text body of an Outlook .msg file, or None."""
    try:
        streams = _read_msg_streams(msg_path)
    except Exception:
        return None
    for name in ("__substg1.0_1000001F", "__substg1.0_1000001E"):
        raw = streams.get(name)
        if raw:
            try:
                if name.endswith("1F"):
                    return raw.decode('utf-16-le', errors='replace')
                return raw.decode('latin-1', errors='replace')
            except Exception:
                return None
    return None


def _parse_manifest_msg(msg_path):
    """Parse an Outlook 'Change in Paging' email (.msg) into the manifest structure.

    These NYT emails are always Broadsheet and list sections as
    <section>[\\t<name>]\\t<pages>[\\t<split>]\\t<color pages> per run.
    Returns the same dict shape as _parse_manifest_pdf, plus an optional
    'split' list (signature page counts) per section.

    The plain-text body stream inside the .msg is often truncated to a short
    preview, so the full body is read through Outlook COM when available and the
    direct compound-file parser is used as a fallback.
    """
    body = _extract_msg_body_text_via_com(msg_path) or _extract_msg_body_text(msg_path)
    return _parse_manifest_msg_body(body)


def _parse_manifest_msg_body(body):
    result = {"product": "NYT", "issue_date": "", "is_tab": False, "sections": []}
    if not body:
        return result
    lines = [line.replace('\r', '') for line in body.split('\n')]
    for line in lines:
        match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", line)
        if match:
            result["issue_date"] = match.group(1)
            break

    by_name = {}
    for line in lines:
        cells = [cell.strip() for cell in line.split('\t')]
        pages_idx = None
        for i, cell in enumerate(cells):
            if cell.isdigit() and int(cell) > 0:
                pages_idx = i
                break
        if pages_idx is None:
            continue
        pages = int(cells[pages_idx])
        before = [cell for cell in cells[:pages_idx] if cell]
        after = [cell for cell in cells[pages_idx + 1:] if cell]
        if not before:
            continue
        if len(before) >= 2 and re.match(r'^[A-Z]$', before[0]):
            letter = before[0]
            name = before[0]
        else:
            letter = ""
            name = before[-1]
        split_counts = []
        for cell in after:
            if "/" in cell and "," not in cell and all(part.isdigit() and int(part) > 0 for part in cell.split("/")):
                split_counts = [int(part) for part in cell.split("/")]
                break
        color_pages = []
        for cell in after:
            if "," in cell:
                for token in cell.split(","):
                    token = token.strip()
                    if token.isdigit():
                        color_pages.append(int(token))
        color_pages = sorted(set(page for page in color_pages if 1 <= page <= pages))
        split = split_counts if len(split_counts) >= 2 and sum(split_counts) == pages else None
        by_name[letter or name] = {
            "letter": letter,
            "name": name,
            "pages": pages,
            "format": "Broadsheet",
            "color_pages": color_pages,
            "split": split,
        }
    result["sections"] = list(by_name.values())
    return result


def _extract_msg_body_text_via_com(msg_path):
    """Read the full .msg body through Outlook COM, or None when unavailable."""
    try:
        import win32com.client
    except Exception:
        return None
    try:
        application = win32com.client.Dispatch('Outlook.Application')
        namespace = application.GetNamespace('MAPI')
        item = namespace.OpenSharedItem(os.path.abspath(msg_path))
        try:
            body = str(item.Body or "")
        finally:
            try:
                item.Close(0)
            except Exception:
                pass
        return body or None
    except Exception:
        return None


def _outlook_selected_email_path():
    """Save the email currently selected in Outlook as a temp .msg file.

    Outlook message drags advertise FileGroupDescriptorW but do not deliver
    their contents through tkdnd, so the drop payload is empty. In that case
    the email being dragged is still selected in Outlook, so we ask Outlook
    for it directly and save a .msg we can parse. Returns the temp path or None.
    """
    try:
        import win32com.client
    except Exception:
        return None
    try:
        application = win32com.client.GetActiveObject('Outlook.Application')
        explorer = application.ActiveExplorer()
        if explorer is None:
            return None
        selection = explorer.Selection
        if selection is None or selection.Count < 1:
            return None
        item = selection.Item(1)
        if getattr(item, 'Class', 0) != 43:  # olMail
            return None
        subject = str(item.Subject or "")
        safe = re.sub(r'[<>:"/\\|?*]', '_', subject).strip() or 'outlook_message'
        temp_path = os.path.join(tempfile.gettempdir(), safe[:80] + '.msg')
        item.SaveAs(temp_path, 3)  # olMSG
        if os.path.isfile(temp_path):
            return temp_path
    except Exception:
        return None
    return None


def _resolve_manifest_drop_path(widget, event):
    """Resolve a drop to a manifest file path (PDF/.msg/.eml) or None.

    Handles normal file drops (paths already on disk) and Outlook email
    drags (FileGroupDescriptorW with no extractable contents, which fall
    back to reading the selected email straight out of Outlook).
    """
    paths = _manifest_paths_from_drop(widget, event.data)
    if paths:
        return paths[0]
    source_types = [str(t) for t in (getattr(event, 'sourcetypes', None) or [])]
    drop_type = str(getattr(event, 'type', '') or '')
    looks_like_email = ('FileGroupDescriptorW' in source_types
                        or 'FileGroupDescriptor' in source_types
                        or drop_type in ('FileGroupDescriptorW', 'FileGroupDescriptor'))
    if looks_like_email or not source_types:
        return _outlook_selected_email_path()
    return None


def _extract_eml_body_text(eml_path):
    """Extract the plain-text body of a .eml (RFC 822) message file.

    Returns the decoded text/plain body (tabs preserved), or "" on any failure.
    """
    try:
        with open(eml_path, "rb") as fh:
            raw = fh.read()
    except Exception:
        return ""
    if not raw:
        return ""
    try:
        msg = email.message_from_bytes(raw)
    except Exception:
        return ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() != "text/plain":
                continue
            disposition = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                return _decode_mime_text(payload, charset)
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return _decode_mime_text(payload, charset)
    return ""


def _decode_mime_text(payload, charset):
    for candidate in (charset, "utf-8", "latin-1"):
        try:
            return payload.decode(candidate)
        except Exception:
            continue
    return payload.decode("latin-1", errors="replace")


def _parse_manifest_eml(eml_path):
    """Parse an email saved as .eml into the manifest structure.

    These NYT emails are plain-text (tab-separated runs), so the parsed body
    uses the same table format as the Outlook .msg messages.
    """
    return _parse_manifest_msg_body(_extract_eml_body_text(eml_path))


def _load_manifest_section(sections, make_section_fn, color_index, sec):
    """Append one manifest section to the plan section list (handling splits).

    Returns a list of (section_name, page) color keys for the color-pages screen.
    """
    color_keys = []
    try:
        pages = int(sec.get("pages") or 0)
    except Exception:
        pages = 0
    if pages <= 0:
        return color_keys
    section_name = sec.get("letter") or sec.get("name") or ""
    section_name = _apply_section_translation(section_name)
    fmt = sec.get("format", "Broadsheet")
    try:
        color_pages = sorted(set(int(page) for page in (sec.get("color_pages") or []) if 1 <= int(page) <= pages))
    except Exception:
        color_pages = []
    split_counts = []
    for count in (sec.get("split") or []):
        try:
            parsed = int(count)
        except Exception:
            parsed = 0
        if parsed > 0:
            split_counts.append(parsed)

    parent = make_section_fn(
        name=section_name,
        pages=str(pages),
        start="1",
        fmt=fmt,
        page_numbers=list(range(1, pages + 1)),
        color_index=color_index,
    )
    sections.append(parent)
    if len(split_counts) >= 2 and sum(split_counts) == pages:
        child_uids = []
        cursor = 1
        for i, count in enumerate(split_counts, start=1):
            group = list(range(cursor, cursor + count))
            child = make_section_fn(
                name=f"{section_name}{i}",
                pages=str(count),
                start=str(cursor),
                fmt=fmt,
                page_numbers=group,
                parent_id=parent.get("uid"),
                color_index=color_index,
            )
            sections.append(child)
            child_uids.append(child.get("uid"))
            for page in color_pages:
                if cursor <= page <= cursor + count - 1:
                    color_keys.append((f"{section_name}{i}", page))
            cursor += count
        parent["is_split_parent"] = True
        parent["split_children"] = child_uids
    else:
        for page in color_pages:
            color_keys.append((section_name, page))
    return color_keys


def _parse_manifest_pdf(pdf_path):
    """Parse a press manifest PDF and return structured data.

    Returns dict with:
      product (str), issue_date (str, mm/dd/yyyy),
      is_tab (bool), sections (list of dicts):
        letter (str), name (str), pages (int), format (str),
        color_pages (list of int, 1-indexed within section)
    """
    import fitz
    from collections import defaultdict

    doc = fitz.open(pdf_path)
    page = doc[0]

    # Positioned text items: (text, x, y)
    pos_items = []
    for block in page.get_text('dict')['blocks']:
        if 'lines' in block:
            for line in block['lines']:
                for span in line['spans']:
                    text = span['text'].strip()
                    if text:
                        pos_items.append((text, span['origin'][0], round(span['origin'][1])))

    all_text_flat = page.get_text()
    doc.close()

    lines = [l.strip() for l in all_text_flat.split("\n") if l.strip()]

    # Detect Tab vs Broadsheet
    title_lines = [l for l in lines[:3] if l]
    is_tab = any("Tab" in l for l in title_lines)

    result = {"product": "", "issue_date": "", "is_tab": is_tab, "sections": []}

    if is_tab:
        return _parse_tab_text(lines, result)

    # --- Broadsheet parsing ---
    # Find date
    for l in lines:
        m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", l)
        if m:
            result["issue_date"] = m.group(1)
            break

    # Find product
    exclude = {"DAY", "DATE", "TOTAL NO. OF PAGES", "NUMBER OF SECTIONS", "PRODUCT",
               "COLOR", "SECTION", "NO. OF PAGES", "NO. OF COLOR ADS", "NO. OF EDIT COLOR",
               "COLOR SAMPLES", "ADVERTISING", "EDITORIAL", "NOTES:", "See", "Attached",
               "Press Report", "SECTION NO. OF PAGES"}
    known_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}

    product_candidates = []
    for l in lines:
        if not l or len(l) < 8:
            continue
        if l in exclude or l in known_days:
            continue
        if l == result["issue_date"] or l.isdigit():
            continue
        if l.startswith("Press Report"):
            continue
        if "_" in l:
            continue
        if re.search(r"\d{4}$", l):
            continue
        product_candidates.append(l)

    dash_candidates = [l for l in product_candidates if " - " in l]
    if dash_candidates:
        result["product"] = max(dash_candidates, key=len)
    elif product_candidates:
        result["product"] = max(product_candidates, key=len)

    # --- Position-aware colour-page parsing ---
    # Build rows (y → [(text, x)]) from positioned items
    rows = defaultdict(list)
    for text, x, y in pos_items:
        rows[y].append((text, round(x)))
    sorted_ys = sorted(rows.keys())

    # Find all page-number columns by clustering digit X values.
    digit_x_counts = defaultdict(int)
    for text, x, y in pos_items:
        if text.isdigit() and 1 <= int(text) <= 200:
            digit_x_counts[round(x)] += 1
    # Only consider X values with multiple digit occurrences
    # (filters out one-off header values like section page counts)
    digit_xs = sorted(x for x, c in digit_x_counts.items() if c >= 2)
    # Cluster X values within 20px of each other -> one column
    columns = []
    if digit_xs:
        cluster = [digit_xs[0]]
        for x in digit_xs[1:]:
            if x - cluster[-1] <= 20:
                cluster.append(x)
            else:
                columns.append(round(sum(cluster) / len(cluster)))
                cluster = [x]
        columns.append(round(sum(cluster) / len(cluster)))

    # Build column boundaries (midpoints between column centers)
    col_boundaries = {}
    for i, col_x in enumerate(columns):
        lo = float('-inf') if i == 0 else (columns[i-1] + col_x) / 2
        hi = float('inf') if i == len(columns)-1 else (col_x + columns[i+1]) / 2
        col_boundaries[col_x] = (lo, hi)

    def _col(x):
        for col_x, (lo, hi) in col_boundaries.items():
            if lo <= x < hi:
                return col_x
        return None

    # Build page_at_y for each column
    def _build_page_at_y(target_x):
        result = {}
        for text, x, y in pos_items:
            if round(x) == target_x and text.isdigit():
                n = int(text)
                if 1 <= n <= 200:
                    result[y] = n
        return result

    page_at_y_by_col = {col_x: _build_page_at_y(col_x) for col_x in columns}

    # Per-column section state
    col_cur = {col_x: None for col_x in columns}
    col_name_found = {col_x: False for col_x in columns}
    sections_by_col = {col_x: [] for col_x in columns}

    def _flush(col_x):
        if col_cur[col_x] is not None:
            sections_by_col[col_x].append(col_cur[col_x])
        col_cur[col_x] = None
        col_name_found[col_x] = False

    def _start(letter, col_x):
        _flush(col_x)
        col_cur[col_x] = {"letter": letter, "pages": 0, "name": "", "full_ys": []}
        col_name_found[col_x] = False

    for y in sorted_ys:
        row_texts = rows[y]
        any_sep = False
        for col_x in columns:
            lo, hi = col_boundaries[col_x]
            if any("\\" in t for t, x in row_texts if lo <= x < hi):
                _flush(col_x)
                any_sep = True
        if any_sep:
            continue

        for text, x in row_texts:
            col_x = _col(x)
            if col_x is None:
                continue
            cur = col_cur[col_x]
            if re.match(r"^[A-Z]$", text):
                _start(text, col_x)
            elif cur is not None and cur["pages"] == 0 and text.isdigit():
                cur["pages"] = int(text)
            elif cur is not None and cur["pages"] > 0 and not col_name_found[col_x] and not text.isdigit():
                cur["name"] = text
                col_name_found[col_x] = True
            elif cur is not None and text in ("Full", "Spot"):
                cur["full_ys"].append(y)

    for col_x in columns:
        _flush(col_x)

    for col_x in columns:
        page_at_y = page_at_y_by_col[col_x]
        for sec in sections_by_col[col_x]:
            pages = sec["pages"]
            color_pages = sorted(set(
                pn for y in sec["full_ys"]
                if (pn := page_at_y.get(y)) and 1 <= pn <= pages
            ))
            result["sections"].append({
                "letter": sec["letter"],
                "name": sec["name"] or sec["letter"],
                "pages": pages,
                "format": "Broadsheet",
                "color_pages": color_pages,
            })

    return result


def _parse_tab_text(lines, result):
    """Parse a Tab-format manifest from flat text lines."""
    for l in lines:
        if l.startswith("Product:"):
            result["product"] = l.replace("Product:", "").strip()
            break

    for l in lines:
        m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", l)
        if m:
            result["issue_date"] = m.group(1)
            break

    section_letter = ""
    page_count = 0
    # Find date index, then section letter + page count come after
    date_idx = -1
    for i, l in enumerate(lines):
        if re.match(r"\d{2}/\d{2}/\d{4}", l):
            date_idx = i
            break
    if date_idx >= 0:
        for i in range(date_idx + 1, min(date_idx + 10, len(lines))):
            l = lines[i]
            if not section_letter and re.match(r"^[A-Z]$", l):
                section_letter = l
                continue
            if section_letter and l.isdigit() and not page_count:
                page_count = int(l)
                break

    # Fallback: scan for single letter followed by digit
    if not section_letter or not page_count:
        for i, l in enumerate(lines):
            if re.match(r"^[A-Z]$", l) and i + 1 < len(lines) and lines[i + 1].isdigit():
                section_letter = l
                page_count = int(lines[i + 1])
                break

    # Parse page pairs: "+ N Full", "+ N Spot", or "+ N"
    page_pairs = []
    page_ref = 1
    for l in lines:
        if l.startswith("+"):
            parts = l.replace("+", "").strip().split()
            if parts:
                try:
                    paired_num = int(parts[0])
                    has_full = "Full" in l or "Spot" in l
                    page_pairs.append((page_ref, paired_num, has_full))
                except ValueError:
                    pass
            page_ref += 1

    color_pages = set()
    for p1, p2, is_color in page_pairs:
        if is_color:
            if 1 <= p1 <= page_count:
                color_pages.add(p1)
            if 1 <= p2 <= page_count:
                color_pages.add(p2)

    if section_letter and page_count > 0:
        result["sections"].append({
            "letter": section_letter,
            "name": section_letter,
            "pages": page_count,
            "format": "Tab",
            "color_pages": sorted(color_pages),
        })

    return result


def _build_translation_tab(owner, load_fn, save_fn):
    """Build one translation-table tab (incoming -> output) and return its frame."""
    translations = load_fn()
    tab = ttk.Frame(owner)

    tree_frame = ttk.Frame(tab)
    tree_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))
    columns = ("incoming", "output")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
    tree.heading("incoming", text="Incoming Name")
    tree.heading("output", text="Output Name")
    tree.column("incoming", width=220, minwidth=140)
    tree.column("output", width=220, minwidth=140)
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    btn_frame = ttk.Frame(tab)
    btn_frame.pack(fill="x", padx=8, pady=(4, 8))

    def _save_and_refresh():
        save_fn(translations)
        _populate()

    def _populate():
        tree.delete(*tree.get_children())
        for entry in translations:
            tree.insert("", "end", values=(entry.get("incoming", ""), entry.get("output", "")))

    def _add():
        add_dlg = tk.Toplevel(owner)
        add_dlg.title("Add Translation")
        add_dlg.transient(owner)
        add_dlg.grab_set()
        add_dlg.resizable(False, False)
        ttk.Label(add_dlg, text="Incoming Name:").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        incoming_var = tk.StringVar()
        ttk.Entry(add_dlg, textvariable=incoming_var, width=40).grid(row=0, column=1, padx=(4, 8), pady=(8, 2))
        ttk.Label(add_dlg, text="Output Name:").grid(row=1, column=0, sticky="w", padx=8, pady=(2, 8))
        output_var = tk.StringVar()
        ttk.Entry(add_dlg, textvariable=output_var, width=40).grid(row=1, column=1, padx=(4, 8), pady=(2, 8))
        btn_frame = ttk.Frame(add_dlg)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(0, 8))
        def _confirm():
            incoming = incoming_var.get().strip()
            if incoming:
                translations.append({"incoming": incoming, "output": output_var.get().strip()})
                _save_and_refresh()
            add_dlg.destroy()
        ttk.Button(btn_frame, text="Add", command=_confirm, width=10).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Cancel", command=add_dlg.destroy, width=10).pack(side="left")
        add_dlg.wait_window()

    def _edit():
        selected = tree.selection()
        if not selected:
            return
        idx = tree.index(selected[0])
        entry = translations[idx]
        edit_dlg = tk.Toplevel(owner)
        edit_dlg.title("Edit Translation")
        edit_dlg.transient(owner)
        edit_dlg.grab_set()
        edit_dlg.resizable(False, False)
        ttk.Label(edit_dlg, text="Incoming Name:").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        incoming_var = tk.StringVar(value=entry.get("incoming", ""))
        ttk.Entry(edit_dlg, textvariable=incoming_var, width=40).grid(row=0, column=1, padx=(4, 8), pady=(8, 2))
        ttk.Label(edit_dlg, text="Output Name:").grid(row=1, column=0, sticky="w", padx=8, pady=(2, 8))
        output_var = tk.StringVar(value=entry.get("output", ""))
        ttk.Entry(edit_dlg, textvariable=output_var, width=40).grid(row=1, column=1, padx=(4, 8), pady=(2, 8))
        btn_frame = ttk.Frame(edit_dlg)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(0, 8))
        def _confirm():
            incoming = incoming_var.get().strip()
            if incoming:
                translations[idx] = {"incoming": incoming, "output": output_var.get().strip()}
                _save_and_refresh()
            edit_dlg.destroy()
        ttk.Button(btn_frame, text="Save", command=_confirm, width=10).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Cancel", command=edit_dlg.destroy, width=10).pack(side="left")
        edit_dlg.wait_window()

    def _delete():
        selected = tree.selection()
        if not selected:
            return
        idx = tree.index(selected[0])
        entry = translations[idx]
        if messagebox.askyesno("Delete Translation", f'Delete translation for "{entry.get("incoming", "")}"?', parent=owner):
            del translations[idx]
            _save_and_refresh()

    ttk.Button(btn_frame, text="Add", command=_add, width=12).pack(side="left", padx=(0, 6))
    ttk.Button(btn_frame, text="Edit", command=_edit, width=12).pack(side="left", padx=(0, 6))
    ttk.Button(btn_frame, text="Delete", command=_delete, width=12).pack(side="left", padx=(0, 6))
    _populate()
    return tab


def _show_translation_table_dialog(parent):
    dlg = tk.Toplevel(parent)
    dlg.title("Translation Tables")
    dlg.transient(parent)
    dlg.grab_set()
    dlg.geometry("560x380")
    dlg.minsize(460, 300)
    notebook = ttk.Notebook(dlg)
    notebook.pack(fill="both", expand=True, padx=8, pady=(8, 4))
    notebook.add(
        _build_translation_tab(dlg, _load_product_translations, _save_product_translations),
        text="Product Names",
    )
    notebook.add(
        _build_translation_tab(dlg, _load_section_translations, _save_section_translations),
        text="Section Names",
    )
    btn_frame = ttk.Frame(dlg)
    btn_frame.pack(fill="x", padx=8, pady=(4, 8))
    ttk.Button(btn_frame, text="Close", command=dlg.destroy, width=12).pack(side="right")
    dlg.wait_window()


def _classify_manifest_path(path):
    """Return the manifest kind ('pdf', 'msg' or 'eml') for a dropped path.

    The extension is used first, then the file magic is inspected so temp files
    produced by tkdnd/Outlook are recognised even with an unexpected name.
    """
    lower = str(path or "").lower()
    try:
        with open(path, "rb") as fh:
            head = fh.read(8)
    except Exception:
        head = b""
    if lower.endswith(".pdf") or head.startswith(b"%PDF"):
        return "pdf"
    if lower.endswith(".msg") or head == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "msg"
    if lower.endswith(".eml"):
        return "eml"
    if head.startswith(b"From ") or head.startswith(b"Subject:"):
        return "eml"
    return None


def _manifest_paths_from_drop(widget, data):
    """Turn a tkdnd drop payload into a list of existing file paths."""
    paths = []
    try:
        items = widget.tk.splitlist(data)
    except Exception:
        items = [data]
    for item in items:
        item = str(item or "").strip()
        if not item:
            continue
        if item.startswith("{") and item.endswith("}"):
            item = item[1:-1]
        if os.path.isfile(item):
            paths.append(item)
    if not paths:
        whole = str(data or "").strip()
        if whole.startswith("{") and whole.endswith("}"):
            whole = whole[1:-1]
        if whole and os.path.isfile(whole):
            paths.append(whole)
    return paths


def _report_unusable_manifest_drop(widget, event):
    """Show what the drop delivered when it was not a recognised manifest file."""
    data = str(getattr(event, "data", "") or "").strip()
    drop_type = str(getattr(event, "type", "") or "").strip()
    source_types = getattr(event, "sourcetypes", None) or []
    details = data[:600] if data else "(empty)"
    messagebox.showinfo(
        "Manifest Drop",
        "This drop was not recognised as a manifest (PDF, .msg or .eml email).\n\n"
        f"Drop type: {drop_type or '(none)'}\n"
        f"Source types: {', '.join(source_types) or '(none)'}\n\n"
        f"Received:\n{details}",
        parent=widget,
    )


def _load_manifest_from_path_in_dialog(dialog, path):
    """Worker: parse a manifest PDF, Outlook .msg or .eml email and fill the wizard."""
    manifest = None
    try:
        kind = _classify_manifest_path(path)
        if kind == "msg":
            manifest = _parse_manifest_msg(path)
        elif kind == "eml":
            manifest = _parse_manifest_eml(path)
        elif kind == "pdf":
            manifest = _parse_manifest_pdf(path)
    except Exception as exc:
        try:
            messagebox.showerror("Load Manifest", f"Could not read the manifest file.\n\n{exc}", parent=dialog)
        except Exception:
            pass
        return
    if manifest is None:
        try:
            messagebox.showerror("Load Manifest", "This drop was not recognised as a manifest (PDF, .msg or .eml email).", parent=dialog)
        except Exception:
            pass
        return
    if not manifest.get("sections"):
        try:
            messagebox.showwarning("Load Manifest", "No sections could be identified in the manifest file.", parent=dialog)
        except Exception:
            pass
        return
    try:
        issue_date_var = getattr(dialog, "_plan_issue_date_var", None)
        publication_var = getattr(dialog, "_plan_publication_var", None)
        sections = getattr(dialog, "_plan_sections", None)
        show_page_one_fn = getattr(dialog, "_plan_show_page_one", None)
        make_section_fn = getattr(dialog, "_plan_make_section", None)
        reset_state_fn = getattr(dialog, "_plan_reset_wizard_state", None)
    except Exception:
        return
    if reset_state_fn is not None:
        reset_state_fn()
    elif sections is not None:
        sections.clear()
    if issue_date_var is not None and manifest.get("issue_date"):
        issue_date_var.set(manifest["issue_date"])
    if publication_var is not None and manifest.get("product"):
        publication_var.set(_apply_product_translation(manifest["product"]))
    if sections is not None and make_section_fn is not None:
        for idx, sec in enumerate(manifest["sections"]):
            for key in _load_manifest_section(sections, make_section_fn, idx, sec):
                dialog._manifest_color_pages[key] = True
    else:
        dialog._manifest_color_pages = {}
    if show_page_one_fn is not None:
        show_page_one_fn()


def _patch_tkdnd_file_mapping(tk):
    """Inject missing Outlook file-drop OLE mappings into tkdnd (see build_plan_wizard)."""
    try:
        tk.eval('dict set ::tkdnd::generic::_platform2tkdnd FileGroupDescriptorW DND_Files')
        tk.eval('dict set ::tkdnd::generic::_platform2tkdnd FileGroupDescriptor  DND_Files')
        tk.eval('dict lappend ::tkdnd::generic::_tkdnd2platform DND_Files FileGroupDescriptorW')
        tk.eval('dict lappend ::tkdnd::generic::_tkdnd2platform DND_Files FileGroupDescriptor')
    except Exception:
        pass


def build_plan_wizard(parent):
    """Open the first two pages of the layout planning wizard."""
    dialog = tk.Toplevel(parent)
    set_window_icon(dialog)
    dialog.title("Plan Layout")
    dialog.geometry("900x660")
    dialog.minsize(820, 560)
    remember_window_geometry(dialog, "plan_layout_wizard", default_geometry="900x660", minsize=(820, 560))
    try:
        dialog.transient(parent)
    except Exception:
        pass

    # Register for drag-and-drop (tkdnd via tkinterdnd2)
    # tkdnd (as of 2.10.1) has FileGroupDescriptorW/W mapping commented out in
    # tkdnd_windows.tcl, so we inject the missing entries so Outlook attachment
    # drops (which use FileGroupDescriptorW + FileContents OLE formats) are
    # recognised and extracted to temp files by the DLL.
    _patch_tkdnd_file_mapping(dialog)
    dialog.drop_target_register(tkdnd.DND_FILES, tkdnd.DND_TEXT)
    def _plan_on_drop(event):
        path = _resolve_manifest_drop_path(dialog, event)
        if path:
            _load_manifest_from_path_in_dialog(dialog, path)
            return
        _report_unusable_manifest_drop(dialog, event)
    dialog.dnd_bind("<<Drop>>", _plan_on_drop)

    format_multiples = {"Broadsheet": 2, "Tab": 4, "8 up": 8}
    format_values = list(format_multiples.keys())
    sections = []
    page_color_state = {}
    page_group_state = {}
    split_status_var = tk.StringVar(value="")
    split_recalc_state = {"active": False}
    plan_validation_state = {"active": False, "after_id": None}
    section_palette = ("#f9d6df", "#d7e8ff", "#d9f2df", "#eadcff")

    outer = ttk.Frame(dialog, padding=16)
    outer.pack(fill="both", expand=True)
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(1, weight=1)
    header_var = tk.StringVar(value="Plan Layout")
    ttk.Label(outer, textvariable=header_var, font=(None, 13, "bold")).grid(row=0, column=0, sticky="w")
    body = ttk.Frame(outer)
    body.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)
    footer = ttk.Frame(outer)
    footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
    footer.columnconfigure(0, weight=1)
    footer_left = ttk.Frame(footer)
    footer_left.grid(row=0, column=0, sticky="w")
    footer_right = ttk.Frame(footer)
    footer_right.grid(row=0, column=1, sticky="e")

    issue_date_var = tk.StringVar(value="")
    publication_var = tk.StringVar(value="")

    def _clear_frame(frame):
        for child in frame.winfo_children():
            child.destroy()

    def _clear_footer():
        _clear_frame(footer_left)
        _clear_frame(footer_right)

    def _uppercase_var_trace(var):
        state = {"updating": False}
        def _apply(*_args):
            if state["updating"]:
                return
            current = str(var.get() or "")
            upper = current.upper()
            if current == upper:
                return
            state["updating"] = True
            try:
                var.set(upper)
            finally:
                state["updating"] = False
        var.trace_add("write", _apply)
        return _apply

    def _format_issue_date_var(*_args):
        raw = (issue_date_var.get() or "").strip()
        if not raw:
            return
        dt = parse_issue_date_flexible(raw)
        if dt:
            normalized = dt.strftime("%m/%d/%Y")
            if normalized != raw:
                issue_date_var.set(normalized)

    def _bind_issue_date_formatting(widget):
        widget.bind("<FocusOut>", lambda _event: (_format_issue_date_var(), _sync_page_one_validation()), add="+")
        widget.bind("<Return>", lambda _event: (_format_issue_date_var(), _sync_page_one_validation(), "break")[-1], add="+")

    def _open_plan_issue_date_picker(widget):
        selected_value = ask_issue_date_with_calendar(
            dialog,
            initial_text=issue_date_var.get().strip(),
            anchor_widget=widget,
            title="Select Issue Date",
        )
        if selected_value:
            issue_date_var.set(selected_value)
            _format_issue_date_var()
            _sync_page_one_validation()
        try:
            widget.focus_set()
            widget.selection_range(0, "end")
            widget.icursor("end")
        except Exception:
            pass
        return "break"

    def _bind_mousewheel_to_canvas(widget, canvas):
        def _on_mousewheel(event):
            try:
                if getattr(event, "num", None) == 4:
                    canvas.yview_scroll(-1, "units")
                elif getattr(event, "num", None) == 5:
                    canvas.yview_scroll(1, "units")
                else:
                    delta = int(getattr(event, "delta", 0) or 0)
                    if delta:
                        canvas.yview_scroll(int(-1 * (delta / 120)), "units")
            except Exception:
                pass
            return "break"
        try:
            widget.bind("<MouseWheel>", _on_mousewheel, add="+")
            widget.bind("<Button-4>", _on_mousewheel, add="+")
            widget.bind("<Button-5>", _on_mousewheel, add="+")
        except Exception:
            pass
        for child in widget.winfo_children():
            _bind_mousewheel_to_canvas(child, canvas)

    _uppercase_var_trace(publication_var)

    def _next_section_name(previous_name):
        value = str(previous_name or "A").strip().upper()
        if not value:
            return "A"
        match = re.match(r"^([A-Z]+)(\d*)$", value)
        if match and match.group(2):
            return f"{match.group(1)}{int(match.group(2)) + 1}"
        if match:
            letters = list(match.group(1))
            idx = len(letters) - 1
            carry = True
            while idx >= 0 and carry:
                if letters[idx] == "Z":
                    letters[idx] = "A"
                    idx -= 1
                else:
                    letters[idx] = chr(ord(letters[idx]) + 1)
                    carry = False
            if carry:
                letters.insert(0, "A")
            return "".join(letters)
        return value + "1"

    section_uid_counter = {"value": 0}

    def _next_section_uid():
        section_uid_counter["value"] = int(section_uid_counter.get("value", 0)) + 1
        return f"section_{section_uid_counter['value']}"

    def _make_section(name="A", pages="", start="1", fmt="Broadsheet", page_numbers=None, parent_id=None, color_index=None, is_split_parent=False):
        name_var = tk.StringVar(value=str(name or "A").upper())
        _uppercase_var_trace(name_var)
        stored_page_numbers = []
        if page_numbers is not None:
            for page_number in page_numbers:
                try:
                    stored_page_numbers.append(int(page_number))
                except Exception:
                    pass
        return {
            "uid": _next_section_uid(),
            "name_var": name_var,
            "pages_var": tk.StringVar(value=pages),
            "start_var": tk.StringVar(value=start),
            "format_var": tk.StringVar(value=fmt if fmt in format_values else "Broadsheet"),
            "pages_label_var": tk.StringVar(value=""),
            "page_numbers": stored_page_numbers,
            "_trace_ids": [],
            "parent_id": parent_id,
            "split_children": [],
            "is_split_parent": bool(is_split_parent),
            "color_index": color_index,
        }

    sections.append(_make_section(color_index=0))

    def _is_subsection(section):
        return bool(section.get("parent_id"))

    def _section_has_subsections(section):
        uid = section.get("uid")
        return any(child.get("parent_id") == uid for child in sections)

    def _top_level_sections():
        return [section for section in sections if not _is_subsection(section)]

    def _section_color_index(section, fallback_index=0):
        try:
            value = section.get("color_index")
            if value is not None:
                return int(value)
        except Exception:
            pass
        if _is_subsection(section):
            parent_id = section.get("parent_id")
            for candidate in sections:
                if candidate.get("uid") == parent_id:
                    return _section_color_index(candidate, fallback_index)
        try:
            section["color_index"] = int(fallback_index)
            return int(fallback_index)
        except Exception:
            return 0

    def _remove_subsections_for_parent(parent_section):
        parent_uid = parent_section.get("uid")
        if not parent_uid:
            return
        sections[:] = [section for section in sections if section.get("parent_id") != parent_uid]
        parent_section["split_children"] = []
        parent_section["is_split_parent"] = False
        _set_split_status("")

    def _parent_for_subsection(section):
        parent_id = section.get("parent_id")
        if not parent_id:
            return None
        for candidate in sections:
            if candidate.get("uid") == parent_id:
                return candidate
        return None

    def _split_children(parent_section):
        parent_uid = parent_section.get("uid")
        if not parent_uid:
            return []
        return [section for section in sections if section.get("parent_id") == parent_uid]

    def _set_split_status(message=""):
        try:
            new_value = str(message or "")
            if (split_status_var.get() or "") != new_value:
                split_status_var.set(new_value)
        except Exception:
            pass

    def _format_page_ranges(page_numbers):
        values = []
        for page_number in page_numbers or []:
            try:
                values.append(int(page_number))
            except Exception:
                pass
        if not values:
            return ""
        ranges = []
        start = prev = values[0]
        for value in values[1:]:
            if value == prev + 1:
                prev = value
                continue
            ranges.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = value
        ranges.append(str(start) if start == prev else f"{start}-{prev}")
        return ", ".join(ranges)

    def _refresh_section_page_labels():
        for section in sections:
            try:
                snap = _section_snapshot(section)
                try:
                    pages = int(snap.get("pages") or 0)
                except Exception:
                    pages = 0
                try:
                    start_page = int(snap.get("start") or 1)
                except Exception:
                    start_page = 1
                page_numbers = _section_page_numbers_from_snapshot(snap, start_page, pages) if pages > 0 else []
                if len(page_numbers) == pages:
                    section["page_numbers"] = list(page_numbers)
                label_var = section.get("pages_label_var")
                if label_var is not None:
                    label_var.set(_format_page_ranges(page_numbers))
            except Exception:
                pass

    def _coerce_positive_int(value):
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = int(text)
        except Exception:
            return None
        return parsed if parsed > 0 else None

    def _recalculate_split_for_parent(parent_section, edited_child=None, refresh_labels=True):
        if parent_section is None or not _section_has_subsections(parent_section):
            _set_split_status("")
            if refresh_labels:
                _refresh_section_page_labels()
            return True
        if split_recalc_state.get("active"):
            return True
        children = _split_children(parent_section)
        if len(children) < 2:
            _set_split_status("")
            return True
        split_recalc_state["active"] = True
        try:
            parent_snap = _section_snapshot(parent_section)
            parent_name = parent_snap.get("name") or "Section"
            fmt = parent_snap.get("format") if parent_snap.get("format") in format_multiples else "Broadsheet"
            multiple = format_multiples.get(fmt, 1)
            parent_pages = _coerce_positive_int(parent_snap.get("pages"))
            parent_start = _coerce_positive_int(parent_snap.get("start")) or 1
            if parent_pages is None:
                _set_split_status(f"{parent_name}: parent page count must be a positive number.")
                return False
            if parent_pages % multiple != 0:
                _set_split_status(f"{parent_name}: parent page count must be a multiple of {multiple} for {fmt}.")
                return False
            if edited_child in children:
                edit_index = children.index(edited_child)
                adjust_index = len(children) - 1 if edit_index != len(children) - 1 else len(children) - 2
                fixed_total = 0
                for idx, child in enumerate(children):
                    if idx == adjust_index:
                        continue
                    child_name = str(child["name_var"].get() or f"subsection {idx + 1}").strip()
                    value = _coerce_positive_int(child["pages_var"].get())
                    if value is None:
                        _set_split_status(f"{child_name}: page count must be a positive number.")
                        return False
                    fixed_total += value
                remainder = parent_pages - fixed_total
                if remainder <= 0:
                    _set_split_status(f"{parent_name}: subsection page counts exceed the parent total of {parent_pages} pages.")
                    return False
                try:
                    children[adjust_index]["pages_var"].set(str(remainder))
                except Exception:
                    pass
            counts = []
            errors = []
            for child in children:
                child_name = str(child["name_var"].get() or "Subsection").strip()
                value = _coerce_positive_int(child["pages_var"].get())
                if value is None:
                    errors.append(f"{child_name}: page count must be a positive number.")
                    continue
                if value % multiple != 0:
                    errors.append(f"{child_name}: page count must be a multiple of {multiple} for {fmt}.")
                counts.append(value or 0)
            if len(counts) == len(children) and sum(counts) != parent_pages:
                errors.append(f"{parent_name}: subsection page counts must add up to {parent_pages} pages.")
            if errors:
                _set_split_status(" ".join(errors))
                if refresh_labels:
                    _refresh_section_page_labels()
                return False
            page_groups = _split_page_number_groups(parent_start, parent_pages, fmt, counts)
            for child, page_group in zip(children, page_groups):
                child["page_numbers"] = list(page_group)
                if page_group:
                    try:
                        child["start_var"].set(str(min(page_group)))
                    except Exception:
                        pass
                try:
                    child["format_var"].set(fmt)
                except Exception:
                    pass
            parent_section["page_numbers"] = list(range(parent_start, parent_start + parent_pages))
            _set_split_status("")
            if refresh_labels:
                _refresh_section_page_labels()
            return True
        finally:
            split_recalc_state["active"] = False

    def _recalculate_all_splits(refresh_labels=True):
        ok = True
        _set_split_status("")
        for parent_section in list(sections):
            if parent_section.get("is_split_parent") and _section_has_subsections(parent_section):
                if not _recalculate_split_for_parent(parent_section, refresh_labels=False):
                    ok = False
                    break
        if refresh_labels:
            _refresh_section_page_labels()
        return ok

    def _bind_split_recalc_trace(section):
        if section.get("_split_trace_bound"):
            return
        def _schedule_recalc(*_args):
            if split_recalc_state.get("active"):
                return
            parent_section = _parent_for_subsection(section) if _is_subsection(section) else section
            try:
                dialog.after_idle(lambda p=parent_section, s=section: _recalculate_split_for_parent(p, edited_child=(s if _is_subsection(s) else None)))
            except Exception:
                _recalculate_split_for_parent(parent_section, edited_child=(section if _is_subsection(section) else None))
        for var_key in ("pages_var", "format_var"):
            try:
                trace_id = section[var_key].trace_add("write", _schedule_recalc)
                section.setdefault("_trace_ids", []).append((var_key, trace_id))
            except Exception:
                pass
        section["_split_trace_bound"] = True

    def _section_snapshot(section):
        return {
            "name": str(section["name_var"].get() or "").strip().upper(),
            "pages": str(section["pages_var"].get() or "").strip(),
            "start": str(section["start_var"].get() or "").strip(),
            "format": str(section["format_var"].get() or "Broadsheet").strip(),
            "page_numbers": list(section.get("page_numbers") or []),
        }

    def _section_page_numbers_from_snapshot(snap, start_page, pages):
        stored = []
        for page_number in (snap.get("page_numbers") or []):
            try:
                stored.append(int(page_number))
            except Exception:
                pass
        if len(stored) == int(pages):
            return stored
        return list(range(int(start_page), int(start_page) + int(pages)))

    def _balanced_legal_page_counts(total_pages, signature_count, multiple):
        total_units = int(total_pages) // int(multiple)
        signature_count = int(signature_count)
        if signature_count < 1 or signature_count > total_units:
            return None
        base_units, remainder = divmod(total_units, signature_count)
        return [int(multiple) * (base_units + (1 if idx < remainder else 0)) for idx in range(signature_count)]

    def _split_page_number_groups(start_page, total_pages, format_name, signature_counts):
        all_pages = list(range(int(start_page), int(start_page) + int(total_pages)))
        fmt = str(format_name or "Broadsheet").strip()
        if fmt == "Broadsheet":
            groups = []
            cursor = 0
            for count in signature_counts:
                groups.append(all_pages[cursor:cursor + int(count)])
                cursor += int(count)
            return groups
        groups = []
        low = 0
        high = len(all_pages)
        for count in signature_counts:
            count = int(count)
            outer_each_side = count // 2
            front = all_pages[low:low + outer_each_side]
            back = all_pages[high - outer_each_side:high]
            groups.append(front + back)
            low += outer_each_side
            high -= outer_each_side
        return groups

    def _ask_signature_count(section_name, pages, max_signatures):
        result = {"value": None}
        prompt = tk.Toplevel(dialog)
        set_window_icon(prompt)
        prompt.title("Split Section")
        try:
            prompt.transient(dialog)
            prompt.grab_set()
        except Exception:
            pass
        prompt.resizable(False, False)
        content = ttk.Frame(prompt, padding=16)
        content.pack(fill="both", expand=True)
        ttk.Label(
            content,
            text=f"Split section {section_name} ({pages} pages) into how many signatures?",
            font=(None, 10, "bold"),
            wraplength=360,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(content, text=f"Enter a number from 2 to {max_signatures}.").grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 10))
        count_var = tk.StringVar(value="2")
        count_entry = ttk.Entry(content, textvariable=count_var, width=8)
        count_entry.grid(row=2, column=0, sticky="w")
        error_var = tk.StringVar(value="")
        ttk.Label(content, textvariable=error_var, foreground="#c62828").grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        buttons = ttk.Frame(content)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(14, 0))

        def _confirm():
            raw = (count_var.get() or "").strip()
            try:
                value = int(raw)
            except Exception:
                error_var.set("Type a whole number.")
                return
            if value < 2 or value > int(max_signatures):
                error_var.set(f"Use a number from 2 to {max_signatures}.")
                return
            result["value"] = value
            try:
                prompt.destroy()
            except Exception:
                pass

        ttk.Button(buttons, text="Cancel", command=prompt.destroy, width=10).pack(side="right")
        ttk.Button(buttons, text="Confirm", command=_confirm, width=10).pack(side="right", padx=(0, 8))
        count_entry.bind("<Return>", lambda _event: (_confirm(), "break")[-1])
        try:
            prompt.update_idletasks()
            x = dialog.winfo_rootx() + max(40, (dialog.winfo_width() - prompt.winfo_reqwidth()) // 2)
            y = dialog.winfo_rooty() + max(40, (dialog.winfo_height() - prompt.winfo_reqheight()) // 2)
            prompt.geometry(f"+{x}+{y}")
        except Exception:
            pass
        count_entry.focus_set()
        try:
            dialog.wait_window(prompt)
        except Exception:
            pass
        return result.get("value")

    def split_section(section):
        snap = _section_snapshot(section)
        name = snap["name"] or "A"
        fmt = snap["format"] if snap["format"] in format_multiples else "Broadsheet"
        multiple = format_multiples.get(fmt, 1)
        try:
            pages = int(snap["pages"])
        except Exception:
            pages = 0
        try:
            start_page = int(snap["start"])
        except Exception:
            start_page = 0
        if pages <= 0 or start_page <= 0:
            messagebox.showerror("Split Section", f"Section {name} needs a valid page count and start page before it can be split.", parent=dialog)
            return
        if pages % multiple != 0:
            messagebox.showerror("Split Section", f"Section {name}: #Pages must be a multiple of {multiple} for {fmt} before it can be split.", parent=dialog)
            return
        if _is_subsection(section):
            messagebox.showinfo("Split Section", "Subsections are already signatures and cannot be split again.", parent=dialog)
            return
        max_signatures = min(4, pages // multiple)
        if max_signatures < 2:
            messagebox.showinfo("Split Section", f"Section {name} is already at the minimum legal size for {fmt}.", parent=dialog)
            return
        signature_count = _ask_signature_count(name, pages, max_signatures)
        if signature_count is None:
            return
        signature_counts = _balanced_legal_page_counts(pages, signature_count, multiple)
        if not signature_counts:
            messagebox.showerror("Split Section", f"Section {name} cannot be split into {signature_count} legal {fmt} signatures.", parent=dialog)
            return
        page_groups = _split_page_number_groups(start_page, pages, fmt, signature_counts)
        try:
            section_index = sections.index(section)
        except Exception:
            return
        _remove_subsections_for_parent(section)
        try:
            section_index = sections.index(section)
        except Exception:
            return
        base_color_index = _section_color_index(section, section_index)
        new_sections = []
        child_ids = []
        for idx, page_group in enumerate(page_groups, start=1):
            if not page_group:
                continue
            subsection_name = f"{name}{idx}"
            child = _make_section(
                name=subsection_name,
                pages=str(len(page_group)),
                start=str(min(page_group)),
                fmt=fmt,
                page_numbers=page_group,
                parent_id=section.get("uid"),
                color_index=base_color_index,
            )
            new_sections.append(child)
            child_ids.append(child.get("uid"))
        section["is_split_parent"] = True
        section["split_children"] = child_ids
        sections[section_index + 1:section_index + 1] = new_sections
        _recalculate_split_for_parent(section, refresh_labels=True)
        show_page_one()

    def _build_plan_display_groups():
        groups = []
        top_index = 0
        for section in sections:
            if _is_subsection(section):
                continue
            color_index = _section_color_index(section, top_index)
            top_index += 1
            snap = _section_snapshot(section)
            parent_name = snap.get("name") or chr(ord("A") + min(top_index - 1, 25))
            children = _split_children(section) if section.get("is_split_parent") and _section_has_subsections(section) else [section]
            child_items = []
            for child in children:
                child_snap = _section_snapshot(child)
                child_name = child_snap.get("name") or parent_name
                try:
                    pages = int(child_snap.get("pages") or 0)
                except Exception:
                    pages = 0
                try:
                    start_page = int(child_snap.get("start") or snap.get("start") or 1)
                except Exception:
                    start_page = 1
                fmt = child_snap.get("format") if child_snap.get("format") in format_multiples else (snap.get("format") if snap.get("format") in format_multiples else "Broadsheet")
                child_items.append({
                    "name": child_name,
                    "pages": pages,
                    "start": start_page,
                    "format": fmt,
                    "page_numbers": _section_page_numbers_from_snapshot(child_snap, start_page, pages) if pages > 0 else [],
                    "is_subsection": _is_subsection(child),
                    "parent_name": parent_name,
                    "color_index": color_index,
                })
            groups.append({
                "name": parent_name,
                "format": snap.get("format") if snap.get("format") in format_multiples else "Broadsheet",
                "pages": _coerce_positive_int(snap.get("pages")) or 0,
                "color_index": color_index,
                "sections": child_items,
                "is_split": bool(section.get("is_split_parent") and _section_has_subsections(section)),
            })
        return groups

    def _collect_plan_page_one_errors(update_status=True):
        errors = []
        issue_text = (issue_date_var.get() or "").strip()
        publication_text = normalize_publication_name(publication_var.get())
        if not issue_text:
            errors.append("Issue Date is required.")
        elif parse_issue_date_flexible(issue_text) is None:
            errors.append("Issue Date must be a valid date.")
        if not publication_text:
            errors.append("Publication is required.")
        split_ok = _recalculate_all_splits(refresh_labels=True)
        split_message = (split_status_var.get() or "").strip()
        if not split_ok and split_message:
            errors.append(split_message)
        if not sections:
            errors.append("Add at least one section.")
        for index, section in enumerate(sections, start=1):
            if section.get("is_split_parent") and _section_has_subsections(section):
                continue
            snap = _section_snapshot(section)
            name = snap["name"] or chr(ord("A") + min(index - 1, 25))
            fmt = snap["format"] if snap["format"] in format_multiples else "Broadsheet"
            multiple = format_multiples.get(fmt, 1)
            try:
                pages = int(snap["pages"])
            except Exception:
                pages = None
            if pages is None or pages <= 0:
                errors.append(f"Section {name}: #Pages must be a positive number.")
            elif pages % multiple != 0:
                errors.append(f"Section {name}: #Pages must be a multiple of {multiple} for {fmt}.")
        if update_status:
            _set_split_status(" ".join(errors[:3]))
        return errors

    def _validate_plan_inputs():
        errors = _collect_plan_page_one_errors(update_status=True)
        if errors:
            messagebox.showerror("Plan Check", "Please fix the following before continuing:\n\n" + "\n".join(f"• {item}" for item in errors), parent=dialog)
            return None
        normalized = []
        issue_text = normalize_issue_date_mmddyyyy((issue_date_var.get() or "").strip())
        product_text = normalize_publication_name(publication_var.get())
        issue_date_var.set(issue_text)
        publication_var.set(product_text)
        for index, section in enumerate(sections, start=1):
            if section.get("is_split_parent") and _section_has_subsections(section):
                continue
            snap = _section_snapshot(section)
            name = snap["name"] or chr(ord("A") + min(index - 1, 25))
            try:
                section["name_var"].set(name)
            except Exception:
                pass
            fmt = snap["format"] if snap["format"] in format_multiples else "Broadsheet"
            try:
                pages = int(snap["pages"])
            except Exception:
                pages = 0
            try:
                start_page = int(snap["start"])
            except Exception:
                start_page = 1
            if start_page <= 0:
                start_page = 1
            normalized.append({
                "name": name,
                "pages": pages,
                "start": start_page,
                "format": fmt,
                "page_numbers": _section_page_numbers_from_snapshot(snap, start_page, pages),
                "is_subsection": _is_subsection(section),
                "parent_name": (_parent_for_subsection(section)["name_var"].get() if _is_subsection(section) and _parent_for_subsection(section) else ""),
                "color_index": _section_color_index(section, index - 1),
            })
        display_groups = _build_plan_display_groups()
        return {"issue_date": issue_text, "publication": product_text, "sections": normalized, "section_groups": display_groups}

    def _bind_page_one_validation_trace(var):
        try:
            if getattr(var, "_plan_validation_trace", False):
                return
        except Exception:
            pass
        def _schedule(*_args):
            if plan_validation_state.get("active"):
                return
            prior_after_id = plan_validation_state.get("after_id")
            if prior_after_id is not None:
                try:
                    dialog.after_cancel(prior_after_id)
                except Exception:
                    pass
                plan_validation_state["after_id"] = None
            try:
                plan_validation_state["after_id"] = dialog.after(80, _sync_page_one_validation)
            except Exception:
                _sync_page_one_validation()
        try:
            var.trace_add("write", _schedule)
            var._plan_validation_trace = True
        except Exception:
            pass

    def _sync_page_one_validation():
        if plan_validation_state.get("active"):
            return False
        plan_validation_state["after_id"] = None
        plan_validation_state["active"] = True
        try:
            next_button = getattr(dialog, "_plan_next_button", None)
            errors = _collect_plan_page_one_errors(update_status=True)
            if next_button is not None:
                try:
                    next_button.state(["disabled"] if errors else ["!disabled"])
                except Exception:
                    try:
                        next_button.configure(state=("disabled" if errors else "normal"))
                    except Exception:
                        pass
            return not errors
        finally:
            plan_validation_state["active"] = False

    def _load_manifest():
        manifest_path = filedialog.askopenfilename(
            parent=dialog,
            title="Select Manifest",
            filetypes=[("Manifest files", "*.pdf *.msg"), ("PDF files", "*.pdf"), ("Outlook messages", "*.msg"), ("All files", "*.*")],
        )
        if manifest_path:
            _load_manifest_from_path_in_dialog(dialog, manifest_path)

    def show_page_one():
        header_var.set("Plan Layout - Sections")
        _clear_frame(body)
        _clear_footer()
        body.rowconfigure(0, weight=0)
        body.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=1)
        top = ttk.Frame(body)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        # Manifest load button row
        manifest_frame = ttk.Frame(top)
        manifest_frame.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        manifest_frame.columnconfigure(0, weight=1)
        load_btn = ttk.Button(
            manifest_frame, text="Load Manifest\u2026",
            command=_load_manifest, width=20,
        )
        load_btn.pack(side="left", padx=(0, 12))
        drop_label = tk.Label(
            manifest_frame,
            text="or drag & drop a manifest PDF or email here",
            foreground="#888888", font=(None, 9, "italic"),
            cursor="hand2",
            bg="#f7f7f7",
        )
        drop_label.pack(side="left", fill="x", expand=True)
        drop_label.bind("<Button-1>", lambda _e: _load_manifest())
        if is_admin():
            ttk.Button(
                manifest_frame, text="Translation Table\u2026",
                command=lambda: _show_translation_table_dialog(dialog),
                width=18,
            ).pack(side="right", padx=(12, 0))

        # Issue Date and Publication row
        entry_row = ttk.Frame(top)
        entry_row.grid(row=1, column=0, columnspan=4, sticky="ew")
        entry_row.columnconfigure(1, weight=1)
        entry_row.columnconfigure(3, weight=1)
        ttk.Label(entry_row, text="Issue Date:", font=(None, 10, "bold")).grid(row=0, column=0, sticky="w")
        issue_entry = ttk.Entry(entry_row, textvariable=issue_date_var, width=18)
        issue_entry.grid(row=0, column=1, sticky="ew", padx=(8, 24))
        _bind_issue_date_formatting(issue_entry)
        issue_entry.bind("<Button-1>", lambda _event, w=issue_entry: _open_plan_issue_date_picker(w), add="+")
        _bind_page_one_validation_trace(issue_date_var)
        _bind_page_one_validation_trace(publication_var)
        ttk.Label(entry_row, text="Publication:", font=(None, 10, "bold")).grid(row=0, column=2, sticky="w")
        ttk.Entry(entry_row, textvariable=publication_var, width=34).grid(row=0, column=3, sticky="ew", padx=(8, 0))

        canvas = tk.Canvas(body, highlightthickness=0, bd=0, background="#f7f7f7")
        canvas.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(14, 0))
        canvas.configure(yscrollcommand=scrollbar.set)
        section_frame = tk.Frame(canvas, background="#f7f7f7", bd=0, highlightthickness=0)
        section_window = canvas.create_window((0, 0), window=section_frame, anchor="nw")
        section_frame.columnconfigure(0, weight=1)
        section_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(section_window, width=e.width))

        column_settings = (
            (0, 14, 18),
            (1, 12, 18),
            (2, 28, 18),
            (3, 8, 24),
            (4, 16, 18),
            (5, 12, 0),
        )
        header_positions = {
            "Section": 6,
            "#Pages": 110,
            "Pages": 204,
            "Split": 430,
            "Format": 510,
        }
        _recalculate_all_splits(refresh_labels=True)
        for col, _width, _pad in column_settings:
            try:
                section_frame.columnconfigure(col, weight=0)
            except Exception:
                pass
        header_frame = tk.Frame(section_frame, background="#f7f7f7", bd=0, highlightthickness=0, height=24)
        header_frame.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0, 5))
        header_frame.grid_propagate(False)
        for title, xpos in header_positions.items():
            label = tk.Label(header_frame, text=title, font=(None, 10, "bold"), anchor="w", background="#f7f7f7")
            label.place(x=xpos, y=2)

        def delete_section(section):
            remaining_top_level = [candidate for candidate in sections if candidate is not section and not _is_subsection(candidate)]
            if (not _is_subsection(section)) and not remaining_top_level:
                messagebox.showinfo("Plan Layout", "At least one section is required.", parent=dialog)
                return
            if section in sections:
                if not _is_subsection(section):
                    _remove_subsections_for_parent(section)
                else:
                    parent_id = section.get("parent_id")
                    for candidate in sections:
                        if candidate.get("uid") == parent_id:
                            candidate["split_children"] = [uid for uid in candidate.get("split_children", []) if uid != section.get("uid")]
                            if not any(child.get("parent_id") == parent_id and child is not section for child in sections):
                                candidate["is_split_parent"] = False
                            break
                try:
                    sections.remove(section)
                except ValueError:
                    pass
            show_page_one()

        top_level_seen = 0
        for row_index, section in enumerate(sections, start=1):
            if not _is_subsection(section):
                color_index = _section_color_index(section, top_level_seen)
                top_level_seen += 1
            else:
                color_index = _section_color_index(section, row_index - 1)
            row_bg = section_palette[color_index % len(section_palette)]
            row_frame = tk.Frame(section_frame, background=row_bg, bd=0, highlightthickness=0, padx=6, pady=4)
            row_frame.grid(row=row_index, column=0, columnspan=6, sticky="ew", pady=(0, 2 if _is_subsection(section) else 5))
            for col, _width, _pad in column_settings:
                try:
                    row_frame.columnconfigure(col, weight=0)
                except Exception:
                    pass
            section_cell = tk.Frame(row_frame, background=row_bg, bd=0, highlightthickness=0)
            section_cell.grid(row=0, column=0, sticky="w", padx=(0, 18))
            if _is_subsection(section):
                tk.Label(section_cell, text="↳", background=row_bg, font=(None, 10, "bold"), width=2, anchor="w").pack(side="left")
                tk.Entry(section_cell, textvariable=section["name_var"], width=11).pack(side="left")
            else:
                tk.Entry(section_cell, textvariable=section["name_var"], width=14).pack(side="left")
            _bind_split_recalc_trace(section)
            _bind_page_one_validation_trace(section["pages_var"])
            _bind_page_one_validation_trace(section["format_var"])
            tk.Entry(row_frame, textvariable=section["pages_var"], width=12).grid(row=0, column=1, sticky="w", padx=(0, 18))
            tk.Label(row_frame, textvariable=section["pages_label_var"], background=row_bg, width=28, anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 18))
            split_button = ttk.Button(row_frame, text=("ReSplit..." if section.get("is_split_parent") and _section_has_subsections(section) else "Split..."), command=lambda s=section: split_section(s), width=8)
            split_button.grid(row=0, column=3, sticky="w", padx=(0, 24))
            if _is_subsection(section):
                try:
                    split_button.state(["disabled"])
                except Exception:
                    split_button.configure(state="disabled")
            ttk.Combobox(row_frame, textvariable=section["format_var"], values=format_values, state="readonly", width=14).grid(row=0, column=4, sticky="w", padx=(0, 18))
            ttk.Button(row_frame, text="x Delete", command=lambda s=section: delete_section(s), width=10).grid(row=0, column=5, sticky="w")

        def add_section():
            top_sections = _top_level_sections()
            previous = top_sections[-1]["name_var"].get() if top_sections else "A"
            sections.append(_make_section(name=_next_section_name(previous), color_index=len(top_sections)))
            show_page_one()

        status_bar = tk.Label(body, textvariable=split_status_var, background="#c62828", foreground="white", anchor="w", padx=8, pady=4)
        def _sync_status_bar(*_args):
            message = (split_status_var.get() or "").strip()
            if message:
                try:
                    status_bar.grid(row=2, column=0, sticky="ew", pady=(6, 0))
                except Exception:
                    pass
            else:
                try:
                    status_bar.grid_remove()
                except Exception:
                    pass
        split_status_var.trace_add("write", _sync_status_bar)
        _sync_status_bar()

        ttk.Button(footer_left, text="+ Add Section", command=add_section, width=16).pack(side="left", padx=(0, 8))
        ttk.Button(footer_right, text="Cancel", command=dialog.destroy, width=12).pack(side="right")
        next_button = ttk.Button(footer_right, text="Next", command=show_page_two_from_validation, width=12)
        next_button.pack(side="right", padx=(0, 8))
        dialog._plan_next_button = next_button
        try:
            dialog.after_idle(_sync_page_one_validation)
        except Exception:
            _sync_page_one_validation()
        _bind_mousewheel_to_canvas(canvas, canvas)
        _bind_mousewheel_to_canvas(section_frame, canvas)

    def _plan_group_color_state(group):
        section_name, pages_tuple = group
        if group in page_color_state:
            return bool(page_color_state.get(group, False))
        return any(bool(page_color_state.get((section_name, int(page)), False)) for page in pages_tuple)

    # Backward-compatible shared helper used by later Plan wizard screens.
    def _group_color_state(group):
        return _plan_group_color_state(group)

    def _draw_color_box(canvas, is_color):
        canvas.delete("all")
        if is_color:
            for idx, color in enumerate(("#00aeef", "#ec008c", "#fff200", "#111111")):
                canvas.create_rectangle(idx * 9, 0, (idx + 1) * 9, 22, fill=color, outline=color)
            canvas.create_rectangle(0, 0, 36, 22, outline="#222222")
        else:
            canvas.create_rectangle(0, 0, 36, 22, fill="#111111", outline="#111111")

    def show_page_two(plan):
        header_var.set("Plan Layout - Color Pages")
        _clear_frame(body)
        _clear_footer()
        body.rowconfigure(0, weight=1)
        body.rowconfigure(1, weight=0)
        body.columnconfigure(0, weight=1)
        canvas = tk.Canvas(body, highlightthickness=0, bd=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas_bg = "#f7f7f7"
        canvas.configure(yscrollcommand=scrollbar.set, background=canvas_bg)
        list_frame = tk.Frame(canvas, background=canvas_bg, bd=0, highlightthickness=0)
        list_window = canvas.create_window((0, 0), window=list_frame, anchor="nw")

        def _sync_canvas_scroll_region(_event=None):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception:
                pass

        page_widgets = {}
        selected_items = []
        section_count_for_layout = len(plan.get("section_groups") or plan.get("sections", []) or [])
        section_row_count = max(1, int((section_count_for_layout + 3) // 4))

        def _sync_list_frame_size(event=None):
            try:
                requested_height = int(list_frame.winfo_reqheight())
            except Exception:
                requested_height = 0
            try:
                viewport_height = int(event.height)
                viewport_width = int(event.width)
            except Exception:
                try:
                    viewport_height = int(canvas.winfo_height())
                    viewport_width = int(canvas.winfo_width())
                except Exception:
                    viewport_height = requested_height
                    viewport_width = 1
            expand_rows = requested_height <= viewport_height
            for grid_row in range(section_row_count):
                try:
                    list_frame.rowconfigure(grid_row, weight=(1 if expand_rows else 0), uniform="plan_section_rows")
                except Exception:
                    pass
            try:
                canvas.itemconfigure(list_window, width=viewport_width, height=(viewport_height if expand_rows else requested_height))
            except Exception:
                pass
            _sync_canvas_scroll_region()

        list_frame.bind("<Configure>", _sync_canvas_scroll_region)
        canvas.bind("<Configure>", _sync_list_frame_size)
        for grid_col in range(4):
            try:
                list_frame.columnconfigure(grid_col, weight=1, uniform="plan_section_columns")
            except Exception:
                pass
        for grid_row in range(section_row_count):
            try:
                list_frame.rowconfigure(grid_row, weight=0, uniform="plan_section_rows")
            except Exception:
                pass

        def _item_label(group):
            _section_name, pages_tuple = group
            pages_tuple = tuple(int(p) for p in pages_tuple)
            if len(pages_tuple) > 1:
                return "/".join(str(p) for p in pages_tuple) + " DT"
            return str(pages_tuple[0])

        def _group_color_state(group):
            section_name, pages_tuple = group
            if group in page_color_state:
                return bool(page_color_state.get(group, False))
            return any(bool(page_color_state.get((section_name, int(page)), False)) for page in pages_tuple)

        def _set_group_color_state(group, value):
            section_name, pages_tuple = group
            page_color_state[group] = bool(value)
            for page in pages_tuple:
                page_color_state[(section_name, int(page))] = bool(value)

        def draw_one(key):
            widgets = page_widgets.get(key)
            if not widgets:
                return
            swatch, label, row_frame, section_bg = widgets
            is_color = _group_color_state(key)
            selected = key in selected_items
            row_bg = "#fff2a8" if selected else section_bg
            try:
                row_frame.configure(background=row_bg)
                label.configure(background=row_bg)
                swatch.configure(background=row_bg)
            except Exception:
                pass
            _draw_color_box(swatch, is_color)
            label.configure(text=f"{_item_label(key)} ({'4C' if is_color else 'K'})")

        def draw_all():
            for key in list(page_widgets):
                draw_one(key)

        def set_all(value):
            for key in list(page_widgets):
                _set_group_color_state(key, bool(value))
            draw_all()

        def set_section(section_name, value):
            for key in list(page_widgets):
                if key[0] == section_name:
                    _set_group_color_state(key, bool(value))
            draw_all()

        def _selected_single_pages_for_section(section_name):
            return [
                key for key in selected_items
                if key[0] == section_name and len(key[1]) == 1
            ]

        def _clear_selection_for_section(section_name):
            selected_items[:] = [key for key in selected_items if key[0] != section_name]

        def _selected_is_valid_double_truck_pair(section_name=None):
            if section_name is None:
                if not selected_items:
                    return False
                section_names = {key[0] for key in selected_items if len(key[1]) == 1}
                if len(section_names) != 1:
                    return False
                section_name = next(iter(section_names))
            section_selected = _selected_single_pages_for_section(section_name)
            return len(section_selected) == 2

        def _select_item(key, add=True):
            section_name, pages_tuple = key
            if not add:
                selected_items.clear()
            if key in selected_items:
                selected_items.remove(key)
            else:
                if len(pages_tuple) > 1:
                    _clear_selection_for_section(section_name)
                    selected_items.append(key)
                else:
                    section_selected = _selected_single_pages_for_section(section_name)
                    if len(section_selected) >= 2:
                        try:
                            selected_items.remove(section_selected[1])
                        except Exception:
                            pass
                    selected_items[:] = [
                        existing for existing in selected_items
                        if not (existing[0] == section_name and len(existing[1]) > 1)
                    ]
                    selected_items.append(key)
            draw_all()

        def _show_context_menu(event, key):
            section_name, pages_tuple = key
            menu = None
            if len(pages_tuple) > 1:
                _clear_selection_for_section(section_name)
                selected_items.append(key)
                draw_all()
                menu = tk.Menu(dialog, tearoff=0)
                menu.add_command(label="Single Pages", command=lambda name=section_name: _set_selected_single_pages(name))
            else:
                if key not in selected_items:
                    _select_item(key, add=True)
                if _selected_is_valid_double_truck_pair(section_name):
                    menu = tk.Menu(dialog, tearoff=0)
                    menu.add_command(label="Set Double Truck (DT)", command=lambda name=section_name: _set_selected_double_truck(name))
            if menu is None:
                return "break"
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    menu.grab_release()
                except Exception:
                    pass
            return "break"

        def _set_selected_double_truck(section_name=None):
            if section_name is None:
                if not selected_items:
                    return
                section_name = selected_items[0][0]
            if not _selected_is_valid_double_truck_pair(section_name):
                return
            section_selected = _selected_single_pages_for_section(section_name)
            pages_tuple = tuple(sorted(int(key[1][0]) for key in section_selected))
            if len(pages_tuple) != 2:
                return
            color_value = any(_group_color_state(group) for group in section_selected)
            for page in pages_tuple:
                page_group_state[(section_name, int(page))] = pages_tuple
                page_color_state.pop((section_name, int(page)), None)
            new_group = (section_name, pages_tuple)
            page_color_state[new_group] = color_value
            _clear_selection_for_section(section_name)
            _rebuild_color_sections()

        def _set_selected_single_pages(section_name=None):
            if section_name is None:
                if not selected_items:
                    return
                section_name = selected_items[0][0]
            groups = [
                group for group in list(selected_items)
                if group[0] == section_name and len(group[1]) > 1
            ]
            if not groups:
                return
            _clear_selection_for_section(section_name)
            for group in groups:
                _section_name, pages_tuple = group
                color_value = _group_color_state(group)
                page_color_state.pop(group, None)
                for page in pages_tuple:
                    page_group_state.pop((section_name, int(page)), None)
                    single_key = (section_name, (int(page),))
                    page_color_state[single_key] = color_value
            _rebuild_color_sections()

        def _logical_groups_for_section(section):
            section_name = section.get("name") or ""
            groups = []
            seen = set()
            for page_number in section.get("page_numbers", []):
                page_number = int(page_number)
                group_pages = page_group_state.get((section_name, page_number))
                if group_pages:
                    group_pages = tuple(sorted(int(p) for p in group_pages))
                else:
                    group_pages = (page_number,)
                key = (section_name, group_pages)
                if key not in seen:
                    seen.add(key)
                    groups.append(key)
            return groups

        def _rebuild_color_sections():
            for child in list_frame.winfo_children():
                child.destroy()
            page_widgets.clear()
            display_groups = plan.get("section_groups") or [
                {
                    "name": section.get("name") or f"Section {idx + 1}",
                    "format": section.get("format") or "",
                    "pages": section.get("pages") or 0,
                    "color_index": idx,
                    "sections": [section],
                    "is_split": False,
                }
                for idx, section in enumerate(plan.get("sections", []) or [])
            ]
            for section_index, group in enumerate(display_groups):
                group_name = group.get("name") or f"Section {section_index + 1}"
                section_grid_row = int(section_index) // 4
                section_grid_col = int(section_index) % 4
                section_bg = section_palette[int(group.get("color_index", section_index)) % len(section_palette)]
                section_box = tk.Frame(list_frame, background=section_bg, bd=1, relief="solid", highlightthickness=0, padx=10, pady=10)
                section_box.grid(row=section_grid_row, column=section_grid_col, sticky="nsew", pady=(0, 12), padx=(0, 12))
                section_box.columnconfigure(1, weight=1)

                group_format = str(group.get('format') or '').strip()
                group_format_label = "BS" if group_format == "Broadsheet" else group_format
                header_text = f"{group_name} - {group_format_label} - {group.get('pages')} pgs"
                tk.Label(section_box, text=header_text, background=section_bg, font=(None, 10, "bold"), anchor="w").grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

                child_sections = list(group.get("sections") or [])
                def _set_group_value(value, child_sections=child_sections):
                    for child in child_sections:
                        set_section(child.get("name") or "", value)
                all_row = tk.Frame(section_box, background=section_bg, bd=0, highlightthickness=0)
                all_row.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
                tk.Label(all_row, text="All:", font=(None, 10, "bold"), background=section_bg).pack(side="left", padx=(0, 8))
                all_color = tk.Canvas(all_row, width=36, height=22, highlightthickness=1, highlightbackground="#777777", bd=0, cursor="hand2", background=section_bg)
                all_color.pack(side="left", padx=(0, 6))
                _draw_color_box(all_color, True)
                tk.Label(all_row, text="Color", cursor="hand2", background=section_bg).pack(side="left", padx=(0, 14))
                all_bw = tk.Canvas(all_row, width=36, height=22, highlightthickness=1, highlightbackground="#777777", bd=0, cursor="hand2", background=section_bg)
                all_bw.pack(side="left", padx=(0, 6))
                _draw_color_box(all_bw, False)
                tk.Label(all_row, text="B/W", cursor="hand2", background=section_bg).pack(side="left")
                all_color.bind("<Button-1>", lambda _event, fn=_set_group_value: fn(True))
                all_bw.bind("<Button-1>", lambda _event, fn=_set_group_value: fn(False))

                row_idx = 2
                for child_section in child_sections:
                    child_name = child_section.get("name") or group_name
                    child_format = str(child_section.get('format') or group_format).strip()
                    child_format_label = "BS" if child_format == "Broadsheet" else child_format
                    child_ranges = _format_page_ranges(child_section.get("page_numbers", []))
                    if group.get("is_split"):
                        child_header_text = f"↳ {child_name} - {child_format_label} - {child_section.get('pages')} pgs"
                        if child_ranges:
                            child_header_text += f" ({child_ranges})"
                        tk.Label(section_box, text=child_header_text, background=section_bg, font=(None, 9, "bold"), anchor="w").grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=(6, 3))
                        row_idx += 1
                    groups = _logical_groups_for_section(child_section)
                    for key in groups:
                        _set_group_color_state(key, _group_color_state(key))
                        row_frame = tk.Frame(section_box, background=section_bg, bd=0, highlightthickness=0)
                        row_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", pady=2, padx=(18 if group.get("is_split") else 0, 0))
                        row_idx += 1
                        swatch = tk.Canvas(row_frame, width=36, height=22, highlightthickness=1, highlightbackground="#777777", bd=0, cursor="hand2", background=section_bg)
                        swatch.pack(side="left", padx=(0, 8))
                        label = tk.Label(row_frame, text="", cursor="hand2", background=section_bg, anchor="w")
                        label.pack(side="left")
                        page_widgets[key] = (swatch, label, row_frame, section_bg)
                        def toggle_color(k=key):
                            _set_group_color_state(k, not _group_color_state(k))
                            draw_one(k)
                        def select_item(k=key):
                            _select_item(k, add=True)
                        swatch.bind("<Button-1>", lambda event, fn=toggle_color: fn())
                        label.bind("<Button-1>", lambda event, fn=select_item: fn())
                        row_frame.bind("<Button-1>", lambda event, fn=select_item: fn())
                        for widget in (swatch, label, row_frame):
                            widget.bind("<Button-3>", lambda event, k=key: _show_context_menu(event, k))
                section_box.rowconfigure(max(1, row_idx), weight=1)
            draw_all()
            try:
                if '_finish_initial_color_page_layout' in locals():
                    canvas.after_idle(_finish_initial_color_page_layout)
            except Exception:
                pass

        _rebuild_color_sections()

        ttk.Button(footer_left, text="All Color", command=lambda: set_all(True), width=12).pack(side="left", padx=(0, 8))
        ttk.Button(footer_left, text="All B/W", command=lambda: set_all(False), width=12).pack(side="left", padx=(0, 8))
        ttk.Button(footer_right, text="Cancel", command=dialog.destroy, width=12).pack(side="right")
        ttk.Button(footer_right, text="Next", command=lambda p=plan: show_page_three(p), width=12).pack(side="right", padx=(0, 8))
        ttk.Button(footer_right, text="Back", command=show_page_one, width=12).pack(side="right", padx=(0, 8))
        draw_all()

        def _finish_initial_color_page_layout():
            try:
                canvas.update_idletasks()
                list_frame.update_idletasks()
            except Exception:
                pass
            try:
                _sync_list_frame_size()
            except Exception:
                pass
            _bind_mousewheel_to_canvas(canvas, canvas)
            _bind_mousewheel_to_canvas(list_frame, canvas)

        try:
            canvas.after_idle(_finish_initial_color_page_layout)
        except Exception:
            _finish_initial_color_page_layout()

    def _plan_assignable_sections(plan):
        items = []
        for group in plan.get("section_groups") or []:
            children = group.get("sections") or []
            if group.get("is_split"):
                for child in children:
                    items.append(dict(child))
            elif children:
                items.append(dict(children[0]))
        if not items:
            items = [dict(section) for section in (plan.get("sections") or [])]
        return items

    def _press_run_summary(run, assignable_sections):
        selected = []
        for section in assignable_sections:
            name = section.get("name") or ""
            var = run.get("section_vars", {}).get(name)
            try:
                if var is not None and var.get():
                    selected.append(f"{name} - {section.get('pages')}p")
            except Exception:
                pass
        return ", ".join(selected) if selected else "No sections assigned"

    def _generate_run_name(run, assignable_sections, plan):
        selected = []
        for group in (plan.get("section_groups") or []):
            children = group.get("sections") or []
            if group.get("is_split"):
                checked_children = []
                for child in children:
                    child_name = child.get("name") or ""
                    var = run.get("section_vars", {}).get(child_name)
                    if var is not None and var.get():
                        checked_children.append(child)
                if not checked_children:
                    continue
                if len(checked_children) == len(children):
                    selected.append(group.get("name", ""))
                else:
                    for child in checked_children:
                        child_name = child.get("name", "")
                        page_numbers = child.get("page_numbers", [])
                        page_text = _format_page_ranges(page_numbers)
                        selected.append(f"{child_name} {page_text}" if page_text else child_name)
            else:
                section = children[0] if children else None
                if not section:
                    continue
                name = section.get("name") or ""
                var = run.get("section_vars", {}).get(name)
                if var is not None and var.get():
                    selected.append(group.get("name", name))
        if not selected:
            return "(empty)"
        return " & ".join(selected)

    def _update_run_name(run, assignable_sections, plan):
        run["name"].set(_generate_run_name(run, assignable_sections, plan))

    def _default_press_runs_for_plan(plan):
        run = {
            "name": tk.StringVar(value="Run 1"),
            "press_var": tk.StringVar(value="Press 1"),
            "section_vars": {},
        }
        for section in _plan_assignable_sections(plan):
            name = section.get("name") or ""
            run["section_vars"][name] = tk.BooleanVar(value=True)
        return [run]

    def show_page_three(plan, press_runs=None):
        header_var.set("Plan Layout - Press Runs")
        _clear_frame(body)
        _clear_footer()
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        assignable_sections = _plan_assignable_sections(plan)
        if press_runs is None:
            press_runs = _default_press_runs_for_plan(plan)
        canvas = tk.Canvas(body, highlightthickness=0, bd=0, background="#f7f7f7")
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        frame = tk.Frame(canvas, background="#f7f7f7", bd=0, highlightthickness=0, padx=12, pady=12)
        win_id = canvas.create_window((0,0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        ttk.Label(frame, text="Create press runs and assign each section or subsection to any run that needs it.", font=(None, 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))

        def add_run():
            idx = len(press_runs) + 1
            run = {"name": tk.StringVar(value=f"Run {idx}"), "press_var": tk.StringVar(value="Press 1"), "section_vars": {}}
            for section in assignable_sections:
                name = section.get("name") or ""
                run["section_vars"][name] = tk.BooleanVar(value=False)
            press_runs.append(run)
            show_page_three(plan, press_runs)

        def delete_run(run):
            if len(press_runs) <= 1:
                messagebox.showinfo("Plan Layout", "At least one press run is required.", parent=dialog)
                return
            try:
                press_runs.remove(run)
            except Exception:
                pass
            show_page_three(plan, press_runs)

        row = 1
        for run_index, run in enumerate(press_runs, start=1):
            box = ttk.LabelFrame(frame, text=f"Press Run {run_index}", padding=10)
            box.grid(row=row, column=0, sticky="ew", pady=(0, 12))
            box.columnconfigure(1, weight=1)
            ttk.Label(box, text="Name:").grid(row=0, column=0, sticky="w")
            name_entry = ttk.Entry(box, textvariable=run["name"], width=18, state="readonly")
            name_entry.grid(row=0, column=1, sticky="w", padx=(6, 18))
            ttk.Label(box, text="Press:").grid(row=0, column=2, sticky="w")
            ttk.Combobox(box, textvariable=run["press_var"], values=("Press 1", "Press 2"), state="readonly", width=10).grid(row=0, column=3, sticky="w", padx=(6, 18))
            ttk.Button(box, text="x Delete", command=lambda r=run: delete_run(r), width=10).grid(row=0, column=4, sticky="e")
            ttk.Label(box, text="Assign sections:", font=(None, 9, "bold")).grid(row=1, column=0, columnspan=5, sticky="w", pady=(10, 4))
            for idx, section in enumerate(assignable_sections):
                name = section.get("name") or ""
                if name not in run["section_vars"]:
                    run["section_vars"][name] = tk.BooleanVar(value=False)
                def _make_section_trace(r, section_name, run_plan=plan):
                    section_var = r["section_vars"].get(section_name)
                    if section_var:
                        def _on_change(*_args, _r=r, _as=assignable_sections, _plan=run_plan):
                            _update_run_name(_r, _as, _plan)
                        try:
                            section_var.trace_add("write", _on_change)
                        except Exception:
                            pass
                _make_section_trace(run, name)
                page_numbers = section.get("page_numbers", [])
                page_range_text = _format_page_ranges(page_numbers)
                label = f"{name} - {section.get('format')} - {section.get('pages')} pgs  ({page_range_text})" if page_range_text else f"{name} - {section.get('format')} - {section.get('pages')} pgs"
                ttk.Checkbutton(box, text=label, variable=run["section_vars"][name]).grid(row=2 + idx, column=0, columnspan=5, sticky="w", pady=1)
            row += 1
        for r in press_runs:
            _update_run_name(r, assignable_sections, plan)
        ttk.Button(footer_left, text="+ Add Press Run", command=add_run, width=18).pack(side="left", padx=(0, 8))
        ttk.Button(footer_right, text="Cancel", command=dialog.destroy, width=12).pack(side="right")
        ttk.Button(footer_right, text="Next", command=lambda p=plan, r=press_runs: show_page_four(p, r), width=12).pack(side="right", padx=(0, 8))
        ttk.Button(footer_right, text="Back", command=lambda p=plan: show_page_two(p), width=12).pack(side="right", padx=(0, 8))
        _bind_mousewheel_to_canvas(canvas, canvas)
        _bind_mousewheel_to_canvas(frame, canvas)

    def _press_run_sections(run, assignable_sections):
        selected = []
        for section in assignable_sections:
            name = section.get("name") or ""
            var = run.get("section_vars", {}).get(name)
            try:
                if var is not None and var.get():
                    selected.append(dict(section))
            except Exception:
                pass
        return selected

    def _press_run_format(sections):
        for section in sections:
            fmt = str(section.get("format") or "").strip()
            if fmt:
                return fmt
        return "Broadsheet"

    def _planned_color_pages_for_sections(sections):
        wanted = []
        for section_index, section in enumerate(sections):
            section_name = section.get("name") or ""
            section_pages = []
            for page_number in section.get("page_numbers", []) or []:
                try:
                    section_pages.append(int(page_number))
                except Exception:
                    pass
            for page_offset, page_number in enumerate(section_pages, start=1):
                group_pages = page_group_state.get((section_name, page_number))
                if group_pages:
                    group = (section_name, tuple(sorted(int(p) for p in group_pages)))
                else:
                    group = (section_name, (page_number,))
                if _group_color_state(group):
                    wanted.append({
                        "section_index": int(section_index),
                        "section_name": section_name,
                        "page": page_number,
                        "template_page": int(page_offset),
                    })
        return wanted

    def _section_aliases_for_template_index(template_data, run_sections, section_index):
        aliases = set()
        try:
            aliases.add(str(section_index + 1))
            aliases.add(chr(ord('A') + int(section_index)))
        except Exception:
            pass
        try:
            run_name = str((run_sections[section_index] or {}).get("name") or "").strip()
            if run_name:
                aliases.add(run_name)
        except Exception:
            pass
        try:
            template_names = template_data.get("section_names") or []
            template_name = str(template_names[section_index] or "").strip()
            if template_name:
                aliases.add(template_name)
        except Exception:
            pass
        return {value.strip().upper() for value in aliases if str(value or "").strip()}

    def _template_color_cells_for_run(template_data, press, fmt, run_sections):
        planned_color_pages = _planned_color_pages_for_sections(run_sections)
        if not planned_color_pages:
            return [], True
        cfg = CONFIG_MAP.get((press, fmt), {}) or {}
        only_k_labels = {str(label or "") for label in cfg.get("only_k_labels", set())}
        color_cells = []
        for wanted in planned_color_pages:
            section_index = int(wanted.get("section_index", 0))
            page_number = int(wanted.get("template_page") or wanted.get("page", 0))
            aliases = _section_aliases_for_template_index(template_data, run_sections, section_index)
            matched = False
            matched_color_capable = False
            for unit in template_data.get("units", []) or []:
                if not isinstance(unit, dict):
                    continue
                unit_label = str(unit.get("label") or "")
                unit_section = str(unit.get("section") or "").strip().upper()
                if aliases and unit_section and unit_section not in aliases:
                    continue
                for r, row in enumerate(unit.get("grid", []) or []):
                    row = row if isinstance(row, list) else []
                    for c, cell_value in enumerate(row):
                        try:
                            cell_page = int(str(cell_value or "").strip())
                        except Exception:
                            continue
                        if cell_page != page_number:
                            continue
                        matched = True
                        if unit_label not in only_k_labels:
                            matched_color_capable = True
                            color_cells.append({"unit": unit_label, "r": int(r), "c": int(c)})
            if not matched or not matched_color_capable:
                return [], False
        # Deduplicate while preserving order.
        seen = set()
        unique = []
        for item in color_cells:
            key = (item.get("unit"), int(item.get("r", 0)), int(item.get("c", 0)))
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique, True

    def _apply_planned_pages_to_template_units(data, template_data, run_sections):
        if not isinstance(data, dict):
            return data
        units = data.get("units") or []
        if not isinstance(units, list):
            return data
        for section_index, section in enumerate(run_sections):
            planned_pages = []
            for page_number in section.get("page_numbers", []) or []:
                try:
                    planned_pages.append(int(page_number))
                except Exception:
                    pass
            if not planned_pages:
                continue
            section_name = str(section.get("name") or "").strip().upper()
            aliases = _section_aliases_for_template_index(template_data, run_sections, section_index)
            for unit in units:
                if not isinstance(unit, dict):
                    continue
                unit_section = str(unit.get("section") or "").strip().upper()
                if aliases and unit_section and unit_section not in aliases:
                    continue
                grid = unit.get("grid") or []
                if not isinstance(grid, list):
                    continue
                assigned_to_this_unit = False
                for r, row in enumerate(grid):
                    if not isinstance(row, list):
                        continue
                    for c, cell_value in enumerate(row):
                        try:
                            relative_page = int(str(cell_value or "").strip())
                        except Exception:
                            continue
                        if 1 <= relative_page <= len(planned_pages):
                            row[c] = str(planned_pages[relative_page - 1])
                            assigned_to_this_unit = True
                if assigned_to_this_unit and section_name:
                    unit["section"] = section_name
        # Empty units should not carry a section assignment into generated layouts.
        # Leaving a section on an empty unit makes the imposition builder include
        # unused units in the generated imposition name.
        for unit in units:
            if not isinstance(unit, dict):
                continue
            has_page = False
            for row in (unit.get("grid") or []):
                if not isinstance(row, list):
                    continue
                for cell_value in row:
                    if str(cell_value or "").strip():
                        has_page = True
                        break
                if has_page:
                    break
            if not has_page:
                unit["section"] = ""
        return data

    def _template_matches_plan_colors(template_path, press, fmt, run_sections):
        try:
            template_data = safe_read_json(template_path) or {}
        except Exception:
            template_data = {}
        if not isinstance(template_data, dict):
            return False
        _color_cells, ok = _template_color_cells_for_run(template_data, press, fmt, run_sections)
        return bool(ok)

    def _candidate_templates_for_run(run, sections):
        press = run["press_var"].get()
        fmt = _press_run_format(sections)
        pages = [int(section.get("pages") or 0) for section in sections]
        try:
            matches = list_matching_templates(press, fmt, section_count=len(pages), section_pages=pages)
        except Exception:
            matches = []
        return [(name, path) for name, path in matches if _template_matches_plan_colors(path, press, fmt, sections)]

    def show_page_four(plan, press_runs):
        header_var.set("Plan Layout - Templates")
        _clear_frame(body)
        _clear_footer()
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        assignable_sections = _plan_assignable_sections(plan)
        run_configs = []
        canvas = tk.Canvas(body, highlightthickness=0, bd=0, background="#f7f7f7")
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        frame = tk.Frame(canvas, background="#f7f7f7", bd=0, highlightthickness=0, padx=12, pady=12)
        win_id = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="Pick a layout template for each press run. If no matching template exists, (NEW) will be used.", font=(None, 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        template_preview_state = {"popup": None, "photo": None, "after_id": None}

        def _hide_template_preview(_event=None):
            after_id = template_preview_state.get("after_id")
            if after_id is not None:
                try:
                    dialog.after_cancel(after_id)
                except Exception:
                    pass
                template_preview_state["after_id"] = None
            popup = template_preview_state.get("popup")
            if popup is not None:
                try:
                    popup.destroy()
                except Exception:
                    pass
            template_preview_state["popup"] = None
            template_preview_state["photo"] = None

        def _show_template_preview(widget, template_var, template_paths, selected_name=None):
            selected_name = (selected_name if selected_name is not None else (template_var.get() or "")).strip()
            template_path = template_paths.get(selected_name)
            if not template_path:
                _hide_template_preview()
                return
            try:
                image, _title = open_json_preview(dialog, template_path, template_mode=True)
            except Exception:
                image = None
            if image is None:
                _hide_template_preview()
                return
            try:
                from PIL import ImageTk
                max_width = 520
                max_height = 360
                image = image.copy()
                image.thumbnail((max_width, max_height))
                photo = ImageTk.PhotoImage(image)
            except Exception:
                _hide_template_preview()
                return
            _hide_template_preview()
            popup = tk.Toplevel(dialog)
            try:
                popup.overrideredirect(True)
                popup.attributes("-topmost", True)
            except Exception:
                pass
            popup.configure(background="#444444")
            title = tk.Label(popup, text=selected_name, background="#444444", foreground="white", anchor="w", padx=6, pady=3)
            title.pack(fill="x")
            label = tk.Label(popup, image=photo, background="#ffffff", bd=1, relief="solid")
            label.pack(padx=2, pady=(0, 2))
            template_preview_state["popup"] = popup
            template_preview_state["photo"] = photo
            try:
                x = widget.winfo_rootx() + widget.winfo_width() + 12
                y = widget.winfo_rooty()
                popup.geometry(f"+{x}+{y}")
            except Exception:
                pass

        def _schedule_template_preview(widget, template_var, template_paths, selected_name=None, delay=350):
            after_id = template_preview_state.get("after_id")
            if after_id is not None:
                try:
                    dialog.after_cancel(after_id)
                except Exception:
                    pass
            template_preview_state["after_id"] = dialog.after(delay, lambda: _show_template_preview(widget, template_var, template_paths, selected_name=selected_name))

        def _bind_template_dropdown_preview(combo, template_var, template_paths):
            def _bind_popdown():
                try:
                    popdown = combo.tk.call("ttk::combobox::PopdownWindow", str(combo))
                    listbox = popdown + ".f.l"
                except Exception:
                    return
                def _motion(x, y):
                    try:
                        index = int(combo.tk.call(listbox, "index", f"@{x},{y}"))
                        values = list(combo.cget("values") or ())
                        if index < 0 or index >= len(values):
                            return
                        hovered_name = str(values[index])
                        if not template_paths.get(hovered_name):
                            _hide_template_preview()
                            return
                        _schedule_template_preview(combo, template_var, template_paths, selected_name=hovered_name, delay=125)
                    except Exception:
                        pass
                def _leave():
                    _hide_template_preview()
                try:
                    combo.tk.call("bind", listbox, "<Motion>", combo.register(_motion) + " %x %y")
                    combo.tk.call("bind", listbox, "<Leave>", combo.register(_leave))
                except Exception:
                    pass
            try:
                combo.configure(postcommand=lambda: combo.after(50, _bind_popdown))
            except Exception:
                pass

        row = 1
        for idx, run in enumerate(press_runs, start=1):
            selected_sections = _press_run_sections(run, assignable_sections)
            if not selected_sections:
                continue
            matches = _candidate_templates_for_run(run, selected_sections)
            values = [name for name, _path in matches] or ["(NEW)"]
            template_var = tk.StringVar(value=values[0])
            path_by_name = {name: p for name, p in matches}
            cfg = {"run": run, "sections": selected_sections, "templates": matches, "template_var": template_var, "template_paths": path_by_name}
            run_configs.append(cfg)
            box = ttk.LabelFrame(frame, text=f"{run['name'].get()} - {run['press_var'].get()}", padding=10)
            box.grid(row=row, column=0, sticky="ew", pady=(0, 12))
            box.columnconfigure(1, weight=1)
            ttk.Label(box, text=f"Sections: {_press_run_summary(run, assignable_sections)}").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
            ttk.Label(box, text="Template:").grid(row=1, column=0, sticky="w")
            template_combo = ttk.Combobox(box, textvariable=template_var, values=values, state="readonly", width=52)
            template_combo.grid(row=1, column=1, sticky="ew", padx=(8, 0))
            template_combo.bind("<Enter>", lambda _event, w=template_combo, v=template_var, p=path_by_name: _schedule_template_preview(w, v, p))
            template_combo.bind("<Leave>", _hide_template_preview)
            template_combo.bind("<ButtonPress-1>", lambda _event, w=template_combo, v=template_var, p=path_by_name: (_bind_template_dropdown_preview(w, v, p), _hide_template_preview()), add="+")
            template_combo.bind("<<ComboboxSelected>>", lambda _event, w=template_combo, v=template_var, p=path_by_name: _schedule_template_preview(w, v, p), add="+")
            _bind_template_dropdown_preview(template_combo, template_var, path_by_name)
            row += 1

        _bind_mousewheel_to_canvas(canvas, canvas)
        _bind_mousewheel_to_canvas(frame, canvas)

        def finish():
            if not run_configs:
                messagebox.showerror("Plan Layout", "Assign at least one section to a press run.", parent=dialog)
                return
            created = []
            created_paths = []
            for idx, cfg in enumerate(run_configs, start=1):
                run = cfg["run"]
                selected_sections = cfg["sections"]
                template_name = cfg["template_var"].get()
                template_path = cfg["template_paths"].get(template_name)
                press = run["press_var"].get()
                fmt = _press_run_format(selected_sections)
                section_pages = [int(s.get("pages") or 0) for s in selected_sections]
                section_names = [str(s.get("name") or chr(ord('A') + i)).upper() for i, s in enumerate(selected_sections)]
                if template_path:
                    data = safe_read_json(template_path) or {}
                    data = json.loads(json.dumps(data, default=str)) if isinstance(data, dict) else {}
                    data.pop("_db_record_id", None); data.pop("_db_record_type", None); data.pop("_file_path", None); data.pop("_layout_name", None)
                    color_template_data = json.loads(json.dumps(data, default=str))
                else:
                    data = {"version": 1, "units": []}
                    color_template_data = data
                data.update({
                    "press": press,
                    "format": fmt,
                    "issue_date": plan.get("issue_date") or "",
                    "product": ((plan.get("publication") or "") + " " + _generate_run_name(run, assignable_sections, plan)).strip(),
                    "section_count": len(selected_sections),
                    "section_pages": section_pages,
                    "section_names": section_names,
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "last_changed_by": get_windows_username(),
                })
                desired_starter = _desired_starter_format_for_publication(data.get("product") or "")
                if desired_starter:
                    data["starter_format"] = desired_starter
                color_cells, color_ok = _template_color_cells_for_run(color_template_data, press, fmt, selected_sections)
                data = _apply_planned_pages_to_template_units(data, color_template_data, selected_sections)
                data["color_cells"] = color_cells if color_ok else []
                name_base = sanitize_filename(f"P{'1' if press == 'Press 1' else '2'} {data.get('product') or 'PLAN'} {''.join(section_names)} {data.get('issue_date','').replace('/', '-')}").strip() or f"Plan Run {idx}"
                filename = name_base + ".json"
                target = os.path.join(LAYOUTS_DIR, filename)
                counter = 1
                while os.path.exists(target):
                    counter += 1
                    target = os.path.join(LAYOUTS_DIR, f"{name_base}_{counter}.json")
                data["name"] = os.path.splitext(os.path.basename(target))[0]
                safe_write_json(target, data)
                created.append(os.path.basename(target))
                created_paths.append(target)
            open_parent = None
            try:
                open_parent = dialog.master if dialog.master is not None else dialog
            except Exception:
                open_parent = dialog
            for created_path in created_paths:
                try:
                    open_json_in_layout(open_parent, created_path, template_mode=False, default_dir=LAYOUTS_DIR)
                except Exception as exc:
                    messagebox.showerror("Open Failed", f"Created layout but could not open it:\n{created_path}\n\n{exc}", parent=dialog)
            dialog.destroy()

        ttk.Button(footer_right, text="Finish", command=finish, width=12).pack(side="right", padx=(0, 8))
        ttk.Button(footer_right, text="Back", command=lambda p=plan, r=press_runs: show_page_three(p, r), width=12).pack(side="right", padx=(0, 8))
        ttk.Button(footer_right, text="Cancel", command=dialog.destroy, width=12).pack(side="right")

    def show_page_two_from_validation():
        plan = _validate_plan_inputs()
        if plan is not None:
            # Apply manifest color state to page_color_state
            manifest_colors = getattr(dialog, "_manifest_color_pages", None)
            if manifest_colors:
                for key, value in manifest_colors.items():
                    section_name, page = key
                    page_color_state[(section_name, (int(page),))] = bool(value)
                dialog._manifest_color_pages = None
            show_page_two(plan)

    def _reset_wizard_for_new_manifest():
        """Reset all Plan wizard state so a newly loaded manifest starts clean."""
        page_color_state.clear()
        page_group_state.clear()
        sections.clear()
        _set_split_status("")
        dialog._manifest_color_pages = {}

    # Store references on dialog for drag-and-drop / load manifest
    dialog._plan_issue_date_var = issue_date_var
    dialog._plan_publication_var = publication_var
    dialog._plan_sections = sections
    dialog._plan_make_section = _make_section
    dialog._plan_show_page_one = show_page_one
    dialog._plan_reset_wizard_state = _reset_wizard_for_new_manifest

    show_page_one()
    return dialog

def build_main_launcher():
    ensure_dir(LAYOUTS_DIR)
    ensure_dir(TEMPLATE_DIR)
    ensure_dir(REGULAR_DIR)
    root = tkdnd.TkinterDnD.Tk()
    set_window_icon(root)
    register_single_instance_window(root)
    _patch_tkdnd_file_mapping(root)
    root.title("Press Layouts")
    root.geometry("1100x760")
    root.minsize(980, 680)
    remember_window_geometry(root, "main_launcher", default_geometry="1100x760", minsize=(980, 680))
    _bind_window_size_memory(root, "main_launcher")
    allow_launcher_maintenance_actions = is_admin()
    style = ttk.Style(root)
    style.configure("LauncherVersion.TLabel", foreground="#1a73e8")
    style.configure("LauncherLink.TLabel", foreground="#1a73e8")
    style.configure("AdminFlag.TLabel", foreground="#c62828", font=(None, 10, "bold"))
    style.configure("DatabaseModeLive.TLabel", foreground="#2e7d32", font=(None, 10, "bold"))
    style.configure("DatabaseModeTest.TLabel", foreground="#ef6c00", font=(None, 10, "bold"))
    paned = tk.PanedWindow(root, orient="vertical", sashrelief="raised", sashwidth=8, bd=0, showhandle=False)
    paned.pack(fill="both", expand=True)
    frame = ttk.Frame(paned, padding=16)
    paned.add(frame, stretch="always", minsize=220)
    frame.rowconfigure(3, weight=1)
    frame.columnconfigure(0, weight=1)
    ttk.Label(frame, text="Layouts:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")
    changelog_data = load_changelog_data()
    running_version = _get_changelog_current_version_value(changelog_data)
    version_check_job = {"id": None}
    launcher_username = get_windows_username()
    status_frame = ttk.Frame(frame)
    status_frame.grid(row=0, column=0, sticky="e")

    def go_to_tomorrow():
        tomorrow_disp = fmt_issue_for_display(tomorrow_issue_date_mmddyyyy())
        target_group_iid = f"__issue_group__::{tomorrow_disp}"
        for child in tree.get_children(""):
            tree.item(child, open=False)
        if target_group_iid in group_by_iid:
            tree.item(target_group_iid, open=True)
            children = tree.get_children(target_group_iid)
            if children:
                first_child = children[0]
                tree.selection_set(first_child)
                tree.focus(first_child)
                tree.see(first_child)

    version_label_var = tk.StringVar(value=_format_version_label(running_version))
    version_label = ttk.Label(status_frame, textvariable=version_label_var, style="LauncherVersion.TLabel", font=(None, 10))
    version_label.pack(side="right")
    version_label.configure(cursor="hand2")
    version_label.bind("<Button-1>", lambda _event: show_changelog_dialog(root))
    username_label = ttk.Label(status_frame, text=f"User: {launcher_username}", anchor="e", justify="right")
    username_label.pack(side="right", padx=(0, 12))
    if _launcher_user_can_open_macros(launcher_username):
        username_label.configure(style="LauncherLink.TLabel", cursor="hand2")
        username_label.bind("<Button-1>", lambda _event: show_launcher_macro_dialog(root, launcher_username=launcher_username))
    if allow_launcher_maintenance_actions:
        ttk.Label(status_frame, text="(ADMIN)", style="AdminFlag.TLabel").pack(side="right", padx=(0, 12))
        db_mode_label = ttk.Label(status_frame, text=_db_mode_label_text(), style=_db_mode_label_style(), anchor="e", justify="right")
        db_mode_label.pack(side="right", padx=(0, 12))
        db_mode_label.configure(cursor="hand2")
        db_mode_label.bind(
            "<Button-1>",
            lambda _event: toggle_database_config_from_launcher(
                db_mode_label,
                refresh_callback=refresh,
                clear_preview_callback=close_preview,
            ),
        )
    search_frame = ttk.Frame(frame)
    search_frame.grid(row=1, column=0, sticky="ew", pady=(8, 4))
    search_frame.columnconfigure(1, weight=1)
    ttk.Label(search_frame, text="Search:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")
    search_var = tk.StringVar(value="")
    search_entry = ttk.Entry(search_frame, textvariable=search_var)
    search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    filter_frame = ttk.Frame(frame)
    filter_frame.grid(row=2, column=0, sticky="ew", pady=(4, 8))
    ttk.Label(filter_frame, text="Issue Date:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")
    issue_date_var = tk.StringVar(value="All")
    issue_date_combo = ttk.Combobox(filter_frame, textvariable=issue_date_var, values=["All"], state="readonly", width=16)
    issue_date_combo.grid(row=0, column=1, sticky="w", padx=(8, 12))
    ttk.Label(filter_frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=2, sticky="w")
    press_var = tk.StringVar(value="All")
    press_combo = ttk.Combobox(filter_frame, textvariable=press_var, values=["All", "Press 1", "Press 2"], state="readonly", width=12)
    press_combo.grid(row=0, column=3, sticky="w", padx=(8, 12))
    ttk.Label(filter_frame, text="Format:", font=(None, 11, "bold")).grid(row=0, column=4, sticky="w")
    format_var = tk.StringVar(value="All")
    format_combo = ttk.Combobox(filter_frame, textvariable=format_var, values=["All", "Broadsheet", "Tab", "8 up"], state="readonly", width=12)
    format_combo.grid(row=0, column=5, sticky="w", padx=(8, 12))
    ttk.Label(filter_frame, text="Pages:", font=(None, 11, "bold")).grid(row=0, column=6, sticky="w")
    pages_filter_var = tk.StringVar(value="All")
    pages_filter_combo = ttk.Combobox(filter_frame, textvariable=pages_filter_var, values=["All"], state="readonly", width=14)
    pages_filter_combo.grid(row=0, column=7, sticky="w", padx=(8, 0))
    filter_frame.columnconfigure(8, weight=1)
    go_tomorrow_btn = ttk.Button(filter_frame, text="Go to Tomorrow", command=go_to_tomorrow)
    go_tomorrow_btn.grid(row=0, column=9, sticky="e", padx=(12, 0))

    columns = ("press", "format", "pages", "color_pages", "plates", "changed_by", "saved")
    tree = ttk.Treeview(frame, columns=columns, show="tree headings", selectmode="browse")
    tree.grid(row=3, column=0, sticky="nsew", pady=(0, 0))
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    vsb.grid(row=3, column=1, sticky="ns", pady=(0, 0))
    tree.configure(yscrollcommand=vsb.set)
    recent_heading_titles = {
        "press": "Press",
        "format": "Format",
        "pages": "Pages",
        "color_pages": "Color Pages",
        "plates": "Plates",
        "changed_by": "Last Changed By",
        "saved": "Last Saved",
    }
    tree.heading("#0", text="Product")
    for key, title in recent_heading_titles.items():
        tree.heading(key, text=title)
    tree.column("#0", width=260, anchor="w")
    tree.column("press", width=90, anchor="center")
    tree.column("format", width=100, anchor="center")
    tree.column("pages", width=120, anchor="center")
    tree.column("color_pages", width=95, anchor="center")
    tree.column("plates", width=70, anchor="center")
    tree.column("changed_by", width=140, anchor="center")
    tree.column("saved", width=170, anchor="center")
    try:
        tree.tag_configure("group_row", font=(None, 10, "bold"), foreground="#1f1f1f")
        tree.tag_configure("issue_group_day_row", font=(None, 10, "bold"), foreground="#2e7d32")
    except Exception:
        pass
    apply_treeview_column_width_state(tree, ("#0",) + tuple(columns), "main_launcher", "layout_tree")
    bind_treeview_state_memory(root, "main_launcher", "layout_tree", tree, columns=("#0",) + tuple(columns))
    row_by_iid = {}
    group_by_iid = {}
    sort_state = load_treeview_sort_state("main_launcher", "layout_tree", "product")
    refresh_job = {"id": None}
    auto_refresh_ms = MAIN_LAUNCHER_REFRESH_INTERVAL_MS
    preview_state = {"win": None, "path": None, "after_id": None, "request_id": 0, "photo": None, "pil_image": None}
    def cancel_pending_preview():
        after_id = preview_state.get("after_id")
        preview_state["after_id"] = None
        if after_id is not None:
            try:
                root.after_cancel(after_id)
            except Exception:
                pass
    def close_preview():
        cancel_pending_preview()
        _clear_preview_panel(preview_label, preview_state, empty_text="Select a layout to preview")
    def _launcher_is_active():
        try:
            focused = root.focus_displayof()
            return bool(focused) and focused.winfo_toplevel() == root
        except Exception:
            return False
    def _current_preview_path():
        return selected_path()
    def show_preview(path):
        cancel_pending_preview()
        preview_state["request_id"] = int(preview_state.get("request_id", 0)) + 1
        request_id = preview_state["request_id"]
        if not path:
            close_preview()
            return
        def _do_show(_path=path, _request_id=request_id):
            preview_state["after_id"] = None
            if _request_id != preview_state.get("request_id"):
                return
            if _current_preview_path() != _path:
                return
            current_sig = _preview_file_signature_for_json(_path)
            if preview_state.get("path") == _path and preview_state.get("photo") is not None and preview_state.get("preview_file_sig") == current_sig:
                return
            close_preview()
            image, preview_title = open_json_preview(root, _path, template_mode=False)
            if image is None:
                _clear_preview_panel(preview_label, preview_state, empty_text="Select a layout to preview")
                return
            _set_preview_panel(preview_label, preview_state, image)
            preview_state["path"] = _path
            preview_state["preview_file_sig"] = current_sig
        preview_state["after_id"] = root.after_idle(_do_show)
    def _on_launcher_focus_in(event=None):
        show_preview(_current_preview_path())
    def _on_launcher_focus_out(event=None):
        def _close_if_really_inactive():
            if _launcher_is_active():
                return
            preview_state["request_id"] = int(preview_state.get("request_id", 0)) + 1
            close_preview()
        root.after_idle(_close_if_really_inactive)
    def sort_rows(rows):
        col = sort_state.get("col")
        if not col:
            return rows
        def keyfunc(r):
            if col == "saved":
                return r["saved_dt"] or datetime.min
            if col == "product":
                return (r["product"] or "").lower()
            if col == "press":
                return (r["press"] or "").lower()
            if col == "format":
                return (r["format"] or "").lower()
            if col == "pages":
                return tuple(r.get("section_pages_sort", (0, 0, 0, 0)))
            if col == "color_pages":
                return int(r.get("color_pages", 0) or 0)
            if col == "plates":
                return int(r.get("plates", 0) or 0)
            return ""
        return sorted(rows, key=keyfunc, reverse=sort_state["desc"])
    def load_rows_into_tree(rows, preserve_selection=None, preserve_focus=None, preserve_yview=None):
        reload_state, has_saved_tree_state = get_treeview_reload_state(tree, "main_launcher", "layout_tree", columns=("#0",) + tuple(columns))
        preserve_selection = tuple(reload_state.get("selected_iids") or preserve_selection or ())
        preserve_focus = str(reload_state.get("focus_iid") or preserve_focus or "").strip() or None
        preserve_yview = tuple(reload_state.get("yview") or preserve_yview or ())
        expanded_group_ids = set(str(iid) for iid in (reload_state.get("open_iids") or []))
        existing_group_ids = tuple(tree.get_children(""))
        preserved_selected_rows = [row_by_iid.get(iid) for iid in preserve_selection if iid in row_by_iid]
        preserved_focus_row = row_by_iid.get(preserve_focus) if preserve_focus in row_by_iid else None
        tree.delete(*existing_group_ids)
        row_by_iid.clear()
        group_by_iid.clear()

        tomorrow_issue_display = fmt_issue_for_display(tomorrow_issue_date_mmddyyyy())

        grouped_rows = {}
        for r in rows:
            issue_label = str(r.get("issue_disp") or "").strip() or "No Issue Date"
            grouped_rows.setdefault(issue_label, []).append(r)

        def issue_group_sort_key(issue_label):
            if issue_label == "No Issue Date":
                return (1, datetime.max)
            issue_dt = parse_issue_date_flexible(issue_label)
            return (0, issue_dt or datetime.max)

        group_labels = list(grouped_rows.keys())
        group_labels.sort(key=issue_group_sort_key)

        known_group_ids = set()
        selection_group_ids = {
            f"__issue_group__::{str(row.get('issue_disp') or '').strip() or 'No Issue Date'}"
            for row in preserved_selected_rows
            if isinstance(row, dict)
        }
        focus_group_id = None
        if isinstance(preserved_focus_row, dict):
            focus_issue = str(preserved_focus_row.get("issue_disp") or "").strip() or "No Issue Date"
            focus_group_id = f"__issue_group__::{focus_issue}"

        def issue_group_display_text(issue_label, issue_count):
            label_text = str(issue_label or "").strip() or "No Issue Date"
            if label_text == "No Issue Date":
                return f"{label_text} ({issue_count})", ("group_row",)
            issue_dt = parse_issue_date_flexible(label_text)
            if issue_dt is None:
                return f"{label_text} ({issue_count})", ("group_row",)
            weekday = issue_dt.strftime("%A")
            return f"{weekday} {label_text} ({issue_count})", ("issue_group_day_row",)

        for issue_label in group_labels:
            group_iid = f"__issue_group__::{issue_label}"
            default_open = (issue_label == tomorrow_issue_display)
            if has_saved_tree_state:
                should_open = bool(group_iid in expanded_group_ids)
            else:
                should_open = default_open
            if group_iid == focus_group_id or group_iid in selection_group_ids:
                should_open = True
            issue_count = len(grouped_rows.get(issue_label, []))
            issue_group_text, issue_group_tags = issue_group_display_text(issue_label, issue_count)
            tree.insert("", "end", iid=group_iid, text=issue_group_text, open=should_open, tags=issue_group_tags)
            group_by_iid[group_iid] = issue_label
            known_group_ids.add(group_iid)
            for r in grouped_rows.get(issue_label, []):
                iid = r["path"]
                tree.insert(group_iid, "end", iid=iid, text=r["product"], values=(
                    r["press"],
                    r["format"],
                    r.get("pages_disp", ""),
                    r.get("color_pages", 0),
                    r.get("plates", 0),
                    r.get("last_changed_by", "Unknown"),
                    r["saved_disp"],
                ))
                row_by_iid[iid] = r
        if preserve_selection:
            existing = [iid for iid in preserve_selection if iid in row_by_iid or iid in known_group_ids]
            if existing:
                tree.selection_set(existing)
        if preserve_focus and (preserve_focus in row_by_iid or preserve_focus in known_group_ids):
            tree.focus(preserve_focus)
        if preserve_yview and len(preserve_yview) > 0:
            try:
                tree.yview_moveto(preserve_yview[0])
            except Exception:
                pass
    def _matches_layout_filter(row):
        search_text = (search_var.get() or "").strip().lower()
        press_filter = (press_var.get() or "All").strip()
        format_filter = (format_var.get() or "All").strip()
        issue_filter = (issue_date_var.get() or "All").strip()
        pages_filter = (pages_filter_var.get() or "All").strip()
        if search_text:
            searchable = " ".join([
                row.get("issue_disp", ""),
                row.get("product", ""),
                row.get("press", ""),
                row.get("format", ""),
                row.get("pages_disp", ""),
                str(row.get("color_pages", "")),
                str(row.get("plates", "")),
                row.get("last_changed_by", ""),
            ]).lower()
            if search_text not in searchable:
                return False
        if press_filter != "All" and row.get("press", "") != press_filter:
            return False
        if format_filter != "All" and row.get("format", "") != format_filter:
            return False
        if issue_filter != "All" and row.get("issue_disp", "") != issue_filter:
            return False
        if pages_filter != "All" and row.get("pages_disp", "") != pages_filter:
            return False
        return True

    def _matches_layout_filter_no_issue(row):
        search_text = (search_var.get() or "").strip().lower()
        press_filter = (press_var.get() or "All").strip()
        format_filter = (format_var.get() or "All").strip()
        pages_filter = (pages_filter_var.get() or "All").strip()
        if search_text:
            searchable = " ".join([
                row.get("issue_disp", ""),
                row.get("product", ""),
                row.get("press", ""),
                row.get("format", ""),
                row.get("pages_disp", ""),
                str(row.get("color_pages", "")),
                str(row.get("plates", "")),
                row.get("last_changed_by", ""),
            ]).lower()
            if search_text not in searchable:
                return False
        if press_filter != "All" and row.get("press", "") != press_filter:
            return False
        if format_filter != "All" and row.get("format", "") != format_filter:
            return False
        return True

    def _matches_layout_filter_no_pages(row):
        search_text = (search_var.get() or "").strip().lower()
        press_filter = (press_var.get() or "All").strip()
        format_filter = (format_var.get() or "All").strip()
        issue_filter = (issue_date_var.get() or "All").strip()
        if search_text:
            searchable = " ".join([
                row.get("issue_disp", ""),
                row.get("product", ""),
                row.get("press", ""),
                row.get("format", ""),
                row.get("pages_disp", ""),
                str(row.get("color_pages", "")),
                str(row.get("plates", "")),
                row.get("last_changed_by", ""),
            ]).lower()
            if search_text not in searchable:
                return False
        if press_filter != "All" and row.get("press", "") != press_filter:
            return False
        if format_filter != "All" and row.get("format", "") != format_filter:
            return False
        if issue_filter != "All" and row.get("issue_disp", "") != issue_filter:
            return False
        return True

    def _pages_display_sort_key(value):
        text = str(value or "")
        numbers = []
        for part in re.findall(r"\d+", text):
            try:
                numbers.append(int(part))
            except Exception:
                pass
        return (numbers, text.lower())

    def update_sort_headings():
        tree.heading("#0", text=_treeview_sort_heading_text("Product", sort_state, "product"), command=lambda: sort_by("product"))
        for col in columns:
            tree.heading(col, text=_treeview_sort_heading_text(recent_heading_titles[col], sort_state, col), command=lambda _c=col: sort_by(_c))

    def refresh(preserve_state=True):
        selected = tree.selection() if preserve_state else ()
        focused = tree.focus() if preserve_state else None
        yview = tree.yview() if preserve_state else None
        all_rows, _changed = get_cached_layout_rows(force=False)
        date_values = [row.get("issue_disp", "") for row in all_rows if _matches_layout_filter_no_issue(row) and row.get("issue_disp")]
        unique_dates = ["All"] + sorted(set(date_values), key=lambda t: datetime.strptime(t, "%m/%d/%Y") if parse_issue_date_flexible(t) else t)
        issue_date_combo.configure(values=unique_dates)
        if issue_date_var.get() not in unique_dates:
            issue_date_var.set("All")
        page_values = [row.get("pages_disp", "") for row in all_rows if _matches_layout_filter_no_pages(row) and row.get("pages_disp")]
        unique_pages = ["All"] + sorted(set(page_values), key=_pages_display_sort_key)
        pages_filter_combo.configure(values=unique_pages)
        if pages_filter_var.get() not in unique_pages:
            pages_filter_var.set("All")
        rows = [row for row in all_rows if _matches_layout_filter(row)]
        rows = sort_rows(rows)
        load_rows_into_tree(rows, preserve_selection=selected, preserve_focus=focused, preserve_yview=yview)
        update_sort_headings()
    def schedule_refresh():
        try:
            if refresh_job["id"] is not None:
                root.after_cancel(refresh_job["id"])
        except Exception:
            pass
        refresh_job["id"] = root.after(auto_refresh_ms, auto_refresh_tick)
    def _check_preview_freshness():
        path = preview_state.get("path")
        if not path:
            return
        current_sig = _preview_file_signature_for_json(path)
        if preview_state.get("preview_file_sig") != current_sig:
            preview_state["photo"] = None
            show_preview(path)
    def auto_refresh_tick():
        refresh_job["id"] = None
        try:
            refresh(preserve_state=True)
        finally:
            if root.winfo_exists():
                schedule_refresh()
                _check_preview_freshness()
    def sort_by(col):
        if sort_state["col"] == col:
            sort_state["desc"] = not sort_state["desc"]
        else:
            sort_state["col"] = col
            sort_state["desc"] = False
        save_treeview_sort_state("main_launcher", "layout_tree", sort_state)
        refresh(preserve_state=True)
    update_sort_headings()
    search_var.trace_add("write", lambda *_: refresh(preserve_state=False))
    press_var.trace_add("write", lambda *_: refresh(preserve_state=False))
    format_var.trace_add("write", lambda *_: refresh(preserve_state=False))
    issue_date_var.trace_add("write", lambda *_: refresh(preserve_state=False))
    pages_filter_var.trace_add("write", lambda *_: refresh(preserve_state=False))
    def selected_path():
        sel = tree.selection()
        candidate = sel[0] if sel else tree.focus()
        if candidate in row_by_iid:
            return candidate
        focused = tree.focus()
        return focused if focused in row_by_iid else None
    def open_selected():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Layout", "Select a layout to open.")
            return
        close_preview()
        open_json_in_layout(root, path, template_mode=False)

    def clone_selected():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Layout", "Select a layout to clone.")
            return
        close_preview()
        open_json_in_layout(
            root,
            path,
            template_mode=False,
            load_as_copy=True,
            copy_blank_issue_only=True,
        )

    def new_layout():
        close_preview()
        build_new_layout_launcher(root)

    def open_plan(drop_path=None):
        close_preview()
        dialog = build_plan_wizard(root)
        if drop_path:
            _load_manifest_from_path_in_dialog(dialog, drop_path)
        return dialog

    def regenerate_selected_preview():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Layout", "Select a layout to regenerate its preview.")
            return
        close_preview()
        try:
            regenerate_preview_image_for_json_path(path, template_mode=False, scale=0.75)
            show_preview(path)
        except Exception as exc:
            messagebox.showerror("Regen Preview Failed", str(exc))

    def delete_selected():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Layout", "Select a layout to delete.")
            return
        name = os.path.basename(path)
        if not messagebox.askyesno("Delete Layout", f"Delete the selected layout file:\n\n{name}"):
            return
        try:
            if preview_state.get("path") == path:
                close_preview()
            remove_preview_image_for_json(path)
            os.remove(path)
        except Exception as exc:
            messagebox.showerror("Delete Failed", f"Could not delete {name}:\n{exc}")
            return
        refresh(preserve_state=False)
    def templates():
        close_preview()
        build_template_editor_launcher(root)
    def regulars():
        close_preview()
        build_regular_editor_launcher(root)
    def cleanup_old_layouts():
        today = datetime.now().date()
        all_rows, _changed = get_cached_layout_rows(force=False)
        if not all_rows:
            messagebox.showinfo("Cleanup", "No layouts are currently available.")
            return
        all_rows.sort(key=lambda r: (r.get("issue_dt") or datetime.max, (r.get("product") or "").lower()))
        dialog = tk.Toplevel(root)
        set_window_icon(dialog)
        dialog.title("Cleanup Layouts")
        dialog.transient(root)
        dialog.geometry("920x420")
        dialog.minsize(820, 360)
        remember_window_geometry(dialog, "cleanup_dialog", default_geometry="920x420", minsize=(820, 360))
        dialog.grab_set()
        outer = ttk.Frame(dialog, padding=16)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)
        ttk.Label(
            outer,
            text="Select individual layouts to delete, or select an issue-date group to select/clear everything in that issue date. Nothing is selected by default.",
            font=(None, 10, "bold")
        ).grid(row=0, column=0, sticky="w")
        cleanup_columns = ("delete", "product", "press", "format", "saved")
        cleanup_tree = ttk.Treeview(outer, columns=cleanup_columns, show="tree headings", selectmode="browse")
        cleanup_tree.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        cleanup_vsb = ttk.Scrollbar(outer, orient="vertical", command=cleanup_tree.yview)
        cleanup_vsb.grid(row=1, column=1, sticky="ns", pady=(8, 0))
        cleanup_tree.configure(yscrollcommand=cleanup_vsb.set)
        cleanup_tree.heading("#0", text="Issue Date / Layout")
        cleanup_tree.heading("delete", text="Delete")
        cleanup_tree.heading("product", text="Product")
        cleanup_tree.heading("press", text="Press")
        cleanup_tree.heading("format", text="Format")
        cleanup_tree.heading("saved", text="Last Saved")
        cleanup_tree.column("#0", width=230, anchor="w")
        cleanup_tree.column("delete", width=70, anchor="center")
        cleanup_tree.column("product", width=260, anchor="w")
        cleanup_tree.column("press", width=90, anchor="center")
        cleanup_tree.column("format", width=110, anchor="center")
        cleanup_tree.column("saved", width=170, anchor="center")
        try:
            cleanup_tree.tag_configure("group_row", font=(None, 10, "bold"), foreground="#1f1f1f")
        except Exception:
            pass
        delete_state = {row["path"]: False for row in all_rows}
        issue_groups = {}
        for row in all_rows:
            issue_label = row.get("issue_disp") or "No Issue Date"
            issue_groups.setdefault(issue_label, []).append(row)

        def checkbox_value_for_path(path):
            return "☑" if delete_state.get(path, False) else "☐"

        def group_checkbox_value(group_iid):
            paths = [child for child in cleanup_tree.get_children(group_iid) if child in delete_state]
            if not paths:
                return "☐"
            checked = sum(1 for path in paths if delete_state.get(path, False))
            if checked == 0:
                return "☐"
            if checked == len(paths):
                return "☑"
            return "◩"

        def refresh_group_checkbox(group_iid):
            try:
                values = list(cleanup_tree.item(group_iid, "values") or [])
                if values:
                    values[0] = group_checkbox_value(group_iid)
                    cleanup_tree.item(group_iid, values=tuple(values))
            except Exception:
                pass

        def populate_cleanup_tree():
            cleanup_tree.delete(*cleanup_tree.get_children())
            for issue_label, rows in issue_groups.items():
                group_iid = "issue::" + str(issue_label)
                cleanup_tree.insert("", "end", iid=group_iid, text=str(issue_label), values=("☐", f"{len(rows)} layout(s)", "", "", ""), tags=("group_row",), open=False)
                for row in rows:
                    path = row["path"]
                    cleanup_tree.insert(group_iid, "end", iid=path, text=os.path.basename(path), values=(
                        checkbox_value_for_path(path),
                        row.get("product") or "",
                        row.get("press") or "",
                        row.get("format") or "",
                        row.get("saved_disp") or "",
                    ))
                refresh_group_checkbox(group_iid)

        def toggle_cleanup_item(item_id):
            if not item_id:
                return
            if item_id in delete_state:
                delete_state[item_id] = not delete_state.get(item_id, False)
                values = cleanup_tree.item(item_id, "values")
                if values:
                    cleanup_tree.item(item_id, values=(checkbox_value_for_path(item_id),) + tuple(values[1:]))
                parent = cleanup_tree.parent(item_id)
                if parent:
                    refresh_group_checkbox(parent)
                cleanup_tree.selection_set(item_id)
                cleanup_tree.focus(item_id)
                return
            if str(item_id).startswith("issue::"):
                child_paths = [child for child in cleanup_tree.get_children(item_id) if child in delete_state]
                if not child_paths:
                    return
                new_value = not all(delete_state.get(path, False) for path in child_paths)
                for path in child_paths:
                    delete_state[path] = new_value
                    values = cleanup_tree.item(path, "values")
                    if values:
                        cleanup_tree.item(path, values=(checkbox_value_for_path(path),) + tuple(values[1:]))
                refresh_group_checkbox(item_id)
                cleanup_tree.selection_set(item_id)
                cleanup_tree.focus(item_id)

        def toggle_from_event(event=None):
            item_id = cleanup_tree.identify_row(event.y) if event is not None else cleanup_tree.focus()
            toggle_cleanup_item(item_id)
            return "break"
        cleanup_tree.bind("<Double-Button-1>", toggle_from_event)
        cleanup_tree.bind("<space>", toggle_from_event)
        populate_cleanup_tree()
        status_var = tk.StringVar(value="Ready.")
        ttk.Label(outer, textvariable=status_var, foreground="#555555").grid(row=2, column=0, sticky="w", pady=(12, 0))
        cleanup_progress_var = tk.DoubleVar(value=0)
        cleanup_progress = ttk.Progressbar(outer, variable=cleanup_progress_var, maximum=1, mode="determinate")
        cleanup_progress.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        btns = ttk.Frame(outer)
        btns.grid(row=4, column=0, pady=(12, 0), sticky="e")

        def _regen_preview_for_path(path, template_mode=False, default_dir=None, prompt_save_template=None):
            try:
                regenerate_preview_image_for_json_path(
                    path,
                    template_mode=template_mode,
                    default_dir=default_dir,
                    prompt_save_template=prompt_save_template,
                    scale=0.75,
                )
                return None
            except Exception as exc:
                return f"{os.path.basename(path)}: {exc}"

        def _cleanup_jobs():
            jobs = []
            layout_rows, _changed = get_cached_layout_rows(force=False)
            for row in layout_rows:
                jobs.append({
                    "label": os.path.basename(row["path"]),
                    "path": row["path"],
                    "template_mode": False,
                    "regular_mode": False,
                    "default_dir": None,
                    "prompt_save_template": None,
                })
            for _name, path in list_json_files(TEMPLATE_DIR):
                jobs.append({
                    "label": os.path.basename(path),
                    "path": path,
                    "template_mode": True,
                    "regular_mode": False,
                    "default_dir": None,
                    "prompt_save_template": None,
                })
            for _name, path in list_json_files(REGULAR_DIR):
                jobs.append({
                    "label": os.path.basename(path),
                    "path": path,
                    "template_mode": False,
                    "regular_mode": True,
                    "default_dir": REGULAR_DIR,
                    "prompt_save_template": False,
                })
            return jobs

        def regen_all_previews_cleanup():
            jobs = _cleanup_jobs()
            total = len(jobs)
            if total <= 0:
                messagebox.showinfo("Regen ALL Previews", "No layout, template, or regular files were found.", parent=dialog)
                return
            if not messagebox.askyesno(
                "Regen ALL Previews",
                f"Regenerate previews for {total} files?",
                parent=dialog,
            ):
                return
            close_preview()
            errors = []
            for idx, job in enumerate(jobs, start=1):
                status_var.set(f"Regenerating {idx} of {total}: {job['label']}")
                dialog.update_idletasks()
                error_text = _regen_preview_for_path(
                    job["path"],
                    template_mode=job["template_mode"],
                    default_dir=job["default_dir"],
                    prompt_save_template=job["prompt_save_template"],
                )
                if error_text:
                    errors.append(error_text)
            _rebuild_template_cache()
            _rebuild_regular_cache()
            _rebuild_layout_cache()
            refresh(preserve_state=False)
            success_count = total - len(errors)
            status_var.set(f"Finished regenerating {success_count} of {total} previews.")
            if errors:
                messagebox.showerror(
                    "Regen ALL Previews",
                    f"Regenerated {success_count} of {total} previews.\n\nErrors:\n" + "\n".join(errors),
                    parent=dialog,
                )
            else:
                messagebox.showinfo(
                    "Regen ALL Previews",
                    f"Successfully regenerated {total} previews.",
                    parent=dialog,
                )

        def _touch_json_path(path, template_mode=False, regular_mode=False, default_dir=None, prompt_save_template=None):
            error_text, _original_path, _final_path = touch_cleanup_json_path(
                path,
                template_mode=template_mode,
                regular_mode=regular_mode,
                default_dir=default_dir,
                prompt_save_template=prompt_save_template,
            )
            return error_text

        def touch_all_cleanup():
            jobs = _cleanup_jobs()
            total = len(jobs)
            if total <= 0:
                messagebox.showinfo("Touch ALL", "No layout, template, or regular files were found.", parent=dialog)
                return
            if not messagebox.askyesno(
                "Touch ALL",
                f"Open and save all {total} layouts, templates, and regular files?\n\nTemplates may be renamed to the corrected imposition filename.",
                parent=dialog,
            ):
                return
            close_preview()
            errors = []
            for idx, job in enumerate(jobs, start=1):
                status_var.set(f"Touching {idx} of {total}: {job['label']}")
                dialog.update_idletasks()
                error_text = _touch_json_path(
                    job["path"],
                    template_mode=job["template_mode"],
                    regular_mode=job["regular_mode"],
                    default_dir=job["default_dir"],
                    prompt_save_template=job["prompt_save_template"],
                )
                if error_text:
                    errors.append(error_text)
            _rebuild_template_cache()
            _rebuild_regular_cache()
            _rebuild_layout_cache()
            refresh(preserve_state=False)
            success_count = total - len(errors)
            status_var.set(f"Finished touching {success_count} of {total} files.")
            if errors:
                messagebox.showerror(
                    "Touch ALL",
                    f"Touched {success_count} of {total} files.\n\nErrors:\n" + "\n".join(errors),
                    parent=dialog,
                )
            else:
                messagebox.showinfo(
                    "Touch ALL",
                    f"Successfully touched {total} files. Any template with a corrected imposition was renamed to its new filename.",
                    parent=dialog,
                )

        def delete_selected_cleanup():
            to_delete = [path for path, checked in delete_state.items() if checked]
            if not to_delete:
                messagebox.showinfo("Cleanup", "No layouts are selected for deletion.", parent=dialog)
                return
            if not messagebox.askyesno(
                "Delete Layouts",
                f"Delete {len(to_delete)} selected layout file(s)?",
                parent=dialog,
            ):
                return
            errors = []
            total_delete = len(to_delete)
            try:
                cleanup_progress.configure(maximum=max(1, total_delete))
            except Exception:
                pass
            cleanup_progress_var.set(0)
            status_var.set(f"Removing 0 of {total_delete} selected layout file(s)...")
            dialog.update_idletasks()
            for idx, path in enumerate(to_delete, start=1):
                status_var.set(f"Removing {idx} of {total_delete}: {os.path.basename(path)}")
                cleanup_progress_var.set(idx - 1)
                dialog.update_idletasks()
                try:
                    remove_preview_image_for_json(path)
                    os.remove(path)
                except Exception as exc:
                    errors.append(f"{os.path.basename(path)}: {exc}")
                cleanup_progress_var.set(idx)
                dialog.update_idletasks()
            status_var.set(f"Removed {total_delete - len(errors)} of {total_delete} selected layout file(s).")
            refresh(preserve_state=False)
            if errors:
                messagebox.showerror(
                    "Cleanup",
                    "Some files could not be deleted:\n\n" + "\n".join(errors),
                    parent=dialog,
                )
            dialog.destroy()
        ttk.Button(btns, text="Touch ALL", command=touch_all_cleanup, width=12).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Regen ALL Previews", command=regen_all_previews_cleanup, width=18).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Delete", command=delete_selected_cleanup, width=12).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Cancel", command=dialog.destroy, width=12).pack(side="left")

    def _find_postgres_client_tool(executable_name):
        try:
            import shutil
        except Exception:
            shutil = None
        executable_name = str(executable_name or "").strip()
        if not executable_name:
            return None
        candidates = []
        if shutil is not None:
            found = shutil.which(executable_name)
            if found:
                candidates.append(found)
            if os.name == "nt" and not executable_name.lower().endswith(".exe"):
                found = shutil.which(executable_name + ".exe")
                if found:
                    candidates.append(found)
        base_dirs = []
        preferred_sql_bin_dir = r"L:\SQL Server\PostgreSQL\bin"
        if os.path.isdir(preferred_sql_bin_dir):
            base_dirs.append(preferred_sql_bin_dir)
        preferred_sql_dir = r"L:\SQL Server"
        if os.path.isdir(preferred_sql_dir):
            base_dirs.append(preferred_sql_dir)
        for env_key in ("ProgramFiles", "ProgramFiles(x86)"):
            env_base = os.environ.get(env_key)
            if env_base:
                postgres_dir = os.path.join(env_base, "PostgreSQL")
                if os.path.isdir(postgres_dir):
                    base_dirs.append(postgres_dir)
        target_names = [executable_name]
        if os.name == "nt" and not executable_name.lower().endswith(".exe"):
            target_names.append(executable_name + ".exe")
        seen = set()
        for base_dir in base_dirs:
            try:
                for root_dir, _dirs, files in os.walk(base_dir):
                    lower_files = {str(name).lower(): name for name in files}
                    for target_name in target_names:
                        match_name = lower_files.get(target_name.lower())
                        if match_name:
                            full_path = os.path.join(root_dir, match_name)
                            if full_path not in seen:
                                candidates.append(full_path)
                                seen.add(full_path)
            except Exception:
                continue
        return candidates[0] if candidates else None

    def show_db_maintenance_dialog():
        dialog = tk.Toplevel(root)
        set_window_icon(dialog)
        dialog.title("DB Maintenance")
        dialog.transient(root)
        dialog.geometry("720x520")
        dialog.minsize(660, 460)
        remember_window_geometry(dialog, "db_maintenance_dialog", default_geometry="720x520", minsize=(660, 460))
        dialog.grab_set()

        outer = ttk.Frame(dialog, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        ttk.Label(
            outer,
            text="Database Maintenance",
            font=(None, 12, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text=(
                "Admin-only tools for PostgreSQL maintenance. Use cleanup for the existing layout cleanup workflow, "
                "and use the other actions for health checks, backups, and optimization."
            ),
            wraplength=660,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 10))

        db_status_job = {"id": None}
        db_status_pulse_job = {"id": None}
        db_status_state = {"connected": False, "phase": 0, "error_text": None, "last_success": None}
        db_status_bar = ttk.Frame(outer)
        db_status_bar.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        db_status_bar.columnconfigure(1, weight=1)
        db_status_indicator = tk.Canvas(db_status_bar, width=16, height=16, highlightthickness=0, bd=0)
        db_status_indicator.grid(row=0, column=0, sticky="nw", padx=(0, 8), pady=(2, 0))
        db_status_indicator_oval = db_status_indicator.create_oval(2, 2, 14, 14, fill="#c62828", outline="#8e0000")
        db_status_var = tk.StringVar(value="Database: checking connection...")
        ttk.Label(db_status_bar, textvariable=db_status_var, anchor="w", justify="left", wraplength=620).grid(row=0, column=1, sticky="ew")

        action_row = ttk.Frame(outer)
        action_row.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        for idx in range(3):
            action_row.columnconfigure(idx, weight=1)

        output = tk.Text(outer, wrap="word", height=16)
        output.grid(row=4, column=0, sticky="nsew")
        output.configure(state="disabled")
        output_scroll = ttk.Scrollbar(outer, orient="vertical", command=output.yview)
        output_scroll.place(in_=output, relx=1.0, rely=0.0, relheight=1.0, x=0, y=0, anchor="ne")
        output.configure(yscrollcommand=output_scroll.set)

        status_var = tk.StringVar(value="Choose a maintenance action.")
        ttk.Label(outer, textvariable=status_var, font=(None, 10, "bold")).grid(row=5, column=0, sticky="w", pady=(10, 0))

        def _db_status_colors(connected, phase):
            phase = int(phase or 0) % 2
            if connected:
                return ("#50c878", "#2e7d32") if phase == 0 else ("#2e7d32", "#1b5e20")
            return ("#ff6f61", "#c62828") if phase == 0 else ("#c62828", "#8e0000")

        def _db_status_last_success_text():
            dt_value = db_status_state.get("last_success")
            if not dt_value:
                return "never"
            try:
                return dt_value.strftime("%m/%d/%Y %H:%M:%S")
            except Exception:
                return str(dt_value)

        def update_db_status_pulse():
            db_status_pulse_job["id"] = None
            try:
                connected = bool(db_status_state.get("connected"))
                phase = (int(db_status_state.get("phase", 0)) + 1) % 2
                db_status_state["phase"] = phase
                fill_color, outline_color = _db_status_colors(connected, phase)
                db_status_indicator.itemconfigure(db_status_indicator_oval, fill=fill_color, outline=outline_color)
            except Exception:
                pass
            try:
                if dialog.winfo_exists():
                    db_status_pulse_job["id"] = dialog.after(700, update_db_status_pulse)
            except Exception:
                db_status_pulse_job["id"] = None

        def update_db_status_indicator():
            try:
                config = _db_load_config()
                server_name = str(config.get("host") or "Unknown Server")
                database_name = str(config.get("database") or "Unknown Database")
            except Exception:
                server_name = "Unknown Server"
                database_name = "Unknown Database"
            connected = False
            error_text = None
            try:
                conn = _db_connect()
                try:
                    cur = conn.cursor()
                    try:
                        cur.execute("SELECT 1")
                        cur.fetchone()
                        connected = True
                        db_status_state["last_success"] = datetime.now()
                    finally:
                        try:
                            cur.close()
                        except Exception:
                            pass
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
            except Exception as exc:
                error_text = str(exc)
                connected = False
            db_status_state["connected"] = connected
            db_status_state["error_text"] = error_text
            try:
                fill_color, outline_color = _db_status_colors(connected, db_status_state.get("phase", 0))
                db_status_indicator.itemconfigure(db_status_indicator_oval, fill=fill_color, outline=outline_color)
                last_success_text = _db_status_last_success_text()
                if connected:
                    db_status_var.set(
                        f"Database: {server_name} / {database_name}\nLast successful check: {last_success_text}"
                    )
                else:
                    message = (
                        f"Database: {server_name} / {database_name} (offline)\n"
                        + f"Last successful check: {last_success_text}"
                    )
                    if error_text:
                        message += "\nError: " + error_text
                    db_status_var.set(message)
            except Exception:
                pass

        def schedule_db_status_check(delay_ms=15000):
            try:
                if db_status_job["id"] is not None:
                    dialog.after_cancel(db_status_job["id"])
            except Exception:
                pass
            try:
                db_status_job["id"] = dialog.after(int(delay_ms), run_db_status_check)
            except Exception:
                db_status_job["id"] = None

        def run_db_status_check():
            db_status_job["id"] = None
            try:
                update_db_status_indicator()
            finally:
                try:
                    if dialog.winfo_exists():
                        schedule_db_status_check(15000)
                except Exception:
                    pass

        def log_message(message_text, clear=False):
            output.configure(state="normal")
            if clear:
                output.delete("1.0", "end")
            output.insert("end", str(message_text or "") + "\n")
            output.see("end")
            output.configure(state="disabled")

        def maintenance_cleanup():
            status_var.set("Opening cleanup dialog...")
            log_message("Opening the existing cleanup workflow.", clear=True)
            cleanup_old_layouts()

        def maintenance_health_check():
            status_var.set("Running database health check...")
            log_message("Running database health check...", clear=True)
            try:
                with _db_cursor() as (cur, config):
                    schema = _db_pg_ident(config.get('schema'))
                    cur.execute('SELECT current_database(), current_user, version()')
                    row = cur.fetchone() or (None, None, None)
                    cur.execute(f"SELECT record_type, COUNT(*) FROM {schema}.records GROUP BY record_type ORDER BY record_type")
                    counts = dict(cur.fetchall() or [])
                    cur.execute(f"SELECT COUNT(*) FROM {schema}.record_locks")
                    lock_count = (cur.fetchone() or [0])[0]
                    cur.execute('SELECT pg_size_pretty(pg_database_size(current_database()))')
                    db_size = (cur.fetchone() or ['Unknown'])[0]
                lines = [
                    f"Database: {row[0] or 'Unknown'}",
                    f"User: {row[1] or 'Unknown'}",
                    f"Server: {str(row[2] or 'Unknown').splitlines()[0]}",
                    f"Layouts: {int(counts.get('layout', 0) or 0)}",
                    f"Templates: {int(counts.get('template', 0) or 0)}",
                    f"Regulars: {int(counts.get('regular', 0) or 0)}",
                    f"Open locks: {int(lock_count or 0)}",
                    f"Database size: {db_size or 'Unknown'}",
                ]
                log_message("\n".join(lines), clear=True)
                status_var.set("Database health check completed.")
            except Exception as exc:
                log_message(f"Health check failed: {exc}", clear=True)
                status_var.set("Database health check failed.")
                messagebox.showerror("DB Health Check", f"Could not run the health check:\n{exc}", parent=dialog)

        def maintenance_backup():
            try:
                import shutil
                import subprocess
            except Exception as exc:
                messagebox.showerror("DB Backup", f"Backup tools are unavailable:\n{exc}", parent=dialog)
                return
            backup_dir = r"L:\SQL Server\Backups"
            try:
                os.makedirs(backup_dir, exist_ok=True)
            except Exception:
                pass
            backup_filename = datetime.now().strftime("press_layouts_backup_%Y%m%d_%H%M%S.sql")
            backup_path = filedialog.asksaveasfilename(
                parent=dialog,
                title="Save Database Backup",
                defaultextension=".sql",
                filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")],
                initialdir=backup_dir if os.path.isdir(backup_dir) else MAIN_DIR,
                initialfile=backup_filename,
            )
            if not backup_path:
                return
            pg_dump_path = _find_postgres_client_tool("pg_dump")
            if not pg_dump_path:
                messagebox.showerror("DB Backup", "pg_dump was not found on this workstation. Press Layouts looked in PATH and under L:\\SQL Server. Please install PostgreSQL client tools first.", parent=dialog)
                return
            try:
                config = _db_load_config()
                env = os.environ.copy()
                env["PGPASSWORD"] = str(config.get("password") or "")
                status_var.set("Creating database backup...")
                log_message(f"Creating backup: {backup_path}", clear=True)
                result = subprocess.run(
                    [
                        pg_dump_path,
                        "-h", str(config.get("host") or ""),
                        "-p", str(config.get("port") or 5432),
                        "-U", str(config.get("user") or ""),
                        "-d", str(config.get("database") or ""),
                        "-f", backup_path,
                    ],
                    capture_output=True,
                    text=True,
                    env=env,
                    check=False,
                )
                if result.returncode != 0:
                    raise RuntimeError((result.stderr or result.stdout or "pg_dump failed").strip())
                log_message(f"Backup complete: {backup_path}", clear=True)
                status_var.set("Database backup completed.")
                messagebox.showinfo("DB Backup", f"Database backup created successfully:\n{backup_path}", parent=dialog)
            except Exception as exc:
                log_message(f"Backup failed: {exc}", clear=True)
                status_var.set("Database backup failed.")
                messagebox.showerror("DB Backup", f"Could not create the database backup:\n{exc}", parent=dialog)

        def maintenance_restore():
            try:
                import subprocess
                import tempfile
            except Exception as exc:
                messagebox.showerror("DB Restore", "Restore tools are unavailable:\n" + str(exc), parent=dialog)
                return
            restore_path = filedialog.askopenfilename(
                parent=dialog,
                title="Select Database Restore File",
                filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")],
            )
            if not restore_path:
                return
            psql_path = _find_postgres_client_tool("psql")
            if not psql_path:
                messagebox.showerror(
                    "DB Restore",
                    "psql was not found on this workstation. Press Layouts looked in PATH and under L:\\SQL Server\\PostgreSQL\\bin. Please install PostgreSQL client tools first.",
                    parent=dialog,
                )
                return
            confirm = messagebox.askyesno(
                "Restore Database",
                "This will replace the entire Press Layouts schema with the contents of the selected backup file.\n\n"
                + f"Backup file: {restore_path}\n\n"
                + "Make sure all users have saved their work before continuing.\n\nDo you want to proceed?",
                parent=dialog,
            )
            if not confirm:
                return
            wrapper_path = None
            try:
                config = _db_load_config()
                env = os.environ.copy()
                env["PGPASSWORD"] = str(config.get("password") or "")
                db_name = str(config.get("database") or "press_layouts")
                schema_name = str(config.get("schema") or "press_layouts")
                status_var.set("Restoring database...")
                log_message(f"Preparing to restore backup: {restore_path}", clear=True)
                log_message(f"Target database: {db_name} | schema: {schema_name}", clear=False)
                with open(restore_path, "r", encoding="utf-8") as backup_file:
                    backup_sql = backup_file.read()
                wrapper_sql = (
                    "SET client_min_messages TO WARNING;\n"
                    + f"DROP SCHEMA IF EXISTS {_db_pg_ident(schema_name)} CASCADE;\n"
                    + backup_sql
                )
                if not wrapper_sql.endswith("\n"):
                    wrapper_sql += "\n"
                with tempfile.NamedTemporaryFile("w", suffix="_press_layouts_restore.sql", delete=False, encoding="utf-8") as tf:
                    tf.write(wrapper_sql)
                    wrapper_path = tf.name
                log_message("Transactional restore wrapper created. Importing backup with psql...", clear=False)
                result = subprocess.run(
                    [
                        psql_path,
                        "-h", str(config.get("host") or ""),
                        "-p", str(config.get("port") or 5432),
                        "-U", str(config.get("user") or ""),
                        "-d", db_name,
                        "-v", "ON_ERROR_STOP=1",
                        "-1",
                        "-f", wrapper_path,
                    ],
                    capture_output=True,
                    text=True,
                    env=env,
                    check=False,
                )
                if result.returncode != 0:
                    raise RuntimeError((result.stderr or result.stdout or "psql restore failed").strip())
                _rebuild_template_cache()
                _rebuild_regular_cache()
                _rebuild_layout_cache()
                refresh(preserve_state=False)
                update_db_status_indicator()
                log_message("Restore completed successfully.", clear=True)
                status_var.set("Database restore completed.")
                if messagebox.askyesno(
                    "DB Restore Complete",
                    "The database restore completed successfully.\n\nWould you like to restart Press Layouts now so every open window reconnects cleanly?",
                    parent=dialog,
                ):
                    restart_press_layout_program(root)
            except Exception as exc:
                log_message("Restore failed: " + str(exc), clear=True)
                status_var.set("Database restore failed.")
                messagebox.showerror("DB Restore", "Could not restore the database:\n" + str(exc), parent=dialog)
            finally:
                if wrapper_path:
                    try:
                        os.remove(wrapper_path)
                    except Exception:
                        pass

        def maintenance_refresh_locks():
            confirm = messagebox.askyesno(
                "Refresh Record Locks",
                "This will clear every current database edit lock.\n\n"
                "Use this when Press Layouts reports a record as open by a user even though it is not actually open anymore.\n\n"
                "Any records that are still truly open will re-register their lock automatically on the next heartbeat.\n\n"
                "Do you want to refresh all record locks now?",
                parent=dialog,
            )
            if not confirm:
                return
            try:
                status_var.set("Refreshing record locks...")
                log_message("Refreshing database record locks...", clear=True)
                removed_rows = _db_refresh_all_record_locks()
                if removed_rows:
                    lines = [f"Removed {len(removed_rows)} record lock(s):"]
                    for row in removed_rows:
                        record_type = str(row.get('record_type') or '').title()
                        file_name = str(row.get('file_name') or row.get('name') or 'Unknown')
                        opened_by = str(row.get('opened_by') or 'Unknown')
                        hostname = str(row.get('hostname') or 'Unknown workstation')
                        process_id = row.get('process_id')
                        heartbeat_at = row.get('heartbeat_at')
                        lines.append(f"- {record_type}: {file_name} | {opened_by} on {hostname} | PID {process_id or 'Unknown'} | heartbeat {heartbeat_at or 'Unknown'}")
                    log_message("\n".join(lines), clear=True)
                else:
                    log_message("No record locks were present.", clear=True)
                status_var.set("Record locks refreshed.")
                messagebox.showinfo("Refresh Record Locks", f"Record locks refreshed.\n\nRemoved {len(removed_rows)} lock(s).", parent=dialog)
            except Exception as exc:
                log_message(f"Record lock refresh failed: {exc}", clear=True)
                status_var.set("Record lock refresh failed.")
                messagebox.showerror("Refresh Record Locks", f"Could not refresh record locks:\n{exc}", parent=dialog)

        def maintenance_optimize():
            if not messagebox.askyesno(
                "Optimize Database",
                "Run VACUUM ANALYZE on the Press Layouts tables now?\n\n"
                "This is usually safe, but it may take a little time on larger databases.",
                parent=dialog,
            ):
                return
            try:
                status_var.set("Optimizing database...")
                log_message("Running VACUUM ANALYZE on Press Layouts tables...", clear=True)
                with _db_cursor() as (cur, config):
                    schema = _db_pg_ident(config.get('schema'))
                    cur.execute(f"VACUUM ANALYZE {schema}.records")
                    cur.execute(f"VACUUM ANALYZE {schema}.record_locks")
                log_message("VACUUM ANALYZE completed successfully.", clear=True)
                status_var.set("Database optimization completed.")
                messagebox.showinfo("Optimize Database", "VACUUM ANALYZE completed successfully.", parent=dialog)
            except Exception as exc:
                log_message(f"Optimization failed: {exc}", clear=True)
                status_var.set("Database optimization failed.")
                messagebox.showerror("Optimize Database", f"Could not optimize the database:\n{exc}", parent=dialog)

        ttk.Button(action_row, text="Cleanup Layouts", command=maintenance_cleanup, width=20).grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 8))
        ttk.Button(action_row, text="Health Check", command=maintenance_health_check, width=20).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))
        ttk.Button(action_row, text="Backup Database", command=maintenance_backup, width=20).grid(row=0, column=2, sticky="ew", pady=(0, 8))
        ttk.Button(action_row, text="Restore Database", command=maintenance_restore, width=20).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(action_row, text="Optimize Database", command=maintenance_optimize, width=20).grid(row=1, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(action_row, text="Refresh Record Locks", command=maintenance_refresh_locks, width=20).grid(row=1, column=2, sticky="ew")

        def close_db_maintenance_dialog():
            try:
                if db_status_job["id"] is not None:
                    dialog.after_cancel(db_status_job["id"])
            except Exception:
                pass
            try:
                if db_status_pulse_job["id"] is not None:
                    dialog.after_cancel(db_status_pulse_job["id"])
            except Exception:
                pass
            try:
                dialog.destroy()
            except Exception:
                pass

        footer = ttk.Frame(outer)
        footer.grid(row=6, column=0, sticky="e", pady=(12, 0))
        ttk.Button(footer, text="Close", command=close_db_maintenance_dialog, width=12).pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW", close_db_maintenance_dialog)
        update_db_status_indicator()
        update_db_status_pulse()
        schedule_db_status_check(15000)

    def _on_main_tree_select(event=None):
        show_preview(selected_path())

    def _on_main_tree_double_click(event=None):
        item_id = tree.identify_row(event.y) if event is not None else tree.focus()
        if item_id in group_by_iid:
            try:
                tree.item(item_id, open=(not bool(tree.item(item_id, "open"))))
            except Exception:
                pass
            return "break"
        open_selected()
        return "break"

    tree.bind("<<TreeviewSelect>>", _on_main_tree_select)
    tree.bind("<Double-Button-1>", _on_main_tree_double_click)
    btns = ttk.Frame(frame)
    btns.grid(row=4, column=0, columnspan=2, pady=(2, 0), sticky="ew")
    btns.columnconfigure(0, weight=1)
    left_btns = ttk.Frame(btns)
    left_btns.grid(row=0, column=0, sticky="w")
    right_btns = ttk.Frame(btns)
    right_btns.grid(row=0, column=1, sticky="e")
    plan_button = ttk.Button(left_btns, text="Plan", command=open_plan, width=12)
    plan_button.pack(side="left", padx=(0, 8))
    def _on_plan_drop(event):
        path = _resolve_manifest_drop_path(root, event)
        if path:
            open_plan(drop_path=path)
            return
        _report_unusable_manifest_drop(root, event)
    plan_button.drop_target_register(tkdnd.DND_FILES)
    plan_button.dnd_bind("<<Drop>>", _on_plan_drop)
    ttk.Button(left_btns, text="New", command=new_layout, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(left_btns, text="Open", command=open_selected, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(left_btns, text="Clone", command=clone_selected, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(right_btns, text="Regulars", command=regulars, width=12).pack(side="right", padx=(0, 8))
    ttk.Button(right_btns, text="Templates", command=templates, width=12).pack(side="right", padx=(0, 8))
    ttk.Button(right_btns, text="Delete", command=delete_selected, width=12).pack(side="right", padx=(0, 8))
    if allow_launcher_maintenance_actions:
        ttk.Button(right_btns, text="DB Maintenance", command=show_db_maintenance_dialog, width=16).pack(side="right", padx=(0, 8))
    preview_pane = ttk.Frame(paned, padding=(0, 0, 0, 0))
    preview_pane.columnconfigure(0, weight=1)
    preview_pane.rowconfigure(0, weight=1)
    preview_box = ttk.Frame(preview_pane, padding=(8, 0, 8, 8))
    preview_box.grid(row=0, column=0, sticky="nsew")
    preview_box.columnconfigure(0, weight=1)
    preview_box.rowconfigure(0, weight=1)
    preview_label = ttk.Label(preview_box, text="Select a layout to preview", anchor="center", justify="center")
    preview_label.grid(row=0, column=0, sticky="nsew")
    preview_label.bind("<Configure>", lambda e: _render_preview_panel_image(preview_label, preview_state), add="+")
    paned.add(preview_pane, minsize=160)
    _bind_preview_pane_memory(root, "main_launcher", paned, preview_pane, default_height=240)
    # Print buttons for selected layout
    def _print_selected_starter():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Layout", "Select a layout to print.")
            return
        try:
            close_preview()
            win = open_json_in_layout(root, path, template_mode=False)
            if hasattr(win, "print_starter"):
                win.print_starter()
        except Exception as e:
            messagebox.showerror("Print Failed", str(e))
        finally:
            try:
                if win and win.winfo_exists():
                    win.destroy()
            except Exception:
                pass

    def _print_selected_layout():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Layout", "Select a layout to print.")
            return
        try:
            close_preview()
            win = open_json_in_layout(root, path, template_mode=False)
            if hasattr(win, "print_layout"):
                win.print_layout()
        except Exception as e:
            messagebox.showerror("Print Failed", str(e))
        finally:
            try:
                if win and win.winfo_exists():
                    win.destroy()
            except Exception:
                pass

    ttk.Button(left_btns, text="Print Starter", command=_print_selected_starter, width=14).pack(side="left", padx=(8, 8))
    ttk.Button(left_btns, text="Print Layout", command=_print_selected_layout, width=12).pack(side="left", padx=(0, 8))

    def schedule_version_check(delay_ms=CHANGELOG_CHECK_INTERVAL_MS):
        try:
            if version_check_job["id"] is not None:
                root.after_cancel(version_check_job["id"])
        except Exception:
            pass
        try:
            version_check_job["id"] = root.after(int(delay_ms), run_version_check)
        except Exception:
            version_check_job["id"] = None

    def run_version_check():
        version_check_job["id"] = None
        try:
            check_for_required_restart(root, running_version)
        finally:
            try:
                if root.winfo_exists():
                    schedule_version_check(CHANGELOG_CHECK_INTERVAL_MS)
            except Exception:
                pass

    def on_close():
        try:
            if refresh_job["id"] is not None:
                root.after_cancel(refresh_job["id"])
        except Exception:
            pass
        try:
            if version_check_job["id"] is not None:
                root.after_cancel(version_check_job["id"])
        except Exception:
            pass
        try:
            restart_dialog = getattr(root, "_restart_required_dialog", None)
            if restart_dialog is not None and restart_dialog.winfo_exists():
                restart_dialog.destroy()
        except Exception:
            pass
        _persist_bound_preview_panes(root)
        close_preview()
        unregister_single_instance_window(root)
        root.destroy()
    root.bind("<FocusIn>", _on_launcher_focus_in, add="+")
    root.protocol("WM_DELETE_WINDOW", on_close)
    refresh(preserve_state=False)
    schedule_refresh()
    schedule_version_check()
    root.mainloop()


# Expose this single-file module under the original UI module name for the original entry-point import.
_single_file_sys.modules.setdefault('press_layout_ui', _single_file_sys.modules[__name__])


import io
import socket
from contextlib import contextmanager
from tkinter import simpledialog


# =============================================================================
# PostgreSQL data backend adapters
# PostgreSQL-backed replacements for former file-style layout/template/regular, preview, and edit-lock operations.
# =============================================================================

_DB_CONFIG_FILENAME = "press_layouts_db.json"
_DB_COLLECTION_ROOTS = {
    "layout": LAYOUTS_DIR,
    "template": TEMPLATE_DIR,
    "regular": REGULAR_DIR,
}
_DB_COLLECTION_BY_ROOT = {v: k for k, v in _DB_COLLECTION_ROOTS.items()}
_DB_BOOTSTRAPPED = False
_DB_BOOTSTRAP_LOCK = threading.Lock()
_DB_DRIVER = None
_DB_POOL = None
_DB_POOL_KEY = None
_DB_POOL_LOCK = threading.RLock()
_DB_POOL_MIN_CONNECTIONS = 1
_DB_POOL_MAX_CONNECTIONS = 6
_DB_LOCK_DEFAULTS = {
    "stale_minutes": 240,
    "heartbeat_seconds": 30,
}

_FS_ensure_dir = ensure_dir
_FS_safe_read_json = safe_read_json
_FS_safe_write_json = safe_write_json
_FS_list_json_files = list_json_files
_FS_json_dir_entries = _json_dir_entries
_FS_preview_image_path_for_json = preview_image_path_for_json
_FS_load_preview_image_for_json = load_preview_image_for_json
_FS_remove_preview_image_for_json = remove_preview_image_for_json
_FS_save_preview_image_for_window = _save_preview_image_for_window
_FS_save_preview_for_current_window = _save_preview_for_current_window
_FS_save_preview_for_saved_template = _save_preview_for_saved_template
_FS_regenerate_preview_image_for_json_path = regenerate_preview_image_for_json_path
_FS_do_save = do_save
_FS_build_press_layout = build_press_layout
_FS_load_changelog_data = load_changelog_data
_FS_os_path_exists = os.path.exists
_FS_os_remove = os.remove


def _db_is_virtual_dir(value):
    return str(value or "").strip() in set(_DB_COLLECTION_ROOTS.values())


def _db_parse_virtual_path(path):
    raw = str(path or "").replace('\\', '/').strip()
    if not raw:
        return None
    if raw in _DB_COLLECTION_BY_ROOT:
        return {"record_type": _DB_COLLECTION_BY_ROOT[raw], "file_name": None, "root": raw}
    for root, record_type in _DB_COLLECTION_BY_ROOT.items():
        prefix = root.rstrip('/') + '/'
        if raw.startswith(prefix):
            return {"record_type": record_type, "file_name": raw[len(prefix):], "root": root}
    return None


def _db_make_virtual_path(record_type, file_name):
    return f"{_DB_COLLECTION_ROOTS[str(record_type)]}/{file_name}"


def ensure_dir(path: str):
    if _db_is_virtual_dir(path):
        return
    _FS_ensure_dir(path)


def _db_load_config():
    config_path = get_selected_db_config_path()
    data = _FS_safe_read_json(config_path)
    if not isinstance(data, dict):
        raise RuntimeError(f"Database configuration file is missing or invalid: {config_path}")
    config = dict(data)
    config.setdefault("host", "gghqsv-primasv")
    config.setdefault("port", 5432)
    config.setdefault("database", "press_layouts")
    config.setdefault("schema", "press_layouts")
    config.setdefault("user", "press_layouts")
    config.setdefault("password", "press_layouts")
    config.setdefault("maintenance_database", "postgres")
    config.setdefault("sslmode", "prefer")
    for key, value in _DB_LOCK_DEFAULTS.items():
        config.setdefault(key, value)
    return config


def _db_import_driver():
    global _DB_DRIVER
    if _DB_DRIVER is not None:
        return _DB_DRIVER
    try:
        driver = importlib.import_module("psycopg2")
    except Exception:
        try:
            driver = importlib.import_module("psycopg")
        except Exception:
            raise RuntimeError("PostgreSQL driver not found in the packaged Press Layouts executable.")
    _DB_DRIVER = driver
    return driver


def _db_pg_ident(value):
    text = str(value or '').strip()
    if not text:
        raise RuntimeError('Database identifier cannot be empty.')
    return '"' + text.replace('"', '""') + '"'


def _db_connect(database=None, maintenance=False):
    driver = _db_import_driver()
    config = _db_load_config()
    dbname = database or (config.get("maintenance_database") if maintenance else config.get("database"))
    kwargs = _db_connection_kwargs(config, dbname)
    conn = driver.connect(**kwargs)
    try:
        conn.autocommit = True
    except Exception:
        pass
    try:
        conn.set_session(autocommit=True)
    except Exception:
        pass
    try:
        import psycopg2.extensions as _psyco_ext
        conn.set_isolation_level(_psyco_ext.ISOLATION_LEVEL_AUTOCOMMIT)
    except Exception:
        pass
    return conn


def _db_connection_kwargs(config, dbname):
    kwargs = {
        "host": config.get("host"),
        "port": int(config.get("port", 5432)),
        "user": config.get("user"),
        "password": config.get("password"),
        "dbname": dbname,
    }
    sslmode = config.get("sslmode")
    if sslmode:
        kwargs["sslmode"] = sslmode
    return kwargs


def _db_pool_config_key(config):
    return tuple(
        (key, str(config.get(key) or ""))
        for key in ("host", "port", "database", "user", "password", "sslmode")
    )


def _db_get_pool():
    """Return the process-wide PostgreSQL pool for the selected database."""
    global _DB_POOL, _DB_POOL_KEY
    config = _db_load_config()
    key = _db_pool_config_key(config)
    with _DB_POOL_LOCK:
        if _DB_POOL is not None and _DB_POOL_KEY == key:
            return _DB_POOL
        _db_close_pool()
        driver = _db_import_driver()
        if str(getattr(driver, "__name__", "")) == "psycopg2":
            from psycopg2.pool import ThreadedConnectionPool
            _DB_POOL = ThreadedConnectionPool(
                _DB_POOL_MIN_CONNECTIONS,
                _DB_POOL_MAX_CONNECTIONS,
                **_db_connection_kwargs(config, config.get("database")),
            )
            _DB_POOL_KEY = key
        else:
            # psycopg3 installations retain the existing direct-connection
            # behavior unless a compatible pool adapter is added explicitly.
            _DB_POOL = None
            _DB_POOL_KEY = None
        return _DB_POOL


def _db_close_pool():
    global _DB_POOL, _DB_POOL_KEY
    with _DB_POOL_LOCK:
        pool = _DB_POOL
        _DB_POOL = None
        _DB_POOL_KEY = None
        if pool is None:
            return
        try:
            pool.closeall()
        except AttributeError:
            try:
                pool.close()
            except Exception:
                pass
        except Exception:
            pass


def _db_pool_connection(pool):
    if pool is None:
        return None, None
    if hasattr(pool, "getconn"):
        return pool.getconn(), "psycopg2"
    return None, None


def _db_return_pool_connection(pool, conn, pool_kind, close=False):
    if conn is None:
        return
    try:
        if close:
            conn.close()
        elif pool_kind == "psycopg2":
            pool.putconn(conn)
        else:
            conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def _db_fetchone(cursor):
    row = cursor.fetchone()
    if row is None:
        return None
    desc = getattr(cursor, 'description', None) or []
    if isinstance(row, dict):
        return row
    return {str((getattr(column, 'name', None) or column[0])): row[idx] for idx, column in enumerate(desc)}


def _db_fetchall(cursor):
    desc = getattr(cursor, 'description', None) or []
    names = [str((getattr(column, 'name', None) or column[0])) for column in desc]
    rows = []
    for row in cursor.fetchall():
        if isinstance(row, dict):
            rows.append(row)
        else:
            rows.append({names[idx]: row[idx] for idx in range(len(names))})
    return rows


def _db_bootstrap():
    global _DB_BOOTSTRAPPED
    if _DB_BOOTSTRAPPED:
        return
    with _DB_BOOTSTRAP_LOCK:
        if _DB_BOOTSTRAPPED:
            return
        config = _db_load_config()
        schema = _db_pg_ident(config.get('schema'))
        dbname = str(config.get('database'))
        conn = _db_connect(maintenance=True)
        try:
            cur = conn.cursor()
            try:
                cur.execute('SELECT 1 FROM pg_database WHERE datname = %s', (dbname,))
                if cur.fetchone() is None:
                    cur.execute(f'CREATE DATABASE {_db_pg_ident(dbname)}')
            finally:
                cur.close()
        finally:
            conn.close()
        conn = _db_connect()
        try:
            cur = conn.cursor()
            try:
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS {schema}')
                cur.execute(f'''CREATE TABLE IF NOT EXISTS {schema}.records (
                    id BIGSERIAL PRIMARY KEY,
                    record_type TEXT NOT NULL CHECK (record_type IN ('layout', 'template', 'regular')),
                    file_name TEXT NOT NULL,
                    file_stem TEXT NOT NULL,
                    name TEXT,
                    press TEXT,
                    format TEXT,
                    issue_date TEXT,
                    product TEXT,
                    section_count INTEGER,
                    section_pages JSONB,
                    saved_at TIMESTAMPTZ,
                    last_changed_by TEXT,
                    data JSONB NOT NULL,
                    preview_png BYTEA,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (record_type, file_name)
                )''')
                cur.execute(f'CREATE INDEX IF NOT EXISTS records_lookup_idx ON {schema}.records (record_type, file_name)')
                cur.execute(f'CREATE INDEX IF NOT EXISTS records_name_idx ON {schema}.records (record_type, name)')
                cur.execute(f'''CREATE TABLE IF NOT EXISTS {schema}.record_locks (
                    record_type TEXT NOT NULL CHECK (record_type IN ('layout', 'template', 'regular')),
                    record_id BIGINT NOT NULL REFERENCES {schema}.records(id) ON DELETE CASCADE,
                    opened_by TEXT NOT NULL,
                    hostname TEXT,
                    process_id INTEGER,
                    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (record_type, record_id)
                )''')
                cur.execute(f'CREATE INDEX IF NOT EXISTS record_locks_heartbeat_idx ON {schema}.record_locks (heartbeat_at)')
                cur.execute(f'''CREATE TABLE IF NOT EXISTS {schema}.product_translations (
                    id BIGSERIAL PRIMARY KEY,
                    incoming TEXT NOT NULL,
                    output TEXT NOT NULL DEFAULT '',
                    UNIQUE (incoming)
                )''')
                cur.execute(f'''CREATE TABLE IF NOT EXISTS {schema}.section_translations (
                    id BIGSERIAL PRIMARY KEY,
                    incoming TEXT NOT NULL,
                    output TEXT NOT NULL DEFAULT '',
                    UNIQUE (incoming)
                )''')
            finally:
                cur.close()
        finally:
            conn.close()
        _DB_BOOTSTRAPPED = True


@contextmanager
def _db_cursor():
    _db_bootstrap()
    config = _db_load_config()
    pool = _db_get_pool()
    conn = None
    pool_kind = None
    pooled = False
    if pool is not None:
        conn, pool_kind = _db_pool_connection(pool)
        pooled = conn is not None
    if conn is None:
        conn = _db_connect()
    elif pooled:
        try:
            conn.autocommit = True
        except Exception:
            pass
    try:
        cur = conn.cursor()
        try:
            yield cur, config
        finally:
            cur.close()
    finally:
        if pooled:
            _db_return_pool_connection(pool, conn, pool_kind, close=bool(sys.exc_info()[0]))
        else:
            conn.close()


def _db_parse_saved_at(value):
    dt = parse_saved_at(value) if value else None
    return dt or datetime.now()


def _db_normalize_file_name(file_name):
    value = str(file_name or '').strip()
    if not value:
        raise RuntimeError('A record name is required.')
    if not value.lower().endswith('.json'):
        value += '.json'
    return sanitize_filename(value)


def _db_row_to_virtual_item(row):
    record_type = str(row.get('record_type') or '')
    file_name = str(row.get('file_name') or '')
    updated_dt = row.get('updated_at') if not isinstance(row.get('updated_at'), str) else parse_saved_at(row.get('updated_at'))
    updated_dt = updated_dt or datetime.now()
    return {
        'name': file_name,
        'path': _db_make_virtual_path(record_type, file_name),
        'mtime_ns': int(updated_dt.timestamp() * 1000000000),
        'ctime_ns': int(updated_dt.timestamp() * 1000000000),
        'size': len(json.dumps(row.get('data') or {}, default=str)),
        'fs_saved_dt': updated_dt,
        'fs_saved_disp': fmt_dt_for_display(updated_dt),
        'db_row': row,
    }



def _db_list_rows(record_type):
    with _db_cursor() as (cur, config):
        schema = _db_pg_ident(config.get('schema'))
        cur.execute(
            f'''SELECT id, record_type, file_name, file_stem, name, press, format, issue_date, product, section_count, section_pages, saved_at, last_changed_by, data, created_at, updated_at FROM {schema}.records WHERE record_type = %s ORDER BY COALESCE(name, file_stem, file_name), file_name''',
            (record_type,),
        )
        return _db_fetchall(cur)


def _db_read_record(record_type, file_name):
    with _db_cursor() as (cur, config):
        schema = _db_pg_ident(config.get('schema'))
        cur.execute(
            f'''SELECT id, record_type, file_name, file_stem, name, press, format, issue_date, product, section_count, section_pages, saved_at, last_changed_by, data, created_at, updated_at FROM {schema}.records WHERE record_type = %s AND file_name = %s''',
            (record_type, file_name),
        )
        return _db_fetchone(cur)

def _db_record_exists(path):
    parsed = _db_parse_virtual_path(path)
    return bool(parsed and parsed.get('file_name') and _db_read_record(parsed['record_type'], parsed['file_name']))


def _db_upsert_record(path, data, preview_png=None, clear_preview=False):
    parsed = _db_parse_virtual_path(path)
    if not parsed or not parsed.get('file_name'):
        raise RuntimeError(f'Invalid database record path: {path}')
    record_type = parsed['record_type']
    file_name = _db_normalize_file_name(parsed['file_name'])
    payload = json.loads(json.dumps(data if isinstance(data, dict) else {}, default=str))
    payload.setdefault('version', 1)
    payload['saved_at'] = payload.get('saved_at') or datetime.now().isoformat(timespec='seconds')
    payload['last_changed_by'] = payload.get('last_changed_by') or get_windows_username()
    payload['name'] = payload.get('name') or os.path.splitext(file_name)[0]
    section_pages = payload.get('section_pages') if isinstance(payload.get('section_pages'), list) else []
    saved_at_dt = _db_parse_saved_at(payload.get('saved_at'))
    with _db_cursor() as (cur, config):
        schema = _db_pg_ident(config.get('schema'))
        cur.execute(f'''INSERT INTO {schema}.records (
            record_type, file_name, file_stem, name, press, format, issue_date, product,
            section_count, section_pages, saved_at, last_changed_by, data, preview_png,
            created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s::jsonb, %s, %s, %s::jsonb, %s, NOW(), NOW()
        )
        ON CONFLICT (record_type, file_name) DO UPDATE SET
            file_stem = EXCLUDED.file_stem,
            name = EXCLUDED.name,
            press = EXCLUDED.press,
            format = EXCLUDED.format,
            issue_date = EXCLUDED.issue_date,
            product = EXCLUDED.product,
            section_count = EXCLUDED.section_count,
            section_pages = EXCLUDED.section_pages,
            saved_at = EXCLUDED.saved_at,
            last_changed_by = EXCLUDED.last_changed_by,
            data = EXCLUDED.data,
            preview_png = CASE WHEN %s THEN NULL WHEN %s IS NOT NULL THEN %s ELSE {schema}.records.preview_png END,
            updated_at = NOW()
        RETURNING id, record_type, file_name, file_stem, name, press, format, issue_date, product, section_count, section_pages, saved_at, last_changed_by, data, preview_png, created_at, updated_at''', (
            record_type, file_name, os.path.splitext(file_name)[0], payload.get('name'), payload.get('press'), payload.get('format'), payload.get('issue_date'), payload.get('product'), int(payload.get('section_count', 1) or 1), json.dumps(section_pages, default=str), saved_at_dt, payload.get('last_changed_by'), json.dumps(payload, default=str), preview_png, bool(clear_preview), preview_png, preview_png))
        return _db_fetchone(cur)


def _db_delete_record(path):
    parsed = _db_parse_virtual_path(path)
    if not parsed or not parsed.get('file_name'):
        raise FileNotFoundError(path)
    with _db_cursor() as (cur, config):
        schema = _db_pg_ident(config.get('schema'))
        cur.execute(f'DELETE FROM {schema}.records WHERE record_type = %s AND file_name = %s RETURNING id', (parsed['record_type'], parsed['file_name']))
        if cur.fetchone() is None:
            raise FileNotFoundError(path)


def _db_store_preview(path, image):
    if image is None:
        return
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    _db_upsert_record(path, safe_read_json(path) or {}, preview_png=buffer.getvalue())



def _db_load_preview_bytes(path):
    parsed = _db_parse_virtual_path(path)
    if not parsed or not parsed.get('file_name'):
        return None
    with _db_cursor() as (cur, config):
        schema = _db_pg_ident(config.get('schema'))
        cur.execute(
            f'''SELECT preview_png FROM {schema}.records WHERE record_type = %s AND file_name = %s''',
            (parsed['record_type'], parsed['file_name']),
        )
        row = cur.fetchone()
    if not row:
        return None
    return row[0] if not isinstance(row, dict) else row.get('preview_png')

def _db_clear_preview(path):
    parsed = _db_parse_virtual_path(path)
    if not parsed or not parsed.get('file_name'):
        return
    row = _db_read_record(parsed['record_type'], parsed['file_name'])
    if row:
        _db_upsert_record(path, row.get('data') or {}, preview_png=None, clear_preview=True)


def safe_read_json(path):
    parsed = _db_parse_virtual_path(path)
    if not parsed or not parsed.get('file_name'):
        return _FS_safe_read_json(path)
    row = _db_read_record(parsed['record_type'], parsed['file_name'])
    if not row:
        return None
    data = row.get('data') or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}
    data = json.loads(json.dumps(data, default=str))
    data['_db_record_id'] = row.get('id')
    data['_db_record_type'] = row.get('record_type')
    data['_file_path'] = _db_make_virtual_path(row.get('record_type'), row.get('file_name'))
    data['_layout_name'] = data.get('name') or row.get('name') or row.get('file_stem')
    return data


def safe_write_json(path, data):
    parsed = _db_parse_virtual_path(path)
    if not parsed or not parsed.get('file_name'):
        return _FS_safe_write_json(path, data)
    to_write = stamp_layout_change_metadata(data, path=path) if isinstance(data, dict) else data
    _db_upsert_record(path, to_write)


def list_json_files(folder):
    parsed = _db_parse_virtual_path(folder)
    if not parsed or parsed.get('file_name'):
        return _FS_list_json_files(folder)
    return [((row.get('name') or row.get('file_stem') or row.get('file_name')), _db_make_virtual_path(parsed['record_type'], row.get('file_name'))) for row in _db_list_rows(parsed['record_type'])]


def _json_dir_entries(folder):
    parsed = _db_parse_virtual_path(folder)
    return _FS_json_dir_entries(folder) if not parsed else [_db_row_to_virtual_item(row) for row in _db_list_rows(parsed['record_type'])]


def preview_image_path_for_json(json_path: str) -> str:
    return f"{json_path}.preview.png" if _db_parse_virtual_path(json_path) else _FS_preview_image_path_for_json(json_path)


def remove_preview_image_for_json(json_path: str):
    if _db_parse_virtual_path(json_path):
        _db_clear_preview(json_path)
    else:
        _FS_remove_preview_image_for_json(json_path)


def load_preview_image_for_json(json_path: str):
    if not _db_parse_virtual_path(json_path):
        return _FS_load_preview_image_for_json(json_path)
    try:
        from PIL import Image
    except Exception:
        return None
    payload = _db_load_preview_bytes(json_path)
    if not payload:
        return None
    try:
        with Image.open(io.BytesIO(payload)) as img:
            return img.copy()
    except Exception:
        return None


def _save_preview_image_for_window(win, json_path, scale=0.75):
    if not _db_parse_virtual_path(json_path):
        return _FS_save_preview_image_for_window(win, json_path, scale=scale)
    if not win or not json_path:
        return
    try:
        win.update_idletasks()
    except Exception:
        pass
    image = None
    try:
        builder = getattr(win, 'build_preview_image', None)
        if callable(builder):
            image = builder(scale=scale)
    except Exception:
        image = None
    if image is None:
        try:
            image = _capture_window_image_for_preview(win)
            image = _resize_preview_image_helper(image, scale=scale)
        except Exception:
            image = None
    if image is not None:
        _db_store_preview(json_path, image)


def _save_preview_for_current_window(win, json_path):
    _save_preview_image_for_window(win, json_path, scale=0.75)


def _save_preview_for_saved_template(ctx, template_path):
    if not template_path:
        return
    data = safe_read_json(template_path)
    if not isinstance(data, dict):
        return
    press = data.get('press') or ''
    fmt = data.get('format') or ''
    cfg = CONFIG_MAP.get((press, fmt))
    if not cfg:
        return
    image = render_layout_preview_image_from_data(data, dict(cfg), scale=0.75, title_base=f"{press} - {fmt}", template_mode=True)
    if image is not None:
        _db_store_preview(template_path, image)


def regenerate_preview_image_for_json_path(json_path, template_mode=False, default_dir=None, prompt_save_template=None, scale=0.75):
    if not _db_parse_virtual_path(json_path):
        return _FS_regenerate_preview_image_for_json_path(json_path, template_mode=template_mode, default_dir=default_dir, prompt_save_template=prompt_save_template, scale=scale)
    data = safe_read_json(json_path)
    if not data:
        raise RuntimeError(f"Could not read: {json_path}")
    press = data.get('press')
    fmt = data.get('format')
    if not press or not fmt:
        raise RuntimeError("JSON missing 'press' or 'format'.")
    base_cfg = CONFIG_MAP.get((press, fmt))
    if not base_cfg:
        raise RuntimeError(f"No config found for {press} - {fmt}")
    image = render_layout_preview_image_from_data(data, dict(base_cfg), scale=scale, title_base=f"{press} - {fmt}", template_mode=bool(template_mode))
    if image is None:
        raise RuntimeError(f"Could not build preview for: {json_path}")
    _db_store_preview(json_path, image)
    return preview_image_path_for_json(json_path)


def _db_unique_virtual_path(record_type, requested_file_name, current_path=None):
    requested_file_name = _db_normalize_file_name(requested_file_name)
    desired_path = _db_make_virtual_path(record_type, requested_file_name)
    if current_path and os.path.normcase(str(current_path)) == os.path.normcase(str(desired_path)):
        return desired_path
    if not _db_record_exists(desired_path):
        return desired_path
    base, ext = os.path.splitext(requested_file_name)
    counter = 1
    while True:
        candidate = _db_make_virtual_path(record_type, f"{base}_{counter}{ext}")
        if current_path and os.path.normcase(str(current_path)) == os.path.normcase(str(candidate)):
            return candidate
        if not _db_record_exists(candidate):
            return candidate
        counter += 1


def save_regular_from_layout(ctx, parent=None):
    try:
        data = collect_layout_data(ctx)
        data['issue_date'] = ''
        errors = validate_layout_data_for_mode(data, template_mode=False, regular_mode=True)
        if errors:
            messagebox.showerror('Save as Regular Failed', 'Please fix the following before saving as a regular:\n\n' + '\n'.join(f'• {item}' for item in errors), parent=parent)
            return False, None
        regular_path = _db_unique_virtual_path('regular', build_regular_filename_suggestion(ctx))
        data['name'] = os.path.splitext(os.path.basename(regular_path))[0]
        safe_write_json(regular_path, data)
        if parent is not None:
            try:
                _save_preview_for_current_window(parent, regular_path)
            except Exception:
                pass
        messagebox.showinfo('Regular Saved', f"Regular saved as:\n{os.path.basename(regular_path)}", parent=parent)
        return True, regular_path
    except Exception as e:
        messagebox.showerror('Save as Regular Failed', f"Could not save regular:\n{str(e)}", parent=parent)
        return False, None


def save_template_from_layout(ctx):
    try:
        data = collect_layout_data(ctx)
        data = _normalize_template_data(data)
        data.pop('issue_date', None)
        data.pop('product', None)
        data.pop('color_cells', None)
        template_path = _db_unique_virtual_path('template', build_filename_suggestion(ctx))
        data['name'] = os.path.splitext(os.path.basename(template_path))[0]
        safe_write_json(template_path, data)
        _save_preview_for_saved_template(ctx, template_path)
        messagebox.showinfo('Template Saved', f"Template saved as:\n{os.path.basename(template_path)}")
    except Exception as e:
        messagebox.showerror('Save Template Failed', f"Could not save template:\n{str(e)}")


def _db_prompt_save_name(parent, title, initial_name):
    suggested = _db_normalize_file_name(initial_name)
    value = simpledialog.askstring(title, 'Record name (.json will be added automatically if omitted):', initialvalue=suggested, parent=parent)
    if value is None:
        return None
    return _db_normalize_file_name(value)


def _db_lock_context():
    return {'opened_by': get_windows_username(), 'hostname': socket.gethostname(), 'process_id': os.getpid()}


def _db_cleanup_stale_locks(cur, schema, stale_minutes):
    cur.execute(f"DELETE FROM {schema}.record_locks WHERE heartbeat_at < (NOW() - (%s * INTERVAL '1 minute'))", (int(stale_minutes),))


def _db_lock_status_for_path(path):
    parsed = _db_parse_virtual_path(path)
    if not parsed or not parsed.get('file_name'):
        return {'record_exists': False, 'conflict': False}
    with _db_cursor() as (cur, config):
        schema = _db_pg_ident(config.get('schema'))
        stale_minutes = int(config.get('stale_minutes', _DB_LOCK_DEFAULTS['stale_minutes']))
        _db_cleanup_stale_locks(cur, schema, stale_minutes)
        cur.execute(f'''SELECT r.id AS record_id, r.file_name, l.opened_by, l.hostname, l.process_id FROM {schema}.records r LEFT JOIN {schema}.record_locks l ON l.record_type = r.record_type AND l.record_id = r.id WHERE r.record_type = %s AND r.file_name = %s''', (parsed['record_type'], parsed['file_name']))
        row = _db_fetchone(cur)
        if not row:
            return {'record_exists': False, 'conflict': False}
        context = _db_lock_context()
        conflict = bool(row.get('opened_by')) and (str(row.get('opened_by') or '').strip().lower() != str(context['opened_by']).strip().lower() or str(row.get('hostname') or '').strip().lower() != str(context['hostname']).strip().lower() or int(row.get('process_id') or 0) != int(context['process_id']))
        return {'record_exists': True, 'conflict': conflict, 'opened_by': row.get('opened_by'), 'hostname': row.get('hostname'), 'process_id': row.get('process_id'), 'record_id': row.get('record_id'), 'record_type': parsed['record_type'], 'file_name': parsed['file_name']}


def _db_acquire_lock(path):
    status = _db_lock_status_for_path(path)
    if not status.get('record_exists') or status.get('conflict'):
        return status
    parsed = _db_parse_virtual_path(path)
    context = _db_lock_context()
    with _db_cursor() as (cur, config):
        schema = _db_pg_ident(config.get('schema'))
        stale_minutes = int(config.get('stale_minutes', _DB_LOCK_DEFAULTS['stale_minutes']))
        _db_cleanup_stale_locks(cur, schema, stale_minutes)
        cur.execute(f'''INSERT INTO {schema}.record_locks (record_type, record_id, opened_by, hostname, process_id, opened_at, heartbeat_at) SELECT r.record_type, r.id, %s, %s, %s, NOW(), NOW() FROM {schema}.records r WHERE r.record_type = %s AND r.file_name = %s ON CONFLICT (record_type, record_id) DO UPDATE SET opened_by = EXCLUDED.opened_by, hostname = EXCLUDED.hostname, process_id = EXCLUDED.process_id, heartbeat_at = NOW()''', (context['opened_by'], context['hostname'], context['process_id'], parsed['record_type'], parsed['file_name']))
    status['conflict'] = False
    return status


def _db_release_lock(path):
    parsed = _db_parse_virtual_path(path)
    if not parsed or not parsed.get('file_name'):
        return
    context = _db_lock_context()
    with _db_cursor() as (cur, config):
        schema = _db_pg_ident(config.get('schema'))
        cur.execute(f'''DELETE FROM {schema}.record_locks l USING {schema}.records r WHERE l.record_type = r.record_type AND l.record_id = r.id AND r.record_type = %s AND r.file_name = %s AND l.opened_by = %s AND COALESCE(l.hostname, '') = %s AND COALESCE(l.process_id, 0) = %s''', (parsed['record_type'], parsed['file_name'], context['opened_by'], context['hostname'], context['process_id']))


def _db_heartbeat_lock(path):
    parsed = _db_parse_virtual_path(path)
    if not parsed or not parsed.get('file_name'):
        return
    context = _db_lock_context()
    updated_count = 0
    with _db_cursor() as (cur, config):
        schema = _db_pg_ident(config.get('schema'))
        cur.execute(f'''UPDATE {schema}.record_locks l SET heartbeat_at = NOW() FROM {schema}.records r WHERE l.record_type = r.record_type AND l.record_id = r.id AND r.record_type = %s AND r.file_name = %s AND l.opened_by = %s AND COALESCE(l.hostname, '') = %s AND COALESCE(l.process_id, 0) = %s''', (parsed['record_type'], parsed['file_name'], context['opened_by'], context['hostname'], context['process_id']))
        try:
            updated_count = int(cur.rowcount or 0)
        except Exception:
            updated_count = 0
    if updated_count <= 0:
        # A DB Maintenance lock refresh intentionally clears the lock table.
        # Active editor windows should claim their own record again on the next
        # heartbeat so truly open records become protected again automatically.
        try:
            _db_acquire_lock(path)
        except Exception:
            pass

def _db_refresh_all_record_locks():
    'Clear all database edit locks and return the lock rows that were removed.'
    removed_rows = []
    with _db_cursor() as (cur, config):
        schema = _db_pg_ident(config.get('schema'))
        cur.execute(f'''SELECT l.record_type, r.file_name, COALESCE(r.name, r.file_stem, r.file_name) AS name, l.opened_by, l.hostname, l.process_id, l.opened_at, l.heartbeat_at FROM {schema}.record_locks l JOIN {schema}.records r ON r.record_type = l.record_type AND r.id = l.record_id ORDER BY l.heartbeat_at, l.opened_by, r.file_name''')
        removed_rows = _db_fetchall(cur)
        cur.execute(f'DELETE FROM {schema}.record_locks')
    return removed_rows


def _db_warn_if_locked(path, parent=None, title='Record Already Open'):
    status = _db_lock_status_for_path(path)
    if status.get('conflict'):
        messagebox.showwarning(title, f"{os.path.basename(path)} is currently open by {status.get('opened_by') or 'another user'} on {status.get('hostname') or 'another workstation'}.\n\nYou can continue, but another user may be editing the same record.", parent=parent)
    return status


def _db_attach_window_lock(win, ctx, warn_on_conflict=False):
    path = ctx.get('file_path') if isinstance(ctx, dict) else None
    if not path or not _db_parse_virtual_path(path):
        return
    previous_path = getattr(win, '_db_locked_path', None)
    if previous_path and previous_path != path:
        try:
            _db_release_lock(previous_path)
        except Exception:
            pass
        win._db_locked_path = None
    status = _db_warn_if_locked(path, parent=win) if warn_on_conflict else _db_lock_status_for_path(path)
    if not status.get('conflict'):
        _db_acquire_lock(path)
        win._db_locked_path = path
    else:
        win._db_locked_path = None
    heartbeat_ms = max(5000, int(_db_load_config().get('heartbeat_seconds', 30)) * 1000)
    prior_job = getattr(win, '_db_lock_heartbeat_job', None)
    if prior_job is not None:
        try:
            win.after_cancel(prior_job)
        except Exception:
            pass
    def _heartbeat():
        try:
            current_path = getattr(win, '_db_locked_path', None)
            if current_path:
                _db_heartbeat_lock(current_path)
            if win.winfo_exists():
                win._db_lock_heartbeat_job = win.after(heartbeat_ms, _heartbeat)
        except Exception:
            win._db_lock_heartbeat_job = None
    try:
        win._db_lock_heartbeat_job = win.after(heartbeat_ms, _heartbeat)
    except Exception:
        win._db_lock_heartbeat_job = None
    if not getattr(win, '_db_lock_destroy_bound', False):
        def _on_destroy(event):
            try:
                if event.widget is not win:
                    return
            except Exception:
                pass
            current_path = getattr(win, '_db_locked_path', None)
            if current_path:
                try:
                    _db_release_lock(current_path)
                except Exception:
                    pass
                win._db_locked_path = None
        try:
            win.bind('<Destroy>', _on_destroy, add='+')
            win._db_lock_destroy_bound = True
        except Exception:
            pass


def do_save(win, ctx):
    path = ctx.get('file_path') if isinstance(ctx, dict) else None
    if path:
        status = _db_warn_if_locked(path, parent=win, title='Save Warning')
        if status.get('conflict') and not messagebox.askyesno('Continue Saving?', 'Another user currently has this record open.\n\nDo you still want to save your changes?', parent=win):
            return False
    ok = _FS_do_save(win, ctx)
    if ok:
        _db_attach_window_lock(win, ctx, warn_on_conflict=False)
    return ok


def do_save_as(win, ctx):
    ok, data = validate_layout_ctx_before_save(ctx, parent=win)
    if not ok:
        return False
    record_type = 'template' if ctx.get('template_mode', False) else ('regular' if _ctx_is_regular_mode(ctx) else 'layout')
    title = 'Save Template As' if record_type == 'template' else ('Save Regular Layout As' if record_type == 'regular' else 'Save Layout As')
    file_name = _db_prompt_save_name(win, title, build_save_filename_suggestion(ctx))
    if not file_name:
        return False
    path = _db_make_virtual_path(record_type, file_name)
    status = _db_warn_if_locked(path, parent=win, title='Save Warning')
    if status.get('conflict') and not messagebox.askyesno('Continue Saving?', 'Another user currently has this record open.\n\nDo you still want to save your changes?', parent=win):
        return False
    try:
        if ctx.get('template_mode', False):
            data = _normalize_template_data(data)
        data = dict(data)
        for _copy_key in ('_db_record_id', '_db_record_type', '_file_path', '_layout_name'):
            data.pop(_copy_key, None)
        # Save As is a copy operation: the new record should carry the new
        # record/template name, even when the source already had a name.
        data['name'] = os.path.splitext(os.path.basename(path))[0]
        safe_write_json(path, data)
        _save_preview_for_current_window(win, path)
        ctx['file_path'] = path
        ctx['layout_name'] = data['name']
        win.title(f"{ctx['title_base']}  —  {os.path.basename(path)}")
        if (not ctx.get('template_mode', False)) and ctx.get('prompt_save_template', True) and not _template_exists_for_imposition(ctx):
            template_suggestion = build_filename_suggestion(ctx)
            if messagebox.askyesno('Save as Template', f"This layout has a new imposition that doesn't match any existing template.\n\nWould you like to save it as a template?\n\nTemplate name: {template_suggestion}", parent=win):
                save_template_from_layout(ctx)
        _db_attach_window_lock(win, ctx, warn_on_conflict=False)
        return True
    except Exception as e:
        messagebox.showerror('Save Failed', str(e), parent=win)
        return False


def build_press_layout(win, title='Press Layout', config=None, load_path=None, load_as_copy=False, initial_data=None):
    units = _FS_build_press_layout(win, title=title, config=config, load_path=load_path, load_as_copy=load_as_copy, initial_data=initial_data)
    ctx = getattr(win, '_press_layout_ctx', None)
    if isinstance(ctx, dict) and ctx.get('file_path'):
        _db_attach_window_lock(win, ctx, warn_on_conflict=True)
    return units


def load_changelog_data():
    data = _FS_load_changelog_data()
    if isinstance(data, dict):
        return data
    return json.loads(json.dumps(DEFAULT_CHANGELOG_DATA))


def _db_os_path_exists(path):
    parsed = _db_parse_virtual_path(path)
    return _db_record_exists(path) if parsed and parsed.get('file_name') else _FS_os_path_exists(path)


def _db_os_remove(path):
    parsed = _db_parse_virtual_path(path)
    if parsed and parsed.get('file_name'):
        _db_delete_record(path)
        return
    return _FS_os_remove(path)


os.path.exists = _db_os_path_exists
os.remove = _db_os_remove

# =============================================================================
# Application entry point
# Startup bootstrap for database selection, update/runtime checks, launcher creation, and the final Tk mainloop.
# =============================================================================

def main():
    if not ensure_single_main_launcher_instance():
        return
    try:
        if not prompt_admin_db_config_selection():
            return
        _db_bootstrap()
        build_main_launcher()
    finally:
        _db_close_pool()
        release_single_main_launcher_instance()


if __name__ == '__main__':
    main()
