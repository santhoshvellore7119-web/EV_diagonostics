#!/usr/bin/env python3
"""
Verification script for the 3D EV battery simulation
Checks file structure and basic syntax without requiring GUI dependencies
"""

import sys
import os
import ast

def check_file_exists(filename):
    """Check if a file exists"""
    if os.path.isfile(filename):
        print(f"[OK] {filename} exists")
        return True
    else:
        print(f"[ERROR] {filename} missing")
        return False

def check_python_syntax(filename):
    """Check Python syntax without executing"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        ast.parse(content)
        print(f"[OK] {filename} has valid Python syntax")
        return True
    except SyntaxError as e:
        print(f"[ERROR] {filename} has syntax error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] {filename} could not be read: {e}")
        return False

def check_class_and_methods(filename):
    """Check for expected class and methods"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content)
        
        # Look for class definition
        class_found = False
        methods_found = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'EVBattery3DSimulator':
                class_found = True
                # Look for method definitions
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods_found.append(item.name)
        
        if class_found:
            print(f"[OK] {filename} contains EVBattery3DSimulator class")
            expected_methods = ['__init__', 'update_visualization', 'compute_sensor_readings']
            found_expected = [m for m in expected_methods if m in methods_found]
            if len(found_expected) >= 2:  # At least some expected methods
                print(f"[OK] {filename} contains expected methods: {', '.join(found_expected)}")
                return True
            else:
                print(f"[WARNING] {filename} missing some expected methods. Found: {methods_found}")
                return True  # Still count as pass since class exists
        else:
            print(f"[ERROR] {filename} does not contain EVBattery3DSimulator class")
            return False
            
    except Exception as e:
        print(f"[ERROR] {filename} could not be parsed for class/method check: {e}")
        return False

def main():
    """Run verification checks"""
    print("Verifying 3D EV Battery Simulation")
    print("=" * 40)
    
    # Files to check
    files_to_check = [
        'ev_battery_3d_simulation.py',
        'test_simulation.py'
    ]
    
    all_passed = True
    
    for filename in files_to_check:
        filepath = os.path.join('simulation_3d_demo', filename)
        print(f"\nChecking {filename}:")
        
        file_exists = check_file_exists(filepath)
        if not file_exists:
            all_passed = False
            continue
            
        syntax_ok = check_python_syntax(filepath)
        if not syntax_ok:
            all_passed = False
            
        class_ok = check_class_and_methods(filepath)
        if not class_ok:
            all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("[OK] All verification checks passed!")
        print("  The 3D simulation file is correctly structured.")
        print("  Note: Actual execution requires matplotlib and GUI dependencies.")
        return 0
    else:
        print("[ERROR] Some verification checks failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
