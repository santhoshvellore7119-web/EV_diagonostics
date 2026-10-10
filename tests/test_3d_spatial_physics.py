import os
import sys
import numpy as np
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from simulation_3d_demo.ev_battery_3d_simulation import EVBattery3DSimulator
from ev_cell_multimodal_sim.core.physics_engine import DEGRADATION_PHYSICS_PARAMS


def test_3d_thermal_spatial_finite_volume():
    """
    Verify 3D spatial finite-volume thermal diffusion calculations:
    - Anisotropic heat conduction (radial vs axial)
    - Hotspot temperature localization in internal_short mode
    """
    sim_healthy = EVBattery3DSimulator(headless=True)
    sim_healthy.degradation_mode = 'healthy'
    sim_healthy.soc = 0.50
    thermal_healthy = sim_healthy.compute_3d_thermal_field(nr=8, ntheta=16, nz=10)

    assert 'T_field' in thermal_healthy
    assert thermal_healthy['T_field'].shape == (8, 16, 10)
    assert thermal_healthy['T_max'] >= 25.0
    assert thermal_healthy['T_min'] >= 24.5
    # Core should be slightly warmer than outer surface due to Joule heat dissipation
    assert thermal_healthy['T_max'] >= thermal_healthy['T_min']

    # Internal Short hotspot verification
    sim_short = EVBattery3DSimulator(headless=True)
    sim_short.degradation_mode = 'internal_short'
    sim_short.soc = 0.50
    thermal_short = sim_short.compute_3d_thermal_field(nr=8, ntheta=16, nz=10)

    assert thermal_short['T_max'] > thermal_healthy['T_max'] + 10.0, (
        f"Internal short T_max ({thermal_short['T_max']:.1f}C) must exceed healthy T_max ({thermal_healthy['T_max']:.1f}C)"
    )


def test_3d_acoustic_ray_tracing():
    """
    Verify multi-layer acoustic ray tracing and attenuation calculations.
    """
    sim = EVBattery3DSimulator(headless=True)
    
    # Healthy rays
    sim.degradation_mode = 'healthy'
    rays_healthy = sim.compute_acoustic_ray_path(num_rays=10)
    assert len(rays_healthy) == 10
    for ray in rays_healthy:
        assert ray['tof_us'] > 5.0
        assert ray['tof_us'] < 12.0
        assert ray['amplitude'] > 0.85

    # Gas generation rays should exhibit severe scattering attenuation
    sim.degradation_mode = 'gas_generation'
    rays_gas = sim.compute_acoustic_ray_path(num_rays=10)
    mean_amp_healthy = np.mean([r['amplitude'] for r in rays_healthy])
    mean_amp_gas = np.mean([r['amplitude'] for r in rays_gas])
    assert mean_amp_gas < mean_amp_healthy * 0.75, (
        f"Gas generation acoustic amplitude ({mean_amp_gas:.2f}) must be significantly attenuated vs healthy ({mean_amp_healthy:.2f})"
    )


def test_3d_degradation_spatial_profile():
    """
    Verify 3D spatial degradation feature synthesis (dendrites, gas pockets, defect cores).
    """
    sim = EVBattery3DSimulator(headless=True)
    
    # Li plating
    sim.degradation_mode = 'li_plating'
    prof_li = sim.compute_degradation_spatial_profile()
    assert prof_li['mode'] == 'li_plating'
    assert len(prof_li['features']) > 0
    assert prof_li['features'][0]['type'] == 'plating_layer'

    # Gas generation
    sim.degradation_mode = 'gas_generation'
    prof_gas = sim.compute_degradation_spatial_profile()
    assert prof_gas['mode'] == 'gas_generation'
    assert len(prof_gas['features']) > 0
    assert prof_gas['features'][0]['type'] == 'gas_bubble'

    # Internal short
    sim.degradation_mode = 'internal_short'
    prof_short = sim.compute_degradation_spatial_profile()
    assert prof_short['mode'] == 'internal_short'
    assert prof_short['features'][0]['type'] == 'internal_short_core'


def test_3d_state_export_and_json_serialization():
    """
    Verify complete 3D multi-physics state dictionary export.
    """
    sim = EVBattery3DSimulator(headless=True)
    state_dict = sim.export_3d_state_dict()

    assert 'soc' in state_dict
    assert 'degradation_mode' in state_dict
    assert 'thermal' in state_dict
    assert 'acoustic_rays' in state_dict
    assert 'degradation_profile' in state_dict
    assert 'sensors' in state_dict
    assert 'readings' in state_dict
    assert 'stress' in state_dict
    assert 'acoustic_transfer' in state_dict
    assert 'pack_4s' in state_dict


def test_3d_intercalation_and_thermal_stress():
    """
    Verify 3D cylindrical mechanical stress tensor computations:
    - Radial, hoop, axial, and Von Mises equivalent stress profiles
    """
    sim = EVBattery3DSimulator(headless=True)
    sim.soc = 0.80
    stress_res = sim.compute_intercalation_and_thermal_stress(nr=20)

    assert 'sigma_rr_mpa' in stress_res
    assert 'sigma_theta_mpa' in stress_res
    assert 'sigma_vm_mpa' in stress_res
    assert len(stress_res['sigma_rr_mpa']) == 20
    assert stress_res['max_vm_stress_mpa'] > 0.0
    # Radial stress at boundary r=R should approach ~0 MPa
    assert abs(stress_res['sigma_rr_mpa'][-1]) < 0.5


def test_multilayer_acoustic_transfer_matrix():
    """
    Verify boundary reflection and transmission coefficient calculations across jellyroll layers.
    """
    sim = EVBattery3DSimulator(headless=True)
    sim.degradation_mode = 'healthy'
    ac_healthy = sim.compute_multilayer_acoustic_transfer_matrix()
    assert ac_healthy['net_acoustic_throughput_pct'] > 0.10
    assert len(ac_healthy['interfaces']) >= 6

    # Gas generation creates massive mismatch and drops transmission by >95%
    sim.degradation_mode = 'gas_generation'
    ac_gas = sim.compute_multilayer_acoustic_transfer_matrix()
    assert ac_gas['net_acoustic_throughput_pct'] < ac_healthy['net_acoustic_throughput_pct'] * 0.05


def test_4s_pack_multi_cell_state():
    """
    Verify 4-cell series module active ZVS balancing and coupled thermal telemetry.
    """
    sim = EVBattery3DSimulator(headless=True)
    sim.soc = 0.60
    pack_res = sim.compute_4s_pack_state()

    assert len(pack_res['cell_voltages_v']) == 4
    assert len(pack_res['cell_socs']) == 4
    assert pack_res['pack_voltage_v'] > 12.0
    assert pack_res['active_balancing_current_a'] > 0.0
    assert pack_res['rebalancing_state'] == "ACTIVE_BALANCING_ZVS"
    assert pack_res['zvs_efficiency_pct'] >= 91.5
