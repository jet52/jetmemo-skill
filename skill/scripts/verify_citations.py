#!/usr/bin/env python3
"""Citation checker — thin wrapper around jetcite for bench memo verification.

Usage:
    python3 verify_citations.py --file memo.md
    python3 verify_citations.py --file memo.md --json
    echo "2024 ND 156" | python3 verify_citations.py

Output: structured citation data with local paths, URLs, and search hints.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate jetcite: bundled in ../lib/jetcite, pip-installed, or bail.
# ---------------------------------------------------------------------------
_BUNDLED_LIB = Path(__file__).resolve().parent.parent / "lib"

if _BUNDLED_LIB.is_dir():
    sys.path.insert(0, str(_BUNDLED_LIB))

try:
    from jetcite import Citation, CitationType, scan_text
    from jetcite.cleanup import preprocess_document_text
    from jetcite.legacy import add_parallel_info, to_legacy_dict
except ImportError as e:
    _jetcite_dir = _BUNDLED_LIB / "jetcite"
    if not _jetcite_dir.is_dir():
        print(
            "ERROR: jetcite not found. Expected bundled copy at:\n"
            f"  {_jetcite_dir}\n"
            "Run 'make vendor-jetcite' to re-vendor, or install via pip:\n"
            "  pip install git+https://github.com/jet52/jetcite.git",
            file=sys.stderr,
        )
    else:
        dep = e.name if hasattr(e, "name") and e.name else str(e)
        print(
            f"ERROR: jetcite found at {_jetcite_dir} but failed to import:\n"
            f"  {e}\n"
            f"Install the missing dependency:  pip install {dep}",
            file=sys.stderr,
        )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_citations(text: str, refs_dir: str = "~/refs",
                   include_pin_cites: bool = True) -> list[dict]:
    """Scan text for all citations. Returns legacy-format dicts.

    Pin-cite short forms ("491 F.3d at 363", "Goss at 365", "Id. ¶ 14")
    appear as entries with cite_type "pin_cite", linked to their parent full
    cite via parent_normalized (None = unresolved — likely a drafting error).
    Pin entries never carry their own local file; verification reads the
    parent's cached opinion (parent_local_path / parent_local_exists).
    """
    refs = Path(refs_dir).expanduser()
    citations = scan_text(text, refs_dir=refs, include_pin_cites=include_pin_cites)

    entries = [to_legacy_dict(c, refs) for c in citations]
    add_parallel_info(entries, citations)
    mark_redundant_parallels(entries)
    annotate_pin_cites(entries)
    annotate_splice_suspects(entries, preprocess_document_text(text))

    return entries


def _primary_of_pair(a: dict, b: dict) -> tuple[dict, dict]:
    """Given two parallel citation entries for the same case, pick the primary.

    Preference order: a locally-cached copy, then a neutral citation, then the
    first entry. Returns (primary, secondary).
    """
    if a.get("local_exists") != b.get("local_exists"):
        return (a, b) if a.get("local_exists") else (b, a)
    a_neutral = a.get("cite_type") == "neutral_cite"
    b_neutral = b.get("cite_type") == "neutral_cite"
    if a_neutral != b_neutral:
        return (a, b) if a_neutral else (b, a)
    return a, b


def mark_redundant_parallels(entries: list[dict]) -> None:
    """Flag parallel-citation siblings that refer to the same case.

    When two entries are parallel cites of each other AND share a non-null
    ``antecedent_name`` (the preceding case name), they point to one opinion.
    The secondary is marked ``redundant_parallel: True`` with ``primary_cite``
    naming the entry that should actually be verified, so the orchestrator can
    collapse the pair into a single item for Agent D.

    Entries are flagged, never removed: link_citations.py still needs every
    cite_text to hyperlink both citation forms in the memo.
    """
    by_norm = {e["normalized"]: e for e in entries}
    for entry in entries:
        if entry.get("redundant_parallel"):
            continue
        parallel = entry.get("parallel_cite")
        if not parallel:
            continue
        sibling = by_norm.get(parallel)
        if sibling is None or sibling.get("redundant_parallel"):
            continue
        ante = entry.get("antecedent_name")
        if not ante or sibling.get("antecedent_name") != ante:
            continue
        primary, secondary = _primary_of_pair(entry, sibling)
        secondary["redundant_parallel"] = True
        secondary["primary_cite"] = primary["normalized"]


# A short numeric token immediately after a suspect cite — the candidate
# true opinion number when the captured one was actually page furniture.
_NEXT_NUM_RE = re.compile(r"^\s{0,4}(\d{1,4})(?!\d)")
_TRAILING_NUM_RE = re.compile(r"^(.*\s)(\d{1,4})$")


def annotate_splice_suspects(entries: list[dict], text: str) -> None:
    """Flag neutral cites that may have spliced page furniture into the
    opinion number (the "2025 ND 13" phantom class).

    jetcite strips page furniture before scanning, so surviving splices are
    rare — but a footer that dodges the stripper can still be captured as
    the opinion number when only a soft line break separates it from the
    reporter. Evidence: the matched cite text spans a line break AND a bare
    numeric token immediately follows the cite in the document (the true
    opinion number, orphaned by the splice). Such entries get
    ``splice_suspect: true`` and ``splice_repair_candidate`` (the cite
    rejoined with the following token). The orchestrator must re-verify the
    candidate before reporting the cite as nonexistent or as an unrelated
    case.

    ``text`` must be the preprocessed document text — entry positions
    index into it.
    """
    for e in entries:
        if e["cite_type"] != "neutral_cite" or "\n" not in e["cite_text"]:
            continue
        end = e["position"] + len(e["cite_text"])
        nxt = _NEXT_NUM_RE.match(text[end:end + 10])
        if nxt is None:
            continue
        m = _TRAILING_NUM_RE.match(e["normalized"])
        if m is None:
            continue
        e["splice_suspect"] = True
        e["splice_repair_candidate"] = f"{m.group(1)}{nxt.group(1)}"


def annotate_pin_cites(entries: list[dict]) -> None:
    """Attach parent context to pin-cite entries.

    Pin cites carry no local file of their own; Agent D verifies the pin
    page/paragraph against the parent's cached opinion, so each resolved pin
    gets ``parent_local_path``/``parent_local_exists`` copied from its parent
    entry. Unresolved pins (explicit short form with no matching earlier full
    cite — e.g. a digit-transposed volume) get ``pin_warning`` so the
    orchestrator surfaces them as defects.
    """
    by_norm = {}
    for e in entries:
        if e["cite_type"] != "pin_cite":
            by_norm.setdefault(e["normalized"], e)
    for e in entries:
        if e["cite_type"] != "pin_cite":
            continue
        parent_norm = e.get("parent_normalized")
        if parent_norm is None:
            e["pin_warning"] = (
                "unresolved short form: no earlier full citation matches"
            )
            continue
        parent = by_norm.get(parent_norm)
        if parent is not None:
            e["parent_local_path"] = parent.get("local_path")
            e["parent_local_exists"] = parent.get("local_exists", False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Parse legal citations, resolve local files, build URLs."
    )
    parser.add_argument("--file", "-f", help="Scan a file for all citations")
    parser.add_argument("--refs-dir", default="~/refs",
                        help="Override refs directory (default: ~/refs)")
    parser.add_argument("--json", action="store_true", default=False,
                        help="Output as JSON")
    parser.add_argument("--pin-cites", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Include pin-cite short forms linked to their "
                             "parent cites (default: on; --no-pin-cites to disable)")
    args = parser.parse_args()

    if args.file:
        path = Path(args.file).expanduser()
        if not path.exists():
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        text = path.read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    results = scan_citations(text, refs_dir=args.refs_dir,
                             include_pin_cites=args.pin_cites)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        pins = [r for r in results if r["cite_type"] == "pin_cite"]
        fulls = [r for r in results if r["cite_type"] != "pin_cite"]
        local = sum(1 for r in fulls if r.get("local_exists"))
        web = sum(1 for r in fulls if r.get("url") and not r.get("local_exists"))
        unresolved = sum(1 for r in fulls if not r.get("local_exists") and not r.get("url"))
        redundant = sum(1 for r in fulls if r.get("redundant_parallel"))
        pin_warnings = sum(1 for r in pins if r.get("pin_warning"))

        print(f"\nCitation Scan Results")
        print(f"{'=' * 40}")
        summary = f"Total: {len(fulls)} | Local: {local} | Web only: {web} | Unresolved: {unresolved}"
        if redundant:
            summary += f" | Parallel dups: {redundant}"
        if pins:
            summary += f" | Pin cites: {len(pins)}"
            if pin_warnings:
                summary += f" ({pin_warnings} UNRESOLVED)"
        print(summary)

        by_type: dict[str, list[dict]] = {}
        for r in fulls:
            by_type.setdefault(r["cite_type"], []).append(r)

        for ctype, cites in sorted(by_type.items()):
            print(f"\n{ctype.upper()} ({len(cites)}):")
            for r in cites:
                status = "local" if r.get("local_exists") else ("url" if r.get("url") else "???")
                ante = r.get("antecedent_name")
                label = f"{ante}, {r['normalized']}" if ante else r["normalized"]
                if r.get("redundant_parallel"):
                    label += f"  (parallel of {r['primary_cite']})"
                print(f"  [{status:5s}] {label}")

        if pins:
            print(f"\nPIN_CITE ({len(pins)}):")
            for r in pins:
                if r.get("pin_warning"):
                    print(f"  [WARN ] {r['normalized']}  ⚠ {r['pin_warning']}")
                else:
                    where = "parent local" if r.get("parent_local_exists") else "parent url"
                    print(f"  [{'ok':5s}] {r['normalized']}  → {r['parent_normalized']} ({where})")


if __name__ == "__main__":
    main()
