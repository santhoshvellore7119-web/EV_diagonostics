"""
Multi-branch fusion network for multi-modal battery diagnostic data with enhanced cross-modal attention.
Now includes uncertainty estimation for State of Health (SOH) predictions.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class _FeatureExtractor(nn.Module):
    """Base feature extractor using 1D convolutions."""

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


class CrossModalAttention(nn.Module):
    """
    Cross-modal attention mechanism that learns diagnostic-specific relationships
    between electrical, ultrasonic, and thermal modalities.
    """

    def __init__(self, feature_dim=128):
        super(CrossModalAttention, self).__init__()
        self.feature_dim = feature_dim

        # Query, Key, Value projections for each modality pair
        self.electrical_to_ultrasonic = nn.MultiheadAttention(feature_dim, num_heads=4, batch_first=True)
        self.electrical_to_thermal = nn.MultiheadAttention(feature_dim, num_heads=4, batch_first=True)
        self.ultrasonic_to_electrical = nn.MultiheadAttention(feature_dim, num_heads=4, batch_first=True)
        self.ultrasonic_to_thermal = nn.MultiheadAttention(feature_dim, num_heads=4, batch_first=True)
        self.thermal_to_electrical = nn.MultiheadAttention(feature_dim, num_heads=4, batch_first=True)
        self.thermal_to_ultrasonic = nn.MultiheadAttention(feature_dim, num_heads=4, batch_first=True)

        # Modality importance weighting (learns which modalities are more diagnostic for different degradation types)
        self.modality_importance = nn.Sequential(
            nn.Linear(feature_dim * 3, feature_dim),
            nn.ReLU(),
            nn.Linear(feature_dim, 3),
            nn.Softmax(dim=-1)
        )

        # Cross-modal interaction fusion
        self.interaction_fusion = nn.Sequential(
            nn.Linear(feature_dim * 3, feature_dim * 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(feature_dim * 2, feature_dim)
        )

    def forward(self, electrical, ultrasonic, thermal):
        """
        Args:
            electrical: Tensor of shape (B, feature_dim)
            ultrasonic: Tensor of shape (B, feature_dim)
            thermal: Tensor of shape (B, feature_dim)
        Returns:
            fused_features: Tensor of shape (B, feature_dim)
            attention_info: Dictionary with attention weights for interpretability
        """
        # Add sequence dimension for MultiheadAttention (B, 1, feature_dim)
        e_seq = electrical.unsqueeze(1)  # (B, 1, D)
        u_seq = ultrasonic.unsqueeze(1)  # (B, 1, D)
        t_seq = thermal.unsqueeze(1)     # (B, 1, D)

        # Cross-modal attention: each modality attends to others
        e_to_u, _ = self.electrical_to_ultrasonic(e_seq, u_seq, u_seq)  # Electrical attends to Ultrasonic
        e_to_t, _ = self.electrical_to_thermal(e_seq, t_seq, t_seq)     # Electrical attends to Thermal
        u_to_e, _ = self.ultrasonic_to_electrical(u_seq, e_seq, e_seq)  # Ultrasonic attends to Electrical
        u_to_t, _ = self.ultrasonic_to_thermal(u_seq, t_seq, t_seq)     # Ultrasonic attends to Thermal
        t_to_e, _ = self.thermal_to_electrical(t_seq, e_seq, e_seq)     # Thermal attends to Electrical
        t_to_u, _ = self.thermal_to_ultrasonic(t_seq, u_seq, u_seq)     # Thermal attends to Ultrasonic

        # Remove sequence dimension
        e_to_u = e_to_u.squeeze(1)  # (B, D)
        e_to_t = e_to_t.squeeze(1)  # (B, D)
        u_to_e = u_to_e.squeeze(1)  # (B, D)
        u_to_t = u_to_t.squeeze(1)  # (B, D)
        t_to_e = t_to_e.squeeze(1)  # (B, D)
        t_to_u = t_to_u.squeeze(1)  # (B, D)

        # Compute modality importance weights based on combined features
        combined_features = torch.cat([electrical, ultrasonic, thermal], dim=-1)  # (B, 3D)
        modality_weights = self.modality_importance(combined_features)  # (B, 3)

        # Weighted sum of original features based on importance
        weighted_electrical = electrical * modality_weights[:, 0:1]
        weighted_ultrasonic = ultrasonic * modality_weights[:, 1:2]
        weighted_thermal = thermal * modality_weights[:, 2:3]

        # Fuse cross-modal interactions
        # Each modality's enhanced representation is combination of self + what it learned from others
        e_enhanced = weighted_electrical + 0.5 * (e_to_u + e_to_t)
        u_enhanced = weighted_ultrasonic + 0.5 * (u_to_e + u_to_t)
        t_enhanced = weighted_thermal + 0.5 * (t_to_e + t_to_u)

        # Final fusion of enhanced modality representations
        interaction_features = torch.cat([e_enhanced, u_enhanced, t_enhanced], dim=-1)  # (B, 3D)
        fused_features = self.interaction_fusion(interaction_features)  # (B, D)

        # Prepare attention info for interpretability (optional)
        attention_info = {
            'modality_weights': modality_weights.detach(),
            'e_to_u_attention': e_to_u.detach(),
            'e_to_t_attention': e_to_t.detach(),
            'u_to_e_attention': u_to_e.detach(),
            'u_to_t_attention': u_to_t.detach(),
            't_to_e_attention': t_to_e.detach(),
            't_to_u_attention': t_to_u.detach()
        }

        return fused_features, attention_info


class MultiBranchFusionNet(nn.Module):
    """
    Multi-branch network with separate encoders for each modality and enhanced fusion strategies.
    Now includes uncertainty estimation for State of Health (SOH) predictions.
    """

    def __init__(self, seq_length=256, num_degradation_classes=6, fusion_type='enhanced_attention'):
        """
        Args:
            seq_length (int): Length of input sequences.
            num_degradation_classes (int): Number of degradation mode classes.
            fusion_type (str): How to fuse features ('concat', 'add', 'attention', 'enhanced_attention').
        """
        super(MultiBranchFusionNet, self).__init__()
        self.fusion_type = fusion_type

        # Modality-specific branches
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
        elif fusion_type == 'enhanced_attention':
            self.fusion_dim = 128
            self.cross_modal_attention = CrossModalAttention(feature_dim=128)
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
        # For uncertainty estimation, we predict both mean and log variance of SOH
        self.soh_mean_head = nn.Linear(128, 1)
        self.soh_logvar_head = nn.Linear(128, 1)

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
                'soh_mean': (B, 1) - predicted mean SOH
                'soh_logvar': (B, 1) - predicted log variance of SOH (for uncertainty)
                'attention_info': dict (only for enhanced_attention fusion type)
        """
        # Extract features from each branch
        feat_e = self.electrical_branch(electrical)
        feat_u = self.ultrasonic_branch(ultrasonic)
        feat_t = self.thermal_branch(thermal)

        # Fusion
        if self.fusion_type == 'concat':
            fused = torch.cat([feat_e, feat_u, feat_t], dim=1)
            attention_info = None
        elif self.fusion_type == 'add':
            fused = feat_e + feat_u + feat_t
            attention_info = None
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
            attention_info = {'attention_weights': attn_weights.squeeze(1).detach()}
        elif self.fusion_type == 'enhanced_attention':
            fused, attention_info = self.cross_modal_attention(feat_e, feat_u, feat_t)

        # Post-fusion processing
        features = self.fusion_fc(fused)

        # Outputs
        degradation_logits = self.classification_head(features)
        soh_mean = self.soh_mean_head(features)
        soh_logvar = self.soh_logvar_head(features)  # Log variance for numerical stability

        result = {
            'degradation_logits': degradation_logits,
            'soh': soh_mean,
            'soh_mean': soh_mean,
            'soh_logvar': soh_logvar
        }

        if attention_info is not None:
            result['attention_info'] = attention_info
            if 'modality_weights' in attention_info:
                result['modality_weights'] = attention_info['modality_weights']

        return result


if __name__ == "__main__":
    # Simple test
    print("Testing MultiBranchFusionNet with uncertainty estimation...")
    model = MultiBranchFusionNet(fusion_type='enhanced_attention')
    batch_size = 4
    seq_len = 256
    dummy_electrical = torch.randn(batch_size, 1, seq_len)
    dummy_ultrasonic = torch.randn(batch_size, 1, seq_len)
    dummy_thermal = torch.randn(batch_size, 1, seq_len)
    output = model(dummy_electrical, dummy_ultrasonic, dummy_thermal)
    print("Classification logits shape:", output['degradation_logits'].shape)
    print("SOH mean shape:", output['soh_mean'].shape)
    print("SOH logvar shape:", output['soh_logvar'].shape)
    if 'attention_info' in output:
        print("Attention info keys:", list(output['attention_info'].keys()))
        print("Modality weights shape:", output['attention_info']['modality_weights'].shape)