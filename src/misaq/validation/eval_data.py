"""Validation for human-authored retrieval evaluation JSONL."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from misaq.domain.enums import SectionStatus
from misaq.domain.errors import DataValidationError
from misaq.domain.statute import Act


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def validate_eval_jsonl(path: Path, acts: Iterable[Act]) -> int:
    """Validate rows and return their count; every failure names its exact reason."""
    sections = {section.id: section for act in acts for section in act.sections}
    rows: list[dict[str, object]] = []
    failures: list[str] = []
    seen_ids: set[str] = set()
    seen_text: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                failures.append(f"line {line_number}: invalid JSON: {error.msg}")
                continue
            if not isinstance(row, dict):
                failures.append(f"line {line_number}: row must be an object")
                continue
            rows.append(row)
            query_id = row.get("id")
            query = row.get("query")
            gold = row.get("gold")
            split = row.get("split")
            if not isinstance(query_id, str) or not query_id:
                failures.append(f"line {line_number}: query id must be non-empty")
            elif query_id in seen_ids:
                failures.append(f"line {line_number}: duplicate query id {query_id!r}")
            else:
                seen_ids.add(query_id)
            if not isinstance(query, str) or not query.strip():
                failures.append(f"line {line_number}: non-empty query text required")
            else:
                normalized = _normalized_text(query)
                previous = seen_text.get(normalized)
                current_split = str(split)
                if previous in {"dev", "test"} and current_split in {"dev", "test"} and previous != current_split:
                    failures.append(f"line {line_number}: normalized query text overlaps splits")
                seen_text[normalized] = current_split
            if not isinstance(split, str) or not split:
                failures.append(f"line {line_number}: split field required")
            if not isinstance(gold, list) or not gold:
                failures.append(f"line {line_number}: non-empty gold list required")
            elif len(set(gold)) != len(gold) or not all(isinstance(item, str) for item in gold):
                failures.append(f"line {line_number}: gold list must contain unique section ids")
            else:
                for section_id in gold:
                    section = sections.get(section_id)
                    if section is None:
                        failures.append(f"line {line_number}: gold section id does not exist: {section_id}")
                    elif section.status is not SectionStatus.IN_FORCE:
                        failures.append(f"line {line_number}: gold section is not in_force: {section_id}")
    if failures:
        raise DataValidationError("eval data validation failed", failures=failures)
    return len(rows)
