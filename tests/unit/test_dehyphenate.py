import pytest

from misaq.domain.enums import ActCode, BlockType, SectionStatus
from misaq.domain.statute import Act, Block, Section
from misaq.processing.dehyphenate import build_corpus, decide, dehyphenate_act, dehyphenate_text

pytestmark = pytest.mark.unit

CORPUS = "the respectively clause. a non-performance event. compensation is due. subject-matter here."


def test_join_when_joined_form_seen_elsewhere():
    assert decide("res", "pectively", CORPUS)[0] == "join"
    assert dehyphenate_text("a res-\npectively b", CORPUS)[0] == "a respectively b"


def test_keep_when_hyphenated_form_seen_elsewhere():
    assert decide("non", "performance", CORPUS)[0] == "keep"
    assert dehyphenate_text("the non-\nperformance", CORPUS)[0] == "the non-performance"


def test_no_evidence_is_ambiguous_and_keeps_hyphen():
    out, d = dehyphenate_text("a zorb-\nquantum x", CORPUS)
    assert out == "a zorb-quantum x" and d[0].action == "ambiguous"


def test_conflicting_evidence_is_ambiguous():
    c = "anything and any-thing"
    assert decide("any", "thing", c)[0] == "ambiguous"


def test_does_not_touch_hyphen_before_uppercase_or_non_break():
    t = "sub-agent and Section 5-\n(1) text and re-\nVocation"
    assert dehyphenate_text(t, CORPUS)[0] == t


def test_corpus_does_not_count_the_broken_form_as_evidence():
    sec = Section(act=ActCode.CA1872, number="1", title="t", title_in_body="t", chapter=None, subheading=None,
                  status=SectionStatus.IN_FORCE, pages=(1,), blocks=(Block(BlockType.BODY, "a res-\npectively b"),))
    act = Act(ActCode.CA1872, "f", "0" * 64, (sec,))
    corpus = build_corpus([act])
    assert "respectively" not in corpus and decide("res", "pectively", corpus)[0] == "ambiguous"


def test_act_level_decisions_carry_section_id():
    sec = Section(act=ActCode.CA1872, number="3", title="t", title_in_body="t", chapter=None, subheading=None,
                  status=SectionStatus.IN_FORCE, pages=(1,), blocks=(Block(BlockType.BODY, "x res-\npectively y"),))
    act = Act(ActCode.CA1872, "f", "0" * 64, (sec,))
    new, decisions = dehyphenate_act(act, CORPUS)
    assert new.sections[0].text == "x respectively y" and decisions[0].section_id == "CA1872:s3"
