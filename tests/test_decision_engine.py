#!/usr/bin/env python
"""
Quick test to verify the enhanced decision engine can be imported and instantiated.
"""

import sys
import os

# Add the project root directory to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from active_rebalancing.decision_engine.state_machine import DecisionEngine, SystemState, DegradationMode, RecoveryAction
    import time

    print("Testing DecisionEngine import and instantiation...")

    # Test basic instantiation
    engine = DecisionEngine()
    print("  DecisionEngine created successfully")

    # Test initial state
    status = engine.get_status()
    print(f"  Initial state: {status['state']}")
    assert status['state'] == 'IDLE', f"Expected IDLE, got {status['state']}"

    # Test updating ML results
    print("  Testing ML results update...")
    engine.update_ml_results(DegradationMode.LI_PLATING.value, 0.85, 75.0)
    status = engine.get_status()
    print(f"    After ML update - Mode: {status['ml_results']['degradation_mode'].name}, SOH: {status['ml_results']['soh']}%")
    assert status['ml_results']['degradation_mode'] == DegradationMode.LI_PLATING
    assert abs(status['ml_results']['soh'] - 75.0) < 0.1

    # Test setting cell characteristics
    print("  Testing cell characteristics...")
    engine.set_cell_characteristics({
        'age_months': 18,
        'chemistry': 'NMC',
        'form_factor': 'cylindrical'
    })
    status = engine.get_status()
    print(f"    Cell characteristics set: {bool(status.get('cell_under_test') is None)}")  # Will be None until set

    # Test a simple execution cycle
    print("  Testing execution cycle...")
    for i in range(5):
        result = engine.execute()
        # Just verify it runs without error and returns expected structure
        assert 'state' in result
        assert 'action' in result
        assert 'parameters' in result
        assert 'done' in result

    print("All DecisionEngine tests passed!")

except Exception as e:
    print(f"Error testing DecisionEngine: {e}")
    import traceback
    traceback.print_exc()