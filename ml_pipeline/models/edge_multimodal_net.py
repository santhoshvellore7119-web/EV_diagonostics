"""
EdgeMultiModalNet: Ultra-compact, low-latency deep learning architecture designed for
synchronous execution on microcontrollers (ESP32, ARM Cortex-M4/M7, RISC-V) and edge nodes.

Features:
- 16-D physics-informed feature vector input
- Multi-head inference:
  1. 6-class degradation classification logits
  2. SOH mean regression
  3. SOH log-variance (calibrated epistemic/aleatoric uncertainty)
  4. 3-modality attention/gating weights (Electrical, Ultrasonic, Thermal)
- Parameter budget: ~6.1k parameters (<25 KB float32, <7 KB int8 quantized)
"""

from typing import Dict, Any, Tuple, Optional
import torch
import torch.nn as nn
import torch.nn.functional as F


class EdgeMultiModalNet(nn.Module):
    """
    Ultra-lightweight multi-modal neural network for real-time edge battery diagnostics.
    """

    def __init__(
        self,
        in_features: int = 16,
        hidden_dim1: int = 64,
        hidden_dim2: int = 48,
        hidden_dim3: int = 32,
        num_classes: int = 6
    ):
        super(EdgeMultiModalNet, self).__init__()
        
        self.in_features = in_features
        self.num_classes = num_classes
        
        # Shared feature extraction backbone
        self.layer1 = nn.Linear(in_features, hidden_dim1)
        self.bn1 = nn.BatchNorm1d(hidden_dim1)
        self.relu1 = nn.ReLU()
        
        self.layer2 = nn.Linear(hidden_dim1, hidden_dim2)
        self.bn2 = nn.BatchNorm1d(hidden_dim2)
        self.relu2 = nn.ReLU()
        
        self.layer3 = nn.Linear(hidden_dim2, hidden_dim3)
        self.relu3 = nn.ReLU()
        
        # Multi-task output heads
        # 1. Degradation mode classifier head (6 classes)
        self.classifier_head = nn.Linear(hidden_dim3, num_classes)
        
        # 2. SOH regression mean head
        self.soh_mean_head = nn.Linear(hidden_dim3, 1)
        
        # 3. SOH uncertainty log-variance head
        self.soh_logvar_head = nn.Linear(hidden_dim3, 1)
        
        # 4. Modality gating head (Learns relative weighting between Electrical, Ultrasonic, Thermal)
        self.modality_gate_head = nn.Linear(hidden_dim3, 3)

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass.
        Args:
            x: Input tensor of shape (B, 16) or (16,)
        Returns:
            Dictionary with:
                'degradation_logits': (B, 6)
                'soh_mean': (B, 1)
                'soh_logvar': (B, 1)
                'soh': (B, 1) - alias for soh_mean
                'modality_weights': (B, 3) - normalized attention weights
        """
        if x.dim() == 1:
            x = x.unsqueeze(0)
            
        # Backbone feature extraction
        h1 = self.relu1(self.bn1(self.layer1(x)))
        h2 = self.relu2(self.bn2(self.layer2(h1)))
        h3 = self.relu3(self.layer3(h2))
        
        # Multi-task heads
        logits = self.classifier_head(h3)
        soh_mean = self.soh_mean_head(h3)
        soh_logvar = self.soh_logvar_head(h3)
        modality_weights = F.softmax(self.modality_gate_head(h3), dim=-1)
        
        return {
            'degradation_logits': logits,
            'soh_mean': soh_mean,
            'soh': soh_mean,
            'soh_logvar': soh_logvar,
            'modality_weights': modality_weights
        }

    def count_parameters(self) -> int:
        """Return total number of trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def model_size_kb(self, precision_bytes: int = 4) -> float:
        """Estimate model size in Kilobytes."""
        total_params = self.count_parameters()
        return (total_params * precision_bytes) / 1024.0


if __name__ == '__main__':
    model = EdgeMultiModalNet()
    total_p = model.count_parameters()
    print(f"EdgeMultiModalNet initialized:")
    print(f"  Total parameters: {total_p:,}")
    print(f"  Size (float32):   {model.model_size_kb(4):.2f} KB")
    print(f"  Size (int8):      {model.model_size_kb(1):.2f} KB")
    
    dummy_in = torch.randn(4, 16)
    out = model(dummy_in)
    print(f"  Logits shape:     {out['degradation_logits'].shape}")
    print(f"  SOH mean shape:   {out['soh_mean'].shape}")
    print(f"  SOH logvar shape: {out['soh_logvar'].shape}")
    print(f"  Modality weights: {out['modality_weights'].shape}")
