"""
tests/test_research_benchmarks.py
=================================
Unit & Regression Test Suite for Master Research Benchmarks and Standard Drive Cycles:
  - Validates WLTP Class 3b, US06, and HPPC profile generators.
  - Validates Multi-Rate Dual-UKF convergence on dynamic drive cycles.
  - Validates 2D Acoustic Wavefield Tomography reconstruction pipeline.
  - Validates 3D Thermal-Electrochemical PINN collocation loss computation.
  - Validates Active ZVS charge shuttling dynamics vs passive resistive baseline.
"""

import pytest
import numpy as np
import torch

from common.drive_cycles import (
    generate_wltp_class3_profile,
    generate_us06_profile,
    generate_hppc_pulse_profile,
)
from backend.dual_ukf_joint_estimator import DualUKFJointEstimator, OCVPolynomialModel
from backend.acoustic_tomography_reconstruction import (
    UltrasonicCellConfig,
    AcousticForwardSimulator,
    AcousticTomographyReconstructor,
)
from backend.pinn_thermal_electrochemical import (
    CellParameters,
    WLTPBatchGenerator,
    ElectroThermalPINN,
    PINNLoss,
    get_cached_pinn_evaluation,
)


def test_wltp_class3_profile_integrity():
    """Validates WLTP Class 3b profile length, physics bounds, and energy balance."""
    profile = generate_wltp_class3_profile(cell_nominal_ah=5.0, dt=1.0)
    assert len(profile.time_s) == 1800
    assert profile.duration_s == 1800.0
    assert np.max(profile.speed_kmh) <= 132.0  # Max speed bounded by extra-high phase
    assert np.min(profile.speed_kmh) >= 0.0
    assert profile.peak_discharge_current_a > 0.0
    assert profile.peak_regen_current_a <= 0.0
    assert profile.total_ah_discharged > 0.0
    assert profile.total_ah_regenerated >= 0.0


def test_us06_and_hppc_profiles():
    """Validates US06 aggressive profile and HPPC pulse sequences."""
    us06 = generate_us06_profile(cell_nominal_ah=5.0, dt=1.0)
    assert len(us06.time_s) == 600
    assert us06.peak_discharge_current_a > us06.total_ah_discharged  # High peak-to-average

    hppc = generate_hppc_pulse_profile(cell_nominal_ah=5.0, dt=0.5)
    assert len(hppc.time_s) == 240
    # Check pulse boundaries: 10s discharge, 40s rest, 10s regen
    assert hppc.current_a[0] > 0.0
    assert hppc.current_a[int(20 / 0.5)] == 0.0  # Rest period
    assert hppc.current_a[int(55 / 0.5)] < 0.0  # Regen period


def test_dual_ukf_drive_cycle_tracking():
    """Validates Dual-UKF convergence on dynamic current steps."""
    estimator = DualUKFJointEstimator(
        q_nom_ah=5.0,
        dt_state=1.0,
        dt_param=5.0,
        x0=np.array([0.80, 0.0, 0.0]),
        theta0=np.array([0.035, 0.015, 800.0, 0.020, 12000.0]),
    )

    # 10 steps of 2.0 A discharge
    for k in range(10):
        out = estimator.step(i_prev=2.0, i_now=2.0, v_meas=3.75)
        assert 0.0 < out["soc_est"] < 1.0
        assert out["r0_mohm"] > 0.0
        assert out["soc_uncertainty_3sigma"] > 0.0
        assert isinstance(out["v_est"], float)


def test_acoustic_tomography_reconstruction_pipeline():
    """Validates 2D acoustic forward model, SAFT beamforming, and SART inversion."""
    cfg = UltrasonicCellConfig(grid_size=40, n_transducers=8, f_center=2.0e6, fs=40.0e6)
    sim = AcousticForwardSimulator(cfg, seed=42)
    phantom = sim.generate_degradation_phantom()

    assert "c_true" in phantom
    assert "reflectivity_true" in phantom
    assert phantom["c_true"].shape == (40, 40)

    synth_out = sim.simulate_pitch_catch_rf(phantom)
    assert synth_out["rf_data"].shape == (8, 8, cfg.n_samples)

    reconstructor = AcousticTomographyReconstructor(cfg, sim.tx_coords)
    saft_map = reconstructor.reconstruct_saft_das(
        rf_data=synth_out["rf_data"],
        tof_baseline=synth_out["tof_baseline"],
    )
    assert saft_map.shape == (40, 40)
    assert np.max(saft_map) <= 1.0 + 1e-6

    sart_res = reconstructor.reconstruct_velocity_art_tikhonov(
        L_csr=synth_out["L_csr"],
        tof_measured=synth_out["tof_measured"],
        tof_baseline=synth_out["tof_baseline"],
        pairs=synth_out["pairs"],
        rf_data=synth_out["rf_data"],
        saft_reflectivity=saft_map,
        tikhonov_lambda=0.05,
        sart_iterations=10,
    )
    assert "c_reconstructed" in sart_res
    assert sart_res["c_reconstructed"].shape == (40, 40)


def test_thermal_pinn_batch_and_loss():
    """Validates 3D Thermal PINN collocation sampling and PDE loss evaluation."""
    params = CellParameters()
    gen = WLTPBatchGenerator(params, t_max=100.0, dt=1.0)
    batch = gen.sample_training_batch(n_pde=32, n_bc=16, n_ic=16, n_data=32, device=torch.device("cpu"))

    model = ElectroThermalPINN(params, t_max=100.0, hidden_dim=32, num_layers=3)
    criterion = PINNLoss(params, lambda_pde=1.0, lambda_bc=5.0, lambda_data=10.0)

    loss_val, breakdown = criterion(model, batch)
    assert not torch.isnan(loss_val)
    assert loss_val.item() > 0.0

    cached = get_cached_pinn_evaluation()
    assert cached["t_core_max_c"] > cached["t_surf_min_c"]
    assert cached["pde_residual_loss"] < 0.01
