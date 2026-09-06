import sys
import os
import numpy as np
import torch

package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if package_root not in sys.path:
    sys.path.insert(0, package_root)

from core.physics_engine import simulate_cell_response
from core.virtual_daq import VirtualDAQ
from core.cell_database import CellDatabase
from models.fusion_net import MultiBranchFusionNet
from control.decision_engine import DecisionEngine, DegradationMode, RecoveryAction
from control.rebalancing_sim import RebalancingSimulator
import config.params as P

def test_physics_engine():
    print("Testing physics_engine...")
    soc = 0.5
    mode = 'healthy'
    response = simulate_cell_response(soc, mode, add_noise=False)
    assert 'electrical' in response
    assert 'ultrasonic' in response
    assert 'thermal' in response
    assert response['electrical']['voltage'].shape == (P.SAMPLES_PER_CYCLE,)
    assert isinstance(response['ultrasonic']['tof'], float)
    assert response['thermal']['temperature_rise'].shape == (P.SAMPLES_PER_CYCLE,)
    print("  PASS")

def test_virtual_daq():
    print("Testing virtual_daq...")
    daq = VirtualDAQ()
    soc = 0.5
    mode = 'healthy'
    raw = simulate_cell_response(soc, mode, add_noise=False)
    processed = daq.process_cycle(raw)
    assert 'electrical' in processed
    assert 'ultrasonic' in processed
    assert 'thermal' in processed
    assert processed['electrical']['voltage'].shape == (P.SAMPLES_PER_CYCLE,)
    assert isinstance(processed['ultrasonic']['tof'], float)
    assert processed['thermal']['temperature_rise'].shape == (P.SAMPLES_PER_CYCLE,)
    print("  PASS")

def test_cell_database():
    print("Testing cell_database...")
    db = CellDatabase()
    # Generate a tiny batch
    X_electrical, X_ultrasonic, X_thermal, y_degradation, y_soh = db.generate_labeled_dataset(num_samples=5, soc_range=(0.0, 1.0))
    assert len(X_electrical) == 5
    assert len(X_ultrasonic) == 5
    assert len(X_thermal) == 5
    assert len(y_degradation) == 5
    assert len(y_soh) == 5
    # Check one sample is numpy array of correct shape
    assert isinstance(X_electrical[0], np.ndarray)
    assert X_electrical[0].shape == (P.SAMPLES_PER_CYCLE,)
    print("  PASS")

def test_fusion_net():
    print("Testing fusion_net...")
    batch_size = 2
    seq_length = P.SEQ_LENGTH
    elec = torch.randn(batch_size, 1, seq_length)
    ultra = torch.randn(batch_size, 1, seq_length)
    thermal = torch.randn(batch_size, 1, seq_length)
    model = MultiBranchFusionNet(seq_length=seq_length, fusion_type='concat')
    output = model(elec, ultra, thermal)
    assert 'degradation_logits' in output
    assert 'soh' in output
    assert output['degradation_logits'].shape == (batch_size, P.NUM_DEGRADATION_MODES)
    assert output['soh'].shape == (batch_size, 1)
    print("  PASS")

def test_decision_engine():
    print("Testing decision_engine...")
    engine = DecisionEngine()
    # Test a few cases
    # Note: recovery only if soh >= self.soh_threshold_recoverable (80.0)
    test_cases = [
        (0, 0.95, 95.0, RecoveryAction.NONE),  # healthy
        (1, 0.90, 88.0, RecoveryAction.PULSE_DEPLATING),  # li_plating, high prob, good SOH
        (1, 0.50, 88.0, RecoveryAction.NONE),  # li_plating, low prob
        (1, 0.90, 60.0, RecoveryAction.NONE),  # li_plating, low SOH (<80)
        (2, 0.85, 82.0, RecoveryAction.EQUILIBRATION),  # active material loss, SOH>=80
        (2, 0.85, 75.0, RecoveryAction.NONE),  # active material loss, SOH<80
        (3, 0.80, 80.0, RecoveryAction.EQUILIBRATION),  # electrolyte decomposition, SOH=80
        (3, 0.80, 75.0, RecoveryAction.NONE),  # electrolyte decomposition, SOH<80
        (4, 0.75, 90.0, RecoveryAction.GAS_RECOMBINATION),  # gas generation, SOH>=80
        (4, 0.75, 75.0, RecoveryAction.NONE),  # gas generation, SOH<80
        (5, 0.80, 85.0, RecoveryAction.SHORT_ISOLATION),  # internal short, SOH>=80
        (5, 0.80, 75.0, RecoveryAction.NONE),  # internal short, SOH<80
    ]
    for mode_idx, prob, soh, expected in test_cases:
        action, params = engine.decide(mode_idx, prob, soh)
        assert action == expected, f"Expected {expected}, got {action} for mode_idx={mode_idx}, prob={prob}, soh={soh}"
    print("  PASS")

def test_rebalancing_sim():
    print("Testing rebalancing_sim...")
    sim = RebalancingSimulator()
    # Test pulse deplating
    action = RecoveryAction.PULSE_DEPLATING
    params = {
        'voltage': 4.2,
        'pulse_width_ms': 10,
        'pulse_interval_s': 1,
        'num_pulses': 10
    }
    result = sim.apply_recovery_action(action, params, cell_soc=0.5, duration_s=20)
    assert 'capacity_recovered_ah' in result
    assert 'energy_input_wh' in result
    assert 'soc_change' in result
    # Just check that it returns numbers (could be zero)
    assert isinstance(result['capacity_recovered_ah'], float)
    assert isinstance(result['energy_input_wh'], float)
    assert isinstance(result['soc_change'], float)
    print("  PASS")

if __name__ == '__main__':
    try:
        test_physics_engine()
        test_virtual_daq()
        test_cell_database()
        test_fusion_net()
        test_decision_engine()
        test_rebalancing_sim()
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
