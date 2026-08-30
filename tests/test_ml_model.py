#!/usr/bin/env python
"""
Quick test to verify the enhanced ML model can be imported and instantiated.
"""

import sys
import os

# Add the ml_pipeline directory to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'ml_pipeline'))
sys.path.insert(0, project_root)

try:
    from models.multibranch_fusion_net import MultiBranchFusionNet
    import torch

    print("Testing MultiBranchFusionNet import and instantiation...")

    # Test different fusion types
    for fusion_type in ['concat', 'add', 'attention', 'enhanced_attention']:
        print(f"  Testing fusion type: {fusion_type}")
        model = MultiBranchFusionNet(fusion_type=fusion_type)
        print(f"    Model created successfully")

        # Test forward pass with dummy data
        batch_size = 2
        seq_len = 128  # Smaller for quick test
        dummy_electrical = torch.randn(batch_size, 1, seq_len)
        dummy_ultrasonic = torch.randn(batch_size, 1, seq_len)
        dummy_thermal = torch.randn(batch_size, 1, seq_len)

        output = model(dummy_electrical, dummy_ultrasonic, dummy_thermal)
        print(f"    Output shapes - logits: {output['degradation_logits'].shape}, SOH: {output['soh'].shape}")

        # Check if attention info is present for enhanced_attention
        if fusion_type == 'enhanced_attention' and 'attention_info' in output:
            print(f"    Attention info present with keys: {list(output['attention_info'].keys())}")

    print("All ML model tests passed!")

except Exception as e:
    print(f"Error testing ML model: {e}")
    import traceback
    traceback.print_exc()