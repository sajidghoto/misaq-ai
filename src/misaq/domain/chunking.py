"""Chunking contracts. These types contain no I/O or model logic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True)
class ChunkingSpec:
    strategy: str
    max_tokens: int
    overlap_tokens: int
    reference_tokenizer: str
    header_prefix: bool = True
    algorithm_version: str = "1"

    def __post_init__(self) -> None:
        if self.strategy not in {"section_aware", "fixed_size"}:
            raise ValueError(f"unsupported chunking strategy: {self.strategy}")
        if self.max_tokens <= 0 or self.overlap_tokens < 0:
            raise ValueError("chunk token limits must be positive")
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError("overlap must be smaller than max_tokens")

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "max_tokens": self.max_tokens,
            "overlap_tokens": self.overlap_tokens,
            "reference_tokenizer": self.reference_tokenizer,
            "header_prefix": self.header_prefix,
            "algorithm_version": self.algorithm_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ChunkingSpec":
        return cls(
            strategy=str(data["strategy"]),
            max_tokens=int(cast(int | str, data["max_tokens"])),
            overlap_tokens=int(cast(int | str, data["overlap_tokens"])),
            reference_tokenizer=str(data["reference_tokenizer"]),
            header_prefix=bool(data.get("header_prefix", True)),
            algorithm_version=str(data.get("algorithm_version", "1")),
        )


@dataclass(frozen=True)
class Chunk:
    id: str
    section_id: str
    act: str
    number: str
    title: str
    chapter: str | None
    subheading: str | None
    original_text: str
    embedded_text: str
    hierarchy: tuple[str, ...]
    provenance: tuple[int, ...]
    source_block_ids: tuple[int, ...]
    footnotes: tuple[dict[str, object], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "section_id": self.section_id,
            "act": self.act,
            "number": self.number,
            "title": self.title,
            "chapter": self.chapter,
            "subheading": self.subheading,
            "original_text": self.original_text,
            "embedded_text": self.embedded_text,
            "hierarchy": list(self.hierarchy),
            "provenance": list(self.provenance),
            "source_block_ids": list(self.source_block_ids),
            "footnotes": [dict(f) for f in self.footnotes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Chunk":
        chapter = data.get("chapter")
        subheading = data.get("subheading")
        hierarchy = data.get("hierarchy", [])
        provenance = data.get("provenance", [])
        source_block_ids = data.get("source_block_ids", [])
        footnotes = data.get("footnotes", [])
        return cls(
            id=str(data["id"]),
            section_id=str(data["section_id"]),
            act=str(data["act"]),
            number=str(data["number"]),
            title=str(data["title"]),
            chapter=chapter if isinstance(chapter, str) else None,
            subheading=subheading if isinstance(subheading, str) else None,
            original_text=str(data["original_text"]),
            embedded_text=str(data["embedded_text"]),
            hierarchy=tuple(str(x) for x in cast(list[object], hierarchy)),
            provenance=tuple(int(x) for x in cast(list[int | str], provenance)),
            source_block_ids=tuple(int(x) for x in cast(list[int | str], source_block_ids)),
            footnotes=tuple(cast(dict[str, object], x) for x in cast(list[object], footnotes)),
        )
