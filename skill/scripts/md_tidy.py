#!/usr/bin/env python3
"""Normalize blank lines in a Markdown memo so every renderer parses it the same.

CommonMark lets a list or table start directly under a paragraph line; pandoc's
own Markdown does not, and renders such a list as a run-on paragraph
("Documents compared - Staff memo: ... - jetmemo draft: ..."). markdownlint
flags the same spots (MD022, MD031, MD032, MD058). This script inserts the
missing blank line before and after headings, fenced code blocks, lists, and
tables. It never changes a non-blank line and never touches text inside a code
fence or YAML front matter, so it is safe to run on every regeneration.

Usage:
    python3 md_tidy.py memo.md [more.md ...]     # rewrite in place
    python3 md_tidy.py --check memo.md           # report only; exit 1 if changes needed

Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_HEADING = re.compile(r"^ {0,3}#{1,6}(\s|$)")
_ITEM = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])(?:\s|$)")
_TABLE = re.compile(r"^ {0,3}\|")
_HRULE = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")


def _kind(line: str) -> str:
    if not line.strip():
        return "blank"
    if _HEADING.match(line):
        return "heading"
    if _HRULE.match(line):
        return "hrule"
    if _ITEM.match(line):
        return "item"
    if _TABLE.match(line):
        return "table"
    if line[:1] in (" ", "\t"):
        return "indented"
    return "text"


def tidy(text: str) -> tuple[str, int]:
    """Return (tidied text, number of blank lines inserted)."""
    lines = text.split("\n")
    out: list[str] = []
    inserted = 0

    def need_blank() -> None:
        nonlocal inserted
        if out and out[-1].strip():
            out.append("")
            inserted += 1

    i = 0
    # YAML front matter passes through untouched.
    if lines and lines[0].strip() == "---":
        end = next((j for j in range(1, len(lines)) if lines[j].strip() in ("---", "...")), None)
        if end is not None:
            out.extend(lines[: end + 1])
            i = end + 1

    prev = "blank"          # kind of the previous emitted block-level line
    in_list = False
    while i < len(lines):
        line = lines[i]
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            need_blank()
            out.append(line)
            i += 1
            while i < len(lines):
                out.append(lines[i])
                closing = _FENCE.match(lines[i])
                i += 1
                if closing and closing.group(1)[0] == marker[0] and len(closing.group(1)) >= len(marker) \
                        and not lines[i - 1].strip()[len(closing.group(1)):].strip():
                    break
            prev, in_list = "fence", False
            continue

        kind = _kind(line)
        if kind == "blank":
            out.append(line)
            prev, in_list = "blank", False
            i += 1
            continue

        if kind == "heading":
            need_blank()
            out.append(line)
            prev, in_list = "heading", False
            i += 1
            continue

        if prev in ("heading", "fence"):
            need_blank()

        if kind == "item":
            if not in_list and prev != "blank":
                need_blank()
            in_list = True
        elif kind == "table":
            if prev != "table" and not in_list:
                need_blank()
            elif in_list and prev != "table" and not line.startswith((" ", "\t")):
                need_blank()
                in_list = False
        elif in_list:
            # Indented lines and lazy continuations stay inside the list item.
            pass
        elif prev == "table":
            need_blank()

        out.append(line)
        prev = kind
        i += 1

    return "\n".join(out), inserted


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--check", action="store_true",
                    help="report what would change; exit 1 if anything would")
    args = ap.parse_args(argv)

    status = 0
    for path in args.files:
        text = path.read_text(encoding="utf-8")
        new, n = tidy(text)
        if not n:
            continue
        if args.check:
            print(f"md_tidy: {path}: {n} blank line(s) needed")
            status = 1
        else:
            path.write_text(new, encoding="utf-8")
            print(f"md_tidy: {path}: inserted {n} blank line(s)")
    return status


if __name__ == "__main__":
    sys.exit(main())
