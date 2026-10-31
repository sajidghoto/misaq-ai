"""Verdict rules relative to the frozen corpus."""
from __future__ import annotations

import re

from misaq.domain.citation import Citation, CitationCheck
from misaq.domain.enums import CitationVerdict
from misaq.verification.normalize import normalize_citation
from misaq.verification.registry import CorpusRegistry


def verify_citation(citation: Citation, registry: CorpusRegistry) -> CitationCheck:
    normalized = normalize_citation(citation, registry)
    context = None
    if citation.system in {"S3", "S4"} and normalized.normalized_id is not None:
        context = normalized.normalized_id in citation.context_section_ids
    if normalized.reason_code is not None:
        verdict = (CitationVerdict.OUT_OF_CORPUS if normalized.reason_code == "ACT_OUT_OF_CORPUS"
                   else CitationVerdict.MALFORMED)
        return _check(citation, normalized, verdict, normalized.reason_code, context)
    assert normalized.act is not None
    if normalized.act not in registry.acts:
        return _check(citation, normalized, CitationVerdict.OUT_OF_CORPUS, "ACT_OUT_OF_CORPUS", context)
    record = registry.acts[normalized.act]
    section = normalized.section
    assert section is not None
    section_number = re.match(r"\d+", section)
    if section_number is None:
        return _check(citation, normalized, CitationVerdict.MALFORMED, "SECTION_INVALID", context)
    if section in record.repealed_sections or any(
        first <= int(section_number.group()) <= last for first, last in record.omitted_ranges
    ):
        return _check(citation, normalized, CitationVerdict.REPEALED_OR_OMITTED, "SECTION_REPEALED_OR_OMITTED", context)
    if section in record.in_force_sections:
        subsection_checked = False
        if citation.subsection is not None:
            subsection_checked = _subsection_is_explicit(citation, normalized.act, registry)
            if subsection_checked and not _subsection_exists(citation, normalized.act, registry):
                return _check(citation, normalized, CitationVerdict.VALID_SECTION_BAD_SUBSECTION,
                              "SUBSECTION_NOT_FOUND", context, subsection_checked)
        return _check(citation, normalized, CitationVerdict.VALID, "SECTION_IN_FORCE", context, subsection_checked)
    exists_in = registry.find_section(section)
    if exists_in:
        return _check(citation, normalized, CitationVerdict.WRONG_ACT, "SECTION_EXISTS_IN_OTHER_ACT",
                      context, False, exists_in)
    return _check(citation, normalized, CitationVerdict.NONEXISTENT_SECTION, "SECTION_NOT_IN_CORPUS", context)


def verify(citations: list[Citation] | tuple[Citation, ...], registry: CorpusRegistry) -> tuple[CitationCheck, ...]:
    return tuple(verify_citation(citation, registry) for citation in citations)


def _subsection_is_explicit(citation: Citation, act: str, registry: CorpusRegistry) -> bool:
    record = registry.acts[act]
    return bool(record and re.search(r"\(\s*\d+[A-Za-z]?\s*\)", record.section_text.get(citation.section or "", "")))


def _subsection_exists(citation: Citation, act: str, registry: CorpusRegistry) -> bool:
    text = registry.acts[act].section_text.get(citation.section or "", "")
    return bool(re.search(rf"\(\s*{re.escape(citation.subsection or '')}\s*\)", text))


def _check(citation, normalized, verdict, reason, context, subsection_checked=False, exists_in=()):
    return CitationCheck(citation.item_id, citation.raw_text, normalized.normalized_id, normalized.act,
                         normalized.section, normalized.subsection, verdict, reason, tuple(exists_in),
                         context, subsection_checked)
