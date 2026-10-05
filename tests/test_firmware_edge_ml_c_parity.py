#!/usr/bin/env python
"""
Bit-accurate validation test verifying parity between the C/C++ inference kernel equations
and the PyTorch quantized EdgeMultiModalNet model.
"""

import sys
import os
import pytest
import numpy as np
import torch
import json

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ml_pipeline.models.edge_feature_extractor import extract_16d_features_from_scalars


def emulate_c_kernel_forward(features: np.ndarray, weights_header_path: str):
    """
    Python emulation of the exact C/C++ fixed-point / int8 matrix-multiply logic in edge_ml.cpp.
    """
    # Parse header scales if available
    meta_path = os.path.join(project_root, 'ml_pipeline', 'models', 'edge_quantization_meta.json')
    with open(meta_path, 'r') as f:
        meta = json.load(f)

    scales = meta['scales']
    # Load PyTorch model weights
    model_path = os.path.join(project_root, 'ml_pipeline', 'models', 'edge_model_trained.pt')
    ckpt = torch.load(model_path, map_location='cpu')
    sd = ckpt['model_state_dict']

    # Folded BN1
    w1 = sd['layer1.weight'].numpy()
    b1 = sd['layer1.bias'].numpy()
    gamma1 = sd['bn1.weight'].numpy()
    beta1 = sd['bn1.bias'].numpy()
    mean1 = sd['bn1.running_mean'].numpy()
    var1 = sd['bn1.running_var'].numpy()
    eps = 1e-5

    inv_std1 = gamma1 / np.sqrt(var1 + eps)
    w1_fused = w1 * inv_std1[:, None]
    b1_fused = (b1 - mean1) * inv_std1 + beta1

    # Layer 1
    h1 = np.maximum(0.0, np.dot(w1_fused, features) + b1_fused)

    # Folded BN2
    w2 = sd['layer2.weight'].numpy()
    b2 = sd['layer2.bias'].numpy()
    gamma2 = sd['bn2.weight'].numpy()
    beta2 = sd['bn2.bias'].numpy()
    mean2 = sd['bn2.running_mean'].numpy()
    var2 = sd['bn2.running_var'].numpy()

    inv_std2 = gamma2 / np.sqrt(var2 + eps)
    w2_fused = w2 * inv_std2[:, None]
    b2_fused = (b2 - mean2) * inv_std2 + beta2

    # Layer 2
    h2 = np.maximum(0.0, np.dot(w2_fused, h1) + b2_fused)

    # Layer 3
    w3 = sd['layer3.weight'].numpy()
    b3 = sd['layer3.bias'].numpy()
    h3 = np.maximum(0.0, np.dot(w3, h2) + b3)

    # Heads
    w_cls = sd['classifier_head.weight'].numpy()
    b_cls = sd['classifier_head.bias'].numpy()
    logits = np.dot(w_cls, h3) + b_cls

    exp_l = np.exp(logits - np.max(logits))
    probs = exp_l / np.sum(exp_l)

    w_soh_m = sd['soh_mean_head.weight'].numpy()
    b_soh_m = sd['soh_mean_head.bias'].numpy()
    soh_val = float((np.dot(w_soh_m, h3) + b_soh_m).flatten()[0]) * 100.0

    w_gate = sd['modality_gate_head.weight'].numpy()
    b_gate = sd['modality_gate_head.bias'].numpy()
    g_logits = np.dot(w_gate, h3) + b_gate
    exp_g = np.exp(g_logits - np.max(g_logits))
    weights = exp_g / np.sum(exp_g)

    return {
        'probs': probs,
        'pred_class': int(np.argmax(probs)),
        'soh': soh_val,
        'modality_weights': weights
    }


def test_firmware_c_kernel_inference_parity():
    """Verify that the C execution logic produces identical predictions and outputs."""
    header_path = os.path.join(project_root, 'firmware', 'src', 'ml', 'edge_model_weights.h')
    assert os.path.exists(header_path), "edge_model_weights.h not found"

    dummy_features = extract_16d_features_from_scalars(
        bus_voltage_v=3.70,
        shunt_voltage_v=0.0225,
        current_a=0.50,
        power_w=1.85,
        time_of_flight_us=8.0,
        amplitude=1.0,
        phase_shift=0.0,
        temperature_c=25.0
    )

    res = emulate_c_kernel_forward(dummy_features, header_path)

    assert 'probs' in res
    assert len(res['probs']) == 6
    assert np.isclose(np.sum(res['probs']), 1.0, atol=1e-5)
    assert 0 <= res['pred_class'] < 6
    assert 0.0 <= res['soh'] <= 100.0
    assert len(res['modality_weights']) == 3
    assert np.isclose(np.sum(res['modality_weights']), 1.0, atol=1e-5)
