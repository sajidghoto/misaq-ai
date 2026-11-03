"""Retrieve and print top sections for one query."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from misaq.domain.embedding import EmbeddingModelSpec
from misaq.domain.retrieval import Query
from misaq.embedding.sentence_transformer import SentenceTransformerEmbedder
from misaq.indexing.index import FaissIndex
from misaq.retrieval.retriever import DenseRetriever

ROOT = Path(__file__).resolve().parents[1]


def _find_index(model: str, chunking: str) -> FaissIndex:
    config = yaml.safe_load((ROOT / "configs/pipeline.yaml").read_text(encoding="utf-8"))
    model_id = config["models"][model]["hf_id"]
    matches = []
    for directory in sorted((ROOT / "data/index").iterdir()):
        meta_path = directory / "index_meta.json"
        if not directory.is_dir() or not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta["model"]["hf_id"] == model_id and meta["chunking"]["strategy"] == chunking:
            matches.append(directory)
    if len(matches) != 1:
        raise RuntimeError(f"expected one index for model={model}, chunking={chunking}; found {len(matches)}")
    return FaissIndex.load(matches[0])


def print_results(retriever: DenseRetriever, query_text: str, k: int) -> None:
    result = retriever.retrieve(Query("demo", query_text))
    chunks = {chunk.section_id: chunk for chunk in retriever.index.chunks}
    for hit in result.hits:
        chunk = chunks[hit.section_id]
        preview = " ".join(chunk.original_text.split())[:200]
        print(
            f"Act: {chunk.act} | Section: {chunk.number} | Title: {chunk.title} | "
            f"Score: {hit.score:.6f} | {preview}"
        )


def main(model: str, chunking: str, query: str, k: int) -> int:
    if k <= 0:
        raise ValueError("--k must be positive")
    config = yaml.safe_load((ROOT / "configs/pipeline.yaml").read_text(encoding="utf-8"))
    index = _find_index(model, chunking)
    embedder = SentenceTransformerEmbedder(EmbeddingModelSpec.from_dict(config["models"][model]))
    print_results(DenseRetriever(index, embedder, top_k=k), query, k)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="bge-small-en-v1.5")
    parser.add_argument("--chunking", default="section_aware")
    parser.add_argument("--query", required=True)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    raise SystemExit(main(args.model, args.chunking, args.query, args.k))
