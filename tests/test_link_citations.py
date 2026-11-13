"""Regression tests for skill/scripts/link_citations.py.

Run: python3 -m pytest tests/  (or python3 tests/test_link_citations.py)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skill" / "scripts"))

from link_citations import link_citations, link_id_cites  # noqa: E402

URL = "https://example.test/a"


def _id(text, memo, parent="2024 ND 1", **extra):
    """A memo-scan pin entry for the first occurrence of `text` in `memo`."""
    return {"cite_text": text, "cite_type": "pin_cite", "url": URL,
            "parent_normalized": parent, "position": memo.index(text), **extra}


def _full(text, memo, normalized=None):
    return {"cite_text": text, "cite_type": "case", "url": URL,
            "normalized": normalized or text, "position": memo.index(text)}


def test_id_from_brief_never_links_inside_words():
    memo = "The court said it did not avoid a valid mid-ruling point."
    cites = [{"cite_text": "id.", "url": URL}, {"cite_text": "Id.", "url": URL},
             {"cite_text": "*Id.* ¶ 4", "url": URL}]
    assert link_citations(memo, cites) == memo


def test_map_pattern_needs_leading_boundary():
    memo = "Subrule 5 differs from Rule 5 here."
    out = link_citations(memo, [{"cite_text": "Rule 5", "url": URL}])
    assert out == f"Subrule 5 differs from [Rule 5]({URL}) here."


def test_id_linked_at_its_offset_only():
    memo = "A, 2024 ND 1, ¶ 3. *Id.* ¶ 4. B, 2024 ND 2, ¶ 5. *Id.*"
    first = _id("*Id.* ¶ 4", memo, pin_paragraph="4")
    out, skipped = link_id_cites(memo, [_full("2024 ND 1", memo), first])
    assert skipped == []
    assert out == (f"A, 2024 ND 1, ¶ 3. *[Id.]({URL})* ¶ 4. "
                   "B, 2024 ND 2, ¶ 5. *Id.*")


def test_id_after_brief_cite_is_skipped_with_its_chain():
    memo = "A, 2024 ND 1, ¶ 3. At. Br. 18, ¶ 28. *Id.* ¶ 29. *Id.* ¶ 30."
    e1 = _id("*Id.* ¶ 29", memo, pin_paragraph="29")
    e2 = _id("*Id.* ¶ 30", memo, pin_paragraph="30")
    out, skipped = link_id_cites(memo, [_full("2024 ND 1", memo), e1, e2])
    assert out == memo and len(skipped) == 2


def test_paragraph_pin_needs_paragraph_numbered_parent():
    memo = "N.D.R.Crim.P. 30. *Id.* ¶ 16."
    e = _id("*Id.* ¶ 16", memo, parent="N.D.R.Crim.P. 30", pin_paragraph="16")
    out, skipped = link_id_cites(memo, [e])
    assert out == memo and len(skipped) == 1


def test_stale_offset_is_skipped():
    memo = "A, 2024 ND 1, ¶ 3. Id."
    e = _id("Id.", memo)
    e["position"] += 2
    out, skipped = link_id_cites(memo, [e])
    assert out == memo and len(skipped) == 1


def test_id_pass_then_map_pass_compose():
    memo = "A, 2024 ND 1, ¶ 3. Id. ¶ 4."
    full = _full("2024 ND 1", memo)
    out, _ = link_id_cites(memo, [full, _id("Id. ¶ 4", memo, pin_paragraph="4")])
    out = link_citations(out, [full])
    assert out == f"A, [2024 ND 1]({URL}), ¶ 3. [Id.]({URL}) ¶ 4."


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
