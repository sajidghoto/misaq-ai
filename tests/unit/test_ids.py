import pytest

from misaq.domain.ids import chunk_id, normalize_number, number_sort_key, parse_section_id, section_id

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("raw,want", [("5", "5"), (" 5 ", "5"), ("27 (A)", "27A"),
                                      ("27(a)", "27A"), ("16a", "16A"), ("178A", "178A")])
def test_normalize_number(raw, want):
    assert normalize_number(raw) == want


@pytest.mark.parametrize("bad", ["", "A5", "5.", "5AB", "five", "5 6"])
def test_normalize_number_rejects(bad):
    with pytest.raises(ValueError):
        normalize_number(bad)


def test_section_id_roundtrip():
    sid = section_id("CA1872", "19a")
    assert sid == "CA1872:s19A"
    assert parse_section_id(sid) == ("CA1872", "19A")


@pytest.mark.parametrize("bad", ["CA1872:19", "ca1872:s19", "CA1872:s", "s19"])
def test_parse_section_id_rejects(bad):
    with pytest.raises(ValueError):
        parse_section_id(bad)


def test_sort_key_orders_lettered_sections_after_plain():
    nums = ["19A", "20", "19", "178A", "178", "9"]
    assert sorted(nums, key=number_sort_key) == ["9", "19", "19A", "20", "178", "178A"]


def test_chunk_id_format():
    assert chunk_id("SGA1930:s16A", "section", 2) == "SGA1930:s16A#section-002"
