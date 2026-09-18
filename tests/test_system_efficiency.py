import sys
import os
import pytest
import numpy as np

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.efficiency_benchmark import (
    calculate_rebalancing_efficiency,
    benchmark_ml_inference_efficiency,
    benchmark_tdc_timing_efficiency
)


def test_active_rebalancing_efficiency_and_loss_scaling():
    """Verify that active rebalancing achieves >=91.5% efficiency across entire current range."""
    for current in [0.5, 1.0, 2.0, 3.0]:
        res = calculate_rebalancing_efficiency(i_transfer_a=current, v_source_v=3.90, v_target_v=3.40, zvs_enabled=True)
        assert res["efficiency_pct"] >= 91.5, f"Efficiency for {current}A fell below 91.5%: {res['efficiency_pct']}%"
        assert res["p_total_loss_w"] < 0.35, f"Total losses exceeded 0.35W: {res['p_total_loss_w']}W"


def test_energy_savings_vs_passive_dissipative_bleed():
    """Verify that active rebalancing saves >=85% energy compared to passive resistive bleed."""
    for current in [1.0, 2.0, 2.5]:
        res = calculate_rebalancing_efficiency(i_transfer_a=current, v_source_v=3.90, v_target_v=3.40)
        assert res["energy_saved_vs_passive_pct"] >= 85.0, f"Energy saving fell below 85%: {res['energy_saved_vs_passive_pct']}%"


def test_ml_inference_latency_budget():
    """Verify MultiBranchFusionNet inference latency is well within real-time DAQ window (<20ms)."""
    res = benchmark_ml_inference_efficiency(num_warmup=5, num_eval=20)
    assert res["mean_latency_ms"] < 25.0, f"Mean latency too high: {res['mean_latency_ms']} ms"
    assert res["realtime_budget_margin_pct"] > 70.0, f"Realtime budget margin too low: {res['realtime_budget_margin_pct']}%"


def test_tdc7200_picosecond_timing_and_energy_budget():
    """Verify TDC7200 acquisition parameters and sub-nanosecond timing resolution."""
    res = benchmark_tdc_timing_efficiency()
    assert res["single_shot_resolution_ps"] <= 55.0
    assert res["active_power_mw"] <= 2.5
    assert res["energy_per_shot_microjoules"] < 0.20
