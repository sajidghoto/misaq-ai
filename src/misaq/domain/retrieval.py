"""Immutable retrieval result contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Query:
    id: str
    text: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("query id cannot be empty")
        if not self.text.strip():
            raise ValueError("query text cannot be empty")


@dataclass(frozen=True)
class Hit:
    section_id: str
    score: float

    def __post_init__(self) -> None:
        if not self.section_id:
            raise ValueError("hit section id cannot be empty")


@dataclass(frozen=True)
class RetrievalResult:
    query: Query
    hits: tuple[Hit, ...]
