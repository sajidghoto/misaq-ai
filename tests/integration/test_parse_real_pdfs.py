import pytest

from conftest import RAW
from misaq.domain.enums import SectionStatus
from misaq.domain.errors import DataValidationError
from misaq.domain.statute import Act
from misaq.validation.statutes import build_report, check_source_hashes, require_ok

pytestmark = pytest.mark.integration


def test_source_hashes_match():
    check_source_hashes(RAW)


@pytest.mark.parametrize("code,toc,parsed_n", [("SGA1930", 68, 68), ("SRA1877", 51, 51), ("CA1872", 194, 195)])
def test_every_contents_entry_parsed(parsed, code, toc, parsed_n):
    act, report = parsed[code]
    assert report.ok and report.toc_entries == toc and report.parsed_sections == parsed_n
    assert len(act.sections) == parsed_n
    assert not report.empty_sections


def test_only_known_section_is_missing_from_contents(parsed):
    _, report = parsed["CA1872"]
    assert report.accepted_not_in_contents == ("141",)
    assert not parsed["SGA1930"][1].accepted_not_in_contents


def test_section_numbers_strictly_increase(parsed):
    from misaq.domain.ids import number_sort_key
    for act, _ in parsed.values():
        keys = [number_sort_key(s.number) for s in act.sections]
        assert keys == sorted(keys) and len(set(keys)) == len(keys)


def test_only_expected_sections_are_not_in_force(parsed):
    got = {(a.code.value, s.number) for a, _ in parsed.values() for s in a.sections
           if s.status is not SectionStatus.IN_FORCE}
    assert got == {("SGA1930", "65"), ("SRA1877", "2")}


def test_no_footnote_markers_leaked_into_numbers_or_titles(parsed):
    import re
    for act, _ in parsed.values():
        for s in act.sections:
            assert re.fullmatch(r"\d+[A-Z]?", s.number), s.id
            assert not re.match(r"^\d", s.title), f"{s.id} title starts with a digit: {s.title!r}"
            if s.status is SectionStatus.IN_FORCE:
                assert not s.title.startswith("["), f"{s.id} title starts with a bracket"


def test_act_json_roundtrip_on_real_data(parsed):
    for act, _ in parsed.values():
        assert Act.from_dict(act.to_dict()) == act


def test_validation_fails_loudly_when_contents_entry_missing():
    toc = [dict(number="1", title="A", chapter=None, extra=[]), dict(number="2", title="B", chapter=None, extra=[])]
    raw = [dict(number="1", title_body="A.", blocks=[dict(type="body", text="x")])]
    from misaq.domain.enums import ActCode
    report = build_report(ActCode.CA1872, toc, raw, ["2"], [], [])
    assert not report.ok
    with pytest.raises(DataValidationError) as e:
        require_ok(report)
    assert "2" in " ".join(e.value.failures)


# ---------------- stage 3: processing ----------------
def test_processed_data_passes_the_gate_and_every_marker_resolves(pipeline):
    from misaq.validation.processed import validate_processed
    for code, (act, _, prep) in pipeline.items():
        assert prep.footnotes.unresolved == (), code
        assert validate_processed(act, prep.footnotes.unresolved) == [], code


def test_hyphen_decisions_on_real_text(pipeline):
    ca = pipeline["CA1872"][2].hyphen_decisions
    actions = {d.action for d in ca}
    assert len(ca) == 18 and actions == {"join", "keep"}          # no ambiguous cases
    assert {(d.left + d.right).lower() for d in ca if d.action == "keep"} == {
        "subjectmatter", "nonperformance", "onequarter", "twothirds"}
    assert all(not d.action == "ambiguous" for d in pipeline["SGA1930"][2].hyphen_decisions)


def test_act_level_notes_are_kept_not_dropped(pipeline):
    assert len(pipeline["SGA1930"][0].notes) == 1
    assert "Phulera" in pipeline["SGA1930"][0].notes[0].text
    assert any("Partnership Act" in n.text for n in pipeline["CA1872"][0].notes)


def test_every_footnote_is_accounted_for(pipeline):
    """Printed footnotes = attached to a section or kept as an Act note. None silently lost."""
    for code, (act, _, prep) in pipeline.items():
        attached = {(f.page, f.marker, f.text) for s in act.sections for f in s.footnotes}
        notes = {(n.page, n.marker, n.text) for n in act.notes}
        assert not attached & notes, code
        assert len(notes) == len(prep.footnotes.orphans), code


def test_frozen_processed_data_is_in_sync_with_the_code(pipeline):
    import json

    from conftest import ROOT
    for code, (act, _, _) in pipeline.items():
        p = ROOT / "data/processed/statutes" / f"{code}.json"
        assert p.exists(), f"run `make parse` and commit {p}"
        assert Act.from_dict(json.loads(p.read_text(encoding="utf-8"))) == act, (
            f"{code}: data/processed is stale. Re-run `make parse` and commit the change on purpose.")
