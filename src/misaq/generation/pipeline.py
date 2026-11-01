"""Resumable Experiment C generation pipeline."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import yaml

from misaq.domain.citation import Citation
from misaq.domain.generation import Clause, GenerationRecord
from misaq.domain.retrieval import Query
from misaq.experiments.fingerprint import config_sha256
from misaq.generation.backends.base import (
    BackendError,
    GenerationBackend,
    GenerationParams,
)
from misaq.generation.cache import ReplayCache
from misaq.generation.prompts import assemble_prompt, parse_structured, prompt_hashes
from misaq.verification.extract import extract_citations
from misaq.verification.registry import CorpusRegistry
from misaq.verification.verify import verify


class GenerationPipeline:
    def __init__(
        self, clauses: list[Clause], backend: GenerationBackend, params: GenerationParams,
        *, system: str = "all", registry: CorpusRegistry | None = None,
        retriever: Any = None, sections: dict[str, dict[str, str]] | None = None,
        cache: ReplayCache | None = None, run_dir: Path | None = None,
        requests_per_minute: int = 60,
    ):
        self.clauses, self.backend, self.params = clauses, backend, params
        self.systems = ["S1", "S2", "S3", "S4"] if system == "all" else [system]
        self.registry, self.retriever = registry, retriever
        self.sections, self.cache = sections or {}, cache
        self.run_dir = run_dir
        self.requests_per_minute = requests_per_minute

    def _context(self, clause: Clause, system: str) -> tuple[list[dict[str, str]], tuple[str, ...]]:
        ids: tuple[str, ...]
        if system == "S3" and self.retriever is not None:
            result = self.retriever.retrieve(Query(clause.clause_id, clause.text))
            ids = tuple(hit.section_id for hit in result.hits)
        elif system == "S4":
            ids = clause.oracle_section_ids
        else:
            ids = ()
        return [self.sections[item] for item in ids if item in self.sections], ids

    def _record(self, clause: Clause, system: str) -> GenerationRecord:
        if not clause.cloud_ok:
            return GenerationRecord(clause.clause_id, system, "error", error_type="PRIVACY",
                                    error="clause is not approved for cloud generation")
        context, ids = self._context(clause, system)
        prompt = assemble_prompt(system, clause, retrieved=context if system == "S3" else (),
                                 oracle=context if system == "S4" else ())
        params = GenerationParams(self.params.model, self.params.temperature, self.params.top_p,
                                  self.params.max_output_tokens, self.params.seed, system != "S1")
        started = time.perf_counter_ns()
        try:
            response = self.cache.get(prompt, params) if self.cache else None
            if response is None:
                response = self.backend.generate(prompt, params)
                if self.cache:
                    self.cache.put(prompt, params, response)
            raw = response.raw_text
            citations: list[dict[str, object]] = []
            if system == "S1":
                extracted = extract_citations(raw)
            else:
                parsed = parse_structured(raw)
                claims = parsed["claims"]
                if not isinstance(claims, list):
                    raise ValueError("claims must be a list")
                extracted = tuple(
                    citation for claim in claims for value in claim["citations"]
                    for citation in extract_citations(str(value))
                )
            checks = verify(tuple(
                Citation(c.item_id, c.raw_text, c.act, c.section, c.subsection, system, ids)
                for c in extracted
            ), self.registry) if self.registry is not None else ()
            citations = [check.__dict__ for check in checks]
            return GenerationRecord(clause.clause_id, system, "ok", raw, {
                **response.metadata, "latency_ms": (time.perf_counter_ns() - started) / 1_000_000,
            }, citations=tuple(citations), in_context=ids if system in {"S3", "S4"} else None,
                retrieved_section_ids=ids if system == "S3" else (),
                oracle_section_ids=ids if system == "S4" else ())
        except ValueError as error:
            return GenerationRecord(clause.clause_id, system, "error", locals().get("raw", ""),
                                    error_type="OUTPUT_PARSE", error=str(error),
                                    in_context=ids if system in {"S3", "S4"} else ())
        except (BackendError, RuntimeError) as error:
            return GenerationRecord(clause.clause_id, system, "error", error_type=type(error).__name__,
                                    error=str(error), in_context=ids if system in {"S3", "S4"} else ())

    def run(self, *, dry_run: bool = False, max_items: int | None = None) -> dict[str, object]:
        planned: list[tuple[str, GenerationParams]] = []
        for clause in self.clauses:
            if not clause.cloud_ok:
                continue
            for system in self.systems:
                context, _ = self._context(clause, system)
                prompt = assemble_prompt(
                    system, clause, retrieved=context if system == "S3" else (),
                    oracle=context if system == "S4" else (),
                )
                planned.append((prompt, GenerationParams(
                    self.params.model, self.params.temperature, self.params.top_p,
                    self.params.max_output_tokens, self.params.seed, system != "S1",
                )))
        if dry_run:
            hits = sum(self.cache.get(prompt, params) is not None for prompt, params in planned) if self.cache else 0
            misses = len(planned) - hits
            return {
                "planned_calls": misses, "cache_hits": hits,
                "minimum_minutes": misses / self.requests_per_minute,
            }
        if self.run_dir is None:
            raise ValueError("run_dir is required for a real run")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        items_path = self.run_dir / "items.jsonl"
        completed = {(str(row["clause_id"]), str(row["system"])) for row in
                     (json.loads(line) for line in items_path.read_text(encoding="utf-8").splitlines()
                      if line.strip())} if items_path.exists() else set()
        self._write_manifest()
        count = 0
        with items_path.open("a", encoding="utf-8") as handle:
            for clause in self.clauses:
                for system in self.systems:
                    if (clause.clause_id, system) in completed or (max_items is not None and count >= max_items):
                        continue
                    record = self._record(clause, system)
                    handle.write(json.dumps(record.__dict__, ensure_ascii=False, default=list) + "\n")
                    handle.flush()
                    count += 1
        return {"items": count, "systems": self.systems}

    def _write_manifest(self) -> None:
        assert self.run_dir is not None
        config = {"systems": self.systems, "model": self.params.to_dict(), "prompt_hashes": prompt_hashes(),
                  "verification_algorithm_version": "1", "protocol_decision_s4_empty": True}
        (self.run_dir / "manifest.json").write_text(json.dumps({
            "manifest_version": "1.0", "kind": "exp_c", "config_hash": config_sha256(config),
            "params": config, "status": "running",
        }, indent=2) + "\n", encoding="utf-8")
        (self.run_dir / "resolved_config.yaml").write_text(
            yaml.safe_dump(config, sort_keys=True), encoding="utf-8"
        )


def load_clauses(path: Path, split: str) -> list[Clause]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = []
    for row in rows:
        if row.get("split", split) != split:
            continue
        result.append(Clause(str(row["clause_id"]), str(row["text"]), bool(row.get("cloud_ok", False)),
                             str(row.get("source", "")), str(row.get("licence", "")),
                             tuple(str(item) for item in row.get("oracle_section_ids", ()))))
    return result
