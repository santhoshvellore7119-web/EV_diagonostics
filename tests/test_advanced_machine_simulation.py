import sys
import os
import pytest
import numpy as np

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.physics_constants import CELL_FORM_FACTORS, MACHINE_CYCLE_STAGES, ACOUSTIC_LAYER_IMPEDANCES
from backend.ascan_synthesizer import synthesize_rf_ascan_waveform, compute_layer_reflection_coefficient
from backend.machine_cycle import MachineCycleController
from fastapi.testclient import TestClient
from backend.main import app


def test_cell_form_factors_physics_constants():
    """Verify all 4 industrial cell form factors are properly specified with physical dimensions and acoustics."""
    expected_formats = ["18650_cylindrical", "21700_cylindrical", "prismatic_100ah", "pouch_60ah"]
    for fmt_key in expected_formats:
        assert fmt_key in CELL_FORM_FACTORS, f"Missing form factor {fmt_key}"
        cfg = CELL_FORM_FACTORS[fmt_key]
        assert cfg["nominal_capacity_ah"] > 0
        assert cfg["path_length_m"] > 0
        assert "clamping_force_n" in cfg
        assert cfg["clamping_force_n"] > 0


def test_ascan_synthesizer_waveform_generation():
    """Verify RF A-Scan synthesis produces correct time domain waveform and envelope."""
    ascan = synthesize_rf_ascan_waveform(
        tof_us=8.2,
        sos=2480.0,
        degradation_mode="healthy",
        attenuation=0.98,
        cell_format="prismatic_100ah"
    )
    assert "time_us" in ascan
    assert "rf_signal" in ascan
    assert "envelope" in ascan
    assert "front_wall_us" in ascan
    assert "back_wall_us" in ascan
    assert "defect_info" in ascan

    time_us = np.array(ascan["time_us"])
    rf = np.array(ascan["rf_signal"])
    env = np.array(ascan["envelope"])

    assert len(time_us) == len(rf) == len(env)
    assert np.max(env) > 0.4  # Strong front wall echo
    assert ascan["tof_us"] > 0


def test_ascan_defect_signatures():
    """Verify defect-specific acoustic reflections (Li plating, Gas delamination, Internal Short)."""
    # 1. Healthy: minimal defect echo
    ascan_healthy = synthesize_rf_ascan_waveform(cell_format="21700_cylindrical", degradation_mode="healthy")
    assert ascan_healthy["defect_info"]["has_defect_echo"] is False

    # 2. Gas delamination: massive acoustic impedance mismatch causing huge reflection
    ascan_gas = synthesize_rf_ascan_waveform(cell_format="21700_cylindrical", degradation_mode="gas_generation")
    assert ascan_gas["defect_info"]["has_defect_echo"] is True
    assert "Gas" in ascan_gas["defect_info"]["defect_type"]

    # 3. Li plating: phase inversion and localized scattering
    ascan_plating = synthesize_rf_ascan_waveform(cell_format="21700_cylindrical", degradation_mode="li_plating")
    assert ascan_plating["defect_info"]["has_defect_echo"] is True
    assert "Li" in ascan_plating["defect_info"]["defect_type"]


def test_acoustic_reflection_coefficients():
    """Verify acoustic reflection calculations based on characteristic acoustic impedance Z."""
    # Transducer PZT to Steel casing
    r_pzt_steel = compute_layer_reflection_coefficient("pzt_5a", "steel_casing")
    assert -1.0 <= r_pzt_steel <= 1.0

    # Separator to Gas pocket (near 100% reflection due to huge impedance drop)
    r_gas = compute_layer_reflection_coefficient("separator_polyolefin", "gas_delamination_void")
    assert abs(r_gas) > 0.95


@pytest.mark.asyncio
async def test_machine_cycle_controller_workflow():
    """Verify full 6-stage automated machine diagnostic and rebalancing cycle."""
    controller = MachineCycleController()
    assert controller.current_stage == 'IDLE'
    assert controller.is_running is False

    controller.set_cell_format("prismatic_100ah")
    assert controller.selected_format == "prismatic_100ah"

    # Run automated cycle
    await controller.start_automated_cycle(target_degradation_mode="healthy")
    
    status = controller.get_status()
    assert "GRADE A" in status["certification_grade"]
    assert status["acoustic_coupling_snr_db"] >= 25.0
    assert status["clamping_force_n"] > 0


@pytest.mark.asyncio
async def test_machine_cycle_degraded_grading():
    """Verify machine assigns Grade B or Recycle for degraded cells."""
    controller = MachineCycleController()
    controller.set_cell_format("21700_cylindrical")
    await controller.start_automated_cycle(target_degradation_mode="internal_short")
    
    status = controller.get_status()
    assert "RECYCLE" in status["certification_grade"]


def test_machine_fastapi_endpoints():
    """Verify all machine management REST API endpoints."""
    client = TestClient(app)
    
    # 1. Get status
    res = client.get("/api/machine/status")
    assert res.status_code == 200
    data = res.json()
    assert "current_stage" in data
    assert "selected_format" in data
    assert "clamping_force_n" in data

    # 2. Set form factor
    res_fmt = client.post("/api/machine/format/set?format_name=prismatic_100ah")
    assert res_fmt.status_code == 200
    assert res_fmt.json()["selected_format"] == "prismatic_100ah"

    # 3. Start cycle
    res_cycle = client.post("/api/machine/cycle/start")
    assert res_cycle.status_code == 200
    assert res_cycle.json()["status"] == "started" or "already_running" in res_cycle.json()["status"]

    # 4. Fetch latest A-Scan
    res_ascan = client.get("/api/ascan/latest")
    assert res_ascan.status_code == 200
    ascan_data = res_ascan.json()
    assert "rf_signal" in ascan_data
    assert "envelope" in ascan_data
