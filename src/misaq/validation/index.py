from __future__ import annotations

import numpy as np

from misaq.domain.embedding import EmbeddingModelSpec
from misaq.indexing.index import FaissIndex


def validate_index(index: FaissIndex, tolerance: float = 1e-5,
                   expected_model: EmbeddingModelSpec | None = None) -> list[str]:
    failures: list[str] = []
    if expected_model is not None and index.meta.model != expected_model:
        failures.append("index model metadata mismatch")
    if index.vectors.shape != (len(index.chunks), index.meta.model.dimension):
        failures.append("vector count or dimension mismatch")
    if not np.isfinite(index.vectors).all():
        failures.append("non-finite vector values")
    if index.meta.model.normalize:
        norms = np.linalg.norm(index.vectors, axis=1)
        if len(norms) and not np.allclose(norms, 1.0, atol=tolerance):
            failures.append("normalized vectors have invalid norms")
    if len(index.chunks):
        scores, ids = index.search(index.vectors, 1)
        if not np.array_equal(ids[:, 0], np.arange(len(index.chunks))):
            failures.append("self-retrieval failed")
    if index.meta.chunk_count != len(index.chunks):
        failures.append("metadata chunk count mismatch")
    return failures
