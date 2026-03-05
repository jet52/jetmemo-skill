#!/usr/bin/env python3
"""Cross-platform installer for the jetmemo skill."""

import shutil
import subprocess
import sys
from pathlib import Path

SKILL_NAME = "jetmemo"
SCRIPT_DIR = Path(__file__).resolve().parent
INSTALL_DIR = Path.home() / ".claude" / "skills" / SKILL_NAME

REF_DIRS = {
    "opin": "ND Supreme Court opinions (markdown)",
    "ndcc": "North Dakota Century Code",
    "ndac": "North Dakota Administrative Code",
    "rule": "North Dakota Court Rules",
}


def main():
    version_file = SCRIPT_DIR / "VERSION"
    version = version_file.read_text().strip() if version_file.exists() else "unknown"
    print(f"Installing {SKILL_NAME} skill v{version}...")

    # If install dir is a symlink (e.g., from dev setup), remove it first
    if INSTALL_DIR.is_symlink():
        INSTALL_DIR.unlink()

    # Clean and recreate target directory
    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR)

    # Copy skill directory wholesale
    skill_src = SCRIPT_DIR / "skill"
    shutil.copytree(skill_src, INSTALL_DIR)

    # Copy VERSION
    shutil.copy2(version_file, INSTALL_DIR / "VERSION")

    print(f"Installed to {INSTALL_DIR}")

    # Check dependencies
    warnings = 0

    try:
        subprocess.run(
            [sys.executable, "-c", "import pypdf"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("WARNING: pypdf Python package not found")
        print("  Install with: pip install pypdf")
        warnings += 1

    refs_dir = Path.home() / "refs"
    for name, description in REF_DIRS.items():
        if not (refs_dir / name).is_dir():
            print(f"WARNING: ~/refs/{name}/ not found")
            print(f"  This directory should contain {description}.")
            warnings += 1

    if warnings:
        print(f"\n{warnings} warning(s). The skill will work but some features may be limited.")
    else:
        print("All dependencies found.")

    print("Done.")


if __name__ == "__main__":
    main()
