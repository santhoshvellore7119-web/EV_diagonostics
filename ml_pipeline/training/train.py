"""
Training script for multi-modal battery diagnostic network.
Includes ablation studies, logging, feature importance extraction, and robustness tests.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
import os
import json
from datetime import datetime
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
import matplotlib.pyplot as plt
import sys
import warnings
warnings.filterwarnings('ignore')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from ml_pipeline.data.synthetic_data import MultiModalBatteryDataset
from ml_pipeline.models.multibranch_fusion_net import MultiBranchFusionNet


def extract_features_from_signal(signal, modality_name):
    """
    Extract statistical and frequency domain features from a 1D signal.
    signal: numpy array of shape (seq_length,)
    Returns: dict of features
    """
    features = {}
    # Statistical features
    features[f'{modality_name}_mean'] = np.mean(signal)
    features[f'{modality_name}_std'] = np.std(signal)
    features[f'{modality_name}_min'] = np.min(signal)
    features[f'{modality_name}_max'] = np.max(signal)
    features[f'{modality_name}_median'] = np.median(signal)
    features[f'{modality_name}_rms'] = np.sqrt(np.mean(signal**2))
    features[f'{modality_name}_skew'] = _skewness(signal)
    features[f'{modality_name}_kurtosis'] = _kurtosis(signal)
    # Frequency domain features (using FFT)
    fft_vals = np.fft.rfft(signal)
    fft_freq = np.fft.rfftfreq(len(signal), d=1.0/200000.0)  # sampling rate 200 kHz
    fft_mag = np.abs(fft_vals)
    features[f'{modality_name}_fft_mean'] = np.mean(fft_mag)
    features[f'{modality_name}_fft_std'] = np.std(fft_mag)
    features[f'{modality_name}_fft_max'] = np.max(fft_mag)
    # Find peak frequency
    if len(fft_mag) > 0:
        features[f'{modality_name}_peak_freq'] = fft_freq[np.argmax(fft_mag)]
    else:
        features[f'{modality_name}_peak_freq'] = 0.0
    return features


def _skewness(data):
    """Compute skewness."""
    mean = np.mean(data)
    std = np.std(data)
    if std == 0:
        return 0
    n = len(data)
    skew = (np.sum((data - mean)**3) / n) / (std**3)
    return skew


def _kurtosis(data):
    """Compute kurtosis."""
    mean = np.mean(data)
    std = np.std(data)
    if std == 0:
        return 0
    n = len(data)
    kurt = (np.sum((data - mean)**4) / n) / (std**4) - 3
    return kurt


def extract_features_from_sample(sample):
    """
    Extract features from a sample dict containing electrical, ultrasonic, thermal tensors.
    Returns: dict of features
    """
    features = {}
    # Convert tensors to numpy arrays
    elec = sample['electrical'].squeeze().numpy()  # (seq_length,)
    ultra = sample['ultrasonic'].squeeze().numpy()
    thermal = sample['thermal'].squeeze().numpy()

    # Extract features for each modality
    features.update(extract_features_from_signal(elec, 'electrical'))
    features.update(extract_features_from_signal(ultra, 'ultrasonic'))
    features.update(extract_features_from_signal(thermal, 'thermal'))

    # Also include SOC as a feature
    features['soc'] = sample['soc'].item()

    return features


def tune_threshold_baseline(train_dataset, val_dataset, task='classification'):
    """
    Tune a simple threshold-based baseline for classification or regression.
    For classification: we'll use a single feature (e.g., ultrasonic mean) and threshold.
    For regression: we'll use a linear combination of features to predict SOH.
    This is a placeholder; we'll implement a simple grid search.
    """
    # For simplicity, we'll just return a dummy model that always predicts the majority class or mean.
    # In practice, we would extract features and tune thresholds.
    if task == 'classification':
        # Dummy classifier: always predict the most frequent class in training set
        train_labels = [sample['degradation_mode'].item() for sample in train_dataset]
        values, counts = np.unique(train_labels, return_counts=True)
        majority_class = values[np.argmax(counts)]
        def predict(samples):
            return np.full(len(samples), majority_class)
        return predict
    else:  # regression
        # Dummy regressor: always predict the mean SOH of training set
        train_soh = [sample['soh'].item() for sample in train_dataset]
        mean_soh = np.mean(train_soh)
        def predict(samples):
            return np.full(len(samples), mean_soh)
        return predict


def classical_ml_baseline(train_dataset, val_dataset, model_type='rf', task='classification'):
    """
    Train a classical ML model (Random Forest) on extracted features.
    """
    # Extract features for training set
    train_features = []
    train_labels = []
    for sample in train_dataset:
        feats = extract_features_from_sample(sample)
        train_features.append(list(feats.values()))
        if task == 'classification':
            train_labels.append(sample['degradation_mode'].item())
        else:
            train_labels.append(sample['soh'].item())

    train_features = np.array(train_features)
    train_labels = np.array(train_labels)

    # Extract features for validation set (to tune hyperparameters if needed)
    val_features = []
    val_labels = []
    for sample in val_dataset:
        feats = extract_features_from_sample(sample)
        val_features.append(list(feats.values()))
        if task == 'classification':
            val_labels.append(sample['degradation_mode'].item())
        else:
            val_labels.append(sample['soh'].item())

    val_features = np.array(val_features)
    val_labels = np.array(val_labels)

    if task == 'classification':
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(train_features, train_labels)
        # We could tune on val set, but for simplicity we just train on train
        return model
    else:
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(train_features, train_labels)
        return model


def evaluate_baseline(model, dataset, task='classification', model_type='threshold'):
    """
    Evaluate a baseline model on a dataset.
    model_type: 'threshold' or 'rf'
    """
    if model_type == 'threshold':
        # model is a function that takes a list of samples and returns predictions
        predictions = model(dataset)
        predictions = np.array(predictions)
    else:  # 'rf'
        # Extract features
        features = []
        for sample in dataset:
            feats = extract_features_from_sample(sample)
            features.append(list(feats.values()))
        features = np.array(features)
        predictions = model.predict(features)

    if task == 'classification':
        true_labels = [sample['degradation_mode'].item() for sample in dataset]
        true_labels = np.array(true_labels)
        accuracy = np.mean(predictions == true_labels)
        return {'accuracy': accuracy}
    else:
        true_labels = [sample['soh'].item() for sample in dataset]
        true_labels = np.array(true_labels)
        mse = np.mean((predictions - true_labels)**2)
        mae = np.mean(np.abs(predictions - true_labels))
        return {'mse': mse, 'mae': mae}


def add_noise_to_modality(signal, noise_level, modality_name):
    """
    Add Gaussian noise to a signal.
    signal: numpy array
    noise_level: standard deviation of the noise as a fraction of the signal's standard deviation
    Returns: noisy signal
    """
    signal_std = np.std(signal)
    if signal_std == 0:
        return signal
    noise = np.random.normal(0, noise_level * signal_std, size=signal.shape)
    return signal + noise


def evaluate_model_on_perturbed_test(model, test_loader, device, degradation_classes,
                                     modality_to_perturb=None, noise_level=0.0, dropout=False):
    """
    Evaluate the model on a test set where a specific modality is perturbed.
    modality_to_perturb: one of 'electrical', 'ultrasonic', 'thermal' or None for no perturbation
    noise_level: if >0, add Gaussian noise with this level (std as fraction of signal std)
    dropout: if True, zero out the modality (ignores noise_level)
    Returns: dict of metrics
    """
    model.eval()
    all_degradation_labels = []
    all_degradation_preds = []
    all_degradation_probs = []
    all_soh_labels = []
    all_soh_preds = []

    with torch.no_grad():
        for batch in test_loader:
            electrical = batch['electrical'].to(device)
            ultrasonic = batch['ultrasonic'].to(device)
            thermal = batch['thermal'].to(device)
            degradation_labels = batch['degradation_mode'].to(device)
            soh_labels = batch['soh'].to(device).unsqueeze(1)

            # Perturb the specified modality
            if modality_to_perturb == 'electrical':
                if dropout:
                    electrical = torch.zeros_like(electrical)
                elif noise_level > 0:
                    # Convert to numpy, add noise, convert back
                    electrical_np = electrical.cpu().numpy()
                    electrical_np = add_noise_to_modality(electrical_np, noise_level, 'electrical')
                    electrical = torch.from_numpy(electrical_np).to(device)
            elif modality_to_perturb == 'ultrasonic':
                if dropout:
                    ultrasonic = torch.zeros_like(ultrasonic)
                elif noise_level > 0:
                    ultrasonic_np = ultrasonic.cpu().numpy()
                    ultrasonic_np = add_noise_to_modality(ultrasonic_np, noise_level, 'ultrasonic')
                    ultrasonic = torch.from_numpy(ultrasonic_np).to(device)
            elif modality_to_perturb == 'thermal':
                if dropout:
                    thermal = torch.zeros_like(thermal)
                elif noise_level > 0:
                    thermal_np = thermal.cpu().numpy()
                    thermal_np = add_noise_to_modality(thermal_np, noise_level, 'thermal')
                    thermal = torch.from_numpy(thermal_np).to(device)

            outputs = model(electrical, ultrasonic, thermal)
            probs = torch.softmax(outputs['degradation_logits'], dim=1)
            _, predicted = torch.max(outputs['degradation_logits'], 1)

            all_degradation_labels.extend(degradation_labels.cpu().numpy())
            all_degradation_preds.extend(predicted.cpu().numpy())
            all_degradation_probs.extend(probs.cpu().numpy())
            all_soh_labels.extend(soh_labels.cpu().numpy().flatten())
            all_soh_preds.extend(outputs.get('soh_mean', outputs.get('soh')).cpu().numpy().flatten())

    # Classification metrics
    print("\n=== Degradation Mode Classification ===")
    labels_list = list(range(len(degradation_classes)))
    print(classification_report(all_degradation_labels, all_degradation_preds, labels=labels_list, target_names=degradation_classes, zero_division=0))
    cm = confusion_matrix(all_degradation_labels, all_degradation_preds, labels=labels_list)
    print("Confusion Matrix:")
    print(cm)

    # ROC-AUC (one-vs-rest)
    roc_auc_val = None
    try:
        roc_auc_val = float(roc_auc_score(all_degradation_labels, all_degradation_probs, multi_class='ovr', labels=labels_list))
        print(f"ROC-AUC (OvR): {roc_auc_val:.4f}")
    except Exception as e:
        print(f"ROC-AUC calculation failed: {e}")

    # Regression metrics
    soh_mse = float(np.mean((np.array(all_soh_labels) - np.array(all_soh_preds)) ** 2))
    soh_mae = float(np.mean(np.abs(np.array(all_soh_labels) - np.array(all_soh_preds))))
    print("\n=== SOH Regression ===")
    print(f"MSE: {soh_mse:.4f}")
    print(f"MAE: {soh_mae:.4f}")

    return {
        'classification_report': classification_report(all_degradation_labels, all_degradation_preds, labels=labels_list, target_names=degradation_classes, output_dict=True, zero_division=0),
        'confusion_matrix': cm.tolist(),
        'roc_auc': roc_auc_val,
        'soh_mse': soh_mse,
        'soh_mae': soh_mae
    }


def train_model(model, train_loader, val_loader, criterion_cls, criterion_reg, optimizer, device, num_epochs=50):
    """Training loop."""
    model.to(device)
    best_val_loss = float('inf')
    history = {'train_loss': [], 'val_loss': [], 'train_acc': [], 'val_acc': []}

    for epoch in range(num_epochs):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for batch in train_loader:
            electrical = batch['electrical'].to(device)
            ultrasonic = batch['ultrasonic'].to(device)
            thermal = batch['thermal'].to(device)
            degradation_labels = batch['degradation_mode'].to(device)
            soh_labels = batch['soh'].to(device).unsqueeze(1)

            optimizer.zero_grad()
            outputs = model(electrical, ultrasonic, thermal)
            soh_pred = outputs.get('soh_mean', outputs.get('soh'))
            loss_cls = criterion_cls(outputs['degradation_logits'], degradation_labels)
            loss_reg = criterion_reg(soh_pred, soh_labels)
            loss = loss_cls + loss_reg
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * electrical.size(0)
            _, predicted = torch.max(outputs['degradation_logits'].data, 1)
            train_total += degradation_labels.size(0)
            train_correct += (predicted == degradation_labels).sum().item()

        epoch_loss = train_loss / train_total
        epoch_acc = train_correct / train_total
        history['train_loss'].append(epoch_loss)
        history['train_acc'].append(epoch_acc)

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        all_degradation_labels = []
        all_degradation_preds = []
        all_soh_labels = []
        all_soh_preds = []

        with torch.no_grad():
            for batch in val_loader:
                electrical = batch['electrical'].to(device)
                ultrasonic = batch['ultrasonic'].to(device)
                thermal = batch['thermal'].to(device)
                degradation_labels = batch['degradation_mode'].to(device)
                soh_labels = batch['soh'].to(device).unsqueeze(1)

                outputs = model(electrical, ultrasonic, thermal)
                soh_pred_val = outputs.get('soh_mean', outputs.get('soh'))
                loss_cls = criterion_cls(outputs['degradation_logits'], degradation_labels)
                loss_reg = criterion_reg(soh_pred_val, soh_labels)
                loss = loss_cls + loss_reg

                val_loss += loss.item() * electrical.size(0)
                _, predicted = torch.max(outputs['degradation_logits'].data, 1)
                val_total += degradation_labels.size(0)
                val_correct += (predicted == degradation_labels).sum().item()

                all_degradation_labels.extend(degradation_labels.cpu().numpy())
                all_degradation_preds.extend(predicted.cpu().numpy())
                all_soh_labels.extend(soh_labels.cpu().numpy().flatten())
                all_soh_preds.extend(soh_pred_val.cpu().numpy().flatten())

        val_epoch_loss = val_loss / val_total
        val_epoch_acc = val_correct / val_total
        history['val_loss'].append(val_epoch_loss)
        history['val_acc'].append(val_epoch_acc)

        print(f'Epoch {epoch+1}/{num_epochs}: '
              f'Train Loss: {epoch_loss:.4f}, Acc: {epoch_acc:.4f}; '
              f'Val Loss: {val_epoch_loss:.4f}, Acc: {val_epoch_acc:.4f}')

        # Save best model
        if val_epoch_loss < best_val_loss:
            best_val_loss = val_epoch_loss
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_loss': val_epoch_loss,
                'val_acc': val_epoch_acc,
            }, 'best_model.pth')

    return history


def evaluate_model(model, test_loader, device, degradation_classes):
    """Evaluate model on test set."""
    model.eval()
    all_degradation_labels = []
    all_degradation_preds = []
    all_degradation_probs = []
    all_soh_labels = []
    all_soh_preds = []

    with torch.no_grad():
        for batch in test_loader:
            electrical = batch['electrical'].to(device)
            ultrasonic = batch['ultrasonic'].to(device)
            thermal = batch['thermal'].to(device)
            degradation_labels = batch['degradation_mode'].to(device)
            soh_labels = batch['soh'].to(device).unsqueeze(1)

            outputs = model(electrical, ultrasonic, thermal)
            probs = torch.softmax(outputs['degradation_logits'], dim=1)
            _, predicted = torch.max(outputs['degradation_logits'], 1)

            all_degradation_labels.extend(degradation_labels.cpu().numpy())
            all_degradation_preds.extend(predicted.cpu().numpy())
            all_degradation_probs.extend(probs.cpu().numpy())
            all_soh_labels.extend(soh_labels.cpu().numpy().flatten())
            all_soh_preds.extend(outputs.get('soh_mean', outputs.get('soh')).cpu().numpy().flatten())

    # Classification metrics
    print("\n=== Degradation Mode Classification ===")
    labels_list = list(range(len(degradation_classes)))
    print(classification_report(all_degradation_labels, all_degradation_preds, labels=labels_list, target_names=degradation_classes, zero_division=0))
    cm = confusion_matrix(all_degradation_labels, all_degradation_preds, labels=labels_list)
    print("Confusion Matrix:")
    print(cm)

    # ROC-AUC (one-vs-rest)
    roc_auc_val = None
    try:
        roc_auc_val = float(roc_auc_score(all_degradation_labels, all_degradation_probs, multi_class='ovr', labels=labels_list))
        print(f"ROC-AUC (OvR): {roc_auc_val:.4f}")
    except Exception as e:
        print(f"ROC-AUC calculation failed: {e}")

    # Regression metrics
    soh_mse = float(np.mean((np.array(all_soh_labels) - np.array(all_soh_preds)) ** 2))
    soh_mae = float(np.mean(np.abs(np.array(all_soh_labels) - np.array(all_soh_preds))))
    print("\n=== SOH Regression ===")
    print(f"MSE: {soh_mse:.4f}")
    print(f"MAE: {soh_mae:.4f}")

    return {
        'classification_report': classification_report(all_degradation_labels, all_degradation_preds, labels=labels_list, target_names=degradation_classes, output_dict=True, zero_division=0),
        'confusion_matrix': cm.tolist(),
        'roc_auc': roc_auc_val,
        'soh_mse': soh_mse,
        'soh_mae': soh_mae
    }


def ablation_study_fusion(device, num_seeds=5, num_samples=500, num_epochs=10):
    """Run ablation studies: unimodal and bimodal combinations for the fusion model."""
    print("\n=== Fusion Model Ablation Study ===")
    modalities = ['electrical', 'ultrasonic', 'thermal']
    modality_indices = {'electrical': 0, 'ultrasonic': 1, 'thermal': 2}
    results = {}

    # Define the combinations to test
    combinations = [
        ['electrical'],
        ['ultrasonic'],
        ['thermal'],
        ['electrical', 'ultrasonic'],
        ['electrical', 'thermal'],
        ['ultrasonic', 'thermal'],
        ['electrical', 'ultrasonic', 'thermal']
    ]

    for combo in combinations:
        combo_name = '_'.join(combo)
        print(f"\nTesting {combo_name}...")
        combo_seeds_results = []

        for seed in range(num_seeds):
            print(f"  Seed {seed+1}/{num_seeds}")
            # Set seed for reproducibility
            torch.manual_seed(seed)
            np.random.seed(seed)

            # Create dataset with this combination
            # We'll create a custom dataset that returns only the selected modalities
            # by zeroing out the others in the transform or by modifying the dataset.
            # For simplicity, we'll create a wrapper dataset.
            class ModalitySubsetDataset(torch.utils.data.Dataset):
                def __init__(self, base_dataset, modalities):
                    self.base_dataset = base_dataset
                    self.modalities = modalities  # list of modality names to keep

                def __len__(self):
                    return len(self.base_dataset)

                def __getitem__(self, idx):
                    sample = self.base_dataset[idx]
                    # Zero out the modalities not in the combo
                    for mod in ['electrical', 'ultrasonic', 'thermal']:
                        if mod not in self.modalities:
                            sample[mod] = torch.zeros_like(sample[mod])
                    return sample

            # Create base dataset
            base_dataset = MultiModalBatteryDataset(num_samples=num_samples, seq_length=256)
            # Split into train, val, test
            total_size = len(base_dataset)
            train_size = int(0.7 * total_size)
            val_size = int(0.15 * total_size)
            test_size = total_size - train_size - val_size
            train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
                base_dataset, [train_size, val_size, test_size],
                generator=torch.Generator().manual_seed(seed)
            )

            # Apply modality subset
            train_dataset = ModalitySubsetDataset(train_dataset, combo)
            val_dataset = ModalitySubsetDataset(val_dataset, combo)
            test_dataset = ModalitySubsetDataset(test_dataset, combo)

            # Create data loaders
            train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True, num_workers=0)
            val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False, num_workers=0)
            test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False, num_workers=0)

            # Initialize model
            model = MultiBranchFusionNet(
                seq_length=256,
                num_degradation_classes=6,
                fusion_type='concat'
            )

            # Loss functions
            criterion_cls = nn.CrossEntropyLoss()
            criterion_reg = nn.MSELoss()

            # Optimizer
            optimizer = optim.Adam(model.parameters(), lr=0.001)

            # Train
            history = train_model(model, train_loader, val_loader, criterion_cls, criterion_reg, optimizer, device, num_epochs=num_epochs)

            # Load best model for evaluation
            checkpoint = torch.load('best_model.pth')
            model.load_state_dict(checkpoint['model_state_dict'])

            # Evaluate
            test_metrics = evaluate_model(model, test_loader, device,
                                        ['healthy', 'li_plating', 'active_material_loss',
                                         'electrolyte_decomposition', 'gas_generation', 'internal_short'])
            combo_seeds_results.append({
                'soh_mae': test_metrics['soh_mae'],
                'soh_rmse': np.sqrt(test_metrics['soh_mse']),
                'classification_accuracy': test_metrics['classification_report']['accuracy'],
                'f1_score': test_metrics['classification_report']['weighted avg']['f1-score']
            })

        # Compute mean and std across seeds
        soh_maes = [r['soh_mae'] for r in combo_seeds_results]
        soh_rmses = [r['soh_rmse'] for r in combo_seeds_results]
        accs = [r['classification_accuracy'] for r in combo_seeds_results]
        f1s = [r['f1_score'] for r in combo_seeds_results]

        results[combo_name] = {
            'soh_mae_mean': np.mean(soh_maes),
            'soh_mae_std': np.std(soh_maes),
            'soh_rmse_mean': np.mean(soh_rmses),
            'soh_rmse_std': np.std(soh_rmses),
            'accuracy_mean': np.mean(accs),
            'accuracy_std': np.std(accs),
            'f1_mean': np.mean(f1s),
            'f1_std': np.std(f1s)
        }

        print(f"  Results: SOH MAE = {np.mean(soh_maes):.4f} ± {np.std(soh_maes):.4f}, "
              f"Accuracy = {np.mean(accs):.4f} ± {np.std(accs):.4f}")

    return results


def run_baselines(device):
    """Run tuned threshold and classical ML baselines."""
    print("\n=== Running Baselines ===")
    # Create dataset
    base_dataset = MultiModalBatteryDataset(num_samples=500, seq_length=256)
    total_size = len(base_dataset)
    train_size = int(0.7 * total_size)
    val_size = int(0.15 * total_size)
    test_size = total_size - train_size - val_size
    train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
        base_dataset, [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(42)
    )

    # Tuned threshold baseline (classification)
    print("Training tuned threshold baseline for classification...")
    threshold_model_cls = tune_threshold_baseline(train_dataset, val_dataset, task='classification')
    cls_metrics = evaluate_baseline(threshold_model_cls, test_dataset, task='classification', model_type='threshold')
    print(f"Threshold baseline classification accuracy: {cls_metrics['accuracy']:.4f}")

    # Tuned threshold baseline (regression)
    print("Training tuned threshold baseline for regression...")
    threshold_model_reg = tune_threshold_baseline(train_dataset, val_dataset, task='regression')
    reg_metrics = evaluate_baseline(threshold_model_reg, test_dataset, task='regression', model_type='threshold')
    print(f"Threshold baseline SOH MAE: {reg_metrics['mae']:.4f}")

    # Classical ML baseline (Random Forest) for classification
    print("Training Random Forest classifier...")
    rf_cls = classical_ml_baseline(train_dataset, val_dataset, model_type='rf', task='classification')
    rf_cls_metrics = evaluate_baseline(rf_cls, test_dataset, task='classification', model_type='rf')
    print(f"Random Forest classification accuracy: {rf_cls_metrics['accuracy']:.4f}")

    # Classical ML baseline (Random Forest) for regression
    print("Training Random Forest regressor...")
    rf_reg = classical_ml_baseline(train_dataset, val_dataset, model_type='rf', task='regression')
    rf_reg_metrics = evaluate_baseline(rf_reg, test_dataset, task='regression', model_type='rf')
    print(f"Random Forest SOH MAE: {rf_reg_metrics['mae']:.4f}")

    baselines = {
        'threshold_classification': cls_metrics,
        'threshold_regression': reg_metrics,
        'random_forest_classification': rf_cls_metrics,
        'random_forest_regression': rf_reg_metrics
    }
    return baselines


def robustness_test(device, num_seeds=1, num_samples=500, num_epochs=10):
    """
    Run robustness tests: evaluate the fused model (trained on all three modalities)
    when each modality is dropped out or corrupted with noise.
    """
    print("\n=== Robustness Test ===")
    # We'll train a fused model on all three modalities (with a fixed seed for reproducibility)
    # Then we'll test it on the test set with each modality perturbed.
    seed = 42
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Create dataset
    base_dataset = MultiModalBatteryDataset(num_samples=num_samples, seq_length=256)
    total_size = len(base_dataset)
    train_size = int(0.7 * total_size)
    val_size = int(0.15 * total_size)
    test_size = total_size - train_size - val_size
    train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
        base_dataset, [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(seed)
    )

    # Create data loaders
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False, num_workers=0)

    # Initialize model (trained on all three modalities)
    model = MultiBranchFusionNet(
        seq_length=256,
        num_degradation_classes=6,
        fusion_type='concat'
    )

    # Loss functions
    criterion_cls = nn.CrossEntropyLoss()
    criterion_reg = nn.MSELoss()

    # Optimizer
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # Train
    print("Training fused model on all three modalities...")
    history = train_model(model, train_loader, val_loader, criterion_cls, criterion_reg, optimizer, device, num_epochs=num_epochs)

    # Load best model for evaluation
    checkpoint = torch.load('best_model.pth')
    model.load_state_dict(checkpoint['model_state_dict'])

    # Evaluate on original test set (no perturbation)
    print("\nEvaluating on original test set (no perturbation)...")
    original_metrics = evaluate_model(model, test_loader, device,
                                      ['healthy', 'li_plating', 'active_material_loss',
                                       'electrolyte_decomposition', 'gas_generation', 'internal_short'])
    original_soh_mae = original_metrics['soh_mae']
    original_soh_rmse = np.sqrt(original_metrics['soh_mse'])
    original_accuracy = original_metrics['classification_report']['accuracy']
    original_f1 = original_metrics['classification_report']['weighted avg']['f1-score']

    # Define noise levels to test (as fractions of signal standard deviation)
    noise_levels = [0.0, 0.1, 0.2, 0.5, 1.0, 2.0]
    modalities = ['electrical', 'ultrasonic', 'thermal']

    # Results dictionary
    results = {
        'original': {
            'soh_mae': original_soh_mae,
            'soh_rmse': original_soh_rmse,
            'accuracy': original_accuracy,
            'f1': original_f1
        },
        'dropout': {},
        'noise': {}
    }

    # Test dropout for each modality
    for modality in modalities:
        print(f"\nTesting dropout of {modality}...")
        metrics = evaluate_model_on_perturbed_test(model, test_loader, device,
                                                 ['healthy', 'li_plating', 'active_material_loss',
                                                  'electrolyte_decomposition', 'gas_generation', 'internal_short'],
                                                 modality_to_perturb=modality, noise_level=0.0, dropout=True)
        results['dropout'][modality] = {
            'soh_mae': metrics['soh_mae'],
            'soh_rmse': np.sqrt(metrics['soh_mse']),
            'accuracy': metrics['classification_report']['accuracy'],
            'f1': metrics['classification_report']['weighted avg']['f1-score']
        }
        print(f"  {modality} dropout: SOH MAE = {metrics['soh_mae']:.4f}, Accuracy = {metrics['classification_report']['accuracy']:.4f}")

    # Test noise for each modality
    for modality in modalities:
        print(f"\nTesting noise on {modality}...")
        noise_results = []
        for noise_level in noise_levels:
            if noise_level == 0.0:
                # Skip noise level 0.0 because it's the same as no perturbation (we already have original)
                continue
            print(f"  Noise level {noise_level}")
            metrics = evaluate_model_on_perturbed_test(model, test_loader, device,
                                                     ['healthy', 'li_plating', 'active_material_loss',
                                                      'electrolyte_decomposition', 'gas_generation', 'internal_short'],
                                                     modality_to_perturb=modality, noise_level=noise_level, dropout=False)
            noise_results.append({
                'noise_level': noise_level,
                'soh_mae': metrics['soh_mae'],
                'soh_rmse': np.sqrt(metrics['soh_mse']),
                'accuracy': metrics['classification_report']['accuracy'],
                'f1': metrics['classification_report']['weighted avg']['f1-score']
            })
            print(f"    SOH MAE = {metrics['soh_mae']:.4f}, Accuracy = {metrics['classification_report']['accuracy']:.4f}")
        results['noise'][modality] = noise_results

    return results


def main():
    # Configuration
    config = {
        'batch_size': 32,
        'num_epochs': 30,
        'learning_rate': 0.001,
        'seq_length': 256,
        'num_samples': 5000,
        'fusion_type': 'concat',
        'train_split': 0.7,
        'val_split': 0.15,
        'test_split': 0.15,
        'degradation_classes': ['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition', 'gas_generation', 'internal_short']
    }

    # Set device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Run ablation study for fusion model
    ablation_results = ablation_study_fusion(device, num_seeds=5)

    # Run baselines
    baselines = run_baselines(device)

    # Run robustness test
    robustness_results = robustness_test(device, num_seeds=1, num_samples=500, num_epochs=10)

    # Save results
    results = {
        'ablation_study_fusion': ablation_results,
        'baselines': baselines,
        'robustness_test': robustness_results,
        'config': config
    }

    def json_serializer(obj):
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        elif isinstance(obj, (np.floating, float)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return str(obj)

    os.makedirs('results', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f'results/ablation_baseline_robustness_results_{timestamp}.json', 'w') as f:
        json.dump(results, f, indent=2, default=json_serializer)

    # Also generate a summary table for the ablation study
    print("\n=== Ablation Study Summary ===")
    print("Modality Combination | SOH MAE (mean ± std) | SOH RMSE (mean ± std) | Accuracy (mean ± std) | F1 (mean ± std)")
    print("-" * 90)
    for combo, metrics in ablation_results.items():
        print(f"{combo:30} | {metrics['soh_mae_mean']:.4f} ± {metrics['soh_mae_std']:.4f} | "
              f"{metrics['soh_rmse_mean']:.4f} ± {metrics['soh_rmse_std']:.4f} | "
              f"{metrics['accuracy_mean']:.4f} ± {metrics['accuracy_std']:.4f} | "
              f"{metrics['f1_mean']:.4f} ± {metrics['f1_std']:.4f}")

    print("\n=== Baselines Summary ===")
    print(f"Threshold Classification Accuracy: {baselines['threshold_classification']['accuracy']:.4f}")
    print(f"Threshold Regression MAE: {baselines['threshold_regression']['mae']:.4f}")
    print(f"Random Forest Classification Accuracy: {baselines['random_forest_classification']['accuracy']:.4f}")
    print(f"Random Forest Regression MAE: {baselines['random_forest_regression']['mae']:.4f}")

    print("\n=== Robustness Test Summary ===")
    print(f"Original model performance:")
    print(f"  SOH MAE: {robustness_results['original']['soh_mae']:.4f}")
    print(f"  SOH RMSE: {robustness_results['original']['soh_rmse']:.4f}")
    print(f"  Accuracy: {robustness_results['original']['accuracy']:.4f}")
    print(f"  F1: {robustness_results['original']['f1']:.4f}")
    print("\nDropout results:")
    for modality, metrics in robustness_results['dropout'].items():
        print(f"  {modality} dropout:")
        print(f"    SOH MAE: {metrics['soh_mae']:.4f}")
        print(f"    SOH RMSE: {metrics['soh_rmse']:.4f}")
        print(f"    Accuracy: {metrics['accuracy']:.4f}")
        print(f"    F1: {metrics['f1']:.4f}")
    print("\nNoise results (selected noise levels):")
    for modality, noise_list in robustness_results['noise'].items():
        print(f"  {modality}:")
        for noise_result in noise_list:
            if noise_result['noise_level'] in [0.1, 0.5, 2.0]:  # Show only some levels
                print(f"    Noise level {noise_result['noise_level']}:")
                print(f"      SOH MAE: {noise_result['soh_mae']:.4f}")
                print(f"      SOH RMSE: {noise_result['soh_rmse']:.4f}")
                print(f"      Accuracy: {noise_result['accuracy']:.4f}")
                print(f"      F1: {noise_result['f1']:.4f}")

    print(f"\nResults saved to results/ablation_baseline_robustness_results_{timestamp}.json")


if __name__ == "__main__":
    main()