"""Exact replay cache for generation calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from .backends.base import BackendResponse, GenerationParams


def cache_key(prompt: str, params: GenerationParams) -> str:
    payload = {"prompt": prompt, "model": params.model, "params": params.to_dict()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ReplayCache:
    def __init__(self, path: Path):
        self.path = path
        self._entries: dict[str, BackendResponse] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._entries[str(row["key"])] = BackendResponse(
                        str(row["raw_text"]), dict(row.get("metadata", {}))
                    )

    def get(self, prompt: str, params: GenerationParams) -> BackendResponse | None:
        return self._entries.get(cache_key(prompt, params))

    def put(self, prompt: str, params: GenerationParams, response: BackendResponse) -> None:
        key = cache_key(prompt, params)
        if key in self._entries:
            return
        self._entries[key] = response
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"key": key, "raw_text": response.raw_text,
                                     "metadata": response.metadata}, ensure_ascii=False) + "\n")

    def planned(self, prompts: Iterable[str], params: GenerationParams, requests_per_minute: int) -> dict[str, object]:
        total = 0
        hits = 0
        for prompt in prompts:
            total += 1
            hits += self.get(prompt, params) is not None
        misses = total - hits
        minutes = misses / requests_per_minute if requests_per_minute > 0 else None
        return {"planned_calls": misses, "cache_hits": hits, "minimum_minutes": minutes}
