from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol, Sequence

import faiss
import numpy as np

from misaq.domain.chunking import Chunk, ChunkingSpec
from misaq.domain.embedding import Embedder, EmbeddingModelSpec
from misaq.domain.index import IndexMeta


class Index(Protocol):
    chunks: list[Chunk]

    def search(self, queries: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        ...


def make_index_id(statute_hashes: Sequence[str], chunking: ChunkingSpec,
                  model: EmbeddingModelSpec) -> str:
    payload = {"statute_hashes": list(statute_hashes), "chunking": chunking.to_dict(), "model": model.to_dict()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


class FaissIndex:
    def __init__(self, meta: IndexMeta, chunks: list[Chunk], vectors: np.ndarray, index: faiss.Index):
        self.meta = meta
        self.chunks = chunks
        self.vectors = vectors
        self._index = index

    @classmethod
    def build(cls, chunks: list[Chunk], embedder: Embedder, statute_hashes: Sequence[str],
              chunking: ChunkingSpec, excluded_repealed_count: int,
              excluded_omitted_count: int) -> "FaissIndex":
        vectors = np.asarray(embedder.encode_documents([c.embedded_text for c in chunks]), dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape != (len(chunks), embedder.spec.dimension):
            raise ValueError(f"invalid vectors shape: {vectors.shape}")
        if not np.isfinite(vectors).all():
            raise ValueError("embedding vectors contain non-finite values")
        index = faiss.IndexFlatIP(embedder.spec.dimension)
        index.add(vectors)
        meta = IndexMeta(
            make_index_id(statute_hashes, chunking, embedder.spec), "faiss",
            tuple(statute_hashes), chunking, embedder.spec, len(chunks),
            excluded_repealed_count, excluded_omitted_count,
        )
        return cls(meta, chunks, vectors, index)

    def search(self, queries: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        return self._index.search(np.asarray(queries, dtype=np.float32), k)

    def save(self, directory: Path, build_report: dict[str, object] | None = None) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(directory / "faiss.bin"))
        with (directory / "chunks.jsonl").open("w", encoding="utf-8") as handle:
            for chunk in self.chunks:
                handle.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
        (directory / "index_meta.json").write_text(json.dumps(self.meta.to_dict(), indent=2), encoding="utf-8")
        if build_report is not None:
            (directory / "build_report.json").write_text(json.dumps(build_report, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, directory: Path) -> "FaissIndex":
        meta = IndexMeta.from_dict(json.loads((directory / "index_meta.json").read_text(encoding="utf-8")))
        chunks = [Chunk.from_dict(json.loads(line)) for line in
                  (directory / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line]
        index = faiss.read_index(str(directory / "faiss.bin"))
        vectors = np.empty((index.ntotal, meta.model.dimension), dtype=np.float32)
        for i in range(index.ntotal):
            vectors[i] = index.reconstruct(i)
        return cls(meta, chunks, vectors, index)
