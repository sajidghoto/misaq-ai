import pytest

from misaq.domain.enums import ActCode, BlockType, SectionStatus
from misaq.domain.statute import Act, Block, Footnote, FootnoteRef, Section
from misaq.processing.pipeline import process_acts

pytestmark = pytest.mark.unit


def _section(number, text, *, status=SectionStatus.UNKNOWN, footnotes=(), refs=()):
    return Section(
        act=ActCode.CA1872,
        number=number,
        title="title",
        title_in_body="title",
        chapter=None,
        subheading=None,
        status=status,
        pages=(1,),
        blocks=(Block(BlockType.BODY, text),),
        footnotes=tuple(footnotes),
        footnote_refs=tuple(refs),
    )


def test_process_acts_aggregates_status_footnote_and_hyphen_reports():
    cited = Footnote(1, "note", "1")
    first = _section(
        "1",
        "a res-\npectively clause",
        footnotes=(cited,),
        refs=(FootnoteRef(1, "1"),),
    )
    second = _section("2", "respectively")
    act = Act(ActCode.CA1872, "x.pdf", "0" * 64, (first, second))

    processed, report = process_acts({ActCode.CA1872: act})[ActCode.CA1872]

    assert [s.status for s in processed.sections] == [SectionStatus.IN_FORCE] * 2
    assert report.status_counts == {"in_force": 2}
    assert report.footnotes.attached == 1
    assert report.footnotes.sections_with_notes == 1
    assert processed.sections[0].text == "a respectively clause"
    assert report.hyphen_decisions[0].action == "join"


def test_process_report_serialises_hyphen_counts():
    section = _section("1", "a zorb-\nquantum clause")
    act = Act(ActCode.CA1872, "x.pdf", "0" * 64, (section,))

    _, report = process_acts({ActCode.CA1872: act})[ActCode.CA1872]

    assert report.to_dict()["hyphens"]["counts"] == {"ambiguous": 1}
