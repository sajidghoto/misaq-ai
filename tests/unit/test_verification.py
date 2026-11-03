import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from misaq.domain.citation import Citation
from misaq.domain.enums import ActCode, BlockType, CitationVerdict, SectionStatus
from misaq.domain.statute import Act, Block, Section
from misaq.verification.extract import extract_citations
from misaq.verification.normalize import normalize_citation
from misaq.verification.registry import Alias, CorpusRegistry
from misaq.verification.verify import verify_citation

ROOT = Path(__file__).resolve().parents[2]


def _act(code=ActCode.CA1872, number="73", text="(1) first\n(2) second", status=SectionStatus.IN_FORCE):
    return Act(code, "source.pdf", "hash", (
        Section(code, number, "Title", "Title", None, None, status, (1,), (Block(BlockType.BODY, text),)),
    ))


def _registry(*acts):
    return CorpusRegistry.from_acts(acts, (
        Alias("CA1872", "Contract Act", True),
        Alias("CA1872", "the Contract Act, 1872", True),
        Alias("CA1872", "Act IX of 1872", False),
        Alias("SGA1930", "Sale of Goods Act, 1930", True),
        Alias("SRA1877", "Specific Relief Act, 1877", True),
    ))


def test_extraction_supports_lists_ranges_and_ignores_non_sections():
    citations = extract_citations("See ss. 73 and 74 of the Contract Act, 1872; Article 5 and Rule 2.")
    assert [citation.section for citation in citations] == ["73", "74"]
    assert all(citation.act == "the Contract Act, 1872" for citation in citations)
    assert extract_citations("sections 45-47 of the Contract Act, 1872", range_cap=2)[0].reason_code == "RANGE_OVER_CAP"

    range_citations = extract_citations("sections 45-47 of the Contract Act, 1872")
    assert [citation.section for citation in range_citations] == ["45", "46", "47"]
    assert extract_citations("Article 5, Order 7, Rule 2, and PLD 2020") == ()


def test_over_cap_range_is_malformed():
    citation = extract_citations("sections 1-4 of the Contract Act, 1872", range_cap=2)[0]
    assert citation.reason_code == "RANGE_OVER_CAP"
    check = verify_citation(citation, _registry(_act()))
    assert check.verdict is CitationVerdict.MALFORMED
    assert check.reason_code == "RANGE_OVER_CAP"


@pytest.mark.parametrize(
    ("citation", "verdict", "reason"),
    [
        (Citation("1", "s. 73", "Contract Act", "73"), CitationVerdict.VALID, "SECTION_IN_FORCE"),
        (Citation("2", "s. 73", "Contract Act", "73", "3"),
         CitationVerdict.VALID_SECTION_BAD_SUBSECTION, "SUBSECTION_NOT_FOUND"),
        (Citation("3", "s. 73", "Contract Act", "99"), CitationVerdict.NONEXISTENT_SECTION, "SECTION_NOT_IN_CORPUS"),
        (Citation("4", "s. 73", "Unknown Act", "73"), CitationVerdict.OUT_OF_CORPUS, "ACT_OUT_OF_CORPUS"),
        (Citation("5", "s. 73"), CitationVerdict.MALFORMED, "ACT_UNSPECIFIED"),
    ],
)
def test_verdict_rules(citation, verdict, reason):
    check = verify_citation(citation, _registry(_act()),)
    assert check.verdict is verdict
    assert check.reason_code == reason


def test_wrong_act_exists_in_and_context():
    registry = _registry(_act(), _act(ActCode.SGA1930, "73", "text"))
    check = verify_citation(Citation("1", "s. 73", "Sale of Goods Act, 1930", "73", system="S3",
                                     context_section_ids=("SGA1930:s73",)), registry)
    assert check.verdict is CitationVerdict.VALID
    assert check.in_context is True
    wrong = verify_citation(
        Citation("2", "s. 73", "Contract Act", "73"),
        _registry(_act(ActCode.CA1872, "99"), _act(ActCode.SGA1930, "73")),
    )
    assert wrong.verdict is CitationVerdict.WRONG_ACT
    assert wrong.exists_in == ("SGA1930",)


def test_normalization_variants():
    registry = _registry(_act())
    for act in ("s. 73", "Section 73", "sec 73"):
        extracted = extract_citations(f"{act} of Act IX of 1872")[0]
        normalized = normalize_citation(extracted, registry)
        assert normalized.normalized_id == "CA1872:s73"
    normalized = normalize_citation(Citation("x", "s. 73", "the Contract Act, 1872", "73"), registry)
    assert normalized.normalized_id == "CA1872:s73"
    structured = normalize_citation(Citation("x", "10(2)", "Contract Act", "10(2)"), registry)
    assert structured.section == "10" and structured.subsection == "2"


def test_real_corpus_repealed_and_omitted_verdicts():
    processed = ROOT / "data" / "processed" / "statutes"
    acts = []
    for path in sorted(processed.glob("*.json")):
        if "_report" not in path.name:
            from misaq.domain.statute import Act
            acts.append(Act.from_dict(json.loads(path.read_text(encoding="utf-8"))))
    registry = CorpusRegistry.from_acts(acts, (
        Alias("SGA1930", "Sale of Goods Act, 1930", True),
        Alias("CA1872", "Contract Act, 1872", True),
    ))
    repealed = next(
        section.number for act in acts if act.code is ActCode.SGA1930 for section in act.sections
        if section.status is SectionStatus.REPEALED
    )
    ca_act = next(act for act in acts if act.code is ActCode.CA1872)
    omitted = str(ca_act.omitted_ranges[0].first)
    assert verify_citation(
        Citation("r", "repealed", "Sale of Goods Act, 1930", repealed), registry
    ).verdict is CitationVerdict.REPEALED_OR_OMITTED
    assert verify_citation(
        Citation("o", "omitted", "Contract Act, 1872", omitted), registry
    ).verdict is CitationVerdict.REPEALED_OR_OMITTED


def test_real_corpus_verdicts_are_independent_of_act_order():
    processed = ROOT / "data" / "processed" / "statutes"
    acts = [
        Act.from_dict(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(processed.glob("*.json"), reverse=True)
        if "_report" not in path.name
    ]
    registry = CorpusRegistry.from_acts(acts, (
        Alias("SGA1930", "Sale of Goods Act, 1930", True),
        Alias("CA1872", "Contract Act, 1872", True),
    ))
    repealed = next(
        section.number
        for act in acts
        if act.code is ActCode.SGA1930
        for section in act.sections
        if section.status is SectionStatus.REPEALED
    )
    assert verify_citation(
        Citation("r", "repealed", "Sale of Goods Act, 1930", repealed),
        registry,
    ).verdict is CitationVerdict.REPEALED_OR_OMITTED
    assert verify_citation(
        Citation("o", "omitted", "Contract Act, 1872", "76"),
        registry,
    ).verdict is CitationVerdict.REPEALED_OR_OMITTED


@given(st.text())
def test_normalizer_never_crashes_and_is_idempotent(text):
    registry = _registry(_act())
    citation = Citation("x", text, "Contract Act", text)
    first = normalize_citation(citation, registry)
    second = normalize_citation(citation, registry)
    assert first == second
