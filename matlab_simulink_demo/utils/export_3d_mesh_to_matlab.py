#!/usr/bin/env python3
"""
3D Battery Mesh & Physics Exporter for MATLAB / Simulink Digital Twin.

Exports coupled 3D spatial thermal field, solid diffusion intercalation stress tensors,
multi-layer acoustic boundary transfer matrices, and 4S pack module co-simulation states
into MATLAB-compatible formats (.mat / structured JSON).
"""

import os
import sys
import json
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from simulation_3d_demo.ev_battery_3d_simulation import EVBattery3DSimulator


def _to_list(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, list):
        return [float(x) if isinstance(x, (np.floating, float, int, np.integer)) else x for x in obj]
    return obj


def export_3d_physics_to_matlab(output_dir: str = None) -> dict:
    """
    Generate and serialize full 3D spatial simulation state into MATLAB workspace files.
    """
    if output_dir is None:
        output_dir = os.path.join(PROJECT_ROOT, 'matlab_simulink_demo', 'validation', 'validation_data')
    os.makedirs(output_dir, exist_ok=True)

    sim = EVBattery3DSimulator(headless=True)
    sim.update_soc(0.60)
    sim.update_degradation_mode('healthy')

    # 1. 3D Thermal Finite-Volume Grid
    thermal_res = sim.compute_3d_thermal_field(nr=25, ntheta=16, nz=30)
    r_nodes = thermal_res['r_grid']
    z_nodes = thermal_res['z_grid']
    temp_grid = thermal_res['T_field']

    # 2. 3D Intercalation & Thermal Elastic Stress Tensors
    stress_results = sim.compute_intercalation_and_thermal_stress(nr=25)

    # 3. 7-Layer Acoustic Transfer Matrix
    acoustic_results = sim.compute_multilayer_acoustic_transfer_matrix()

    # 4. 4S Pack Level Multi-Cell State
    pack_4s = sim.compute_4s_pack_state()

    payload = {
        "grid": {
            "r_nodes_m": _to_list(r_nodes),
            "z_nodes_m": _to_list(z_nodes),
            "radius_cell_m": 0.009,
            "height_cell_m": 0.065,
        },
        "thermal_3d": {
            "temperature_grid_c": _to_list(temp_grid),
            "t_core_max_c": round(float(thermal_res['T_max']), 3),
            "t_surf_min_c": round(float(thermal_res['T_min']), 3),
            "t_ambient_c": 25.0,
        },
        "stress_tensors": {
            "radius_m": _to_list(stress_results["r_grid_m"]),
            "sigma_rr_mpa": _to_list(stress_results["sigma_rr_mpa"]),
            "sigma_theta_mpa": _to_list(stress_results["sigma_theta_mpa"]),
            "sigma_zz_mpa": _to_list(stress_results["sigma_zz_mpa"]),
            "sigma_vm_mpa": _to_list(stress_results["sigma_vm_mpa"]),
            "max_von_mises_mpa": round(float(stress_results["max_vm_stress_mpa"]), 4),
        },
        "acoustic_transfer": {
            "layers": acoustic_results["layers"],
            "interfaces": acoustic_results["interfaces"],
            "net_acoustic_throughput_pct": acoustic_results["net_acoustic_throughput_pct"],
        },
        "pack_4s_module": pack_4s,
    }

    # Save to JSON
    json_path = os.path.join(output_dir, 'matlab_3d_battery_mesh.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)

    # Save to MAT file if scipy is available
    mat_path = os.path.join(output_dir, 'matlab_3d_battery_mesh.mat')
    try:
        from scipy.io import savemat
        savemat(mat_path, {
            "r_nodes": np.array(r_nodes),
            "z_nodes": np.array(z_nodes),
            "T_field": np.array(temp_grid),
            "sigma_rr": np.array(stress_results["sigma_rr_mpa"]),
            "sigma_tt": np.array(stress_results["sigma_theta_mpa"]),
            "sigma_zz": np.array(stress_results["sigma_zz_mpa"]),
            "sigma_vm": np.array(stress_results["sigma_vm_mpa"]),
            "P_acoustic": np.array(acoustic_results["net_acoustic_throughput_pct"]),
        })
        payload["mat_file"] = mat_path
    except ImportError:
        payload["mat_file"] = None

    payload["json_file"] = json_path
    print(f"[SUCCESS] Exported 3D physics dataset to MATLAB directory: {json_path}")
    return payload


if __name__ == '__main__':
    export_3d_physics_to_matlab()
