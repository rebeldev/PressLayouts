import os
import glob
from datetime import datetime
from tkinter import filedialog, messagebox

from .config import LAYOUTS_DIR, TEMPLATE_DIR
from .helpers import *


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
        "section_names": [],
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
        # collect section names if available
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
        if ctx.get("template_mode", False):
            data = _normalize_template_data(data)
        safe_write_json(ctx["file_path"], data)
        
        # If saving a layout (not template mode) and imposition doesn't match existing template, ask to save as template
        if not ctx.get("template_mode", False):
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
        ctx["file_path"] = path
        ctx["layout_name"] = data["name"]
        win.title(f"{ctx['title_base']}  —  {os.path.basename(path)}")
        
        # If saving a layout (not template mode) and imposition doesn't match existing template, ask to save as template
        if not ctx.get("template_mode", False):
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

def _template_exists_for_imposition(ctx) -> bool:
    """Check if a template with the same imposition already exists."""
    ensure_dir(TEMPLATE_DIR)
    press = ctx.get("press_name", "")
    fmt = ctx.get("format_name", "")
    
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
            pages.append(min_pages_for_format(fmt))
    
    # List all templates and check for matching imposition
    template_files = sorted(glob.glob(os.path.join(TEMPLATE_DIR, "*.json")))
    for tmpl_path in template_files:
        tmpl_data = safe_read_json(tmpl_path)
        if not isinstance(tmpl_data, dict):
            continue
        
        # Check press, format, section_count, section_pages
        if tmpl_data.get("press") != press or tmpl_data.get("format") != fmt:
            continue
        if tmpl_data.get("section_count") != section_count:
            continue
        if tmpl_data.get("section_pages") != pages:
            continue
        
        # Check units match
        tmpl_units = tmpl_data.get("units", [])
        ctx_units = ctx.get("units", [])
        
        if len(tmpl_units) != len(ctx_units):
            continue
        
        # Compare unit structure
        units_match = True
        for tu, cu in zip(tmpl_units, ctx_units):
            tu_grid = tu.get("grid", [])
            cu_grid = [
                [cell.get().strip() for cell in row]
                for row in cu.get("entries", [])
            ]
            if tu_grid != cu_grid:
                units_match = False
                break
        
        if units_match:
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
        messagebox.showinfo("Template Saved", f"Template saved as:\n{template_filename}")
    except Exception as e:
        messagebox.showerror("Save Template Failed", f"Could not save template:\n{str(e)}")

