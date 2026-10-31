"""Index identity and count contract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from .chunking import ChunkingSpec
from .embedding import EmbeddingModelSpec


@dataclass(frozen=True)
class IndexMeta:
    index_id: str
    backend: str
    statute_hashes: tuple[str, ...]
    chunking: ChunkingSpec
    model: EmbeddingModelSpec
    chunk_count: int
    excluded_repealed_count: int
    excluded_omitted_count: int

    def __post_init__(self) -> None:
        if self.chunk_count < 0 or self.excluded_repealed_count < 0 or self.excluded_omitted_count < 0:
            raise ValueError("index counts cannot be negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "index_id": self.index_id, "backend": self.backend,
            "statute_hashes": list(self.statute_hashes),
            "chunking": self.chunking.to_dict(), "model": self.model.to_dict(),
            "chunk_count": self.chunk_count,
            "excluded_repealed_count": self.excluded_repealed_count,
            "excluded_omitted_count": self.excluded_omitted_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "IndexMeta":
        return cls(
            index_id=str(data["index_id"]), backend=str(data["backend"]),
            statute_hashes=tuple(str(x) for x in cast(list[object], data["statute_hashes"])),
            chunking=ChunkingSpec.from_dict(cast(dict[str, object], data["chunking"])),
            model=EmbeddingModelSpec.from_dict(cast(dict[str, object], data["model"])),
            chunk_count=int(cast(int | str, data["chunk_count"])),
            excluded_repealed_count=int(cast(int | str, data["excluded_repealed_count"])),
            excluded_omitted_count=int(cast(int | str, data["excluded_omitted_count"])),
        )
