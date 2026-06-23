import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk

APP_NAME = "Press Layouts"
RESTART_EXIT_CODE = 42
MANAGED_ENV_VAR = "PRESS_LAYOUTS_MANAGED_BY_LAUNCHER"
SHARED_CHANGELOG_ENV_VAR = "PRESS_LAYOUTS_SHARED_CHANGELOG_PATH"
DEFAULT_SHARED_CHANGELOG_PATH = r"L:\changelog.json"
DEFAULT_LOCAL_ROOT = r"%LOCALAPPDATA%\PressLayouts"
VERSION_FILE_NAME = "current_version.txt"
READY_MARKER_NAME = ".release_ready"


def _expand_path(value, default=""):
    text = str(value or default or "").strip()
    if not text:
        return ""
    return os.path.normpath(os.path.expandvars(os.path.expanduser(text)))


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _normalize_version(value):
    text = str(value or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    return text.strip()


def _version_sort_key(value):
    normalized = _normalize_version(value)
    if not normalized:
        return tuple()
    import re
    items = []
    for part in re.split(r"([0-9]+)", normalized):
        if not part:
            continue
        if part.isdigit():
            items.append((0, int(part)))
        else:
            items.append((1, part.lower()))
    return tuple(items)


def _resolve_shared_changelog_path():
    env_value = _expand_path(os.environ.get(SHARED_CHANGELOG_ENV_VAR, ""))
    if env_value:
        return env_value
    return _expand_path(DEFAULT_SHARED_CHANGELOG_PATH)


def _load_distribution_config(changelog_path):
    data = _load_json(changelog_path)
    distribution = data.get("distribution") if isinstance(data, dict) else None
    if not isinstance(distribution, dict):
        distribution = {}
    current_version = _normalize_version(data.get("current_version"))
    current_release = _normalize_version(distribution.get("current_release") or current_version)
    if not current_release:
        raise RuntimeError("changelog.json is missing current_version/current_release.")
    release_root = _expand_path(distribution.get("release_root"), r"L:\PressLayouts\releases")
    entry_exe = str(distribution.get("entry_exe") or "press_layouts.exe").strip() or "press_layouts.exe"
    local_root = _expand_path(distribution.get("local_root"), DEFAULT_LOCAL_ROOT)
    retain_local_versions = 1
    package_type = str(distribution.get("package_type") or "onedir").strip().lower() or "onedir"
    if package_type != "onedir":
        raise RuntimeError(f"Unsupported package_type '{package_type}'. This launcher expects an onedir release.")
    return {
        "changelog": data,
        "distribution": distribution,
        "current_release": current_release,
        "release_root": release_root,
        "entry_exe": entry_exe,
        "local_root": local_root,
        "retain_local_versions": retain_local_versions,
        "package_type": package_type,
    }


def _source_release_dir(config):
    return os.path.join(config["release_root"], config["current_release"])


def _local_release_dir(config):
    return os.path.join(config["local_root"], "releases", config["current_release"])


def _local_entry_exe(config):
    return os.path.join(_local_release_dir(config), config["entry_exe"])


def _ready_marker(path):
    return os.path.join(path, READY_MARKER_NAME)


class LauncherSplashScreen:
    def __init__(self, title=APP_NAME):
        self.root = None
        self.status_var = None
        self.detail_var = None
        self.progress = None
        try:
            root = tk.Tk()
            root.title(f"{title} Launcher")
            root.resizable(False, False)
            root.attributes("-topmost", True)
            root.protocol("WM_DELETE_WINDOW", lambda: None)
            root.geometry("460x170")

            body = ttk.Frame(root, padding=16)
            body.pack(fill="both", expand=True)
            body.columnconfigure(0, weight=1)

            ttk.Label(body, text=title, font=(None, 12, "bold")).grid(row=0, column=0, sticky="w")
            self.status_var = tk.StringVar(value="Starting launcher...")
            self.detail_var = tk.StringVar(value="")
            ttk.Label(body, textvariable=self.status_var, wraplength=420, justify="left").grid(row=1, column=0, sticky="w", pady=(12, 4))
            ttk.Label(body, textvariable=self.detail_var, wraplength=420, justify="left", foreground="#555555").grid(row=2, column=0, sticky="w")

            self.progress = ttk.Progressbar(body, mode="indeterminate", length=420)
            self.progress.grid(row=3, column=0, sticky="ew", pady=(16, 0))
            self.progress.start(10)

            root.update_idletasks()
            width = root.winfo_width() or 460
            height = root.winfo_height() or 170
            screen_width = root.winfo_screenwidth() or width
            screen_height = root.winfo_screenheight() or height
            pos_x = max(0, int((screen_width - width) / 2))
            pos_y = max(0, int((screen_height - height) / 2))
            root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
            root.update()
            self.root = root
        except Exception:
            self.root = None
            self.status_var = None
            self.detail_var = None
            self.progress = None

    def set_status(self, status, detail=""):
        if self.root is None:
            return
        try:
            self.status_var.set(str(status or ""))
            self.detail_var.set(str(detail or ""))
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass

    def close(self):
        if self.root is None:
            return
        try:
            if self.progress is not None:
                self.progress.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        self.root = None


def _local_release_is_ready(config):
    target_dir = _local_release_dir(config)
    return os.path.isdir(target_dir) and os.path.isfile(_ready_marker(target_dir))


def _update_required(config):
    return not _local_release_is_ready(config)


def _copy_release_if_needed(config, splash=None):
    source_dir = _source_release_dir(config)
    if not os.path.isdir(source_dir):
        raise RuntimeError(f"Shared release folder not found: {source_dir}")
    local_root = config["local_root"]
    target_dir = _local_release_dir(config)
    os.makedirs(os.path.join(local_root, "releases"), exist_ok=True)
    if os.path.isdir(target_dir) and os.path.isfile(_ready_marker(target_dir)):
        if splash is not None:
            splash.set_status(
                "Latest version is already cached locally.",
                f"Using local release {config['current_release']}."
            )
        return target_dir
    staging_dir = target_dir + ".staging"
    if splash is not None:
        splash.set_status(
            "Preparing local update...",
            f"Copying Press Layouts {config['current_release']} from {source_dir}"
        )
    if os.path.isdir(staging_dir):
        shutil.rmtree(staging_dir, ignore_errors=True)
    shutil.copytree(source_dir, staging_dir)
    if splash is not None:
        splash.set_status(
            "Finalizing local update...",
            f"Marking local release {config['current_release']} as ready."
        )
    Path(_ready_marker(staging_dir)).write_text(config["current_release"], encoding="utf-8")
    if os.path.isdir(target_dir):
        shutil.rmtree(target_dir, ignore_errors=True)
    os.replace(staging_dir, target_dir)
    Path(os.path.join(local_root, VERSION_FILE_NAME)).write_text(config["current_release"], encoding="utf-8")
    return target_dir


def _cleanup_old_local_versions(config, splash=None):
    releases_dir = Path(config["local_root"]) / "releases"
    if not releases_dir.is_dir():
        return
    current_name = str(config["current_release"] or "").strip()
    removed_any = False
    for child in releases_dir.iterdir():
        if not child.is_dir():
            continue
        if child.name == current_name:
            continue
        if splash is not None:
            splash.set_status(
                "Removing previous local versions...",
                f"Deleting {child.name} from the local cache."
            )
        shutil.rmtree(child, ignore_errors=True)
        removed_any = True
    if splash is not None and not removed_any:
        splash.set_status(
            "Local cache cleanup complete.",
            f"Only version {current_name} is stored locally."
        )


def _launch_once(config, changelog_path):
    splash = None
    try:
        if _update_required(config):
            splash = LauncherSplashScreen(APP_NAME)
            if splash is not None:
                splash.set_status(
                    "Checking for updates...",
                    f"Preparing Press Layouts {config['current_release']} on this computer."
                )
        _copy_release_if_needed(config, splash=splash)
        _cleanup_old_local_versions(config, splash=splash)
        exe_path = _local_entry_exe(config)
        if not os.path.isfile(exe_path):
            raise RuntimeError(f"Local release entry EXE not found: {exe_path}")
        if splash is not None:
            splash.set_status(
                "Launching Press Layouts...",
                f"Opening {config['entry_exe']} from local version {config['current_release']}."
            )
        env = os.environ.copy()
        env[MANAGED_ENV_VAR] = "1"
        env[SHARED_CHANGELOG_ENV_VAR] = changelog_path
        popen_kwargs = {
            "cwd": os.path.dirname(exe_path),
            "env": env,
        }
        if os.name == "nt":
            creationflags = 0
            creationflags |= int(getattr(subprocess, "DETACHED_PROCESS", 0) or 0)
            creationflags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) or 0)
            if creationflags:
                popen_kwargs["creationflags"] = creationflags
        subprocess.Popen([exe_path], **popen_kwargs)
        if splash is not None:
            splash.set_status(
                "Launch started.",
                "Press Layouts is opening now. The launcher will close automatically."
            )
            time.sleep(0.35)
        return 0
    finally:
        if splash is not None:
            splash.close()


def run_launcher():
    changelog_path = _resolve_shared_changelog_path()
    if not os.path.isfile(changelog_path):
        raise RuntimeError(f"Shared changelog manifest not found: {changelog_path}")
    while True:
        config = _load_distribution_config(changelog_path)
        exit_code = _launch_once(config, changelog_path)
        if exit_code == RESTART_EXIT_CODE:
            time.sleep(1.0)
            continue
        return int(exit_code)


def main():
    try:
        return run_launcher()
    except Exception as exc:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Press Layouts Launcher", str(exc))
            root.destroy()
        except Exception:
            print(f"Press Layouts Launcher failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
