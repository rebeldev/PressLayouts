import os
import json
import glob
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# --------- SETTINGS ---------
LAYOUT_DIR = r"C:\Users\MBradbury\Documents\Press Layouts\jsons"

# --------- UTILS ---------
def build_focus_order(issue_entry, product_entry, units, grid_rows, grid_cols, press_name):
    """
    Return an ordered list of widgets matching the requested traversal.
    - units is a list of dicts: {label, section_entry, entries}
    - entries is 2D list [grid_rows][grid_cols] of ttk.Entry
    """
    unit_map = {u["label"]: u for u in units}

    # Determine press number suffix from press_name
    # Expect "Press 1" / "Press 2"
    press_num = "1" if "1" in press_name else "2"

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
        "units": []
    }

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
    issue = ctx["issue_entry"].get().strip() or "layout"
    suggested = sanitize_filename(f"{ctx['press_name']} - {ctx['format_name']} - {issue}.json")

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

    # Header with issue/product + save buttons
    header_frame = ttk.Frame(win, padding=(16, 12, 16, 8))
    header_frame.pack(fill="x")

    ttk.Label(header_frame, text="Issue Date:", font=(None, 12, "bold")).grid(row=0, column=0, sticky="w")
    issue_entry = ttk.Entry(header_frame, width=16, font=(None, 12))
    issue_entry.grid(row=0, column=1, sticky="w", padx=(8, 32))

    product_entry = ttk.Entry(header_frame, font=(None, 14), width=35, justify="center")
    product_entry.grid(row=0, column=3, columnspan=2, sticky="w", padx=(8, 24))

    # Save buttons (right side)
    btn_frame = ttk.Frame(header_frame)
    btn_frame.grid(row=0, column=6, sticky="e")

    header_frame.columnconfigure(2, weight=1)
    header_frame.columnconfigure(3, weight=1)
    header_frame.columnconfigure(4, weight=1)
    header_frame.columnconfigure(5, weight=1)
    header_frame.columnconfigure(6, weight=0)

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

    # Left bank
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

    # Right bank
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

    # --- Layout context for saving/loading ---
    ctx = {
        "title_base": title_base,
        "press_name": config.get("press_name", ""),
        "format_name": config.get("format_name", ""),
        "issue_entry": issue_entry,
        "product_entry": product_entry,
        "units": units,
        "file_path": None,
        "layout_name": None,
    }

    def _save():
        do_save(win, ctx)

    def _save_as():
        do_save_as(win, ctx)

    ttk.Button(btn_frame, text="Save", command=_save, width=10, takefocus=False).pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="Save As", command=_save_as, width=10, takefocus=False).pack(side="left")

    # If load_path provided, load it now
    if load_path:
        data = safe_read_json(load_path)
        if data:
            ctx["file_path"] = load_path
            ctx["layout_name"] = data.get("name") or os.path.splitext(os.path.basename(load_path))[0]
            win.title(f"{title_base}  —  {os.path.basename(load_path)}")
            populate_layout_from_data(ctx, data)

    # ----- CUSTOM TAB ORDER -----
    focus_list = build_focus_order(
        issue_entry=issue_entry,
        product_entry=product_entry,
        units=units,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        press_name=config.get("press_name", "")
    )
    set_custom_tab_order(focus_list)

    print("Tab order widgets:", len(focus_list))
    print("First 10:", [str(w) for w in focus_list[:10]])

    # Issue date should have focus when window opens
    win.after(50, issue_entry.focus_set)

    # Window sizing rules (autosize for tab/broadsheet, full width for 8-up)
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
def list_matching_layouts(press_name, format_name):
    """
    Return list of (display_name, path) for json files that match press+format.
    Matching is based on reading JSON metadata; if missing, falls back to filename contains.
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
                disp = data.get("name") or stem
                results.append((disp, p))
        else:
            # Fallback: filename contains both strings
            if press_name.lower().replace(" ", "") in stem.lower().replace(" ", "") and \
               format_name.lower().replace(" ", "") in stem.lower().replace(" ", ""):
                results.append((stem, p))

    return results


def build_interface():
    root = tk.Tk()
    root.title("Press Layout Launcher")
    root.geometry("520x210")
    root.minsize(500, 200)

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    # Press
    ttk.Label(frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", pady=6)
    press_var = tk.StringVar(value="Press 1")
    press_combo = ttk.Combobox(frame, textvariable=press_var, values=["Press 1", "Press 2"], state="readonly", width=18)
    press_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))

    # Format
    ttk.Label(frame, text="Format:", font=(None, 11, "bold")).grid(row=1, column=0, sticky="w", pady=6)
    format_var = tk.StringVar(value="Broadsheet")
    format_combo = ttk.Combobox(frame, textvariable=format_var, values=["Broadsheet", "Tab", "8 up"], state="readonly", width=18)
    format_combo.grid(row=1, column=1, sticky="w", padx=(8, 0))

    # Layouts dropdown (filtered)
    ttk.Label(frame, text="Layouts:", font=(None, 11, "bold")).grid(row=2, column=0, sticky="w", pady=6)
    layout_var = tk.StringVar(value="")
    layouts_combo = ttk.Combobox(frame, textvariable=layout_var, state="readonly", width=42)
    layouts_combo.grid(row=2, column=1, sticky="w", padx=(8, 0))

    # Store mapping from display name -> path
    layout_path_map = {}

    def refresh_layouts(*_):
        press = press_var.get()
        fmt = format_var.get()
        matches = list_matching_layouts(press, fmt)

        layout_path_map.clear()
        display_names = [""]  # blank = no selection (new layout)
        for disp, path in matches:
            # disambiguate duplicate display names
            base = disp
            i = 2
            while disp in layout_path_map:
                disp = f"{base} ({i})"
                i += 1
            layout_path_map[disp] = path
            display_names.append(disp)

        layouts_combo["values"] = display_names
        layout_var.set("")  # reset selection when press/format changes

    press_combo.bind("<<ComboboxSelected>>", refresh_layouts)
    format_combo.bind("<<ComboboxSelected>>", refresh_layouts)

    # Initial populate
    refresh_layouts()

    def on_new_or_open():
        press = press_var.get()
        fmt = format_var.get()

        cfg = CONFIG_MAP.get((press, fmt))
        if not cfg:
            messagebox.showwarning("Not Configured", f"{press} - {fmt} is not configured yet.")
            return

        selected = layout_var.get().strip()
        load_path = layout_path_map.get(selected) if selected else None

        title = f"{press} - {fmt}"
        win = tk.Toplevel(root)
        build_press_layout(win, title=title, config=cfg, load_path=load_path)

    # Buttons
    btn_row = ttk.Frame(frame)
    btn_row.grid(row=3, column=0, columnspan=2, pady=16, sticky="w")

    ttk.Button(btn_row, text="New / Open", command=on_new_or_open, width=14).pack(side="left")
    ttk.Button(btn_row, text="Refresh Layouts", command=refresh_layouts, width=16).pack(side="left", padx=10)

    root.mainloop()


if __name__ == "__main__":
    build_interface()