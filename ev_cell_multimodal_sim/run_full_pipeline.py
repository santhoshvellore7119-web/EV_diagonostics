"""
Master end-to-end execution script for the EV battery multi-modal diagnostic simulation.
Runs the complete pipeline: Data Generation -> Model Training -> Evaluation -> Decision Engine -> Rebalancing Simulation -> Report.
"""

import os
import sys
import time
import json
import numpy as np
import torch
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.cell_database import CellDatabase
from models.train import train_model
from models.evaluate import evaluate_model
from control.decision_engine import DecisionEngine
from models.fusion_net import MultiBranchFusionNet
from control.rebalancing_sim import RebalancingSimulator
from config import params as P


def run_full_pipeline():
    """
    Execute the full simulation pipeline.
    """
    # Record start time for the entire pipeline
    start_time_global = time.time()

    print("=" * 60)
    print("LOW-COST MULTI-MODAL DIAGNOSTIC AND ACTIVE CELL-REBALANCING SYSTEM")
    print("FULL PIPELINE EXECUTION")
    print("=" * 60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Step 0: Setup
    print("Step 0: Setting up environment...")
    os.makedirs('data', exist_ok=True)
    os.makedirs('models', exist_ok=True)
    os.makedirs('results', exist_ok=True)
    print("Directories created.")
    print()

    # Step 1: Data Generation
    print("Step 1: Generating synthetic dataset...")
    start_time = time.time()
    db = CellDatabase()
    # Generate a dataset for training and evaluation
    X_electrical, X_ultrasonic, X_thermal, y_degradation, y_soh = db.generate_labeled_dataset(
        num_samples=5000, soc_range=(0.0, 1.0)
    )
    # Save the dataset
    np.save('data/X_electrical.npy', X_electrical)
    np.save('data/X_ultrasonic.npy', X_ultrasonic)
    np.save('data/X_thermal.npy', X_thermal)
    np.save('data/y_degradation.npy', y_degradation)
    np.save('data/y_soh.npy', y_soh)
    elapsed = time.time() - start_time
    print(f"  Generated {len(X_electrical)} samples.")
    print(f"  Saved to data/ directory.")
    print(f"  Time elapsed: {elapsed:.2f} seconds")
    print()

    # Step 2: Model Training
    print("Step 2: Training multi-branch fusion network...")
    start_time = time.time()
    # We'll use the training function from models/train.py, but we need to adapt it to work without data loaders
    # For simplicity, we'll replicate the essential parts here or call the train.py script.
    # We'll call the train.py script as a subprocess for simplicity in this script.
    # However, to avoid subprocess complexity, we'll import and use the training logic directly.
    # Let's reuse the train_model function from models.train, but we need to prepare data loaders.
    from torch.utils.data import TensorDataset, DataLoader, random_split

    # Convert to tensors
    X_electrical_tensor = torch.from_numpy(X_electrical).float()
    X_ultrasonic_tensor = torch.from_numpy(X_ultrasonic).float()
    X_thermal_tensor = torch.from_numpy(X_thermal).float()
    y_degradation_tensor = torch.from_numpy(y_degradation).long()
    y_soh_tensor = torch.from_numpy(y_soh).float()

    # Reshape for CNN: (N, 1, L)
    X_electrical_tensor = X_electrical_tensor.view(-1, 1, P.SEQ_LENGTH)
    X_ultrasonic_tensor = X_ultrasonic_tensor.view(-1, 1, P.SEQ_LENGTH)
    X_thermal_tensor = X_thermal_tensor.view(-1, 1, P.SEQ_LENGTH)

    # Create TensorDataset
    dataset = TensorDataset(
        X_electrical_tensor,
        X_ultrasonic_tensor,
        X_thermal_tensor,
        y_degradation_tensor,
        y_soh_tensor
    )

    # Split dataset
    train_size = int(0.7 * len(dataset))
    val_size = int(0.15 * len(dataset))
    test_size = len(dataset) - train_size - val_size
    train_dataset, val_dataset, test_dataset = random_split(
        dataset, [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(P.RANDOM_SEED)
    )

    # Create data loaders
    train_loader = DataLoader(train_dataset, batch_size=P.BATCH_SIZE, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_dataset, batch_size=P.BATCH_SIZE, shuffle=False, num_workers=2)
    test_loader = DataLoader(test_dataset, batch_size=P.BATCH_SIZE, shuffle=False, num_workers=2)

    # Initialize model
    model = MultiBranchFusionNet(
        seq_length=P.SEQ_LENGTH,
        num_degradation_classes=P.NUM_DEGRADATION_MODES,
        fusion_type=getattr(P, 'FUSION_TYPE', 'concat')
    )

    # Loss functions
    criterion_cls = torch.nn.CrossEntropyLoss()
    criterion_reg = torch.nn.MSELoss()

    # Optimizer
    optimizer = torch.optim.Adam(model.parameters(), lr=P.LEARNING_RATE)

    # Train
    print(f"  Training configuration:")
    print(f"    Batch size: {P.BATCH_SIZE}")
    print(f"    Learning rate: {P.LEARNING_RATE}")
    print(f"    Epochs: {P.NUM_EPOCHS}")
    print(f"    Fusion type: {getattr(P, 'FUSION_TYPE', 'concat')}")
    history = train_model(model, train_loader, val_loader, criterion_cls, optimizer,
                          torch.device('cuda' if torch.cuda.is_available() else 'cpu'),
                          num_epochs=P.NUM_EPOCHS, use_uncertainty=True)
    # The train_model function already saves the best model as 'best_model.pth'
    elapsed = time.time() - start_time
    print(f"  Training completed.")
    print(f"  Time elapsed: {elapsed:.2f} seconds")
    print()

    # Step 3: Model Evaluation
    print("Step 3: Evaluating model performance...")
    start_time = time.time()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    # Load the best model
    checkpoint = torch.load('best_model.pth', map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()
    # Evaluate
    results = evaluate_model('best_model.pth', test_loader, device)
    elapsed = time.time() - start_time
    print(f"  Evaluation completed.")
    print(f"  ROC-AUC: {results['roc_auc']:.4f}" if results['roc_auc'] is not None else "  ROC-AUC: Failed")
    print(f"  SOH RMSE: {results['soh_rmse']:.4f}")
    print(f"  Time elapsed: {elapsed:.2f} seconds")
    print()

    # Save evaluation results
    evaluation_results = {
        'timestamp': datetime.now().isoformat(),
        'metrics': results
    }
    with open('results/evaluation_results.json', 'w') as f:
        json.dump(evaluation_results, f, indent=2)
    print("  Evaluation results saved to results/evaluation_results.json")
    print()

    # Step 4: Decision Engine Simulation
    print("Step 4: Simulating decision engine...")
    start_time = time.time()
    engine = DecisionEngine()
    # We'll simulate a few test cases
    test_cases = [
        # (mode_idx, prob, soh, expected_action)
        (0, 0.95, 95.0, 'NONE'),  # healthy
        (1, 0.90, 88.0, 'PULSE_DEPLATING'),  # li_plating, high prob, good SOH
        (1, 0.50, 88.0, 'NONE'),  # li_plating, low prob
        (1, 0.90, 60.0, 'NONE'),  # li_plating, low SOH
        (2, 0.85, 82.0, 'EQUILIBRATION'),  # active_material_loss
        (3, 0.80, 80.0, 'EQUILIBRATION'),  # electrolyte_decomposition
        (4, 0.75, 90.0, 'GAS_RECOMBINATION'),  # gas_generation
        (5, 0.80, 75.0, 'SHORT_ISOLATION'),  # internal_short
    ]
    decisions = []
    for mode_idx, prob, soh, expected in test_cases:
        action, parameters = engine.decide(mode_idx, prob, soh)
        decisions.append({
            'mode_idx': mode_idx,
            'mode_name': ['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition', 'gas_generation', 'internal_short'][mode_idx],
            'probability': prob,
            'soh': soh,
            'decision': action.name if hasattr(action, 'name') else str(action),
            'parameters': parameters,
            'expected': expected
        })
    elapsed = time.time() - start_time
    print(f"  Simulated {len(test_cases)} test cases.")
    print(f"  Time elapsed: {elapsed:.2f} seconds")
    print()

    # Save decision engine results
    decision_results = {
        'timestamp': datetime.now().isoformat(),
        'test_cases': decisions
    }
    with open('results/decision_results.json', 'w') as f:
        json.dump(decision_results, f, indent=2)
    print("  Decision results saved to results/decision_results.json")
    print()

    # Step 5: Rebalancing Simulation
    print("Step 5: Simulating active rebalancing...")
    start_time = time.time()
    sim = RebalancingSimulator()
    # Simulate a few recovery actions
    recovery_tests = [
        # (action, parameters, soc, duration)
        ('PULSE_DEPLATING',
         {'voltage': 4.2, 'pulse_width_ms': 10, 'pulse_interval_s': 1, 'num_pulses': 50},
         0.5, 100),
        ('EQUILIBRATION',
         {'current': 0.5, 'direction': 'charge'},
         0.5, 300),
        ('GAS_RECOMBINATION',
         {'voltage': 3.9},
         0.5, 600),
        ('SHORT_ISOLATION',
         {},
         0.5, 10),
        ('BALANCING',
         {'target_voltage': 3.7, 'tolerance': 0.01},
         0.5, 300)
    ]
    recovery_results = []
    for action_name, params, soc, duration in recovery_tests:
        # Convert action name to enum
        from control.decision_engine import RecoveryAction
        action_enum = getattr(RecoveryAction, action_name)
        result = sim.apply_recovery_action(action_enum, params, soc, duration)
        recovery_results.append({
            'action': action_name,
            'parameters': params,
            'initial_soc': soc,
            'duration_s': duration,
            'soc_change': result['soc_change'],
            'capacity_recovered_ah': result['capacity_recovered_ah'],
            'energy_input_wh': result['energy_input_wh']
        })
    elapsed = time.time() - start_time
    print(f"  Simulated {len(recovery_tests)} recovery actions.")
    print(f"  Time elapsed: {elapsed:.2f} seconds")
    print()

    # Save rebalancing results
    rebalancing_results = {
        'timestamp': datetime.now().isoformat(),
        'recovery_actions': recovery_results
    }
    with open('results/rebalancing_results.json', 'w') as f:
        json.dump(rebalancing_results, f, indent=2)
    print("  Rebalancing results saved to results/rebalancing_results.json")
    print()

    # Step 6: Generate Final Report
    print("Step 6: Generating final report...")
    report = {
        'pipeline_execution': {
            'start_time': datetime.now().isoformat(),
            'end_time': datetime.now().isoformat(),
            'total_time_elapsed': time.time() - start_time_global if 'start_time_global' in locals() else 0
        },
        'data_generation': {
            'num_samples': len(X_electrical),
            'soc_range': [0.0, 1.0],
            'degradation_modes': ['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition', 'gas_generation', 'internal_short']
        },
        'model_training': {
            'best_model_path': 'best_model.pth',
            'final_val_loss': checkpoint['val_loss'] if 'checkpoint' in locals() else None,
            'final_val_acc': checkpoint['val_acc'] if 'checkpoint' in locals() else None
        },
        'model_evaluation': evaluation_results['metrics'],
        'decision_engine': decision_results,
        'rebalancing_simulation': rebalancing_results
    }
    # Calculate total time
    total_elapsed = time.time() - start_time_global if 'start_time_global' in locals() else time.time() - start_time
    report['pipeline_execution']['total_time_elapsed'] = total_elapsed
    report['pipeline_execution']['end_time'] = datetime.now().isoformat()

    with open('results/final_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    print("  Final report saved to results/final_report.json")
    print()

    print("=" * 60)
    print("PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
    print(f"Total time elapsed: {total_elapsed:.2f} seconds")
    print("Results saved in the 'results' directory.")
    print("=" * 60)


if __name__ == "__main__":
    # Record the start time for the entire pipeline
    start_time_global = time.time()
    run_full_pipeline()