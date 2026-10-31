"""Embedding model contract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, cast

import numpy as np


@dataclass(frozen=True)
class EmbeddingModelSpec:
    hf_id: str
    revision: str
    dimension: int
    max_seq_length: int
    normalize: bool
    query_prefix: str
    document_prefix: str
    pooling: str
    trust_remote_code: bool
    batch_size: int
    device: str = "cpu"

    def __post_init__(self) -> None:
        if self.dimension <= 0 or self.max_seq_length <= 0 or self.batch_size <= 0:
            raise ValueError("embedding dimensions and limits must be positive")
        if self.device != "cpu":
            raise ValueError("only CPU embedding is supported")

    def to_dict(self) -> dict[str, object]:
        return {
            "hf_id": self.hf_id, "revision": self.revision, "dimension": self.dimension,
            "max_seq_length": self.max_seq_length, "normalize": self.normalize,
            "query_prefix": self.query_prefix, "document_prefix": self.document_prefix,
            "pooling": self.pooling, "trust_remote_code": self.trust_remote_code,
            "batch_size": self.batch_size, "device": self.device,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "EmbeddingModelSpec":
        return cls(
            hf_id=str(data["hf_id"]), revision=str(data["revision"]),
            dimension=int(cast(int | str, data["dimension"])),
            max_seq_length=int(cast(int | str, data["max_seq_length"])),
            normalize=bool(data["normalize"]), query_prefix=str(data["query_prefix"]),
            document_prefix=str(data["document_prefix"]), pooling=str(data["pooling"]),
            trust_remote_code=bool(data["trust_remote_code"]),
            batch_size=int(cast(int | str, data["batch_size"])),
            device=str(data.get("device", "cpu")),
        )


class Embedder(Protocol):
    spec: EmbeddingModelSpec

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        ...

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        ...
