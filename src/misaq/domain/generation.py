"""Immutable contracts for clause generation experiments."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractMeta:
    contract_id: str = ""
    source: str = ""
    licence: str = ""


@dataclass(frozen=True)
class Clause:
    clause_id: str
    text: str
    cloud_ok: bool
    source: str = ""
    licence: str = ""
    oracle_section_ids: tuple[str, ...] = ()
    contract: ContractMeta = ContractMeta()
    heading: str | None = None
    label: str | None = None
    path: str = ""
    parent_clause_id: str | None = None
    source_pages: tuple[int, ...] = ()
    kind: str = "operative_clause"
    confidence: float = 1.0
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.clause_id or not self.text.strip():
            raise ValueError("clause_id and text are required")


@dataclass(frozen=True)
class Claim:
    issue: str
    explanation: str
    citations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClauseAnalysis:
    claims: tuple[Claim, ...]
    no_supported_provision: bool


@dataclass(frozen=True)
class GenerationRecord:
    clause_id: str
    system: str
    status: str
    raw_text: str = ""
    metadata: dict[str, object] | None = None
    error_type: str | None = None
    error: str | None = None
    citations: tuple[dict[str, object], ...] = ()
    in_context: tuple[str, ...] | None = None
    retrieved_section_ids: tuple[str, ...] = ()
    oracle_section_ids: tuple[str, ...] = ()
