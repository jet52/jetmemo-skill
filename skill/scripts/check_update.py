#!/usr/bin/env python3
"""Check for jetmemo skill updates against the GitHub repo."""

import json
import sys
import urllib.request
from pathlib import Path

REPO = "jet52/jetmemo-skill"
GITHUB_API = f"https://api.github.com/repos/{REPO}/releases/latest"
SKILL_DIR = Path.home() / ".claude" / "skills" / "jetmemo"
VERSION_FILE = SKILL_DIR / "VERSION"


def local_version() -> str | None:
    """Read the locally installed version."""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return None


def latest_release() -> str | None:
    """Fetch the latest release tag from GitHub."""
    req = urllib.request.Request(
        GITHUB_API, headers={"Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("tag_name", "").lstrip("v")
    except Exception:
        return None


def parse_version(v: str) -> tuple[int, ...]:
    """Parse a semver string into a comparable tuple."""
    return tuple(int(x) for x in v.split("."))


def main():
    local = local_version()
    if not local:
        print("jetmemo: version unknown (no VERSION file)")
        sys.exit(1)

    remote = latest_release()
    if not remote:
        print(f"jetmemo v{local} (update check failed — couldn't reach GitHub)")
        sys.exit(0)

    if parse_version(remote) > parse_version(local):
        print(f"jetmemo v{local} — update available: v{remote}")
        print(f"  https://github.com/{REPO}/releases/latest")
        sys.exit(0)
    else:
        print(f"jetmemo v{local} (up to date)")
        sys.exit(0)


if __name__ == "__main__":
    main()
