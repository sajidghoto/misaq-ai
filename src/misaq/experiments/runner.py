"""Resumable Experiment B retrieval evaluation runner."""
from __future__ import annotations

import json
import statistics
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import yaml

from misaq.domain.errors import MisaqError
from misaq.domain.retrieval import Query, RetrievalResult
from misaq.evaluation.stats import bootstrap_metric_cis
from misaq.experiments.fingerprint import config_sha256, environment_fingerprint, git_info, sha256_file
from misaq.retrieval.metrics import mean_reciprocal_rank, metrics_at_k


class Retriever(Protocol):
    def retrieve(self, query: Query) -> RetrievalResult:
        ...


def _read_rows(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ExperimentRunner:
    def __init__(
        self,
        retriever: Retriever,
        eval_path: Path,
        run_dir: Path,
        config: dict[str, object],
        *,
        split: str = "dev",
    ):
        self.retriever = retriever
        self.eval_path = eval_path
        self.run_dir = run_dir
        self.config = config
        self.split = split
        self.items_path = run_dir / "items.jsonl"
        self._ensure_manifest()

    def _ensure_manifest(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.run_dir / "manifest.json"
        if manifest_path.exists():
            return
        params = {
            "model": self.config.get("model"),
            "chunking": self.config.get("chunking"),
            "ks": self.config.get("ks", self.config.get("k", [1, 3, 5, 10])),
            "top_n": self.config.get("top_n"),
            "split": self.split,
            "bootstrap_resamples": self._bootstrap().get("resamples", 10_000),
            "bootstrap_seed": self._bootstrap().get("seed", 0),
            "retrieval_algorithm_version": self.config.get("retrieval_algorithm_version"),
            "verification_algorithm_version": self.config.get("verification_algorithm_version"),
        }
        git = git_info(self.run_dir.parent)
        eval_fingerprint = sha256_file(self.eval_path, "evaluation").to_dict()
        _write_json(manifest_path, {
            "manifest_version": "1.0",
            "run_id": self.run_dir.name,
            "kind": "exp_b",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git": git,
            "config_hash": config_sha256(self.config),
            "data": [eval_fingerprint],
            "params": params,
            "models": {"model": self.config.get("model")},
            "seed": params["bootstrap_seed"],
            "env": environment_fingerprint(),
            "stages": [],
            "outputs": {},
            "status": "running",
        })
        (self.run_dir / "resolved_config.yaml").write_text(
            yaml.safe_dump(self.config, sort_keys=True), encoding="utf-8"
        )

    def _bootstrap(self) -> dict[str, object]:
        value = self.config.get("bootstrap", {})
        return value if isinstance(value, dict) else {}

    def run(self, *, max_items: int | None = None) -> dict[str, object]:
        rows = [row for row in _read_rows(self.eval_path) if row.get("split") == self.split]
        completed_ids = {
            str(row["id"]) for row in (_read_rows(self.items_path) if self.items_path.exists() else [])
        }
        processed_this_call = 0
        tracemalloc.start()
        try:
            with self.items_path.open("a", encoding="utf-8") as output:
                for row in rows:
                    query_id = str(row["id"])
                    if query_id in completed_ids:
                        continue
                    if max_items is not None and processed_this_call >= max_items:
                        break
                    item = self._evaluate(row)
                    output.write(json.dumps(item, ensure_ascii=False) + "\n")
                    output.flush()
                    completed_ids.add(query_id)
                    processed_this_call += 1
        finally:
            _, peak_memory = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        return self._write_summary(rows, peak_memory)

    def _evaluate(self, row: dict[str, object]) -> dict[str, object]:
        started = time.perf_counter_ns()
        try:
            query = Query(str(row["id"]), str(row["query"]))
            result = self.retriever.retrieve(query)
            retrieved = [{"section_id": hit.section_id, "score": hit.score} for hit in result.hits]
            section_ids = [str(hit["section_id"]) for hit in retrieved]
            gold_value = row.get("gold")
            if not isinstance(gold_value, list):
                raise ValueError("gold must be a list")
            gold = {str(section_id) for section_id in gold_value}
            configured_ks = self._ks()
            per_k = metrics_at_k(section_ids, gold, configured_ks)
            metrics = {
                f"precision@{k}": values["precision"]
                for k, values in per_k.items()
            } | {
                f"recall@{k}": values["recall"]
                for k, values in per_k.items()
            }
            metrics["mrr"] = mean_reciprocal_rank(section_ids, gold)
            return {
                "id": query.id,
                "retrieved": retrieved,
                "metrics": metrics,
                "latency_ms": (time.perf_counter_ns() - started) / 1_000_000,
                "status": "ok",
            }
        except (MisaqError, KeyError, TypeError, ValueError, RuntimeError) as error:
            return {
                "id": str(row["id"]),
                "retrieved": [],
                "metrics": {},
                "latency_ms": (time.perf_counter_ns() - started) / 1_000_000,
                "status": "error",
                "error_type": type(error).__name__,
                "error": str(error),
            }

    def _write_summary(self, rows: list[dict[str, object]], peak_memory: int) -> dict[str, object]:
        items = _read_rows(self.items_path) if self.items_path.exists() else []
        expected = {str(row["id"]) for row in rows}
        item_ids = {str(row["id"]) for row in items}
        failures = [row for row in items if row.get("status") == "error"]
        missing = sorted(expected - item_ids)
        successful = [row for row in items if row.get("status") == "ok"]
        metric_rows: list[dict[str, float]] = []
        for row in successful:
            metric_value = row.get("metrics")
            if isinstance(metric_value, dict):
                metric_rows.append({str(name): float(value) for name, value in metric_value.items()})
        metrics: dict[str, float] = {}
        if metric_rows:
            names = sorted({name for row in metric_rows for name in row})
            metrics = {name: statistics.mean(float(row[name]) for row in metric_rows) for name in names}
        bootstrap = self._bootstrap()
        resamples_value = bootstrap.get("resamples", 10_000)
        seed_value = bootstrap.get("seed", 0)
        resamples = int(resamples_value) if isinstance(resamples_value, (int, str)) else 10_000
        seed = int(seed_value) if isinstance(seed_value, (int, str)) else 0
        confidence_intervals = bootstrap_metric_cis(
            metric_rows,
            resamples=resamples,
            seed=seed,
        )
        latencies = sorted(
            float(value) for row in successful
            if (value := row.get("latency_ms")) is not None
            and isinstance(value, (int, float, str))
        )
        summary: dict[str, object] = {
            "status": "complete" if not failures and not missing else "incomplete",
            "metrics_final": not failures and not missing,
            "metrics": metrics,
            "confidence_intervals": confidence_intervals,
            "counts": {
                "expected": len(expected),
                "completed": len(successful),
                "errors": len(failures),
                "missing": len(missing),
            },
            "failures": failures,
            "latency_ms": {
                "p50": statistics.median(latencies) if latencies else None,
                "p95": _percentile(latencies, 0.95) if latencies else None,
            },
            "peak_memory_bytes": peak_memory,
            "bootstrap": {"resamples": resamples, "seed": seed, "unit": "query"},
        }
        _write_json(self.run_dir / "summary.json", summary)
        return summary

    def _ks(self) -> list[int]:
        value = self.config.get("ks", self.config.get("k", [1, 3, 5, 10]))
        return [int(item) for item in value] if isinstance(value, list) else [1, 3, 5, 10]


def _percentile(values: list[float], probability: float) -> float:
    index = min(len(values) - 1, int(round((len(values) - 1) * probability)))
    return values[index]
