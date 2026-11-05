import importlib.util
from pathlib import Path

import pytest


def _module():
    spec = importlib.util.spec_from_file_location("eval_ingestion", Path("scripts/09_eval_ingestion.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_test_split_guard_requires_final(tmp_path: Path):
    with pytest.raises(RuntimeError, match="requires --final"):
        _module().guard_test_split(tmp_path, tmp_path / "gold.jsonl", False)
