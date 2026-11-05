import json
from pathlib import Path

import pytest

from misaq.evaluation.ingestion_eval import (
    bootstrap_contract_ci,
    evaluate_contract,
    load_gold,
    validate_gold,
)


def _rows():
    return [
        {"paragraph_index": 0, "role": "heading", "level": 1, "is_clause_start": True},
        {"paragraph_index": 1, "role": "body", "level": 1, "is_clause_start": False},
        {"paragraph_index": 2, "role": "body", "level": 1, "is_clause_start": True},
    ]


def test_ingestion_metrics_and_contract_bootstrap():
    metrics = evaluate_contract(_rows(), _rows())
    assert metrics["clause_start_f1"] == 1.0
    assert metrics["clause_count_absolute_error"] == 0
    low, high = bootstrap_contract_ci([metrics, {**metrics, "clause_start_f1": 0.0}], "clause_start_f1",
                                      resamples=100, seed=2)
    assert 0.0 <= low <= high <= 1.0


def test_gold_validator_rejects_missing_fields():
    with pytest.raises(ValueError, match="exactly"):
        validate_gold([{"paragraph_index": 0}], {})


def test_gold_loader_validates_manifest(tmp_path: Path):
    gold = tmp_path / "contract.jsonl"
    gold.write_text(json.dumps(_rows()[0]) + "\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({
        "contract_id": "c", "agreement_type": "nda", "source_url": "https://example.test",
        "licence": "CC", "file_hash": "abc", "split": "dev", "reader_fingerprint": "fp",
    }), encoding="utf-8")
    rows, manifest = load_gold(gold)
    assert len(rows) == 1
    assert manifest["split"] == "dev"
