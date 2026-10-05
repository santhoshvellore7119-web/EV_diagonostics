#!/usr/bin/env python3
"""
Unit tests for the 3D EV battery simulation module.
"""

import sys
import os
import matplotlib
matplotlib.use('Agg')


def test_imports():
    """Test that required modules can be imported."""
    import numpy as np
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    import matplotlib.widgets as widgets
    assert np is not None
    assert plt is not None


def test_simulation_creation():
    """Test that we can create the simulation object."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from ev_battery_3d_simulation import EVBattery3DSimulator
    
    sim = EVBattery3DSimulator(headless=True)
    assert sim.soc == 0.5
    assert sim.degradation_mode == 'healthy'


def test_parameter_updates():
    """Test that parameter updates work properly."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from ev_battery_3d_simulation import EVBattery3DSimulator
    
    sim = EVBattery3DSimulator(headless=True)
    
    sim.update_soc(0.8)
    assert abs(sim.soc - 0.8) < 1e-6
    
    sim.update_degradation_mode('li_plating')
    assert sim.degradation_mode == 'li_plating'


def test_sensor_readings():
    """Test that sensor readings computation works properly."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from ev_battery_3d_simulation import EVBattery3DSimulator
    
    sim = EVBattery3DSimulator(headless=True)
    
    readings = sim.compute_sensor_readings()
    
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


if __name__ == '__main__':
    test_imports()
    test_simulation_creation()
    test_parameter_updates()
    test_sensor_readings()
    print("[OK] All 3D simulation tests passed.")
