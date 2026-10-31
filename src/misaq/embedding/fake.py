from __future__ import annotations

import hashlib
from typing import Sequence

import numpy as np

from misaq.domain.embedding import EmbeddingModelSpec


class FakeEmbedder:
    def __init__(self, spec: EmbeddingModelSpec):
        self.spec = spec

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        rows = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            row = rng.standard_normal(self.spec.dimension).astype(np.float32)
            if self.spec.normalize:
                row /= np.linalg.norm(row)
            rows.append(row)
        return np.asarray(rows, dtype=np.float32)

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode([self.spec.query_prefix + text for text in texts])

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode([self.spec.document_prefix + text for text in texts])
