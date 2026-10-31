"""Deterministic fingerprints for experiment inputs and execution environments."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path
from typing import Any, Callable, TypedDict

import yaml

from misaq.domain.manifest import DataFingerprint


class GitInfo(TypedDict):
    available: bool
    commit: str | None
    branch: str | None
    dirty: bool | None


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_file(path: Path, category: str = "file") -> DataFingerprint:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return DataFingerprint(str(path), digest.hexdigest(), size, category)


def config_sha256(config: Any) -> str:
    if isinstance(config, (str, Path)):
        with Path(config).open("r", encoding="utf-8", newline=None) as stream:
            config = yaml.safe_load(stream)
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()


def environment_fingerprint() -> dict[str, object]:
    try:
        import psutil
        ram = int(psutil.virtual_memory().total)
    except ImportError:
        ram = 0
    packages = sorted(
        f"{distribution.metadata['Name']}=={distribution.version}"
        for distribution in importlib.metadata.distributions()
    )
    package_hash = hashlib.sha256("\n".join(packages).encode("utf-8")).hexdigest()
    return {
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "ram_bytes": ram,
        "packages_sha256": package_hash,
        "packages_basis": "importlib.metadata name==version list (pip freeze stand-in)",
    }


def git_info(
    cwd: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> GitInfo:
    run = runner or subprocess.run
    try:
        commit = run(["git", "rev-parse", "HEAD"], cwd=cwd, check=True,
                     capture_output=True, text=True).stdout.strip()
        branch = run(["git", "branch", "--show-current"], cwd=cwd, check=True,
                     capture_output=True, text=True).stdout.strip()
        dirty_result = run(["git", "status", "--porcelain"], cwd=cwd, check=True,
                           capture_output=True, text=True)
        return {"available": True, "commit": commit, "branch": branch, "dirty": bool(dirty_result.stdout)}
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "commit": None, "branch": None, "dirty": None}
