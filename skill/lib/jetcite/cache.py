"""Local reference cache for fetched citation content.

Resolves citations to local file paths in a ~/refs/ directory structure
and caches fetched content for future offline access.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from jetcite.models import Citation, CitationType, Source
from jetcite.patterns.base import roman_to_int

# Staleness thresholds in days — informational only, not auto-refetch
STALENESS_DAYS = {
    CitationType.CASE: None,  # permanent
    CitationType.CONSTITUTION: None,  # permanent
    CitationType.STATUTE: 90,
    CitationType.REGULATION: 90,
    CitationType.COURT_RULE: 180,
}

DEFAULT_REFS_DIR = Path.home() / "refs"

# Historical ND reporters stored under opin/ (before neutral citations)
_ND_REPORTERS = frozenset({"N.W.", "N.W.2d", "N.D."})

# Federal case reporters stored under federal/
_FEDERAL_REPORTERS = frozenset({
    "U.S.", "S. Ct.", "L. Ed.", "L. Ed. 2d",
    "F.", "F.2d", "F.3d", "F.4th",
    "F. Supp.", "F. Supp. 2d", "F. Supp. 3d",
    "B.R.", "F.R.D.", "Fed. Cl.", "M.J.",
    "Vet. App.", "T.C.", "F. App\u2019x", "F. App'x",
})


def _reporter_dir(reporter: str) -> str:
    """Normalize a reporter abbreviation to a directory name."""
    if reporter == "U.S.":
        return "scotus"
    return reporter.replace(".", "").replace(" ", "").replace("\u2019", "").replace("'", "")


def _citation_path(citation: Citation) -> Path | None:
    """Map a citation to its relative path within the refs directory.

    Three-tier layout for cases:
      opin/     — ND cases (neutral cites + historical ND reporters)
      federal/  — federal case reporters
      reporter/ — all other state and regional reporters

    Returns None if the citation type/components don't map to a known path.
    """
    c = citation.components

    if citation.cite_type == CitationType.CASE:
        if citation.jurisdiction == "nd" and "year" in c and "number" in c:
            # ND neutral citation: opin/markdown/{year}/{year}ND{number}.md
            return Path("opin/markdown") / c["year"] / f"{c['year']}ND{c['number']}.md"
        elif "reporter" in c and "volume" in c and "page" in c:
            reporter = c["reporter"]
            rdir = _reporter_dir(reporter)
            if reporter in _ND_REPORTERS:
                return Path("opin") / rdir / c["volume"] / f"{c['page']}.md"
            elif reporter in _FEDERAL_REPORTERS:
                return Path("federal") / rdir / c["volume"] / f"{c['page']}.md"
            else:
                return Path("reporter") / rdir / c["volume"] / f"{c['page']}.md"
        return None

    if citation.cite_type == CitationType.STATUTE:
        if citation.jurisdiction == "nd":
            # NDCC: ndcc/title-{t}/chapter-{t}-{ch}.md
            if "title" in c and "chapter" in c:
                t = f"{c['title']}.{c['title_dec']}" if c.get("title_dec") else c["title"]
                ch = f"{c['chapter']}.{c['chapter_dec']}" if c.get("chapter_dec") else c["chapter"]
                return Path("ndcc") / f"title-{t}" / f"chapter-{t}-{ch}.md"
        elif "title" in c and "section" in c:
            # USC: federal/usc/{title}/{section}.md
            return Path("federal/usc") / c["title"] / f"{c['section']}.md"
        return None

    if citation.cite_type == CitationType.CONSTITUTION:
        if citation.jurisdiction == "nd":
            if "article" in c and "section" in c:
                art_num = roman_to_int(c["article"])
                return Path("cnst") / f"art-{art_num:02d}" / f"sec-{c['section']}.md"
        return None

    if citation.cite_type == CitationType.REGULATION:
        if citation.jurisdiction == "nd" and all(k in c for k in ("part1", "part2", "part3")):
            # NDAC: ndac/title-{p1}/article-{p1}-{p2}/chapter-{p1}-{p2}-{p3}.md
            return (Path("ndac") / f"title-{c['part1']}"
                    / f"article-{c['part1']}-{c['part2']}"
                    / f"chapter-{c['part1']}-{c['part2']}-{c['part3']}.md")
        elif "title" in c and "section" in c:
            return Path("federal/cfr") / c["title"] / f"{c['section']}.md"
        return None

    if citation.cite_type == CitationType.COURT_RULE:
        rule_set = c.get("rule_set", "")
        rule_parts = c.get("parts", [])
        if rule_set and rule_parts:
            if rule_set == "ndstdsimposinglawyersanctions":
                filename = f"rule-{'-'.join(rule_parts)}.md"
            elif rule_set == "ndcodejudconduct":
                filename = f"rule-{rule_parts[0]}.md"
            elif rule_set == "rltdpracticeoflawbylawstudents":
                arabic = roman_to_int(rule_parts[0])
                filename = f"rule-{arabic}.md" if arabic else f"rule-{rule_parts[0]}.md"
            else:
                filename = f"rule-{'.'.join(rule_parts)}.md"
            return Path("rule") / rule_set / filename
        return None

    return None


def resolve_local(citation: Citation, refs_dir: Path | None = None) -> Path | None:
    """Check if a citation has a local cached file.

    Returns the full path if found, None otherwise.
    """
    if refs_dir is None:
        refs_dir = DEFAULT_REFS_DIR

    rel = _citation_path(citation)
    if rel is None:
        return None

    full = refs_dir / rel
    if full.is_file():
        return full
    return None


def cache_content(
    citation: Citation,
    content: str,
    refs_dir: Path | None = None,
    source_url: str | None = None,
    content_type: str = "text/markdown",
) -> Path | None:
    """Write content to the local cache and create a .meta.json sidecar.

    Returns the path written, or None if the citation can't be mapped to a path.
    """
    if refs_dir is None:
        refs_dir = DEFAULT_REFS_DIR

    rel = _citation_path(citation)
    if rel is None:
        return None

    full = refs_dir / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")

    # Write sidecar metadata
    meta = {
        "citation": citation.normalized,
        "source_url": source_url or (citation.sources[0].url if citation.sources else None),
        "fetched": datetime.now(timezone.utc).isoformat(),
        "content_type": content_type,
    }
    meta_path = full.with_suffix(full.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return full


def read_meta(path: Path) -> dict | None:
    """Read the .meta.json sidecar for a cached file."""
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    if meta_path.is_file():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return None


def is_stale(citation: Citation, path: Path) -> bool | None:
    """Check if a cached file is stale based on staleness policy.

    Returns True if stale, False if fresh, None if no metadata or no policy.
    """
    max_days = STALENESS_DAYS.get(citation.cite_type)
    if max_days is None:
        return False  # permanent content

    meta = read_meta(path)
    if not meta or "fetched" not in meta:
        return None

    fetched = datetime.fromisoformat(meta["fetched"])
    age = (datetime.now(timezone.utc) - fetched).days
    return age > max_days


def add_local_source(citation: Citation, path: Path) -> None:
    """Add a local file source to the front of a citation's sources list."""
    local_url = path.as_uri()
    # Don't add duplicate
    if any(s.name == "local" for s in citation.sources):
        return
    citation.sources.insert(0, Source(name="local", url=local_url))


def fetch_and_cache(
    citation: Citation,
    refs_dir: Path | None = None,
    timeout: float = 10.0,
) -> Path | None:
    """Fetch citation content from its primary web source and cache locally.

    Downloads the content at the citation's first non-local source URL,
    writes it to the cache, and adds a local Source to the citation.

    Returns the cached file path, or None if fetching fails or the
    citation can't be mapped to a cache path.
    """
    if refs_dir is None:
        refs_dir = DEFAULT_REFS_DIR

    # Don't fetch if already cached
    existing = resolve_local(citation, refs_dir)
    if existing is not None:
        add_local_source(citation, existing)
        return existing

    # Find a web source URL
    source_url = None
    for s in citation.sources:
        if s.name != "local":
            source_url = s.url
            break
    if source_url is None:
        return None

    # Fetch
    try:
        resp = httpx.get(source_url, follow_redirects=True, timeout=timeout)
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException):
        return None

    content = resp.text
    content_type = resp.headers.get("content-type", "text/html").split(";")[0].strip()

    # Convert HTML to markdown for readable caching
    if content_type == "text/html":
        from markdownify import markdownify
        content = markdownify(content, strip=["img", "script", "style"]).strip()
        content_type = "text/markdown"

    path = cache_content(citation, content, refs_dir, source_url=source_url,
                         content_type=content_type)
    if path is not None:
        add_local_source(citation, path)
    return path
