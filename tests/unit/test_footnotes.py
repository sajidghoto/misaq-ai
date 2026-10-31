import pytest

from misaq.domain.enums import ActCode, BlockType, SectionStatus
from misaq.domain.statute import Act, Block, Footnote, FootnoteRef, Section
from misaq.processing.footnotes import attach_footnotes

pytestmark = pytest.mark.unit

POOL = (Footnote(5, "note for A", "2"), Footnote(5, "note for B", "3"), Footnote(5, "title note", "1"))


def _sec(n, refs):
    return Section(act=ActCode.SGA1930, number=n, title="t", title_in_body="t", chapter=None, subheading=None,
                   status=SectionStatus.IN_FORCE, pages=(5,), blocks=(Block(BlockType.BODY, "x"),),
                   footnotes=POOL, footnote_refs=tuple(FootnoteRef(5, m) for m in refs))


def test_each_section_gets_only_the_notes_it_cites():
    act = Act(ActCode.SGA1930, "f", "0" * 64, (_sec("1", ["2"]), _sec("2", ["3"])))
    new, rep = attach_footnotes(act)
    assert [f.text for f in new.sections[0].footnotes] == ["note for A"]
    assert [f.text for f in new.sections[1].footnotes] == ["note for B"]
    assert rep.attached == 2 and not rep.unresolved


def test_uncited_notes_become_act_notes_not_lost():
    act = Act(ActCode.SGA1930, "f", "0" * 64, (_sec("1", ["2"]), _sec("2", ["3"])))
    new, rep = attach_footnotes(act)
    assert [n.text for n in new.notes] == ["title note"] and len(rep.orphans) == 1


def test_cited_but_unprinted_marker_is_reported():
    act = Act(ActCode.SGA1930, "f", "0" * 64, (_sec("1", ["9"]),))
    _, rep = attach_footnotes(act)
    assert rep.unresolved == (("SGA1930:s1", 5, "9"),)


def test_same_marker_cited_twice_in_one_section_attaches_once():
    act = Act(ActCode.SGA1930, "f", "0" * 64, (_sec("1", ["2", "2"]),))
    new, _ = attach_footnotes(act)
    assert [f.text for f in new.sections[0].footnotes] == ["note for A"]
