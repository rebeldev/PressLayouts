import tkinter as tk
from tkinter import ttk

def _contrast_text_color(hex_color: str) -> str:
    """Return black/white text for good contrast on a hex background."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    # Perceived luminance
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "black" if luminance > 150 else "white"

def apply_window_sizing(win, config):
    """
    Size the window based on config:
      - autosize=True: shrink-wrap to contents (tab/broadsheet)
      - full_width=True: set to full screen width (8 up)
    """
    autosize = config.get("autosize", False)
    full_width = config.get("full_width", False)

    # Let Tk calculate requested sizes
    win.update_idletasks()

    req_w = win.winfo_reqwidth()
    req_h = win.winfo_reqheight()

    scr_w = win.winfo_screenwidth()
    scr_h = win.winfo_screenheight()

    # margins so the window doesn't touch screen edges / taskbar
    margin_w = config.get("screen_margin_w", 40)
    margin_h = config.get("screen_margin_h", 120)

    max_w = max(400, scr_w - margin_w)
    max_h = max(300, scr_h - margin_h)

    if full_width:
        w = scr_w  # full width of screen
        h = min(req_h, max_h)
        # place near top-left; adjust y if you want it lower
        win.geometry(f"{w}x{h}+0+0")
        return

    if autosize:
        w = min(req_w, max_w)
        h = min(req_h, max_h)

        # Center it on screen (nice touch)
        x = max(0, (scr_w - w) // 2)
        y = max(0, (scr_h - h) // 2)

        win.geometry(f"{w}x{h}+{x}+{y}")
        return

    # Otherwise: respect whatever geometry was set elsewhere (no change)

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

    # Draw center dividers (vertical/horizontal) in the grid
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

    # Match the unit background so the swatch rows blend in
    style = ttk.Style(unit_frame)
    unit_bg = style.lookup("Unit.TFrame", "background") or "#f0f0f0"

    for key, color in colors:
        row_frame = tk.Frame(color_frame, bg=unit_bg, height=24)
        row_frame.pack(fill="x", pady=1)
        row_frame.pack_propagate(False)

        # Center the swatch pair under the unit grid
        swatch_container = tk.Frame(row_frame, bg=unit_bg)
        swatch_container.place(relx=0.5, rely=0.5, anchor="center")

        text_color = _contrast_text_color(color)

        for i in range(swatch_cols):
            swatch = tk.Label(
                swatch_container,
                text=key,                 # <-- letter INSIDE each swatch
                fg=text_color,
                bg=color,
                font=(None, 9, "bold"),
                relief="solid",
                borderwidth=1,
                width=sw_w,
                height=sw_h,
            )
            swatch.pack(side="left")

            # Divider between the two swatches (keeps the centerline)
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


def build_press_layout(win, title="Press Layout", config=None):
    config = config or {}

    win.title(title)
    try:
        geom = config.get("geometry")
        if geom:
            win.geometry(geom)
    except Exception:
        pass

    style = ttk.Style(win)
    style.configure("Unit.TFrame", background="#f0f0f0", relief="solid", borderwidth=1)
    style.configure("Box.TFrame", background="#ffffff", relief="solid", borderwidth=1)

    header_frame = ttk.Frame(win, padding=(16, 12, 16, 8))
    header_frame.pack(fill="x")

    ttk.Label(header_frame, text="Issue Date:", font=(None, 12, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Entry(header_frame, width=16, font=(None, 12)).grid(row=0, column=1, sticky="w", padx=(8, 32))
    ttk.Entry(header_frame, font=(None, 14), width=35, justify="center").grid(row=0, column=3, columnspan=2, sticky="w", padx=(8, 24))

    header_frame.columnconfigure(2, weight=1)
    header_frame.columnconfigure(3, weight=1)
    header_frame.columnconfigure(4, weight=1)
    header_frame.columnconfigure(5, weight=1)

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

    # After all widgets have been created/placed:
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
    "left_labels": ["E1", "D1", "C1", "B1-Lower", "B1-Upper", "A1"],
    "right_labels": ["F1", "G1-Lower", "G1-Upper", "E2", "D2", "C2"],
    "only_k_labels": {"E1", "B1-Lower", "B1-Upper", "G1-Lower", "G1-Upper", "E2"},
    "folder_label": "Folder - 1",
}

PRESS_1_BROADSHEET = {
    **PRESS_1_BASE,
    "grid_rows": 2,
    "grid_cols": 2,
    "autosize": True,
}

PRESS_1_TAB = {
    **PRESS_1_BASE,
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
    "grid_rows": 2,
    "grid_cols": 8,
    "enable_hscroll": True,
    "full_width": True,
    "scroll_height_hint": 360,
}

# PRESS 2
PRESS_2_BASE = {
    **BASE_COMMON,
    "left_labels": ["E2", "D2", "C2", "B2-Lower", "B2-Upper", "A2"],
    "right_labels": ["F2", "G2-Lower", "G2-Upper"],
    "only_k_labels": {"E2", "B2-Lower", "B2-Upper", "G2-Lower", "G2-Upper"},
    "folder_label": "Folder - 2",
}

PRESS_2_BROADSHEET = {
    **PRESS_2_BASE,
    "grid_rows": 2,
    "grid_cols": 2,
    "autosize": True,
}

PRESS_2_TAB = {
    **PRESS_2_BASE,
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
    "grid_rows": 2,
    "grid_cols": 8,
    "enable_hscroll": True,
    "full_width": True,
    "scroll_height_hint": 360,
}

def build_interface():
    root = tk.Tk()
    root.title("Press Layout Launcher")
    root.geometry("400x150")
    root.minsize(380, 140)

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", pady=8)
    press_var = tk.StringVar(value="Press 1")
    ttk.Combobox(frame, textvariable=press_var, values=["Press 1", "Press 2"], state="readonly", width=15)\
        .grid(row=0, column=1, sticky="w", padx=(8, 0))

    ttk.Label(frame, text="Format:", font=(None, 11, "bold")).grid(row=1, column=0, sticky="w", pady=8)
    format_var = tk.StringVar(value="Broadsheet")
    ttk.Combobox(frame, textvariable=format_var, values=["Broadsheet", "Tab", "8 up"], state="readonly", width=15)\
        .grid(row=1, column=1, sticky="w", padx=(8, 0))

    def on_new():
        press = press_var.get()
        fmt = format_var.get()

        if press == "Press 1" and fmt == "Broadsheet":
            cfg, title = PRESS_1_BROADSHEET, "Press 1 - Broadsheet"
        elif press == "Press 1" and fmt == "Tab":
            cfg, title = PRESS_1_TAB, "Press 1 - Tab"
        elif press == "Press 1" and fmt == "8 up":
            cfg, title = PRESS_1_8UP, "Press 1 - 8 up"
        elif press == "Press 2" and fmt == "Broadsheet":
            cfg, title = PRESS_2_BROADSHEET, "Press 2 - Broadsheet"
        elif press == "Press 2" and fmt == "Tab":
            cfg, title = PRESS_2_TAB, "Press 2 - Tab"
        elif press == "Press 2" and fmt == "8 up":
            cfg, title = PRESS_2_8UP, "Press 2 - 8 up"
        else:
            cfg, title = None, f"{press} - {fmt}"

        if cfg is None:
            win = tk.Toplevel(root)
            ttk.Label(win, text=f"{press} - {fmt} is not configured yet.",
                      padding=20, font=(None, 12, "bold")).pack()
            return

        win = tk.Toplevel(root)
        build_press_layout(win, title=title, config=cfg)

    ttk.Button(frame, text="New", command=on_new, width=12).grid(row=2, column=0, columnspan=2, pady=20)

    root.mainloop()


if __name__ == "__main__":
    build_interface()