import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKING_ROOT = Path("L:/Working")
SHARED_ROOT = Path("L:/")
CHANGELOG_PATH = WORKING_ROOT / "changelog.json"
FALLBACK_CHANGELOG_PATH = ROOT.parent / "changelog.json"
SHARED_CHANGELOG_PATH = SHARED_ROOT / "changelog.json"
DIST_ROOT = ROOT / "dist"
DIST_APP_DIR = DIST_ROOT / "press_layouts"
BUILD_RELEASE_SCRIPT = ROOT / "build_press_layouts_release.py"
BUILD_LAUNCHER_SCRIPT = ROOT / "build_press_layouts_launcher.py"
DEFAULT_RELEASE_ROOT = Path("L:/PressLayouts/releases")
DEFAULT_LAUNCHER_ROOT = Path("L:/PressLayouts/launcher")
DEFAULT_LAUNCHER_NAME = "press_layouts_launcher.exe"


def resolve_working_changelog_path():
    if CHANGELOG_PATH.exists():
        return CHANGELOG_PATH
    if FALLBACK_CHANGELOG_PATH.exists():
        return FALLBACK_CHANGELOG_PATH
    raise FileNotFoundError(
        f"Could not find changelog.json at {CHANGELOG_PATH} or {FALLBACK_CHANGELOG_PATH}"
    )


SOURCE_CHANGELOG_PATH = resolve_working_changelog_path()


def load_changelog():
    with open(SOURCE_CHANGELOG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_changelog(data):
    SOURCE_CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SOURCE_CHANGELOG_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def run_build(script_path, label):
    if not script_path.is_file():
        raise RuntimeError(f"{label} build script not found: {script_path}")
    cmd = [sys.executable, str(script_path)]
    print(f"Building {label} with: {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=ROOT)
    if completed.returncode != 0:
        raise RuntimeError(f"{label} build failed with exit code {completed.returncode}")


def find_launcher_dist_executable(expected_name=DEFAULT_LAUNCHER_NAME):
    candidates = []
    explicit = DIST_ROOT / expected_name
    if explicit.is_file():
        candidates.append(explicit)
    candidates.extend(path for path in DIST_ROOT.rglob(expected_name) if path.is_file())
    if not candidates:
        raise RuntimeError(
            f"Built launcher executable not found under {DIST_ROOT} (expected {expected_name})"
        )
    candidates = sorted(
        {candidate.resolve() for candidate in candidates},
        key=lambda candidate: (-candidate.stat().st_mtime, len(candidate.parts), str(candidate).lower()),
    )
    return candidates[0]


def copy_release(version, release_root):
    target_dir = release_root / version
    if not DIST_APP_DIR.is_dir():
        raise RuntimeError(f"Built onedir app folder not found: {DIST_APP_DIR}")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(DIST_APP_DIR, target_dir)
    return target_dir


def copy_launcher(distribution):
    launcher_name = str(distribution.get("launcher_exe") or DEFAULT_LAUNCHER_NAME).strip() or DEFAULT_LAUNCHER_NAME
    launcher_source = find_launcher_dist_executable(launcher_name)
    launcher_target_dir = Path(str(distribution.get("launcher_root") or DEFAULT_LAUNCHER_ROOT))
    launcher_target_dir.mkdir(parents=True, exist_ok=True)
    launcher_target_path = launcher_target_dir / launcher_name
    shutil.copy2(launcher_source, launcher_target_path)
    return launcher_source, launcher_target_path


def copy_shared_changelog():
    SHARED_CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_CHANGELOG_PATH, SHARED_CHANGELOG_PATH)
    return SHARED_CHANGELOG_PATH


def publish_release(version=None):
    run_build(BUILD_RELEASE_SCRIPT, "release")
    run_build(BUILD_LAUNCHER_SCRIPT, "launcher")

    changelog = load_changelog()
    version = str(version or changelog.get("current_version") or "").strip()
    if not version:
        raise RuntimeError("Could not determine current_version from changelog.json")

    distribution = changelog.setdefault("distribution", {})
    release_root = Path(str(distribution.get("release_root") or DEFAULT_RELEASE_ROOT))
    target_dir = copy_release(version, release_root)

    distribution["current_release"] = version
    distribution.setdefault("package_type", "onedir")
    distribution.setdefault("entry_exe", "press_layouts.exe")
    distribution.setdefault("launcher_exe", DEFAULT_LAUNCHER_NAME)
    distribution.setdefault("launcher_root", str(DEFAULT_LAUNCHER_ROOT))
    changelog["distribution"] = distribution
    save_changelog(changelog)

    launcher_source, launcher_target = copy_launcher(distribution)
    shared_changelog = copy_shared_changelog()

    print(f"Published Press Layouts {version} to {target_dir}")
    print(f"Copied launcher from {launcher_source} to {launcher_target}")
    print(f"Copied changelog from {SOURCE_CHANGELOG_PATH} to {shared_changelog}")


if __name__ == "__main__":
    publish_release(*sys.argv[1:2])
