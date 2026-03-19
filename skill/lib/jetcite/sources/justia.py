"""Justia URL generation for U.S. Reports citations."""


def us_reports_url(volume: str, page: str) -> str:
    """Generate a Justia URL for a U.S. Reports citation."""
    return f"https://supreme.justia.com/cases/federal/us/{volume}/{page}"
