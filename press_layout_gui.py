from logging import config
import os
import json
import glob
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# --------- SETTINGS ---------
LAYOUT_DIR = r"C:\Users\MBradbury\Documents\Press Layouts\jsons"

# --------- UTILS ---------
def build_imposition_text(ctx) -> str:
    """
    Imposition field = suggested filename minus the .json extension
    """
    name = build_filename_suggestion(ctx)  # returns something ending in .json
    return os.path.splitext(name)[0]

FORMAT_MIN_PAGES = {
    "Broadsheet": 2,
    "Tab": 4,
    "8 up": 8,
}

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
    - If fill_only_blanks=True: only fills blanks/invalids (preserves valid user input).
    - If fill_only_blanks=False: forces enabled sections to the minimum for the format.
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
            # leave disabled ones blank
            section_page_vars[i].set("")

def unit_row_has_numbers(unit_dict, row_index: int) -> bool:
    """True if the given grid row contains at least one integer page number."""
    entries_2d = unit_dict["entries"]
    if row_index < 0 or row_index >= len(entries_2d):
        return False
    for cell in entries_2d[row_index]:
        if safe_int(cell.get()) is not None:
            return True
    return False


def unit_dinky_suffix(unit_dict) -> str:
    """
    Return dinky suffix:
      - 'ds' if only TOP row has numbers
      - 'os' if only BOTTOM row has numbers
      - '' otherwise (both rows or neither)
    Assumes 2-row grids for your layouts, but safely handles other sizes.
    """
    top_has = unit_row_has_numbers(unit_dict, 0)
    bottom_has = unit_row_has_numbers(unit_dict, 1)

    if top_has and not bottom_has:
        return "ds"
    if bottom_has and not top_has:
        return "os"
    return ""

def parse_section_id(text: str):
    """
    Convert a unit's section-entry text into a section index 1..4.
    Accepts:
      - "1", "2", "3", "4"
      - "S1", "S2", ...
      - "A", "B", "C", "D"  (mapped to 1..4)
    Returns int 1..4 or None if not parseable.
    """
    if text is None:
        return None
    t = text.strip().upper()
    if not t:
        return None

    # "S1" style
    if t.startswith("S") and len(t) >= 2 and t[1:].isdigit():
        n = int(t[1:])
        return n if 1 <= n <= 4 else None

    # numeric
    if t.isdigit():
        n = int(t)
        return n if 1 <= n <= 4 else None

    # letter A-D
    if t in ("A", "B", "C", "D"):
        return ord(t) - ord("A") + 1

    return None


def abbrev_unit_label(label: str) -> str:
    """
    Make unit labels filename-friendly and compact.
    Examples:
      "G1-Lower" -> "G1L"
      "G1-Upper" -> "G1U"
      "B2-Lower" -> "B2L"
      "B2-Upper" -> "B2U"
      "E2" -> "E2"
    """
    if not label:
        return ""
    s = label.replace("-Lower", "L").replace("-Upper", "U")
    s = s.replace("-", "")  # remove remaining hyphens
    s = s.replace(" ", "")  # remove spaces just in case
    return s


def safe_int(value):
    try:
        return int(str(value).strip())
    except Exception:
        return None


def unit_min_page_number(unit_dict):
    """
    Return the smallest integer found in the unit's grid entries.
    If none found, return None.
    """
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
    """
    Build filename per template:
      P# S{pages}{units...} S{pages}{units...} ...

    Units for each section come from the unit's section_entry (1..4 / S1.. / A..D).
    Unit ordering within each section is by the lowest page number found in that unit's grid.
    """
    # Press number
    press_name = ctx.get("press_name", "")
    press_num = "1" if "1" in press_name else "2"
    prefix = f"P{press_num}"

    # Section count and pages (stop at section_count)
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

    # Group units by section from the "section entry above each unit"
    units_by_section = {i: [] for i in range(1, section_count + 1)}
    for u in ctx["units"]:
        sec_id = parse_section_id(u["section_entry"].get())
        if sec_id is None:
            continue
        if 1 <= sec_id <= section_count:
            units_by_section[sec_id].append(u)

    # Build segments: S{pages}{U1U2...}
    segments = []
    for sec_idx in range(1, section_count + 1):
        sec_pages = pages[sec_idx - 1]
        sec_units = units_by_section.get(sec_idx, [])

        # Sort by min page number in that unit (page 1 unit first).
        # Units without numbers go last.
        def sort_key(u):
            m = unit_min_page_number(u)
            return (m is None, m if m is not None else 10**9)

        sec_units_sorted = sorted(sec_units, key=sort_key)

        units_part = "".join(
            f"{abbrev_unit_label(u['label'])}{unit_dinky_suffix(u)}"
            for u in sec_units_sorted
        )

        segments.append(f"{sec_pages}{units_part}")

    # Join using spaces between section chunks
    name = prefix + " " + " ".join(segments)

    # Sanitize and add extension
    name = sanitize_filename(name).strip()
    if not name.lower().endswith(".json"):
        name += ".json"
    return name

def get_unit_order(units, press_name):
    """Return your preferred unit traversal order, filtered to units that exist in this layout."""
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
    """
    Arrow navigation:
      - Grid cells:
          Up/Down = same unit, same column, row-1/row+1
          Left/Right = same row, col-1/col+1; at edges jump to prev/next unit (same row)
      - Non-grid entries:
          Up/Left = previous in focus_list
          Down/Right = next in focus_list

    Left/Right only change focus when caret is at start/end of text (so you can still edit text).
    """

    focus_list = [w for w in focus_list if w is not None]
    if len(focus_list) < 2:
        return

    # next/prev maps using widget objects (reliable)
    n = len(focus_list)
    next_map = {focus_list[i]: focus_list[(i + 1) % n] for i in range(n)}
    prev_map = {focus_list[i]: focus_list[(i - 1) % n] for i in range(n)}

    # Unit order in your preferred traversal (F..A), filtered to existing units
    unit_order = get_unit_order(units, press_name)
    unit_map = {u["label"]: u for u in units}
    unit_index = {lab: i for i, lab in enumerate(unit_order)}

    # Grid lookup: cell_widget -> (unit_label, entries_2d, row, col)
    grid_lookup = {}
    for u in units:
        entries_2d = u["entries"]
        for r, row in enumerate(entries_2d):
            for c, cell in enumerate(row):
                grid_lookup[cell] = (u["label"], entries_2d, r, c)

    def _goto(w):
        w.focus_set()
        try:
            w.selection_range(0, "end")  # optional: fast overwrite
        except Exception:
            pass
        return "break"

    def on_left(event):
        w = event.widget

        # Allow normal cursor movement unless caret is at start
        try:
            if w.index("insert") > 0:
                return
        except Exception:
            return

        if w in grid_lookup:
            lab, entries_2d, r, c = grid_lookup[w]

            # move left within unit
            if c - 1 >= 0:
                return _goto(entries_2d[r][c - 1])

            # at left edge -> jump to previous unit (WRAP), same row, last column
            if lab in unit_index and unit_order:
                prev_lab = unit_order[(unit_index[lab] - 1) % len(unit_order)]  # <-- wrap
                prev_entries = unit_map[prev_lab]["entries"]
                last_col = len(prev_entries[r]) - 1
                return _goto(prev_entries[r][last_col])

            # fallback: workflow prev
            return _goto(prev_map[w])

        # Non-grid: workflow prev
        return _goto(prev_map[w])

    def on_right(event):
        w = event.widget

        # Allow normal cursor movement unless caret is at end
        try:
            if w.index("insert") < len(w.get()):
                return
        except Exception:
            return

        if w in grid_lookup:
            lab, entries_2d, r, c = grid_lookup[w]

            # move right within unit
            if c + 1 < len(entries_2d[r]):
                return _goto(entries_2d[r][c + 1])

            # at right edge -> jump to next unit (WRAP), same row, first column
            if lab in unit_index and unit_order:
                next_lab = unit_order[(unit_index[lab] + 1) % len(unit_order)]  # <-- wrap
                next_entries = unit_map[next_lab]["entries"]
                return _goto(next_entries[r][0])

            # fallback: workflow next
            return _goto(next_map[w])

        # Non-grid: workflow next
        return _goto(next_map[w])

    def on_up(event):
        w = event.widget

        if w in grid_lookup:
            lab, entries_2d, r, c = grid_lookup[w]
            rows = len(entries_2d)

            # Wrap: top row -> bottom row (same column)
            target_r = (r - 1) % rows

            # Move if column exists in target row
            if c < len(entries_2d[target_r]):
                return _goto(entries_2d[target_r][c])

            # Safety fallback (shouldn't happen in your 2-row consistent grids)
            return _goto(prev_map[w])

        # Non-grid: workflow previous
        return _goto(prev_map[w])

    def on_down(event):
        w = event.widget

        if w in grid_lookup:
            lab, entries_2d, r, c = grid_lookup[w]
            rows = len(entries_2d)

            # Wrap: bottom row -> top row (same column)
            target_r = (r + 1) % rows

            # Move if column exists in target row
            if c < len(entries_2d[target_r]):
                return _goto(entries_2d[target_r][c])

            # Safety fallback
            return _goto(next_map[w])

        # Non-grid: workflow next
        return _goto(next_map[w])

    # Bind to all widgets in the focus chain
    for w in focus_list:
        try:
            w.configure(takefocus=True)
        except Exception:
            pass

        w.bind("<KeyPress-Left>", on_left)
        w.bind("<KeyPress-Right>", on_right)
        w.bind("<KeyPress-Up>", on_up)
        w.bind("<KeyPress-Down>", on_down)

        # keypad arrow variants
        w.bind("<KP_Left>", on_left)
        w.bind("<KP_Right>", on_right)
        w.bind("<KP_Up>", on_up)
        w.bind("<KP_Down>", on_down)

def build_focus_order(issue_entry, product_entry, units, grid_rows, grid_cols, press_name, extra_widgets=None):
    """
    Return an ordered list of widgets matching the requested traversal.
    - units is a list of dicts: {label, section_entry, entries}
    - entries is 2D list [grid_rows][grid_cols] of ttk.Entry
    - extra_widgets is an optional list of widgets to include after issue/product.
    """
    unit_map = {u["label"]: u for u in units}

    # Determine press number suffix from press_name
    # Expect "Press 1" / "Press 2"
    press_num = "1" if "1" in press_name else "2"

    focus_widgets = [issue_entry, product_entry]
    if extra_widgets:
        focus_widgets.extend(extra_widgets)

    # Preferred unit order specified by you (Press 1 baseline),
    # with F/G/B/A using the current press number.
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

    # Filter to only labels that exist for this press layout window
    unit_order = [lab for lab in preferred_labels if lab in unit_map]

    focus_widgets = [issue_entry, product_entry]

    # --- Section entry phase ---
    for lab in unit_order:
        focus_widgets.append(unit_map[lab]["section_entry"])

    # --- Grid phase ---
    # Top row (row 0) across units in forward order
    if grid_rows >= 1:
        r = 0
        for lab in unit_order:
            row_entries = unit_map[lab]["entries"][r]
            for c in range(min(grid_cols, len(row_entries))):
                focus_widgets.append(row_entries[c])

    # Remaining rows (1..end) across units in reverse order
    # AND within each unit, traverse columns right-to-left so:
    # top-right A -> bottom-right A -> bottom-left A -> bottom-right B -> ...
    for r in range(1, grid_rows):
        for lab in reversed(unit_order):
            row_entries = unit_map[lab]["entries"][r]
            last_col = min(grid_cols, len(row_entries)) - 1
            for c in range(last_col, -1, -1):
                focus_widgets.append(row_entries[c])

    return focus_widgets

def set_custom_tab_order(widgets):
    """
    Force a specific tab order (Tab and Shift+Tab) for a list of widgets.
    Wraps around at ends.
    """
    widgets = [w for w in widgets if w is not None]

    # Remove duplicates while preserving order
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

        # Ensure widget can accept focus
        try:
            w.configure(takefocus=True)
        except Exception:
            pass

        # Bind Tab / Shift-Tab
        w.bind("<Tab>", lambda e, _n=nxt: _goto(_n))
        w.bind("<Shift-Tab>", lambda e, _p=prv: _goto(_p))

        # Some Tk builds use ISO_Left_Tab for Shift-Tab (more common on Linux, sometimes on ttk)
        w.bind("<ISO_Left_Tab>", lambda e, _p=prv: _goto(_p))
        
def _contrast_text_color(hex_color: str) -> str:
    """Return black/white text for good contrast on a hex background."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "black" if luminance > 150 else "white"


def ensure_layout_dir():
    os.makedirs(LAYOUT_DIR, exist_ok=True)


def safe_read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def safe_write_json(path, data):
    ensure_layout_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, "_")
    return name.strip()


def apply_window_sizing(win, config):
    """
    Size the window based on config:
      - autosize=True: shrink-wrap to contents (tab/broadsheet)
      - full_width=True: set to full screen width (8 up)
    """
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
        return


# --------- UI BUILDERS ---------
def create_press_unit(
    parent,
    unit_label,
    use_cmyk=True,
    grid_rows=2,
    grid_cols=2,
    swatch_cols=2,          # always keep 2 swatches per color row
    cell_pad=0,
    midline_thickness=4,
    midline_color="#444444",
    unit_padding=(6, 6, 6, 6),
    cell_font=None,
    cell_width=None,
    swatch_size=(4, 1),     # (width, height) in text units for tk.Label swatches
):
    unit_frame = ttk.Frame(parent, style="Unit.TFrame", padding=unit_padding)

    section_entry = ttk.Entry(unit_frame, width=8, justify="center", font=(None, 10))
    section_entry.pack(pady=(0, 6))

    box_frame = ttk.Frame(unit_frame, style="Box.TFrame")
    box_frame.pack(fill="both", expand=True)

    # --- Default sizing rules (overridable per config) ---
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

        if cell_font is None:
            cell_font = default_font
        if cell_width is None:
            cell_width = default_width

    # --- Thick center divider logic for the grid ---
    use_v_sep = (grid_cols % 2 == 0 and grid_cols > 1)
    use_h_sep = (grid_rows % 2 == 0 and grid_rows > 1)

    mid_col = grid_cols // 2
    mid_row = grid_rows // 2

    total_grid_cols = grid_cols + (1 if use_v_sep else 0)
    total_grid_rows = grid_rows + (1 if use_h_sep else 0)

    def map_col(c):
        if use_v_sep and c >= mid_col:
            return c + 1
        return c

    def map_row(r):
        if use_h_sep and r >= mid_row:
            return r + 1
        return r

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

    grid_entries = []
    for r in range(grid_rows):
        row_entries = []
        for c in range(grid_cols):
            cell_entry = ttk.Entry(
                box_frame,
                justify="center",
                font=cell_font,
                width=cell_width,
            )
            cell_entry.grid(
                row=map_row(r),
                column=map_col(c),
                sticky="nsew",
                padx=cell_pad,
                pady=cell_pad
            )
            row_entries.append(cell_entry)
        grid_entries.append(row_entries)

    # Draw center dividers in the grid
    if use_v_sep:
        if use_h_sep:
            tk.Frame(box_frame, bg=midline_color).grid(
                row=0, column=mid_col, rowspan=mid_row, sticky="nsew"
            )
            tk.Frame(box_frame, bg=midline_color).grid(
                row=mid_row + 1, column=mid_col,
                rowspan=total_grid_rows - (mid_row + 1),
                sticky="nsew"
            )
        else:
            tk.Frame(box_frame, bg=midline_color).grid(
                row=0, column=mid_col, rowspan=total_grid_rows, sticky="nsew"
            )

    if use_h_sep:
        if use_v_sep:
            tk.Frame(box_frame, bg=midline_color).grid(
                row=mid_row, column=0, columnspan=mid_col, sticky="nsew"
            )
            tk.Frame(box_frame, bg=midline_color).grid(
                row=mid_row, column=mid_col + 1,
                columnspan=total_grid_cols - (mid_col + 1),
                sticky="nsew"
            )
            tk.Frame(box_frame, bg=midline_color).grid(
                row=mid_row, column=mid_col, sticky="nsew"
            )
        else:
            tk.Frame(box_frame, bg=midline_color).grid(
                row=mid_row, column=0, columnspan=total_grid_cols, sticky="nsew"
            )

    ttk.Label(unit_frame, text=unit_label, font=(None, 10, "bold")).pack(pady=(6, 0))

    # ---- Color swatches (centered under grid) ----
    color_frame = ttk.Frame(unit_frame)
    color_frame.pack(pady=(6, 0), fill="x")

    if use_cmyk:
        colors = [
            ("K", "#7f7f7f"),
            ("Y", "#fff176"),
            ("M", "#f48fb1"),
            ("C", "#90caf9"),
        ]
    else:
        colors = [("K", "#7f7f7f")]

    sw_w, sw_h = swatch_size
    style = ttk.Style(unit_frame)
    unit_bg = style.lookup("Unit.TFrame", "background") or "#f0f0f0"

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
                text=key,               # letter inside each swatch
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
                tk.Frame(
                    swatch_container,
                    bg=midline_color,
                    width=midline_thickness,
                    height=18
                ).pack(side="left", padx=1)

    return unit_frame, section_entry, grid_entries


def make_press_area(parent, enable_hscroll=False, height_hint=320):
    """
    Creates and returns a frame to place press units into.
    If enable_hscroll is True, returns an inner frame inside a canvas with a horizontal scrollbar.
    """
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


# --------- SAVE / LOAD LOGIC ---------
def collect_layout_data(ctx):
    """Collect all entered data from the current layout window into a JSON-serializable dict."""
    now = datetime.now().isoformat(timespec="seconds")
    data = {
        "version": 1,
        "name": ctx.get("layout_name") or "",
        "press": ctx["press_name"],
        "format": ctx["format_name"],
        "saved_at": now,
        "issue_date": ctx["issue_entry"].get().strip(),
        "product": ctx["product_entry"].get().strip(),
        "section_count": 1,
        "section_pages": [1],
        "units": []
    }

    # Section metadata from layout UI
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
                pages.append(1)
        data["section_count"] = section_count
        data["section_pages"] = pages

    for u in ctx["units"]:
        section = u["section_entry"].get().strip()
        grid = []
        for row in u["entries"]:
            grid.append([cell.get().strip() for cell in row])
        data["units"].append({
            "label": u["label"],
            "section": section,
            "grid": grid
        })

    return data


def populate_layout_from_data(ctx, data):
    """Populate UI entries from loaded data."""
    ctx["issue_entry"].delete(0, "end")
    ctx["issue_entry"].insert(0, data.get("issue_date", ""))

    ctx["product_entry"].delete(0, "end")
    ctx["product_entry"].insert(0, data.get("product", ""))

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
                ctx["section_page_vars"][i].set("1")
            else:
                ctx["section_page_vars"][i].set("")

        if ctx.get("_update_section_page_states"):
            ctx["_update_section_page_states"](section_count)

    # Map units by label for quick access
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


def do_save(win, ctx):
    """Save to current file if known, otherwise Save As."""
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
    """Prompt for file path and save."""
    ensure_layout_dir()

    # Suggest a filename
    suggested = build_filename_suggestion(ctx)

    path = filedialog.asksaveasfilename(
        parent=win,
        initialdir=LAYOUT_DIR,
        initialfile=suggested,
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")]
    )
    if not path:
        return False

    try:
        data = collect_layout_data(ctx)
        # Set name if empty
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


# --------- LAYOUT WINDOW ---------
def build_press_layout(win, title="Press Layout", config=None, load_path=None):
    config = config or {}

    # Style setup
    style = ttk.Style(win)
    style.configure("Unit.TFrame", background="#f0f0f0", relief="solid", borderwidth=1)
    style.configure("Box.TFrame", background="#ffffff", relief="solid", borderwidth=1)

    title_base = title
    win.title(title_base)

    # ---------------- HEADER ----------------
    header_frame = ttk.Frame(win, padding=(16, 12, 16, 8))
    header_frame.pack(fill="x")

    # Row 0: Issue Date / Product / Save buttons
    ttk.Label(header_frame, text="Issue Date:", font=(None, 12, "bold")).grid(row=0, column=0, sticky="w")
    issue_entry = ttk.Entry(header_frame, width=16, font=(None, 12))
    issue_entry.grid(row=0, column=1, sticky="w", padx=(8, 32))

    product_entry = ttk.Entry(header_frame, font=(None, 14), width=35, justify="center")
    product_entry.grid(row=0, column=3, columnspan=2, sticky="w", padx=(8, 12))

    # --- Imposition (moved to the right of Product, before Save buttons) ---
    imposition_var = tk.StringVar(value="")

    imposition_frame = ttk.Frame(header_frame)
    imposition_frame.grid(row=0, column=5, sticky="ew", padx=(0, 12))

    ttk.Label(imposition_frame, text="Imposition:", font=(None, 11, "bold")).pack(side="left", padx=(0, 6))

    imposition_entry = ttk.Entry(
        imposition_frame,
        textvariable=imposition_var,
        font=(None, 11),
        width=28,             # adjust to taste
        justify="center",
        state="readonly",
        takefocus=False
    )
    imposition_entry.pack(side="left", fill="x", expand=True)

    # Save buttons (right side)
    btn_frame = ttk.Frame(header_frame)
    btn_frame.grid(row=0, column=6, sticky="e")

    header_frame.columnconfigure(2, weight=1)
    header_frame.columnconfigure(3, weight=1)
    header_frame.columnconfigure(4, weight=1)
    header_frame.columnconfigure(5, weight=1)
    header_frame.columnconfigure(6, weight=0)

    # ---------------- SECTION METADATA ----------------
    # Row 1: Sections + Section pages
    section_count_var = tk.StringVar(value=str(config.get("section_count", 1)))
    section_page_vars = []
    section_page_entries = []

    ttk.Label(header_frame, text="Sections:", font=(None, 12, "bold")).grid(row=1, column=0, sticky="w", pady=6)

    sections_spinbox = ttk.Spinbox(
        header_frame,
        from_=1,
        to=4,
        textvariable=section_count_var,
        width=3,
        justify="center"
    )
    sections_spinbox.grid(row=1, column=1, sticky="w", padx=(8, 32))

    pages_frame = ttk.Frame(header_frame)
    pages_frame.grid(row=1, column=3, columnspan=2, sticky="w", padx=(8, 24))

    ttk.Label(pages_frame, text="Section pages:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")

    # Calculate increment based on format
    format_name = config.get("format_name", "")
    page_increment = min_pages_for_format(format_name)
    max_pages = page_increment * 10  # Allow multiples up to 10x the increment

    initial_pages = config.get("section_pages", [1, 1, 1, 1])
    for idx in range(4):
        page_value = str(initial_pages[idx] if idx < len(initial_pages) else page_increment)
        var = tk.StringVar(value=page_value)
        section_page_vars.append(var)

        ttk.Label(pages_frame, text=f"S{idx+1}", font=(None, 10)).grid(
            row=0, column=1 + idx * 2, sticky="e", padx=(10, 2)
        )
        spinbox = ttk.Spinbox(
            pages_frame,
            from_=page_increment,
            to=max_pages,
            increment=page_increment,
            textvariable=var,
            width=4,
            justify="center"
        )
        spinbox.grid(row=0, column=2 + idx * 2, sticky="w")
        section_page_entries.append(spinbox)

    def _update_section_page_states(count):
        """Enable/disable section page entries; clear disabled ones."""
        for idx, entry in enumerate(section_page_entries):
            if idx < count:
                entry.state(["!disabled"])
            else:
                entry.state(["disabled"])
                section_page_vars[idx].set("")

    def _on_section_count_changed(event=None):
        """When sections change, enable/disable fields and set new ones to min valid for the format."""
        try:
            count = int(section_count_var.get())
        except Exception:
            count = 1
        count = max(1, min(4, count))
        section_count_var.set(str(count))

        _update_section_page_states(count)

        # Apply format minimums; fill blanks/invalids only
        apply_min_pages_to_section_vars(
            format_name=config.get("format_name", ""),
            section_count_var=section_count_var,
            section_page_vars=section_page_vars,
            fill_only_blanks=True
        )

        update_imposition()

    # Apply enable/disable and enforce minimums on initial open
    try:
        _update_section_page_states(int(section_count_var.get()))
    except Exception:
        _update_section_page_states(1)

    apply_min_pages_to_section_vars(
        format_name=config.get("format_name", ""),
        section_count_var=section_count_var,
        section_page_vars=section_page_vars,
        fill_only_blanks=True
    )

    # ---------------- PRESS AREA ----------------
    press_area_frame = ttk.Frame(win, padding=(16, 0, 16, 12))
    press_area_frame.pack(fill="both", expand=True)

    enable_hscroll = config.get("enable_hscroll", False)
    _, press_frame, _canvas = make_press_area(
        press_area_frame,
        enable_hscroll=enable_hscroll,
        height_hint=config.get("scroll_height_hint", 340)
    )

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

    # Left bank units
    for idx, label in enumerate(left_labels):
        use_cmyk = label not in only_k_labels
        unit_frame, section_entry, grid_entries = create_press_unit(
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
        units.append({"label": label, "section_entry": section_entry, "entries": grid_entries})

    # Folder block
    folder_frame = ttk.Frame(press_frame, padding=folder_padding)
    folder_frame.grid(row=0, column=len(left_labels), padx=folder_padx, sticky="n")

    arrow_canvas = tk.Canvas(
        folder_frame, width=140, height=170,
        highlightthickness=0, background=win.cget("bg")
    )
    arrow_canvas.pack(pady=(0, 8))
    arrow_canvas.create_polygon(55, 14, 85, 14, 70, 44, fill="#666666", outline="#666666")
    arrow_canvas.create_polygon(55, 64, 85, 64, 70, 94, fill="#666666", outline="#666666")
    arrow_canvas.create_polygon(55, 114, 85, 114, 70, 144, fill="#666666", outline="#666666")
    arrow_canvas.create_polygon(15, 64, 45, 64, 30, 94, fill="#666666", outline="#666666")

    ttk.Label(folder_frame, text=folder_label, font=(None, 12, "bold")).pack()

    # Right bank units
    for idx, label in enumerate(right_labels):
        use_cmyk = label not in only_k_labels
        unit_frame, section_entry, grid_entries = create_press_unit(
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
        units.append({"label": label, "section_entry": section_entry, "entries": grid_entries})

    # ---------------- CONTEXT ----------------
    ctx = {
        "title_base": title_base,
        "press_name": config.get("press_name", ""),
        "format_name": config.get("format_name", ""),

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
    }

    # ---------------- SAVE BUTTONS ----------------
    def _save():
        do_save(win, ctx)

    def _save_as():
        do_save_as(win, ctx)

    ttk.Button(btn_frame, text="Save", command=_save, width=10, takefocus=False).pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="Save As", command=_save_as, width=10, takefocus=False).pack(side="left")

    # ---------------- LIVE IMPOSITION UPDATER ----------------
    ctx["_imposition_updating"] = False

    def update_imposition(*_):
        if ctx["_imposition_updating"]:
            return
        ctx["_imposition_updating"] = True
        try:
            # build_imposition_text(ctx) should return filename suggestion minus ".json"
            imposition_var.set(build_imposition_text(ctx))
        finally:
            ctx["_imposition_updating"] = False

    # Bind updates: section vars
    sections_spinbox.configure(command=_on_section_count_changed)
    section_count_var.trace_add("write", lambda *_: _on_section_count_changed())
    section_count_var.trace_add("write", lambda *_: update_imposition())
    for var in section_page_vars:
        var.trace_add("write", lambda *_: update_imposition())

    # Bind updates: issue/product
    issue_entry.bind("<KeyRelease>", update_imposition)
    issue_entry.bind("<FocusOut>", update_imposition)
    product_entry.bind("<KeyRelease>", update_imposition)
    product_entry.bind("<FocusOut>", update_imposition)

    # Bind updates: unit section entries + grid cells
    for u in units:
        u["section_entry"].bind("<KeyRelease>", update_imposition)
        u["section_entry"].bind("<FocusOut>", update_imposition)
        for row in u["entries"]:
            for cell in row:
                cell.bind("<KeyRelease>", update_imposition)
                cell.bind("<FocusOut>", update_imposition)

    # ---------------- LOAD (if provided) ----------------
    if load_path:
        data = safe_read_json(load_path)
        if data:
            ctx["file_path"] = load_path
            ctx["layout_name"] = data.get("name") or os.path.splitext(os.path.basename(load_path))[0]
            win.title(f"{title_base}  —  {os.path.basename(load_path)}")
            populate_layout_from_data(ctx, data)

            # After load, enforce format minimums (fill blanks/invalids only)
            apply_min_pages_to_section_vars(
                format_name=config.get("format_name", ""),
                section_count_var=section_count_var,
                section_page_vars=section_page_vars,
                fill_only_blanks=True
            )

    # Compute imposition once now that UI is populated (and possibly loaded)
    update_imposition()

    # ---------------- CUSTOM TAB ORDER + ARROWS ----------------
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

    # Initial focus
    win.after(50, issue_entry.focus_set)

    # Window sizing rules
    apply_window_sizing(win, config)

    return units

# ---------------- CONFIGS ----------------

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

# PRESS 1
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

# PRESS 2
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


# --------- LAUNCHER ---------
def list_matching_layouts(press_name, format_name, section_count=None, section_pages=None):
    """
    Return list of (display_name, path) for json files that match press+format and optional metadata.
    Matching is based on reading JSON metadata; fallback by filename is only used when no section metadata selection is provided.
    """
    ensure_layout_dir()
    paths = sorted(glob.glob(os.path.join(LAYOUT_DIR, "*.json")))

    results = []
    for p in paths:
        data = safe_read_json(p)
        stem = os.path.splitext(os.path.basename(p))[0]

        if data and isinstance(data, dict):
            p_name = data.get("press")
            f_name = data.get("format")
            if p_name == press_name and f_name == format_name:
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
        elif section_count is None:
            # Fallback: filename contains both strings when no section metadata selection is present
            if press_name.lower().replace(" ", "") in stem.lower().replace(" ", "") and \
               format_name.lower().replace(" ", "") in stem.lower().replace(" ", ""):
                results.append((stem, p))

    return results


def build_interface():
    root = tk.Tk()
    root.title("Press Layout Launcher")
    root.geometry("700x380")
    root.minsize(680, 360)

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    # Row 0: Press
    ttk.Label(frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", pady=8, padx=(0, 8))
    press_var = tk.StringVar(value="Press 1")
    press_combo = ttk.Combobox(frame, textvariable=press_var, values=["Press 1", "Press 2"], state="readonly", width=16)
    press_combo.grid(row=0, column=1, sticky="w", padx=(0, 24))

    # Row 1: Format
    ttk.Label(frame, text="Format:", font=(None, 11, "bold")).grid(row=1, column=0, sticky="w", pady=8, padx=(0, 8))
    format_var = tk.StringVar(value="Broadsheet")
    format_combo = ttk.Combobox(frame, textvariable=format_var, values=["Broadsheet", "Tab", "8 up"], state="readonly", width=16)
    format_combo.grid(row=1, column=1, sticky="w", padx=(0, 24))

    FORMAT_MIN_PAGES = {
        "Broadsheet": 2,
        "Tab": 4,
        "8 up": 8,
    }

    def min_pages_for_format(fmt: str) -> int:
        return FORMAT_MIN_PAGES.get(fmt, 1)

    def is_valid_page_count(value: str, multiple: int) -> bool:
        try:
            n = int(value.strip())
            return n >= multiple and (n % multiple == 0)
        except Exception:
            return False

    def apply_min_pages_to_sections(fill_only_blanks=True):
        """
        Set enabled section page fields to a valid value for the selected format.
        If fill_only_blanks=True, only fills blanks/invalids (won't overwrite user-entered valid values).
        """
        fmt = format_var.get()
        minimum = min_pages_for_format(fmt)

        try:
            count = int(section_count_var.get())
        except Exception:
            count = 1
        count = max(1, min(4, count))

        for i in range(4):
            if i < count:
                current = section_page_vars[i].get().strip()
                if fill_only_blanks:
                    # Only fill if blank or invalid for this format
                    if (current == "") or (not is_valid_page_count(current, minimum)):
                        section_page_vars[i].set(str(minimum))
                else:
                    section_page_vars[i].set(str(minimum))
            else:
                # Disabled sections remain blank
                section_page_vars[i].set("")

    # Row 2: Sections + Pages (same row)
    ttk.Label(frame, text="Sections:", font=(None, 11, "bold")).grid(row=2, column=0, sticky="w", pady=8, padx=(0, 8))
    section_count_var = tk.StringVar(value="1")
    section_count_spinbox = ttk.Spinbox(
        frame,
        from_=1,
        to=4,
        textvariable=section_count_var,
        width=3,
        justify="center"
    )
    section_count_spinbox.grid(row=2, column=1, sticky="w", padx=(0, 24))

    ttk.Label(frame, text="Pages:", font=(None, 11, "bold")).grid(row=2, column=2, sticky="w", padx=(0, 8))

    section_page_vars = []
    section_page_spinboxes = []
    for idx in range(4):
        var = tk.StringVar(value="2")
        section_page_vars.append(var)
        ttk.Label(frame, text=f"S{idx+1}:", font=(None, 10)).grid(row=2, column=3 + idx * 2, sticky="e", padx=(12, 4))
        spinbox = ttk.Spinbox(
            frame,
            from_=2,
            to=20,
            increment=2,
            textvariable=var,
            width=3,
            justify="center"
        )
        spinbox.grid(row=2, column=4 + idx * 2, sticky="w", padx=(0, 0))
        section_page_spinboxes.append(spinbox)

    # Row 3: Templates list (scrollable)
    ttk.Label(frame, text="Templates:", font=(None, 11, "bold")).grid(row=3, column=0, sticky="nw", pady=(8, 0), padx=(0, 8))

    templates_frame = ttk.Frame(frame)
    templates_frame.grid(row=3, column=1, columnspan=7, sticky="nsew", padx=(0, 0), pady=(8, 0))

    templates_listbox = tk.Listbox(
        templates_frame,
        height=6,
        width=70,
        exportselection=False
    )
    templates_listbox.grid(row=0, column=0, sticky="nsew")

    templates_scroll = ttk.Scrollbar(templates_frame, orient="vertical", command=templates_listbox.yview)
    templates_scroll.grid(row=0, column=1, sticky="ns")
    templates_listbox.configure(yscrollcommand=templates_scroll.set)

    templates_frame.rowconfigure(0, weight=1)
    templates_frame.columnconfigure(0, weight=1)

    frame.rowconfigure(3, weight=1)
    frame.columnconfigure(1, weight=1)

    # Store mapping from list index -> path
    template_paths = []

    def _update_section_page_states(count):
        for idx, spinbox in enumerate(section_page_spinboxes):
            if idx < count:
                spinbox.state(["!disabled"])
            else:
                spinbox.state(["disabled"])
                section_page_vars[idx].set("")

    def _on_section_count_changed(event=None):
        try:
            count = int(section_count_var.get())
        except Exception:
            count = 1
        count = max(1, min(4, count))
        section_count_var.set(str(count))

        _update_section_page_states(count)

        # Fill any newly-enabled (blank) sections with the minimum for the format
        apply_min_pages_to_sections(fill_only_blanks=True)

        refresh_layouts()

    section_count_spinbox.configure(command=_on_section_count_changed)
    section_count_var.trace_add("write", lambda *_: _on_section_count_changed())

    def refresh_layouts(*_):
        press = press_var.get()
        fmt = format_var.get()

        try:
            section_count = int(section_count_var.get())
        except Exception:
            section_count = 1
        section_count = max(1, min(4, section_count))

        section_pages = []
        for i in range(section_count):
            try:
                section_pages.append(max(1, int(section_page_vars[i].get().strip())))
            except Exception:
                section_pages.append(1)

        matches = list_matching_layouts(
            press, fmt,
            section_count=section_count,
            section_pages=section_pages
        )

        # Clear current list
        templates_listbox.delete(0, "end")
        template_paths.clear()

        # Populate listbox
        for disp, path in matches:
            templates_listbox.insert("end", disp)
            template_paths.append(path)

        # Nothing selected by default
        templates_listbox.selection_clear(0, "end")

    def _on_format_changed(event=None):
        fmt = format_var.get()
        increment = min_pages_for_format(fmt)
        max_pages = increment * 10

        # Update spinbox configurations for new format
        for spinbox in section_page_spinboxes:
            spinbox.configure(from_=increment, to=max_pages, increment=increment)

        apply_min_pages_to_sections()
        refresh_layouts()

    format_combo.bind("<<ComboboxSelected>>", _on_format_changed)

    for var in section_page_vars:
        var.trace_add("write", lambda *_: refresh_layouts())

    # Initial populate
    _update_section_page_states(int(section_count_var.get()))
    apply_min_pages_to_sections()
    refresh_layouts()

    def on_new_or_open():
        press = press_var.get()
        fmt = format_var.get()

        base_cfg = CONFIG_MAP.get((press, fmt))
        if not base_cfg:
            messagebox.showwarning("Not Configured", f"{press} - {fmt} is not configured yet.")
            return

        try:
            section_count = int(section_count_var.get())
        except Exception:
            section_count = 1
        section_count = max(1, min(4, section_count))
        section_pages = []
        for i in range(section_count):
            try:
                section_pages.append(max(1, int(section_page_vars[i].get().strip())))
            except Exception:
                section_pages.append(1)

        cfg = dict(base_cfg)
        cfg["section_count"] = section_count
        cfg["section_pages"] = section_pages

        sel = templates_listbox.curselection()
        load_path = template_paths[sel[0]] if sel else None

        title = f"{press} - {fmt}"
        win = tk.Toplevel(root)
        build_press_layout(win, title=title, config=cfg, load_path=load_path)

    def on_template_double_click(event=None):
        if templates_listbox.curselection():
            on_new_or_open()

    templates_listbox.bind("<Double-Button-1>", on_template_double_click)

    # Row 4: Buttons
    btn_row = ttk.Frame(frame)
    btn_row.grid(row=4, column=0, columnspan=8, pady=(12, 0), sticky="w")

    ttk.Button(btn_row, text="New / Open", command=on_new_or_open, width=14).pack(side="left", padx=(0, 8))
    ttk.Button(btn_row, text="Refresh Templates", command=refresh_layouts, width=16).pack(side="left")

    root.mainloop()


if __name__ == "__main__":
    build_interface()