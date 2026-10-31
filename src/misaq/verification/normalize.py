"""Normalize citation act and section variants."""
from __future__ import annotations

import re
from dataclasses import dataclass

from misaq.domain.citation import Citation
from misaq.verification.registry import CorpusRegistry


@dataclass(frozen=True)
class NormalizedCitation:
    act: str | None
    section: str | None
    subsection: str | None
    normalized_id: str | None
    reason_code: str | None = None


def normalize_citation(citation: Citation, registry: CorpusRegistry) -> NormalizedCitation:
    if citation.reason_code is not None:
        return NormalizedCitation(None, citation.section, citation.subsection, None, citation.reason_code)
    if not citation.act:
        return NormalizedCitation(None, citation.section, citation.subsection, None, "ACT_UNSPECIFIED")
    alias = registry.resolve_act(citation.act)
    if alias is None:
        return NormalizedCitation(None, citation.section, citation.subsection, None, "ACT_OUT_OF_CORPUS")
    section = citation.section
    subsection = citation.subsection
    embedded = re.fullmatch(r"(\d+[A-Za-z]?)\s*\(([^)]+)\)", section or "")
    if embedded is not None and subsection is None:
        section, subsection = embedded.group(1), embedded.group(2)
    if not section or re.fullmatch(r"\d+[A-Za-z]?", section) is None:
        return NormalizedCitation(alias.act, section, subsection, None, "SECTION_INVALID")
    normalized = f"{alias.act}:s{section}"
    return NormalizedCitation(alias.act, section, subsection, normalized)
