from __future__ import annotations

from eval.drift_power_csm import (
    achieved_power,
    build_drift_power_report,
    minimum_detectable_drop,
    one_sided_two_proportion_p_value,
    required_n_per_arm,
)


def test_one_sided_two_proportion_detects_large_drop():
    assert one_sided_two_proportion_p_value(7, 7, 0, 7) < 0.01
    assert one_sided_two_proportion_p_value(7, 7, 7, 7) == 1.0


def test_power_helpers_are_monotone_enough_for_claim_scope():
    small_drop_n = required_n_per_arm(1.0, 0.9)
    large_drop_n = required_n_per_arm(1.0, 0.5)

    assert small_drop_n is not None
    assert large_drop_n is not None
    assert small_drop_n > large_drop_n
    assert achieved_power(1.0, 0.0, 7, 7) == 1.0
    assert minimum_detectable_drop(1.0, 7, 7) > 0.4


def test_drift_power_report_scopes_current_gold_power():
    report = build_drift_power_report()

    assert report["hard_ok"] is True
    assert report["baseline"]["variant"] == "control_good"
    assert report["baseline"]["overall"]["pass_count"] == 7
    assert report["power"]["current_independent_examples_per_arm"] == 7
    assert report["power"]["minimum_detectable_drop_at_current_n"] > 0.4
    assert report["expanded_hard_layer_power"]["n"] == 64
    assert (
        report["expanded_hard_layer_power"]["power"]["minimum_detectable_drop_at_current_n"]
        < report["power"]["minimum_detectable_drop_at_current_n"]
    )
    assert report["specificity"]["false_alarms"] == []
    assert "noop_equivalent" in report["specificity"]["negative_controls"]
    assert report["claim_boundary"]["overall_power_only"] is True
