"""
Ablation and Performance Benchmark Study for Multi-Modal EV Battery Diagnostics.
Systematic empirical evaluation of:
1. Tuned Multi-Threshold BMS Baseline
2. Classical Machine Learning Baseline (Random Forest on 16D Physical Features)
3. Unimodal Models (E-only, U-only, T-only)
4. Bimodal Models (E+U, E+T, U+T)
5. Full Trimodal Fusion Model (E+U+T Teacher: MultiBranchFusionNet)
6. Compact Edge Student Model (EdgeMultiModalNet, 16D input, 5.84 KB int8)
7. Multi-Seed Statistical Validation (5 random seeds: Mean +/- Std)
8. Robustness under Sensor Corruption (0 to 5 sigma noise) and 100% Sensor Dropout
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import accuracy_score, f1_score, mean_squared_error, mean_absolute_error
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ml_pipeline.data.synthetic_data import ContinuousMultiModalBatteryDataset
from ml_pipeline.models.multibranch_fusion_net import MultiBranchFusionNet
from ml_pipeline.models.edge_multimodal_net import EdgeMultiModalNet
from ml_pipeline.models.edge_feature_extractor import extract_16d_features_from_scalars


def evaluate_tuned_bms_baseline(samples: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Tuned multi-threshold industrial BMS rule-based classifier and linear SOH estimator.
    """
    preds = []
    soh_preds = []

    for s in samples:
        r0 = float(s['r0'].item() if isinstance(s['r0'], torch.Tensor) else s['r0'])
        sos = float(s['sos'].item() if isinstance(s['sos'], torch.Tensor) else s['sos'])
        atten = float(s['attenuation'].item() if isinstance(s['attenuation'], torch.Tensor) else s['attenuation'])
        temp_amb = float(s['temp_ambient'].item() if isinstance(s['temp_ambient'], torch.Tensor) else s['temp_ambient'])

        # Multi-dimensional threshold classifier
        if temp_amb > 34.0 or r0 > 0.085:
            pred_idx = 5  # internal short
        elif atten < 0.40 or s.get('gas_reverb', False):
            pred_idx = 4  # gas generation
        elif sos < 2200.0:
            pred_idx = 3  # electrolyte decomposition
        elif r0 > 0.048:
            pred_idx = 2  # active material loss
        elif sos > 2650.0:
            pred_idx = 1  # li plating
        else:
            pred_idx = 0  # healthy

        # Linear heuristic SOH estimator
        est_soh = 100.0 - (r0 - 0.025) * 600.0 - max(0.0, (2450.0 - sos) * 0.04)
        est_soh = float(np.clip(est_soh, 45.0, 100.0))

        preds.append(pred_idx)
        soh_preds.append(est_soh)

    return np.array(preds), np.array(soh_preds)


def extract_features_and_arrays(samples: List[Dict[str, Any]]):
    """Extracts raw tensors and 16D tabular features for benchmarking."""
    X_16d = []
    elecs, ultras, therms, degs, sohs = [], [], [], [], []

    for s in samples:
        soc = float(s['soc'].item() if isinstance(s['soc'], torch.Tensor) else s['soc'])
        r0 = float(s['r0'].item() if isinstance(s['r0'], torch.Tensor) else s['r0'])
        sos = float(s['sos'].item() if isinstance(s['sos'], torch.Tensor) else s['sos'])
        atten = float(s['attenuation'].item() if isinstance(s['attenuation'], torch.Tensor) else s['attenuation'])
        phase = float(s['phase_shift'].item() if isinstance(s['phase_shift'], torch.Tensor) else s['phase_shift'])
        temp = float(s['temp_ambient'].item() if isinstance(s['temp_ambient'], torch.Tensor) else s['temp_ambient'])

        # Convert physical parameters to hardware sensor scalars
        v_bus = 3.0 + 1.2 * soc - 0.5 * r0
        v_shunt = 0.5 * r0
        curr_a = 0.5
        p_w = v_bus * curr_a
        tof_us = (2.0 * 0.010 / max(100.0, sos)) * 1e6

        f16 = extract_16d_features_from_scalars(
            bus_voltage_v=v_bus,
            shunt_voltage_v=v_shunt,
            current_a=curr_a,
            power_w=p_w,
            time_of_flight_us=tof_us,
            amplitude=atten,
            phase_shift=phase,
            temperature_c=temp,
            temp_gradient_c_per_s=0.10
        )
        X_16d.append(f16)
        elecs.append(s['electrical'])
        ultras.append(s['ultrasonic'])
        therms.append(s['thermal'])
        degs.append(int(s['degradation_mode'].item() if isinstance(s['degradation_mode'], torch.Tensor) else s['degradation_mode']))
        sohs.append(float(s['soh'].item() if isinstance(s['soh'], torch.Tensor) else s['soh']))

    return (
        np.array(X_16d, dtype=np.float32),
        torch.stack(elecs),
        torch.stack(ultras),
        torch.stack(therms),
        np.array(degs, dtype=np.int64),
        np.array(sohs, dtype=np.float32)
    )


def run_modality_masked_inference(
    model: nn.Module,
    elecs: torch.Tensor,
    ultras: torch.Tensor,
    therms: torch.Tensor,
    mask_config: str,  # 'E', 'U', 'T', 'E+U', 'E+T', 'U+T', 'E+U+T'
    device: torch.device
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Executes forward pass with unselected modalities masked to neutral baseline.
    """
    e_in = elecs.to(device).clone()
    u_in = ultras.to(device).clone()
    t_in = therms.to(device).clone()

    if 'E' not in mask_config:
        e_in = torch.zeros_like(e_in)
    if 'U' not in mask_config:
        u_in = torch.zeros_like(u_in)
    if 'T' not in mask_config:
        t_in = torch.zeros_like(t_in)

    model.eval()
    with torch.no_grad():
        out = model(e_in, u_in, t_in)
        logits = out['degradation_logits']
        soh = out.get('soh_mean', out.get('soh'))

        preds = torch.argmax(logits, dim=1).cpu().numpy()
        soh_preds = soh.squeeze(-1).cpu().numpy()
        if np.mean(soh_preds) < 2.0:
            soh_preds = soh_preds * 100.0

    return preds, soh_preds


def run_ablation_study(num_seeds: int = 5, num_eval_samples: int = 180) -> Dict[str, Any]:
    print("=" * 90, flush=True)
    print(" [ABLATION STUDY] Multi-Modal EV Battery Diagnostic Model Architecture Benchmarking", flush=True)
    print(f" Validating 7 Modality Configurations across {num_seeds} Random Seeds (N={num_eval_samples})", flush=True)
    print("=" * 90, flush=True)

    device = torch.device('cpu')

    # Load Trained Teacher Model
    teacher_path = os.path.join(project_root, 'ml_pipeline', 'models', 'fusion_net_trained.pt')
    teacher = MultiBranchFusionNet(seq_length=256, num_degradation_classes=6, fusion_type='enhanced_attention')
    if os.path.exists(teacher_path):
        ckpt_t = torch.load(teacher_path, map_location=device)
        teacher.load_state_dict(ckpt_t.get('model_state_dict', ckpt_t))
    teacher.eval()

    # Load Trained Student Model
    student_path = os.path.join(project_root, 'ml_pipeline', 'models', 'edge_model_trained.pt')
    student = EdgeMultiModalNet(in_features=16, hidden_dim1=64, hidden_dim2=48, hidden_dim3=32, num_classes=6)
    if os.path.exists(student_path):
        ckpt_s = torch.load(student_path, map_location=device)
        student.load_state_dict(ckpt_s.get('model_state_dict', ckpt_s))
    student.eval()

    # Define Configurations
    configs = [
        ("Tuned BMS Baseline", "BMS_Rule"),
        ("Random Forest (16D Features)", "RandomForest"),
        ("Electrical Only (E)", "E"),
        ("Ultrasonic Only (U)", "U"),
        ("Thermal Only (T)", "T"),
        ("Bimodal: Electrical + Ultrasonic (E+U)", "E+U"),
        ("Bimodal: Electrical + Thermal (E+T)", "E+T"),
        ("Bimodal: Ultrasonic + Thermal (U+T)", "U+T"),
        ("Full Trimodal Fusion (E+U+T Teacher)", "E+U+T"),
        ("Edge Multi-Modal Student (16D Int8)", "Student_Edge")
    ]

    metrics_per_config = {cfg_name: {'rmse': [], 'mae': [], 'acc': [], 'f1': []} for cfg_name, _ in configs}

    # Evaluate across multiple seeds
    for seed_idx in range(num_seeds):
        curr_seed = 100 + seed_idx * 17
        ds_test = ContinuousMultiModalBatteryDataset(
            num_samples=num_eval_samples,
            seq_length=256,
            split='test_indist',
            seed=curr_seed
        )
        samples = [ds_test[i] for i in range(len(ds_test))]
        X_16d, elecs, ultras, therms, y_true, soh_true = extract_features_and_arrays(samples)

        # Train Random Forest on a separate reference training seed
        ds_train_rf = ContinuousMultiModalBatteryDataset(num_samples=300, seq_length=256, split='train', seed=curr_seed + 1)
        samples_train_rf = [ds_train_rf[i] for i in range(len(ds_train_rf))]
        X_train_rf, _, _, _, y_train_rf, soh_train_rf = extract_features_and_arrays(samples_train_rf)

        rf_cls = RandomForestClassifier(n_estimators=40, max_depth=8, random_state=curr_seed)
        rf_cls.fit(X_train_rf, y_train_rf)
        rf_reg = RandomForestRegressor(n_estimators=40, max_depth=8, random_state=curr_seed)
        rf_reg.fit(X_train_rf, soh_train_rf)

        for cfg_name, cfg_type in configs:
            if cfg_type == "BMS_Rule":
                preds, soh_preds = evaluate_tuned_bms_baseline(samples)
            elif cfg_type == "RandomForest":
                preds = rf_cls.predict(X_16d)
                soh_preds = rf_reg.predict(X_16d)
            elif cfg_type == "Student_Edge":
                with torch.no_grad():
                    out_s = student(torch.from_numpy(X_16d))
                    preds = torch.argmax(out_s['degradation_logits'], dim=1).numpy()
                    soh_preds = out_s['soh'].squeeze(-1).numpy()
                    if np.mean(soh_preds) < 2.0:
                        soh_preds = soh_preds * 100.0
            else:
                preds, soh_preds = run_modality_masked_inference(
                    teacher, elecs, ultras, therms, mask_config=cfg_type, device=device
                )

            acc = accuracy_score(y_true, preds) * 100.0
            f1 = f1_score(y_true, preds, average='macro', zero_division=0) * 100.0
            rmse = float(np.sqrt(mean_squared_error(soh_true, soh_preds)))
            mae = float(mean_absolute_error(soh_true, soh_preds))

            metrics_per_config[cfg_name]['rmse'].append(rmse)
            metrics_per_config[cfg_name]['mae'].append(mae)
            metrics_per_config[cfg_name]['acc'].append(acc)
            metrics_per_config[cfg_name]['f1'].append(f1)

    # Compute Summary Stats (Mean +/- Std)
    summary_results = {}
    print("\n" + "=" * 98, flush=True)
    print(f"{'Architecture / Configuration':<42} | {'SOH RMSE (%)':<16} | {'SOH MAE (%)':<15} | {'Mode Acc (%)':<14} | {'Macro F1 (%)':<12}", flush=True)
    print("-" * 98, flush=True)

    for cfg_name, _ in configs:
        rmses = metrics_per_config[cfg_name]['rmse']
        maes = metrics_per_config[cfg_name]['mae']
        accs = metrics_per_config[cfg_name]['acc']
        f1s = metrics_per_config[cfg_name]['f1']

        rmse_mean, rmse_std = np.mean(rmses), np.std(rmses)
        mae_mean, mae_std = np.mean(maes), np.std(maes)
        acc_mean, acc_std = np.mean(accs), np.std(accs)
        f1_mean, f1_std = np.mean(f1s), np.std(f1s)

        summary_results[cfg_name] = {
            'rmse_mean': float(rmse_mean), 'rmse_std': float(rmse_std),
            'mae_mean': float(mae_mean), 'mae_std': float(mae_std),
            'acc_mean': float(acc_mean), 'acc_std': float(acc_std),
            'f1_mean': float(f1_mean), 'f1_std': float(f1_std)
        }

        rmse_str = f"{rmse_mean:.2f} +/- {rmse_std:.2f}"
        mae_str = f"{mae_mean:.2f} +/- {mae_std:.2f}"
        acc_str = f"{acc_mean:.1f} +/- {acc_std:.1f}"
        f1_str = f"{f1_mean:.1f} +/- {f1_std:.1f}"

        print(f"{cfg_name:<42} | {rmse_str:<16} | {mae_str:<15} | {acc_str:<14} | {f1_str:<12}", flush=True)

    print("=" * 98 + "\n", flush=True)

    # Sensor Robustness Sweep
    print("Evaluating Robustness under Sensor Corruption & Dropout...", flush=True)
    robustness_results = {}
    noise_levels = [0.0, 1.0, 2.0, 3.0, 5.0]
    for n_mult in noise_levels:
        ds_noisy = ContinuousMultiModalBatteryDataset(num_samples=120, seq_length=256, noise_multiplier=n_mult, seed=999)
        samples_noisy = [ds_noisy[i] for i in range(len(ds_noisy))]
        _, e_n, u_n, t_n, y_n, soh_n = extract_features_and_arrays(samples_noisy)
        p_n, s_n = run_modality_masked_inference(teacher, e_n, u_n, t_n, 'E+U+T', device)
        robustness_results[f"noise_{n_mult}x"] = {
            'rmse': float(np.sqrt(mean_squared_error(soh_n, s_n))),
            'acc': float(accuracy_score(y_n, p_n) * 100.0)
        }

    for drop_mod in ['electrical', 'ultrasonic', 'thermal']:
        ds_drop = ContinuousMultiModalBatteryDataset(num_samples=120, seq_length=256, dropout_modality=drop_mod, seed=888)
        samples_drop = [ds_drop[i] for i in range(len(ds_drop))]
        _, e_d, u_d, t_d, y_d, soh_d = extract_features_and_arrays(samples_drop)
        p_d, s_d = run_modality_masked_inference(teacher, e_d, u_d, t_d, 'E+U+T', device)
        robustness_results[f"dropout_{drop_mod}"] = {
            'rmse': float(np.sqrt(mean_squared_error(soh_d, s_d))),
            'acc': float(accuracy_score(y_d, p_d) * 100.0)
        }

    # Save Results
    os.makedirs(os.path.join(project_root, 'results'), exist_ok=True)
    out_json_path = os.path.join(project_root, 'results', 'ablation_benchmark_results.json')
    with open(out_json_path, 'w') as f:
        json.dump({'ablation_matrix': summary_results, 'robustness_curves': robustness_results}, f, indent=2)
    print(f"[OK] Saved comprehensive benchmark results to: {out_json_path}", flush=True)

    return summary_results


if __name__ == '__main__':
    run_ablation_study()
