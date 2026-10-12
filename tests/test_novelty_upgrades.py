#!/usr/bin/env python3
"""
Unit & Integration Tests for Novelty Engineering Upgrades & Bug Fixes:
1. 2-RC Electro-Thermal-Acoustic ODE + Reversible Entropic Heat + Coulomb Counting
2. Online Forgetting-Factor RLS Impedance Observer + 16-Point EIS Nyquist Spectrum
3. Remaining Useful Life (RUL) & Knee-Point Trajectory Forecaster
4. Closed-Loop Active Rebalancing Feedback & State Machine Transition (No Infinite Loop)
5. FFT Hilbert Transform Analytic A-Scan Envelope & Instantaneous Phase
6. Token-Level Cross-Modal Transformer Attention (L=32), Gradient Saliency, & PINN Physics Residual
7. FastAPI Endpoints (/api/rebalance/trigger, /api/system/reset, /api/evidence/*)
"""

import os
import sys
import asyncio
import numpy as np
import torch
import pytest
from fastapi.testclient import TestClient

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.battery_physics import DynamicBatteryPhysicsEngine, OnlineRLSImpedanceObserver
from backend.ascan_synthesizer import compute_hilbert_analytic_envelope, synthesize_rf_ascan_waveform
from backend.ml_processor import MLProcessor
from backend.rebalancing import RebalancingProcessor
from backend.main import app
from ml_pipeline.models.multibranch_fusion_net import MultiBranchFusionNet, extract_feature_importance
from active_rebalancing.decision_engine.state_machine import DecisionEngine, SystemState, DegradationMode


def test_online_rls_observer_and_eis_nyquist_spectrum():
    """Verify OnlineRLSImpedanceObserver tracks R0/R1/C1/R2/C2 and generates 16-point EIS Nyquist spectra."""
    obs = OnlineRLSImpedanceObserver(r0_init=0.045, r1_init=0.025, c1_init=1800.0)
    res = obs.update(
        v_terminal=3.54,
        ocv=3.60,
        current_a=1.0,
        r0_true_hint=0.058,
        r1_true_hint=0.032,
        c1_true_hint=1500.0,
        dt=0.1
    )
    assert "ecm_r0_est" in res
    assert "ecm_r1_est" in res
    assert "ecm_c1_est" in res
    assert "ecm_r2_est" in res
    assert "ecm_c2_est" in res
    assert "eis_spectrum" in res

    eis = res["eis_spectrum"]
    assert len(eis["frequencies_hz"]) == 16
    assert len(eis["z_real_ohm"]) == 16
    assert len(eis["z_imag_ohm"]) == 16
    # Low-frequency real impedance (index 0, 0.01 Hz) exceeds high-frequency real impedance (index -1, 10 kHz)
    assert eis["z_real_ohm"][0] > eis["z_real_ohm"][-1]


def test_2rc_ode_coulomb_counting_rul_and_closed_loop_feedback():
    """Verify 2-RC ODE, Coulomb counting, RUL forecasting, and closed-loop active rebalancing recovery."""
    engine = DynamicBatteryPhysicsEngine(chemistry='nmc_811', form_factor='18650_cylindrical')
    engine.set_parameters(soc=0.70, degradation_mode='li_plating', load_current_c=1.0, noise_level=0.0)

    f1 = engine.step(dt=1.0)
    # Discharging at 1C reduces SOC via Coulomb counting and builds polarization voltage V_rc1, V_rc2
    assert f1["simulation_soc"] < 0.70
    assert f1["ecm_v_rc1"] > 0.0
    assert f1["ecm_v_rc2"] > 0.0
    assert f1["rul_remaining_cycles"] > 0
    assert f1["rul_knee_point_cycles"] > 0
    assert len(f1["pack_cells"]) == 4

    # Apply closed-loop PULSE_DEPLATING feedback and verify SOH recovery & R0 reduction
    r0_before = engine.r0
    engine.apply_rebalancing_feedback("PULSE_DEPLATING", actual_current_a=1.5, dt=1.0)
    assert engine.rebalancing_recovery_soh_bonus > 0.0
    assert engine.r0 < r0_before


def test_hilbert_analytic_envelope_and_phase():
    """Verify FFT Hilbert transform computes accurate analytic envelope and instantaneous phase."""
    t = np.linspace(0, 10e-6, 512)
    env_true = np.exp(-((t - 5e-6) / 1.2e-6) ** 2)
    carrier = np.cos(2.0 * np.pi * 5e6 * t)
    rf = env_true * carrier

    env_est, phase_est = compute_hilbert_analytic_envelope(rf)
    assert env_est.shape == rf.shape
    assert phase_est.shape == rf.shape
    # Peak of Hilbert envelope matches Gaussian envelope peak within 2%
    assert abs(np.max(env_est) - 1.0) < 0.02

    ascan = synthesize_rf_ascan_waveform(tof_us=8.0, sos=2500.0, degradation_mode="li_plating")
    assert "instantaneous_phase_rad" in ascan
    assert len(ascan["instantaneous_phase_rad"]) == len(ascan["rf_signal"])


def test_token_level_cross_modal_attention_and_gradient_saliency():
    """Verify MultiBranchFusionNet L=32 token-level attention and input-gradient saliency."""
    model = MultiBranchFusionNet(seq_length=256, num_degradation_classes=6, fusion_type='enhanced_attention')
    model.eval()

    e = torch.randn(2, 1, 256)
    u = torch.randn(2, 1, 256)
    t = torch.randn(2, 1, 256)

    out = model(e, u, t)
    assert out["degradation_logits"].shape == (2, 6)
    assert out["soh_mean"].shape == (2, 1)
    assert out["modality_weights"].shape == (2, 3)

    importance = extract_feature_importance(model, e, u, t)
    assert set(importance.keys()) == {"electrical", "ultrasonic", "thermal"}
    assert abs(sum(importance.values()) - 1.0) < 1e-4


def test_pinn_residual_and_rul_in_ml_processor():
    """Verify MLProcessor computes PINN physics consistency residual and RUL trajectory."""
    async def _run():
        proc = MLProcessor(sequence_length=256)
        await proc.initialize()
        raw_frame = {
            "source": "3d",
            "cellId": "CELL_TEST",
            "electrical_voltage": 3.58,
            "electrical_current": 0.50,
            "electrical_resistance": 0.045,
            "ultrasonic_timeOfFlight": 8.0,
            "ultrasonic_amplitude": 0.95,
            "ultrasonic_phaseShift": 0.0,
            "ultrasonic_speedOfSound": 2500.0,
            "thermal_temperature": 25.4,
            "thermal_tempGradient": 0.05,
            "simulation_soc": 0.50,
        }
        processed = await proc.process_frame(raw_frame)
        assert "pinn_physics_residual" in processed
        assert 0.0 <= processed["pinn_physics_residual"] <= 1.0
        assert "rul_remaining_cycles" in processed
        assert "rul_knee_point_cycles" in processed

    asyncio.run(_run())


def test_rebalancing_state_machine_completes_without_infinite_loop():
    """Verify DecisionEngine transitions ANALYZING -> REBALANCING -> VERIFYING without resetting timer."""
    import time
    de = DecisionEngine()
    de.active_recovery_window_s = 0.05
    de.update_ml_results(DegradationMode.LI_PLATING.value, 0.92, 86.0)
    de.transition_to(SystemState.ANALYZING)

    # 1. ANALYZING -> REBALANCING
    de.execute()
    assert de.state == SystemState.REBALANCING

    # 2. First execute() in REBALANCING sets recovery_start_time
    de.execute()
    assert de.recovery_start_time is not None

    # 3. Wait for active_recovery_window_s and verify transition to VERIFYING (no infinite timer reset!)
    time.sleep(0.06)
    de.execute()
    assert de.state == SystemState.VERIFYING


def test_new_fastapi_endpoints():
    """Verify /api/rebalance/trigger, /api/system/reset, and /api/evidence/* endpoints."""
    client = TestClient(app)

    res_trig = client.post("/api/rebalance/trigger", json={"action": "equilibration"})
    assert res_trig.status_code == 200
    assert res_trig.json()["status"] == "triggered"

    res_ev = client.get("/api/evidence/summary")
    assert res_ev.status_code == 200
    assert "is_recording" in res_ev.json()

    res_rst = client.post("/api/system/reset")
    assert res_rst.status_code == 200
    assert res_rst.json()["status"] == "reset"
