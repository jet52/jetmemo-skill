"""CourtListener URL generation for case citations.

The /c/ redirect URLs are lightweight browser-facing links that resolve to
the opinion page. For programmatic verification or bulk lookups,
CourtListener's Citation Lookup API is preferred:

    POST https://www.courtlistener.com/api/rest/v4/citation-lookup/
    (requires auth token, 60 citations/min, 250 per request)

We generate /c/ URLs for display and avoid HEAD-requesting them in verify
mode when an alternative authoritative source exists.
"""

from urllib.parse import quote


def courtlistener_url(reporter: str, volume: str, page: str) -> str:
    """Generate a CourtListener URL for a case citation."""
    encoded = quote(reporter, safe="")
    return f"https://www.courtlistener.com/c/{encoded}/{volume}/{page}/"


def courtlistener_neutral_url(jurisdiction: str, year: str, number: str) -> str:
    """Generate a CourtListener URL for a neutral citation."""
    return f"https://www.courtlistener.com/c/{jurisdiction}/{year}/{number}/"
