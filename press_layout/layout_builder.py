import os
import tkinter as tk
from tkinter import ttk, messagebox

from .config import LAYOUTS_DIR, TEMPLATE_DIR
from .helpers import *
from .persistence import collect_layout_data, populate_layout_from_data, do_save, do_save_as

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
    window_state_key = "template_layout_window" if template_mode else "layout_window"
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
    

    header_frame.columnconfigure(2, weight=1)
    header_frame.columnconfigure(3, weight=1)
    header_frame.columnconfigure(4, weight=1)
    header_frame.columnconfigure(5, weight=1)

    controls_outer_frame = ttk.Frame(win, padding=(16, 0, 16, 12))
    controls_center_frame = ttk.Frame(controls_outer_frame)
    controls_center_frame.pack(anchor="center")
    btn_frame = ttk.Frame(controls_center_frame)

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
    # Auto-select text on focus for section count spinbox
    sections_spinbox.bind('<FocusIn>', lambda e: e.widget.select_range(0, 'end'))

    pages_frame = ttk.Frame(header_frame)
    # place pages_frame closer to the section count and tighten spacing
    pages_frame.grid(row=1, column=2, columnspan=3, sticky="w", padx=(4, 8))
    ttk.Label(pages_frame, text="Section pages:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")

    format_name = config.get("format_name", "")
    page_increment = min_pages_for_format(format_name)
    max_pages = page_increment * 10

    initial_pages = config.get("section_pages", [page_increment] * 4)
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
        # only prefill names for enabled sections; disabled sections remain blank
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
        parsed = parse_section_id(raw)
        if parsed is not None:
            return parsed
        try:
            count = max(1, min(4, int(section_count_var.get())))
        except Exception:
            count = 1
        for idx in range(count):
            display = _section_display_name(idx + 1, names_snapshot=names_snapshot)
            if raw == display:
                return idx + 1
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
        entry = ttk.Entry(pages_frame, textvariable=nvar, width=6, justify="center", font=(None, 10))
        # center the name above the page spinbox column
        entry.grid(row=0, column=2 + idx * 2, sticky="", padx=(6, 2))
        section_name_entries.append(entry)

    for idx in range(4):
        page_value = str(initial_pages[idx] if idx < len(initial_pages) else page_increment)
        var = tk.StringVar(value=page_value)
        section_page_vars.append(var)

        ttk.Label(pages_frame, text=f"S{idx + 1}", font=(None, 10)).grid(
            row=1, column=1 + idx * 2, sticky="e", padx=(10, 2)
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
        sp.grid(row=1, column=2 + idx * 2, sticky="w")
        section_page_entries.append(sp)

    # Auto-select text on focus for all section page spinboxes
    for sp in section_page_entries:
        sp.bind('<FocusIn>', lambda e: e.widget.select_range(0, 'end'))

    def _update_section_page_states(count):
        for idx, entry in enumerate(section_page_entries):
            if idx < count:
                entry.state(["!disabled"])
                # enable name entries as well
                try:
                    section_name_entries[idx].state(["!disabled"])
                except Exception:
                    pass
                # ensure enabled sections have a sensible default if blank
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
                entry.state(["disabled"])
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


    apply_min_pages_to_section_vars(format_name, section_count_var, section_page_vars, fill_only_blanks=True)

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
        "issue_entry": issue_entry,
        "product_entry": product_entry,
        "section_count_var": section_count_var,
        "section_page_vars": section_page_vars,
        "_update_section_page_states": _update_section_page_states,
        "imposition_var": imposition_var,
        "section_name_vars": section_name_vars,
        "section_name_entries": section_name_entries,
        "_refresh_unit_section_choices": _refresh_unit_section_choices,
        "_capture_unit_section_assignments": _capture_unit_section_assignments,
        "imposition_entry": imposition_entry,
        "color_pages_var": color_pages_var,
        "plates_var": plates_var,
        "grid_cols": grid_cols,
        "units": units,
        "file_path": None,
        "layout_name": None,
        "template_mode": template_mode,
        "default_dir": TEMPLATE_DIR if template_mode else LAYOUTS_DIR,
        "color_cells": set(),  # per-cell storage
    }

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
    if not template_mode:
        color_toggle = ttk.Checkbutton(
            btn_frame,
            style="SlideToggle.TCheckbutton",
            text="Color Select",
            variable=color_select_var,
            takefocus=False
        )
        color_toggle.pack(side="left", padx=(0, 12))

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

    def do_save_with_starter():
        ok = do_save(win, ctx)
        if ok:
            _persist_starter_format_to_file()
            try:
                ctx["dirty"] = False
            except Exception:
                pass
        return ok

    def do_save_as_with_starter():
        ok = do_save_as(win, ctx)
        if ok:
            _persist_starter_format_to_file()
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
        return {
            "publication": product_entry.get().strip(),
            "issue_date": issue_text,
            "color_pages": (ctx.get("color_pages_var", color_pages_var).get() or "").strip(),
            "plates": (ctx.get("plates_var", plates_var).get() or "").strip(),
        }

    def _load_starter_font(size, bold=False):
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
        try:
            from PIL import Image, ImageDraw
        except Exception:
            raise RuntimeError("Pillow is required for starter sheet printing. Please install pillow (pip install pillow).")

        publication = fields.get("publication", "")
        issue_date = fields.get("issue_date", "")
        color_pages = fields.get("color_pages", "")
        plates = fields.get("plates", "")
        fmt = (format_name or "Standard").strip().upper()

        if fmt == "NYT":
            img = Image.new("RGB", (2200, 2000), "white")
            draw = ImageDraw.Draw(img)
            title_font = _load_starter_font(100, bold=True)
            label_font = _load_starter_font(64, bold=True)
            value_font = _load_starter_font(72, bold=True)
            _draw_text(draw, (700, 55), "NYT CLOSE SHEET", title_font)
            _draw_line(draw, (350, 175, 2000, 175), width=6)
            _draw_text(draw, (10, 315), "Date:", label_font)
            _draw_text(draw, (270, 315), issue_date, value_font)
            _draw_line(draw, (190, 385, 720, 385), width=3)
            _draw_text(draw, (1320, 315), "Kills:", label_font)
            _draw_line(draw, (1510, 385, 1850, 385), width=3)
            _draw_text(draw, (1360, 435), "PS:", label_font)
            _draw_line(draw, (1510, 505, 1850, 505), width=3)
            _draw_text(draw, (10, 650), "Publication:", label_font)
            _draw_text(draw, (540, 650), publication, value_font)
            _draw_line(draw, (450, 720, 1850, 720), width=3)
            _draw_text(draw, (10, 900), "Color Pages:", label_font)
            _draw_text(draw, (540, 900), color_pages, value_font)
            _draw_line(draw, (450, 970, 1000, 970), width=3)
            _draw_text(draw, (1130, 900), "Color add:", label_font)
            _draw_line(draw, (1510, 970, 1850, 970), width=3)
            _draw_text(draw, (1110, 1000), "Color drop:", label_font)
            _draw_line(draw, (1510, 1070, 1850, 1070), width=3)
            _draw_text(draw, (10, 1125), "Plates Needed:", label_font)
            _draw_text(draw, (540, 1125), plates, value_font)
            _draw_line(draw, (450, 1195, 870, 1195), width=3)
            _draw_text(draw, (10, 1340), "Starter Image Time:", label_font)
            _draw_line(draw, (720, 1410, 1130, 1410), width=3)
            _draw_text(draw, (10, 1555), "Starter Plate Time:", label_font)
            _draw_line(draw, (720, 1625, 1130, 1625), width=3)
            _draw_text(draw, (10, 1765), "Closed:", label_font)
            _draw_line(draw, (240, 1835, 880, 1835), width=3)
            return img

        if fmt == "USAT":
            img = Image.new("RGB", (1900, 1820), "white")
            draw = ImageDraw.Draw(img)
            label_font = _load_starter_font(64, bold=True)
            value_font = _load_starter_font(72, bold=True)
            _draw_text(draw, (10, 70), "PUBLICATION:", label_font)
            _draw_text(draw, (820, 70), publication, value_font)
            _draw_line(draw, (660, 140, 1830, 140), width=4)
            _draw_text(draw, (10, 305), "ISSUE DATE:", label_font)
            _draw_text(draw, (980, 305), issue_date, value_font)
            _draw_line(draw, (660, 375, 1830, 375), width=4)
            _draw_text(draw, (10, 565), "COLOR PAGES:", label_font)
            _draw_text(draw, (920, 565), color_pages, value_font)
            _draw_line(draw, (660, 635, 1830, 635), width=4)
            _draw_text(draw, (10, 825), "# OF PLATES:", label_font)
            _draw_text(draw, (920, 825), plates, value_font)
            _draw_line(draw, (660, 895, 1830, 895), width=4)
            _draw_text(draw, (10, 1115), "FIRST IMAGE:", label_font)
            _draw_line(draw, (660, 1185, 1830, 1185), width=4)
            _draw_text(draw, (10, 1375), "LAST IMAGE:", label_font)
            _draw_line(draw, (660, 1445, 1830, 1445), width=4)
            _draw_text(draw, (10, 1635), "LAST PLATE:", label_font)
            _draw_line(draw, (660, 1705, 1830, 1705), width=4)
            return img

        img = Image.new("RGB", (2100, 1700), "white")
        draw = ImageDraw.Draw(img)
        label_font = _load_starter_font(64, bold=True)
        value_font = _load_starter_font(72, bold=True)
        _draw_text(draw, (10, 80), "PUBLICATION:", label_font)
        _draw_text(draw, (760, 80), publication, value_font)
        _draw_line(draw, (560, 150, 2010, 150), width=4)
        _draw_text(draw, (10, 360), "ISSUE DATE:", label_font)
        _draw_text(draw, (980, 360), issue_date, value_font)
        _draw_line(draw, (560, 430, 2010, 430), width=4)
        _draw_text(draw, (10, 640), "COLOR PAGES:", label_font)
        _draw_text(draw, (980, 640), color_pages, value_font)
        _draw_line(draw, (560, 710, 2010, 710), width=4)
        _draw_text(draw, (10, 920), "# OF PLATES:", label_font)
        _draw_text(draw, (980, 920), plates, value_font)
        _draw_line(draw, (560, 990, 2010, 990), width=4)
        _draw_text(draw, (10, 1220), "LAST IMAGE:", label_font)
        _draw_line(draw, (560, 1290, 2010, 1290), width=4)
        _draw_text(draw, (10, 1520), "LAST PLATE:", label_font)
        _draw_line(draw, (560, 1590, 2010, 1590), width=4)
        return img

    def _show_starter_printer_dialog():
        try:
            import win32print
        except Exception as e:
            raise RuntimeError(f"Missing win32print dependency: {e}")
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
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
        dialog.title("Print Starter")
        dialog.transient(win)
        dialog.resizable(False, False)
        remember_window_geometry(dialog, "starter_print_dialog", default_geometry="560x150", minsize=(520, 150))
        dialog.grab_set()
        printer_var = tk.StringVar(value=default_printer)
        copies_var = tk.IntVar(value=1)
        ttk.Label(dialog, text="Printer:").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        printer_combo = ttk.Combobox(dialog, textvariable=printer_var, values=printer_names, state="readonly", width=50)
        printer_combo.grid(row=0, column=1, sticky="ew", padx=12, pady=(12, 4))
        printer_combo.focus_set()
        ttk.Label(dialog, text="Copies:").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        copies_spin = ttk.Spinbox(dialog, from_=1, to=999, textvariable=copies_var, width=8)
        copies_spin.grid(row=1, column=1, sticky="w", padx=12, pady=4)
        copies_spin.bind('<FocusIn>', lambda e: e.widget.select_range(0, 'end'))
        ttk.Label(dialog, text="Orientation: Landscape", font=(None, 10, "bold")).grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 4))
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(8, 12), padx=12, sticky="e")
        def _on_print():
            result["printer"] = printer_var.get()
            try:
                result["copies"] = max(1, int(copies_var.get()))
            except Exception:
                result["copies"] = 1
            dialog.destroy()
        def _on_cancel():
            dialog.destroy()
        ttk.Button(button_frame, text="Print", command=_on_print, width=10).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="Cancel", command=_on_cancel, width=10).pack(side="left")
        dialog.protocol("WM_DELETE_WINDOW", _on_cancel)
        dialog.columnconfigure(1, weight=1)
        win.wait_window(dialog)
        if "printer" not in result:
            return None
        return result["printer"], result["copies"]

    def _direct_print_image(img_path, printer_name, copies, orientation="Landscape", margins_inches=None):
        try:
            import win32ui
            import win32con
            import win32api
            import tempfile
            import time
            from PIL import Image, ImageWin
            import traceback
        except Exception as e:
            raise RuntimeError(f"Missing dependency: {e}")
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
            if orientation == 'Landscape':
                img = img.transpose(Image.ROTATE_90)
            try:
                fd, shell_path = tempfile.mkstemp(suffix='.bmp')
                os.close(fd)
                img.save(shell_path, format='BMP')
                for _ in range(max(1, copies)):
                    win32api.ShellExecute(0, 'printto', shell_path, f'\"{printer_name}\"', '.', 0)
                    time.sleep(1.5)
                return True
            except Exception:
                pass
            dc = win32ui.CreateDC()
            dc.CreatePrinterDC(printer_name)
            printable_area = (dc.GetDeviceCaps(win32con.HORZRES), dc.GetDeviceCaps(win32con.VERTRES))
            offset_x = dc.GetDeviceCaps(win32con.PHYSICALOFFSETX)
            offset_y = dc.GetDeviceCaps(win32con.PHYSICALOFFSETY)
            dpi_x = max(1, dc.GetDeviceCaps(win32con.LOGPIXELSX))
            dpi_y = max(1, dc.GetDeviceCaps(win32con.LOGPIXELSY))
            margins_inches = margins_inches or {"left": 0.15, "top": 0.15, "right": 0.15, "bottom": 0.15}
            left_margin = max(0, int(round(float(margins_inches.get("left", 0.15)) * dpi_x)))
            top_margin = max(0, int(round(float(margins_inches.get("top", 0.15)) * dpi_y)))
            right_margin = max(0, int(round(float(margins_inches.get("right", 0.15)) * dpi_x)))
            bottom_margin = max(0, int(round(float(margins_inches.get("bottom", 0.15)) * dpi_y)))
            safe_w = max(1, printable_area[0] - left_margin - right_margin)
            safe_h = max(1, printable_area[1] - top_margin - bottom_margin)
            scale = min(safe_w / img.size[0], safe_h / img.size[1])
            scaled = img.resize((max(1, int(img.size[0] * scale)), max(1, int(img.size[1] * scale))), Image.LANCZOS)
            dib = ImageWin.Dib(scaled)
            x = int(offset_x + left_margin + ((safe_w - scaled.size[0]) / 2))
            y = int(offset_y + top_margin + ((safe_h - scaled.size[1]) / 2))
            dc.StartDoc(img_path)
            for _ in range(max(1, copies)):
                dc.StartPage()
                dib.draw(dc.GetHandleOutput(), (x, y, x + scaled.size[0], y + scaled.size[1]))
                dc.EndPage()
            dc.EndDoc()
            dc.DeleteDC()
            return True
        except Exception as e:
            try:
                err = traceback.format_exc()
            except Exception:
                err = str(e)
            try:
                dc.DeleteDC()
            except Exception:
                pass
            raise RuntimeError(err)

    def print_starter_sheet():
        if template_mode:
            return
        format_name = starter_format_var.get().strip() or "Standard"
        try:
            img = _make_starter_sheet_image(format_name, _starter_sheet_fields())
            import tempfile
            fd, path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            img.save(path, format="PNG")
        except Exception as e:
            messagebox.showerror("Starter Sheet", str(e))
            return
        try:
            printed = False
            error_message = None
            if os.name == 'nt':
                try:
                    selection = _show_starter_printer_dialog()
                    if selection:
                        printer_name, copies = selection
                        printed = _direct_print_image(path, printer_name, copies, orientation="Landscape")
                except Exception as e:
                    error_message = str(e)
            if not printed:
                if error_message:
                    messagebox.showwarning("Starter Sheet", f"Direct print failed:\n{error_message}\n\nOpening image preview instead.")
                try:
                    os.startfile(path)
                except Exception:
                    messagebox.showinfo("Starter Sheet", f"Saved starter sheet preview to:\n{path}\nPlease open this file and print it in landscape mode.")
        except Exception as e:
            messagebox.showerror("Starter Sheet", str(e))

    def _measure_text(draw, text, font):
        text = text or ""
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            return right - left, bottom - top
        except Exception:
            return draw.textsize(text, font=font)

    def _draw_centered_text(draw, box, text, font, fill="black"):
        x0, y0, x1, y1 = box
        tw, th = _measure_text(draw, text, font)
        tx = x0 + max(0, ((x1 - x0) - tw) / 2)
        ty = y0 + max(0, ((y1 - y0) - th) / 2)
        draw.text((tx, ty), text or "", fill=fill, font=font)

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
        try:
            from PIL import Image, ImageDraw
        except Exception:
            raise RuntimeError("Pillow is required for printing. Please install pillow (pip install pillow).")
        img_w, img_h = 2200, 1700
        img = Image.new("RGB", (img_w, img_h), "white")
        draw = ImageDraw.Draw(img)
        if grid_cols >= 8:
            title_sz, header_sz, text_sz, unit_sz, section_sz, cell_sz = 46, 34, 24, 24, 30, 18
        elif grid_cols >= 4:
            title_sz, header_sz, text_sz, unit_sz, section_sz, cell_sz = 52, 36, 26, 24, 32, 22
        else:
            title_sz, header_sz, text_sz, unit_sz, section_sz, cell_sz = 56, 38, 28, 24, 34, 26
        title_font = _load_starter_font(title_sz, bold=True)
        header_font = _load_starter_font(header_sz, bold=True)
        issue_font = _load_starter_font(header_sz + 4, bold=True)
        text_font = _load_starter_font(text_sz, bold=False)
        small_font = _load_starter_font(max(18, text_sz - 4), bold=False)
        sections_print_font = _load_starter_font(max(36, (max(18, text_sz - 4)) * 2), bold=True)
        unit_font = _load_starter_font(unit_sz, bold=True)
        section_font = _load_starter_font(section_sz, bold=True)
        cell_font_render = _load_starter_font(cell_sz, bold=True)
        margin_x = 55
        header_top = 26
        header_h = 180
        footer_h = 74
        grid_top = header_top + header_h + 14
        footer_y = img_h - footer_h - 30
        raw_issue = issue_entry.get().strip()
        issue_text = raw_issue
        if not template_mode:
            try:
                dt = parse_issue_date_flexible(raw_issue)
                if dt:
                    issue_text = dt.strftime("%m/%d/%Y")
            except Exception:
                pass
        product_text = product_entry.get().strip()
        imposition_text = imposition_var.get().strip()
        # Use product name as the prominent centered title and place Issue Date on the same row
        label_top = header_top
        _draw_centered_text(draw, (margin_x, label_top, img_w - margin_x, label_top + 60), product_text or title_base or ("Template Layout" if template_mode else "Press Layout"), title_font)
        draw.text((margin_x, label_top + 66), f"Issue Date: {issue_text}", fill="black", font=sections_print_font)
        draw.text((img_w - margin_x - 420 - 300, label_top + 66), f"Imposition: {imposition_text}", fill="black", font=text_font)
        try:
            count = max(1, min(4, int(section_count_var.get())))
        except Exception:
            count = 1
        # Build section page counts as: Sections: 12 / 16 / 20
        values = []
        for idx in range(count):
            value = (section_page_vars[idx].get() or "").strip()
            if value:
                values.append(value)
        sections_text = " / ".join(values)
        if sections_text:
            draw.text((margin_x, label_top + 118), f"Sections: {sections_text}", fill="black", font=sections_print_font)
        draw.line((margin_x, grid_top - 18, img_w - margin_x, grid_top - 18), fill="#444444", width=3)
        left_order, right_order, unit_map = _visible_print_labels()
        total_units = len(left_order) + len(right_order)
        if total_units <= 0:
            draw.text((margin_x, grid_top + 20), "No units to print.", fill="black", font=text_font)
            return img
        gap = max(10, int(unit_padx * 2.4))
        folder_gap = max(gap + 8, int(folder_padx * 1.5))
        folder_w = 150 if grid_cols <= 4 else 175
        left_gaps = max(0, len(left_order) - 1) * gap
        right_gaps = max(0, len(right_order) - 1) * gap
        usable_w = img_w - (2 * margin_x) - left_gaps - right_gaps - (2 * folder_gap) - folder_w
        unit_w = max(115, int(usable_w / max(1, total_units)))
        unit_h = footer_y - grid_top - 12
        box_top_offset = 64
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
                (folder_mid - folder_arrow_w/2, cy - 24),
                (folder_mid + folder_arrow_w/2, cy - 24),
                (folder_mid, cy + 28)
            ], fill="#666666", outline="#666666")
        left_triangle_center_y = arrow_center_y + 84
        # shift left triangle well to the left so it doesn't touch the middle triangle
        left_triangle_left = folder_x0 - 18
        draw.polygon([
            (left_triangle_left, left_triangle_center_y - 24),
            (left_triangle_left + folder_arrow_w, left_triangle_center_y - 24),
            (left_triangle_left + folder_arrow_w / 2, left_triangle_center_y + 28)
        ], fill="#666666", outline="#666666")
        # Move folder label down below the entire stack of triangles
        folder_label_top = arrow_center_y + 168 + 36
        _draw_centered_text(draw, (folder_x0, folder_label_top, folder_x1, folder_label_top + unit_label_h), folder_label, unit_font)
        for lab in left_order + right_order:
            unit = unit_map[lab]
            x0 = x_positions[lab]
            x1 = x0 + unit_w
            y0 = grid_top
            y1 = y0 + unit_h

            section_text = (unit.get("section_entry").get() or "").strip().upper() if unit.get("section_entry") else ""
            section_label_space = section_h + 6
            if section_text:
                _draw_centered_text(draw, (x0, y0, x1, y0 + section_h), section_text, section_font)

            box_top = y0 + section_label_space

            # Compute cols/rows and constrain printed box height so cells
            # don't become vertically stretched. Prefer roughly square cells
            # by basing box height on cell width when possible.
            entries = unit.get("entries", [])
            rows = len(entries)
            cols = len(entries[0]) if rows else 0
            if rows <= 0 or cols <= 0:
                continue

            # base cell width from unit width
            cell_w = (x1 - x0) / cols
            # original available box height
            orig_box_h = max(1, y1 - box_top)
            # desired box height to keep cells near-square
            desired_box_h = int(rows * cell_w * 1.05)
            box_h = min(orig_box_h, desired_box_h)
            # ensure a minimum reasonable height so labels/footer don't overlap
            min_box_h = max(24, int(unit_label_h + section_h + 8))
            box_h = max(min_box_h, box_h)
            # recompute y1 to reflect adjusted box height
            y1 = box_top + box_h
            draw.rectangle((x0, box_top, x1, y1), outline="black", width=2, fill="white")
            cell_h = box_h / rows
            mid_col = cols // 2
            mid_row = rows // 2
            for r in range(1, rows):
                yy = box_top + (r * cell_h)
                width = midline_thickness if (rows % 2 == 0 and r == mid_row) else 1
                color = midline_color if width > 1 else "#888888"
                draw.line((x0, yy, x1, yy), fill=color, width=width)
            for c in range(1, cols):
                xx = x0 + (c * cell_w)
                width = midline_thickness if (cols % 2 == 0 and c == mid_col) else 1
                color = midline_color if width > 1 else "#888888"
                draw.line((xx, box_top, xx, y1), fill=color, width=width)
            for r in range(rows):
                for c in range(cols):
                    cx0 = x0 + (c * cell_w)
                    cy0 = box_top + (r * cell_h)
                    cx1 = x0 + ((c + 1) * cell_w)
                    cy1 = box_top + ((r + 1) * cell_h)
                    value = ""
                    try:
                        value = (entries[r][c].get() or "").strip()
                    except Exception:
                        value = ""
                    if value:
                        _draw_centered_text(draw, (cx0 + 2, cy0 + 2, cx1 - 2, cy1 - 2), value, cell_font_render)
                    if (lab, r, c) in ctx.get("color_cells", set()):
                        pad = max(5, int(min(cell_w, cell_h) * 0.12))
                        draw.ellipse((cx0 + pad, cy0 + pad, cx1 - pad, cy1 - pad), outline="red", width=3)
            # After cells, draw the unit label below the grid, then stacked larger swatches
            label_top = y1 + 6
            _draw_centered_text(draw, (x0, label_top, x1, label_top + unit_label_h), lab, unit_font)
            section_offset = 0

            # Draw stacked, larger color swatches (one row per color, multiple columns per row)
            try:
                use_cmyk = lab not in only_k_labels
            except Exception:
                use_cmyk = True
            if use_cmyk:
                colors = [("K", "#7f7f7f"), ("Y", "#fff176"), ("M", "#f48fb1"), ("C", "#90caf9")]
            else:
                colors = [("K", "#7f7f7f")]
            sw_cols = swatch_cols if swatch_cols and swatch_cols > 0 else 1
            sw_h = max(28, int(unit_label_h * 1.5))
            sw_spacing = 8
            sw_start_y = label_top + unit_label_h + section_offset + 8
            for ci, (key, color) in enumerate(colors):
                # compute swatch width for this row
                row_count = sw_cols
                sw_w = max(18, int(min((unit_w * 0.9) / max(1, row_count), cell_w * 0.9)))
                row_total_w = row_count * sw_w + (row_count - 1) * sw_spacing
                row_x = x0 + (unit_w - row_total_w) / 2.0
                row_y = sw_start_y + ci * (sw_h + sw_spacing)
                for i in range(sw_cols):
                    sx0 = row_x + i * (sw_w + sw_spacing)
                    sx1 = sx0 + sw_w
                    sy1 = row_y + sw_h
                    draw.rectangle((sx0, row_y, sx1, sy1), fill=color, outline="#333333")
                    try:
                        rcol = int(color.lstrip('#')[0:2], 16)
                        gcol = int(color.lstrip('#')[2:4], 16)
                        bcol = int(color.lstrip('#')[4:6], 16)
                        luminance = 0.299 * rcol + 0.587 * gcol + 0.114 * bcol
                        text_fill = "black" if luminance > 150 else "white"
                    except Exception:
                        text_fill = "black"
                    _draw_centered_text(draw, (sx0, row_y, sx1, sy1), key, small_font, fill=text_fill)
        try:
            update_color_and_plate_counts()
        except Exception:
            pass
        color_pages_text = (ctx.get("color_pages_var", color_pages_var).get() or "0").strip()
        plates_text = (ctx.get("plates_var", plates_var).get() or "0").strip()
        draw.line((margin_x, footer_y - 14, img_w - margin_x, footer_y - 14), fill="#444444", width=3)
        draw.text((margin_x, footer_y), f"Color Pages: {color_pages_text}", fill="black", font=header_font)
        draw.text((margin_x + 480, footer_y), f"Plates: {plates_text}", fill="black", font=header_font)
        return img

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
            img.save(path, format="PNG")
            direct_print_error = {"message": None}
            def _show_printer_dialog():
                try:
                    import win32print
                except Exception as e:
                    direct_print_error["message"] = f"Missing win32print dependency: {e}"
                    return None
                try:
                    printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
                except Exception as e:
                    direct_print_error["message"] = f"Could not enumerate printers: {e}"
                    return None
                printer_names = [info[2] for info in printers if info and len(info) >= 3 and info[2]]
                if not printer_names:
                    direct_print_error["message"] = "No printers were found on this system."
                    return None
                try:
                    default_printer = win32print.GetDefaultPrinter()
                except Exception:
                    default_printer = None
                if default_printer not in printer_names:
                    default_printer = printer_names[0]
                result = {}
                dialog = tk.Toplevel(win)
                dialog.title("Print")
                dialog.transient(win)
                dialog.resizable(False, False)
                remember_window_geometry(dialog, "layout_print_dialog", default_geometry="620x240", minsize=(560, 220))
                dialog.grab_set()
                printer_var = tk.StringVar(value=default_printer)
                copies_var = tk.IntVar(value=5)
                orientation_var = tk.StringVar(value="Landscape")
                left_margin_var = tk.StringVar(value="0.15")
                top_margin_var = tk.StringVar(value="0.15")
                right_margin_var = tk.StringVar(value="0.15")
                bottom_margin_var = tk.StringVar(value="0.15")
                ttk.Label(dialog, text="Printer:").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
                printer_combo = ttk.Combobox(dialog, textvariable=printer_var, values=printer_names, state="readonly", width=50)
                printer_combo.grid(row=0, column=1, sticky="ew", padx=12, pady=(12, 4))
                printer_combo.focus_set()
                ttk.Label(dialog, text="Copies:").grid(row=1, column=0, sticky="w", padx=12, pady=4)
                copies_spin_print = ttk.Spinbox(dialog, from_=1, to=999, textvariable=copies_var, width=8)
                copies_spin_print.grid(row=1, column=1, sticky="w", padx=12, pady=4)
                copies_spin_print.bind('<FocusIn>', lambda e: e.widget.select_range(0, 'end'))
                ttk.Label(dialog, text="Orientation:").grid(row=2, column=0, sticky="w", padx=12, pady=4)
                orient_frame = ttk.Frame(dialog)
                orient_frame.grid(row=2, column=1, sticky="w", padx=12, pady=4)
                ttk.Radiobutton(orient_frame, text="Landscape", variable=orientation_var, value="Landscape").pack(side="left")
                ttk.Radiobutton(orient_frame, text="Portrait", variable=orientation_var, value="Portrait").pack(side="left", padx=(12, 0))
                ttk.Label(dialog, text="Margins (inches):").grid(row=3, column=0, sticky="nw", padx=12, pady=4)
                margins_frame = ttk.Frame(dialog)
                margins_frame.grid(row=3, column=1, sticky="w", padx=12, pady=4)
                ttk.Label(margins_frame, text="Left").grid(row=0, column=0, sticky="w")
                left_spin = ttk.Spinbox(margins_frame, from_=0.0, to=2.0, increment=0.05, textvariable=left_margin_var, width=6)
                left_spin.grid(row=0, column=1, padx=(6, 12), pady=2)
                left_spin.bind('<FocusIn>', lambda e: e.widget.select_range(0, 'end'))
                ttk.Label(margins_frame, text="Top").grid(row=0, column=2, sticky="w")
                top_spin = ttk.Spinbox(margins_frame, from_=0.0, to=2.0, increment=0.05, textvariable=top_margin_var, width=6)
                top_spin.grid(row=0, column=3, padx=(6, 0), pady=2)
                top_spin.bind('<FocusIn>', lambda e: e.widget.select_range(0, 'end'))
                ttk.Label(margins_frame, text="Right").grid(row=1, column=0, sticky="w")
                right_spin = ttk.Spinbox(margins_frame, from_=0.0, to=2.0, increment=0.05, textvariable=right_margin_var, width=6)
                right_spin.grid(row=1, column=1, padx=(6, 12), pady=2)
                right_spin.bind('<FocusIn>', lambda e: e.widget.select_range(0, 'end'))
                ttk.Label(margins_frame, text="Bottom").grid(row=1, column=2, sticky="w")
                bottom_spin = ttk.Spinbox(margins_frame, from_=0.0, to=2.0, increment=0.05, textvariable=bottom_margin_var, width=6)
                bottom_spin.grid(row=1, column=3, padx=(6, 0), pady=2)
                bottom_spin.bind('<FocusIn>', lambda e: e.widget.select_range(0, 'end'))
                button_frame = ttk.Frame(dialog)
                button_frame.grid(row=4, column=0, columnspan=2, pady=(8, 12), padx=12, sticky="e")
                def _parse_margin(value, default=0.15):
                    try:
                        return max(0.0, float(str(value).strip()))
                    except Exception:
                        return default
                def _on_print():
                    result['printer'] = printer_var.get()
                    try:
                        result['copies'] = max(1, int(copies_var.get()))
                    except Exception:
                        result['copies'] = 1
                    result['orientation'] = orientation_var.get()
                    result['margins_inches'] = {'left': _parse_margin(left_margin_var.get()), 'top': _parse_margin(top_margin_var.get()), 'right': _parse_margin(right_margin_var.get()), 'bottom': _parse_margin(bottom_margin_var.get())}
                    dialog.destroy()
                def _on_cancel():
                    dialog.destroy()
                ttk.Button(button_frame, text="Print", command=_on_print, width=10).pack(side="left", padx=(0, 8))
                ttk.Button(button_frame, text="Cancel", command=_on_cancel, width=10).pack(side="left")
                dialog.protocol("WM_DELETE_WINDOW", _on_cancel)
                dialog.columnconfigure(1, weight=1)
                win.wait_window(dialog)
                if 'printer' not in result:
                    direct_print_error['message'] = "Printer selection was canceled."
                    return None
                return result['printer'], result['copies'], result['orientation'], result['margins_inches']
            printed = False
            if os.name == 'nt':
                try:
                    printer_selection = _show_printer_dialog()
                    if printer_selection:
                        printer_name, copies, orientation, margins_inches = printer_selection
                        printed = _direct_print_image(path, printer_name, copies, orientation=orientation, margins_inches=margins_inches)
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
        ttk.Label(btn_frame, text="Starter:").pack(side="left", padx=(0, 6))
        starter_combo = ttk.Combobox(btn_frame, textvariable=starter_format_var, values=["Standard", "NYT", "USAT"], state="readonly", width=10)
        starter_combo.pack(side="left", padx=(0, 8))
        starter_combo.bind("<<ComboboxSelected>>", lambda e: _mark_dirty_var())
        ttk.Button(btn_frame, text="Print Starter", command=print_starter_sheet, width=12, takefocus=False).pack(side="left", padx=(0, 12))
    ttk.Button(btn_frame, text="Print", command=lambda: print_layout(win, ctx), width=10, takefocus=False).pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="Save", command=do_save_with_starter, width=10, takefocus=False).pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="Save As", command=do_save_as_with_starter, width=10, takefocus=False).pack(side="left")
    btn_frame.pack(side="left")

    # Expose print functions for external callers (launcher use)
    try:
        win.print_layout = lambda: print_layout(win, ctx)
        win.print_starter = lambda: print_starter_sheet()
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
            section_entry.bind("<KeyRelease>", lambda e, _u=u: (_record_unit_section_assignment(_u), update_imposition()))
            section_entry.bind("<<ComboboxSelected>>", lambda e, _u=u: (_record_unit_section_assignment(_u), update_imposition()))
            section_entry.bind("<FocusOut>", lambda e, _u=u: (_record_unit_section_assignment(_u), update_imposition()))
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
                entry.bind("<FocusOut>", lambda e, _u=u, _r=r, _c=c: (refresh_cell_overlay(_u, _r, _c), update_imposition()))
                entry.bind("<KeyRelease>", lambda e, _u=u, _r=r, _c=c: (refresh_cell_overlay(_u, _r, _c), update_imposition()))

    if color_toggle is not None:
        color_toggle.configure(command=refresh_color_overlays)

    # ---- Load file (open vs copy) ----
    if load_path:
        data = safe_read_json(load_path)
        if data:
            populate_layout_from_data(ctx, data)
            _capture_unit_section_assignments()
            _refresh_unit_section_choices()
            apply_min_pages_to_section_vars(format_name, section_count_var, section_page_vars, fill_only_blanks=True)
            if not template_mode:
                starter_format_var.set(data.get("starter_format") or "Standard")

            if load_as_copy:
                ctx["file_path"] = None
                ctx["layout_name"] = None
                tmpl = os.path.splitext(os.path.basename(load_path))[0]
                win.title(f"{title_base}  —  (from template: {tmpl})")
            else:
                ctx["file_path"] = load_path
                ctx["layout_name"] = data.get("name") or os.path.splitext(os.path.basename(load_path))[0]
                win.title(f"{title_base}  —  {os.path.basename(load_path)}")

    _capture_unit_section_assignments()
    # initial refreshes
    update_imposition()
    refresh_color_overlays()

    # --- change tracking (dirty flag) ---------------------------------
    ctx["dirty"] = False

    def _mark_dirty_event(event=None):
        try:
            ctx["dirty"] = True
        except Exception:
            pass

    def _mark_dirty_var(*_):
        try:
            ctx["dirty"] = True
        except Exception:
            pass


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
    if not has_saved_window_state:
        apply_window_sizing(win, config)
    remember_window_geometry(
        win,
        window_state_key,
    )
    # Bind change events to mark the layout as dirty
    try:
        issue_entry.bind("<KeyRelease>", _mark_dirty_event)
        product_entry.bind("<KeyRelease>", _mark_dirty_event)
        for sv in section_page_vars:
            try:
                sv.trace_add("write", _mark_dirty_var)
            except Exception:
                pass
        sections_spinbox.configure(command=_mark_dirty_var)
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
                return
            # if save failed or cancelled, do not close
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
