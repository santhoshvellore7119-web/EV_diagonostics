#!/usr/bin/env python3
"""
EV Battery Diagnostics - ML Pipeline Standalone Runner
=====================================================
Modular CLI tool for training, evaluating, and running ablation studies
on the multi-modal fusion deep learning architecture (Electrical + Ultrasonic + Thermal).

Usage:
  python ml_pipeline/run_ml_pipeline.py --mode fast
  python ml_pipeline/run_ml_pipeline.py --mode train --epochs 20 --samples 2000
  python ml_pipeline/run_ml_pipeline.py --mode evaluate --checkpoint results/best_model.pth
  python ml_pipeline/run_ml_pipeline.py --mode ablation --epochs 5 --samples 500
"""

import os
import sys
import argparse
import json
import time
from datetime import datetime
import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split

from ml_pipeline.data.synthetic_data import MultiModalBatteryDataset
from ml_pipeline.models.multibranch_fusion_net import MultiBranchFusionNet
from ml_pipeline.training.train import train_model, evaluate_model, extract_feature_importance


DEGRADATION_CLASSES = [
    'healthy',
    'li_plating',
    'active_material_loss',
    'electrolyte_decomposition',
    'gas_generation',
    'internal_short'
]


def json_serializer(obj):
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


def run_smoke_test(device):
    """Fast smoke test to verify all pipeline components in under 5 seconds."""
    print("=" * 70)
    print(" [FAST TEST] Running Rapid ML Pipeline Verification")
    print("=" * 70)

    seq_len = 128
    num_samples = 64
    batch_size = 16

    print(f"[*] Initializing Synthetic Multi-Modal Dataset ({num_samples} samples, seq={seq_len})...")
    ds = MultiModalBatteryDataset(num_samples=num_samples, seq_length=seq_len)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True)

    print("[*] Instantiating MultiBranchFusionNet with Cross-Modal Attention...")
    model = MultiBranchFusionNet(
        seq_length=seq_len,
        num_degradation_classes=len(DEGRADATION_CLASSES),
        fusion_type='enhanced_attention'
    ).to(device)

    criterion_cls = nn.CrossEntropyLoss()
    criterion_reg = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3)

    print("[*] Executing forward + backward + optimization pass (2 epochs)...")
    model.train()
    for epoch in range(2):
        running_loss = 0.0
        for batch in loader:
            e = batch['electrical'].to(device)
            u = batch['ultrasonic'].to(device)
            t = batch['thermal'].to(device)
            deg_labels = batch['degradation_mode'].to(device)
            soh_labels = batch['soh'].to(device).unsqueeze(1)

            optimizer.zero_grad()
            out = model(e, u, t)

            loss_cls = criterion_cls(out['degradation_logits'], deg_labels)
            loss_reg = criterion_reg(out['soh_mean'], soh_labels)
            loss = loss_cls + loss_reg
            loss.backward()
            optimizer.step()
            running_loss += loss.item()

        print(f"    Epoch {epoch+1}/2 complete - batch loss: {running_loss/len(loader):.4f}")

    print("[*] Evaluating output shapes and uncertainty estimation:")
    sample_batch = next(iter(loader))
    with torch.no_grad():
        out = model(
            sample_batch['electrical'].to(device),
            sample_batch['ultrasonic'].to(device),
            sample_batch['thermal'].to(device)
        )
    print(f"    - degradation_logits shape: {tuple(out['degradation_logits'].shape)}")
    print(f"    - soh_mean shape:          {tuple(out['soh_mean'].shape)}")
    print(f"    - soh_logvar shape:        {tuple(out['soh_logvar'].shape)}")
    if 'attention_info' in out and out['attention_info']:
        print(f"    - modality_weights shape:  {tuple(out['attention_info']['modality_weights'].shape)}")

    print("\n[OK] ML Pipeline Smoke Test Passed Successfully!")
    return True


def run_training(args, device):
    """Full or custom training loop."""
    print("=" * 70)
    print(" [TRAIN] Multi-Modal Fusion Deep Learning Network")
    print("=" * 70)
    print(f" Device:      {device}")
    print(f" Samples:     {args.samples}")
    print(f" Epochs:      {args.epochs}")
    print(f" Batch Size:  {args.batch_size}")
    print(f" Fusion Type: {args.fusion_type}")
    print(f" LR:          {args.lr}")
    print("-" * 70)

    # 1. Dataset
    print("[*] Generating synthetic multi-modal time-series data...")
    dataset = MultiModalBatteryDataset(num_samples=args.samples, seq_length=args.seq_length)
    
    total = len(dataset)
    n_train = int(0.7 * total)
    n_val = int(0.15 * total)
    n_test = total - n_train - n_val

    train_ds, val_ds, test_ds = random_split(
        dataset, [n_train, n_val, n_test],
        generator=torch.Generator().manual_seed(args.seed)
    )

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False)

    # 2. Model
    model = MultiBranchFusionNet(
        seq_length=args.seq_length,
        num_degradation_classes=len(DEGRADATION_CLASSES),
        fusion_type=args.fusion_type
    ).to(device)

    criterion_cls = nn.CrossEntropyLoss()
    criterion_reg = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)

    # 3. Train
    print("[*] Starting training epochs...")
    t_start = time.time()
    history = train_model(
        model, train_loader, val_loader,
        criterion_cls, criterion_reg, optimizer,
        device, num_epochs=args.epochs
    )
    t_elapsed = time.time() - t_start
    print(f"\n[*] Training completed in {t_elapsed:.2f} seconds.")

    # 4. Evaluation
    print("\n[*] Evaluating on held-out test partition...")
    test_metrics = evaluate_model(model, test_loader, device, DEGRADATION_CLASSES)

    # 5. Feature Importance
    print("\n[*] Extracting feature gradient importance...")
    importance = extract_feature_importance(model, test_loader, device)

    # 6. Save results
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(args.output_dir, f"ml_run_{timestamp}.json")

    results = {
        'timestamp': timestamp,
        'config': vars(args),
        'history': history,
        'test_metrics': test_metrics,
        'feature_importance': {k: v.tolist() for k, v in importance.items()}
    }

    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=json_serializer)

    print(f"\n[OK] Run telemetry exported to: {output_path}")
    return results


def run_ablation(args, device):
    """Runs ablation experiment across individual and combined modalities."""
    print("=" * 70)
    print(" [ABLATION] Multi-Modal Modality Sensitivity Study")
    print("=" * 70)

    modalities = {
        'Electrical Only': {'e': True, 'u': False, 't': False},
        'Ultrasonic Only': {'e': False, 'u': True, 't': False},
        'Thermal Only':    {'e': False, 'u': False, 't': True},
        'Electrical + Ultrasonic': {'e': True, 'u': True, 't': False},
        'Electrical + Thermal':    {'e': True, 'u': False, 't': True},
        'Tri-Modal Fusion (Full)': {'e': True, 'u': True, 't': True},
    }

    results = {}
    print(f"Evaluating {len(modalities)} modality configurations ({args.epochs} epochs each)...")

    dataset = MultiModalBatteryDataset(num_samples=args.samples, seq_length=args.seq_length)
    n_train = int(0.7 * len(dataset))
    n_val = int(0.15 * len(dataset))
    n_test = len(dataset) - n_train - n_val

    train_ds, val_ds, test_ds = random_split(
        dataset, [n_train, n_val, n_test],
        generator=torch.Generator().manual_seed(args.seed)
    )

    for name, mask in modalities.items():
        print(f"\n--- Training Configuration: {name} ---")
        model = MultiBranchFusionNet(
            seq_length=args.seq_length,
            num_degradation_classes=len(DEGRADATION_CLASSES),
            fusion_type='concat'
        ).to(device)

        optimizer = optim.Adam(model.parameters(), lr=args.lr)
        criterion_cls = nn.CrossEntropyLoss()
        criterion_reg = nn.MSELoss()

        train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
        test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False)

        model.train()
        for epoch in range(args.epochs):
            for batch in train_loader:
                e = batch['electrical'].to(device) if mask['e'] else torch.zeros_like(batch['electrical']).to(device)
                u = batch['ultrasonic'].to(device) if mask['u'] else torch.zeros_like(batch['ultrasonic']).to(device)
                t = batch['thermal'].to(device) if mask['t'] else torch.zeros_like(batch['thermal']).to(device)
                
                deg_labels = batch['degradation_mode'].to(device)
                soh_labels = batch['soh'].to(device).unsqueeze(1)

                optimizer.zero_grad()
                out = model(e, u, t)
                loss = criterion_cls(out['degradation_logits'], deg_labels) + criterion_reg(out['soh_mean'], soh_labels)
                loss.backward()
                optimizer.step()

        # Evaluate
        model.eval()
        correct, total = 0, 0
        soh_diffs = []
        with torch.no_grad():
            for batch in test_loader:
                e = batch['electrical'].to(device) if mask['e'] else torch.zeros_like(batch['electrical']).to(device)
                u = batch['ultrasonic'].to(device) if mask['u'] else torch.zeros_like(batch['ultrasonic']).to(device)
                t = batch['thermal'].to(device) if mask['t'] else torch.zeros_like(batch['thermal']).to(device)
                
                deg_labels = batch['degradation_mode'].to(device)
                soh_labels = batch['soh'].to(device).unsqueeze(1)

                out = model(e, u, t)
                _, preds = torch.max(out['degradation_logits'], 1)
                correct += (preds == deg_labels).sum().item()
                total += deg_labels.size(0)
                soh_diffs.extend(torch.abs(out['soh_mean'] - soh_labels).cpu().numpy().flatten())

        acc = correct / total if total > 0 else 0.0
        mae = float(np.mean(soh_diffs))
        results[name] = {'accuracy': acc, 'soh_mae': mae}
        print(f"Result [{name}] -> Classification Accuracy: {acc*100:.2f}%, SOH MAE: {mae:.4f}")

    print("\n" + "=" * 70)
    print(" ABLATION STUDY SUMMARY")
    print("=" * 70)
    print(f"{'Modality Configuration':<30} | {'Degradation Acc':<16} | {'SOH MAE':<10}")
    print("-" * 62)
    for name, m in results.items():
        print(f"{name:<30} | {m['accuracy']*100:>14.2f}% | {m['soh_mae']:>10.4f}")
    print("=" * 70)
    return results


def main():
    parser = argparse.ArgumentParser(description="EV Battery Diagnostics - ML Pipeline CLI")
    parser.add_argument('--mode', type=str, default='fast', choices=['fast', 'train', 'ablation', 'evaluate'],
                        help="Operating mode (default: fast)")
    parser.add_argument('--epochs', type=int, default=10, help="Number of training epochs")
    parser.add_argument('--samples', type=int, default=1000, help="Number of synthetic samples to generate")
    parser.add_argument('--batch-size', type=int, default=32, help="Batch size")
    parser.add_argument('--seq-length', type=int, default=256, help="Sequence length for time-series")
    parser.add_argument('--lr', type=float, default=1e-3, help="Learning rate")
    parser.add_argument('--fusion-type', type=str, default='enhanced_attention',
                        choices=['concat', 'add', 'attention', 'enhanced_attention'],
                        help="Multi-modal fusion architecture")
    parser.add_argument('--seed', type=int, default=42, help="Random seed")
    parser.add_argument('--output-dir', type=str, default='results', help="Directory to save artifacts")
    parser.add_argument('--checkpoint', type=str, default='best_model.pth', help="Checkpoint path for evaluation")

    args = parser.parse_args()

    # Set seeds
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    if args.mode == 'fast':
        run_smoke_test(device)
    elif args.mode == 'train':
        run_training(args, device)
    elif args.mode == 'ablation':
        run_ablation(args, device)
    elif args.mode == 'evaluate':
        if not os.path.exists(args.checkpoint):
            print(f"[!] Checkpoint not found: {args.checkpoint}. Running fast smoke test instead.")
            run_smoke_test(device)
        else:
            print(f"[*] Loading model from {args.checkpoint}...")
            model = MultiBranchFusionNet(
                seq_length=args.seq_length,
                num_degradation_classes=len(DEGRADATION_CLASSES),
                fusion_type=args.fusion_type
            ).to(device)
            ckpt = torch.load(args.checkpoint, map_location=device)
            model.load_state_dict(ckpt['model_state_dict'])
            ds = MultiModalBatteryDataset(num_samples=500, seq_length=args.seq_length)
            loader = DataLoader(ds, batch_size=32, shuffle=False)
            evaluate_model(model, loader, device, DEGRADATION_CLASSES)


if __name__ == '__main__':
    main()
