"""Run one model/chunking Experiment B evaluation."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

from misaq.domain.embedding import EmbeddingModelSpec
from misaq.domain.errors import DataValidationError
from misaq.domain.statute import Act
from misaq.embedding.sentence_transformer import SentenceTransformerEmbedder
from misaq.experiments.fingerprint import git_info, sha256_file
from misaq.experiments.runner import ExperimentRunner
from misaq.indexing.index import FaissIndex
from misaq.retrieval.retriever import DenseRetriever
from misaq.validation.eval_data import validate_eval_jsonl
from misaq.validation.statutes import check_processed_hashes

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/experiments/exp_b_retrieval.yaml"


def _acts() -> tuple[Act, ...]:
    processed = ROOT / "data/processed/statutes"
    return tuple(
        Act.from_dict(json.loads((processed / f"{code}.json").read_text(encoding="utf-8")))
        for code in ("CA1872", "SGA1930", "SRA1877")
    )


def _listed_eval_hash(eval_path: Path) -> bool:
    sums = eval_path.parent / "SHA256SUMS"
    if not sums.exists():
        return False
    expected = {
        name.lstrip("*"): digest
        for digest, name in (line.split(maxsplit=1) for line in sums.read_text(encoding="utf-8").splitlines() if line)
    }
    fingerprint = sha256_file(eval_path)
    return expected.get(eval_path.name) == fingerprint.sha256


def guard_test_split(root: Path, eval_path: Path, final: bool) -> None:
    if not final:
        raise RuntimeError("test split requires --final")
    git = git_info(root)
    if git["dirty"] is not False:
        raise RuntimeError("test split requires a clean git tree")
    try:
        check_processed_hashes(root / "data/processed/statutes")
    except DataValidationError as error:
        raise RuntimeError("test split requires verified processed-statute hashes") from error
    if not _listed_eval_hash(eval_path):
        raise RuntimeError(
            f"test split eval file hash is not listed in {eval_path.parent / 'SHA256SUMS'}"
        )


def _find_index(model_name: str, chunking_name: str, index_id: str | None = None) -> FaissIndex:
    pipeline = yaml.safe_load((ROOT / "configs/pipeline.yaml").read_text(encoding="utf-8"))
    model_id = pipeline["models"][model_name]["hf_id"]
    matches: list[Path] = []
    for directory in sorted((ROOT / "data/index").iterdir()):
        if not directory.is_dir() or not (directory / "index_meta.json").exists():
            continue
        meta = json.loads((directory / "index_meta.json").read_text(encoding="utf-8"))
        if (
            meta["model"]["hf_id"] == model_id
            and meta["chunking"]["strategy"] == chunking_name
            and (index_id is None or meta["index_id"] == index_id)
        ):
            matches.append(directory)
    if len(matches) == 1:
        return FaissIndex.load(matches[0])
    if len(matches) > 1:
        ids = ", ".join(path.name for path in matches)
        raise RuntimeError(
            f"multiple indexes for model={model_name}, chunking={chunking_name}: {ids}; "
            "use --index-id"
        )
    suffix = f", index_id={index_id}" if index_id is not None else ""
    raise RuntimeError(f"no built index for model={model_name}, chunking={chunking_name}{suffix}")


def main(model: str, chunking: str, split: str, final: bool, index_id: str | None = None) -> int:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    config["model"] = model
    config["chunking"] = chunking
    config["split"] = split
    eval_path = ROOT / str(config["eval_file"])
    acts = _acts()
    validate_eval_jsonl(eval_path, acts)
    if split == "test":
        guard_test_split(ROOT, eval_path, final)
    index = _find_index(model, chunking, index_id)
    pipeline = yaml.safe_load((ROOT / "configs/pipeline.yaml").read_text(encoding="utf-8"))
    embedder = SentenceTransformerEmbedder(EmbeddingModelSpec.from_dict(pipeline["models"][model]))
    ks = [int(value) for value in config["ks"]]
    retriever = DenseRetriever(index, embedder, top_n=int(config["top_n"]), top_k=max(ks))
    run_id = f"exp_b_{model}_{chunking}_{split}_{datetime.now():%Y-%m-%dT%H-%M-%S}"
    summary = ExperimentRunner(retriever, eval_path, ROOT / "runs" / run_id, config, split=split).run()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="bge-small-en-v1.5")
    parser.add_argument("--chunking", default="section_aware")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--index-id")
    args = parser.parse_args()
    try:
        sys.exit(main(args.model, args.chunking, args.split, args.final, args.index_id))
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
