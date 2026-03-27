#!/usr/bin/env python3
"""Ensure ~/refs is available, creating a symlink if needed.

In Claude Code, ~/refs typically exists as a real directory. In Cowork
(sandboxed VMs), mounted folders appear under /sessions/*/mnt/<name>/
rather than at ~/refs. This script detects a mounted 'refs' directory
and symlinks ~/refs to it so the rest of the skill works unchanged.

Fails open — if nothing is found, exits silently and the skill falls
back to web lookups as usual.
"""

import glob
import sys
from pathlib import Path


def main() -> None:
    refs = Path.home() / "refs"

    # Already exists (real dir or working symlink) — nothing to do
    if refs.is_dir():
        return

    # Clean up broken symlink
    if refs.is_symlink():
        refs.unlink()

    # Look for a mounted directory named "refs" under Cowork mount points
    matches = [
        Path(p)
        for p in glob.glob("/sessions/*/mnt/refs")
        if Path(p).is_dir()
    ]

    if len(matches) == 1:
        target = matches[0]
        refs.symlink_to(target)
        print(f"Linked ~/refs -> {target}")
    elif len(matches) > 1:
        print(
            f"WARNING: Found multiple mounted refs directories: "
            f"{', '.join(str(m) for m in matches)}. "
            f"Symlink ~/refs manually to the correct one.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
