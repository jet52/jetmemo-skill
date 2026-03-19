"""CLI entry point for jetcite."""

from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path

import click

from jetcite.models import Citation
from jetcite.resolver import verify_citations_sync
from jetcite.scanner import lookup, scan_text


def _format_url(cite: Citation) -> str:
    """Return the primary URL for a citation."""
    if cite.sources:
        return cite.sources[0].url
    return "(no URL)"


def _format_table(citations: list[Citation], all_sources: bool = False) -> str:
    """Format citations as a human-readable table."""
    if not citations:
        return "No citations found."

    lines = []
    lines.append(f"  {'#':>3}  {'Citation':<30} {'Type':<14} URL")
    lines.append(f"  {'─' * 3}  {'─' * 30} {'─' * 14} {'─' * 50}")

    for i, cite in enumerate(citations, 1):
        url = _format_url(cite)
        verified = ""
        if cite.sources and cite.sources[0].verified is not None:
            verified = " ✓" if cite.sources[0].verified else " ✗"
        lines.append(f"  {i:>3}  {cite.normalized:<30} {cite.cite_type.value:<14} {url}{verified}")

        if cite.parallel_cites:
            lines.append(f"       {'':30} {'= ' + ', '.join(cite.parallel_cites)}")

        if all_sources and len(cite.sources) > 1:
            for src in cite.sources[1:]:
                v = ""
                if src.verified is not None:
                    v = " ✓" if src.verified else " ✗"
                lines.append(f"       {'':30} {'':14} {src.url}{v}")

    return "\n".join(lines)


def _format_json(citations: list[Citation]) -> str:
    """Format citations as JSON."""
    return json.dumps([c.to_dict() for c in citations], indent=2)


@click.command()
@click.argument("citation", required=False)
@click.option("--scan", "scan_file", type=str,
              help="Scan a document file for citations (use '-' for stdin).")
@click.option("--format", "fmt", type=click.Choice(["url", "json", "table"]),
              default=None, help="Output format.")
@click.option("--verify", is_flag=True, help="HTTP-verify each URL.")
@click.option("--open", "open_url", is_flag=True, help="Open the first URL in browser.")
@click.option("--from-clipboard", is_flag=True, help="Read citation from clipboard.")
@click.option("--all-sources", is_flag=True, help="Show all available URLs.")
@click.option("--refs-dir", type=click.Path(exists=False), default=None,
              help="Check local reference cache at this directory.")
@click.option("--fetch", "do_fetch", is_flag=True,
              help="Fetch citation content from web and cache locally (requires --refs-dir).")
def main(
    citation: str | None,
    scan_file: str | None,
    fmt: str | None,
    verify: bool,
    open_url: bool,
    from_clipboard: bool,
    all_sources: bool,
    refs_dir: str | None,
    do_fetch: bool,
):
    """Parse legal citations and generate URLs to official sources."""
    refs_path = Path(refs_dir).expanduser() if refs_dir else None

    if do_fetch and refs_path is None:
        click.echo("Error: --fetch requires --refs-dir", err=True)
        sys.exit(1)

    # Determine input
    if scan_file:
        if scan_file == "-":
            text = sys.stdin.read()
        else:
            with open(scan_file) as f:
                text = f.read()
        citations = scan_text(text, refs_dir=refs_path)
        if fmt is None:
            fmt = "table"
    elif from_clipboard:
        try:
            import pyperclip
            citation = pyperclip.paste().strip()
        except ImportError:
            click.echo("Error: install pyperclip for clipboard support: pip install pyperclip",
                        err=True)
            sys.exit(1)
        except pyperclip.PyperclipException as e:
            click.echo(f"Error: could not read from clipboard: {e}", err=True)
            sys.exit(1)

    if not scan_file:
        if citation is None and not from_clipboard:
            # Try reading from stdin if piped
            if not sys.stdin.isatty():
                citation = sys.stdin.read().strip()
            else:
                click.echo("Usage: jetcite <citation> or jetcite --scan <file>", err=True)
                sys.exit(1)

        if citation:
            result = lookup(citation, refs_dir=refs_path)
            if result:
                citations = [result]
            else:
                click.echo(f"No citation pattern matched: {citation}", err=True)
                sys.exit(1)
        else:
            click.echo("No citation provided.", err=True)
            sys.exit(1)

        if fmt is None:
            fmt = "url"

    # Verify if requested
    if verify:
        verify_citations_sync(citations, rate_limit=1.0)

    # Fetch and cache if requested
    if do_fetch and refs_path:
        from jetcite.cache import fetch_and_cache
        for cite in citations:
            cached = fetch_and_cache(cite, refs_dir=refs_path)
            if cached:
                click.echo(f"Cached: {cite.normalized} -> {cached}", err=True)

    # Open URL
    if open_url and citations and citations[0].sources:
        webbrowser.open(citations[0].sources[0].url)

    # Output
    if fmt == "json":
        click.echo(_format_json(citations))
    elif fmt == "table":
        click.echo(_format_table(citations, all_sources=all_sources))
    else:  # url
        for cite in citations:
            click.echo(_format_url(cite))


if __name__ == "__main__":
    main()
