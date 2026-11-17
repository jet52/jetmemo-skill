"""Regression tests for skill/scripts/md_tidy.py.

Run: python3 -m pytest tests/  (or python3 tests/test_md_tidy.py)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skill" / "scripts"))

from md_tidy import tidy  # noqa: E402


def test_list_under_paragraph_gets_blank_line():
    src = "Intro text:\n- one\n- two\nAfter."
    new, n = tidy(src)
    assert new == "Intro text:\n\n- one\n- two\nAfter."  # lazy continuation stays
    assert n == 1


def test_bold_label_then_list():
    new, _ = tidy("**Strengths**\n- a\n- b\n")
    assert new == "**Strengths**\n\n- a\n- b\n"


def test_heading_gets_blank_lines_both_sides():
    new, n = tidy("text\n### Heading\nbody")
    assert new == "text\n\n### Heading\n\nbody"
    assert n == 2


def test_table_after_paragraph_and_before_text():
    src = "Lead-in:\n| a | b |\n|---|---|\n| 1 | 2 |\nAfter."
    new, _ = tidy(src)
    assert new == "Lead-in:\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nAfter."


def test_fence_contents_untouched():
    src = "Run:\n```bash\n# not a heading\n- not a list\n```\nDone."
    new, _ = tidy(src)
    assert new == "Run:\n\n```bash\n# not a heading\n- not a list\n```\n\nDone."


def test_nested_and_indented_list_lines_untouched():
    src = "- one\n  continuation\n  - nested\n- two\n"
    assert tidy(src) == (src, 0)


def test_blank_placeholders_and_rules_untouched():
    src = "*Boyda*, 2026 ND 197, ___ N.W.3d ___.\n\n---\n\nEnd."
    assert tidy(src) == (src, 0)


def test_front_matter_untouched():
    src = "---\ntitle: x\n---\n# Memo\n"
    new, _ = tidy(src)
    assert new == "---\ntitle: x\n---\n\n# Memo\n"


def test_idempotent():
    src = "Intro:\n- a\n## H\n| x |\n|---|\nText\n```\ncode\n```\nTail"
    once, _ = tidy(src)
    assert tidy(once) == (once, 0)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
