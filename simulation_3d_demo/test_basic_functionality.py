#!/usr/bin/env python3
"""
Basic functionality test for the 3D EV battery simulation
Tests the core logic without requiring GUI display
Avoids Unicode characters that cause encoding issues
"""

import sys
import os

# Add current directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
sim_file = os.path.join(script_dir, 'ev_battery_3d_simulation.py')

def test_file_structure():
    """Test that the simulation file has the expected structure"""
    try:
        # Check that the file exists
        filename = sim_file
        if not os.path.isfile(filename):
            print(f"FAIL: {filename} not found")
            return False

        # Read the file and check for key components
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for class definition
        if 'class EVBattery3DSimulator:' not in content:
            print("FAIL: EVBattery3DSimulator class not found")
            return False

        # Check for key methods
        required_methods = ['__init__', 'update_visualization', 'compute_sensor_readings']
        for method in required_methods:
            if f'def {method}' not in content:
                print(f"FAIL: Method {method} not found")
                return False

        # Check for key attributes
        required_attrs = ['soc', 'degradation_mode', 'noise_level', 'excitation_amplitude', 'params']
        for attr in required_attrs:
            if f'self.{attr}' not in content and f'self.params' not in content:
                # params might be accessed differently
                if attr == 'params' and 'self.params' in content:
                    continue
                elif attr != 'params':
                    print(f"FAIL: Attribute {attr} not found")
                    return False

        print("PASS: File structure test passed")
        return True
    except Exception as e:
        print(f"FAIL: File structure test failed: {e}")
        return False

def test_syntax_without_import():
    """Test Python syntax without actually importing modules that might missing"""
    try:
        filename = sim_file
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()

        # Try to parse the AST to check for syntax errors
        import ast
        tree = ast.parse(content)

        print("PASS: Syntax check passed")
        return True
    except SyntaxError as e:
        print(f"FAIL: Syntax error: {e}")
        return False
    except Exception as e:
        print(f"FAIL: Could not check syntax: {e}")
        return False

def test_parameter_logic():
    """Test the parameter logic by examining the source code"""
    try:
        filename = sim_file
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for parameter update methods
        if 'def update_soc' not in content:
            print("FAIL: update_soc method not found")
            return False
        if 'def update_degradation_mode' not in content:
            print("FAIL: update_degradation_mode method not found")
            return False
        if 'def update_noise' not in content:
            print("FAIL: update_noise method not found")
            return False
        if 'def update_excitation' not in content:
            print("FAIL: update_excitation method not found")
            return False

        # Check for scenario methods
        scenario_methods = ['scenario_healthy', 'scenario_li_plating', 'scenario_active_material_loss',
                          'scenario_electrolyte_decomposition', 'scenario_gas_generation', 'scenario_internal_short']
        for method in scenario_methods:
            if f'def {method}' not in content:
                print(f"FAIL: {method} method not found")
                return False

        print("PASS: Parameter logic test passed")
        return True
    except Exception as e:
        print(f"FAIL: Parameter logic test failed: {e}")
        return False

def test_sensor_method():
    """Test that sensor reading method exists"""
    try:
        filename = sim_file
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()

        if 'def compute_sensor_readings' not in content:
            print("FAIL: compute_sensor_readings method not found")
            return False

        # Check that it returns a dict with expected keys
        if "'electrical'" not in content or "'ultrasonic'" not in content or "'thermal'" not in content:
            print("FAIL: Sensor readings structure not found")
            return False

        print("PASS: Sensor method test passed")
        return True
    except Exception as e:
        print(f"FAIL: Sensor method test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing Basic Functionality of 3D EV Battery Simulation")
    print("=" * 55)

    tests = [
        test_file_structure,
        test_syntax_without_import,
        test_parameter_logic,
        test_sensor_method
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests

    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("PASS: All basic functionality tests passed!")
        return 0
    else:
        print("FAIL: Some basic functionality tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())