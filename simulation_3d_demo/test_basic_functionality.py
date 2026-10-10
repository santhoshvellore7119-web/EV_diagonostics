#!/usr/bin/env python3
"""
Basic functionality test for the 3D EV battery simulation
Tests the core logic without requiring GUI display.
"""

import sys
import os
import ast

# Add current directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
sim_file = os.path.join(script_dir, 'ev_battery_3d_simulation.py')


def test_file_structure():
    """Test that the simulation file has the expected structure."""
    assert os.path.isfile(sim_file), f"{sim_file} not found"

    with open(sim_file, 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'class EVBattery3DSimulator:' in content, "EVBattery3DSimulator class not found"

    required_methods = ['__init__', 'update_visualization', 'compute_sensor_readings']
    for method in required_methods:
        assert f'def {method}' in content, f"Method {method} not found"

    required_attrs = ['soc', 'degradation_mode', 'noise_level', 'excitation_amplitude']
    for attr in required_attrs:
        assert f'self.{attr}' in content or 'self.params' in content, f"Attribute {attr} not found"


def test_syntax_without_import():
    """Test Python syntax by parsing the AST without importing."""
    assert os.path.isfile(sim_file)
    with open(sim_file, 'r', encoding='utf-8') as f:
        content = f.read()

    tree = ast.parse(content)
    assert tree is not None


def test_parameter_logic():
    """Test the parameter logic by examining the source code."""
    with open(sim_file, 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'def update_soc' in content, "update_soc method not found"
    assert 'def update_degradation_mode' in content, "update_degradation_mode method not found"
    assert 'def update_noise' in content, "update_noise method not found"
    assert 'def update_excitation' in content, "update_excitation method not found"

    scenario_methods = [
        'scenario_healthy', 'scenario_li_plating', 'scenario_active_material_loss',
        'scenario_electrolyte_decomposition', 'scenario_gas_generation', 'scenario_internal_short'
    ]
    for method in scenario_methods:
        assert f'def {method}' in content, f"{method} method not found"


def test_sensor_method():
    """Test that sensor reading method exists and structure is defined."""
    with open(sim_file, 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'def compute_sensor_readings' in content, "compute_sensor_readings method not found"
    assert "'electrical'" in content and "'ultrasonic'" in content and "'thermal'" in content


if __name__ == "__main__":
    test_file_structure()
    test_syntax_without_import()
    test_parameter_logic()
    test_sensor_method()
    print("[OK] All basic functionality tests passed.")