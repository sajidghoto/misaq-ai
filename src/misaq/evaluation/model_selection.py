"""Pure model selection from measured development results."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelEvaluation:
    """Measured development results and configured size metadata for one model."""

    name: str
    recall_at_5: float
    peak_ram_bytes: int
    parameter_count: int


def select_model(
    candidates: Sequence[ModelEvaluation],
    config: Mapping[str, object],
) -> str:
    """Return the smallest eligible model name under the configured selection rule."""
    selection = config.get("selection")
    if not isinstance(selection, Mapping):
        raise ValueError("selection configuration must be provided")

    tolerance = selection.get("recall_at_5_tolerance")
    max_peak_ram = selection.get("max_peak_ram_bytes")
    if tolerance is None or max_peak_ram is None:
        raise ValueError("selection tolerance and RAM budget must be configured")
    if not isinstance(tolerance, (int, float)) or tolerance < 0:
        raise ValueError("recall_at_5_tolerance must be a non-negative number")
    if not isinstance(max_peak_ram, int) or max_peak_ram < 0:
        raise ValueError("max_peak_ram_bytes must be a non-negative integer")
    if not candidates:
        raise ValueError("model candidates cannot be empty")

    best_recall = max(candidate.recall_at_5 for candidate in candidates)
    eligible = [
        candidate
        for candidate in candidates
        if candidate.recall_at_5 >= best_recall - float(tolerance)
        and candidate.peak_ram_bytes <= max_peak_ram
    ]
    if not eligible:
        raise ValueError("no model satisfies the recall tolerance and RAM budget")

    selected = min(eligible, key=lambda candidate: (candidate.parameter_count, candidate.name))
    return selected.name
