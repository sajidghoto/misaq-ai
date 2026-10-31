"""Pure section-level retrieval metrics."""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence


def _validate_k(k: int) -> None:
    if k <= 0:
        raise ValueError("k must be positive")


def _unique_prefix(retrieved: Iterable[str], k: int) -> list[str]:
    _validate_k(k)
    result: list[str] = []
    seen: set[str] = set()
    for section_id in retrieved:
        if section_id not in seen:
            seen.add(section_id)
            result.append(section_id)
        if len(result) == k:
            break
    return result


def _require_gold(gold: set[str]) -> None:
    if not gold:
        raise ValueError("gold set cannot be empty")


def precision_at_k(retrieved: Iterable[str], gold: set[str], k: int) -> float:
    """Return unique relevant sections in the first k unique results divided by k."""
    _require_gold(gold)
    return len(set(_unique_prefix(retrieved, k)) & gold) / k


def recall_at_k(retrieved: Iterable[str], gold: set[str], k: int) -> float:
    """Return unique relevant sections in the first k unique results divided by gold size."""
    _require_gold(gold)
    return len(set(_unique_prefix(retrieved, k)) & gold) / len(gold)


def mean_reciprocal_rank(retrieved: Iterable[str], gold: set[str]) -> float:
    """Return reciprocal rank of the first unique relevant result, or zero if absent."""
    _require_gold(gold)
    for rank, section_id in enumerate(_unique_prefix(retrieved, 2**31 - 1), 1):
        if section_id in gold:
            return 1.0 / rank
    return 0.0


def metrics_at_k(
    retrieved: Iterable[str], gold: set[str], ks: Sequence[int] = (1, 3, 5, 10)
) -> Mapping[int, Mapping[str, float]]:
    """Return precision and recall for each configured k."""
    _require_gold(gold)
    values = list(retrieved)
    return {k: {"precision": precision_at_k(values, gold, k), "recall": recall_at_k(values, gold, k)} for k in ks}


mrr = mean_reciprocal_rank
