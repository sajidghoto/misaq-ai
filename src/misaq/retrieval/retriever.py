"""Dense retrieval over a built chunk index."""
from __future__ import annotations

from misaq.domain.embedding import Embedder
from misaq.domain.retrieval import Hit, Query, RetrievalResult
from misaq.indexing.index import Index


class DenseRetriever:
    def __init__(self, index: Index, embedder: Embedder, top_n: int = 20, top_k: int = 10):
        if top_n <= 0 or top_k <= 0:
            raise ValueError("top_n and top_k must be positive")
        self.index = index
        self.embedder = embedder
        self.top_n = top_n
        self.top_k = top_k

    def retrieve(self, query: Query) -> RetrievalResult:
        vectors = self.embedder.encode_queries([query.text])
        scores, positions = self.index.search(vectors, self.top_n)
        section_scores: dict[str, float] = {}
        for score, position in zip(scores[0], positions[0], strict=True):
            if position < 0:
                continue
            section_id = self.index.chunks[int(position)].section_id
            section_scores[section_id] = max(section_scores.get(section_id, float("-inf")), float(score))
        ordered = sorted(section_scores.items(), key=lambda item: (-item[1], item[0]))
        hits = tuple(Hit(section_id, score) for section_id, score in ordered[:self.top_k])
        return RetrievalResult(query, hits)
