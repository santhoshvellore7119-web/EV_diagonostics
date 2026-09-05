#!/usr/bin/env python
"""
Unit and integration tests for MultiBranchFusionNet deep learning model.
"""

import sys
import os
import pytest
import torch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'ml_pipeline'))
sys.path.insert(0, project_root)

from ml_pipeline.models.multibranch_fusion_net import MultiBranchFusionNet


@pytest.mark.parametrize("fusion_type", ['concat', 'add', 'attention', 'enhanced_attention'])
def test_fusion_net_architectures(fusion_type):
    """Test model instantiation and forward pass across all supported fusion types."""
    batch_size = 2
    seq_len = 128
    num_classes = 6

    model = MultiBranchFusionNet(
        seq_length=seq_len,
        num_degradation_classes=num_classes,
        fusion_type=fusion_type
    )

    dummy_electrical = torch.randn(batch_size, 1, seq_len)
    dummy_ultrasonic = torch.randn(batch_size, 1, seq_len)
    dummy_thermal = torch.randn(batch_size, 1, seq_len)

    output = model(dummy_electrical, dummy_ultrasonic, dummy_thermal)

    assert 'degradation_logits' in output
    assert output['degradation_logits'].shape == (batch_size, num_classes)
    assert 'soh_mean' in output
    assert output['soh_mean'].shape == (batch_size, 1)
    assert 'soh_logvar' in output
    assert output['soh_logvar'].shape == (batch_size, 1)

    if fusion_type == 'enhanced_attention':
        assert 'attention_info' in output
        assert 'modality_weights' in output['attention_info']


if __name__ == '__main__':
    print("Running MultiBranchFusionNet tests directly...")
    for f in ['concat', 'add', 'attention', 'enhanced_attention']:
        test_fusion_net_architectures(f)
        print(f"  [OK] Fusion type '{f}' passed")
    print("All ML model tests passed successfully!")