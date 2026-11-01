import pytest

from misaq.evaluation.model_selection import ModelEvaluation, select_model

pytestmark = pytest.mark.unit


def _config(tolerance: float | None = 0.02, ram: int | None = 100) -> dict[str, object]:
    return {"selection": {"recall_at_5_tolerance": tolerance, "max_peak_ram_bytes": ram}}


def test_selects_smallest_candidate_within_tolerance():
    candidates = [
        ModelEvaluation("large", recall_at_5=0.90, peak_ram_bytes=50, parameter_count=100),
        ModelEvaluation("small", recall_at_5=0.89, peak_ram_bytes=50, parameter_count=10),
    ]

    assert select_model(candidates, _config()) == "small"


def test_tolerance_edge_is_inclusive():
    candidates = [
        ModelEvaluation("best", recall_at_5=0.90, peak_ram_bytes=50, parameter_count=100),
        ModelEvaluation("edge", recall_at_5=0.88, peak_ram_bytes=50, parameter_count=10),
    ]

    assert select_model(candidates, _config(tolerance=0.02)) == "edge"


def test_ram_budget_filters_candidate_before_size_comparison():
    candidates = [
        ModelEvaluation("small", recall_at_5=0.90, peak_ram_bytes=101, parameter_count=10),
        ModelEvaluation("large", recall_at_5=0.90, peak_ram_bytes=100, parameter_count=100),
    ]

    assert select_model(candidates, _config()) == "large"


def test_equal_parameter_count_uses_name_as_deterministic_tie_breaker():
    candidates = [
        ModelEvaluation("zeta", recall_at_5=0.90, peak_ram_bytes=50, parameter_count=10),
        ModelEvaluation("alpha", recall_at_5=0.90, peak_ram_bytes=50, parameter_count=10),
    ]

    assert select_model(candidates, _config()) == "alpha"


@pytest.mark.parametrize(
    "config",
    [
        _config(tolerance=None),
        _config(ram=None),
    ],
)
def test_null_selection_config_raises(config: dict[str, object]):
    candidate = ModelEvaluation("model", recall_at_5=0.90, peak_ram_bytes=50, parameter_count=10)

    with pytest.raises(ValueError, match="must be configured"):
        select_model([candidate], config)
