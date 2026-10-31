"""Atomic experiment manifest lifecycle."""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from misaq.domain.errors import ManifestError
from misaq.domain.manifest import DataFingerprint, RunManifest, StageRecord
from misaq.experiments.fingerprint import (
    config_sha256,
    environment_fingerprint,
    git_info,
    sha256_file,
)


def make_run_id(name: str, when: datetime, config_hash: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-_") or "run"
    return f"{safe_name}_{when:%Y-%m-%dT%H-%M}_{config_hash[:6]}"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n",
                                     dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content.replace("\r\n", "\n").replace("\r", "\n"))
    temporary.replace(path)


def _relative_path(path: Path, root: Path) -> str:
    absolute = path.resolve()
    try:
        return os.path.relpath(absolute, Path.cwd().resolve())
    except ValueError:
        return os.path.relpath(absolute, root.resolve())


class ExperimentRun:
    def __init__(self, root: Path, manifest: RunManifest):
        self.root = root
        self.run_dir = root / manifest.run_id
        self.manifest = manifest

    @classmethod
    def create(
        cls,
        root: Path,
        name: str,
        config: Any,
        *,
        clock: Callable[[], datetime],
        kind: str = "experiment",
        data: tuple[DataFingerprint, ...] = (),
        params: dict[str, object] | None = None,
        models: dict[str, object] | None = None,
        seed: int | None = None,
        git_runner: Callable[..., Any] | None = None,
        cwd: Path | None = None,
    ) -> ExperimentRun:
        if isinstance(config, (str, Path)) and Path(config).exists():
            resolved = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
        elif isinstance(config, str):
            resolved = yaml.safe_load(config)
        else:
            resolved = config
        config_hash = config_sha256(resolved)
        created_at = clock()
        run_id = make_run_id(name, created_at, config_hash)
        run_dir = root / run_id
        manifest_path = run_dir / "manifest.json"
        if manifest_path.exists():
            existing = RunManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
            if existing.status == "finished":
                raise ManifestError(f"Finished run already exists: {run_id}")
        git = git_info(cwd, git_runner)
        manifest = RunManifest(
            run_id, kind, created_at.isoformat(), git["commit"], git["dirty"], config_hash,
            data=tuple(DataFingerprint(_relative_path(Path(item.path), root), item.sha256, item.bytes, item.category)
                      for item in data),
            params=params or {}, env=environment_fingerprint(),
            git_branch=git["branch"], git_available=git["available"], models=models or {}, seed=seed)
        run = cls(root, manifest)
        run._write_manifest()
        _atomic_write(run.run_dir / "resolved_config.yaml", yaml.safe_dump(
            resolved, sort_keys=True, allow_unicode=True, default_flow_style=False))
        return run

    @classmethod
    def load(cls, root: Path, run_id: str) -> ExperimentRun:
        path = root / run_id / "manifest.json"
        if not path.exists():
            raise ManifestError(f"Manifest does not exist: {path}")
        return cls(root, RunManifest.from_dict(json.loads(path.read_text(encoding="utf-8"))))

    def _write_manifest(self) -> None:
        _atomic_write(self.run_dir / "manifest.json", json.dumps(
            self.manifest.to_dict(), ensure_ascii=False, indent=2, separators=(",", ": "))+ "\n")

    def update_stage(self, name: str, status: str, started_at: str, finished_at: str | None = None,
                     counts: dict[str, int] | None = None, error: str | None = None) -> None:
        stages = tuple(stage for stage in self.manifest.stages if stage.name != name)
        values = {field: getattr(self.manifest, field) for field in self.manifest.__dataclass_fields__}
        values["stages"] = stages + (StageRecord(name, status, started_at, finished_at, counts or {}, error),)
        self.manifest = RunManifest(**values)
        self._write_manifest()

    def finalize(self, outputs: dict[str, Path], *, clock: Callable[[], datetime],
                 git_runner: Callable[..., Any] | None = None, cwd: Path | None = None) -> None:
        git = git_info(cwd, git_runner)
        if git["available"] and git["dirty"]:
            raise ManifestError("Cannot finalize a run with a dirty git tree")
        fingerprints = {}
        for name, path in outputs.items():
            fingerprint = sha256_file(path).to_dict()
            fingerprint["path"] = _relative_path(path, self.root)
            fingerprints[name] = fingerprint
        values = {field: getattr(self.manifest, field) for field in self.manifest.__dataclass_fields__}
        values.update({"outputs": fingerprints, "status": "finished", "git_commit": git["commit"],
                       "git_branch": git["branch"], "git_dirty": git["dirty"],
                       "git_available": git["available"]})
        self.manifest = RunManifest(**values)
        self._write_manifest()
