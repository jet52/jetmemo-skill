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

def scan_citations(text: str, refs_dir: str = "~/refs") -> list[dict]:
    """Scan text for all citations. Returns legacy-format dicts."""
    refs = Path(refs_dir).expanduser()
    citations = scan_text(text, refs_dir=refs)

    entries = [to_legacy_dict(c, refs) for c in citations]
    add_parallel_info(entries, citations)

    return entries


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
    args = parser.parse_args()

    if args.file:
        path = Path(args.file).expanduser()
        if not path.exists():
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        text = path.read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    results = scan_citations(text, refs_dir=args.refs_dir)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        local = sum(1 for r in results if r.get("local_exists"))
        web = sum(1 for r in results if r.get("url") and not r.get("local_exists"))
        unresolved = sum(1 for r in results if not r.get("local_exists") and not r.get("url"))

        print(f"\nCitation Scan Results")
        print(f"{'=' * 40}")
        print(f"Total: {len(results)} | Local: {local} | Web only: {web} | Unresolved: {unresolved}")

        by_type: dict[str, list[dict]] = {}
        for r in results:
            by_type.setdefault(r["cite_type"], []).append(r)

        for ctype, cites in sorted(by_type.items()):
            print(f"\n{ctype.upper()} ({len(cites)}):")
            for r in cites:
                status = "local" if r.get("local_exists") else ("url" if r.get("url") else "???")
                print(f"  [{status:5s}] {r['normalized']}")


if __name__ == "__main__":
    main()
