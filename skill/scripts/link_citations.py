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
    """Escape regex special characters in citation text.

    Appends a negative lookahead for word characters when the citation
    ends in an alphanumeric, so that "Rule 5" does not match inside
    "Rule 52" and "N.D.R.Juv.P. 5" does not match inside "N.D.R.Juv.P. 52".
    """
    pattern = re.escape(text)
    if text and text[-1].isalnum():
        pattern += r"(?![A-Za-z0-9])"
    return pattern


# ---------------------------------------------------------------------------
# Short-form alias detection
# ---------------------------------------------------------------------------
# A bench memo will typically cite an authority in full once (e.g.,
# "N.D.R.Juv.P. 9" or "N.D.C.C. \u00a7 27-19.1-01(3)") and then refer to it
# repeatedly in short form ("Rule 9(a)(3)", "\u00a7 27-19.1-01(5)", "Section
# 27-19.1-01"). jetcite typically returns only the full form, so the
# short-form references are not in `citations.json`.
#
# To preserve the relationship, we derive short-form aliases from the
# full-form citations: every linked "N.D.R.{set}.P. {N}" registers
# "Rule {N}" as an alias; every linked "N.D.C.C. \u00a7 {section}" registers
# "\u00a7 {section}" and "Section {section}". If two different rule sets share
# the same rule number with different URLs, the short-form is ambiguous
# and is skipped (the writer must spell out the rule set).

_RULE_FULLFORM_RE = re.compile(
    r"^N\.D\.R\.(?:[A-Za-z]+\.?)+P?\.?\s+(\d+(?:\.\d+)?)\b"
)
_STATUTE_FULLFORM_RE = re.compile(
    r"^N\.D\.C\.C\.\s+\u00a7\s+([\d.\-]+?)(?:\([^)]+\))*$"
)


def _add_shortform_aliases(cite_map: dict[str, str]) -> dict[str, str]:
    """Register Rule N / \u00a7 N.N / Section N.N aliases for unambiguous full-form cites.

    Returns the enriched cite_map. Aliases are added only when the short
    form would not be ambiguous across the citations seen.
    """
    rule_aliases: dict[str, set[str]] = {}
    section_aliases: dict[str, set[str]] = {}

    for text, url in cite_map.items():
        rm = _RULE_FULLFORM_RE.match(text)
        if rm:
            rule_aliases.setdefault(f"Rule {rm.group(1)}", set()).add(url)
            continue
        sm = _STATUTE_FULLFORM_RE.match(text)
        if sm:
            section = sm.group(1).rstrip(".,")
            section_aliases.setdefault(f"\u00a7 {section}", set()).add(url)
            section_aliases.setdefault(f"Section {section}", set()).add(url)

    enriched = dict(cite_map)
    for alias, urls in {**rule_aliases, **section_aliases}.items():
        if len(urls) == 1 and alias not in enriched:
            enriched[alias] = next(iter(urls))
    return enriched


def link_citations(markdown: str, citations: list[dict]) -> str:
    """Replace bare citation text in markdown with [cite_text](url) links.

    Skips text that is already inside a markdown link. Short-form aliases
    ("Rule N", "§ N.N.N", "Section N.N.N") are derived from full-form
    citations so that subsequent short references in the memo are linked
    to the same URL.
    """
    cite_map = _add_shortform_aliases(_build_cite_map(citations))
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
