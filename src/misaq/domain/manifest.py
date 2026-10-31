"""Run manifest: everything needed to reproduce or audit one run."""
from __future__ import annotations

from dataclasses import dataclass, field

MANIFEST_VERSION = "1.0"


@dataclass(frozen=True)
class DataFingerprint:
    path: str
    sha256: str
    bytes: int
    category: str = "file"

    def to_dict(self) -> dict:
        return {"path": self.path, "sha256": self.sha256, "bytes": self.bytes, "category": self.category}

    @classmethod
    def from_dict(cls, value: dict) -> DataFingerprint:
        return cls(value["path"], value["sha256"], value["bytes"], value.get("category", "file"))


@dataclass(frozen=True)
class StageRecord:
    name: str
    status: str                       # "running" | "ok" | "failed"
    started_at: str                   # ISO-8601, supplied by the caller
    finished_at: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "started_at": self.started_at,
                "finished_at": self.finished_at, "counts": dict(self.counts), "error": self.error}

    @classmethod
    def from_dict(cls, value: dict) -> StageRecord:
        return cls(value["name"], value["status"], value["started_at"], value.get("finished_at"),
                   dict(value.get("counts", {})), value.get("error"))


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    kind: str                         # "parse" | "exp_b" | "exp_c" | ...
    created_at: str
    git_commit: str | None
    git_dirty: bool | None
    config_hash: str
    data: tuple[DataFingerprint, ...] = ()
    params: dict[str, object] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    stages: tuple[StageRecord, ...] = ()
    manifest_version: str = MANIFEST_VERSION
    git_branch: str | None = None
    git_available: bool | None = None
    models: dict[str, object] = field(default_factory=dict)
    seed: int | None = None
    outputs: dict[str, object] = field(default_factory=dict)
    status: str = "running"

    def to_dict(self) -> dict:
        return {
            "manifest_version": self.manifest_version, "run_id": self.run_id, "kind": self.kind,
            "created_at": self.created_at,
            "git": {"commit": self.git_commit, "branch": self.git_branch, "dirty": self.git_dirty,
                    "available": self.git_available},
            "config_hash": self.config_hash,
            "data": [d.to_dict() for d in self.data], "params": dict(self.params),
            "models": dict(self.models), "seed": self.seed, "env": dict(self.env),
            "stages": [s.to_dict() for s in self.stages], "outputs": dict(self.outputs),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: dict) -> RunManifest:
        git = value.get("git", {})
        return cls(
            run_id=value["run_id"], kind=value["kind"], created_at=value["created_at"],
            git_commit=git.get("commit"), git_dirty=git.get("dirty"), config_hash=value["config_hash"],
            data=tuple(DataFingerprint.from_dict(item) for item in value.get("data", ())),
            params=dict(value.get("params", {})), env=dict(value.get("env", {})),
            stages=tuple(StageRecord.from_dict(item) for item in value.get("stages", ())),
            manifest_version=value.get("manifest_version", MANIFEST_VERSION),
            git_branch=git.get("branch"), git_available=git.get("available"),
            models=dict(value.get("models", {})), seed=value.get("seed"),
            outputs=dict(value.get("outputs", {})), status=value.get("status", "running"))
