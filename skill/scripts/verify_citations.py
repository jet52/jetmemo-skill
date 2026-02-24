#!/usr/bin/env python3
"""Verify citations in a bench memo against external sources.

Usage:
    python verify_citations.py <memo_file> [--courtlistener-key KEY] [--opinions-dir DIR]

Checks ND case citations against local opinion files, ND Courts website,
and optionally CourtListener. Checks ND statutes against ndlegis.gov.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path


def extract_nd_case_citations(text: str) -> list[dict]:
    """Extract unique ND case citations (YYYY ND ###)."""
    seen = set()
    results = []
    for match in re.finditer(r"(\d{4})\s+ND\s+(\d+)", text):
        normalized = f"{match.group(1)} ND {match.group(2)}"
        if normalized not in seen:
            seen.add(normalized)
            results.append({
                "citation": normalized,
                "year": match.group(1),
                "number": match.group(2),
                "type": "nd_case",
            })
    return results


def extract_statute_citations(text: str) -> list[dict]:
    """Extract unique N.D.C.C. citations."""
    seen = set()
    results = []
    for match in re.finditer(r"N\.D\.C\.C\.\s*§\s*([\d\-\.]+(?:\([^)]*\))*)", text):
        section = match.group(1)
        if section not in seen:
            seen.add(section)
            results.append({
                "citation": f"N.D.C.C. § {section}",
                "section": section,
                "type": "ndcc",
            })
    return results


def extract_nw2d_citations(text: str) -> list[dict]:
    """Extract unique N.W.2d citations."""
    seen = set()
    results = []
    for match in re.finditer(r"(\d+)\s+N\.W\.2d\s+(\d+)", text):
        normalized = f"{match.group(1)} N.W.2d {match.group(2)}"
        if normalized not in seen:
            seen.add(normalized)
            results.append({
                "citation": normalized,
                "type": "nw2d",
            })
    return results


def verify_local(citation: dict, opinions_dir: str) -> dict | None:
    """Check if an ND case exists in local opinion markdown files."""
    if not opinions_dir or citation["type"] != "nd_case":
        return None
    md_dir = Path(opinions_dir) / "markdown"
    if not md_dir.is_dir():
        md_dir = Path(opinions_dir)
        if not md_dir.is_dir():
            return None

    year = citation["year"]
    num = citation["number"]
    filepath = md_dir / year / f"{year}ND{num}.md"

    if filepath.is_file():
        # Extract case name from first ~2000 chars
        text = filepath.read_text(encoding="utf-8", errors="replace")[:2000]
        name_match = re.search(
            r"([A-Z][A-Za-z.\-\s]+?)\s*(?:,\s*\n)?\s*v\.\s*\n?\s*([A-Z][A-Za-z.\-\s]+?)(?:\s*\n|,)",
            text,
        )
        case_name = ""
        if name_match:
            plaintiff = name_match.group(1).strip().split("\n")[-1].strip()
            defendant = name_match.group(2).strip().split("\n")[0].strip()
            case_name = f"{plaintiff} v. {defendant}"
        return {
            "verified": True,
            "source": "local",
            "case_name": case_name,
            "path": str(filepath),
        }
    return None


def verify_nd_courts(citation: dict) -> dict | None:
    """Check ndcourts.gov for an ND case."""
    if citation["type"] != "nd_case":
        return None
    try:
        time.sleep(1)  # Rate limit
        cite_str = citation["citation"]
        url = f"https://www.ndcourts.gov/supreme-court/opinions?search={urllib.parse.quote(cite_str)}"
        req = urllib.request.Request(url, headers={"User-Agent": "bench-memo-verifier/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            if cite_str in html:
                return {
                    "verified": True,
                    "source": "nd_courts",
                    "url": url,
                }
    except Exception as e:
        return {"verified": False, "source": "nd_courts", "error": str(e)}
    return None


def verify_courtlistener(citation: dict, api_key: str) -> dict | None:
    """Check CourtListener for a case citation."""
    if not api_key:
        return None
    try:
        data = json.dumps({"text": citation["citation"]}).encode("utf-8")
        req = urllib.request.Request(
            "https://www.courtlistener.com/api/rest/v4/citation-lookup/",
            data=data,
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "bench-memo-verifier/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            results = json.loads(resp.read().decode("utf-8"))
            for match in results:
                if match.get("citation") == citation["citation"] and match.get("clusters"):
                    cluster = match["clusters"][0]
                    return {
                        "verified": True,
                        "source": "courtlistener",
                        "case_name": cluster.get("case_name", ""),
                        "url": f"https://www.courtlistener.com{cluster.get('absolute_url', '')}",
                    }
    except Exception as e:
        return {"verified": False, "source": "courtlistener", "error": str(e)}
    return None


def verify_statute(citation: dict) -> dict | None:
    """Check ndlegis.gov for a statute section."""
    if citation["type"] != "ndcc":
        return None
    section = re.sub(r"\(.*\)", "", citation["section"]).strip()
    parts = section.split("-")
    if len(parts) < 2:
        return None
    title = parts[0].zfill(2)
    chapter = parts[1].zfill(2)
    try:
        time.sleep(1)
        url = f"https://www.ndlegis.gov/cencode/t{title}c{chapter}.html"
        req = urllib.request.Request(url, headers={"User-Agent": "bench-memo-verifier/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            if section in html:
                return {
                    "verified": True,
                    "source": "nd_statutes",
                    "url": url,
                }
    except Exception as e:
        return {"verified": False, "source": "nd_statutes", "error": str(e)}
    return None


def main():
    parser = argparse.ArgumentParser(description="Verify citations in a bench memo")
    parser.add_argument("memo_file", help="Path to the memo markdown file")
    parser.add_argument("--courtlistener-key", default=os.environ.get("COURTLISTENER_API_KEY", ""),
                        help="CourtListener API key")
    parser.add_argument("--opinions-dir", default=os.environ.get("OPINIONS_MD",
                        os.environ.get("COURT_DATA", "/Users/jerod/cDocs/refs/ndsc_opinions/markdown")),
                        help="Path to local ND opinions directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    memo_text = Path(args.memo_file).read_text(encoding="utf-8")

    nd_cases = extract_nd_case_citations(memo_text)
    statutes = extract_statute_citations(memo_text)
    nw2d_cases = extract_nw2d_citations(memo_text)

    results = {"verified": [], "unverified": [], "skipped": []}

    # Verify ND cases
    for cite in nd_cases:
        result = verify_local(cite, args.opinions_dir)
        if not result:
            result = verify_nd_courts(cite)
        if not result and args.courtlistener_key:
            result = verify_courtlistener(cite, args.courtlistener_key)
        if result and result.get("verified"):
            results["verified"].append({**cite, **result})
        else:
            error = result.get("error", "Not found") if result else "Not found in any source"
            results["unverified"].append({**cite, "error": error})

    # Verify statutes
    for cite in statutes:
        result = verify_statute(cite)
        if result and result.get("verified"):
            results["verified"].append({**cite, **result})
        else:
            error = result.get("error", "Not found") if result else "Not found"
            results["unverified"].append({**cite, "error": error})

    # N.W.2d citations — skip (need CourtListener for these)
    for cite in nw2d_cases:
        if args.courtlistener_key:
            result = verify_courtlistener(cite, args.courtlistener_key)
            if result and result.get("verified"):
                results["verified"].append({**cite, **result})
            else:
                results["skipped"].append({**cite, "reason": "N.W.2d lookup requires CourtListener"})
        else:
            results["skipped"].append({**cite, "reason": "N.W.2d lookup requires CourtListener API key"})

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        v = len(results["verified"])
        u = len(results["unverified"])
        s = len(results["skipped"])
        print(f"\nCitation Verification Results")
        print(f"{'=' * 40}")
        print(f"Verified: {v} | Unverified: {u} | Skipped: {s}")
        print()
        if results["verified"]:
            print("VERIFIED:")
            for r in results["verified"]:
                name = r.get("case_name", "")
                src = r.get("source", "")
                extra = f" ({name})" if name else ""
                print(f"  + {r['citation']}{extra} [{src}]")
        if results["unverified"]:
            print("\nUNVERIFIED:")
            for r in results["unverified"]:
                err = r.get("error", "")
                print(f"  - {r['citation']}: {err}")
        if results["skipped"]:
            print("\nSKIPPED:")
            for r in results["skipped"]:
                reason = r.get("reason", "")
                print(f"  ~ {r['citation']}: {reason}")


if __name__ == "__main__":
    main()
