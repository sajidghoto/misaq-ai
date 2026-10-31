from __future__ import annotations

from typing import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer

from misaq.domain.chunking import Chunk
from misaq.domain.embedding import EmbeddingModelSpec


class SentenceTransformerEmbedder:
    def __init__(self, spec: EmbeddingModelSpec):
        self.spec = spec
        self.model = SentenceTransformer(
            spec.hf_id, revision=spec.revision, device=spec.device,
            trust_remote_code=spec.trust_remote_code,
        )
        self.model.max_seq_length = spec.max_seq_length

    def _encode(self, texts: Sequence[str], prefix: str) -> np.ndarray:
        prepared = [prefix + text for text in texts]
        lengths = [len(self.model.tokenizer.encode(text, add_special_tokens=True)) for text in prepared]
        too_long = [length for length in lengths if length > self.spec.max_seq_length]
        if too_long:
            raise ValueError(f"text exceeds {self.spec.hf_id} max_seq_length: {too_long[0]}")
        values = self.model.encode(
            prepared, batch_size=self.spec.batch_size, show_progress_bar=False,
            normalize_embeddings=self.spec.normalize, convert_to_numpy=True,
        )
        result = np.asarray(values, dtype=np.float32)
        if result.ndim != 2 or result.shape[1] != self.spec.dimension:
            raise ValueError(f"embedding dimension mismatch: {result.shape}")
        return result

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode(texts, self.spec.query_prefix)

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode(texts, self.spec.document_prefix)

    def encode_chunks(self, chunks: Sequence[Chunk]) -> np.ndarray:
        return self.encode_documents([chunk.embedded_text for chunk in chunks])
