"""
Evaluation script for the trained model.
Computes ROC-AUC, classification metrics, and SOH RMSE.
Updated for uncertainty-aware fusion network.
"""

import torch
import numpy as np
import json
import os
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from core.cell_database import CellDatabase
from models.fusion_net import MultiBranchFusionNet, BaselineFusionNet
from config import params as P


def evaluate_model(model_path, test_loader, device, return_uncertainty=False):
    """
    Evaluate a trained model on the test set.
    Returns a dictionary of metrics.
    """
    # Determine model type from checkpoint or assume uncertainty-aware
    checkpoint = torch.load(model_path, map_location=device)
    # Try to infer model type from state dict keys
    state_dict_keys = set(checkpoint['model_state_dict'].keys())
    is_uncertainty_aware = 'electrical_branch.fc_uncertainty.weight' in state_dict_keys

    if is_uncertainty_aware:
        model = MultiBranchFusionNet(
            seq_length=P.SEQ_LENGTH,
            num_degradation_classes=P.NUM_DEGRADATION_MODES
        )
    else:
        # Fallback to baseline model
        fusion_type = getattr(P, 'FUSION_TYPE', 'concat')
        model = BaselineFusionNet(
            seq_length=P.SEQ_LENGTH,
            num_degradation_classes=P.NUM_DEGRADATION_MODES,
            fusion_type=fusion_type
        )

    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()

    # Initialize lists to store predictions and labels
    all_degradation_labels = []
    all_degradation_preds = []
    all_degradation_probs = []
    all_soh_labels = []
    all_soh_preds = []
    all_soh_vars = []  # For uncertainty-aware models

    with torch.no_grad():
        for batch in test_loader:
            elec_batch, ultra_batch, thermal_batch, degradation_batch, soh_batch = batch
            elec_batch = elec_batch.to(device)
            ultra_batch = ultra_batch.to(device)
            thermal_batch = thermal_batch.to(device)
            degradation_batch = degradation_batch.to(device)
            soh_batch = soh_batch.to(device).unsqueeze(1)

            outputs = model(elec_batch, ultra_batch, thermal_batch)
            probs = torch.softmax(outputs['degradation_logits'], dim=1)
            _, predicted = torch.max(outputs['degradation_logits'], 1)

            all_degradation_labels.extend(degradation_batch.cpu().numpy())
            all_degradation_preds.extend(predicted.cpu().numpy())
            all_degradation_probs.extend(probs.cpu().numpy())
            all_soh_labels.extend(soh_batch.cpu().numpy().flatten())

            if is_uncertainty_aware:
                all_soh_preds.extend(outputs['soh_mean'].cpu().numpy().flatten())
                all_soh_vars.extend(outputs['soh_var'].cpu().numpy().flatten())
            else:
                all_soh_preds.extend(outputs['soh'].cpu().numpy().flatten())

    # Classification metrics
    target_names = ['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition', 'gas_generation', 'internal_short']
    clf_report = classification_report(all_degradation_labels, all_degradation_preds, target_names=target_names, output_dict=True)
    cm = confusion_matrix(all_degradation_labels, all_degradation_preds)

    # ROC-AUC (one-vs-rest)
    try:
        roc_auc = roc_auc_score(all_degradation_labels, all_degradation_probs, multi_class='ovr')
    except Exception as e:
        roc_auc = None
        print(f"ROC-AUC calculation failed: {e}")

    # Regression metrics
    soh_mse = np.mean((np.array(all_soh_labels) - np.array(all_soh_preds)) ** 2)
    soh_rmse = np.sqrt(soh_mse)
    soh_mae = np.mean(np.abs(np.array(all_soh_labels) - np.array(all_soh_preds)))

    results = {
        'classification_report': clf_report,
        'confusion_matrix': cm.tolist(),
        'roc_auc': roc_auc,
        'soh_mse': soh_mse,
        'soh_rmse': soh_rmse,
        'soh_mae': soh_mae,
        'is_uncertainty_aware': is_uncertainty_aware
    }

    # Add uncertainty-specific metrics if applicable
    if is_uncertainty_aware and return_uncertainty:
        mean_var = np.mean(all_soh_vars)
        results['mean_predictive_variance'] = mean_var
        if mean_var > 0:
            results['uncertainty_ratio'] = soh_mse / mean_var  # Ideal ~1.0
        else:
            results['uncertainty_ratio'] = None

    return results


def run_evaluation(model_path='best_model.pth'):
    """
    Run evaluation using the test set generated in the same way as in training.
    """
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Generate test dataset (same as in training)
    db = CellDatabase()
    X_electrical, X_ultrasonic, X_thermal, y_degradation, y_soh = db.generate_labeled_dataset(
        num_samples=1000, soc_range=(0.0, 1.0)  # smaller set for quick evaluation
    )

    # Convert to tensors and reshape
    X_electrical = np.array(X_electrical, dtype=np.float32).reshape(-1, 1, P.SEQ_LENGTH)
    X_ultrasonic = np.array(X_ultrasonic, dtype=np.float32).reshape(-1, 1, P.SEQ_LENGTH)
    X_thermal = np.array(X_thermal, dtype=np.float32).reshape(-1, 1, P.SEQ_LENGTH)
    y_degradation = np.array(y_degradation, dtype=np.long)
    y_soh = np.array(y_soh, dtype=np.float32)

    # Create TensorDataset and DataLoader
    test_dataset = torch.utils.data.TensorDataset(
        torch.from_numpy(X_electrical),
        torch.from_numpy(X_ultrasonic),
        torch.from_numpy(X_thermal),
        torch.from_numpy(y_degradation),
        torch.from_numpy(y_soh)
    )
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=P.BATCH_SIZE, shuffle=False)

    # Evaluate
    results = evaluate_model(model_path, test_loader, device, return_uncertainty=True)

    # Print results
    print("\n=== Evaluation Results ===")
    print(f"Model Type: {'Uncertainty-Aware Fusion' if results['is_uncertainty_aware'] else 'Baseline Fusion'}")
    print(f"ROC-AUC: {results['roc_auc']:.4f}" if results['roc_auc'] is not None else "ROC-AUC: Failed")
    print(f"SOH MSE: {results['soh_mse']:.4f}")
    print(f"SOH RMSE: {results['soh_rmse']:.4f}")
    print(f"SOH MAE: {results['soh_mae']:.4f}")

    if results['is_uncertainty_aware']:
        if 'mean_predictive_variance' in results:
            print(f"Mean Predictive Variance: {results['mean_predictive_variance']:.4f}")
        if 'uncertainty_ratio' in results and results['uncertainty_ratio'] is not None:
            print(f"Uncertainty Ratio (MSE/MeanVar): {results['uncertainty_ratio']:.4f}")
            print("(Ideal value close to 1.0 indicates well-calibrated uncertainty)")

    print("\nClassification Report:")
    for key, value in results['classification_report'].items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v:.4f}" if isinstance(v, float) else f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")

    return results


if __name__ == "__main__":
    run_evaluation()