"""Immutable citation verification contracts."""
from __future__ import annotations

from dataclasses import dataclass

from .enums import CitationVerdict


@dataclass(frozen=True)
class Citation:
    item_id: str
    raw_text: str
    act: str | None = None
    section: str | None = None
    subsection: str | None = None
    system: str = "S1"
    context_section_ids: tuple[str, ...] = ()
    reason_code: str | None = None


@dataclass(frozen=True)
class CitationCheck:
    item_id: str
    raw_text: str
    normalized_id: str | None
    act: str | None
    section: str | None
    subsection: str | None
    verdict: CitationVerdict
    reason_code: str
    exists_in: tuple[str, ...] = ()
    in_context: bool | None = None
    subsection_checked: bool = False
