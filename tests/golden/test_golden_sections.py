import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.golden
CASES = json.loads((Path(__file__).parent / "fixtures/sections.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['act']}-s{c['number']}")
def test_section_matches_hand_checked_fixture(parsed, case):
    act, _ = parsed[case["act"]]
    s = act.get(case["number"])
    assert s is not None, "section not parsed"
    if "title" in case:
        assert s.title == case["title"]
    if "title_startswith" in case:
        assert s.title.startswith(case["title_startswith"])
    if "title_endswith" in case:
        assert s.title.rstrip(".").endswith(case["title_endswith"])
    if "chapter" in case:
        assert s.chapter == case["chapter"]
    if "pages" in case:
        assert list(s.pages) == case["pages"]
    if "status" in case:
        assert s.status.value == case["status"]
    if "flags" in case:
        assert list(s.flags) == case["flags"]
    flat = " ".join(s.text.split())
    for snippet in case.get("contains", []):
        assert snippet in flat, f"missing text: {snippet!r}"
    for snippet in case.get("footnote_contains", []):
        assert any(snippet in f.text for f in s.footnotes), f"missing footnote: {snippet!r}"
    for btype, n in case.get("block_types_include", {}).items():
        assert sum(b.type.value == btype for b in s.blocks) >= n, f"expected >= {n} {btype} blocks"
    for snippet in case.get("text_not_contains", []):
        assert snippet not in flat, f"leaked text: {snippet!r}"
    if "subheading" in case:
        assert s.subheading == case["subheading"]
    if "footnote_count" in case:
        assert len(s.footnotes) == case["footnote_count"], [f.text[:40] for f in s.footnotes]
    if case.get("no_blocks"):
        assert not s.blocks


def test_absent_and_omitted(parsed):
    fx = json.loads((Path(__file__).parent / "fixtures/sections.json").read_text(encoding="utf-8"))
    for code, nums in fx["absent_numbers"].items():
        act, _ = parsed[code]
        for n in nums:
            assert act.get(n) is None and act.is_omitted(n)
    for code, ranges in fx["omitted_ranges"].items():
        act, _ = parsed[code]
        assert [[r.first, r.last] for r in act.omitted_ranges] == ranges
