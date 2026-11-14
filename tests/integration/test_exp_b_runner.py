import importlib.util
import json
from pathlib import Path
from typing import cast

import pytest

from misaq.domain.chunking import Chunk, ChunkingSpec
from misaq.domain.embedding import EmbeddingModelSpec
from misaq.domain.errors import DataValidationError, IndexFilesMissingError
from misaq.domain.retrieval import Query
from misaq.embedding.fake import FakeEmbedder
from misaq.experiments.runner import ExperimentRunner
from misaq.indexing.index import FaissIndex
from misaq.retrieval.retriever import DenseRetriever


def test_test_split_guard_requires_final(tmp_path: Path):
    module = _script_module()

    try:
        module.guard_test_split(tmp_path, tmp_path / "eval.jsonl", False)
    except RuntimeError as error:
        assert str(error) == "test split requires --final"
    else:
        raise AssertionError("test split guard did not refuse")


def test_find_index_missing_files_includes_build_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    module = _script_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    pipeline_path = tmp_path / "configs" / "pipeline.yaml"
    pipeline_path.parent.mkdir(parents=True)
    pipeline_path.write_text(
        "models:\n  bge-small-en-v1.5:\n    hf_id: BAAI/bge-small-en-v1.5\n",
        encoding="utf-8",
    )
    index_dir = tmp_path / "data" / "index" / "test-index"
    index_dir.mkdir(parents=True)
    (index_dir / "index_meta.json").write_text(
        json.dumps({
            "model": {"hf_id": "BAAI/bge-small-en-v1.5"},
            "chunking": {"strategy": "section_aware"},
        }),
        encoding="utf-8",
    )

    with pytest.raises(IndexFilesMissingError) as error:
        module._find_index("bge-small-en-v1.5", "section_aware")

    assert str(error.value) == (
        "index files are missing (chunks.jsonl, faiss.bin) for "
        "model=bge-small-en-v1.5, chunking=section_aware; build with: "
        "python scripts\\03_build_index.py --model bge-small-en-v1.5 "
        "--chunking section_aware"
    )


def _script_module():
    spec = importlib.util.spec_from_file_location("run_exp_b", Path("scripts/05_run_exp_b.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _retriever():
    spec = EmbeddingModelSpec("fake", "rev", 4, 32, True, "", "", "mean", False, 2)
    embedder = FakeEmbedder(spec)
    chunks = [
        Chunk("A:1#0", "A:1", "A", "1", "One", None, None, "one", "one", (), (), (0,)),
        Chunk("A:2#0", "A:2", "A", "2", "Two", None, None, "two", "two", (), (), (1,)),
    ]
    index = FaissIndex.build(chunks, embedder, ("hash",), ChunkingSpec("fixed_size", 8, 1, "fake"), 0, 0)
    return DenseRetriever(index, embedder, top_n=2, top_k=2)


def _write_eval(path: Path):
    rows = [
        {"id": "q1", "query": "one", "gold": ["A:1"], "split": "dev"},
        {"id": "q2", "query": "two", "gold": ["A:2"], "split": "dev"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_runner_normal_run_and_resume(tmp_path: Path):
    eval_path = tmp_path / "eval.jsonl"
    _write_eval(eval_path)
    calls: list[str] = []

    class CountingRetriever:
        def retrieve(self, query: Query):
            calls.append(query.id)
            return _retriever().retrieve(query)

    runner = ExperimentRunner(
        CountingRetriever(), eval_path, tmp_path / "run",
        {"ks": [1, 2], "bootstrap": {"resamples": 50, "seed": 2},
         "retrieval_algorithm_version": "r1", "verification_algorithm_version": "v1"},
    )
    manifest_path = tmp_path / "run" / "manifest.json"
    assert manifest_path.is_file()
    assert not (tmp_path / "run" / "items.jsonl").exists()

    first = runner.run(max_items=1)
    assert first["status"] == "incomplete"
    assert len((tmp_path / "run" / "items.jsonl").read_text(encoding="utf-8").splitlines()) == 1

    resumed = runner.run()
    assert resumed["status"] == "complete"
    counts = cast(dict[str, int], resumed["counts"])
    assert counts["completed"] == 2
    assert len((tmp_path / "run" / "items.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert calls == ["q1", "q2"]
    manifest = cast(dict[str, object], json.loads(manifest_path.read_text(encoding="utf-8")))
    params = cast(dict[str, object], manifest["params"])
    assert params["retrieval_algorithm_version"] == "r1"
    assert params["verification_algorithm_version"] == "v1"
    latency = cast(dict[str, object], first["latency_ms"])
    assert latency["p50"] is not None
    assert latency["p95"] is not None
    assert isinstance(first["peak_memory_bytes"], int)


def test_runner_records_error_and_continues(tmp_path: Path):
    eval_path = tmp_path / "eval.jsonl"
    _write_eval(eval_path)

    class FailingRetriever:
        def retrieve(self, query: Query):
            if query.id == "q1":
                raise ValueError("synthetic failure")
            return _retriever().retrieve(query)

    runner = ExperimentRunner(
        FailingRetriever(), eval_path, tmp_path / "run", {"ks": [1], "bootstrap": {"resamples": 20}}
    )
    summary = runner.run()

    assert summary["status"] == "incomplete"
    rows = [json.loads(line) for line in (tmp_path / "run" / "items.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["status"] == "error"
    assert rows[0]["error_type"] == "ValueError"
    assert rows[1]["status"] == "ok"
    assert len(rows) == 2


def test_test_split_guard_refuses_dirty_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = _script_module()
    monkeypatch.setattr(module, "git_info", lambda root: {"dirty": True})

    with pytest.raises(RuntimeError, match="test split requires a clean git tree"):
        module.guard_test_split(tmp_path, tmp_path / "eval.jsonl", True)


def test_test_split_guard_refuses_unlisted_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = _script_module()
    eval_path = tmp_path / "eval.jsonl"
    eval_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "git_info", lambda root: {"dirty": False})
    monkeypatch.setattr(module, "check_processed_hashes", lambda path: None)

    with pytest.raises(RuntimeError, match="test split eval file hash is not listed"):
        module.guard_test_split(tmp_path, eval_path, True)


def test_listed_eval_hash_matches_fingerprint_digest(tmp_path: Path):
    module = _script_module()
    eval_path = tmp_path / "eval.jsonl"
    eval_path.write_text("{}", encoding="utf-8")
    digest = module.sha256_file(eval_path).sha256
    (tmp_path / "SHA256SUMS").write_text(f"{digest}  eval.jsonl\n", encoding="utf-8")

    assert module._listed_eval_hash(eval_path)


def test_main_refuses_eval_validation_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = _script_module()
    config_path = tmp_path / "config.yaml"
    eval_path = tmp_path / "eval.jsonl"
    eval_path.write_text("{}", encoding="utf-8")
    config_path.write_text("eval_file: eval.jsonl\n", encoding="utf-8")
    monkeypatch.setattr(module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(module, "_acts", lambda: ())

    def fail_validation(path, acts):
        raise DataValidationError("synthetic validation failure")

    monkeypatch.setattr(module, "validate_eval_jsonl", fail_validation)
    with pytest.raises(DataValidationError, match="synthetic validation failure"):
        module.main("fake", "section_aware", "dev", False)
