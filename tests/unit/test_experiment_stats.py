from misaq.evaluation.stats import paired_bootstrap_difference, percentile_bootstrap_ci


def test_percentile_bootstrap_ci_is_deterministic_and_sane():
    values = [0.0, 0.5, 1.0, 0.5]

    first = percentile_bootstrap_ci(values, resamples=500, seed=7)
    second = percentile_bootstrap_ci(values, resamples=500, seed=7)

    assert first == second
    assert 0.0 <= first[0] <= first[1] <= 1.0
    mean = sum(values) / len(values)
    assert first[0] <= mean <= first[1]


def test_paired_bootstrap_difference_is_zero_for_identical_metrics():
    values = [0.2, 0.4, 0.8]

    result = paired_bootstrap_difference(values, values, resamples=300, seed=3)

    assert result["estimate"] == 0.0
    assert result["ci"] == (0.0, 0.0)
