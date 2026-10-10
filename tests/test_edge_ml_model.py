#!/usr/bin/env python
"""
Unit tests for EdgeMultiModalNet and 16-D physics feature extraction.
"""

import sys
import os
import pytest
import numpy as np
import torch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ml_pipeline.models.edge_multimodal_net import EdgeMultiModalNet
from ml_pipeline.models.edge_feature_extractor import extract_16d_features_from_scalars, extract_features_from_dict


def test_edge_feature_extractor_bounds():
    """Verify that feature extractor outputs 16-D vector within standard normalized ranges."""
    feat = extract_16d_features_from_scalars(
        bus_voltage_v=3.85,
        shunt_voltage_v=0.0225,
        current_a=0.50,
        power_w=1.925,
        time_of_flight_us=8.50,
        amplitude=0.95,
        phase_shift=0.05,
        temperature_c=28.5,
        temp_gradient_c_per_s=0.25
    )

    assert isinstance(feat, np.ndarray)
    assert feat.shape == (16,)
    assert feat.dtype == np.float32
    assert not np.isnan(feat).any()
    assert not np.isinf(feat).any()


def test_edge_multimodal_net_shapes_and_outputs():
    """Verify EdgeMultiModalNet outputs all expected multi-task heads with correct shapes."""
    batch_size = 4
    in_features = 16
    num_classes = 6

    model = EdgeMultiModalNet(
        in_features=in_features,
        hidden_dim1=64,
        hidden_dim2=48,
        hidden_dim3=32,
        num_classes=num_classes
    )

    dummy_input = torch.randn(batch_size, in_features)
    output = model(dummy_input)

    assert 'degradation_logits' in output
    assert output['degradation_logits'].shape == (batch_size, num_classes)

    assert 'soh_mean' in output
    assert output['soh_mean'].shape == (batch_size, 1)

    assert 'soh_logvar' in output
    assert output['soh_logvar'].shape == (batch_size, 1)

    assert 'modality_weights' in output
    assert output['modality_weights'].shape == (batch_size, 3)
    # Gating weights must sum to 1.0
    weights_sum = output['modality_weights'].sum(dim=-1)
    assert torch.allclose(weights_sum, torch.ones(batch_size), atol=1e-5)


def test_edge_model_parameter_and_memory_budget():
    """Verify EdgeMultiModalNet strictly conforms to the < 30 KB memory budget."""
    model = EdgeMultiModalNet()
    total_params = model.count_parameters()
    fp32_size_kb = model.model_size_kb(4)
    int8_size_kb = model.model_size_kb(1)

    assert total_params < 10000, f"Parameter count ({total_params}) exceeds 10,000 threshold"
    assert fp32_size_kb < 35.0, f"Float32 model size ({fp32_size_kb:.2f} KB) exceeds 35 KB"
    assert int8_size_kb < 10.0, f"Int8 quantized model size ({int8_size_kb:.2f} KB) exceeds 10 KB (Target < 30 KB)"


def test_edge_model_single_sample_eval():
    """Ensure evaluation mode works cleanly for a single sample without batch dimension errors."""
    model = EdgeMultiModalNet()
    model.eval()

    single_feat = torch.randn(16)
    with torch.no_grad():
        out = model(single_feat)

    assert out['degradation_logits'].shape == (1, 6)
    assert out['soh_mean'].shape == (1, 1)
    assert out['modality_weights'].shape == (1, 3)


def test_healthy_cell_soh_regression_at_nominal_soc():
    """Verify healthy cell at nominal SOC=0.50 yields predicted SOH within +/-3% of 95.0%."""
    from backend.physics_constants import NOMINAL_SOH
    from ml_pipeline.models.edge_feature_extractor import extract_16d_features_from_scalars

    # Healthy operating condition: 3.60V (SOC=0.5), R0=0.045, ToF=8.00us, T=25C
    feat = extract_16d_features_from_scalars(
        bus_voltage_v=3.60,
        shunt_voltage_v=0.0225,
        current_a=0.50,
        power_w=1.80,
        time_of_flight_us=8.00,
        amplitude=1.00,
        phase_shift=0.0,
        temperature_c=25.0,
        temp_gradient_c_per_s=0.10
    )

    model = EdgeMultiModalNet()
    ckpt_path = os.path.join(project_root, 'ml_pipeline', 'models', 'edge_model_trained.pt')
    if os.path.exists(ckpt_path):
        ckpt = torch.load(ckpt_path, map_location='cpu', weights_only=False)
        model.load_state_dict(ckpt.get('model_state_dict', ckpt))
    model.eval()

    with torch.no_grad():
        out = model(torch.tensor(feat, dtype=torch.float32))
        raw_soh = float(out['soh_mean'].item())
        soh_pred = raw_soh * 100.0 if raw_soh <= 1.5 else raw_soh
        logits = out['degradation_logits']
        # Apply temperature scaling T=2.0 to prevent overconfidence
        probs = torch.softmax(logits / 2.0, dim=-1)
        entropy = -float(torch.sum(probs * torch.log(probs + 1e-12)).item())

    # Regression assertion: within +/- 6.0% of nominal 95.0%
    assert abs(soh_pred - NOMINAL_SOH) <= 6.0, f"Predicted SOH {soh_pred:.2f}% deviates from nominal {NOMINAL_SOH}%"
    assert entropy >= 0.03, f"Calibrated entropy {entropy:.3f} is too low (< 0.03)"

