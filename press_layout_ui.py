"""Press Layout UI (final consolidated version)."""

import os
import glob
import json
import calendar
import re
import sys
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image

import press_layout_core as helpers_mod
from press_layout_core import *

SORT_ASCENDING_INDICATOR = " ▲"
SORT_DESCENDING_INDICATOR = " ▼"


def _treeview_sort_heading_text(base_title, sort_state, col):
    active_col = sort_state.get("col")
    if active_col != col:
        return base_title
    return f'{base_title}{SORT_DESCENDING_INDICATOR if sort_state.get("desc") else SORT_ASCENDING_INDICATOR}'

# ===== BEGIN: layout_builder.py =====
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
        "section_count_var": _StaticValue(section_count),
        "section_page_vars": section_page_vars,
        "section_name_vars": section_name_vars,
        "units": units,
        "color_cells": color_cells,
    }


def _build_imposition_text_from_layout_data(data, config=None):
    try:
        ctx = _layout_data_to_headless_ctx(data, config=config, title_base="")
        return build_imposition_text(ctx)
    except Exception:
        pass
    fallback = str((data or {}).get("name") or "").strip()
    if fallback.lower().endswith('.json'):
        fallback = os.path.splitext(fallback)[0]
    return fallback


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
    imposition_text = _build_imposition_text_from_layout_data(data, config=config)

    label_top = header_top
    fallback_title = title_base or ("Template Layout" if template_mode else "Press Layout")
    _render_draw_centered_text(draw, (margin_x, label_top, img_w - margin_x, label_top + 60), product_text or fallback_title, title_font)
    draw.text((margin_x, label_top + 66), f"Issue Date: {issue_text}", fill="black", font=sections_print_font)
    draw.text((img_w - margin_x - 420 - 300, label_top + 66), f"Imposition: {imposition_text}", fill="black", font=text_font)

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
        sw_h = max(28, int(unit_label_h * 1.5))
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

    # template mode disables issue/product
    if template_mode:
        issue_entry.state(["disabled"])
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

    def do_save_with_starter():
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
            "publication": product_entry.get().strip(),
            "issue_date": issue_text,
            "color_pages": (ctx.get("color_pages_var", color_pages_var).get() or "").strip(),
            "plates": (ctx.get("plates_var", plates_var).get() or "").strip(),
            "total_pages": str(total_pages),
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
        margin = 110
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
                return [""], _load_starter_font(max_size, bold=bold)
            for size in range(int(max_size), int(min_size) - 1, -2):
                font = _load_starter_font(size, bold=bold)
                lines = _wrap_lines(content, font, max_width, max_lines=max_lines)
                sizes = [_measure(draw, line, font) for line in lines]
                widths = [w for w, _h in sizes] or [0]
                heights = [h for _w, h in sizes] or [0]
                line_gap = max(10, int(size * 0.18))
                total_h = sum(heights) + line_gap * max(0, len(lines) - 1)
                if max(widths) <= max_width and total_h <= max_height:
                    return lines, font
            font = _load_starter_font(min_size, bold=bold)
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

    def _direct_print_image(img_path, printer_name, copies, orientation="Landscape", margins_inches=None, align_top=False):
        try:
            import win32ui
            import win32con
            import win32print
            from PIL import Image, ImageWin, ImageChops
            import traceback
        except Exception as e:
            raise RuntimeError(f"Missing dependency: {e}")

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
            # On this landscape print path the image is rotated before printing,
            # so a "top-aligned" starter sheet needs to anchor on the leading edge
            # after rotation. That means using the X position for landscape starter
            # alignment instead of only changing Y.
            if align_top and orientation_text == 'Landscape':
                x = int(offset_x + left_margin)
                y = int(offset_y + top_margin + ((safe_h - scaled.size[1]) / 2))
            else:
                x = int(offset_x + left_margin + ((safe_w - scaled.size[0]) / 2))
                y = int(offset_y + top_margin) if align_top else int(offset_y + top_margin + ((safe_h - scaled.size[1]) / 2))

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

    def print_starter_sheet():
        if template_mode:
            return
        format_name = starter_format_var.get().strip() or "Standard"
        try:
            img = _make_starter_sheet_image(format_name, _starter_sheet_fields())
            import tempfile
            fd, path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            img.save(path, format="PNG", dpi=(300, 300))
        except Exception as e:
            messagebox.showerror("Starter Sheet", str(e))
            return
        try:
            printed = False
            error_message = None
            if os.name == 'nt':
                try:
                    selection = _show_print_dialog("Print", default_copies=1)
                    if selection:
                        printer_name, copies = selection
                        printed = _direct_print_image(path, printer_name, copies, orientation="Landscape", align_top=True)
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
        try:
            from PIL import Image, ImageDraw
        except Exception:
            raise RuntimeError("Pillow is required for printing. Please install pillow (pip install pillow).")
        img_w, img_h = 2200, 1940
        img = Image.new("RGB", (img_w, img_h), "white")
        draw = ImageDraw.Draw(img)
        if grid_cols >= 8:
            title_sz, header_sz, text_sz, unit_sz, section_sz, cell_sz = 50, 42, 24, 24, 30, 18
        elif grid_cols >= 4:
            title_sz, header_sz, text_sz, unit_sz, section_sz, cell_sz = 56, 44, 26, 24, 32, 22
        else:
            title_sz, header_sz, text_sz, unit_sz, section_sz, cell_sz = 60, 46, 28, 24, 34, 38
        title_font = _load_starter_font(title_sz, bold=True)
        header_font = _load_starter_font(header_sz, bold=True)
        issue_font = _load_starter_font(header_sz + 4, bold=True)
        text_font = _load_starter_font(text_sz, bold=False)
        small_font = _load_starter_font(max(18, text_sz - 4), bold=False)
        sections_print_font = _load_starter_font(max(36, (max(18, text_sz - 4)) * 2), bold=True)
        unit_font = _load_starter_font(unit_sz, bold=True)
        section_font = _load_starter_font(section_sz, bold=True)
        cell_font_render = _load_starter_font(cell_sz, bold=True)
        color_cell_font_render = _load_starter_font(cell_sz + 2, bold=True)
        legend_font = _load_starter_font(header_sz, bold=True)
        legend_symbol_font = _load_starter_font(header_sz, bold=True)
        legend_list_font = _load_starter_font(header_sz, bold=True)
        margin_x = 55
        header_top = 26
        header_h = 180
        footer_h = 150
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
        section_display_lookup = {}
        for idx in range(count):
            try:
                section_name = (section_name_vars[idx].get() or "").strip().upper()
            except Exception:
                section_name = ""
            if not section_name:
                section_name = chr(ord("A") + idx)
            section_display_lookup[section_name] = idx
        color_page_refs = []
        seen_color_refs = set()
        legend_circle_diameter = 54
        show_bold_color_marks = ((ctx.get("format_name") or "").strip().lower() == "broadsheet")
        # Build section page counts as: Sections: 12 / 16 / 20
        values = []
        total_page_count = 0
        for idx in range(count):
            value = (section_page_vars[idx].get() or "").strip()
            if value:
                values.append(value)
                try:
                    total_page_count += int(value)
                except Exception:
                    pass
        sections_text = " / ".join(values)
        if sections_text:
            draw.text((margin_x, label_top + 118), f"Pages: {sections_text}", fill="black", font=sections_print_font)
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
                    is_color_page = (lab, r, c) in ctx.get("color_cells", set())
                    if value:
                        if is_color_page and show_bold_color_marks:
                            _draw_centered_text_heavy(draw, (cx0 + 2, cy0 + 2, cx1 - 2, cy1 - 2), value, color_cell_font_render, fill="black", offset=1)
                        else:
                            _draw_centered_text(draw, (cx0 + 2, cy0 + 2, cx1 - 2, cy1 - 2), value, cell_font_render)
                    if is_color_page:
                        pad = max(5, int(min(cell_w, cell_h) * 0.11))
                        circle_diameter = max(10, int(min(cell_w, cell_h) - (2 * pad)))
                        legend_circle_diameter = circle_diameter
                        circle_width = 6 if show_bold_color_marks else 3
                        draw.ellipse((cx0 + pad, cy0 + pad, cx1 - pad, cy1 - pad), outline="red", width=circle_width)
                        section_ref = section_text.strip().upper()
                        page_ref = str(value or "").strip()
                        if section_ref and page_ref:
                            ref_text = f"{section_ref}{page_ref}"
                            if ref_text not in seen_color_refs:
                                seen_color_refs.add(ref_text)
                                try:
                                    page_num = int(page_ref)
                                except Exception:
                                    page_num = 10**9
                                color_page_refs.append((section_display_lookup.get(section_ref, 999), section_ref, page_num, ref_text))
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
        footer_line_y = footer_y - 14
        draw.line((margin_x, footer_line_y, img_w - margin_x, footer_line_y), fill="#444444", width=3)
        draw.text((margin_x, footer_y), f"Color Pages: {color_pages_text}", fill="black", font=header_font)
        draw.text((margin_x + 480, footer_y), f"Plates: {plates_text}", fill="black", font=header_font)
        draw.text((margin_x + 900, footer_y), f"Total Pages: {total_page_count}", fill="black", font=header_font)

        # Large legend and color-page list above the footer line.
        legend_circle_diameter = max(42, int(legend_circle_diameter))
        legend_y = footer_line_y - 190
        legend_circle_box = (
            margin_x,
            legend_y,
            margin_x + legend_circle_diameter,
            legend_y + legend_circle_diameter,
        )
        draw.ellipse(legend_circle_box, outline="red", width=6)
        _draw_centered_text_heavy(draw, legend_circle_box, "#", legend_symbol_font, fill="black", offset=1)
        draw.text((margin_x + legend_circle_diameter + 24, legend_y), "= color page", fill="black", font=legend_font)

        color_page_refs_sorted = [item[3] for item in sorted(color_page_refs, key=lambda item: (item[0], item[2], item[3]))]
        refs_text = "Color pages list: " + (", ".join(color_page_refs_sorted) if color_page_refs_sorted else "None")
        list_y = legend_y + legend_circle_diameter + 26
        max_text_width = max(260, img_w - (2 * margin_x))
        wrapped_lines = _wrap_text_to_width(draw, refs_text, legend_list_font, max_text_width)
        line_h = max(44, _measure_text(draw, "Ag", legend_list_font)[1] + 10)
        for line_index, line_text in enumerate(wrapped_lines):
            draw.text((margin_x, list_y + (line_index * line_h)), line_text, fill="black", font=legend_list_font)
        return img

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

    product_entry.bind("<KeyRelease>", lambda e: update_imposition())
    product_entry.bind("<FocusOut>", lambda e: update_imposition())

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
        product_entry.bind("<KeyRelease>", _mark_dirty_event)
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

# ===== END: layout_builder.py =====

# ===== BEGIN: launchers.py =====
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


def _fit_image_to_width(image, max_width):
    try:
        from PIL import Image
    except Exception as e:
        raise RuntimeError(f"Pillow is required for previews: {e}")
    if image is None:
        return None
    try:
        max_width = max(1, int(max_width))
    except Exception:
        return image
    width, height = image.size
    if width <= 0 or height <= 0:
        return image
    if width == max_width:
        return image
    scale = max_width / float(width)
    return image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS)


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


def list_matching_regular_layouts(press_name, format_name):
    rows, _changed = get_cached_regular_rows(force=False)
    return [row for row in rows if row.get("press") == press_name and row.get("format") == format_name]

def _rebuild_layout_cache(entries=None):
    if entries is None:
        entries = _json_dir_entries(LAYOUTS_DIR)
    rows = []
    for item in entries:
        path = item.get("path") or ""
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


def _bind_cache_watcher(win, getter, on_change, interval_ms=1500):
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
    cfg["copy_blank_issue_product"] = bool(copy_blank_issue_product)
    cfg["copy_issue_date_tomorrow"] = bool(copy_issue_date_tomorrow)
    if default_dir:
        cfg["default_dir"] = default_dir
    if prompt_save_template is not None:
        cfg["prompt_save_template"] = bool(prompt_save_template)
    title = f"{press} - {fmt}"
    win = tk.Toplevel(root)
    win.withdraw()
    build_press_layout(
        win,
        title=title,
        config=cfg,
        load_path=json_path,
        load_as_copy=bool(load_as_copy),
    )
    return win


def _resize_preview_image(image, scale=0.75):
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


def _launcher_monitor_rect(launcher):
    try:
        rect = _window_rect(launcher)
    except Exception:
        rect = None
    try:
        monitors = helpers_mod._monitor_rects_win32()
    except Exception:
        monitors = []
    if rect and monitors:
        try:
            monitor = helpers_mod._find_best_monitor_for_rect(rect, monitors)
            if monitor:
                return monitor
        except Exception:
            pass
    try:
        sw = int(launcher.winfo_screenwidth())
        sh = int(launcher.winfo_screenheight())
    except Exception:
        sw, sh = 1920, 1080
    return {"left": 0, "top": 0, "right": sw, "bottom": sh, "primary": True}


def _clamp_preview_position(monitor, x, y, width, height, margin=20):
    left = int(monitor.get("left", 0))
    top = int(monitor.get("top", 0))
    right = int(monitor.get("right", left + width))
    bottom = int(monitor.get("bottom", top + height))
    min_x = left + margin
    min_y = top + margin
    max_x = max(min_x, right - width - margin)
    max_y = max(min_y, bottom - height - margin)
    x = max(min_x, min(int(x), max_x))
    y = max(min_y, min(int(y), max_y))
    return x, y


def _capture_window_image(win):
    try:
        from PIL import ImageGrab
    except Exception as e:
        raise RuntimeError(f"Pillow ImageGrab is required for previews: {e}")

    # Prefer a real screenshot of the actual layout window. This matches the
    # on-screen UI instead of using the print preview rendering path.
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

    rect = _window_rect(win)
    if not rect:
        raise RuntimeError("Could not determine preview window bounds.")
    bbox = (rect["left"], rect["top"], rect["right"], rect["bottom"])

    # Give Tk/Windows a brief moment so the fully rendered layout is visible
    # before the screenshot is taken.
    try:
        win.after(60)
        win.update()
    except Exception:
        pass

    image = None
    try:
        image = ImageGrab.grab(bbox=bbox, all_screens=True)
    except Exception:
        image = None

    # Fallback to PrintWindow when available for a more robust capture on Windows.
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
    cfg["default_dir"] = REGULAR_DIR
    cfg["prompt_save_template"] = False

    win = tk.Toplevel(parent)
    win.withdraw()
    build_press_layout(win, title=f"{press} - {fmt}", config=cfg, load_path=None, load_as_copy=False)


def build_new_layout_launcher(parent):
    root = tk.Toplevel(parent)
    root.title("New Layout")
    root.geometry("1180x760")
    root.minsize(1040, 680)
    remember_window_geometry(root, "new_layout_launcher", default_geometry="1180x760", minsize=(1040, 680))
    _bind_window_size_memory(root, "new_layout_launcher")

    paned = tk.PanedWindow(root, orient="vertical", sashrelief="raised", sashwidth=8, bd=0, showhandle=False)
    paned.pack(fill="both", expand=True)
    frame = ttk.Frame(paned, padding=16)
    paned.add(frame, stretch="always", minsize=220)
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(4, weight=1)

    mode_state = {"regular": False}
    preview_state = {"win": None, "path": None, "after_id": None, "request_id": 0, "photo": None, "pil_image": None}
    launcher_template_sort_state = {"col": None, "desc": False}
    launcher_regular_sort_state = {"col": None, "desc": False}
    template_rows_by_iid = {}
    regular_rows = {}

    mode_bar = ttk.Frame(frame)
    mode_bar.grid(row=0, column=0, columnspan=12, sticky="ew", pady=(0, 8))
    mode_bar.columnconfigure(1, weight=1)
    mode_button = ttk.Button(mode_bar, text="From Regular", width=16)
    mode_button.grid(row=0, column=0, sticky="w")
    mode_note_var = tk.StringVar(value="Guided mode: filter templates, then pick one or create a blank layout from a specific press / format / section setup.")
    ttk.Label(mode_bar, textvariable=mode_note_var).grid(row=0, column=1, sticky="w", padx=(12, 0))

    ttk.Label(frame, text="Press:", font=(None, 11, "bold")).grid(row=1, column=0, sticky="w", pady=8, padx=(0, 8))
    press_var = tk.StringVar(value="All")
    press_combo = ttk.Combobox(frame, textvariable=press_var, values=["All", "Press 1", "Press 2"], state="readonly", width=16)
    press_combo.grid(row=1, column=1, sticky="w", padx=(0, 24))

    ttk.Label(frame, text="Format:", font=(None, 11, "bold")).grid(row=2, column=0, sticky="w", pady=8, padx=(0, 8))
    format_var = tk.StringVar(value="All")
    format_combo = ttk.Combobox(frame, textvariable=format_var, values=["All", "Broadsheet", "Tab", "8 up"], state="readonly", width=16)
    format_combo.grid(row=2, column=1, sticky="w", padx=(0, 24))

    section_frame = ttk.Frame(frame)
    section_frame.grid(row=3, column=0, columnspan=12, sticky="ew")
    ttk.Label(section_frame, text="Sections:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w", pady=8, padx=(0, 8))
    section_count_var = tk.StringVar(value="All")
    section_count_combo = ttk.Combobox(section_frame, textvariable=section_count_var, values=["All", "1", "2", "3", "4"], state="readonly", width=8)
    section_count_combo.grid(row=0, column=1, sticky="w", padx=(0, 24))

    template_container = ttk.Frame(frame)
    template_container.grid(row=4, column=0, columnspan=12, sticky="nsew", pady=(8, 0))
    template_container.columnconfigure(0, weight=1)
    template_container.rowconfigure(2, weight=1)
    ttk.Label(template_container, text="Templates:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="nw")
    template_search_row = ttk.Frame(template_container)
    template_search_row.grid(row=1, column=0, sticky="ew", pady=(6, 8))
    template_search_row.columnconfigure(1, weight=1)
    ttk.Label(template_search_row, text="Search:").grid(row=0, column=0, sticky="w", padx=(0, 8))
    template_search_var = tk.StringVar(value="")
    ttk.Entry(template_search_row, textvariable=template_search_var).grid(row=0, column=1, sticky="ew")
    templates_frame = ttk.Frame(template_container)
    templates_frame.grid(row=2, column=0, sticky="nsew")
    templates_frame.rowconfigure(0, weight=1)
    templates_frame.columnconfigure(0, weight=1)
    template_columns = ("name", "press", "format", "sections", "pages", "saved")
    templates_tree = ttk.Treeview(templates_frame, columns=template_columns, show="headings", selectmode="browse")
    templates_tree.grid(row=0, column=0, sticky="nsew")
    templates_scroll = ttk.Scrollbar(templates_frame, orient="vertical", command=templates_tree.yview)
    templates_scroll.grid(row=0, column=1, sticky="ns")
    templates_tree.configure(yscrollcommand=templates_scroll.set)
    launcher_template_heading_titles = {"name": "Template Name", "press": "Press", "format": "Format", "sections": "Sections", "pages": "Pages", "saved": "Last Saved"}
    for key, title, width, anchor in [("name", launcher_template_heading_titles["name"], 300, "w"), ("press", launcher_template_heading_titles["press"], 90, "center"), ("format", launcher_template_heading_titles["format"], 110, "center"), ("sections", launcher_template_heading_titles["sections"], 80, "center"), ("pages", launcher_template_heading_titles["pages"], 130, "center"), ("saved", launcher_template_heading_titles["saved"], 170, "center")]:
        templates_tree.heading(key, text=title)
        templates_tree.column(key, width=width, anchor=anchor)

    regular_container = ttk.Frame(frame)
    regular_container.columnconfigure(0, weight=1)
    regular_container.rowconfigure(2, weight=1)
    ttk.Label(regular_container, text="Regular Layouts:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="nw")
    regular_search_row = ttk.Frame(regular_container)
    regular_search_row.grid(row=1, column=0, sticky="ew", pady=(6, 8))
    regular_search_row.columnconfigure(1, weight=1)
    ttk.Label(regular_search_row, text="Search:").grid(row=0, column=0, sticky="w", padx=(0, 8))
    regular_search_var = tk.StringVar(value="")
    ttk.Entry(regular_search_row, textvariable=regular_search_var).grid(row=0, column=1, sticky="ew")
    regular_frame = ttk.Frame(regular_container)
    regular_frame.grid(row=2, column=0, sticky="nsew")
    regular_frame.rowconfigure(0, weight=1)
    regular_frame.columnconfigure(0, weight=1)
    regular_columns = ("product", "press", "format", "pages", "color_pages", "plates", "saved")
    regular_tree = ttk.Treeview(regular_frame, columns=regular_columns, show="headings", selectmode="browse")
    regular_tree.grid(row=0, column=0, sticky="nsew")
    regular_scroll = ttk.Scrollbar(regular_frame, orient="vertical", command=regular_tree.yview)
    regular_scroll.grid(row=0, column=1, sticky="ns")
    regular_tree.configure(yscrollcommand=regular_scroll.set)
    launcher_regular_heading_titles = {"product": "Product", "press": "Press", "format": "Format", "pages": "Pages", "color_pages": "Color Pages", "plates": "Plates", "saved": "Last Saved"}
    for key, title, width, anchor in [("product", launcher_regular_heading_titles["product"], 260, "w"), ("press", launcher_regular_heading_titles["press"], 90, "center"), ("format", launcher_regular_heading_titles["format"], 100, "center"), ("pages", launcher_regular_heading_titles["pages"], 120, "center"), ("color_pages", launcher_regular_heading_titles["color_pages"], 95, "center"), ("plates", launcher_regular_heading_titles["plates"], 70, "center"), ("saved", launcher_regular_heading_titles["saved"], 170, "center")]:
        regular_tree.heading(key, text=title)
        regular_tree.column(key, width=width, anchor=anchor)

    btn_row = ttk.Frame(frame)
    btn_row.grid(row=5, column=0, columnspan=12, pady=(12, 0), sticky="w")
    action_button = ttk.Button(btn_row, text="New / Open", width=14)
    action_button.pack(side="left", padx=(0, 8))
    refresh_button = ttk.Button(btn_row, text="Refresh Templates", width=16)
    refresh_button.pack(side="left")

    preview_box = ttk.LabelFrame(paned, text="Preview", padding=8)
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
        return sel[0] if sel else None
    def selected_regular_path():
        sel = regular_tree.selection()
        return sel[0] if sel else None
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
            if not _launcher_is_active():
                return
            if preview_state.get("path") == _path and preview_state.get("photo") is not None:
                return
            close_preview()
            image, _preview_title = open_json_preview(root, _path, template_mode=(not mode_state["regular"]))
            if image is None:
                _clear_preview_panel(preview_label, preview_state, empty_text=current_empty_text())
                return
            _set_preview_panel(preview_label, preview_state, image)
            preview_state["path"] = _path
        preview_state["after_id"] = root.after_idle(_do_show)
    def _active_section_count():
        value = (section_count_var.get() or "All").strip()
        if value == "All":
            return None
        try:
            return max(1, min(4, int(value)))
        except Exception:
            return None
    def update_launcher_template_sort_headings():
        for col in template_columns:
            templates_tree.heading(col, text=_treeview_sort_heading_text(launcher_template_heading_titles[col], launcher_template_sort_state, col), command=lambda _c=col: sort_launcher_templates_by(_c))
    def sort_launcher_template_rows(rows):
        col = launcher_template_sort_state.get("col")
        if not col:
            return rows
        def keyfunc(r):
            if col == "name":
                return ((r.get("name") or "").lower(), r.get("saved_dt") or datetime.min)
            if col == "press":
                return ((r.get("press") or "").lower(), (r.get("name") or "").lower())
            if col == "format":
                return ((r.get("format") or "").lower(), (r.get("name") or "").lower())
            if col == "sections":
                return (int(r.get("section_count") or 0), tuple(r.get("section_pages_sort", (0, 0, 0, 0))), (r.get("name") or "").lower())
            if col == "pages":
                return (tuple(r.get("section_pages_sort", (0, 0, 0, 0))), int(r.get("section_count") or 0), (r.get("name") or "").lower())
            if col == "saved":
                return (r.get("saved_dt") or datetime.min, (r.get("name") or "").lower())
            return ""
        return sorted(rows, key=keyfunc, reverse=launcher_template_sort_state["desc"])
    def sort_launcher_regular_rows(rows):
        col = launcher_regular_sort_state.get("col")
        if not col:
            return rows
        def keyfunc(r):
            if col == "product":
                return ((r.get("product") or "").lower(), tuple(r.get("section_pages_sort", (0, 0, 0, 0))), r.get("saved_dt") or datetime.min)
            if col == "press":
                return (r.get("press") or "").lower()
            if col == "format":
                return (r.get("format") or "").lower()
            if col == "pages":
                return tuple(r.get("section_pages_sort", (0, 0, 0, 0)))
            if col == "color_pages":
                return int(r.get("color_pages", 0) or 0)
            if col == "plates":
                return int(r.get("plates", 0) or 0)
            if col == "saved":
                return r.get("saved_dt") or datetime.min
            return ""
        return sorted(rows, key=keyfunc, reverse=launcher_regular_sort_state["desc"])
    def update_launcher_regular_sort_headings():
        for col in regular_columns:
            regular_tree.heading(col, text=_treeview_sort_heading_text(launcher_regular_heading_titles[col], launcher_regular_sort_state, col), command=lambda _c=col: sort_launcher_regular_by(_c))
    def sort_launcher_templates_by(col):
        if launcher_template_sort_state["col"] == col:
            launcher_template_sort_state["desc"] = not launcher_template_sort_state["desc"]
        else:
            launcher_template_sort_state["col"] = col
            launcher_template_sort_state["desc"] = False
        refresh_templates()
    def sort_launcher_regular_by(col):
        if launcher_regular_sort_state["col"] == col:
            launcher_regular_sort_state["desc"] = not launcher_regular_sort_state["desc"]
        else:
            launcher_regular_sort_state["col"] = col
            launcher_regular_sort_state["desc"] = False
        refresh_regulars()
    def _matches_template_filters(row):
        search_text = (template_search_var.get() or "").strip().lower()
        press_filter = (press_var.get() or "All").strip()
        format_filter = (format_var.get() or "All").strip()
        active_count = _active_section_count()
        if search_text:
            searchable = " ".join([row.get("name", ""), row.get("press", ""), row.get("format", ""), str(row.get("section_count") or ""), row.get("pages_disp", ""), row.get("saved_disp", "")]).lower()
            if search_text not in searchable:
                return False
        if press_filter != "All" and row.get("press", "") != press_filter:
            return False
        if format_filter != "All" and row.get("format", "") != format_filter:
            return False
        if active_count is not None and int(row.get("section_count") or 0) != active_count:
            return False
        return True
    def _matches_regular_filters(row):
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
    def refresh_templates(*_):
        if mode_state["regular"]:
            return
        selected = selected_template_path()
        template_rows_by_iid.clear()
        templates_tree.delete(*templates_tree.get_children())
        cached_rows, _changed = get_cached_templates(force=False)
        rows = []
        for cached in cached_rows:
            if not bool(cached.get("valid", False)):
                continue
            row = {"path": cached.get("path"), "name": cached.get("name") or os.path.splitext(os.path.basename(cached.get("path") or ""))[0], "press": cached.get("press") or "", "format": cached.get("format") or "", "section_count": int(cached.get("section_count") or 0), "section_pages_sort": tuple(([int(v) for v in (cached.get("section_pages") or []) if str(v).strip() != "" and int(v) > 0] + [0, 0, 0, 0])[:4]), "pages_disp": _format_section_pages_for_display({"section_pages": cached.get("section_pages") or [], "section_count": cached.get("section_count") or 0}), "saved_dt": cached.get("saved_dt"), "saved_disp": cached.get("saved_disp") or ""}
            if _matches_template_filters(row):
                rows.append(row)
        rows = sort_launcher_template_rows(rows)
        for row in rows:
            iid = row["path"]
            template_rows_by_iid[iid] = row
            templates_tree.insert("", "end", iid=iid, values=(row.get("name", ""), row.get("press", ""), row.get("format", ""), row.get("section_count", ""), row.get("pages_disp", ""), row.get("saved_disp", "")))
        update_launcher_template_sort_headings()
        if selected and selected in template_rows_by_iid:
            templates_tree.selection_set(selected)
            templates_tree.focus(selected)
        else:
            close_preview()
    def refresh_regulars(*_):
        if not mode_state["regular"]:
            return
        selected = selected_regular_path()
        rows, _changed = get_cached_regular_rows(force=False)
        rows = [row for row in rows if _matches_regular_filters(row)]
        rows = sort_launcher_regular_rows(rows)
        regular_tree.delete(*regular_tree.get_children())
        regular_rows.clear()
        for row in rows:
            iid = row.get("path")
            regular_rows[iid] = row
            regular_tree.insert("", "end", iid=iid, values=(row.get("product", ""), row.get("press", ""), row.get("format", ""), row.get("pages_disp", ""), row.get("color_pages", 0), row.get("plates", 0), row.get("saved_disp", "")))
        update_launcher_regular_sort_headings()
        if selected and selected in regular_rows:
            regular_tree.selection_set(selected)
            regular_tree.focus(selected)
        else:
            close_preview()
    def update_mode_widgets():
        if mode_state["regular"]:
            section_frame.grid_remove()
            template_container.grid_remove()
            regular_container.grid(row=4, column=0, columnspan=12, sticky="nsew", pady=(8, 0))
            action_button.configure(text="Clone Regular")
            refresh_button.configure(text="Refresh Regulars", command=refresh_regulars)
            mode_button.configure(text="Standard Mode")
            mode_note_var.set("Regular mode: filter regular layouts, then clone the selected regular into a new layout dated tomorrow.")
        else:
            regular_container.grid_remove()
            section_frame.grid()
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

    template_search_var.trace_add("write", lambda *_: refresh_templates())
    regular_search_var.trace_add("write", lambda *_: refresh_regulars())
    press_var.trace_add("write", lambda *_: (refresh_templates(), refresh_regulars()))
    format_var.trace_add("write", lambda *_: (refresh_templates(), refresh_regulars()))
    section_count_var.trace_add("write", lambda *_: refresh_templates())
    templates_tree.bind("<<TreeviewSelect>>", lambda e: show_preview(current_preview_path()))
    templates_tree.bind("<Double-Button-1>", lambda e: on_new_or_open())
    regular_tree.bind("<<TreeviewSelect>>", lambda e: show_preview(current_preview_path()))
    regular_tree.bind("<Double-Button-1>", lambda e: on_new_or_open())
    action_button.configure(command=on_new_or_open)
    mode_button.configure(command=toggle_mode)
    update_launcher_template_sort_headings()
    update_launcher_regular_sort_headings()
    template_cache_watcher = _bind_cache_watcher(root, get_cached_templates, lambda: refresh_templates())
    regular_cache_watcher = _bind_cache_watcher(root, get_cached_regular_rows, lambda: refresh_regulars())
    update_mode_widgets()
    root.bind("<FocusIn>", lambda e: show_preview(current_preview_path()), add="+")
    root.bind("<FocusOut>", lambda e: close_preview(), add="+")
    root.protocol("WM_DELETE_WINDOW", lambda: (_persist_bound_preview_panes(root), _cancel_cache_watcher(root, template_cache_watcher), _cancel_cache_watcher(root, regular_cache_watcher), close_preview(), root.destroy()))
    return root
def build_template_editor_launcher(parent):
    root = tk.Toplevel(parent)
    root.title("Template Editor")
    root.geometry("900x700")
    root.minsize(820, 620)
    remember_window_geometry(root, "template_editor_launcher", default_geometry="900x700", minsize=(820, 620))
    _bind_window_size_memory(root, "template_editor_launcher")
    paned = tk.PanedWindow(root, orient="vertical", sashrelief="raised", sashwidth=8, bd=0, showhandle=False)
    paned.pack(fill="both", expand=True)
    frame = ttk.Frame(paned, padding=16)
    paned.add(frame, stretch="always", minsize=220)
    frame.rowconfigure(2, weight=1)
    frame.columnconfigure(0, weight=1)

    filter_frame = ttk.Frame(frame)
    filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    filter_frame.columnconfigure(3, weight=1)
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
    format_combo.grid(row=0, column=5, sticky="w", padx=(8, 0))
    search_var.trace_add("write", lambda *_: refresh())
    press_var.trace_add("write", lambda *_: refresh())
    format_var.trace_add("write", lambda *_: refresh())

    list_frame = ttk.Frame(frame)
    list_frame.grid(row=1, column=0, sticky="nsew")
    list_frame.rowconfigure(0, weight=1)
    list_frame.columnconfigure(0, weight=1)

    columns = ("name", "press", "format", "saved")
    tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
    tree.grid(row=0, column=0, sticky="nsew")
    vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    vsb.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=vsb.set)

    template_heading_titles = {
        "name": "Template Name",
        "press": "Press",
        "format": "Format",
        "saved": "Last Saved",
    }
    for key, title in template_heading_titles.items():
        tree.heading(key, text=title)
    tree.column("name", width=280, anchor="w")
    tree.column("press", width=90, anchor="center")
    tree.column("format", width=120, anchor="center")
    tree.column("saved", width=170, anchor="center")

    template_rows = []
    row_by_iid = {}
    sort_state = {"col": None, "desc": False}
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
            if not _launcher_is_active():
                return
            if preview_state.get("path") == _path and preview_state.get("photo") is not None:
                return
            close_preview()
            image, preview_title = open_json_preview(root, _path, template_mode=True)
            if image is None:
                _clear_preview_panel(preview_label, preview_state, empty_text="Select a template to preview")
                return
            _set_preview_panel(preview_label, preview_state, image)
            preview_state["path"] = _path
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
            if col == "name":
                return (r["name"] or "").lower()
            if col == "press":
                return (r["press"] or "").lower()
            if col == "format":
                return (r["format"] or "").lower()
            if col == "saved":
                return r["saved_dt"] or datetime.min
            return ""

        return sorted(rows, key=keyfunc, reverse=sort_state["desc"])

    def load_rows(rows):
        tree.delete(*tree.get_children())
        row_by_iid.clear()
        for row in rows:
            iid = row["path"]
            tree.insert("", "end", iid=iid, values=(row["name"], row["press"], row["format"], row["saved_disp"]))
            row_by_iid[iid] = row

    def _matches_template_filter(row):
        search_text = (search_var.get() or "").strip().lower()
        press_filter = (press_var.get() or "All").strip()
        format_filter = (format_var.get() or "All").strip()
        if search_text:
            searchable = " ".join([row.get("name", ""), row.get("press", ""), row.get("format", "")]).lower()
            if search_text not in searchable:
                return False
        if press_filter != "All" and row.get("press", "") != press_filter:
            return False
        if format_filter != "All" and row.get("format", "") != format_filter:
            return False
        return True

    def update_sort_headings():
        tree.heading("name", text=_treeview_sort_heading_text(template_heading_titles["name"], sort_state, "name"), command=lambda: sort_by("name"))
        tree.heading("press", text=_treeview_sort_heading_text(template_heading_titles["press"], sort_state, "press"), command=lambda: sort_by("press"))
        tree.heading("format", text=_treeview_sort_heading_text(template_heading_titles["format"], sort_state, "format"), command=lambda: sort_by("format"))
        tree.heading("saved", text=_treeview_sort_heading_text(template_heading_titles["saved"], sort_state, "saved"), command=lambda: sort_by("saved"))

    def refresh():
        template_rows.clear()
        cached_rows, _changed = get_cached_templates(force=False)
        for cached in cached_rows:
            row = {
                "path": cached.get("path"),
                "name": cached.get("name") or os.path.splitext(os.path.basename(cached.get("path") or ""))[0],
                "press": cached.get("press") or "",
                "format": cached.get("format") or "",
                "saved_dt": cached.get("saved_dt"),
                "saved_disp": cached.get("saved_disp") or "",
            }
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
        refresh()

    update_sort_headings()

    def selected_path():
        sel = tree.selection()
        return sel[0] if sel else None

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

    tree.bind("<<TreeviewSelect>>", lambda e: show_preview(selected_path()))
    tree.bind("<Double-Button-1>", lambda e: open_selected())
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
    ttk.Button(right_btns, text="Regen Preview", command=regenerate_selected_preview, width=14).pack(side="right", padx=(0, 8))
    preview_box = ttk.LabelFrame(paned, text="Preview", padding=8)
    preview_box.columnconfigure(0, weight=1)
    preview_label = ttk.Label(preview_box, text="Select a template to preview", anchor="center", justify="center")
    preview_label.grid(row=0, column=0, sticky="nsew")
    preview_box.rowconfigure(0, weight=1)
    preview_label.bind("<Configure>", lambda e: _render_preview_panel_image(preview_label, preview_state), add="+")
    paned.add(preview_box, minsize=160)
    _bind_preview_pane_memory(root, "template_editor_launcher", paned, preview_box, default_height=240)
    refresh()
    template_cache_watcher = _bind_cache_watcher(root, get_cached_templates, lambda: refresh())
    root.bind("<FocusIn>", _on_launcher_focus_in, add="+")
    root.bind("<FocusOut>", _on_launcher_focus_out, add="+")
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


def _load_layout_color_and_plate_counts(path):
    data = safe_read_json(path) or {}
    return _layout_color_and_plate_counts_from_data(data)



def build_regular_editor_launcher(parent):
    root = tk.Toplevel(parent)
    root.title("Regular Editor")
    root.geometry("980x720")
    root.minsize(900, 640)
    remember_window_geometry(root, "regular_editor_launcher", default_geometry="980x720", minsize=(900, 640))
    _bind_window_size_memory(root, "regular_editor_launcher")

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
    columns = ("product", "press", "format", "pages", "color_pages", "plates", "saved")
    tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
    tree.grid(row=0, column=0, sticky="nsew")
    vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    vsb.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=vsb.set)
    regular_heading_titles = {
        "product": "Product",
        "press": "Press",
        "format": "Format",
        "pages": "Pages",
        "color_pages": "Color Pages",
        "plates": "Plates",
        "saved": "Last Saved",
    }
    for key, title, width, anchor in [("product", regular_heading_titles["product"], 260, "w"), ("press", regular_heading_titles["press"], 90, "center"), ("format", regular_heading_titles["format"], 100, "center"), ("pages", regular_heading_titles["pages"], 120, "center"), ("color_pages", regular_heading_titles["color_pages"], 95, "center"), ("plates", regular_heading_titles["plates"], 70, "center"), ("saved", regular_heading_titles["saved"], 170, "center")]:
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor=anchor)

    sort_state = {"col": None, "desc": False}
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
        return sel[0] if sel else None
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
            image, _pt = open_json_preview(root, _path, template_mode=False)
            if image is None:
                close_preview()
                return
            _set_preview_panel(preview_label, preview_state, image)
            preview_state["path"] = _path
        preview_state["after_id"] = root.after_idle(_do_show)
    def sort_rows(rows):
        col = sort_state.get("col")
        if not col:
            return rows
        def keyfunc(r):
            if col == "product":
                return (r.get("product") or "").lower()
            if col == "press":
                return (r.get("press") or "").lower()
            if col == "format":
                return (r.get("format") or "").lower()
            if col == "pages":
                return tuple(r.get("section_pages_sort", (0,0,0,0)))
            if col == "color_pages":
                return int(r.get("color_pages", 0) or 0)
            if col == "plates":
                return int(r.get("plates", 0) or 0)
            if col == "saved":
                return r.get("saved_dt") or datetime.min
            return ""
        return sorted(rows, key=keyfunc, reverse=sort_state["desc"])
    def matches(row):
        search_text = (search_var.get() or "").strip().lower()
        if search_text:
            hay = " ".join([row.get("product", ""), row.get("press", ""), row.get("format", ""), row.get("pages_disp", ""), str(row.get("color_pages", "")), str(row.get("plates", ""))]).lower()
            if search_text not in hay:
                return False
        if (press_var.get() or "All") != "All" and row.get("press") != press_var.get():
            return False
        if (format_var.get() or "All") != "All" and row.get("format") != format_var.get():
            return False
        return True
    def update_sort_headings():
        for col in columns:
            tree.heading(col, text=_treeview_sort_heading_text(regular_heading_titles[col], sort_state, col), command=lambda _c=col: sort_by(_c))

    def refresh():
        rows, _changed = get_cached_regular_rows(force=False)
        rows = sort_rows([row for row in rows if matches(row)])
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", iid=row["path"], values=(row.get("product", ""), row.get("press", ""), row.get("format", ""), row.get("pages_disp", ""), row.get("color_pages", 0), row.get("plates", 0), row.get("saved_disp", "")))
        update_sort_headings()
    def sort_by(col):
        if sort_state["col"] == col:
            sort_state["desc"] = not sort_state["desc"]
        else:
            sort_state["col"] = col
            sort_state["desc"] = False
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
    tree.bind("<<TreeviewSelect>>", lambda e: show_preview(selected_path()))
    tree.bind("<Double-Button-1>", lambda e: open_selected())
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
    ttk.Button(right, text="Regen Preview", command=regenerate_selected_preview, width=14).pack(side="right", padx=(0, 8))
    preview_box = ttk.LabelFrame(paned, text="Preview", padding=8)
    preview_box.columnconfigure(0, weight=1)
    preview_label = ttk.Label(preview_box, text="Select a regular layout to preview", anchor="center", justify="center")
    preview_label.grid(row=0, column=0, sticky="nsew")
    preview_box.rowconfigure(0, weight=1)
    preview_label.bind("<Configure>", lambda e: _render_preview_panel_image(preview_label, preview_state), add="+")
    paned.add(preview_box, minsize=160)
    _bind_preview_pane_memory(root, "regular_editor_launcher", paned, preview_box, default_height=240)
    refresh()
    regular_cache_watcher = _bind_cache_watcher(root, get_cached_regular_rows, lambda: refresh())
    root.protocol("WM_DELETE_WINDOW", lambda: (_persist_bound_preview_panes(root), _cancel_cache_watcher(root, regular_cache_watcher), close_preview(), root.destroy()))
    return root


CHANGELOG_PATH = os.path.join(MAIN_DIR, "changelog.json")
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

def restart_press_layout_program(root=None):
    python_executable = sys.executable or "python"
    if getattr(sys, "frozen", False):
        restart_args = [python_executable]
    else:
        script_path = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else os.path.join(MAIN_DIR, "press_layout_entry.py")
        restart_args = [python_executable, script_path]
        if len(sys.argv) > 1:
            restart_args.extend(sys.argv[1:])
    try:
        os.chdir(MAIN_DIR)
    except Exception:
        pass
    if root is not None:
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
    os.execv(python_executable, restart_args)

def show_restart_required_dialog(parent, running_version, latest_version):
    existing = getattr(parent, "_restart_required_dialog", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return existing
    except Exception:
        pass

    dialog = tk.Toplevel(parent)
    parent._restart_required_dialog = dialog
    dialog.title("Update Available")
    try:
        dialog.transient(parent)
    except Exception:
        pass
    try:
        dialog.grab_set()
    except Exception:
        pass
    dialog.resizable(False, False)
    remember_window_geometry(dialog, "restart_required_dialog", default_geometry="520x220", minsize=(520, 220))

    body = ttk.Frame(dialog, padding=16)
    body.pack(fill="both", expand=True)
    body.columnconfigure(0, weight=1)

    ttk.Label(body, text="A newer version of Press Layouts is available.", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")
    message = (
        f"You are using {_format_version_label(running_version)}, but {_format_version_label(latest_version)} is now available.\n\n"
        "Please save your work and restart the program to load the latest version."
    )
    ttk.Label(body, text=message, justify="left", wraplength=460).grid(row=1, column=0, sticky="w", pady=(10, 0))

    button_row = ttk.Frame(body)
    button_row.grid(row=2, column=0, sticky="e", pady=(18, 0))

    def _close_dialog():
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
        _close_dialog()
        try:
            restart_press_layout_program(parent)
        except Exception as exc:
            messagebox.showerror("Restart Failed", f"Could not restart Press Layouts.\n\n{exc}")

    ttk.Button(button_row, text="Restart", command=_restart_now, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(button_row, text="Cancel", command=_close_dialog, width=12).pack(side="left")

    dialog.protocol("WM_DELETE_WINDOW", _close_dialog)
    dialog.bind("<Escape>", lambda _event: _close_dialog())
    try:
        dialog.lift()
        dialog.focus_force()
    except Exception:
        pass
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

def populate_changelog_tree(tree, changelog_data=None):
    data = changelog_data if isinstance(changelog_data, dict) else load_changelog_data()
    versions = get_changelog_versions(data)
    tree.delete(*tree.get_children())
    _configure_changelog_tree_tags(tree)
    if not versions:
        tree.insert("", "end", text="No changelog entries found.", tags=("summary",))
        return
    for index, entry in enumerate(versions):
        version_label = str(entry.get("version") or "").strip() or "0.0.0"
        if not version_label.lower().startswith("v"):
            version_label = f"v{version_label}"
        released = str(entry.get("released") or "").strip()
        summary = str(entry.get("summary") or "").strip()
        version_text = f"Press Layouts {version_label}"
        if released:
            version_text += f"  •  {released}"
        version_id = tree.insert("", "end", text=version_text, open=(index == 0), tags=("version",))
        if summary:
            tree.insert(version_id, "end", text=summary, tags=("summary",))
        for section in _normalize_change_sections(entry):
            title = section.get("title") or "Changes"
            items = section.get("items") or []
            category_tag = _category_tag_name(title)
            item_tag = _item_tag_name(title)
            color = _category_color(title)
            tree.tag_configure(category_tag, foreground=color, font=(None, 10, "bold"))
            tree.tag_configure(item_tag, foreground=color)
            category_id = tree.insert(version_id, "end", text=title, open=True, tags=(category_tag,))
            for item in items:
                tree.insert(category_id, "end", text=item, tags=("item", item_tag))

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

def build_main_launcher():  
    ensure_dir(LAYOUTS_DIR)  
    ensure_dir(TEMPLATE_DIR)  
    ensure_dir(REGULAR_DIR)  
    root = tk.Tk()  
    root.title("Press Layouts")  
    root.geometry("1100x760")  
    root.minsize(980, 680)  
    remember_window_geometry(root, "main_launcher", default_geometry="1100x760", minsize=(980, 680))
    _bind_window_size_memory(root, "main_launcher")  
    ttk.Style(root).configure("LauncherVersion.TLabel", foreground="#1a73e8")
    paned = tk.PanedWindow(root, orient="vertical", sashrelief="raised", sashwidth=8, bd=0, showhandle=False)
    paned.pack(fill="both", expand=True)
    frame = ttk.Frame(paned, padding=16)
    paned.add(frame, stretch="always", minsize=220)
    frame.rowconfigure(2, weight=1)
    frame.columnconfigure(0, weight=1)
    ttk.Label(frame, text="Layouts:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")
    changelog_data = load_changelog_data()
    running_version = _get_changelog_current_version_value(changelog_data)
    version_check_job = {"id": None}
    version_label_var = tk.StringVar(value=_format_version_label(running_version))
    version_label = ttk.Label(frame, textvariable=version_label_var, style="LauncherVersion.TLabel", font=(None, 10))
    version_label.grid(row=0, column=0, sticky="e")
    version_label.configure(cursor="hand2")
    version_label.bind("<Button-1>", lambda _event: show_changelog_dialog(root))
    filter_frame = ttk.Frame(frame)
    filter_frame.grid(row=1, column=0, sticky="ew", pady=(8, 8))
    filter_frame.columnconfigure(5, weight=1)
    ttk.Label(filter_frame, text="Search:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")
    search_var = tk.StringVar(value="")
    search_entry = ttk.Entry(filter_frame, textvariable=search_var)
    search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 12))
    ttk.Label(filter_frame, text="Press:", font=(None, 11, "bold")).grid(row=0, column=2, sticky="w")
    press_var = tk.StringVar(value="All")
    press_combo = ttk.Combobox(filter_frame, textvariable=press_var, values=["All", "Press 1", "Press 2"], state="readonly", width=12)
    press_combo.grid(row=0, column=3, sticky="w", padx=(8, 12))
    ttk.Label(filter_frame, text="Format:", font=(None, 11, "bold")).grid(row=0, column=4, sticky="w")
    format_var = tk.StringVar(value="All")
    format_combo = ttk.Combobox(filter_frame, textvariable=format_var, values=["All", "Broadsheet", "Tab", "8 up"], state="readonly", width=12)
    format_combo.grid(row=0, column=5, sticky="w", padx=(8, 12))
    ttk.Label(filter_frame, text="Issue Date:", font=(None, 11, "bold")).grid(row=0, column=6, sticky="w")
    issue_date_var = tk.StringVar(value="All")
    issue_date_combo = ttk.Combobox(filter_frame, textvariable=issue_date_var, values=["All"], state="readonly", width=16)
    issue_date_combo.grid(row=0, column=7, sticky="w", padx=(8, 0))

    columns = ("issue", "product", "press", "format", "pages", "color_pages", "plates", "saved")
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
    tree.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    vsb.grid(row=2, column=1, sticky="ns", pady=(0, 0))
    tree.configure(yscrollcommand=vsb.set)  
    recent_heading_titles = {
        "issue": "Issue Date",
        "product": "Product",
        "press": "Press",
        "format": "Format",
        "pages": "Pages",
        "color_pages": "Color Pages",
        "plates": "Plates",
        "saved": "Last Saved",
    }
    for key, title in recent_heading_titles.items():
        tree.heading(key, text=title)
    tree.column("issue", width=110, anchor="center")  
    tree.column("product", width=260, anchor="w")  
    tree.column("press", width=90, anchor="center")  
    tree.column("format", width=100, anchor="center")  
    tree.column("pages", width=120, anchor="center")  
    tree.column("color_pages", width=95, anchor="center")  
    tree.column("plates", width=70, anchor="center")  
    tree.column("saved", width=170, anchor="center")  
    row_by_iid = {}  
    sort_state = {"col": None, "desc": False}  
    refresh_job = {"id": None}  
    auto_refresh_ms = 5000    
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
            if not _launcher_is_active():
                return
            if preview_state.get("path") == _path and preview_state.get("photo") is not None:
                return
            close_preview()
            image, preview_title = open_json_preview(root, _path, template_mode=False)
            if image is None:
                _clear_preview_panel(preview_label, preview_state, empty_text="Select a layout to preview")
                return
            _set_preview_panel(preview_label, preview_state, image)
            preview_state["path"] = _path
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
            if col == "pages":
                return tuple(r.get("section_pages_sort", (0, 0, 0, 0)))
            if col == "color_pages":
                return int(r.get("color_pages", 0) or 0)
            if col == "plates":
                return int(r.get("plates", 0) or 0)
            return ""  
        return sorted(rows, key=keyfunc, reverse=sort_state["desc"])  
    def load_rows_into_tree(rows, preserve_selection=None, preserve_focus=None, preserve_yview=None):  
        tree.delete(*tree.get_children())  
        row_by_iid.clear()  
        for r in rows:  
            iid = r["path"]  
            tree.insert("", "end", iid=iid, values=(  
                r["issue_disp"],  
                r["product"],  
                r["press"],  
                r["format"],  
                r.get("pages_disp", ""),
                r.get("color_pages", 0),
                r.get("plates", 0),
                r["saved_disp"],  
            ))  
            row_by_iid[iid] = r  
        if preserve_selection:  
            existing = [iid for iid in preserve_selection if iid in row_by_iid]  
            if existing:  
                tree.selection_set(existing)  
        if preserve_focus and preserve_focus in row_by_iid:  
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
        if search_text:
            searchable = " ".join([
                row.get("issue_disp", ""),
                row.get("product", ""),
                row.get("press", ""),
                row.get("format", ""),
                row.get("pages_disp", ""),
                str(row.get("color_pages", "")),
                str(row.get("plates", "")),
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

    def _matches_layout_filter_no_issue(row):
        search_text = (search_var.get() or "").strip().lower()
        press_filter = (press_var.get() or "All").strip()
        format_filter = (format_var.get() or "All").strip()
        if search_text:
            searchable = " ".join([
                row.get("issue_disp", ""),
                row.get("product", ""),
                row.get("press", ""),
                row.get("format", ""),
                row.get("pages_disp", ""),
                str(row.get("color_pages", "")),
                str(row.get("plates", "")),
            ]).lower()
            if search_text not in searchable:
                return False
        if press_filter != "All" and row.get("press", "") != press_filter:
            return False
        if format_filter != "All" and row.get("format", "") != format_filter:
            return False
        return True

    def update_sort_headings():
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
    def auto_refresh_tick():  
        refresh_job["id"] = None  
        try:  
            refresh(preserve_state=True)  
        finally:  
            if root.winfo_exists():  
                schedule_refresh()  
    def sort_by(col):
        if sort_state["col"] == col:
            sort_state["desc"] = not sort_state["desc"]
        else:
            sort_state["col"] = col
            sort_state["desc"] = False
        refresh(preserve_state=True)
    update_sort_headings()
    search_var.trace_add("write", lambda *_: refresh(preserve_state=False))
    press_var.trace_add("write", lambda *_: refresh(preserve_state=False))
    format_var.trace_add("write", lambda *_: refresh(preserve_state=False))
    issue_date_var.trace_add("write", lambda *_: refresh(preserve_state=False))
    def selected_path():  
        sel = tree.selection()  
        return sel[0] if sel else None  
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
            copy_blank_issue_product=True,
        )

    def new_layout():
        close_preview()
        build_new_layout_launcher(root)

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
            text="All layouts are shown below. Layouts with an issue date of today or earlier are pre-selected for deletion (double-click a row to keep/remove it from deletion):",  
            font=(None, 10, "bold")  
        ).grid(row=0, column=0, sticky="w")  
        cleanup_columns = ("delete", "issue", "product", "press", "format", "saved")  
        cleanup_tree = ttk.Treeview(outer, columns=cleanup_columns, show="headings", selectmode="browse")  
        cleanup_tree.grid(row=1, column=0, sticky="nsew", pady=(8, 0))  
        cleanup_vsb = ttk.Scrollbar(outer, orient="vertical", command=cleanup_tree.yview)  
        cleanup_vsb.grid(row=1, column=1, sticky="ns", pady=(8, 0))  
        cleanup_tree.configure(yscrollcommand=cleanup_vsb.set)  
        cleanup_tree.heading("delete", text="Delete")  
        cleanup_tree.heading("issue", text="Issue Date")  
        cleanup_tree.heading("product", text="Product")  
        cleanup_tree.heading("press", text="Press")  
        cleanup_tree.heading("format", text="Format")  
        cleanup_tree.heading("saved", text="Last Saved")  
        cleanup_tree.column("delete", width=70, anchor="center")  
        cleanup_tree.column("issue", width=110, anchor="center")  
        cleanup_tree.column("product", width=280, anchor="w")  
        cleanup_tree.column("press", width=90, anchor="center")  
        cleanup_tree.column("format", width=120, anchor="center")  
        cleanup_tree.column("saved", width=170, anchor="center")  
        delete_state = {  
            row["path"]: bool(row.get("issue_dt") and row.get("issue_dt").date() <= today)  
            for row in all_rows  
        }  
        def checkbox_value(path):  
            return "☑" if delete_state.get(path, False) else "☐"  
        def populate_cleanup_tree():  
            cleanup_tree.delete(*cleanup_tree.get_children())  
            for row in all_rows:  
                path = row["path"]  
                cleanup_tree.insert("", "end", iid=path, values=(  
                    checkbox_value(path),  
                    row["issue_disp"],  
                    row["product"],  
                    row["press"],  
                    row["format"],  
                    row["saved_disp"],  
                ))  
        def toggle_cleanup_item(path):  
            if not path or path not in delete_state:  
                return  
            delete_state[path] = not delete_state[path]  
            row = cleanup_tree.item(path, "values")  
            if row:  
                cleanup_tree.item(path, values=(checkbox_value(path),) + tuple(row[1:]))  
            cleanup_tree.selection_set(path)  
            cleanup_tree.focus(path)  
        def toggle_from_event(event=None):  
            path = cleanup_tree.identify_row(event.y) if event is not None else cleanup_tree.focus()  
            toggle_cleanup_item(path)  
            return "break"  
        cleanup_tree.bind("<Double-Button-1>", toggle_from_event)  
        cleanup_tree.bind("<space>", toggle_from_event)  
        populate_cleanup_tree()  
        status_var = tk.StringVar(value="Ready.")
        ttk.Label(outer, textvariable=status_var, foreground="#555555").grid(row=2, column=0, sticky="w", pady=(12, 0))
        btns = ttk.Frame(outer)  
        btns.grid(row=3, column=0, pady=(12, 0), sticky="e")  

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

        def regen_all_previews_cleanup():
            jobs = []
            layout_rows, _changed = get_cached_layout_rows(force=False)
            for row in layout_rows:
                jobs.append({
                    "label": os.path.basename(row["path"]),
                    "path": row["path"],
                    "template_mode": False,
                    "default_dir": None,
                    "prompt_save_template": None,
                })
            for _name, path in list_json_files(TEMPLATE_DIR):
                jobs.append({
                    "label": os.path.basename(path),
                    "path": path,
                    "template_mode": True,
                    "default_dir": None,
                    "prompt_save_template": None,
                })
            for _name, path in list_json_files(REGULAR_DIR):
                jobs.append({
                    "label": os.path.basename(path),
                    "path": path,
                    "template_mode": False,
                    "default_dir": REGULAR_DIR,
                    "prompt_save_template": False,
                })
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
            for path in to_delete:  
                try:  
                    remove_preview_image_for_json(path)
                    os.remove(path)  
                except Exception as exc:  
                    errors.append(f"{os.path.basename(path)}: {exc}")  
            refresh(preserve_state=False)  
            if errors:  
                messagebox.showerror(  
                    "Cleanup",  
                    "Some files could not be deleted:\n\n" + "\n".join(errors),  
                    parent=dialog,  
                )  
            dialog.destroy()  
        ttk.Button(btns, text="Regen ALL Previews", command=regen_all_previews_cleanup, width=18).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Delete", command=delete_selected_cleanup, width=12).pack(side="left", padx=(0, 8))  
        ttk.Button(btns, text="Cancel", command=dialog.destroy, width=12).pack(side="left")  

    tree.bind("<<TreeviewSelect>>", lambda e: show_preview(selected_path()))
    tree.bind("<Double-Button-1>", lambda e: open_selected())
    btns = ttk.Frame(frame)
    btns.grid(row=3, column=0, columnspan=2, pady=12, sticky="ew")
    btns.columnconfigure(0, weight=1)
    left_btns = ttk.Frame(btns)
    left_btns.grid(row=0, column=0, sticky="w")
    right_btns = ttk.Frame(btns)
    right_btns.grid(row=0, column=1, sticky="e")
    ttk.Button(left_btns, text="New", command=new_layout, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(left_btns, text="Open", command=open_selected, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(left_btns, text="Clone", command=clone_selected, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(right_btns, text="Regulars", command=regulars, width=12).pack(side="right", padx=(0, 8))
    ttk.Button(right_btns, text="Templates", command=templates, width=12).pack(side="right", padx=(0, 8))
    ttk.Button(right_btns, text="Delete", command=delete_selected, width=12).pack(side="right", padx=(0, 8))
    ttk.Button(right_btns, text="Cleanup", command=cleanup_old_layouts, width=12).pack(side="right", padx=(0, 8))
    ttk.Button(right_btns, text="Regen Preview", command=regenerate_selected_preview, width=14).pack(side="right", padx=(0, 8))
    preview_box = ttk.LabelFrame(paned, text="Preview", padding=8)
    preview_box.columnconfigure(0, weight=1)
    preview_label = ttk.Label(preview_box, text="Select a layout to preview", anchor="center", justify="center")
    preview_label.grid(row=0, column=0, sticky="nsew")
    preview_box.rowconfigure(0, weight=1)
    preview_label.bind("<Configure>", lambda e: _render_preview_panel_image(preview_label, preview_state), add="+")
    paned.add(preview_box, minsize=160)
    _bind_preview_pane_memory(root, "main_launcher", paned, preview_box, default_height=240)
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
        root.destroy()  
    root.bind("<FocusIn>", _on_launcher_focus_in, add="+")
    root.bind("<FocusOut>", _on_launcher_focus_out, add="+")
    root.protocol("WM_DELETE_WINDOW", on_close)  
    refresh(preserve_state=False)  
    schedule_refresh()  
    schedule_version_check()
    root.mainloop()

# ===== END: launchers.py =====