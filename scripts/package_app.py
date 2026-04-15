from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
RELEASE_DIR = ROOT / "release"
APP_NAME = "evm-xer-analyzer"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build standalone app artifacts with PyInstaller.")
    parser.add_argument(
        "--version",
        default=_read_version(),
        help="Version label used in the packaged artifact filename.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove previous build, dist, and release directories before packaging.",
    )
    args = parser.parse_args()

    if args.clean:
        for directory in (BUILD_DIR, DIST_DIR, RELEASE_DIR):
            shutil.rmtree(directory, ignore_errors=True)

    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onedir",
            "--name",
            APP_NAME,
            str(ROOT / "evm_xer_analyzer" / "__main__.py"),
        ]
    )

    packaged_path = _find_packaged_output()
    release_archive = _archive_output(packaged_path, args.version)
    print(release_archive)
    return 0


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def _find_packaged_output() -> Path:
    mac_app = DIST_DIR / f"{APP_NAME}.app"
    if mac_app.exists():
        return mac_app

    app_dir = DIST_DIR / APP_NAME
    if app_dir.exists():
        return app_dir

    raise FileNotFoundError("PyInstaller finished, but no packaged app output was found in dist/.")


def _archive_output(packaged_path: Path, version: str) -> Path:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    platform_tag = _platform_tag()
    archive_base = RELEASE_DIR / f"{APP_NAME}-{version}-{platform_tag}"

    if packaged_path.suffix == ".app":
        temp_dir = RELEASE_DIR / f"{APP_NAME}-mac-bundle"
        shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True)
        shutil.copytree(packaged_path, temp_dir / packaged_path.name)
        archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return Path(archive_path)

    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=DIST_DIR, base_dir=packaged_path.name)
    return Path(archive_path)


def _platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        if machine in {"arm64", "aarch64"}:
            return "macos-arm64"
        return "macos-x64"
    if system == "windows":
        return "windows-x64"
    return f"{system}-{machine}"


def _read_version() -> str:
    pyproject = ROOT / "pyproject.toml"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version = "):
            return stripped.split("=", 1)[1].strip().strip('"')
    return "0.0.0"


if __name__ == "__main__":
    raise SystemExit(main())
