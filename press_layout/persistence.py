from datetime import datetime
from tkinter import filedialog, messagebox

from .config import LAYOUTS_DIR, TEMPLATE_DIR
from .helpers import *

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
        return True
    except Exception as e:
        messagebox.showerror("Save As Failed", str(e))
        return False
