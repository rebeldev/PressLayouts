import os  
import glob  
import json
import re
import tkinter as tk  
from tkinter import ttk, messagebox  
from .config import *  
from .helpers import *  
from . import helpers as helpers_mod
from .layout_builder import build_press_layout  
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


def _apply_saved_preview_pane_height(win, state_key, paned, preview_box, default_height=240, min_height=160):
    def _apply():
        try:
            win.update_idletasks()
            total_h = max(1, int(paned.winfo_height()))
            data = _load_window_size_state().get(state_key, {})
            target = int(data.get("preview_height", default_height))
            target = max(min_height, min(target, max(min_height, total_h - 120)))
            sash_y = max(80, total_h - target)
            paned.sash_place(0, 0, sash_y)
        except Exception:
            pass
    try:
        win.after_idle(_apply)
    except Exception:
        _apply()


def _bind_preview_pane_memory(win, state_key, paned, preview_box, default_height=240):
    _apply_saved_preview_pane_height(win, state_key, paned, preview_box, default_height=default_height)
    pending = {"id": None}

    def _persist_preview_height():
        pending["id"] = None
        try:
            height = int(preview_box.winfo_height())
        except Exception:
            return
        if height <= 1:
            return
        data = _load_window_size_state()
        entry = data.get(state_key)
        if not isinstance(entry, dict):
            entry = {}
            data[state_key] = entry
        entry["preview_height"] = height
        _save_window_size_state(data)

    def _schedule(event=None):
        try:
            if pending["id"] is not None:
                win.after_cancel(pending["id"])
        except Exception:
            pass
        try:
            pending["id"] = win.after(150, _persist_preview_height)
        except Exception:
            pass

    try:
        preview_box.bind("<Configure>", _schedule, add="+")
        paned.bind("<ButtonRelease-1>", _schedule, add="+")
    except Exception:
        pass


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
    win.withdraw()
    build_press_layout(
        win,
        title=title,
        config=cfg,
        load_path=json_path,
        load_as_copy=False,
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


def _position_window_on_launcher_monitor(win, launcher, x_offset=32, y_offset=32):
    monitor = _launcher_monitor_rect(launcher)
    try:
        root_rect = _window_rect(launcher) or {
            "left": int(monitor.get("left", 0)),
            "top": int(monitor.get("top", 0)),
            "right": int(monitor.get("left", 0)) + 800,
            "bottom": int(monitor.get("top", 0)) + 600,
        }
        win.update_idletasks()
        width = max(1, int(win.winfo_reqwidth() or win.winfo_width() or 800))
        height = max(1, int(win.winfo_reqheight() or win.winfo_height() or 600))
        x = root_rect["left"] + x_offset
        y = root_rect["top"] + y_offset
        x, y = _clamp_preview_position(monitor, x, y, width, height)
        win.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass
    return monitor


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


def _create_image_preview_window(root, image, title, launcher):
    try:
        from PIL import ImageTk
    except Exception as e:
        raise RuntimeError(f"Pillow is required for previews: {e}")
    preview = tk.Toplevel(root)
    preview.title(title)
    try:
        preview.transient(root)
    except Exception:
        pass
    try:
        preview.bind("<Escape>", lambda e: preview.destroy(), add="+")
    except Exception:
        pass
    outer = ttk.Frame(preview, padding=8)
    outer.pack(fill="both", expand=True)
    label = ttk.Label(outer)
    label.pack(fill="both", expand=True)
    photo = ImageTk.PhotoImage(image)
    label.configure(image=photo)
    label.image = photo
    preview._preview_photo = photo
    try:
        width, height = image.size
        preview.geometry(f"{max(320, width + 24)}x{max(220, height + 24)}")
        monitor = _launcher_monitor_rect(launcher)
        launcher_rect = _window_rect(launcher) or monitor
        # Prefer to open to the right of the launcher, but clamp to the same monitor.
        x = launcher_rect["right"] + 16
        y = launcher_rect["top"]
        x, y = _clamp_preview_position(monitor, x, y, max(320, width + 24), max(220, height + 24))
        preview.geometry(f"{max(320, width + 24)}x{max(220, height + 24)}+{x}+{y}")
    except Exception:
        pass
    return preview


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

    temp_win = open_json_in_layout(root, json_path, template_mode=template_mode)
    if not temp_win:
        return None, None
    preview_title = None
    try:
        _position_window_on_launcher_monitor(temp_win, root, x_offset=40, y_offset=40)
        try:
            preview_title = "Preview"
        except Exception:
            preview_title = "Preview"
        image = _capture_window_image(temp_win)
        try:
            image = _resize_preview_image(image, scale=0.75)
            out_path = preview_image_path_for_json(json_path)
            ensure_dir(os.path.dirname(out_path))
            image.save(out_path, format="PNG")
        except Exception:
            pass
    finally:
        try:
            if temp_win and temp_win.winfo_exists():
                temp_win.destroy()
        except Exception:
            pass
    return image, (preview_title or "Preview")


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

def build_new_layout_launcher(parent):  
    root = tk.Toplevel(parent)  
    root.title("New Layout")  
    root.geometry("900x700")  
    root.minsize(820, 620)  
    remember_window_geometry(root, "new_layout_launcher", default_geometry="900x700", minsize=(820, 620))
    _bind_window_size_memory(root, "new_layout_launcher")  
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
    # Auto-select text on focus for section count spinbox
    section_count_spinbox.bind('<FocusIn>', lambda e: e.widget.select_range(0, 'end'))  
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
    # Auto-select text on focus for all section page spinboxes
    for spinbox in section_page_spinboxes:
        spinbox.bind('<FocusIn>', lambda e: e.widget.select_range(0, 'end'))
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
        try:
            sel = templates_listbox.curselection()
            return template_paths[sel[0]] if sel else None
        except Exception:
            return None
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
        close_preview()
        win = tk.Toplevel(parent)  
        build_press_layout(  
            win,  
            title=f"{press} - {fmt}",  
            config=cfg,  
            load_path=load_path,  
            load_as_copy=True  # NEW LAYOUT from template => copy  
        )  
        close_preview()
        root.destroy()  
    def _on_template_selection_change(event=None):
        sel = templates_listbox.curselection()
        show_preview(template_paths[sel[0]] if sel else None)
    templates_listbox.bind("<<ListboxSelect>>", _on_template_selection_change)
    templates_listbox.bind("<Double-Button-1>", lambda e: on_new_or_open())
    btn_row = ttk.Frame(frame)  
    btn_row.grid(row=4, column=0, columnspan=8, pady=(12, 0), sticky="w")  
    ttk.Button(btn_row, text="New / Open", command=on_new_or_open, width=14).pack(side="left", padx=(0, 8))  
    ttk.Button(btn_row, text="Refresh Templates", command=refresh_templates, width=16).pack(side="left")  
    preview_box = ttk.LabelFrame(paned, text="Preview", padding=8)
    preview_box.columnconfigure(0, weight=1)
    preview_label = ttk.Label(preview_box, text="Select a template to preview", anchor="center", justify="center")
    preview_label.grid(row=0, column=0, sticky="nsew")
    preview_box.rowconfigure(0, weight=1)
    preview_label.bind("<Configure>", lambda e: _render_preview_panel_image(preview_label, preview_state), add="+")
    paned.add(preview_box, minsize=160)
    _bind_preview_pane_memory(root, "new_layout_launcher", paned, preview_box, default_height=240)
    root.bind("<FocusIn>", _on_launcher_focus_in, add="+")
    root.bind("<FocusOut>", _on_launcher_focus_out, add="+")
    root.protocol("WM_DELETE_WINDOW", lambda: (close_preview(), root.destroy()))
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

    tree.heading("name", text="Template Name")
    tree.heading("press", text="Press")
    tree.heading("format", text="Format")
    tree.heading("saved", text="Last Saved")
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

    def refresh():
        template_rows.clear()
        for disp, path in list_json_files(TEMPLATE_DIR):
            data = safe_read_json(path)
            name = os.path.splitext(os.path.basename(path))[0]
            press = ""
            fmt = ""
            if isinstance(data, dict):
                name = data.get("name") or name
                press = data.get("press") or ""
                fmt = data.get("format") or ""
            try:
                saved_dt = datetime.fromtimestamp(os.path.getmtime(path))
                saved_disp = saved_dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                saved_dt = None
                saved_disp = ""
            row = {
                "path": path,
                "name": name,
                "press": press,
                "format": fmt,
                "saved_dt": saved_dt,
                "saved_disp": saved_disp,
            }
            if _matches_template_filter(row):
                template_rows.append(row)
        load_rows(sort_rows(list(template_rows)))

    def sort_by(col):
        if sort_state["col"] == col:
            sort_state["desc"] = not sort_state["desc"]
        else:
            sort_state["col"] = col
            sort_state["desc"] = False
        refresh()

    tree.heading("name", command=lambda: sort_by("name"))
    tree.heading("press", command=lambda: sort_by("press"))
    tree.heading("format", command=lambda: sort_by("format"))
    tree.heading("saved", command=lambda: sort_by("saved"))

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
        temp_win = None
        try:
            temp_win = open_json_in_layout(root, path, template_mode=True)
            if not temp_win:
                return
            _position_window_on_launcher_monitor(temp_win, root, x_offset=40, y_offset=40)
            save_window_preview_image(temp_win, path, scale=0.75)
            show_preview(path)
        except Exception as exc:
            messagebox.showerror("Regen Preview Failed", str(exc), parent=root)
        finally:
            try:
                if temp_win and temp_win.winfo_exists():
                    temp_win.destroy()
            except Exception:
                pass

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
    root.bind("<FocusIn>", _on_launcher_focus_in, add="+")
    root.bind("<FocusOut>", _on_launcher_focus_out, add="+")
    root.protocol("WM_DELETE_WINDOW", lambda: (close_preview(), root.destroy()))
    return root

def build_main_launcher():  
    ensure_dir(LAYOUTS_DIR)  
    ensure_dir(TEMPLATE_DIR)  
    root = tk.Tk()  
    root.title("Press Layouts")  
    root.geometry("1100x760")  
    root.minsize(980, 680)  
    remember_window_geometry(root, "main_launcher", default_geometry="1100x760", minsize=(980, 680))
    _bind_window_size_memory(root, "main_launcher")  
    paned = tk.PanedWindow(root, orient="vertical", sashrelief="raised", sashwidth=8, bd=0, showhandle=False)
    paned.pack(fill="both", expand=True)
    frame = ttk.Frame(paned, padding=16)
    paned.add(frame, stretch="always", minsize=220)
    frame.rowconfigure(2, weight=1)
    frame.columnconfigure(0, weight=1)
    ttk.Label(frame, text="Layouts:", font=(None, 11, "bold")).grid(row=0, column=0, sticky="w")
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

    columns = ("issue", "product", "press", "format", "saved")
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
    tree.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    vsb.grid(row=2, column=1, sticky="ns", pady=(0, 0))
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
            searchable = " ".join([row.get("issue_disp", ""), row.get("product", ""), row.get("press", ""), row.get("format", "")]).lower()
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
            searchable = " ".join([row.get("issue_disp", ""), row.get("product", ""), row.get("press", ""), row.get("format", "")]).lower()
            if search_text not in searchable:
                return False
        if press_filter != "All" and row.get("press", "") != press_filter:
            return False
        if format_filter != "All" and row.get("format", "") != format_filter:
            return False
        return True

    def refresh(preserve_state=True):
        selected = tree.selection() if preserve_state else ()
        focused = tree.focus() if preserve_state else None
        yview = tree.yview() if preserve_state else None
        all_rows = build_layout_rows()
        date_values = [row.get("issue_disp", "") for row in all_rows if _matches_layout_filter_no_issue(row) and row.get("issue_disp")]
        unique_dates = ["All"] + sorted(set(date_values), key=lambda t: datetime.strptime(t, "%m/%d/%Y") if parse_issue_date_flexible(t) else t)
        issue_date_combo.configure(values=unique_dates)
        if issue_date_var.get() not in unique_dates:
            issue_date_var.set("All")
        rows = [row for row in all_rows if _matches_layout_filter(row)]
        rows = sort_rows(rows)
        load_rows_into_tree(rows, preserve_selection=selected, preserve_focus=focused, preserve_yview=yview)
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
    tree.heading("issue", command=lambda: sort_by("issue"))
    tree.heading("product", command=lambda: sort_by("product"))
    tree.heading("press", command=lambda: sort_by("press"))
    tree.heading("format", command=lambda: sort_by("format"))
    tree.heading("saved", command=lambda: sort_by("saved"))
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
    def new_layout():  
        close_preview()
        build_new_layout_launcher(root)  
    def regenerate_selected_preview():
        path = selected_path()
        if not path:
            messagebox.showinfo("Select a Layout", "Select a layout to regenerate its preview.")
            return
        close_preview()
        temp_win = None
        try:
            temp_win = open_json_in_layout(root, path, template_mode=False)
            if not temp_win:
                return
            _position_window_on_launcher_monitor(temp_win, root, x_offset=40, y_offset=40)
            save_window_preview_image(temp_win, path, scale=0.75)
            show_preview(path)
        except Exception as exc:
            messagebox.showerror("Regen Preview Failed", str(exc))
        finally:
            try:
                if temp_win and temp_win.winfo_exists():
                    temp_win.destroy()
            except Exception:
                pass

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
    def cleanup_old_layouts():  
        today = datetime.now().date()  
        all_rows = build_layout_rows()  
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
        btns = ttk.Frame(outer)  
        btns.grid(row=2, column=0, pady=(12, 0), sticky="e")  
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
    ttk.Button(right_btns, text="Templates", command=templates, width=12).pack(side="right", padx=(0, 8))
    ttk.Button(right_btns, text="Delete", command=delete_selected, width=12).pack(side="right", padx=(0, 8))
    ttk.Button(right_btns, text="Cleanup", command=cleanup_old_layouts, width=12).pack(side="right", padx=(0, 8))
    ttk.Button(right_btns, text="Refresh", command=lambda: refresh(preserve_state=True), width=12).pack(side="right")
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
    def on_close():  
        try:  
            if refresh_job["id"] is not None:  
                root.after_cancel(refresh_job["id"])  
        except Exception:  
            pass  
        close_preview()
        root.destroy()  
    root.bind("<FocusIn>", _on_launcher_focus_in, add="+")
    root.bind("<FocusOut>", _on_launcher_focus_out, add="+")
    root.protocol("WM_DELETE_WINDOW", on_close)  
    refresh(preserve_state=False)  
    schedule_refresh()  
    root.mainloop()