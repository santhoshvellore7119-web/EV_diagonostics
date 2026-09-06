#!/usr/bin/env python
"""
Unit and integration tests for Active Rebalancing Decision Engine state machine.
"""

import sys
import os
import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from active_rebalancing.decision_engine.state_machine import DecisionEngine, SystemState, DegradationMode, RecoveryAction


def test_decision_engine_instantiation():
    """Verify decision engine initializes in IDLE state."""
    engine = DecisionEngine()
    status = engine.get_status()
    assert status['state'] == 'IDLE' or status['state'] == SystemState.IDLE.name


def test_decision_engine_ml_update():
    """Verify ML diagnostic inferences update state machine parameters."""
    engine = DecisionEngine()
    engine.update_ml_results(DegradationMode.LI_PLATING.value, 0.85, 75.0)
    status = engine.get_status()
    assert status['ml_results']['degradation_mode'] == DegradationMode.LI_PLATING
    assert abs(status['ml_results']['soh'] - 75.0) < 0.1


def test_decision_engine_cell_characteristics():
    """Verify setting cell chemistry and characteristics."""
    engine = DecisionEngine()
    engine.set_cell_characteristics({
        'age_months': 18,
        'chemistry': 'NMC',
        'form_factor': 'cylindrical'
    })
    status = engine.get_status()
    assert status is not None


def test_decision_engine_execution_cycles():
    """Verify execution cycles advance state machine without uncaught exceptions."""
    engine = DecisionEngine()
    for _ in range(5):
        result = engine.execute()
        assert 'state' in result
        assert 'action' in result
        assert 'parameters' in result
        assert 'done' in result


if __name__ == '__main__':
    print("Running DecisionEngine tests directly...")
    test_decision_engine_instantiation()
    test_decision_engine_ml_update()
    test_decision_engine_cell_characteristics()
    test_decision_engine_execution_cycles()
    print("All DecisionEngine tests passed successfully!")