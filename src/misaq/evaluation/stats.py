"""Deterministic query-level bootstrap statistics."""
from __future__ import annotations

import random
from collections.abc import Sequence


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("bootstrap values cannot be empty")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def percentile_bootstrap_ci(
    values: Sequence[float],
    *,
    resamples: int = 10_000,
    seed: int = 0,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Return a percentile CI for the mean, resampling queries with replacement."""
    if not values:
        raise ValueError("values cannot be empty")
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    rng = random.Random(seed)
    count = len(values)
    means = [sum(values[rng.randrange(count)] for _ in range(count)) / count for _ in range(resamples)]
    tail = (1.0 - confidence) / 2.0
    return _percentile(means, tail), _percentile(means, 1.0 - tail)


def paired_bootstrap_difference(
    first: Sequence[float],
    second: Sequence[float],
    *,
    resamples: int = 10_000,
    seed: int = 0,
    confidence: float = 0.95,
) -> dict[str, float | tuple[float, float]]:
    """Return the paired mean difference and its query-level percentile CI."""
    if len(first) != len(second) or not first:
        raise ValueError("paired values must be non-empty and have equal length")
    differences = [left - right for left, right in zip(first, second, strict=True)]
    estimate = sum(differences) / len(differences)
    return {
        "estimate": estimate,
        "ci": percentile_bootstrap_ci(
            differences, resamples=resamples, seed=seed, confidence=confidence
        ),
    }


def bootstrap_metric_cis(
    metrics: Sequence[dict[str, float]],
    *,
    resamples: int = 10_000,
    seed: int = 0,
    confidence: float = 0.95,
) -> dict[str, tuple[float, float]]:
    """Calculate independent CIs for each metric using the same query unit."""
    if not metrics:
        return {}
    names = sorted({name for row in metrics for name in row})
    return {
        name: percentile_bootstrap_ci(
            [row[name] for row in metrics if name in row],
            resamples=resamples,
            seed=seed,
            confidence=confidence,
        )
        for name in names
    }
