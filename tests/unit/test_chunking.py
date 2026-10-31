import pytest

from misaq.chunking.chunker import chunk_act
from misaq.domain.chunking import ChunkingSpec
from misaq.domain.enums import ActCode, BlockType, SectionStatus
from misaq.domain.statute import Act, Block, Section

pytestmark = pytest.mark.unit


class FakeTokenizer:
    def __init__(self):
        self.words = {}

    def encode(self, text: str, **kwargs: object) -> list[int]:
        tokens = []
        for word in text.split():
            token = hash(word)
            self.words[token] = word
            tokens.append(token)
        return tokens

    def decode(self, tokens: list[int], **kwargs: object) -> str:
        return " ".join(self.words[token] for token in tokens)


def make_act(status=SectionStatus.IN_FORCE):
    sections = (
        Section(ActCode.CA1872, "10", "Title", "Title", "CHAPTER I", None, status, (1,),
                (Block(BlockType.BODY, "one two three four"), Block(BlockType.PROVISO, "five six"))),
    )
    return Act(ActCode.CA1872, "x", "a" * 64, sections)


def test_section_aware_never_crosses_blocks_or_sections():
    spec = ChunkingSpec("section_aware", 3, 0, "fake", False)
    chunks = chunk_act(make_act(), spec, FakeTokenizer())
    assert [c.original_text for c in chunks] == ["one two three", "four five six"]
    assert [c.source_block_ids for c in chunks] == [(0,), (0, 1)]
    assert all(c.section_id == "CA1872:s10" for c in chunks)


def test_section_aware_packs_blocks_when_section_fits_budget():
    section = Section(ActCode.CA1872, "10", "Title", "Title", "CHAPTER I", None,
                      SectionStatus.IN_FORCE, (1,),
                      (Block(BlockType.BODY, "one two"), Block(BlockType.PROVISO, "three four")))
    act = Act(ActCode.CA1872, "x", "a" * 64, (section,))
    chunks = chunk_act(act, ChunkingSpec("section_aware", 4, 0, "fake", False), FakeTokenizer())
    assert len(chunks) == 1
    assert chunks[0].source_block_ids == (0, 1)


def test_fixed_size_overlap_and_exclusions():
    spec = ChunkingSpec("fixed_size", 3, 1, "fake", False)
    chunks = chunk_act(make_act(), spec, FakeTokenizer())
    assert [c.original_text for c in chunks] == ["one two three", "three four five", "five six"]
    assert len(chunk_act(make_act(SectionStatus.REPEALED), spec, FakeTokenizer())) == 0


def test_golden_section_numbers_are_supported(parsed):
    for code, _number in (("CA1872", "10"), ("SGA1930", "16A"), ("SRA1877", "27A"), ("CA1872", "141")):
        act, _ = parsed[code]
        assert chunk_act(act, ChunkingSpec("section_aware", 400, 0, "fake"), FakeTokenizer())
