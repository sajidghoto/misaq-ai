import pytest

from misaq.domain.enums import ActCode, BlockType, SectionStatus
from misaq.domain.statute import Act, Block, OmittedRange, Section
from misaq.processing.status import classify

pytestmark = pytest.mark.unit


def _sec(number, title, text=None, act=ActCode.SGA1930):
    blocks = (Block(BlockType.BODY, text),) if text else ()
    return Section(act=act, number=number, title=title, title_in_body=title, chapter=None,
                   subheading=None, status=SectionStatus.UNKNOWN, pages=(1,), blocks=blocks)


def _act(*secs, omitted=()):
    return Act(code=ActCode.SGA1930, source_file="x.pdf", source_sha256="0" * 64,
               sections=tuple(secs), omitted_ranges=tuple(omitted))


def test_repealed_title():
    s = _sec("65", "[Repealed]")
    assert classify(s, _act(s)) is SectionStatus.REPEALED


def test_repealed_by_body_text():
    s = _sec("2", "[Repealed.]", "[Repeal of enactments.] Rep. by the Amending Act, 1891 (XII of 1891).")
    assert classify(s, _act(s)) is SectionStatus.REPEALED


def test_normal_section_is_in_force():
    s = _sec("5", "Contract of sale how made", "A contract of sale is made by an offer.")
    assert classify(s, _act(s)) is SectionStatus.IN_FORCE


def test_word_repeal_inside_long_text_is_not_repeal():
    s = _sec("3", "Application", "The unrepealed provisions of the Contract Act, 1872, shall continue to apply.")
    assert classify(s, _act(s)) is SectionStatus.IN_FORCE


def test_omitted_range_lookup():
    a = _act(omitted=[OmittedRange(45, 51)])
    assert a.is_omitted("46") and not a.is_omitted("44") and not a.is_omitted("52")
    assert a.get("46") is None


def test_section_in_omitted_range_is_omitted():
    s = _sec("46", "Omitted")
    assert classify(s, _act(s, omitted=[OmittedRange(45, 51)])) is SectionStatus.OMITTED
