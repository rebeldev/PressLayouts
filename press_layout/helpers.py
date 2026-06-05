import os
import json
import glob
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk

from .config import FORMAT_MIN_PAGES, LAYOUTS_DIR, TEMPLATE_DIR

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
        sec_text = (u["section_entry"].get() or "").strip().upper()
        sec_id = None
        # Try mapping via explicit section name variables (if present in ctx)
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

        # fallback to numeric/S#/A-D parsing
        if sec_id is None:
            sec_id = parse_section_id(sec_text)

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


def preview_image_path_for_json(json_path: str) -> str:
    base, _ = os.path.splitext(str(json_path or ""))
    return base + ".preview.png"


def remove_preview_image_for_json(json_path: str):
    path = preview_image_path_for_json(json_path)
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
    if not path or not os.path.exists(path):
        return None
    try:
        with Image.open(path) as img:
            return img.copy()
    except Exception:
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
    image = _capture_window_image_for_preview(win)
    image = _resize_preview_image_helper(image, scale=scale)
    out_path = preview_image_path_for_json(json_path)
    ensure_dir(os.path.dirname(out_path))
    image.save(out_path, format="PNG")
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

