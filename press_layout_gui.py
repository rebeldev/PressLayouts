import os
import json
import glob
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ------------------ SETTINGS ------------------
MAIN_DIR = r"C:\Users\MBradbury\Documents\Press Layouts"
LAYOUTS_DIR = os.path.join(MAIN_DIR, "Layouts")
TEMPLATE_DIR = os.path.join(MAIN_DIR, "Templates")

# ------------------ FORMAT RULES ------------------
FORMAT_MIN_PAGES = {
    "Broadsheet": 2,
    "Tab": 4,
    "8 up": 8,
}

# ------------------ DIR / JSON HELPERS ------------------
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

# ------------------ SECTION MIN-PAGES HELPERS ------------------
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

# ------------------ DATE HELPERS (flexible parsing) ------------------
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

# ------------------ LAYOUT FILENAME SUGGESTION (layouts only) ------------------
def build_layout_filename_suggestion(ctx) -> str:
    raw_date = ctx["issue_entry"].get().strip() if ctx.get("issue_entry") else ""
    raw_product = ctx["product_entry"].get().strip() if ctx.get("product_entry") else ""

    dt = parse_issue_date_flexible(raw_date)
    date_part = dt.strftime("%m%d%Y") if dt else "00000000"
    product_part = raw_product if raw_product else "Layout"
    return sanitize_filename(f"{date_part} - {product_part}.json").strip()

# ------------------ TEMPLATE NAME (existing) HELPERS ------------------
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

def build_filename_suggestion(ctx) -> str:
    # Template-style suggestion
    press_name = ctx.get("press_name", "")
    press_num = "1" if "1" in press_name else "2"
    prefix = f"P{press_num}"

    try:
        section_count = int(ctx["section_count_var"].get())
    except Exception:
        section_count = 1
    section_count = max(1, min(4, section_count))

    pages = []
    for i in range(section_count):
        try:
            pages.append(max(1, int(ctx["section_page_vars"][i].get().strip())))
        except Exception:
            pages.append(1)

    units_by_section = {i: [] for i in range(1, section_count + 1)}
    for u in ctx["units"]:
        sec_id = parse_section_id(u["section_entry"].get())
        if sec_id is None:
            continue
        if 1 <= sec_id <= section_count:
            units_by_section[sec_id].append(u)

    segments = []
    for sec_idx in range(1, section_count + 1):
        sec_pages = pages[sec_idx - 1]
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

# ------------------ TAB ORDER + ARROWS ------------------
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

    # top row forward
    if grid_rows >= 1:
        r = 0
        for lab in unit_order:
            row_entries = unit_map[lab]["entries"][r]
            for c in range(min(grid_cols, len(row_entries))):
                focus_widgets.append(row_entries[c])

    # bottom row reverse, columns reversed
    for r in range(1, grid_rows):
        for lab in reversed(unit_order):
            row_entries = unit_map[lab]["entries"][r]
            last_col = min(grid_cols, len(row_entries)) - 1
            for c in range(last_col, -1, -1):
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

    def _goto(target):
        target.focus_set()
        return "break"

    for i, w in enumerate(ordered):
        nxt = ordered[(i + 1) % n]
        prv = ordered[(i - 1) % n]
        try:
            w.configure(takefocus=True)
        except Exception:
            pass
        w.bind("<Tab>", lambda e, _n=nxt: _goto(_n))
        w.bind("<Shift-Tab>", lambda e, _p=prv: _goto(_p))
        w.bind("<ISO_Left_Tab>", lambda e, _p=prv: _goto(_p))

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

# ------------------ UI HELPERS ------------------
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
):
    unit_frame = ttk.Frame(parent, style="Unit.TFrame", padding=unit_padding)

    section_entry = ttk.Entry(unit_frame, width=8, justify="center", font=(None, 10))
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
            cell_entry.pack(fill="both", expand=True)

            overlay = tk.Canvas(cell_container, highlightthickness=0, bg="#ffffff")
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

# ------------------ SAVE/LOAD ------------------
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
        "section_pages": [min_pages_for_format(ctx.get("format_name", ""))],
        "units": []
    }

    if ctx.get("section_count_var"):
        try:
            section_count = int(ctx["section_count_var"].get())
        except Exception:
            section_count = 1
        section_count = max(1, min(4, section_count))

        pages = []
        for i in range(section_count):
            text = ctx["section_page_vars"][i].get().strip()
            try:
                pages.append(max(1, int(text)))
            except Exception:
                pages.append(min_pages_for_format(ctx.get("format_name", "")))

        data["section_count"] = section_count
        data["section_pages"] = pages

    for u in ctx["units"]:
        section = u["section_entry"].get().strip()
        grid = []
        for row in u["entries"]:
            grid.append([cell.get().strip() for cell in row])
        data["units"].append({"label": u["label"], "section": section, "grid": grid})

    # ---- per-cell color selection (layouts only) ----
    if not ctx.get("template_mode", False):
        # store list of dicts for JSON stability
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

    unit_map = {u["label"]: u for u in ctx["units"]}
    for udata in data.get("units", []):
        label = udata.get("label")
        if label not in unit_map:
            continue
        u = unit_map[label]
        u["section_entry"].delete(0, "end")
        u["section_entry"].insert(0, udata.get("section", ""))

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
    try:
        data = collect_layout_data(ctx)
        safe_write_json(ctx["file_path"], data)
        messagebox.showinfo("Saved", f"Saved:\n{ctx['file_path']}")
        return True
    except Exception as e:
        messagebox.showerror("Save Failed", str(e))
        return False

def do_save_as(win, ctx):
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
        if not data.get("name"):
            data["name"] = os.path.splitext(os.path.basename(path))[0]
        safe_write_json(path, data)
        ctx["file_path"] = path
        ctx["layout_name"] = data["name"]
        win.title(f"{ctx['title_base']}  —  {os.path.basename(path)}")
        messagebox.showinfo("Saved", f"Saved:\n{path}")
        return True
    except Exception as e:
        messagebox.showerror("Save As Failed", str(e))
        return False

# ------------------ LAYOUT WINDOW ------------------
def build_press_layout(win, title="Press Layout", config=None, load_path=None, load_as_copy=False):
    config = config or {}

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

    btn_frame = ttk.Frame(header_frame)
    btn_frame.grid(row=0, column=6, sticky="e")

    header_frame.columnconfigure(2, weight=1)
    header_frame.columnconfigure(3, weight=1)
    header_frame.columnconfigure(4, weight=1)
    header_frame.columnconfigure(5, weight=1)
    header_frame.columnconfigure(6, weight=0)

    # template mode disables issue/product
    if template_mode:
        issue_entry.state(["disabled"])
        product_entry.state(["disabled"])

    # Sections
    section_count_var = tk.StringVar(value=str(config.get("section_count", 1)))
    section_page_vars = []
    section_page_entries = []

    ttk.Label(header_frame, text="Sections:", font=(None, 12, "bold")).grid(row=1, column=0, sticky="w", pady=6)
    sections_spinbox = ttk.Spinbox(header_frame, from_=1, to=4, textvariable=section_count_var, width=3, justify="center")
    sections_spinbox.grid(row=1, column=1, sticky="w", padx=(8, 32))

    pages_frame = ttk.Frame(header_frame)
    pages_frame.grid(row=1, column=3, columnspan=2, sticky="w", padx=(8, 24))
    ttk.Label(pages_frame, text="Section pages:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")

    format_name = config.get("format_name", "")
    page_increment = min_pages_for_format(format_name)
    max_pages = page_increment * 10

    initial_pages = config.get("section_pages", [page_increment] * 4)
    for idx in range(4):
        page_value = str(initial_pages[idx] if idx < len(initial_pages) else page_increment)
        var = tk.StringVar(value=page_value)
        section_page_vars.append(var)

        ttk.Label(pages_frame, text=f"S{idx + 1}", font=(None, 10)).grid(
            row=0, column=1 + idx * 2, sticky="e", padx=(10, 2)
        )
        sp = ttk.Spinbox(
            pages_frame,
            from_=page_increment,
            to=max_pages,
            increment=page_increment,
            textvariable=var,
            width=4,
            justify="center"
        )
        sp.grid(row=0, column=2 + idx * 2, sticky="w")
        section_page_entries.append(sp)

    def _update_section_page_states(count):
        for idx, entry in enumerate(section_page_entries):
            if idx < count:
                entry.state(["!disabled"])
            else:
                entry.state(["disabled"])
                section_page_vars[idx].set("")

    try:
        _update_section_page_states(int(section_count_var.get()))
    except Exception:
        _update_section_page_states(1)

    apply_min_pages_to_section_vars(format_name, section_count_var, section_page_vars, fill_only_blanks=True)

    # Press area
    press_area_frame = ttk.Frame(win, padding=(16, 0, 16, 12))
    press_area_frame.pack(fill="both", expand=True)

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
        )
        unit_frame.grid(row=0, column=idx, padx=unit_padx, pady=unit_pady, sticky="n")
        units.append({
            "label": label,
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
        )
        unit_frame.grid(row=0, column=len(left_labels) + 1 + idx, padx=unit_padx, pady=unit_pady, sticky="n")
        units.append({
            "label": label,
            "section_entry": section_entry,
            "entries": grid_entries,
            "overlays": cell_overlays,
            "color_capable": bool(use_cmyk),
        })

    # Context
    ctx = {
        "title_base": title_base,
        "press_name": config.get("press_name", ""),
        "format_name": format_name,
        "issue_entry": issue_entry,
        "product_entry": product_entry,
        "section_count_var": section_count_var,
        "section_page_vars": section_page_vars,
        "_update_section_page_states": _update_section_page_states,
        "imposition_var": imposition_var,
        "imposition_entry": imposition_entry,
        "units": units,
        "file_path": None,
        "layout_name": None,
        "template_mode": template_mode,
        "default_dir": TEMPLATE_DIR if template_mode else LAYOUTS_DIR,
        "color_cells": set(),  # per-cell storage
    }

    # ---- Color Select toggle (layouts only) ----
    color_select_var = tk.BooleanVar(value=False)
    color_toggle = None
    if not template_mode:
        color_toggle = ttk.Checkbutton(
            btn_frame,
            style="SlideToggle.TCheckbutton",
            text="Color Select",
            variable=color_select_var,
            takefocus=False
        )
        color_toggle.pack(side="left", padx=(0, 12))

    # Save buttons
    ttk.Button(btn_frame, text="Save", command=lambda: do_save(win, ctx), width=10, takefocus=False)\
        .pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="Save As", command=lambda: do_save_as(win, ctx), width=10, takefocus=False)\
        .pack(side="left")

    # Live imposition updater
    ctx["_imposition_updating"] = False

    def update_imposition(*_):
        if ctx["_imposition_updating"]:
            return
        ctx["_imposition_updating"] = True
        try:
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

    issue_entry.bind("<FocusOut>", on_issue_date_focus_out)
    issue_entry.bind("<Return>", lambda e: (on_issue_date_focus_out(), "break"))
    issue_entry.bind("<KeyRelease>", lambda e: update_imposition())

    product_entry.bind("<KeyRelease>", lambda e: update_imposition())
    product_entry.bind("<FocusOut>", lambda e: update_imposition())

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
            apply_min_pages_to_section_vars(format_name, section_count_var, section_page_vars, fill_only_blanks=True)
            update_imposition()
            refresh_color_overlays()
        finally:
            _busy["busy"] = False

    sections_spinbox.configure(command=_on_section_count_changed)
    section_count_var.trace_add("write", lambda *_: _on_section_count_changed())

    for var in section_page_vars:
        var.trace_add("write", lambda *_: update_imposition())

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

    def refresh_color_overlays():
        selecting = (not template_mode) and color_select_var.get()

        for u in ctx["units"]:
            color_ok = u.get("color_capable", False)
            overlays = u.get("overlays", [])
            entries = u.get("entries", [])

            for r in range(len(overlays)):
                for c in range(len(overlays[r])):
                    overlay = overlays[r][c]
                    entry = entries[r][c]
                    key = (u["label"], r, c)
                    circled = key in ctx["color_cells"]

                    if circled or (selecting and color_ok):
                        overlay_show(overlay)
                        overlay_render_cell(overlay, entry.get(), circled)
                    else:
                        overlay_hide(overlay)
                        overlay.delete("all")

    # bind overlay clicks
    for u in ctx["units"]:
        overlays = u["overlays"]
        for r in range(len(overlays)):
            for c in range(len(overlays[r])):
                ov = overlays[r][c]
                ov.bind("<Button-1>", lambda e, _u=u, _r=r, _c=c: toggle_color_cell(_u, _r, _c))

    if color_toggle is not None:
        color_toggle.configure(command=refresh_color_overlays)

    # ---- Load file (open vs copy) ----
    if load_path:
        data = safe_read_json(load_path)
        if data:
            populate_layout_from_data(ctx, data)
            apply_min_pages_to_section_vars(format_name, section_count_var, section_page_vars, fill_only_blanks=True)

            if load_as_copy:
                ctx["file_path"] = None
                ctx["layout_name"] = None
                tmpl = os.path.splitext(os.path.basename(load_path))[0]
                win.title(f"{title_base}  —  (from template: {tmpl})")
            else:
                ctx["file_path"] = load_path
                ctx["layout_name"] = data.get("name") or os.path.splitext(os.path.basename(load_path))[0]
                win.title(f"{title_base}  —  {os.path.basename(load_path)}")

    # initial refreshes
    update_imposition()
    refresh_color_overlays()

    # ---- tab order + arrows ----
    focus_list = build_focus_order(
        issue_entry=issue_entry,
        product_entry=product_entry,
        units=units,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        press_name=config.get("press_name", ""),
        extra_widgets=[sections_spinbox] + section_page_entries
    )
    set_custom_tab_order(focus_list)
    enable_arrow_navigation(focus_list, units, config.get("press_name", ""))

    win.after(50, issue_entry.focus_set)
    apply_window_sizing(win, config)
    return units

# =========================
# PART 3 — CONFIGS + LAUNCHERS + MAIN
# =========================

# ------------------ CONFIGS ------------------
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

# Press 1
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

# Press 2
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


# ------------------ TEMPLATE MATCHING (New Layout launcher) ------------------
def list_matching_templates(press_name, format_name, section_count=None, section_pages=None):
    """
    Templates live in TEMPLATE_DIR and are matched by JSON metadata.
    In the New Layout launcher, we additionally filter by section_count & section_pages.
    """
    ensure_dir(TEMPLATE_DIR)
    paths = sorted(glob.glob(os.path.join(TEMPLATE_DIR, "*.json")))

    results = []
    for p in paths:
        data = safe_read_json(p)
        stem = os.path.splitext(os.path.basename(p))[0]

        if not (data and isinstance(data, dict)):
            # fallback display if corrupt
            results.append((stem, p))
            continue

        if data.get("press") != press_name or data.get("format") != format_name:
            continue

        if section_count is not None:
            file_section_count = data.get("section_count")
            file_section_pages = data.get("section_pages", [])
            if file_section_count != section_count:
                continue
            if len(file_section_pages) < section_count:
                continue
            if any(file_section_pages[i] != section_pages[i] for i in range(section_count)):
                continue

        disp = data.get("name") or stem
        results.append((disp, p))

    return results


# ------------------ OPEN JSON INTO LAYOUT WINDOW ------------------
def open_json_in_layout(root, json_path, template_mode=False):
    data = safe_read_json(json_path)
    if not data:
        messagebox.showerror("Open Failed", f"Could not read:\n{json_path}")
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

    title = f"{press} - {fmt}"
    win = tk.Toplevel(root)
    build_press_layout(
        win,
        title=title,
        config=cfg,
        load_path=json_path,
        load_as_copy=False
    )


# ------------------ NEW LAYOUT LAUNCHER ------------------
def build_new_layout_launcher(parent):
    root = tk.Toplevel(parent)
    root.title("New Layout")
    root.geometry("760x420")
    root.minsize(720, 380)

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    # Press / Format
    ttk.Label(frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", pady=8, padx=(0, 8))
    press_var = tk.StringVar(value="Press 1")
    press_combo = ttk.Combobox(frame, textvariable=press_var, values=["Press 1", "Press 2"], state="readonly", width=16)
    press_combo.grid(row=0, column=1, sticky="w", padx=(0, 24))

    ttk.Label(frame, text="Format:", font=(None, 11, "bold")).grid(row=1, column=0, sticky="w", pady=8, padx=(0, 8))
    format_var = tk.StringVar(value="Broadsheet")
    format_combo = ttk.Combobox(frame, textvariable=format_var, values=["Broadsheet", "Tab", "8 up"], state="readonly", width=16)
    format_combo.grid(row=1, column=1, sticky="w", padx=(0, 24))

    # Sections + Pages
    ttk.Label(frame, text="Sections:", font=(None, 11, "bold")).grid(row=2, column=0, sticky="w", pady=8, padx=(0, 8))
    section_count_var = tk.StringVar(value="1")
    section_count_spinbox = ttk.Spinbox(frame, from_=1, to=4, textvariable=section_count_var, width=3, justify="center")
    section_count_spinbox.grid(row=2, column=1, sticky="w", padx=(0, 24))

    ttk.Label(frame, text="Pages:", font=(None, 11, "bold")).grid(row=2, column=2, sticky="w", padx=(0, 8))

    section_page_vars = []
    section_page_spinboxes = []
    for idx in range(4):
        var = tk.StringVar(value=str(min_pages_for_format(format_var.get())))
        section_page_vars.append(var)
        ttk.Label(frame, text=f"S{idx+1}:", font=(None, 10)).grid(row=2, column=3 + idx * 2, sticky="e", padx=(12, 4))
        spinbox = ttk.Spinbox(frame, from_=2, to=80, increment=2, textvariable=var, width=3, justify="center")
        spinbox.grid(row=2, column=4 + idx * 2, sticky="w")
        section_page_spinboxes.append(spinbox)

    # Templates list
    ttk.Label(frame, text="Templates:", font=(None, 11, "bold")).grid(row=3, column=0, sticky="nw", pady=(8, 0), padx=(0, 8))
    templates_frame = ttk.Frame(frame)
    templates_frame.grid(row=3, column=1, columnspan=7, sticky="nsew", pady=(8, 0))

    templates_listbox = tk.Listbox(templates_frame, height=8, width=72, exportselection=False)
    templates_listbox.grid(row=0, column=0, sticky="nsew")
    templates_scroll = ttk.Scrollbar(templates_frame, orient="vertical", command=templates_listbox.yview)
    templates_scroll.grid(row=0, column=1, sticky="ns")
    templates_listbox.configure(yscrollcommand=templates_scroll.set)
    templates_frame.rowconfigure(0, weight=1)
    templates_frame.columnconfigure(0, weight=1)

    frame.rowconfigure(3, weight=1)
    frame.columnconfigure(1, weight=1)

    template_paths = []

    def _update_section_page_states(count):
        for idx, sp in enumerate(section_page_spinboxes):
            if idx < count:
                sp.state(["!disabled"])
            else:
                sp.state(["disabled"])
                section_page_vars[idx].set("")

    def apply_min_pages_to_sections(fill_only_blanks=True):
        fmt = format_var.get()
        minimum = min_pages_for_format(fmt)

        try:
            count = int(section_count_var.get())
        except Exception:
            count = 1
        count = max(1, min(4, count))

        for i in range(4):
            if i < count:
                cur = section_page_vars[i].get().strip()
                if fill_only_blanks:
                    if cur == "" or not is_valid_page_count(cur, minimum):
                        section_page_vars[i].set(str(minimum))
                else:
                    section_page_vars[i].set(str(minimum))
            else:
                section_page_vars[i].set("")

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
            apply_min_pages_to_sections(fill_only_blanks=True)
            refresh_templates()
        finally:
            _busy["busy"] = False

    def refresh_templates(*_):
        press = press_var.get()
        fmt = format_var.get()

        try:
            count = int(section_count_var.get())
        except Exception:
            count = 1
        count = max(1, min(4, count))

        pages = []
        for i in range(count):
            try:
                pages.append(max(1, int(section_page_vars[i].get().strip())))
            except Exception:
                pages.append(min_pages_for_format(fmt))

        matches = list_matching_templates(press, fmt, section_count=count, section_pages=pages)

        templates_listbox.delete(0, "end")
        template_paths.clear()
        for disp, path in matches:
            templates_listbox.insert("end", disp)
            template_paths.append(path)
        templates_listbox.selection_clear(0, "end")

    def _on_format_changed(event=None):
        fmt = format_var.get()
        inc = min_pages_for_format(fmt)
        max_pages = inc * 10
        for sp in section_page_spinboxes:
            sp.configure(from_=inc, to=max_pages, increment=inc)
        apply_min_pages_to_sections(fill_only_blanks=False)
        refresh_templates()

    section_count_spinbox.configure(command=_on_section_count_changed)
    section_count_var.trace_add("write", lambda *_: _on_section_count_changed())

    format_combo.bind("<<ComboboxSelected>>", _on_format_changed)
    press_combo.bind("<<ComboboxSelected>>", lambda e: refresh_templates())
    for var in section_page_vars:
        var.trace_add("write", lambda *_: refresh_templates())

    _update_section_page_states(int(section_count_var.get()))
    _on_format_changed()
    refresh_templates()

    def on_new_or_open():
        press = press_var.get()
        fmt = format_var.get()

        base_cfg = CONFIG_MAP.get((press, fmt))
        if not base_cfg:
            messagebox.showwarning("Not Configured", f"{press} - {fmt} is not configured yet.")
            return

        try:
            count = int(section_count_var.get())
        except Exception:
            count = 1
        count = max(1, min(4, count))

        pages = []
        for i in range(count):
            try:
                pages.append(max(1, int(section_page_vars[i].get().strip())))
            except Exception:
                pages.append(min_pages_for_format(fmt))

        cfg = dict(base_cfg)
        cfg["section_count"] = count
        cfg["section_pages"] = pages
        cfg["template_mode"] = False

        sel = templates_listbox.curselection()
        load_path = template_paths[sel[0]] if sel else None

        win = tk.Toplevel(parent)
        build_press_layout(
            win,
            title=f"{press} - {fmt}",
            config=cfg,
            load_path=load_path,
            load_as_copy=True  # NEW LAYOUT from template => copy
        )

    templates_listbox.bind("<Double-Button-1>", lambda e: on_new_or_open())

    btn_row = ttk.Frame(frame)
    btn_row.grid(row=4, column=0, columnspan=8, pady=(12, 0), sticky="w")

    ttk.Button(btn_row, text="New / Open", command=on_new_or_open, width=14).pack(side="left", padx=(0, 8))
    ttk.Button(btn_row, text="Refresh Templates", command=refresh_templates, width=16).pack(side="left")

    return root


# ------------------ TEMPLATE EDITOR LAUNCHER ------------------
def build_template_editor_launcher(parent):
    root = tk.Toplevel(parent)
    root.title("Template Editor")
    root.geometry("680x360")
    root.minsize(640, 320)

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    frame.rowconfigure(2, weight=1)
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", pady=8)
    press_var = tk.StringVar(value="Press 1")
    press_combo = ttk.Combobox(frame, textvariable=press_var, values=["Press 1", "Press 2"], state="readonly", width=16)
    press_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))

    ttk.Label(frame, text="Format:", font=(None, 11, "bold")).grid(row=1, column=0, sticky="w", pady=8)
    format_var = tk.StringVar(value="Broadsheet")
    format_combo = ttk.Combobox(frame, textvariable=format_var, values=["Broadsheet", "Tab", "8 up"], state="readonly", width=16)
    format_combo.grid(row=1, column=1, sticky="w", padx=(8, 0))

    ttk.Label(frame, text="Templates:", font=(None, 11, "bold")).grid(row=2, column=0, sticky="nw", pady=(8, 0))

    list_frame = ttk.Frame(frame)
    list_frame.grid(row=2, column=1, sticky="nsew", pady=(8, 0))
    list_frame.rowconfigure(0, weight=1)
    list_frame.columnconfigure(0, weight=1)

    lb = tk.Listbox(list_frame, height=10, exportselection=False)
    lb.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(list_frame, orient="vertical", command=lb.yview)
    sb.grid(row=0, column=1, sticky="ns")
    lb.configure(yscrollcommand=sb.set)

    template_paths = []

    def refresh():
        lb.delete(0, "end")
        template_paths.clear()
        press = press_var.get()
        fmt = format_var.get()

        for disp, path in list_json_files(TEMPLATE_DIR):
            data = safe_read_json(path)
            if data and data.get("press") == press and data.get("format") == fmt:
                lb.insert("end", disp)
                template_paths.append(path)

    def open_selected():
        sel = lb.curselection()
        if not sel:
            messagebox.showinfo("Select a Template", "Select a template to open.")
            return
        open_json_in_layout(parent, template_paths[sel[0]], template_mode=True)

    def new_template():
        press = press_var.get()
        fmt = format_var.get()
        base_cfg = CONFIG_MAP.get((press, fmt))
        if not base_cfg:
            messagebox.showwarning("Not Configured", f"{press} - {fmt} not configured.")
            return
        cfg = dict(base_cfg)
        cfg["section_count"] = 1
        cfg["section_pages"] = [min_pages_for_format(fmt)]
        cfg["template_mode"] = True
        win = tk.Toplevel(parent)
        build_press_layout(win, title=f"{press} - {fmt}", config=cfg, load_path=None, load_as_copy=False)

    press_combo.bind("<<ComboboxSelected>>", lambda e: refresh())
    format_combo.bind("<<ComboboxSelected>>", lambda e: refresh())
    lb.bind("<Double-Button-1>", lambda e: open_selected())

    btns = ttk.Frame(frame)
    btns.grid(row=3, column=0, columnspan=2, pady=12, sticky="w")
    ttk.Button(btns, text="New Template", command=new_template, width=14).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Open Template", command=open_selected, width=14).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Refresh", command=refresh, width=10).pack(side="left")

    refresh()
    return root


# ------------------ MAIN LAUNCHER ------------------
def build_main_launcher():
    ensure_dir(LAYOUTS_DIR)
    ensure_dir(TEMPLATE_DIR)

    root = tk.Tk()
    root.title("Press Layouts")
    root.geometry("980x480")
    root.minsize(920, 420)

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(0, weight=1)

    ttk.Label(frame, text="Layouts:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")

    columns = ("issue", "product", "press", "format", "saved")
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
    tree.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    vsb.grid(row=1, column=1, sticky="ns", pady=(8, 0))
    tree.configure(yscrollcommand=vsb.set)

    tree.heading("issue", text="Issue Date")
    tree.heading("product", text="Product")
    tree.heading("press", text="Press")
    tree.heading("format", text="Format")
    tree.heading("saved", text="Last Saved")

    tree.column("issue", width=110, anchor="center")
    tree.column("product", width=300, anchor="w")
    tree.column("press", width=90, anchor="center")
    tree.column("format", width=120, anchor="center")
    tree.column("saved", width=170, anchor="center")

    row_by_iid = {}
    sort_state = {"col": None, "desc": False}

    def load_rows_into_tree(rows):
        tree.delete(*tree.get_children())
        row_by_iid.clear()
        for r in rows:
            iid = r["path"]
            tree.insert("", "end", iid=iid, values=(
                r["issue_disp"],
                r["product"],
                r["press"],
                r["format"],
                r["saved_disp"],
            ))
            row_by_iid[iid] = r

    def refresh():
        rows = build_layout_rows()
        load_rows_into_tree(rows)

    def sort_by(col):
        if sort_state["col"] == col:
            sort_state["desc"] = not sort_state["desc"]
        else:
            sort_state["col"] = col
            sort_state["desc"] = False

        rows = list(row_by_iid.values())

        def keyfunc(r):
            if col == "issue":
                return r["issue_dt"] or datetime.min
            if col == "saved":
                return r["saved_dt"] or datetime.min
            if col == "product":
                return (r["product"] or "").lower()
            if col == "press":
                return (r["press"] or "").lower()
            if col == "format":
                return (r["format"] or "").lower()
            return ""

        rows.sort(key=keyfunc, reverse=sort_state["desc"])
        load_rows_into_tree(rows)

    tree.heading("issue", command=lambda: sort_by("issue"))
    tree.heading("product", command=lambda: sort_by("product"))
    tree.heading("press", command=lambda: sort_by("press"))
    tree.heading("format", command=lambda: sort_by("format"))
    tree.heading("saved", command=lambda: sort_by("saved"))

    def selected_path():
        sel = tree.selection()
        return sel[0] if sel else None

    def open_selected():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Layout", "Select a layout to open.")
            return
        open_json_in_layout(root, path, template_mode=False)

    def new_layout():
        build_new_layout_launcher(root)

    def templates():
        build_template_editor_launcher(root)

    tree.bind("<Double-Button-1>", lambda e: open_selected())

    btns = ttk.Frame(frame)
    btns.grid(row=2, column=0, pady=12, sticky="w")
    ttk.Button(btns, text="New", command=new_layout, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Open", command=open_selected, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Templates", command=templates, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Refresh", command=refresh, width=12).pack(side="left")

    refresh()
    root.mainloop()


if __name__ == "__main__":
    build_main_launcher()
