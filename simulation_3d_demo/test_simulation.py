#!/usr/bin/env python3
"""
Test script for the 3D EV battery simulation
"""

import sys
import os

def test_imports():
    """Test that required modules can be imported"""
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
        import matplotlib.widgets as widgets
        print("✓ All required imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_simulation_creation():
    """Test that we can create the simulation object"""
    try:
        # Add the simulation directory to path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
        
        # Import the simulation class
        from ev_battery_3d_simulation import EVBattery3DSimulator
        
        # Create an instance (but don't show it)
        sim = EVBattery3DSimulator.__new__(EVBattery3DSimulator)
        sim.__init__()
        
        print("✓ Simulation object created successfully")
        return True
    except Exception as e:
        print(f"✗ Error creating simulation: {e}")
        return False

def test_parameter_updates():
    """Test that parameter updates work"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
        from ev_battery_3d_simulation import EVBattery3DSimulator
        
        sim = EVBattery3DSimulator.__new__(EVBattery3DSimulator)
        sim.__init__()
        
        # Test updating parameters
        original_soc = sim.soc
        sim.update_soc(0.8)
        assert sim.soc == 0.8, f"SOC not updated correctly: {sim.soc}"
        
        sim.update_degradation_mode('li_plating')
        assert sim.degradation_mode == 'li_plating', f"Degradation mode not updated: {sim.degradation_mode}"
        
        print("✓ Parameter updates work correctly")
        return True
    except Exception as e:
        print(f"✗ Error testing parameter updates: {e}")
        return False

def test_sensor_readings():
    """Test that sensor readings computation works"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
        from ev_battery_3d_simulation import EVBattery3DSimulator
        
        sim = EVBattery3DSimulator.__new__(EVBattery3DSimulator)
        sim.__init__()
        
        # Get sensor readings
        readings = sim.compute_sensor_readings()
        
        # Check that we have the expected structure
        assert 'electrical' in readings
        assert 'ultrasonic' in readings
        assert 'thermal' in readings
        
        assert 'voltage' in readings['electrical']
        assert 'current' in readings['electrical']
        assert 'power' in readings['electrical']
        
        assert 'tof' in readings['ultrasonic']
        assert 'amplitude' in readings['ultrasonic']
        assert 'phase_shift' in readings['ultrasonic']
        
        assert 'temperature_rise' in readings['thermal']
        assert 'dT_dt' in readings['thermal']
        
        print("✓ Sensor readings computation works correctly")
        return True
    except Exception as e:
        print(f"✗ Error testing sensor readings: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing 3D EV Battery Simulation")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_simulation_creation,
        test_parameter_updates,
        test_sensor_readings
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
