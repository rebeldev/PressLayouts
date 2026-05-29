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
    def print_layout(win, ctx):
        try:
            from PIL import ImageGrab, Image
        except Exception:
            messagebox.showerror("Print Failed", "Pillow is required for printing. Please install pillow (pip install pillow).")
            return

        # Hide only the button/toggle group while capturing so the printout
        # still includes the Color Pages / Plates counters.
        was_btn_visible = False
        hidden_unused_press1_unit_frames = []
        original_geometry = None
        original_product_width = None
        original_imposition_width = None
        original_minsize = None
        try:
            try:
                was_btn_visible = btn_frame.winfo_ismapped()
                if was_btn_visible:
                    btn_frame.pack_forget()
            except Exception:
                was_btn_visible = False

            # In Press 1 layouts, do not print unused E2 / D2 / C2 units.
            try:
                if ctx.get("press_name") == "Press 1":
                    for unit in ctx.get("units", []):
                        if unit.get("label") not in {"E2", "D2", "C2"}:
                            continue
                        if unit_min_page_number(unit) is not None:
                            continue
                        frame = unit.get("frame")
                        if frame is not None and frame.winfo_ismapped():
                            hidden_unused_press1_unit_frames.append(frame)
                            frame.grid_remove()
            except Exception:
                hidden_unused_press1_unit_frames = []

            # If any Press 1 tail units are hidden, temporarily condense the
            # header row and resize the print window to just the printed content.
            try:
                original_geometry = win.geometry()
            except Exception:
                original_geometry = None
            try:
                original_product_width = int(product_entry.cget("width"))
            except Exception:
                original_product_width = None
            try:
                original_imposition_width = int(imposition_entry.cget("width"))
            except Exception:
                original_imposition_width = None
            try:
                original_minsize = tuple(win.minsize())
            except Exception:
                original_minsize = None

            if hidden_unused_press1_unit_frames:
                try:
                    product_text = product_entry.get().strip()
                    imposition_text = imposition_var.get().strip()
                    if original_product_width is not None:
                        product_entry.configure(width=max(12, min(original_product_width, len(product_text) + 2)))
                    if original_imposition_width is not None:
                        imposition_entry.configure(width=max(10, min(original_imposition_width, len(imposition_text) + 2)))
                except Exception:
                    pass

            # Let geometry changes settle before capture.
            try:
                import time
            except Exception:
                time = None
            try:
                if original_minsize is not None:
                    win.minsize(1, 1)
                win.update_idletasks()
                content_width = max(
                    header_frame.winfo_reqwidth(),
                    press_area_frame.winfo_reqwidth(),
                    controls_outer_frame.winfo_reqwidth(),
                )
                content_height = (
                    header_frame.winfo_reqheight()
                    + press_area_frame.winfo_reqheight()
                    + controls_outer_frame.winfo_reqheight()
                )
                win.geometry(f"{max(200, content_width + 24)}x{max(200, content_height + 24)}")
                win.update_idletasks()
                try:
                    win.update()
                except Exception:
                    pass
                if time is not None:
                    time.sleep(0.18)
                win.update_idletasks()
                try:
                    win.update()
                except Exception:
                    pass
                if time is not None:
                    time.sleep(0.05)
            except Exception:
                pass

            # capture window contents
            win.update_idletasks()
            try:
                win.update()
            except Exception:
                pass
            x = win.winfo_rootx()
            y = win.winfo_rooty()
            w = win.winfo_width()
            h = win.winfo_height()
            bbox = (x, y, x + w, y + h)
            img = ImageGrab.grab(bbox)

            # target: 11 x 8.5 inches in landscape at 200 DPI
            dpi = 200
            target_w = int(11 * dpi)
            target_h = int(8.5 * dpi)

            img.thumbnail((target_w, target_h), Image.LANCZOS)

            import tempfile, os
            fd, path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            img.save(path, format="PNG")

            # direct print using native Windows print dialog when available
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

                default_printer = None
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
                dialog.grab_set()

                printer_var = tk.StringVar(value=default_printer)
                copies_var = tk.IntVar(value=1)
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
                copies_spin = ttk.Spinbox(dialog, from_=1, to=999, textvariable=copies_var, width=8)
                copies_spin.grid(row=1, column=1, sticky="w", padx=12, pady=4)

                ttk.Label(dialog, text="Orientation:").grid(row=2, column=0, sticky="w", padx=12, pady=4)
                orient_frame = ttk.Frame(dialog)
                orient_frame.grid(row=2, column=1, sticky="w", padx=12, pady=4)
                ttk.Radiobutton(orient_frame, text="Landscape", variable=orientation_var, value="Landscape").pack(side="left")
                ttk.Radiobutton(orient_frame, text="Portrait", variable=orientation_var, value="Portrait").pack(side="left", padx=(12, 0))

                ttk.Label(dialog, text="Margins (inches):").grid(row=3, column=0, sticky="nw", padx=12, pady=4)
                margins_frame = ttk.Frame(dialog)
                margins_frame.grid(row=3, column=1, sticky="w", padx=12, pady=4)
                ttk.Label(margins_frame, text="Left").grid(row=0, column=0, sticky="w")
                ttk.Spinbox(margins_frame, from_=0.0, to=2.0, increment=0.05, textvariable=left_margin_var, width=6).grid(row=0, column=1, padx=(6, 12), pady=2)
                ttk.Label(margins_frame, text="Top").grid(row=0, column=2, sticky="w")
                ttk.Spinbox(margins_frame, from_=0.0, to=2.0, increment=0.05, textvariable=top_margin_var, width=6).grid(row=0, column=3, padx=(6, 0), pady=2)
                ttk.Label(margins_frame, text="Right").grid(row=1, column=0, sticky="w")
                ttk.Spinbox(margins_frame, from_=0.0, to=2.0, increment=0.05, textvariable=right_margin_var, width=6).grid(row=1, column=1, padx=(6, 12), pady=2)
                ttk.Label(margins_frame, text="Bottom").grid(row=1, column=2, sticky="w")
                ttk.Spinbox(margins_frame, from_=0.0, to=2.0, increment=0.05, textvariable=bottom_margin_var, width=6).grid(row=1, column=3, padx=(6, 0), pady=2)

                button_frame = ttk.Frame(dialog)
                button_frame.grid(row=4, column=0, columnspan=2, pady=(8, 12), padx=12, sticky="e")

                def _parse_margin_inches(value, default=0.15):
                    try:
                        return max(0.0, float(str(value).strip()))
                    except Exception:
                        return default

                def _on_print():
                    result["printer"] = printer_var.get()
                    try:
                        val = int(copies_var.get())
                        result["copies"] = max(1, val)
                    except Exception:
                        result["copies"] = 1
                    result["margins_inches"] = {
                        "left": _parse_margin_inches(left_margin_var.get()),
                        "top": _parse_margin_inches(top_margin_var.get()),
                        "right": _parse_margin_inches(right_margin_var.get()),
                        "bottom": _parse_margin_inches(bottom_margin_var.get()),
                    }
                    dialog.destroy()

                def _on_cancel():
                    dialog.destroy()

                ttk.Button(button_frame, text="Print", command=_on_print, width=10).pack(side="left", padx=(0, 8))
                ttk.Button(button_frame, text="Cancel", command=_on_cancel, width=10).pack(side="left")

                dialog.protocol("WM_DELETE_WINDOW", _on_cancel)
                dialog.columnconfigure(1, weight=1)
                win.wait_window(dialog)

                if "printer" not in result:
                    direct_print_error["message"] = "Printer selection was canceled."
                    return None
                return result["printer"], result["copies"], orientation_var.get(), result.get("margins_inches", {"left": 0.15, "top": 0.15, "right": 0.15, "bottom": 0.15})

            def _direct_print(img_path, printer_name, copies, orientation, margins_inches=None):
                try:
                    import win32ui
                    import win32con
                    from PIL import Image, ImageWin
                    import traceback
                except Exception as e:
                    direct_print_error["message"] = f"Missing dependency: {e}"
                    return False

                try:
                    dc = win32ui.CreateDC()
                    dc.CreatePrinterDC(printer_name)
                    img = Image.open(img_path)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    if orientation == 'Landscape':
                        img = img.transpose(Image.ROTATE_90)

                    printable_area = (
                        dc.GetDeviceCaps(win32con.HORZRES),
                        dc.GetDeviceCaps(win32con.VERTRES)
                    )
                    printer_size = (
                        dc.GetDeviceCaps(win32con.PHYSICALWIDTH),
                        dc.GetDeviceCaps(win32con.PHYSICALHEIGHT)
                    )
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

                    ratios = (safe_w / img.size[0], safe_h / img.size[1])
                    scale = min(ratios)
                    scaled = img.resize(
                        (max(1, int(img.size[0] * scale)), max(1, int(img.size[1] * scale))),
                        Image.LANCZOS
                    )
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
                    direct_print_error["message"] = traceback.format_exc()
                    try:
                        dc.DeleteDC()
                    except Exception:
                        pass
                    return False

            printed = False
            if os.name == 'nt':
                try:
                    printer_selection = _show_printer_dialog()
                    if printer_selection:
                        printer_name, copies, orientation, margins_inches = printer_selection
                        printed = _direct_print(path, printer_name, copies, orientation, margins_inches)
                except Exception as e:
                    direct_print_error["message"] = str(e)
                    printed = False

            if not printed:
                if os.name == 'nt' and direct_print_error["message"]:
                    messagebox.showwarning(
                        "Print Failed",
                        f"Direct print failed:\n{direct_print_error['message']}\n\nOpening image preview instead."
                    )
                try:
                    os.startfile(path)
                except Exception:
                    messagebox.showinfo("Print", f"Saved preview to:\n{path}\nPlease open this file and print to your printer in landscape mode.")
        except Exception as e:
            messagebox.showerror("Print Failed", str(e))
        finally:
            # restore button/toggle group visibility
            try:
                if was_btn_visible:
                    btn_frame.pack(side="left")
            except Exception:
                pass
            # restore any Press 1 units that were temporarily hidden for print
            try:
                for frame in hidden_unused_press1_unit_frames:
                    frame.grid()
            except Exception:
                pass
            # restore header sizing / window size after print-only adjustments
            try:
                if original_product_width is not None:
                    product_entry.configure(width=original_product_width)
            except Exception:
                pass
            try:
                if original_imposition_width is not None:
                    imposition_entry.configure(width=original_imposition_width)
            except Exception:
                pass
            try:
                if original_minsize is not None:
                    win.minsize(original_minsize[0], original_minsize[1])
            except Exception:
                pass
            try:
                if original_geometry:
                    win.geometry(original_geometry)
                    win.update_idletasks()
            except Exception:
                pass

    ttk.Button(btn_frame, text="Print", command=lambda: print_layout(win, ctx), width=10, takefocus=False).pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="Save", command=lambda: do_save(win, ctx), width=10, takefocus=False)\
        .pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="Save As", command=lambda: do_save_as(win, ctx), width=10, takefocus=False)\
        .pack(side="left")
    btn_frame.pack(side="left")

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
                entry.bind("<FocusOut>", lambda e, _u=u, _r=r, _c=c: refresh_cell_overlay(_u, _r, _c))
                entry.bind("<KeyRelease>", lambda e, _u=u, _r=r, _c=c: refresh_cell_overlay(_u, _r, _c))

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
