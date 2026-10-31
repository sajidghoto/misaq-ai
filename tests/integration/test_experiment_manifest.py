import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from misaq.domain.errors import ManifestError
from misaq.experiments.manifest import ExperimentRun, make_run_id


def clean_git_runner(*args, **kwargs):
    command = args[0]
    output = {"rev-parse": "abc\n", "branch": "main\n", "status": ""}
    key = command[1]
    return subprocess.CompletedProcess(command, 0, output[key], "")


@pytest.mark.integration
def test_manifest_lifecycle(tmp_path: Path):
    now = datetime(2026, 10, 31, 18, 30)
    run = ExperimentRun.create(
        tmp_path, "demo", {"b": 2, "a": 1}, clock=lambda: now, git_runner=clean_git_runner,
        params={"x": 1}, models={"model": {"id": "m", "revision": "r"}}, seed=4)
    assert (run.run_dir / "manifest.json").exists()
    assert (run.run_dir / "resolved_config.yaml").exists()
    run.update_stage("items", "ok", "start", "end", {"items": 2, "failures": 0})
    output = tmp_path / "output.json"
    output.write_text("{}", encoding="utf-8")
    run.finalize({"result": output}, clock=lambda: now, git_runner=clean_git_runner)
    loaded = ExperimentRun.load(tmp_path, run.manifest.run_id)
    assert loaded.manifest.status == "finished"
    result = loaded.manifest.outputs["result"]
    assert isinstance(result, dict)
    assert result["bytes"] == 2
    assert json.loads((loaded.run_dir / "manifest.json").read_text(encoding="utf-8"))["status"] == "finished"
    assert isinstance(result["path"], str)
    assert not Path(result["path"]).is_absolute()


def test_dirty_tree_blocks_finalize(tmp_path: Path):
    def dirty_runner(*args, **kwargs):
        command = args[0]
        output = {"rev-parse": "abc\n", "branch": "main\n", "status": " M x\n"}
        return subprocess.CompletedProcess(command, 0, output[command[1]], "")

    run = ExperimentRun.create(tmp_path, "demo", {}, clock=lambda: datetime(2026, 1, 1), git_runner=dirty_runner)
    with pytest.raises(ManifestError):
        run.finalize({}, clock=lambda: datetime(2026, 1, 1), git_runner=dirty_runner)


def test_manifest_and_config_exist_before_stage_processing(tmp_path: Path):
    run = ExperimentRun.create(
        tmp_path, "demo", {"value": 1}, clock=lambda: datetime(2026, 1, 1),
        git_runner=clean_git_runner)
    assert (run.run_dir / "manifest.json").is_file()
    assert (run.run_dir / "resolved_config.yaml").is_file()
    assert run.manifest.stages == ()


def test_finished_run_cannot_be_overwritten(tmp_path: Path):
    now = datetime(2026, 1, 1)
    run = ExperimentRun.create(tmp_path, "demo", {}, clock=lambda: now, git_runner=clean_git_runner)
    run.finalize({}, clock=lambda: now, git_runner=clean_git_runner)
    with pytest.raises(ManifestError):
        ExperimentRun.create(tmp_path, "demo", {}, clock=lambda: now, git_runner=clean_git_runner)


def test_manifest_writes_utf8_lf_and_replaces_atomically(tmp_path: Path, monkeypatch):
    replacements = []
    original_replace = Path.replace

    def replace(self, target):
        replacements.append((self, target))
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", replace)
    run = ExperimentRun.create(
        tmp_path, "demo", {"message": "café"}, clock=lambda: datetime(2026, 1, 1),
        git_runner=clean_git_runner)
    manifest_path = run.run_dir / "manifest.json"
    raw = manifest_path.read_bytes()
    assert raw.decode("utf-8")
    assert b"\r" not in raw
    assert replacements


def test_run_id_is_clock_deterministic():
    assert make_run_id("a b", datetime(2026, 1, 1, 2, 3), "abcdef123") == "a-b_2026-01-01T02-03_abcdef"
