import sys
import os
import numpy as np
import torch
# Add the parent directory to sys.path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'models'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'control'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))

from physics_engine import simulate_cell_response
from virtual_daq import VirtualDAQ
from cell_database import CellDatabase
from fusion_net import MultiBranchFusionNet
from decision_engine import DecisionEngine, RecoveryAction
from rebalancing_sim import RebalancingSimulator
import params as P

def test_data_to_model():
    """Test that data generated can be fed into the model"""
    print("Testing data generation to model flow...")
    db = CellDatabase()
    # Generate a very small batch for quick testing
    X_electrical, X_ultrasonic, X_thermal, y_degradation, y_soh = db.generate_labeled_dataset(
        num_samples=10, soc_range=(0.0, 1.0)
    )
    # Convert to numpy arrays and reshape for CNN
    X_electrical = np.array(X_electrical).reshape(-1, 1, P.SEQ_LENGTH)
    X_ultrasonic = np.array(X_ultrasonic).reshape(-1, 1, P.SEQ_LENGTH)
    X_thermal = np.array(X_thermal).reshape(-1, 1, P.SEQ_LENGTH)
    y_degradation = np.array(y_degradation)
    y_soh = np.array(y_soh)
    
    # Convert to tensors
    elec_tensor = torch.from_numpy(X_electrical).float()
    ultra_tensor = torch.from_numpy(X_ultrasonic).float()
    thermal_tensor = torch.from_numpy(X_thermal).float()
    
    # Create model and do a forward pass
    model = MultiBranchFusionNet(
        seq_length=P.SEQ_LENGTH,
        num_degradation_classes=P.NUM_DEGRADATION_MODES,
        fusion_type='concat'
    )
    model.eval()
    with torch.no_grad():
        output = model(elec_tensor, ultra_tensor, thermal_tensor)
    
    assert 'degradation_logits' in output
    assert 'soh' in output
    assert output['degradation_logits'].shape == (10, P.NUM_DEGRADATION_MODES)
    assert output['soh'].shape == (10, 1)
    print("  PASS")

def test_decision_to_rebalancing():
    """Test that decision engine output can be used by rebalancing simulator"""
    print("Testing decision engine to rebalancing simulator flow...")
    engine = DecisionEngine()
    sim = RebalancingSimulator()
    
    # Test a case that should trigger pulse deplating
    mode_idx = 1  # Li plating
    prob = 0.9
    soh = 88.0
    
    action, params = engine.decide(mode_idx, prob, soh)
    assert action == RecoveryAction.PULSE_DEPLATING
    
    # Now apply this action in the simulator
    result = sim.apply_recovery_action(action, params, cell_soc=0.5, duration_s=20)
    assert 'capacity_recovered_ah' in result
    assert 'energy_input_wh' in result
    assert 'soc_change' in result
    print("  PASS")

def test_full_cycle():
    """Test a full cycle: sense -> decide -> act"""
    print("Testing full sense-decide-act cycle...")
    db = CellDatabase()
    daq = VirtualDAQ()
    engine = DecisionEngine()
    sim = RebalancingSimulator()
    
    # Generate a sample
    soc = 0.5
    mode = 'li_plating'  # This should be recoverable
    raw_response = simulate_cell_response(soc, mode, add_noise=False)
    processed = daq.process_cycle(raw_response)
    
    # For simplicity, we'll just use one feature from each modality as input to a mock model
    # In reality, we'd use the full signals, but for this test we'll mock the ML output
    # to simulate what the model would predict
    
    # Mock ML prediction: high confidence li_plating with good SOH
    predicted_mode_idx = 1  # li_plating
    predicted_prob = 0.92
    predicted_soh = 87.0
    
    # Run decision engine
    action, params = engine.decide(predicted_mode_idx, predicted_prob, predicted_soh)
    
    # Should recommend pulse deplating for li_plating with good SOH and high probability
    assert action == RecoveryAction.PULSE_DEPLATING
    
    # Apply the recovery action
    result = sim.apply_recovery_action(action, params, cell_soc=soc, duration_s=50)
    
    # Check that we got reasonable results
    assert isinstance(result['capacity_recovered_ah'], float)
    assert isinstance(result['energy_input_wh'], float)
    assert isinstance(result['soc_change'], float)
    
    print("  PASS")

if __name__ == '__main__':
    try:
        test_data_to_model()
        test_decision_to_rebalancing()
        test_full_cycle()
        print("\nAll integration tests passed!")
    except Exception as e:
        print(f"\nIntegration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
