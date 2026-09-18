import os
import sys
import re
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ev_cell_multimodal_sim.core.physics_engine import DEGRADATION_PHYSICS_PARAMS


def test_matlab_degradation_mode_library_parity():
    """
    Parse matlab_simulink_demo/utils/degradation_mode_library.m and verify that all
    scaling factors align with the canonical Python physics parameters.
    """
    matlab_file = os.path.join(project_root, 'matlab_simulink_demo', 'utils', 'degradation_mode_library.m')
    assert os.path.exists(matlab_file), f"File {matlab_file} not found"

    with open(matlab_file, 'r', encoding='utf-8') as f:
        content = f.read()

    modes = ['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition', 'gas_generation', 'internal_short']
    healthy_phys = DEGRADATION_PHYSICS_PARAMS['healthy']

    for mode in modes:
        phys = DEGRADATION_PHYSICS_PARAMS[mode]
        # Verify mode is present in MATLAB library
        assert f"base_modes('{mode}')" in content, f"Mode '{mode}' missing in degradation_mode_library.m"
        
        # Verify relative R0 scale
        expected_r0_scale = phys['r0'] / healthy_phys['r0']
        match_r0 = re.search(rf"base_modes\('{mode}'\)\s*=\s*struct\([^)]*'R0_scale',\s*([0-9.]+)", content)
        assert match_r0 is not None, f"Could not parse R0_scale for mode '{mode}'"
        parsed_r0_scale = float(match_r0.group(1))
        assert abs(parsed_r0_scale - expected_r0_scale) < 0.05, (
            f"Mode '{mode}' MATLAB R0_scale ({parsed_r0_scale:.3f}) does not match expected ({expected_r0_scale:.3f})"
        )

        # Verify relative SOS scale
        expected_sos_factor = phys['sos'] / healthy_phys['sos']
        match_sos = re.search(rf"base_modes\('{mode}'\)\s*=\s*struct\([^)]*'sos_factor',\s*([0-9.]+)", content)
        assert match_sos is not None, f"Could not parse sos_factor for mode '{mode}'"
        parsed_sos_factor = float(match_sos.group(1))
        assert abs(parsed_sos_factor - expected_sos_factor) < 0.05, (
            f"Mode '{mode}' MATLAB sos_factor ({parsed_sos_factor:.3f}) does not match expected ({expected_sos_factor:.3f})"
        )
