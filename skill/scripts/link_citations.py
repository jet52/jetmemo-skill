#!/usr/bin/env python3
"""Post-process memo markdown to hyperlink citations using URLs from citations.json.

Usage:
    python3 link_citations.py memo.md citations.json

Modifies memo.md in place, wrapping bare citation text with markdown links
using the URLs from citations.json. Already-linked text (inside markdown
link syntax) is left untouched.
"""

import json
import re
import sys
from pathlib import Path


def _build_cite_map(citations: list[dict]) -> dict[str, str]:
    """Build a map from cite_text -> url, keeping only entries with URLs.

    Dash variants (en dash, em dash) in cite_text are normalized to hyphens
    so that citations extracted from PDFs (which often use en dashes) match
    memo text written with plain hyphens.
    """
    seen: dict[str, str] = {}
    for entry in citations:
        text = _normalize_dashes(entry.get("cite_text", "").strip())
        url = entry.get("url")
        if text and url and text not in seen:
            seen[text] = url
    return seen


def _normalize_dashes(text: str) -> str:
    """Replace en dashes and em dashes with hyphens."""
    return text.replace("\u2013", "-").replace("\u2014", "-")


def _escape_for_regex(text: str) -> str:
    """Escape regex special characters in citation text."""
    return re.escape(text)


def link_citations(markdown: str, citations: list[dict]) -> str:
    """Replace bare citation text in markdown with [cite_text](url) links.

    Skips text that is already inside a markdown link.
    """
    cite_map = _build_cite_map(citations)
    if not cite_map:
        return markdown

    # Sort longest first to avoid partial matches
    sorted_cites = sorted(cite_map.keys(), key=len, reverse=True)

    for cite_text in sorted_cites:
        url = cite_map[cite_text]
        pattern = _escape_for_regex(cite_text)

        # Match cite_text only when NOT already inside a markdown link.
        # Negative lookbehind: not preceded by ]( (url part of link) or
        # preceded by [ (link text opening). We use a callback to check
        # the surrounding context more carefully.
        def _replace(m, _url=url, _cite=cite_text):
            start = m.start()
            # Check if this match is inside an existing markdown link.
            # Look backward for an unmatched [ that would indicate we're
            # inside [link text](url).
            prefix = markdown[:start]

            # Inside link text: [...HERE...](url)
            last_open = prefix.rfind("[")
            last_close = prefix.rfind("]")
            if last_open > last_close:
                return m.group(0)  # inside link text, skip

            # Inside link URL: [text](HERE)
            last_paren_open = prefix.rfind("](")
            if last_paren_open != -1:
                # Check if there's a closing ) after the ](
                between = prefix[last_paren_open + 2:]
                if ")" not in between:
                    return m.group(0)  # inside URL, skip

            return f"[{_cite}]({_url})"

        markdown = re.sub(pattern, _replace, markdown)

    return markdown


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <memo.md> <citations.json>", file=sys.stderr)
        sys.exit(1)

    memo_path = Path(sys.argv[1])
    cite_path = Path(sys.argv[2])

    if not memo_path.exists():
        print(f"Error: memo file not found: {memo_path}", file=sys.stderr)
        sys.exit(1)
    if not cite_path.exists():
        print(f"Error: citations file not found: {cite_path}", file=sys.stderr)
        sys.exit(1)

    markdown = memo_path.read_text(encoding="utf-8")
    citations = json.loads(cite_path.read_text(encoding="utf-8"))

    result = link_citations(markdown, citations)

    memo_path.write_text(result, encoding="utf-8")

    # Count how many links were inserted
    original_links = len(re.findall(r"\[[^\]]+\]\([^)]+\)", markdown))
    new_links = len(re.findall(r"\[[^\]]+\]\([^)]+\)", result))
    added = new_links - original_links
    print(f"Linked {added} citation(s) in {memo_path.name}")


if __name__ == "__main__":
    main()
