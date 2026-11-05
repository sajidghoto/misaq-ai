"""Public, memory-only contract ingestion API."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from misaq.domain.generation import Clause, ContractMeta
from misaq.ingestion.readers import normalise, read_bytes
from misaq.ingestion.structure import build_structure, load_structure_config
from misaq.ingestion.units import select_units


@dataclass(frozen=True)
class IngestionReport:
    format: str
    paragraph_count: int
    clause_count: int
    numbering_scheme: str | None
    confidence_summary: dict[str, float]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format, "paragraph_count": self.paragraph_count,
            "clause_count": self.clause_count, "numbering_scheme": self.numbering_scheme,
            "confidence_summary": dict(self.confidence_summary), "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class IngestionResult:
    contract: ContractMeta
    clauses: tuple[Clause, ...]
    report: IngestionReport


@dataclass(frozen=True)
class IngestionConfig:
    max_unit_tokens: int = 400
    tiny_unit_tokens: int = 40
    structure_path: Path | None = None


def _config(value: Any) -> IngestionConfig:
    if isinstance(value, IngestionConfig):
        return value
    if value is None:
        path = Path(__file__).resolve().parents[3] / "configs" / "ingestion.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    elif isinstance(value, (str, Path)):
        data = yaml.safe_load(Path(value).read_text(encoding="utf-8"))
    elif isinstance(value, dict):
        data = value
    else:
        raise TypeError("config must be an IngestionConfig, path, mapping, or None")
    units = data.get("analysis_units", {})
    return IngestionConfig(int(units.get("max_unit_tokens", 400)),
                           int(units.get("tiny_unit_tokens", 40)))


def _tokenizer(config: Any):
    candidate = config.get("tokenizer") if isinstance(config, dict) else None
    if candidate is None:
        return None
    if callable(candidate):
        return candidate
    if hasattr(candidate, "encode"):
        return lambda text: candidate.encode(text)
    raise TypeError("config tokenizer must be callable or provide encode")


def ingest_bytes(data: bytes, filename: str, config: Any = None) -> IngestionResult:
    settings = _config(config)
    paragraphs, reader_warnings = read_bytes(data, filename)
    paragraphs = normalise(paragraphs)
    structure = build_structure(paragraphs, load_structure_config(settings.structure_path))
    tokenizer = _tokenizer(config)
    units = select_units(structure, paragraphs, settings.max_unit_tokens,
                         settings.tiny_unit_tokens, tokenizer)
    parent_ids = {unit.path: unit.unit_id for unit in units}
    clauses = tuple(
        Clause(
            unit.unit_id, unit.text, False, filename, "",
            contract=ContractMeta(contract_id=filename, source=filename),
            heading=unit.heading, label=unit.label, path=unit.path,
            parent_clause_id=parent_ids.get(unit.parent_path) if unit.parent_path else None,
            source_pages=unit.source_pages, kind=unit.kind,
            confidence=unit.confidence, warnings=unit.warnings,
        )
        for unit in units
    )
    warnings = tuple(dict.fromkeys((*reader_warnings, *structure.warnings,
                                    *(warning for unit in units for warning in unit.warnings))))
    confidences = [unit.confidence for unit in units]
    scheme = next((node.scheme for node in structure.children if node.scheme), None)
    report = IngestionReport(
        filename.lower().rsplit(".", 1)[-1], len(paragraphs), len(clauses), scheme,
        {"min": min(confidences, default=0.0), "mean": sum(confidences) / len(confidences)
         if confidences else 0.0, "max": max(confidences, default=0.0)}, warnings,
    )
    return IngestionResult(ContractMeta(contract_id=filename, source=filename), clauses, report)


def ingest_path(path: Path | str, config: Any = None) -> IngestionResult:
    source = Path(path)
    return ingest_bytes(source.read_bytes(), source.name, config)


__all__ = ["IngestionConfig", "IngestionReport", "IngestionResult", "ingest_bytes", "ingest_path"]
