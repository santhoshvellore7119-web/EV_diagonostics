function [pred_class_idx, probs, soh_mean, soh_std, modality_weights] = multibranch_fusion_net_matlab(x_16d, weights_mat_path)
% MULTIBRANCH_FUSION_NET_MATLAB
% Zero-Toolbox Pure Base MATLAB Neural Inference Engine for EV Battery Diagnostics.
% Loads the exported PyTorch weights (edge_model_weights.mat) and executes the
% 3-layer BatchNorm-folded MLP + multi-task classification, SOH mean/uncertainty,
% and modality gating heads.
%
% Inputs:
%   x_16d            : 16x1 standardized physical feature vector
%   weights_mat_path : (Optional) path to edge_model_weights.mat
%
% Outputs:
%   pred_class_idx   : 1-based class index (1=healthy .. 6=internal_short)
%   probs            : 6x1 softmax class probabilities
%   soh_mean         : Predicted State of Health (%)
%   soh_std          : Predicted epistemic uncertainty standard deviation (%)
%   modality_weights : 3x1 learned modality importance [Electrical; Ultrasonic; Thermal]

    if nargin < 2 || isempty(weights_mat_path)
        util_dir = fileparts(mfilename('fullpath'));
        weights_mat_path = fullfile(util_dir, '..', 'models', 'edge_model_weights.mat');
    end

    x = double(x_16d(:));
    w = load(weights_mat_path);

    % Layer 1 (16 -> 64, Fused BatchNorm + ReLU)
    h1 = max(0, double(w.W1) * x + double(w.B1(:)));

    % Layer 2 (64 -> 48, Fused BatchNorm + ReLU)
    h2 = max(0, double(w.W2) * h1 + double(w.B2(:)));

    % Layer 3 (48 -> 32 + ReLU)
    h3 = max(0, double(w.W3) * h2 + double(w.B3(:)));

    % Multi-Task Output Heads
    logits = double(w.W_CLS) * h3 + double(w.B_CLS(:));
    logits_shift = logits - max(logits);
    exp_l = exp(logits_shift);
    probs = exp_l ./ sum(exp_l);
    [~, pred_class_idx] = max(probs);

    soh_raw = double(w.W_SOH_M) * h3 + double(w.B_SOH_M(:));
    if abs(soh_raw) <= 1.5
        soh_mean = max(0.0, min(100.0, soh_raw * 100.0));
    else
        soh_mean = max(0.0, min(100.0, soh_raw));
    end

    logvar = max(-6.0, min(3.0, double(w.W_SOH_V) * h3 + double(w.B_SOH_V(:))));
    soh_std = exp(0.5 * logvar) * 100.0;

    gate_logits = double(w.W_GATE) * h3 + double(w.B_GATE(:));
    gate_exp = exp(gate_logits - max(gate_logits));
    modality_weights = gate_exp ./ sum(gate_exp);
end
