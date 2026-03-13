#!/usr/bin/env python3
"""
extract_text - Try multiple PDF text extractors in priority order.

Extracts per-page, scores each page individually, and picks the best
extractor based on text-bearing pages. Pages with little or no text
(scanned exhibits, images) are flagged for visual read.

Writes the best extraction to <file>.txt. Exits 0 if usable text was
extracted, 1 if all extractors produced poor output (needs visual read).

Usage:
    python3 extract_text.py <file>.pdf [<file2>.pdf ...]
    python3 extract_text.py --list-extractors
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

__version__ = "1.1.0"

# --- Quality thresholds ---
GOOD_WPL = 5.0  # words/line: stop immediately
MARGINAL_WPL = 3.0  # words/line: keep looking but stash as candidate
GARBLED_RATIO_MAX = 0.05  # max fraction of garbled characters
# Per-page: minimum chars to consider a page "text-bearing" vs "sparse"
PAGE_MIN_CHARS = 50


# --- Per-page quality ---


@dataclass
class PageScore:
    page_num: int  # 1-indexed
    text: str
    words_per_line: float
    char_count: int
    garbled_ratio: float

    @property
    def is_sparse(self) -> bool:
        """Page has too little text to evaluate — likely scanned/image."""
        return self.char_count < PAGE_MIN_CHARS

    @property
    def is_good(self) -> bool:
        return (
            not self.is_sparse
            and self.words_per_line >= GOOD_WPL
            and self.garbled_ratio <= GARBLED_RATIO_MAX
        )

    @property
    def is_marginal(self) -> bool:
        return (
            not self.is_sparse
            and self.words_per_line >= MARGINAL_WPL
            and self.garbled_ratio <= GARBLED_RATIO_MAX
        )


@dataclass
class ExtractionResult:
    extractor: str
    pages: list[PageScore]

    @property
    def text_pages(self) -> list[PageScore]:
        """Pages with enough text to score."""
        return [p for p in self.pages if not p.is_sparse]

    @property
    def sparse_pages(self) -> list[PageScore]:
        """Pages with little/no text (scanned, images)."""
        return [p for p in self.pages if p.is_sparse]

    @property
    def good_pages(self) -> list[PageScore]:
        return [p for p in self.pages if p.is_good]

    @property
    def poor_pages(self) -> list[PageScore]:
        """Text-bearing pages that scored poorly."""
        return [p for p in self.text_pages if not p.is_good and not p.is_marginal]

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def total_chars(self) -> int:
        return sum(p.char_count for p in self.pages)

    @property
    def avg_wpl(self) -> float:
        """Average words/line across text-bearing pages only."""
        tp = self.text_pages
        if not tp:
            return 0.0
        return sum(p.words_per_line for p in tp) / len(tp)

    @property
    def is_good(self) -> bool:
        """Good if most text-bearing pages are good."""
        tp = self.text_pages
        if not tp:
            return False
        good_frac = len(self.good_pages) / len(tp)
        return good_frac >= 0.7

    @property
    def is_marginal(self) -> bool:
        tp = self.text_pages
        if not tp:
            return False
        marginal_or_better = [p for p in tp if p.is_marginal or p.is_good]
        return len(marginal_or_better) / len(tp) >= 0.5

    @property
    def score(self) -> float:
        """Higher is better. Used to compare extractors."""
        tp = self.text_pages
        if not tp:
            return 0.0
        return sum(p.words_per_line for p in tp if p.is_good or p.is_marginal) / len(tp)

    @property
    def visual_read_pages(self) -> list[int]:
        """1-indexed page numbers that need visual read."""
        pages = []
        for p in self.pages:
            if p.is_sparse or (not p.is_sparse and not p.is_marginal):
                pages.append(p.page_num)
        return pages

    def visual_read_ranges(self) -> str:
        """Compact string like '31-40, 45' for visual read pages."""
        nums = self.visual_read_pages
        if not nums:
            return ""
        ranges = []
        start = nums[0]
        prev = nums[0]
        for n in nums[1:]:
            if n == prev + 1:
                prev = n
            else:
                ranges.append(f"{start}" if start == prev else f"{start}-{prev}")
                start = n
                prev = n
        ranges.append(f"{start}" if start == prev else f"{start}-{prev}")
        return ", ".join(ranges)


# --- Scoring helpers ---


def _compute_garbled_ratio(text: str) -> float:
    """Fraction of characters that are likely garbled/non-printable."""
    if not text:
        return 1.0
    garbled = 0
    total = 0
    for ch in text:
        if ch in ("\n", "\r", "\t", " "):
            continue
        total += 1
        cat = unicodedata.category(ch)
        # Cc=control, Co=private use, Cn=unassigned, Cs=surrogate
        if cat.startswith(("Cc", "Co", "Cn", "Cs")):
            garbled += 1
        elif ch == "\ufffd":
            garbled += 1
    return garbled / total if total > 0 else 1.0


def _compute_words_per_line(text: str) -> float:
    """Average words per non-empty line."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    total_words = sum(len(ln.split()) for ln in lines)
    return total_words / len(lines)


def _score_page(page_num: int, text: str) -> PageScore:
    return PageScore(
        page_num=page_num,
        text=text,
        words_per_line=_compute_words_per_line(text),
        char_count=len(text),
        garbled_ratio=_compute_garbled_ratio(text),
    )


# --- Extractors ---
# Each returns a list of per-page text strings, or None if unavailable.


def _extract_pdftotext(pdf_path: Path) -> list[str] | None:
    """Poppler pdftotext CLI. Split pages on form feed characters."""
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return None
    try:
        result = subprocess.run(
            [pdftotext, str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout:
            # pdftotext inserts \f between pages
            pages = result.stdout.split("\f")
            # Remove trailing empty element from final \f
            if pages and not pages[-1].strip():
                pages = pages[:-1]
            return pages if pages else None
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _extract_pypdf(pdf_path: Path) -> list[str] | None:
    """pypdf pure-Python extraction."""
    try:
        import pypdf
    except ImportError:
        return None
    try:
        reader = pypdf.PdfReader(str(pdf_path))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        return pages if pages else None
    except Exception:
        return None


def _extract_pymupdf(pdf_path: Path) -> list[str] | None:
    """PyMuPDF (fitz) extraction."""
    try:
        import fitz
    except ImportError:
        return None
    try:
        doc = fitz.open(str(pdf_path))
        pages = []
        for page in doc:
            text = page.get_text() or ""
            pages.append(text)
        doc.close()
        return pages if pages else None
    except Exception:
        return None


def _extract_pdfplumber(pdf_path: Path) -> list[str] | None:
    """pdfplumber extraction (optional dependency)."""
    try:
        import pdfplumber
    except ImportError:
        return None
    try:
        pages = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
        return pages if pages else None
    except Exception:
        return None


def _extract_marker(pdf_path: Path) -> list[str] | None:
    """marker_single CLI (slow, ML-based). Returns whole doc as single page."""
    marker_bin = shutil.which("marker_single")
    if not marker_bin:
        return None
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    marker_bin,
                    str(pdf_path),
                    "--output_format",
                    "markdown",
                    "--disable_image_extraction",
                    "--output_dir",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                return None
            out_dir = Path(tmpdir)
            md_files = list(out_dir.rglob("*.md"))
            if md_files:
                text = md_files[0].read_text(encoding="utf-8")
                # marker doesn't provide per-page splits, return as one block
                return [text] if text else None
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


# Ordered extraction pipeline
EXTRACTORS = [
    ("pdftotext", _extract_pdftotext),
    ("pypdf", _extract_pypdf),
    ("PyMuPDF", _extract_pymupdf),
    ("pdfplumber", _extract_pdfplumber),
    ("marker", _extract_marker),
]


def list_extractors() -> list[tuple[str, bool]]:
    """Return list of (name, available) for all extractors."""
    availability = []
    for name, _ in EXTRACTORS:
        if name == "pdftotext":
            available = shutil.which("pdftotext") is not None
        elif name == "pypdf":
            try:
                import pypdf  # noqa: F401
                available = True
            except ImportError:
                available = False
        elif name == "PyMuPDF":
            try:
                import fitz  # noqa: F401
                available = True
            except ImportError:
                available = False
        elif name == "pdfplumber":
            try:
                import pdfplumber  # noqa: F401
                available = True
            except ImportError:
                available = False
        elif name == "marker":
            available = shutil.which("marker_single") is not None
        else:
            available = False
        availability.append((name, available))
    return availability


def extract_pdf(pdf_path: Path, verbose: bool = True) -> ExtractionResult | None:
    """Try extractors in priority order. Return best result or None."""
    best: ExtractionResult | None = None

    for name, func in EXTRACTORS:
        if verbose:
            print(f"  Trying {name}...", end=" ", flush=True)

        page_texts = func(pdf_path)

        if page_texts is None:
            if verbose:
                print("not available" if name != "marker" else "skipped/failed")
            continue

        pages = [_score_page(i + 1, text) for i, text in enumerate(page_texts)]
        result = ExtractionResult(extractor=name, pages=pages)

        n_text = len(result.text_pages)
        n_good = len(result.good_pages)
        n_sparse = len(result.sparse_pages)
        n_poor = len(result.poor_pages)

        if verbose:
            status = "good" if result.is_good else ("marginal" if result.is_marginal else "poor")
            parts = [f"{result.avg_wpl:.1f} avg words/line"]
            parts.append(f"{len(pages)} pages ({n_text} text, {n_sparse} sparse)")
            if n_text:
                parts.append(f"{n_good}/{n_text} good")
            if n_poor:
                parts.append(f"{n_poor} poor")
            print(f"{', '.join(parts)} — {status}")

        if result.is_good:
            return result

        if result.is_marginal and (best is None or result.score > best.score):
            best = result

    return best


def process_pdf(pdf_path: Path, verbose: bool = True) -> bool:
    """Extract text from a PDF. Returns True if usable text was produced."""
    txt_path = pdf_path.with_suffix(".txt")

    if verbose:
        print(f"\n{pdf_path.name}:")

    result = extract_pdf(pdf_path, verbose=verbose)

    if result is None:
        if verbose:
            print(f"  All extractors failed — needs visual read")
        return False

    txt_path.write_text(result.full_text, encoding="utf-8")

    if verbose:
        label = "good" if result.is_good else "marginal (best available)"
        print(f"  Winner: {result.extractor} — {result.avg_wpl:.1f} avg words/line — {label}")

        vr = result.visual_read_ranges()
        if vr:
            print(f"  Visual read needed for pages: {vr}")

        print(f"  Wrote {txt_path.name}")

    # Write a sidecar JSON with per-page quality info for the orchestrator
    meta_path = pdf_path.with_suffix(".extraction.json")
    meta = {
        "extractor": result.extractor,
        "total_pages": len(result.pages),
        "text_pages": len(result.text_pages),
        "sparse_pages": len(result.sparse_pages),
        "avg_words_per_line": round(result.avg_wpl, 1),
        "quality": "good" if result.is_good else "marginal",
        "visual_read_pages": result.visual_read_pages,
        "visual_read_ranges": result.visual_read_ranges(),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Extract text from PDFs using the best available method."
    )
    parser.add_argument("pdfs", nargs="*", type=Path, help="PDF files to extract")
    parser.add_argument(
        "--list-extractors",
        action="store_true",
        help="Show available extractors and exit",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress progress output"
    )
    args = parser.parse_args()

    if args.list_extractors:
        print("Available PDF text extractors (in priority order):")
        for name, available in list_extractors():
            status = "available" if available else "not installed"
            print(f"  {name}: {status}")
        sys.exit(0)

    if not args.pdfs:
        parser.error("No PDF files specified")

    verbose = not args.quiet
    any_failed = False

    for pdf_path in args.pdfs:
        if not pdf_path.exists():
            print(f"Error: {pdf_path} not found", file=sys.stderr)
            any_failed = True
            continue
        if not pdf_path.suffix.lower() == ".pdf":
            print(f"Warning: {pdf_path} does not have .pdf extension", file=sys.stderr)

        success = process_pdf(pdf_path, verbose=verbose)
        if not success:
            any_failed = True

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
