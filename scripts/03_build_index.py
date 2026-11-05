"""Build a configured section-aware index."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import psutil
import yaml
from transformers import AutoTokenizer

from misaq.chunking.chunker import chunk_act
from misaq.domain.chunking import ChunkingSpec
from misaq.domain.embedding import EmbeddingModelSpec
from misaq.domain.enums import ActCode, SectionStatus
from misaq.domain.statute import Act
from misaq.embedding.sentence_transformer import SentenceTransformerEmbedder
from misaq.indexing.index import FaissIndex
from misaq.validation.chunks import validate_chunks
from misaq.validation.index import validate_index

ROOT = Path(__file__).resolve().parents[1]


class ReferenceTokenizer:
    def __init__(self, backend: object):
        encode = getattr(backend, "encode", None)
        decode = getattr(backend, "decode", None)
        if not callable(encode) or not callable(decode):
            raise TypeError("reference tokenizer does not provide callable encode/decode methods")
        self._encode = encode
        self._decode = decode

    def encode(self, text: str, **kwargs: object) -> list[int]:
        tokens = self._encode(text, **kwargs)
        if not isinstance(tokens, list) or not all(isinstance(token, int) for token in tokens):
            raise TypeError("reference tokenizer encode() returned an invalid token list")
        return tokens

    def decode(self, tokens: list[int], **kwargs: object) -> str:
        text = self._decode(tokens, **kwargs)
        if not isinstance(text, str):
            raise TypeError("reference tokenizer decode() returned a non-string value")
        return text


def main(model_name: str, chunking_name: str) -> int:
    config = yaml.safe_load((ROOT / "configs/pipeline.yaml").read_text(encoding="utf-8"))
    model_data = config["models"][model_name]
    model_spec = EmbeddingModelSpec.from_dict(model_data)
    chunk_data = config["chunking"][chunking_name]
    chunk_spec = ChunkingSpec(
        chunk_data["strategy"], chunk_data["max_tokens"], chunk_data["overlap_tokens"],
        config["reference_tokenizer"]["model"], chunk_data["header_prefix"],
        chunk_data["algorithm_version"],
    )
    tokenizer = ReferenceTokenizer(AutoTokenizer.from_pretrained(
        config["reference_tokenizer"]["model"], revision=config["reference_tokenizer"]["revision"],
    ))
    acts = []
    for code in ActCode:
        path = ROOT / "data/processed/statutes" / f"{code.value}.json"
        acts.append(Act.from_dict(json.loads(path.read_text(encoding="utf-8"))))
    chunks = []
    expected_section_ids: set[str] = set()
    statute_hashes = []
    repealed = 0
    omitted = 0
    for act in acts:
        statute_hashes.append(act.source_sha256)
        repealed += sum(section.status is SectionStatus.REPEALED for section in act.sections)
        omitted += sum(r.last - r.first + 1 for r in act.omitted_ranges)
        expected_section_ids.update(
            section.id for section in act.sections if section.status is SectionStatus.IN_FORCE
        )
        chunks.extend(chunk_act(act, chunk_spec, tokenizer))
    counts = [len(tokenizer.encode(chunk.embedded_text, add_special_tokens=True)) for chunk in chunks]
    failures = validate_chunks(chunks, counts, chunk_spec.max_tokens, expected_section_ids)
    if failures:
        raise ValueError("; ".join(failures))
    process = psutil.Process()
    embedder = SentenceTransformerEmbedder(model_spec)
    before = process.memory_info().rss
    started = time.perf_counter()
    index = FaissIndex.build(chunks, embedder, statute_hashes, chunk_spec, repealed, omitted)
    elapsed = time.perf_counter() - started
    peak = max(before, process.memory_info().rss)
    failures = validate_index(index)
    if failures:
        raise ValueError("; ".join(failures))
    out = ROOT / "data/index" / index.meta.index_id
    index.save(out, {
        "chunks_per_second": len(chunks) / elapsed if elapsed else 0.0,
        "peak_memory_bytes": peak,
        "elapsed_seconds": elapsed,
    })
    print(json.dumps({"index": str(out), "model": model_name, "chunking": chunking_name,
                      "chunks": len(chunks), "chunks_per_second": len(chunks) / elapsed,
                      "peak_memory_bytes": peak}, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        choices=(
            "bge-small-en-v1.5",
            "bge-base-en-v1.5",
            "bge-large-en-v1.5",
            "all-MiniLM-L6-v2",
        ),
        default="bge-small-en-v1.5",
    )
    parser.add_argument("--chunking", choices=("section_aware", "fixed_size"), default="section_aware")
    args = parser.parse_args()
    sys.exit(main(args.model, args.chunking))
