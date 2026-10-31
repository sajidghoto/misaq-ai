"""Run manifest: everything needed to reproduce or audit one run."""
from __future__ import annotations

from dataclasses import dataclass, field

MANIFEST_VERSION = "1.0"


@dataclass(frozen=True)
class DataFingerprint:
    path: str
    sha256: str
    bytes: int

    def to_dict(self) -> dict:
        return {"path": self.path, "sha256": self.sha256, "bytes": self.bytes}


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

    def to_dict(self) -> dict:
        return {
            "manifest_version": self.manifest_version, "run_id": self.run_id, "kind": self.kind,
            "created_at": self.created_at,
            "git": {"commit": self.git_commit, "dirty": self.git_dirty},
            "config_hash": self.config_hash,
            "data": [d.to_dict() for d in self.data], "params": dict(self.params),
            "env": dict(self.env), "stages": [s.to_dict() for s in self.stages],
        }
