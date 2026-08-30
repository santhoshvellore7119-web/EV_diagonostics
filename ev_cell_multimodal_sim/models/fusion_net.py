"""
Uncertainty-aware multi-branch fusion network for multi-modal battery diagnostic data.
Implements heteroscedastic uncertainty estimation and confidence-weighted attention fusion.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class _FeatureExtractorWithUncertainty(nn.Module):
    """Feature extractor that outputs both features and uncertainty (log variance)."""

    def __init__(self, in_channels=1, out_features=128):
        super(_FeatureExtractorWithUncertainty, self).__init__()
        self.conv1 = nn.Conv1d(in_channels, 32, kernel_size=5, stride=2, padding=2)
        self.bn1 = nn.BatchNorm1d(32)
        self.conv2 = nn.Conv1d(32, 64, kernel_size=5, stride=2, padding=2)
        self.bn2 = nn.BatchNorm1d(64)
        self.conv3 = nn.Conv1d(64, 128, kernel_size=5, stride=2, padding=2)
        self.bn3 = nn.BatchNorm1d(128)
        self.global_avg_pool = nn.AdaptiveAvgPool1d(1)
        self.fc_features = nn.Linear(128, out_features)
        # Uncertainty head: predicts log variance
        self.fc_uncertainty = nn.Linear(128, out_features)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.global_avg_pool(x)
        x = x.view(x.size(0), -1)
        features = self.fc_features(x)
        # Predict log variance (uncertainty)
        log_var = self.fc_uncertainty(x)
        # Convert to precision (inverse variance) for confidence weighting
        # Precision = exp(-log_var) = 1/var
        precision = torch.exp(-log_var)
        return features, precision


class MultiBranchFusionNet(nn.Module):
    """
    Multi-branch network with uncertainty-aware confidence-weighted attention fusion.
    Each modality branch outputs features and precision (inverse variance).
    Fusion uses precision-weighted attention: higher precision -> higher weight.
    """

    def __init__(self, seq_length, num_degradation_classes=6, fusion_type='uncertainty_attention', **kwargs):
        """
        Args:
            seq_length (int): Length of input sequences.
            num_degradation_classes (int): Number of degradation mode classes.
            fusion_type (str): Fusion mode.
        """
        super(MultiBranchFusionNet, self).__init__()
        self.fusion_type = fusion_type

        # Modality-specific branches with uncertainty estimation
        self.electrical_branch = _FeatureExtractorWithUncertainty(in_channels=1, out_features=128)
        self.ultrasonic_branch = _FeatureExtractorWithUncertainty(in_channels=1, out_features=128)
        self.thermal_branch = _FeatureExtractorWithUncertainty(in_channels=1, out_features=128)

        # Post-fusion processing dimension
        if self.fusion_type == 'concat':
            self.fusion_dim = 128 * 3
        else:
            self.fusion_dim = 128

        # Shared post-fusion processing
        self.fusion_fc = nn.Sequential(
            nn.Linear(self.fusion_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.3)
        )

        # Output heads
        self.classification_head = nn.Linear(128, num_degradation_classes)
        # Regression head for SOH mean
        self.soh_mean_head = nn.Linear(128, 1)
        # Regression head for SOH log variance (for confidence interval)
        self.soh_log_var_head = nn.Linear(128, 1)

    def forward(self, electrical, ultrasonic, thermal):
        """
        Forward pass with uncertainty-aware fusion.
        Args:
            electrical: Tensor of shape (B, 1, L)
            ultrasonic: Tensor of shape (B, 1, L)
            thermal: Tensor of shape (B, 1, L)
        Returns:
            dict with keys:
                'degradation_logits': (B, num_classes)
                'soh': (B, 1) - predicted SOH mean
                'soh_mean': (B, 1) - predicted SOH mean
                'soh_var': (B, 1) - predicted SOH variance
                'modality_precisions': dict with precision for each modality
                'features': (B, 128) - fused features
        """
        # Extract features and precision from each branch
        feat_e, prec_e = self.electrical_branch(electrical)  # (B, 128), (B, 128)
        feat_u, prec_u = self.ultrasonic_branch(ultrasonic)  # (B, 128), (B, 128)
        feat_t, prec_t = self.thermal_branch(thermal)        # (B, 128), (B, 128)

        if self.fusion_type == 'concat':
            fused = torch.cat([feat_e, feat_u, feat_t], dim=1)
        elif self.fusion_type == 'add':
            fused = feat_e + feat_u + feat_t
        else:
            # Confidence-weighted attention fusion
            # Stack features and precisions
            stacked_features = torch.stack([feat_e, feat_u, feat_t], dim=1)
            stacked_precisions = torch.stack([prec_e, prec_u, prec_t], dim=1)

            # Compute attention weights based on precision
            modality_confidence = torch.mean(stacked_precisions, dim=2)  # (B, 3)
            modality_weights = F.softmax(modality_confidence, dim=1).unsqueeze(2)  # (B, 3, 1)
            fused = torch.sum(stacked_features * modality_weights, dim=1)  # (B, 128)

        # Post-fusion processing
        features = self.fusion_fc(fused)  # (B, 128)

        # Outputs
        degradation_logits = self.classification_head(features)  # (B, num_classes)
        soh_mean = self.soh_mean_head(features)                 # (B, 1)
        soh_log_var = self.soh_log_var_head(features)           # (B, 1)
        soh_var = torch.exp(soh_log_var)                        # Ensure positive variance

        return {
            'degradation_logits': degradation_logits,
            'soh': soh_mean,
            'soh_mean': soh_mean,
            'soh_var': soh_var,
            'modality_precisions': {
                'electrical': prec_e,
                'ultrasonic': prec_u,
                'thermal': prec_t
            },
            'features': features
        }


# Keep the baseline concatenation version for ablation studies
class _FeatureExtractor(nn.Module):
    """Base feature extractor using 1D convolutions (baseline version)."""

    def __init__(self, in_channels=1, out_features=128):
        super(_FeatureExtractor, self).__init__()
        self.conv1 = nn.Conv1d(in_channels, 32, kernel_size=5, stride=2, padding=2)
        self.bn1 = nn.BatchNorm1d(32)
        self.conv2 = nn.Conv1d(32, 64, kernel_size=5, stride=2, padding=2)
        self.bn2 = nn.BatchNorm1d(64)
        self.conv3 = nn.Conv1d(64, 128, kernel_size=5, stride=2, padding=2)
        self.bn3 = nn.BatchNorm1d(128)
        self.global_avg_pool = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Linear(128, out_features)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.global_avg_pool(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        return x


class BaselineFusionNet(nn.Module):
    """
    Baseline multi-branch network with concatenation fusion.
    Used for ablation studies to compare against uncertainty-aware fusion.
    """

    def __init__(self, seq_length, num_degradation_classes=6, fusion_type='concat'):
        """
        Args:
            seq_length (int): Length of input sequences.
            num_degradation_classes (int): Number of degradation mode classes.
            fusion_type (str): How to fuse features ('concat', 'add', 'attention').
        """
        super(BaselineFusionNet, self).__init__()
        self.fusion_type = fusion_type

        # Modality-specific branches (no uncertainty)
        self.electrical_branch = _FeatureExtractor(in_channels=1, out_features=128)
        self.ultrasonic_branch = _FeatureExtractor(in_channels=1, out_features=128)
        self.thermal_branch = _FeatureExtractor(in_channels=1, out_features=128)

        # Fusion layer
        if fusion_type == 'concat':
            self.fusion_dim = 128 * 3
        elif fusion_type == 'add':
            self.fusion_dim = 128
        elif fusion_type == 'attention':
            self.fusion_dim = 128
            self.attention = nn.Sequential(
                nn.Linear(128 * 3, 128),
                nn.Tanh(),
                nn.Linear(128, 3)
            )
        else:
            raise ValueError(f"Unsupported fusion type: {fusion_type}")

        # Shared post-fusion processing
        self.fusion_fc = nn.Sequential(
            nn.Linear(self.fusion_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.3)
        )

        # Output heads
        self.classification_head = nn.Linear(128, num_degradation_classes)
        self.regression_head = nn.Linear(128, 1)  # SOH output

    def forward(self, electrical, ultrasonic, thermal):
        """
        Forward pass.
        Args:
            electrical: Tensor of shape (B, 1, L)
            ultrasonic: Tensor of shape (B, 1, L)
            thermal: Tensor of shape (B, 1, L)
        Returns:
            dict with keys:
                'degradation_logits': (B, num_classes)
                'soh': (B, 1)
        """
        # Extract features from each branch
        feat_e = self.electrical_branch(electrical)
        feat_u = self.ultrasonic_branch(ultrasonic)
        feat_t = self.thermal_branch(thermal)

        # Fusion
        if self.fusion_type == 'concat':
            fused = torch.cat([feat_e, feat_u, feat_t], dim=1)
        elif self.fusion_type == 'add':
            fused = feat_e + feat_u + feat_t
        elif self.fusion_type == 'attention':
            # Stack features: (B, 3, 128)
            stacked = torch.stack([feat_e, feat_u, feat_t], dim=1)
            # Flatten for attention: (B, 3*128)
            flat = stacked.view(stacked.size(0), -1)
            # Compute attention weights: (B, 3)
            attn_weights = F.softmax(self.attention(flat), dim=1)
            # Weighted sum: (B, 1, 3) * (B, 3, 128) -> (B, 1, 128) -> (B, 128)
            attn_weights = attn_weights.unsqueeze(1)
            fused = torch.bmm(attn_weights, stacked).squeeze(1)

        # Post-fusion processing
        features = self.fusion_fc(fused)

        # Outputs
        degradation_logits = self.classification_head(features)
        soh = self.regression_head(features)

        return {
            'degradation_logits': degradation_logits,
            'soh': soh
        }


if __name__ == "__main__":
    # Simple test
    from config import params as P
    print("Testing UncertaintyAware FusionNet...")
    model = MultiBranchFusionNet(seq_length=P.SEQ_LENGTH)
    batch_size = 4
    dummy_electrical = torch.randn(batch_size, 1, P.SEQ_LENGTH)
    dummy_ultrasonic = torch.randn(batch_size, 1, P.SEQ_LENGTH)
    dummy_thermal = torch.randn(batch_size, 1, P.SEQ_LENGTH)
    output = model(dummy_electrical, dummy_ultrasonic, dummy_thermal)
    print("Classification logits shape:", output['degradation_logits'].shape)
    print("SOH mean shape:", output['soh_mean'].shape)
    print("SOH var shape:", output['soh_var'].shape)
    print("Features shape:", output['features'].shape)
    print("Modality precisions keys:", output['modality_precisions'].keys())

    print("\nTesting Baseline FusionNet (concat)...")
    baseline_model = BaselineFusionNet(seq_length=P.SEQ_LENGTH, fusion_type='concat')
    baseline_output = baseline_model(dummy_electrical, dummy_ultrasonic, dummy_thermal)
    print("Baseline classification logits shape:", baseline_output['degradation_logits'].shape)
    print("Baseline SOH shape:", baseline_output['soh'].shape)