"""Press Layout Core (final consolidated version)."""

import os
import json
import glob
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ===== BEGIN: config.py =====
MAIN_DIR = os.path.dirname(os.path.abspath(__file__))
LAYOUTS_DIR = os.path.join(MAIN_DIR, "Layouts")
TEMPLATE_DIR = os.path.join(MAIN_DIR, "Templates")
REGULAR_DIR = os.path.join(MAIN_DIR, "Regular")
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

# ===== END: config.py =====

# ===== BEGIN: helpers.py =====
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, "_")
    return name.strip()
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
def apply_min_pages_to_section_vars(format_name, section_count_var, section_page_vars, fill_only_blanks=True):
    """
    Ensure enabled section page values are valid for the format.
    - fill_only_blanks=True: only fills blanks/invalids
    - fill_only_blanks=False: forces enabled sections to minimum
    """
    minimum = min_pages_for_format(format_name)

    try:
        count = int(section_count_var.get())
    except Exception:
        count = 1
    count = max(1, min(4, count))
    section_count_var.set(str(count))

    for i in range(4):
        if i < count:
            current = section_page_vars[i].get().strip()
            if fill_only_blanks:
                if (current == "") or (not is_valid_page_count(current, minimum)):
                    section_page_vars[i].set(str(minimum))
            else:
                section_page_vars[i].set(str(minimum))
        else:
            section_page_vars[i].set("")
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
def build_layout_rows():
    ensure_dir(LAYOUTS_DIR)
    rows = []

    for path in sorted(glob.glob(os.path.join(LAYOUTS_DIR, "*.json"))):
        data = safe_read_json(path) or {}

        press = data.get("press", "") or ""
        fmt = data.get("format", "") or ""
        issue = data.get("issue_date", "") or ""
        product = data.get("product", "") or ""
        saved_at = data.get("saved_at", "") or ""

        issue_dt = parse_issue_date_flexible(issue)
        saved_dt = parse_saved_at(saved_at)

        rows.append({
            "path": path,
            "issue_dt": issue_dt,
            "issue_disp": fmt_issue_for_display(issue),
            "product": product,
            "press": press,
            "format": fmt,
            "saved_dt": saved_dt,
            "saved_disp": fmt_dt_for_display(saved_dt),
        })

    return rows
def build_layout_filename_suggestion(ctx) -> str:
    raw_date = ctx["issue_entry"].get().strip() if ctx.get("issue_entry") else ""
    raw_product = ctx["product_entry"].get().strip() if ctx.get("product_entry") else ""

    dt = parse_issue_date_flexible(raw_date)
    date_part = dt.strftime("%m%d%Y") if dt else "00000000"
    product_part = raw_product if raw_product else "Layout"
    return sanitize_filename(f"{date_part} - {product_part}.json").strip()
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

        def sort_key(u):
            m = unit_min_page_number(u)
            return (m is None, m if m is not None else 10**9)

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
        return _goto(prev_map[w])

    def on_right(event):
        w = event.widget
        if w in grid_lookup:
            return grid_right(w)
        return _goto(next_map[w])

    def on_up(event):
        w = event.widget
        if w in grid_lookup:
            return grid_up(w)
        return _goto(prev_map[w])

    def on_down(event):
        w = event.widget
        if w in grid_lookup:
            return grid_down(w)
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

            cell_entry = ttk.Entry(cell_container, justify="center", font=cell_font, width=cell_width)
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


def load_window_state_map():
    data = safe_read_json(window_state_file_path())
    return data if isinstance(data, dict) else {}


def save_window_state_map(state_map):
    if not isinstance(state_map, dict):
        return
    safe_write_json(window_state_file_path(), state_map)


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
            state_map[state_key] = state
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

# ===== END: helpers.py =====

# ===== BEGIN: persistence.py =====
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
        from press_layout_ui import render_layout_preview_image_from_data
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


def _validate_used_units_have_sections(ctx, parent=None) -> bool:
    offending_labels = []
    for unit_ctx in ctx.get("units", []):
        try:
            section_value = (unit_ctx["section_entry"].get() or "").strip()
        except Exception:
            section_value = ""
        if section_value:
            continue
        if _unit_has_assigned_pages(unit_ctx):
            offending_labels.append(str(unit_ctx.get("label") or "Unit"))

    if not offending_labels:
        return True

    labels_text = ", ".join(offending_labels)
    messagebox.showerror(
        "Missing Section Assignment",
        "All units with pages assigned must be assigned a section before saving.\n\n"
        f"Units missing a section: {labels_text}",
        parent=parent,
    )
    return False



def collect_layout_data(ctx):
    now = datetime.now().isoformat(timespec="seconds")
    data = {
        "version": 1,
        "name": ctx.get("layout_name") or "",
        "press": ctx["press_name"],
        "format": ctx["format_name"],
        "saved_at": now,
        "issue_date": ctx["issue_entry"].get().strip() if ctx.get("issue_entry") else "",
        "product": ctx["product_entry"].get().strip() if ctx.get("product_entry") else "",
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
        data["color_cells"] = [
            {"unit": unit, "r": int(r), "c": int(c)}
            for (unit, r, c) in sorted(ctx.get("color_cells", set()))
        ]
    return data
def populate_layout_from_data(ctx, data):
    if ctx.get("issue_entry"):
        ctx["issue_entry"].state(["!disabled"])
        ctx["issue_entry"].delete(0, "end")
        ctx["issue_entry"].insert(0, data.get("issue_date", ""))
        if ctx.get("template_mode"):
            ctx["issue_entry"].state(["disabled"])

    if ctx.get("product_entry"):
        ctx["product_entry"].state(["!disabled"])
        ctx["product_entry"].delete(0, "end")
        ctx["product_entry"].insert(0, data.get("product", ""))
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
    if not ctx.get("file_path"):
        return do_save_as(win, ctx)
    if not _validate_used_units_have_sections(ctx, parent=win):
        return False
    try:
        data = collect_layout_data(ctx)
        if ctx.get("template_mode", False):
            data = _normalize_template_data(data)
        safe_write_json(ctx["file_path"], data)
        _save_preview_for_current_window(win, ctx["file_path"])
        
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
    if not _validate_used_units_have_sections(ctx, parent=win):
        return False
    default_dir = ctx.get("default_dir", LAYOUTS_DIR)
    ensure_dir(default_dir)

    if ctx.get("template_mode"):
        suggested = build_filename_suggestion(ctx)
    else:
        suggested = build_layout_filename_suggestion(ctx)

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
        data = collect_layout_data(ctx)
        if ctx.get("template_mode", False):
            data = _normalize_template_data(data)
        if not data.get("name"):
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


def _template_exists_for_imposition(ctx) -> bool:
    """Check if a template with the same imposition already exists.

    The prompt shown to the user is about imposition matching, so the primary
    comparison should be the generated imposition/template name. As a fallback,
    we also do a structural match against the template JSON in case a template
    was renamed manually.
    """
    ensure_dir(TEMPLATE_DIR)
    press = ctx.get("press_name", "")
    fmt = ctx.get("format_name", "")

    current_data = _normalize_template_data(collect_layout_data(ctx))
    current_data.pop("issue_date", None)
    current_data.pop("product", None)
    current_data.pop("color_cells", None)

    target_imposition_name = build_imposition_text(ctx)
    current_section_count = current_data.get("section_count")
    current_section_pages = current_data.get("section_pages")
    current_units_by_label = {
        str(unit.get("label") or ""): unit.get("grid", [])
        for unit in (current_data.get("units", []) or [])
        if isinstance(unit, dict)
    }

    template_files = sorted(glob.glob(os.path.join(TEMPLATE_DIR, "*.json")))
    for tmpl_path in template_files:
        tmpl_data = safe_read_json(tmpl_path)
        if not isinstance(tmpl_data, dict):
            continue

        if tmpl_data.get("press") != press or tmpl_data.get("format") != fmt:
            continue

        template_stem = os.path.splitext(os.path.basename(tmpl_path))[0]
        template_name = tmpl_data.get("name") or template_stem
        if _imposition_name_matches(template_name, target_imposition_name) or _imposition_name_matches(template_stem, target_imposition_name):
            return True

        normalized_template = _normalize_template_data(tmpl_data)
        if normalized_template.get("section_count") != current_section_count:
            continue
        if normalized_template.get("section_pages") != current_section_pages:
            continue

        template_units_by_label = {
            str(unit.get("label") or ""): unit.get("grid", [])
            for unit in (normalized_template.get("units", []) or [])
            if isinstance(unit, dict)
        }
        if template_units_by_label == current_units_by_label:
            return True

    return False
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

# ===== END: persistence.py =====