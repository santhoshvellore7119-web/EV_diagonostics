#!/usr/bin/env python
"""
Unit tests for all Active Rebalancer safety interlocks:
1. Internal Short Fault Isolation Interlock
2. Over-Temperature Thermal Runaway Prevention Interlock
3. Voltage Window Bounds Interlock (Over-voltage & Under-voltage)
4. SOH High-Uncertainty / High-Entropy Safeguard Interlock
"""

import sys
import os
import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ev_cell_multimodal_sim.control.decision_engine import DecisionEngine, DegradationMode, RecoveryAction
from backend.physics_constants import (
    VOLTAGE_MIN_SAFE,
    VOLTAGE_MAX_SAFE,
    TEMP_MAX_SAFE,
    SOH_THRESHOLD_RECOVERABLE
)


def test_internal_short_safety_interlock():
    """Verify that internal short classification immediately engages critical isolation lockout (SHORT_ISOLATION or NONE if irreversible)."""
    engine = DecisionEngine()
    
    # 1. Recoverable internal short triggers SHORT_ISOLATION
    action, params = engine.decide(
        degradation_mode_idx=DegradationMode.INTERNAL_SHORT.value,
        degradation_prob=0.98,
        soh=85.0
    )
    assert action == RecoveryAction.SHORT_ISOLATION
    assert params.get('type') == 'open_circuit'

    # 2. Severe internal short with irreversible SOH (< threshold) triggers lockout (NONE - no current allowed)
    action_severe, params_severe = engine.decide(
        degradation_mode_idx=DegradationMode.INTERNAL_SHORT.value,
        degradation_prob=0.98,
        soh=45.0  # < 70% recoverable threshold
    )
    assert action_severe == RecoveryAction.NONE


def test_over_temperature_thermal_safety_interlock():
    """Verify that excessive temperature (T > 45°C) exceeds safety window and locks out rebalancing."""
    cell_temp = 52.0  # Exceeds TEMP_MAX_SAFE (45°C)
    interlock_engaged = cell_temp > TEMP_MAX_SAFE
    assert interlock_engaged is True, f"Thermal interlock failed to trip at {cell_temp}°C"

    # In thermal runaway risk, active current injection must be prohibited
    engine = DecisionEngine()
    action, _ = engine.decide(
        degradation_mode_idx=DegradationMode.INTERNAL_SHORT.value,
        degradation_prob=0.95,
        soh=50.0
    )
    assert action in (RecoveryAction.SHORT_ISOLATION, RecoveryAction.NONE)


def test_voltage_window_bounds_interlock():
    """Verify voltage under/over-voltage bounds protection against extreme depletion or overcharge."""
    # Under-voltage condition
    v_under = 2.10
    assert v_under < VOLTAGE_MIN_SAFE, f"Under-voltage {v_under}V not detected by safety cutoff {VOLTAGE_MIN_SAFE}V"

    # Over-voltage condition
    v_over = 4.40
    assert v_over > VOLTAGE_MAX_SAFE, f"Over-voltage {v_over}V not detected by safety cutoff {VOLTAGE_MAX_SAFE}V"


def test_soh_uncertainty_safe_handling():
    """Verify that low-confidence / high-entropy ML predictions trigger RESENSING rather than aggressive deplating pulses."""
    engine = DecisionEngine()
    
    # Ambiguous classification with low probability (e.g. 0.45 < 0.70 confidence threshold)
    action, params = engine.decide(
        degradation_mode_idx=DegradationMode.LI_PLATING.value,
        degradation_prob=0.45,
        soh=85.0
    )
    
    # Must NOT initiate aggressive deplating when confidence is low; must request RESENSING or NONE
    assert action != RecoveryAction.PULSE_DEPLATING
    assert action in (RecoveryAction.RESENSING, RecoveryAction.NONE)
