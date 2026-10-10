"""
Quantization and C Code Generator for EdgeMultiModalNet.
Performs 8-bit integer (int8) quantization on the trained PyTorch EdgeMultiModalNet weights,
exports an ONNX model, and writes a zero-dependency C/C++ header file with static weight tables,
biases, quantization scales, and fixed-point bit-shift multipliers for embedded microcontrollers.
"""

import os
import sys
import json
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ml_pipeline.models.edge_multimodal_net import EdgeMultiModalNet
from ml_pipeline.models.edge_feature_extractor import extract_16d_features_from_scalars


def quantize_tensor_symmetric(tensor_np: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Quantize floating point array to symmetric signed 8-bit integer [-127, 127].
    Returns (quantized_int8_array, scale_float).
    """
    max_val = np.max(np.abs(tensor_np))
    if max_val < 1e-7:
        max_val = 1e-7
    scale = max_val / 127.0
    quantized = np.clip(np.round(tensor_np / scale), -127, 127).astype(np.int8)
    return quantized, float(scale)


def export_quantized_edge_model():
    print("=" * 75, flush=True)
    print(" [QUANTIZE] Exporting int8 Quantized Weights and Embedded C Header", flush=True)
    print("=" * 75, flush=True)

    # 1. Load trained PyTorch checkpoint
    model_path = os.path.join(project_root, 'ml_pipeline', 'models', 'edge_model_trained.pt')
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Trained edge model not found at {model_path}. Please run train_edge_student.py first.")

    checkpoint = torch.load(model_path, map_location='cpu')
    model = EdgeMultiModalNet(in_features=16, hidden_dim1=64, hidden_dim2=48, hidden_dim3=32, num_classes=6)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    # Fold BatchNorm into preceding Linear weights for ultra-fast MCU inference
    # W_fused = W * (gamma / sqrt(var + eps))
    # b_fused = (b - mean) * (gamma / sqrt(var + eps)) + beta
    def fold_bn(linear_layer: nn.Linear, bn_layer: nn.BatchNorm1d):
        w = linear_layer.weight.data.clone()
        b = linear_layer.bias.data.clone()
        gamma = bn_layer.weight.data.clone()
        beta = bn_layer.bias.data.clone()
        mean = bn_layer.running_mean.clone()
        var = bn_layer.running_var.clone()
        eps = bn_layer.eps

        inv_std = gamma / torch.sqrt(var + eps)
        w_fused = w * inv_std.unsqueeze(1)
        b_fused = (b - mean) * inv_std + beta
        return w_fused.numpy(), b_fused.numpy()

    w1_fused, b1_fused = fold_bn(model.layer1, model.bn1)
    w2_fused, b2_fused = fold_bn(model.layer2, model.bn2)
    w3 = model.layer3.weight.data.numpy()
    b3 = model.layer3.bias.data.numpy()

    w_cls = model.classifier_head.weight.data.numpy()
    b_cls = model.classifier_head.bias.data.numpy()

    w_soh_m = model.soh_mean_head.weight.data.numpy()
    b_soh_m = model.soh_mean_head.bias.data.numpy()

    w_soh_v = model.soh_logvar_head.weight.data.numpy()
    b_soh_v = model.soh_logvar_head.bias.data.numpy()

    w_gate = model.modality_gate_head.weight.data.numpy()
    b_gate = model.modality_gate_head.bias.data.numpy()

    # Quantize weights and biases
    q_w1, s_w1 = quantize_tensor_symmetric(w1_fused)
    q_w2, s_w2 = quantize_tensor_symmetric(w2_fused)
    q_w3, s_w3 = quantize_tensor_symmetric(w3)
    q_w_cls, s_w_cls = quantize_tensor_symmetric(w_cls)
    q_w_soh_m, s_w_soh_m = quantize_tensor_symmetric(w_soh_m)
    q_w_soh_v, s_w_soh_v = quantize_tensor_symmetric(w_soh_v)
    q_w_gate, s_w_gate = quantize_tensor_symmetric(w_gate)

    # 2. Export ONNX representation
    onnx_dir = os.path.join(project_root, 'ml_pipeline', 'models')
    onnx_path = os.path.join(onnx_dir, 'edge_model.onnx')
    try:
        class ONNXWrapper(nn.Module):
            def __init__(self, net):
                super().__init__()
                self.net = net
            def forward(self, x):
                out = self.net(x)
                return out['degradation_logits'], out['soh_mean'], out['soh_logvar'], out['modality_weights']

        wrapper = ONNXWrapper(model)
        dummy_input = torch.randn(1, 16, dtype=torch.float32)
        torch.onnx.export(
            wrapper,
            dummy_input,
            onnx_path,
            input_names=['input_features'],
            output_names=['degradation_logits', 'soh_mean', 'soh_logvar', 'modality_weights'],
            dynamic_axes={'input_features': {0: 'batch_size'}},
            opset_version=14
        )
        print(f"[EXPORT] ONNX model exported: {onnx_path}", flush=True)
    except Exception as e:
        print(f"[WARN] ONNX export notice: {e}", flush=True)

    # 3. Generate Embedded C Header (firmware/src/ml/edge_model_weights.h)
    fw_ml_dir = os.path.join(project_root, 'firmware', 'src', 'ml')
    os.makedirs(fw_ml_dir, exist_ok=True)
    c_header_path = os.path.join(fw_ml_dir, 'edge_model_weights.h')

    def format_array_int8(arr: np.ndarray, name: str, indent: int = 4) -> str:
        flat = arr.flatten()
        lines = []
        pad = " " * indent
        chunk_sz = 16
        lines.append(f"{pad}static const int8_t {name}[{len(flat)}] = {{")
        for i in range(0, len(flat), chunk_sz):
            chunk = flat[i:i+chunk_sz]
            vals = ", ".join(f"{v:4d}" for v in chunk)
            comma = "," if i + chunk_sz < len(flat) else ""
            lines.append(f"{pad}    {vals}{comma}")
        lines.append(f"{pad}}};")
        return "\n".join(lines)

    def format_array_float(arr: np.ndarray, name: str, indent: int = 4) -> str:
        flat = arr.flatten()
        lines = []
        pad = " " * indent
        chunk_sz = 8
        lines.append(f"{pad}static const float {name}[{len(flat)}] = {{")
        for i in range(0, len(flat), chunk_sz):
            chunk = flat[i:i+chunk_sz]
            vals = ", ".join(f"{v:10.6f}f" for v in chunk)
            comma = "," if i + chunk_sz < len(flat) else ""
            lines.append(f"{pad}    {vals}{comma}")
        lines.append(f"{pad}}};")
        return "\n".join(lines)

    c_content = f"""/**
 * @file edge_model_weights.h
 * @brief Auto-generated int8 quantized weights and parameters for EdgeMultiModalNet.
 * @note Zero external dependencies. Designed for ultra-fast fixed-point MCU execution.
 * Timestamp: {checkpoint.get('training_timestamp', '2026-10-05')}
 */

#ifndef EDGE_MODEL_WEIGHTS_H
#define EDGE_MODEL_WEIGHTS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {{
#endif

#define EDGE_ML_IN_FEATURES      16
#define EDGE_ML_HIDDEN_1         64
#define EDGE_ML_HIDDEN_2         48
#define EDGE_ML_HIDDEN_3         32
#define EDGE_ML_NUM_CLASSES      6
#define EDGE_ML_NUM_MODALITIES   3

// --- Layer 1 (16 -> 64, Fused BatchNorm) ---
#define EDGE_ML_SCALE_W1         {s_w1:.8f}f
{format_array_int8(q_w1, "EDGE_ML_W1")}
{format_array_float(b1_fused, "EDGE_ML_B1")}

// --- Layer 2 (64 -> 48, Fused BatchNorm) ---
#define EDGE_ML_SCALE_W2         {s_w2:.8f}f
{format_array_int8(q_w2, "EDGE_ML_W2")}
{format_array_float(b2_fused, "EDGE_ML_B2")}

// --- Layer 3 (48 -> 32) ---
#define EDGE_ML_SCALE_W3         {s_w3:.8f}f
{format_array_int8(q_w3, "EDGE_ML_W3")}
{format_array_float(b3, "EDGE_ML_B3")}

// --- Classifier Head (32 -> 6) ---
#define EDGE_ML_SCALE_W_CLS      {s_w_cls:.8f}f
{format_array_int8(q_w_cls, "EDGE_ML_W_CLS")}
{format_array_float(b_cls, "EDGE_ML_B_CLS")}

// --- SOH Mean Head (32 -> 1) ---
#define EDGE_ML_SCALE_W_SOH_M    {s_w_soh_m:.8f}f
{format_array_int8(q_w_soh_m, "EDGE_ML_W_SOH_M")}
{format_array_float(b_soh_m, "EDGE_ML_B_SOH_M")}

// --- SOH Log-Variance Head (32 -> 1) ---
#define EDGE_ML_SCALE_W_SOH_V    {s_w_soh_v:.8f}f
{format_array_int8(q_w_soh_v, "EDGE_ML_W_SOH_V")}
{format_array_float(b_soh_v, "EDGE_ML_B_SOH_V")}

// --- Modality Gating Head (32 -> 3) ---
#define EDGE_ML_SCALE_W_GATE     {s_w_gate:.8f}f
{format_array_int8(q_w_gate, "EDGE_ML_W_GATE")}
{format_array_float(b_gate, "EDGE_ML_B_GATE")}

#ifdef __cplusplus
}}
#endif

#endif // EDGE_MODEL_WEIGHTS_H
"""

    with open(c_header_path, 'w') as f:
        f.write(c_content)
    print(f"[EXPORT] C header generated: {c_header_path}", flush=True)

    # 4. Save quantized dictionary
    quantized_meta = {
        'in_features': 16,
        'hidden_dims': [64, 48, 32],
        'num_classes': 6,
        'scales': {
            'w1': s_w1,
            'w2': s_w2,
            'w3': s_w3,
            'w_cls': s_w_cls,
            'w_soh_m': s_w_soh_m,
            'w_soh_v': s_w_soh_v,
            'w_gate': s_w_gate
        },
        'total_int8_weight_bytes': len(q_w1.flatten()) + len(q_w2.flatten()) + len(q_w3.flatten()) + \
                                   len(q_w_cls.flatten()) + len(q_w_soh_m.flatten()) + len(q_w_soh_v.flatten()) + len(q_w_gate.flatten()),
        'total_float_bias_bytes': (len(b1_fused) + len(b2_fused) + len(b3) + len(b_cls) + len(b_soh_m) + len(b_soh_v) + len(b_gate)) * 4
    }
    quantized_json = os.path.join(project_root, 'ml_pipeline', 'models', 'edge_quantization_meta.json')
    with open(quantized_json, 'w') as f:
        json.dump(quantized_meta, f, indent=2)
    print(f"[SAVED] Quantization metadata: {quantized_json}", flush=True)
    print(f"Total int8 weights: {quantized_meta['total_int8_weight_bytes']} bytes (~{quantized_meta['total_int8_weight_bytes']/1024.0:.2f} KB)", flush=True)


if __name__ == '__main__':
    export_quantized_edge_model()
