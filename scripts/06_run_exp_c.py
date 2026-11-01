"""Run Experiment C generation; the cloud owner supplies the real API key."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import yaml

from misaq.generation.backends.base import AuthError, GenerationBackend, GenerationParams
from misaq.generation.backends.cloud import CloudBackend
from misaq.generation.backends.local import LocalBackend
from misaq.generation.cache import ReplayCache
from misaq.generation.pipeline import GenerationPipeline, load_clauses

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name.startswith("export "):
            name = name[7:].strip()
        if value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        if name:
            os.environ.setdefault(name, value)


def smoke(backend: GenerationBackend | None = None) -> int:
    load_dotenv(ROOT / ".env")
    config = yaml.safe_load((ROOT / "configs/backends.yaml").read_text(encoding="utf-8"))["cloud"]
    params = GenerationParams(str(config["model"]), float(config["temperature"]), float(config["top_p"]),
                              int(config["max_output_tokens"]), config.get("seed"))
    prompt = "In one sentence, explain what a contract is."
    started = time.perf_counter_ns()
    selected_backend = backend or CloudBackend(
        str(config["api_key_env"]), int(config["requests_per_minute"]), int(config["max_calls"]),
        max_retries=0,
    )
    response = selected_backend.generate(prompt, params)
    result: dict[str, object] = {
        "model_version": response.metadata.get("model_version", "not provided"),
        "tools": [],
        "latency_ms": (time.perf_counter_ns() - started) / 1_000_000,
        "cache_used": False,
    }
    for key in ("prompt_tokens", "output_tokens"):
        if key in response.metadata and response.metadata[key] is not None:
            result[key] = response.metadata[key]
    print(json.dumps(result))
    return 0


def main(system: str, backend_name: str, split: str, dry_run: bool, smoke_mode: bool = False) -> int:
    if smoke_mode:
        return smoke()
    config = yaml.safe_load((ROOT / "configs/backends.yaml").read_text(encoding="utf-8"))[backend_name]
    clauses_path = ROOT / "data" / "eval" / "exp_c_clauses.jsonl"
    if not clauses_path.exists():
        raise RuntimeError("Experiment C clause input is not present; use a synthetic tmp_path fixture")
    clauses = load_clauses(clauses_path, split)
    params = GenerationParams(str(config["model"]), float(config["temperature"]), float(config["top_p"]),
                              int(config["max_output_tokens"]), config.get("seed"))
    backend = LocalBackend() if backend_name == "local" else CloudBackend(
        str(config["api_key_env"]), int(config["requests_per_minute"]), int(config["max_calls"]))
    pipeline = GenerationPipeline(
        clauses, backend, params, system=system,
        cache=ReplayCache(ROOT / "runs" / "exp_c_cache.jsonl"),
        run_dir=ROOT / "runs" / f"exp_c_{split}",
        requests_per_minute=int(config["requests_per_minute"]),
    )
    print(json.dumps(pipeline.run(dry_run=dry_run), indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", choices=("S1", "S2", "S3", "S4", "all"), default="all")
    parser.add_argument("--backend", choices=("cloud", "local"), default="cloud")
    parser.add_argument("--split", choices=("pilot", "pool"), default="pilot")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true",
                        help="send one public toy prompt through the real cloud backend")
    args = parser.parse_args()
    try:
        raise SystemExit(main(args.system, args.backend, args.split, args.dry_run, args.smoke))
    except AuthError as error:
        parser.exit(1, f"AuthError: {error}\n")
