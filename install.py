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
    "opin": "Court opinions (by reporter)",
    "statute/NDCC": "North Dakota Century Code",
    "reg/NDAC": "North Dakota Administrative Code",
    "rule": "Court rules",
    "cnst": "Constitutions",
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

    # Required: pdftotext (Poppler)
    if not shutil.which("pdftotext"):
        print("WARNING: pdftotext not found (Poppler)")
        print("  Install with: brew install poppler  (macOS)")
        warnings += 1

    # Python packages (pypdf, pdfplumber, python-docx, jetcite's deps) live in
    # the skill's own venv, built from requirements.txt by bootstrap_env.py.
    # Build it now so the first memo doesn't pay for it; the skill re-runs the
    # bootstrap at startup either way, so a failure here is not fatal.
    venv_python = None
    r = subprocess.run([sys.executable, str(INSTALL_DIR / "bootstrap_env.py")],
                       capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("VENV_PYTHON="):
            venv_python = line.split("=", 1)[1]
    if r.returncode == 0 and venv_python:
        print(f"Python venv ready: {venv_python}")
    else:
        print("WARNING: could not build the skill's Python venv now "
              "(network needed on first build); jetmemo will retry at startup.")
        if r.stderr.strip():
            print("  " + r.stderr.strip().splitlines()[-1])
        warnings += 1

    # Optional PDF extractors (improve text extraction quality)
    optional_missing = []
    if venv_python:
        try:
            subprocess.run([venv_python, "-c", "import fitz"],
                           capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            optional_missing.append(
                ("PyMuPDF", f"{venv_python} -m pip install pymupdf"))
    if not shutil.which("marker_single"):
        optional_missing.append(("marker", "pip install marker-pdf  (CLI on PATH)"))

    if optional_missing:
        print(f"\nOptional PDF extractors not found (text extraction will still work):")
        for name, install_cmd in optional_missing:
            print(f"  {name}: {install_cmd}")

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
