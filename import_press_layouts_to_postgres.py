#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from datetime import datetime

CONFIG_FILENAME = 'press_layouts_db.json'
COLLECTIONS = {'layout': 'Layouts', 'template': 'Templates', 'regular': 'Regular'}


def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    data.setdefault('maintenance_database', 'postgres')
    data.setdefault('sslmode', 'prefer')
    data.setdefault('schema', 'press_layouts')
    data.setdefault('database', 'press_layouts')
    return data


def import_driver():
    try:
        import importlib
        return importlib.import_module("psycopg2")
    except Exception:
        import importlib
        return importlib.import_module("psycopg")


def pg_ident(value):
    return '"' + str(value).replace('"', '""') + '"'


def connect(config, maintenance=False):
    driver = import_driver()
    kwargs = {
        'host': config.get('host'),
        'port': int(config.get('port', 5432)),
        'user': config.get('user'),
        'password': config.get('password'),
        'dbname': config.get('maintenance_database') if maintenance else config.get('database'),
    }
    if config.get('sslmode'):
        kwargs['sslmode'] = config.get('sslmode')
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


def bootstrap(config):
    schema = pg_ident(config.get('schema'))

    # CREATE DATABASE must be executed outside a transaction block.
    conn = connect(config, maintenance=True)
    try:
        cur = conn.cursor()
        try:
            cur.execute('SELECT 1 FROM pg_database WHERE datname = %s', (config.get('database'),))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE {pg_ident(config.get("database"))}')
        finally:
            cur.close()
    finally:
        conn.close()

    conn = connect(config, maintenance=False)
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
        finally:
            cur.close()
    finally:
        conn.close()


def upsert_record(config, record_type, file_name, data, preview_png=None):
    schema = pg_ident(config.get('schema'))
    file_name = file_name if file_name.lower().endswith('.json') else file_name + '.json'
    saved_at = data.get('saved_at') or datetime.now().isoformat(timespec='seconds')
    with connect(config, maintenance=False) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f'''INSERT INTO {schema}.records (
                    record_type, file_name, file_stem, name, press, format, issue_date, product,
                    section_count, section_pages, saved_at, last_changed_by, data, preview_png,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s::jsonb, %s, %s, %s::jsonb, %s,
                    NOW(), NOW()
                ) ON CONFLICT (record_type, file_name) DO UPDATE SET
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
                    preview_png = COALESCE(EXCLUDED.preview_png, {schema}.records.preview_png),
                    updated_at = NOW()''',
                (
                    record_type,
                    file_name,
                    os.path.splitext(file_name)[0],
                    data.get('name') or os.path.splitext(file_name)[0],
                    data.get('press'),
                    data.get('format'),
                    data.get('issue_date'),
                    data.get('product'),
                    int(data.get('section_count', 1) or 1),
                    json.dumps(data.get('section_pages', []), default=str),
                    saved_at,
                    data.get('last_changed_by'),
                    json.dumps(data, default=str),
                    preview_png,
                ),
            )


def import_collection(config, base_dir, record_type):
    folder = Path(base_dir) / COLLECTIONS[record_type]
    if not folder.exists():
        print(f'Skipping missing folder: {folder}')
        return 0
    imported = 0
    for json_path in sorted(folder.glob('*.json')):
        with json_path.open('r', encoding='utf-8') as fh:
            data = json.load(fh)
        preview_path = json_path.with_suffix('.preview.png')
        preview_png = preview_path.read_bytes() if preview_path.exists() else None
        upsert_record(config, record_type, json_path.name, data, preview_png=preview_png)
        imported += 1
        print(f'Imported {record_type}: {json_path.name}')
    return imported


def main():
    parser = argparse.ArgumentParser(description='Import Press Layout flat files into PostgreSQL.')
    parser.add_argument('--base-dir', default=str(Path(__file__).resolve().parent), help='Folder that contains Layouts, Templates, and Regular.')
    parser.add_argument('--config', default=str(Path(__file__).resolve().parent / CONFIG_FILENAME), help='Path to the PostgreSQL connection JSON file.')
    args = parser.parse_args()
    config = load_config(args.config)
    bootstrap(config)
    total = 0
    for record_type in ('layout', 'template', 'regular'):
        total += import_collection(config, args.base_dir, record_type)
    print(f'Imported {total} total records.')


if __name__ == '__main__':
    main()
