import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

from misaq.domain.enums import ActCode, BlockType, SectionStatus
from misaq.domain.generation import Clause
from misaq.domain.statute import Act, Block, Section
from misaq.generation.backends import cloud as cloud_module
from misaq.generation.backends.base import AuthError, BackendResponse, GenerationParams, RateLimitError
from misaq.generation.backends.cloud import CloudBackend
from misaq.generation.backends.local import LocalBackend
from misaq.generation.cache import ReplayCache, cache_key
from misaq.generation.pipeline import GenerationPipeline
from misaq.generation.prompts import assemble_prompt
from misaq.verification.registry import Alias, CorpusRegistry


class StubBackend:
    def __init__(self, responses=None, fail_on=(), invalid=False):
        self.calls = []
        self.responses = responses or {}
        self.fail_on = set(fail_on)
        self.invalid = invalid

    def generate(self, prompt, params):
        self.calls.append((prompt, params))
        if len(self.calls) in self.fail_on:
            raise RuntimeError("stub backend error")
        if params.structured and self.invalid:
            return BackendResponse("not json")
        if params.structured:
            return BackendResponse(json.dumps({
                "claims": [{"issue": "issue", "explanation": "explanation",
                            "citations": ["s. 73 of Contract Act"]}],
                "no_supported_provision": False,
            }), {"model": "stub"})
        return BackendResponse("See s. 73 of Contract Act", {"model": "stub"})


def _registry():
    act = Act(ActCode.CA1872, "synthetic", "hash", (
        Section(ActCode.CA1872, "73", "Damages", "Damages", None, None,
                SectionStatus.IN_FORCE, (1,), (Block(BlockType.BODY, "text"),)),
    ))
    return CorpusRegistry.from_acts((act,), (Alias("CA1872", "Contract Act", True),))


def _pipeline(tmp_path, backend, system="all"):
    clauses = [
        Clause("c1", "Clause one", True, "synthetic", "synthetic", ("CA1872:s73",)),
        Clause("c2", "Clause two", False, "synthetic", "synthetic"),
        Clause("c3", "Clause three", True, "synthetic", "synthetic"),
    ]
    sections = {"CA1872:s73": {"id": "CA1872:s73", "act": "Contract Act, 1872", "text": "section"}}
    return GenerationPipeline(
        clauses, backend, GenerationParams("stub-model", 0.0, 1.0, 100),
        system=system, registry=_registry(), sections=sections,
        cache=ReplayCache(tmp_path / "cache.jsonl"), run_dir=tmp_path / "run",
    )


def _all_cloud_pipeline(tmp_path, backend):
    pipeline = _pipeline(tmp_path, backend)
    pipeline.clauses = [
        Clause("c1", "Clause one", True, "synthetic", "synthetic", ("CA1872:s73",)),
        Clause("c2", "Clause two", True, "synthetic", "synthetic"),
        Clause("c3", "Clause three", True, "synthetic", "synthetic"),
    ]
    return pipeline


def test_prompt_protocol_and_leaks():
    clause = Clause("c", "PRIVATE CLAUSE", True)
    evidence = [{"id": "CA1872:s73", "act": "Contract Act, 1872", "text": "RETRIEVED"}]
    oracle = [{"id": "CA1872:s74", "act": "Contract Act, 1872", "text": "ORACLE"}]
    assert "PRIVATE CLAUSE" in assemble_prompt("S1", clause)
    assert "RETRIEVED" not in assemble_prompt("S1", clause, retrieved=evidence)
    assert "RETRIEVED" not in assemble_prompt("S2", clause, retrieved=evidence)
    assert "ORACLE" not in assemble_prompt("S3", clause, retrieved=evidence, oracle=oracle)
    assert "ORACLE" not in assemble_prompt("S1", clause, oracle=oracle)
    assert "ORACLE" in assemble_prompt("S4", clause, oracle=oracle)


def test_s4_empty_oracle_uses_exact_protocol_line():
    prompt = assemble_prompt("S4", Clause("c", "clause", True))
    assert prompt.count("No in-scope provision was identified for this clause.") == 1


def test_cache_key_and_hit(tmp_path):
    params = GenerationParams("m", 0.1, 1.0, 10)
    cache = ReplayCache(tmp_path / "cache.jsonl")
    cache.put("p", params, BackendResponse("exact", {"x": 1}))
    assert cache.get("p", params).raw_text == "exact"
    assert cache_key("p", params) == cache_key("p", params)
    assert cache_key("p", params) != cache_key("q", params)


def test_pipeline_cache_hit_never_calls_backend(tmp_path):
    backend = StubBackend()
    pipeline = _pipeline(tmp_path, backend, system="S1")
    pipeline._record(pipeline.clauses[0], "S1")
    pipeline._record(pipeline.clauses[0], "S1")
    assert len(backend.calls) == 1


def test_three_synthetic_clauses_x_four_systems(tmp_path):
    backend = StubBackend()
    pipeline = _all_cloud_pipeline(tmp_path, backend)
    pipeline.run()
    rows = [json.loads(line) for line in (tmp_path / "run" / "items.jsonl").read_text().splitlines()]
    assert len(rows) == 12
    assert {(row["clause_id"], row["system"]) for row in rows} == {
        (f"c{clause}", system) for clause in range(1, 4) for system in ("S1", "S2", "S3", "S4")
    }


def test_same_model_and_decoding_params_across_systems(tmp_path):
    backend = StubBackend()
    pipeline = _pipeline(tmp_path, backend)
    pipeline.run()
    values = {(params.model, params.temperature, params.top_p, params.max_output_tokens, params.seed)
              for _, params in backend.calls}
    assert values == {("stub-model", 0.0, 1.0, 100, None)}


def test_pipeline_privacy_parse_error_and_resume(tmp_path):
    backend = StubBackend()
    pipeline = _pipeline(tmp_path, backend)
    result = pipeline.run(max_items=1)
    assert result["items"] == 1
    result = pipeline.run()
    assert result["items"] == 11
    rows = [json.loads(line) for line in (tmp_path / "run" / "items.jsonl").read_text().splitlines()]
    assert len(rows) == 12
    assert any(row["error_type"] == "PRIVACY" for row in rows)
    assert all("system" in row for row in rows)
    assert (tmp_path / "run" / "manifest.json").exists()
    assert (tmp_path / "run" / "resolved_config.yaml").exists()


def test_backend_error_is_recorded_and_run_continues(tmp_path):
    pipeline = _pipeline(tmp_path, StubBackend(fail_on={1}))
    pipeline.run()
    rows = [json.loads(line) for line in (tmp_path / "run" / "items.jsonl").read_text().splitlines()]
    assert len(rows) == 12
    assert sum(row["status"] == "error" for row in rows) >= 2
    assert any(row["error"] == "stub backend error" for row in rows)


def test_verification_and_context_fields_are_recorded(tmp_path):
    class Retriever:
        def retrieve(self, query):
            return types.SimpleNamespace(hits=(types.SimpleNamespace(section_id="CA1872:s73"),))

    pipeline = _pipeline(tmp_path, StubBackend(), system="all")
    pipeline.retriever = Retriever()
    pipeline.run()
    rows = [json.loads(line) for line in (tmp_path / "run" / "items.jsonl").read_text().splitlines()]
    c1 = {(row["clause_id"], row["system"]): row for row in rows if row["clause_id"] == "c1"}
    assert c1[("c1", "S1")]["in_context"] is None
    assert c1[("c1", "S2")]["in_context"] is None
    assert c1[("c1", "S3")]["in_context"] == ["CA1872:s73"]
    assert c1[("c1", "S3")]["retrieved_section_ids"] == ["CA1872:s73"]
    assert c1[("c1", "S4")]["in_context"] == ["CA1872:s73"]
    assert c1[("c1", "S4")]["oracle_section_ids"] == ["CA1872:s73"]
    assert c1[("c1", "S1")]["citations"][0]["verdict"] == "valid"


def test_manifest_contains_prompt_hashes_and_verifier_version(tmp_path):
    pipeline = _pipeline(tmp_path, StubBackend(), system="S1")
    pipeline.run()
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    assert set(manifest["params"]["prompt_hashes"]) == {"s1_plain", "s2_structured", "s3_s4_grounded"}
    assert manifest["params"]["verification_algorithm_version"] == "1"


def test_manifest_and_resolved_config_exist_before_first_item(tmp_path):
    run_dir = tmp_path / "run"

    class ObservingBackend(StubBackend):
        def generate(self, prompt, params):
            assert (run_dir / "manifest.json").exists()
            assert (run_dir / "resolved_config.yaml").exists()
            return super().generate(prompt, params)

    _pipeline(tmp_path, ObservingBackend(), system="S1").run()


def test_local_backend_has_clear_failure():
    with pytest.raises(RuntimeError, match="local feasibility test not run"):
        LocalBackend().generate("prompt", GenerationParams("model", 0.0, 1.0, 10))


def test_dry_run_does_not_call_backend(tmp_path):
    backend = StubBackend()
    result = _pipeline(tmp_path, backend).run(dry_run=True)
    assert result["planned_calls"] == 8
    assert not backend.calls


def test_dry_run_uses_system_specific_cache_params(tmp_path):
    backend = StubBackend()
    pipeline = _pipeline(tmp_path, backend, system="S2")
    prompt = assemble_prompt("S2", pipeline.clauses[0])
    pipeline.cache.put(prompt, GenerationParams("stub-model", 0.0, 1.0, 100, None, True),
                       BackendResponse("cached"))
    result = pipeline.run(dry_run=True)
    assert result["cache_hits"] == 1
    assert result["planned_calls"] == 1


def test_structured_parse_failure_is_recorded(tmp_path):
    pipeline = _pipeline(tmp_path, StubBackend(invalid=True), system="S2")
    pipeline.run()
    row = json.loads((tmp_path / "run" / "items.jsonl").read_text().splitlines()[0])
    assert row["status"] == "error"
    assert row["error_type"] == "OUTPUT_PARSE"
    assert row["raw_text"] == "not json"


def test_cloud_backend_explicitly_disables_tools(monkeypatch):
    configs = []

    class Config:
        def __init__(self, **kwargs):
            configs.append(kwargs)

    class Models:
        def generate_content(self, **kwargs):
            return types.SimpleNamespace(text="ok", model_version="stub")

    google = types.ModuleType("google")
    genai = types.ModuleType("google.genai")
    genai.types = types.SimpleNamespace(GenerateContentConfig=Config)
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    backend = CloudBackend("UNUSED", 10, 1, client=types.SimpleNamespace(models=Models()))
    backend.generate("prompt", GenerationParams("model", 0.0, 1.0, 10))
    assert configs[0]["tools"] == []


def test_cloud_backend_missing_key_raises_auth_error(monkeypatch):
    google = types.ModuleType("google")
    genai = types.ModuleType("google.genai")
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.delenv("MISAQ_TEST_MISSING_KEY", raising=False)

    with pytest.raises(AuthError, match="MISAQ_TEST_MISSING_KEY"):
        CloudBackend("MISAQ_TEST_MISSING_KEY", 10, 1)


def test_smoke_bypasses_cache(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).parents[2] / "scripts" / "06_run_exp_c.py"
    spec = importlib.util.spec_from_file_location("run_exp_c", script_path)
    assert spec is not None and spec.loader is not None
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "backends.yaml").write_text(
        "cloud:\n"
        "  model: configured-model\n"
        "  temperature: 0.0\n"
        "  top_p: 1.0\n"
        "  max_output_tokens: 10\n"
        "  requests_per_minute: 10\n"
        "  max_calls: 1\n"
        "  api_key_env: MISAQ_TEST_KEY\n",
        encoding="utf-8",
    )
    cache_path = tmp_path / "runs" / "exp_c_smoke_cache.jsonl"
    cache_path.parent.mkdir()
    cache_path.write_text(
        '{"key":"old","raw_text":"cached","metadata":{"model_version":"cached"}}\n',
        encoding="utf-8",
    )

    class StubSmokeBackend:
        def __init__(self):
            self.calls = 0

        def generate(self, prompt, params):
            self.calls += 1
            return BackendResponse("live", {"model_version": "response-model", "prompt_tokens": 2})

    backend = StubSmokeBackend()
    monkeypatch.setattr(script, "ROOT", tmp_path)
    assert script.smoke(backend) == 0
    output = json.loads(capsys.readouterr().out)
    assert backend.calls == 1
    assert output == {
        "model_version": "response-model",
        "tools": [],
        "latency_ms": output["latency_ms"],
        "cache_used": False,
        "prompt_tokens": 2,
    }
    assert cache_path.read_text(encoding="utf-8") == (
        '{"key":"old","raw_text":"cached","metadata":{"model_version":"cached"}}\n'
    )


def test_smoke_loads_dotenv_without_overriding_environment(tmp_path, monkeypatch):
    script_path = Path(__file__).parents[2] / "scripts" / "06_run_exp_c.py"
    spec = importlib.util.spec_from_file_location("run_exp_c_dotenv", script_path)
    assert spec is not None and spec.loader is not None
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    env_path = tmp_path / ".env"
    env_path.write_text(
        'MISAQ_TEST_DOTENV="from-file"\nexport MISAQ_TEST_EXPORTED=exported\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("MISAQ_TEST_DOTENV", "from-environment")
    script.load_dotenv(env_path)
    assert os.environ["MISAQ_TEST_DOTENV"] == "from-environment"
    assert os.environ["MISAQ_TEST_EXPORTED"] == "exported"


def test_cloud_backend_enforces_rate_limit_and_max_calls(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(cloud_module.time, "monotonic", lambda: clock[0])

    class Models:
        def generate_content(self, **kwargs):
            return types.SimpleNamespace(text="ok", model_version="stub")

    class Config:
        def __init__(self, **kwargs):
            pass

    google = types.ModuleType("google")
    genai = types.ModuleType("google.genai")
    genai.types = types.SimpleNamespace(GenerateContentConfig=Config)
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)

    def sleep(seconds):
        clock[0] += seconds

    backend = CloudBackend("UNUSED", 1, 2, client=types.SimpleNamespace(models=Models()), sleep=sleep)
    params = GenerationParams("model", 0.0, 1.0, 10)
    backend.generate("one", params)
    backend.generate("two", params)
    with pytest.raises(RateLimitError, match="max_calls"):
        backend.generate("three", params)
