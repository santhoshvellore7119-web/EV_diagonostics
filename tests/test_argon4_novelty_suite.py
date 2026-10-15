"""
Unit & Integration Tests for Argon-4 Generated Frontier Modules:
1. Ultrasonic 2D Acoustic Wavefield Tomography & SAFT Beamforming
2. Dual-Unscented Kalman Filter (Dual-UKF) Multi-Rate Joint Estimator
3. Physics-Informed Neural Network (PINN) Electro-Thermal PDE Solver
4. Copilot & Research REST API Endpoints
"""

import pytest
import numpy as np
import torch
from fastapi.testclient import TestClient

from backend.acoustic_tomography_reconstruction import (
    UltrasonicCellConfig,
    AcousticForwardSimulator,
    AcousticTomographyReconstructor,
    get_cached_tomography_heatmap
)
from backend.dual_ukf_joint_estimator import (
    OCVPolynomialModel,
    MerweSigmaWeights,
    DualUKFJointEstimator,
    ensure_spd_and_cholesky
)
from backend.pinn_thermal_electrochemical import (
    CellParameters,
    ElectroThermalPINN,
    PINNLoss,
    WLTPBatchGenerator,
    get_cached_pinn_evaluation
)
from backend.main import app


@pytest.fixture
def api_client():
    return TestClient(app)


# ==============================================================================
# 1. Ultrasonic 2D Tomography & SAFT Tests
# ==============================================================================

def test_acoustic_tomography_phantom_and_forward():
    cfg = UltrasonicCellConfig(grid_size=32, n_samples=300)
    sim = AcousticForwardSimulator(cfg, seed=123)
    phantom = sim.generate_degradation_phantom()

    assert "c_true" in phantom
    assert "reflectivity_true" in phantom
    assert phantom["c_true"].shape == (32, 32)
    # Check that lithium plating stiffens velocity above baseline c0
    assert np.max(phantom["c_true"]) > cfg.c0
    # Check that gas pocket reduces velocity below baseline c0
    assert np.min(phantom["c_true"]) < cfg.c0

    fwd = sim.simulate_pitch_catch_rf(phantom)
    assert fwd["rf_data"].shape == (8, 8, 300)
    assert fwd["tof_measured"].shape == (8, 8)


def test_acoustic_tomography_saft_and_tikhonov():
    cfg = UltrasonicCellConfig(grid_size=32, n_samples=300)
    sim = AcousticForwardSimulator(cfg, seed=42)
    phantom = sim.generate_degradation_phantom()
    fwd = sim.simulate_pitch_catch_rf(phantom)

    recon = AcousticTomographyReconstructor(cfg, sim.tx_coords)
    saft_img = recon.reconstruct_saft_das(fwd["rf_data"], fwd["tof_baseline"])
    assert saft_img.shape == (32, 32)
    assert np.max(saft_img) <= 1.0 + 1e-6

    vel_recon = recon.reconstruct_velocity_art_tikhonov(
        fwd["L_csr"], fwd["tof_measured"], fwd["tof_baseline"],
        fwd["pairs"], fwd["rf_data"], saft_img, sart_iterations=5
    )
    assert "c_reconstructed" in vel_recon
    assert vel_recon["c_reconstructed"].shape == (32, 32)


# ==============================================================================
# 2. Dual-UKF Joint Estimator Tests
# ==============================================================================

def test_dual_ukf_ocv_and_cholesky():
    # 6th-order polynomial evaluation
    soc_vals = np.array([0.2, 0.5, 0.8])
    ocv_vals = OCVPolynomialModel.ocv(soc_vals)
    assert np.all(ocv_vals > 3.0) and np.all(ocv_vals < 4.4)

    # Cholesky & SPD preservation
    P = np.array([[1.0, 0.5], [0.5, 2.0]])
    P_spd, S = ensure_spd_and_cholesky(P)
    assert np.allclose(P_spd, S @ S.T, atol=1e-8)


def test_dual_ukf_step_convergence():
    estimator = DualUKFJointEstimator(
        q_nom_ah=5.0,
        dt_state=0.1,
        dt_param=0.5,  # Trigger param step every 5 steps
        x0=np.array([0.60, 0.0, 0.0]),
        theta0=np.array([0.030, 0.015, 1000.0, 0.020, 15000.0])
    )

    # Step through 10 iterations under discharge
    for _ in range(10):
        out = estimator.step(i_prev=1.5, i_now=1.5, v_meas=3.62)

    assert 0.0 <= out["soc_est"] <= 1.0
    assert out["r0_mohm"] > 5.0
    assert out["v_est"] > 3.0


# ==============================================================================
# 3. Physics-Informed Neural Network (PINN) Tests
# ==============================================================================

def test_pinn_architecture_forward_pass():
    params = CellParameters()
    model = ElectroThermalPINN(params, t_max=600.0, hidden_dim=32, num_layers=3)

    r = torch.rand(16, 1) * params.radius
    z = torch.rand(16, 1) * params.height
    t = torch.rand(16, 1) * 600.0
    i = torch.full((16, 1), 2.0)
    t_amb = torch.full((16, 1), 298.15)

    t_pred, eta_pred = model(r, z, t, i, t_amb)
    assert t_pred.shape == (16, 1)
    assert eta_pred.shape == (16, 1)
    assert torch.all(t_pred > 270.0) and torch.all(t_pred < 360.0)


def test_pinn_loss_and_derivatives():
    params = CellParameters()
    gen = WLTPBatchGenerator(params, t_max=100.0, dt=2.0)
    model = ElectroThermalPINN(params, t_max=100.0, hidden_dim=32, num_layers=3)
    criterion = PINNLoss(params, lambda_pde=1.0, lambda_bc=1.0, lambda_data=1.0)

    batch = gen.sample_training_batch(n_pde=32, n_bc=16, n_ic=16, n_data=32)
    loss, metrics = criterion(model, batch)

    assert loss.item() > 0.0
    assert "mse_pde" in metrics
    assert "mse_bc" in metrics
    assert "mse_data" in metrics


# ==============================================================================
# 4. REST API Integration Endpoints
# ==============================================================================

def test_tomography_heatmap_endpoint(api_client):
    res = api_client.get("/api/research/tomography_heatmap")
    assert res.status_code == 200
    data = res.json()
    assert "metadata" in data
    assert "heatmaps" in data
    assert len(data["transducer_ring"]) == 8


def test_dual_ukf_telemetry_endpoint(api_client):
    res = api_client.get("/api/research/dual_ukf_telemetry")
    assert res.status_code == 200
    data = res.json()
    assert "soc_pct" in data
    assert "r0_mohm" in data
    assert "v_terminal_estimated_v" in data


def test_pinn_temperature_field_endpoint(api_client):
    res = api_client.get("/api/research/pinn_temperature_field")
    assert res.status_code == 200
    data = res.json()
    assert "temperature_contour_c" in data
    assert "t_core_max_c" in data
    assert data["t_core_max_c"] > 20.0


def test_copilot_chat_endpoint(api_client):
    res = api_client.post("/api/copilot/chat", json={"message": "How does acoustic CWI work?"})
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert len(data["reply"]) > 20
