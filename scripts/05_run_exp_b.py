"""Run one model/chunking Experiment B evaluation."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

import yaml

from misaq.domain.embedding import EmbeddingModelSpec
from misaq.domain.errors import DataValidationError, IndexFilesMissingError, MisaqError
from misaq.domain.statute import Act
from misaq.embedding.sentence_transformer import SentenceTransformerEmbedder
from misaq.experiments.configurations import EXP_B_COMBINATIONS
from misaq.experiments.fingerprint import git_info, sha256_file
from misaq.experiments.runner import ExperimentRunner
from misaq.indexing.index import FaissIndex
from misaq.retrieval.retriever import DenseRetriever
from misaq.validation.eval_data import validate_eval_jsonl
from misaq.validation.statutes import check_processed_hashes

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/experiments/exp_b_retrieval.yaml"


def _build_index_command(model_name: str, chunking_name: str) -> str:
    return (
        f"python scripts\\03_build_index.py --model {model_name} "
        f"--chunking {chunking_name}"
    )


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


def _eval_path(config: dict[str, object], split: str) -> Path:
    eval_files = config.get("eval_files")
    if not isinstance(eval_files, dict) or not isinstance(eval_files.get(split), str):
        raise ValueError(f"no evaluation file configured for split {split!r}")
    return ROOT / str(eval_files[split])


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
    index_root = ROOT / "data/index"
    directories = sorted(index_root.iterdir()) if index_root.is_dir() else []
    for directory in directories:
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
        missing_files = [
            filename for filename in ("chunks.jsonl", "faiss.bin")
            if not (matches[0] / filename).is_file()
        ]
        if missing_files:
            command = _build_index_command(model_name, chunking_name)
            missing = ", ".join(missing_files)
            raise IndexFilesMissingError(
                f"index files are missing ({missing}) for model={model_name}, "
                f"chunking={chunking_name}; build with: {command}"
            )
        return FaissIndex.load(matches[0])
    if len(matches) > 1:
        ids = ", ".join(path.name for path in matches)
        raise RuntimeError(
            f"multiple indexes for model={model_name}, chunking={chunking_name}: {ids}; "
            "use --index-id"
        )
    suffix = f", index_id={index_id}" if index_id is not None else ""
    command = _build_index_command(model_name, chunking_name)
    raise IndexFilesMissingError(
        f"no built index for model={model_name}, chunking={chunking_name}{suffix}; "
        f"build with: {command}"
    )


def run_experiment(
    model: str, chunking: str, split: str, final: bool, index_id: str | None = None
) -> dict[str, object]:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    config["model"] = model
    config["chunking"] = chunking
    config["split"] = split
    eval_path = _eval_path(config, split)
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
    return ExperimentRunner(retriever, eval_path, ROOT / "runs" / run_id, config, split=split).run()


def main(model: str, chunking: str, split: str, final: bool, index_id: str | None = None) -> int:
    summary = run_experiment(model, chunking, split, final, index_id)
    print(json.dumps(summary, indent=2))
    return 0


def _dict_value(value: object, key: str) -> object | None:
    if isinstance(value, dict):
        return value.get(key)
    return None


def _metric_text(result: dict[str, object], metric: str) -> str:
    summary = result.get("summary")
    value = _dict_value(_dict_value(summary, "metrics"), metric)
    return f"{value:.4f}" if isinstance(value, (float, int)) else "-"


def _recall_ci_text(result: dict[str, object]) -> str:
    summary = result.get("summary")
    interval = _dict_value(_dict_value(summary, "confidence_intervals"), "recall@5")
    if (
        isinstance(interval, (list, tuple))
        and len(interval) == 2
        and all(isinstance(value, (float, int)) for value in interval)
    ):
        return f"{interval[0]:.4f}-{interval[1]:.4f}"
    return "-"


def _recall_at_5(result: dict[str, object]) -> float | None:
    summary = result.get("summary")
    value = _dict_value(_dict_value(summary, "metrics"), "recall@5")
    return float(value) if isinstance(value, (float, int)) else None


def _table_row(result: dict[str, object]) -> list[str]:
    summary = result.get("summary")
    counts = _dict_value(summary, "counts")
    latency = _dict_value(summary, "latency_ms")
    expected = _dict_value(counts, "expected")
    completed = _dict_value(counts, "completed")
    errors = _dict_value(counts, "errors")
    done = f"{completed}/{expected} ({errors} err)" if expected is not None else "-"
    p50 = _dict_value(latency, "p50")
    p95 = _dict_value(latency, "p95")
    peak_memory = _dict_value(summary, "peak_memory_bytes")
    return [
        str(result["model"]),
        str(result["chunking"]),
        str(result["status"]),
        done,
        *(_metric_text(result, metric) for metric in (
            "recall@1", "precision@1",
            "recall@3", "precision@3",
            "recall@5", "precision@5",
            "recall@10", "precision@10",
            "mrr",
        )),
        _recall_ci_text(result),
        f"{p50:.2f}" if isinstance(p50, (float, int)) else "-",
        f"{p95:.2f}" if isinstance(p95, (float, int)) else "-",
        f"{peak_memory:,}" if isinstance(peak_memory, int) else "-",
    ]


def _print_summary_table(results: list[dict[str, object]]) -> None:
    headers = [
        "Model", "Chunking", "Status", "Done",
        "R@1", "P@1", "R@3", "P@3", "R@5", "P@5", "R@10", "P@10",
        "MRR", "R@5 95% CI", "P50 ms", "P95 ms", "Peak RAM B",
    ]
    rows = [headers, *(_table_row(result) for result in results)]
    widths = [max(len(row[column]) for row in rows) for column in range(len(headers))]
    print("\nExperiment B dev summary")
    print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows[1:]:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def _print_conclusion(results: list[dict[str, object]]) -> None:
    complete = [
        (result, recall)
        for result in results
        if result.get("status") == "complete"
        and (recall := _recall_at_5(result)) is not None
    ]
    if not complete:
        print("Conclusion: no complete dev runs; no comparison conclusion can be drawn.")
        return
    best_recall = max(recall for _, recall in complete)
    leaders = [result for result, recall in complete if recall == best_recall]
    names = ", ".join(
        f"{result['model']} / {result['chunking']} (95% CI {_recall_ci_text(result)})"
        for result in leaders
    )
    has_incomplete = len(complete) != len(results)
    prefix = "Highest observed among completed runs" if has_incomplete else "Highest dev Recall@5"
    suffix = " Sweep incomplete; do not treat as a full comparison." if has_incomplete else (
        " Dev comparison only; this is not an automatic model selection or a test result."
    )
    print(f"Conclusion: {prefix} is {best_recall:.4f} for {names}.{suffix}")


def run_all() -> int:
    results: list[dict[str, object]] = []
    for model, chunking in EXP_B_COMBINATIONS:
        print(f"\nRunning dev evaluation: {model} / {chunking}")
        try:
            summary = run_experiment(model, chunking, "dev", False)
        except (MisaqError, OSError, RuntimeError, ValueError) as error:
            results.append({
                "model": model,
                "chunking": chunking,
                "status": "error",
                "error": str(error),
            })
        else:
            status = summary.get("status")
            result: dict[str, object] = {
                "model": model,
                "chunking": chunking,
                "status": status if isinstance(status, str) else "invalid",
                "summary": summary,
            }
            if result["status"] == "complete" and _recall_at_5(result) is None:
                result["status"] = "invalid_summary"
                result["error"] = "completed summary is missing recall@5"
            results.append(result)
    _print_summary_table(results)
    for result in results:
        if result.get("error"):
            print(f"Error for {result['model']} / {result['chunking']}: {result['error']}")
    _print_conclusion(results)
    return 1 if any(result.get("status") != "complete" for result in results) else 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="run every supported combination on dev")
    parser.add_argument("--model")
    parser.add_argument("--chunking")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--index-id")
    args = parser.parse_args(argv)
    if args.all and (
        args.model is not None
        or args.chunking is not None
        or args.split != "dev"
        or args.final
        or args.index_id is not None
    ):
        parser.error("--all is dev-only and cannot be combined with model, chunking, --final, or --index-id")
    return args


if __name__ == "__main__":
    args = _parse_args()
    try:
        if args.all:
            sys.exit(run_all())
        sys.exit(main(
            args.model or "bge-small-en-v1.5",
            args.chunking or "section_aware",
            args.split,
            args.final,
            args.index_id,
        ))
    except (MisaqError, OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
