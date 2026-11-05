"""Pure evaluation metrics for contract-ingestion annotations."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Sequence


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def evaluate_contract(predicted: Sequence[dict[str, Any]], gold: Sequence[dict[str, Any]]) -> dict[str, float]:
    pred_starts = {i for i, row in enumerate(predicted) if row.get("is_clause_start") is True}
    gold_starts = {i for i, row in enumerate(gold) if row.get("is_clause_start") is True}
    true = len(pred_starts & gold_starts)
    precision = true / len(pred_starts) if pred_starts else 0.0
    recall = true / len(gold_starts) if gold_starts else (1.0 if not pred_starts else 0.0)
    matched = pred_starts & gold_starts
    level = sum(predicted[i].get("level") == gold[i].get("level") for i in matched) / len(matched) if matched else 0.0
    role_matches = sum(
        predicted[i].get("role") == gold[i].get("role")
        for i in range(min(len(predicted), len(gold)))
    )
    role = role_matches / max(len(gold), 1)
    return {
        "clause_start_precision": precision, "clause_start_recall": recall,
        "clause_start_f1": _f1(precision, recall), "level_accuracy": level,
        "element_role_accuracy": role, "clause_count_absolute_error": abs(len(pred_starts) - len(gold_starts)),
        "coverage": len(predicted) / len(gold) if gold else 1.0,
    }


def bootstrap_contract_ci(contract_metrics: Sequence[dict[str, float]], metric: str,
                          resamples: int = 10_000, seed: int = 0,
                          confidence: float = 0.95) -> tuple[float, float]:
    if not contract_metrics or resamples <= 0 or not 0 < confidence < 1:
        raise ValueError("metrics, resamples, and confidence must be valid")
    values = [row[metric] for row in contract_metrics]
    rng = random.Random(seed)
    samples = [sum(rng.choice(values) for _ in values) / len(values) for _ in range(resamples)]
    samples.sort()
    tail = (1 - confidence) / 2
    return samples[int(tail * (len(samples) - 1))], samples[int((1 - tail) * (len(samples) - 1))]


def validate_gold(records: Sequence[dict[str, Any]], manifest: dict[str, Any]) -> None:
    required = {"paragraph_index", "role", "level", "is_clause_start"}
    if not records or any(set(row) != required for row in records):
        raise ValueError("gold rows must contain exactly paragraph_index, role, level, is_clause_start")
    indexes = [row["paragraph_index"] for row in records]
    if indexes != list(range(len(records))):
        raise ValueError("gold paragraph_index values must be contiguous from zero")
    if any(not isinstance(row["role"], str) or not row["role"].strip() for row in records):
        raise ValueError("gold role must be non-empty text")
    if any(not isinstance(row["level"], int) or row["level"] < 0 for row in records):
        raise ValueError("gold level must be a non-negative integer")
    if any(not isinstance(row["is_clause_start"], bool) for row in records):
        raise ValueError("gold is_clause_start must be boolean")
    for key in ("contract_id", "agreement_type", "source_url", "licence", "file_hash", "split", "reader_fingerprint"):
        if not manifest.get(key):
            raise ValueError(f"gold manifest missing {key}")


def load_gold(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_path = path.with_name("manifest.json")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_gold(rows, manifest)
    return rows, manifest
