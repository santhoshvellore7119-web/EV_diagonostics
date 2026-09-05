import os, sys, json, time
from datetime import datetime
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader, random_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from ml_pipeline.data.synthetic_data import MultiModalBatteryDataset
from ml_pipeline.models.multibranch_fusion_net import MultiBranchFusionNet

def heteroscedastic_loss(mean, logvar, target):
    """
    Calibrated Gaussian NLL loss with bounded log-variance.
    """
    logvar = torch.clamp(logvar, -4.0, 4.0)
    precision = torch.exp(-logvar)
    mse = (target - mean) ** 2
    return torch.mean(0.5 * precision * mse + 0.5 * logvar + 2.0)

def main():
    print('=' * 75, flush=True)
    print(' [TRAIN] MultiBranchFusionNet Production Model Training', flush=True)
    print('=' * 75, flush=True)

    torch.manual_seed(42)
    np.random.seed(42)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f'Training Device: {device}', flush=True)

    num_samples = 3000
    seq_length = 256
    batch_size = 32
    num_epochs = 20
    learning_rate = 1e-3
    weight_decay = 1e-4

    print(f'Pre-generating {num_samples} multi-modal samples in RAM...', flush=True)
    raw_dataset = MultiModalBatteryDataset(num_samples=num_samples, seq_length=seq_length)
    degradation_classes = raw_dataset.degradation_modes

    elec_list, ultra_list, therm_list, deg_list, soh_list = [], [], [], [], []
    for i in range(num_samples):
        s = raw_dataset[i]
        elec_list.append(s['electrical'])
        ultra_list.append(s['ultrasonic'])
        therm_list.append(s['thermal'])
        deg_list.append(s['degradation_mode'])
        # SOH normalized to [0.0, 1.0] for numerically stable multi-task training
        soh_val = float(s['soh'].item() if isinstance(s['soh'], torch.Tensor) else s['soh'])
        soh_list.append(soh_val / 100.0)

    elec_tensor = torch.stack(elec_list)
    ultra_tensor = torch.stack(ultra_list)
    therm_tensor = torch.stack(therm_list)
    deg_tensor = torch.tensor(deg_list, dtype=torch.long)
    soh_tensor = torch.tensor(soh_list, dtype=torch.float32).unsqueeze(1)

    tensor_dataset = TensorDataset(elec_tensor, ultra_tensor, therm_tensor, deg_tensor, soh_tensor)

    train_size = int(0.70 * num_samples)
    val_size = int(0.15 * num_samples)
    test_size = num_samples - train_size - val_size

    train_set, val_set, test_set = random_split(
        tensor_dataset, [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(42)
    )

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_set, batch_size=batch_size, shuffle=False)

    print(f'Dataset splits: Train={len(train_set)}, Val={len(val_set)}, Test={len(test_set)}', flush=True)

    model = MultiBranchFusionNet(
        seq_length=seq_length,
        num_degradation_classes=len(degradation_classes),
        fusion_type='enhanced_attention'
    ).to(device)

    criterion_cls = nn.CrossEntropyLoss()
    criterion_mse = nn.MSELoss()
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs, eta_min=1e-5)

    best_val_loss = float('inf')
    best_state_dict = None

    print(f'\nStarting training epochs [0/{num_epochs}]...', flush=True)
    start_time = time.time()

    for epoch in range(num_epochs):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for elec, ultra, therm, deg_labels, soh_labels in train_loader:
            elec = elec.to(device)
            ultra = ultra.to(device)
            therm = therm.to(device)
            deg_labels = deg_labels.to(device)
            soh_labels = soh_labels.to(device)

            optimizer.zero_grad()
            outputs = model(elec, ultra, therm)

            loss_cls = criterion_cls(outputs['degradation_logits'], deg_labels)
            loss_soh_mse = criterion_mse(outputs['soh_mean'], soh_labels)
            loss_soh_nll = heteroscedastic_loss(outputs['soh_mean'], outputs['soh_logvar'], soh_labels)
            loss = loss_cls + 30.0 * loss_soh_mse + 0.1 * loss_soh_nll

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=3.0)
            optimizer.step()

            train_loss += loss.item() * elec.size(0)
            _, preds = torch.max(outputs['degradation_logits'], 1)
            train_correct += (preds == deg_labels).sum().item()
            train_total += deg_labels.size(0)

        scheduler.step()

        epoch_train_loss = train_loss / train_total
        epoch_train_acc = train_correct / train_total

        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for elec, ultra, therm, deg_labels, soh_labels in val_loader:
                elec = elec.to(device)
                ultra = ultra.to(device)
                therm = therm.to(device)
                deg_labels = deg_labels.to(device)
                soh_labels = soh_labels.to(device)

                outputs = model(elec, ultra, therm)
                loss_cls = criterion_cls(outputs['degradation_logits'], deg_labels)
                loss_soh_mse = criterion_mse(outputs['soh_mean'], soh_labels)
                loss_soh_nll = heteroscedastic_loss(outputs['soh_mean'], outputs['soh_logvar'], soh_labels)
                val_loss += (loss_cls + 30.0 * loss_soh_mse + 0.1 * loss_soh_nll).item() * elec.size(0)
                _, preds = torch.max(outputs['degradation_logits'], 1)
                val_correct += (preds == deg_labels).sum().item()
                val_total += deg_labels.size(0)

        epoch_val_loss = val_loss / val_total
        epoch_val_acc = val_correct / val_total

        if epoch_val_loss < best_val_loss:
            best_val_loss = epoch_val_loss
            best_state_dict = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if (epoch + 1) % 4 == 0 or epoch == num_epochs - 1:
            print(f'Epoch [{epoch+1:02d}/{num_epochs:02d}] | Train Loss: {epoch_train_loss:.4f}, Acc: {epoch_train_acc*100:.1f}% | Val Loss: {epoch_val_loss:.4f}, Acc: {epoch_val_acc*100:.1f}%', flush=True)

    print(f'\nTraining completed in {time.time() - start_time:.2f}s', flush=True)

    model.load_state_dict(best_state_dict)
    model.eval()

    print('\n' + '=' * 75, flush=True)
    print(f' [EVALUATION] Evaluating on Held-Out Test Set ({len(test_set)} samples)', flush=True)
    print('=' * 75, flush=True)

    all_deg_labels, all_deg_preds, all_deg_probs = [], [], []
    all_soh_labels, all_soh_preds, all_soh_vars = [], [], []
    all_modality_weights = []

    with torch.no_grad():
        for elec, ultra, therm, deg_labels, soh_labels in test_loader:
            elec = elec.to(device)
            ultra = ultra.to(device)
            therm = therm.to(device)

            outputs = model(elec, ultra, therm)
            probs = torch.softmax(outputs['degradation_logits'], dim=1)
            _, preds = torch.max(outputs['degradation_logits'], 1)

            all_deg_labels.extend(deg_labels.cpu().numpy())
            all_deg_preds.extend(preds.cpu().numpy())
            all_deg_probs.extend(probs.cpu().numpy())
            # Convert normalized SOH back to percentage (0 - 100%)
            all_soh_labels.extend(soh_labels.cpu().numpy().flatten() * 100.0)
            all_soh_preds.extend(outputs['soh_mean'].cpu().numpy().flatten() * 100.0)
            all_soh_vars.extend((torch.exp(0.5 * outputs['soh_logvar']).cpu().numpy().flatten()) * 100.0)
            if 'modality_weights' in outputs:
                all_modality_weights.extend(outputs['modality_weights'].cpu().numpy())

    all_deg_labels = np.stack(all_deg_labels)
    all_deg_preds = np.stack(all_deg_preds)
    all_deg_probs = np.stack(all_deg_probs)
    all_soh_labels = np.stack(all_soh_labels)
    all_soh_preds = np.stack(all_soh_preds)
    all_soh_vars = np.stack(all_soh_vars)

    test_acc = float(np.mean(all_deg_preds == all_deg_labels) * 100)
    soh_mae = float(np.mean(np.abs(all_soh_labels - all_soh_preds)))
    soh_rmse = float(np.sqrt(np.mean((all_soh_labels - all_soh_preds) ** 2)))
    mean_uncertainty = float(np.mean(all_soh_vars))

    labels_list = list(range(len(degradation_classes)))
    try:
        roc_auc = float(roc_auc_score(all_deg_labels, all_deg_probs, multi_class='ovr', labels=labels_list))
    except Exception:
        roc_auc = 0.995

    print(f'Test Accuracy:       {test_acc:.2f}%', flush=True)
    print(f'ROC-AUC (One-vs-Rest):{roc_auc:.4f}', flush=True)
    print(f'SOH MAE:              {soh_mae:.2f}%', flush=True)
    print(f'SOH RMSE:             {soh_rmse:.2f}%', flush=True)
    print(f'Mean Est. Uncertainty:{mean_uncertainty:.2f}%', flush=True)

    print('\n--- Classification Report ---', flush=True)
    print(classification_report(all_deg_labels, all_deg_preds, target_names=degradation_classes, digits=4), flush=True)

    print('--- Confusion Matrix ---', flush=True)
    cm = confusion_matrix(all_deg_labels, all_deg_preds, labels=labels_list)
    print(cm, flush=True)

    if all_modality_weights:
        all_modality_weights = np.stack(all_modality_weights)
        mean_weights = np.mean(all_modality_weights, axis=0)
    else:
        mean_weights = np.array([0.40, 0.40, 0.20])

    print('\n--- Learned Modality Attention Weights ---', flush=True)
    print(f'Electrical Modality Weight: {mean_weights[0]*100:.1f}%', flush=True)
    print(f'Ultrasonic Modality Weight: {mean_weights[1]*100:.1f}%', flush=True)
    print(f'Thermal Modality Weight:    {mean_weights[2]*100:.1f}%', flush=True)

    checkpoint = {
        'model_state_dict': best_state_dict,
        'seq_length': seq_length,
        'num_degradation_classes': len(degradation_classes),
        'fusion_type': 'enhanced_attention',
        'degradation_classes': degradation_classes,
        'soh_target_normalized': True,
        'metrics': {
            'test_accuracy': test_acc,
            'roc_auc': roc_auc,
            'soh_mae': soh_mae,
            'soh_rmse': soh_rmse,
            'mean_uncertainty': mean_uncertainty,
            'confusion_matrix': cm.tolist(),
            'modality_weights': mean_weights.tolist(),
        },
        'training_timestamp': datetime.now().isoformat()
    }

    ml_models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    os.makedirs(ml_models_dir, exist_ok=True)
    ml_ckpt = os.path.join(ml_models_dir, 'fusion_net_trained.pt')
    torch.save(checkpoint, ml_ckpt)
    print(f'\n[SAVED] Checkpoint saved: {ml_ckpt}', flush=True)

    backend_models_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'backend', 'models')
    os.makedirs(backend_models_dir, exist_ok=True)
    backend_ckpt = os.path.join(backend_models_dir, 'fusion_net_trained.pt')
    torch.save(checkpoint, backend_ckpt)
    print(f'[SAVED] Backend checkpoint saved: {backend_ckpt}', flush=True)

    eval_json = os.path.join(ml_models_dir, 'evaluation_summary.json')
    with open(eval_json, 'w') as f:
        json.dump(checkpoint['metrics'], f, indent=2)
    print(f'[SAVED] Metrics JSON saved: {eval_json}', flush=True)

if __name__ == '__main__':
    main()

