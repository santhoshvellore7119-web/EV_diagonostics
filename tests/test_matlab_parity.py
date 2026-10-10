import os
import sys
import re
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ev_cell_multimodal_sim.core.physics_engine import DEGRADATION_PHYSICS_PARAMS


def test_matlab_degradation_mode_library_parity():
    """
    Parse matlab_simulink_demo/utils/degradation_mode_library.m and verify that all
    scaling factors align with the canonical Python physics parameters.
    """
    matlab_file = os.path.join(project_root, 'matlab_simulink_demo', 'utils', 'degradation_mode_library.m')
    assert os.path.exists(matlab_file), f"File {matlab_file} not found"

    with open(matlab_file, 'r', encoding='utf-8') as f:
        content = f.read()

    modes = ['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition', 'gas_generation', 'internal_short']
    healthy_phys = DEGRADATION_PHYSICS_PARAMS['healthy']

    for mode in modes:
        phys = DEGRADATION_PHYSICS_PARAMS[mode]
        # Verify mode is present in MATLAB library
        assert f"base_modes('{mode}')" in content, f"Mode '{mode}' missing in degradation_mode_library.m"
        
        # Verify relative R0 scale
        expected_r0_scale = phys['r0'] / healthy_phys['r0']
        match_r0 = re.search(rf"base_modes\('{mode}'\)\s*=\s*struct\([^)]*'R0_scale',\s*([0-9.]+)", content)
        assert match_r0 is not None, f"Could not parse R0_scale for mode '{mode}'"
        parsed_r0_scale = float(match_r0.group(1))
        assert abs(parsed_r0_scale - expected_r0_scale) < 0.05, (
            f"Mode '{mode}' MATLAB R0_scale ({parsed_r0_scale:.3f}) does not match expected ({expected_r0_scale:.3f})"
        )

        # Verify relative SOS scale
        expected_sos_factor = phys['sos'] / healthy_phys['sos']
        match_sos = re.search(rf"base_modes\('{mode}'\)\s*=\s*struct\([^)]*'sos_factor',\s*([0-9.]+)", content)
        assert match_sos is not None, f"Could not parse sos_factor for mode '{mode}'"
        parsed_sos_factor = float(match_sos.group(1))
        assert abs(parsed_sos_factor - expected_sos_factor) < 0.05, (
            f"Mode '{mode}' MATLAB sos_factor ({parsed_sos_factor:.3f}) does not match expected ({expected_sos_factor:.3f})"
        )


def test_matlab_edge_weights_numerical_parity():
    """
    Verify that the MATLAB weight matrix file edge_model_weights.mat produces
    identical forward inference predictions to the PyTorch EdgeMultiModalNet model.
    """
    import scipy.io as sio
    import torch
    import numpy as np
    from ml_pipeline.models.edge_multimodal_net import EdgeMultiModalNet

    mat_file = os.path.join(project_root, 'ml_pipeline', 'models', 'edge_model_weights.mat')
    ckpt_file = os.path.join(project_root, 'backend', 'models', 'edge_model_trained.pt')
    assert os.path.exists(mat_file), f"MATLAB weights file {mat_file} missing"
    assert os.path.exists(ckpt_file), f"PyTorch checkpoint {ckpt_file} missing"

    # Instantiate and load PyTorch model
    net = EdgeMultiModalNet()
    ckpt = torch.load(ckpt_file, map_location='cpu')
    net.load_state_dict(ckpt['model_state_dict'] if 'model_state_dict' in ckpt else ckpt)
    net.eval()

    # Generate test feature vector
    np.random.seed(42)
    x_np = np.random.randn(1, 16).astype(np.float32)
    x_tensor = torch.from_numpy(x_np)

    with torch.no_grad():
        pt_out = net(x_tensor)

    # Replicate MATLAB forward pass using exported .mat weights
    weights = sio.loadmat(mat_file)
    z1 = x_np @ weights['layer1.weight'].T + weights['layer1.bias']
    z1_bn = (z1 - weights['bn1.running_mean']) / np.sqrt(weights['bn1.running_var'] + 1e-5) * weights['bn1.weight'] + weights['bn1.bias']
    a1 = np.maximum(z1_bn, 0)

    z2 = a1 @ weights['layer2.weight'].T + weights['layer2.bias']
    z2_bn = (z2 - weights['bn2.running_mean']) / np.sqrt(weights['bn2.running_var'] + 1e-5) * weights['bn2.weight'] + weights['bn2.bias']
    a2 = np.maximum(z2_bn, 0)

    a3 = np.maximum(a2 @ weights['layer3.weight'].T + weights['layer3.bias'], 0)

    cls_out = a3 @ weights['classifier_head.weight'].T + weights['classifier_head.bias']
    soh_m = a3 @ weights['soh_mean_head.weight'].T + weights['soh_mean_head.bias']
    soh_v = a3 @ weights['soh_logvar_head.weight'].T + weights['soh_logvar_head.bias']

    # Assert machine-precision parity (< 1e-4)
    diff_cls = float(np.max(np.abs(cls_out - pt_out['degradation_logits'].numpy())))
    diff_soh = float(np.max(np.abs(soh_m - pt_out['soh_mean'].numpy())))
    diff_var = float(np.max(np.abs(soh_v - pt_out['soh_logvar'].numpy())))

    assert diff_cls < 1e-4, f"Degradation logits differ between PyTorch and MATLAB: {diff_cls}"
    assert diff_soh < 1e-4, f"SOH mean differs between PyTorch and MATLAB: {diff_soh}"
    assert diff_var < 1e-4, f"SOH logvar differs between PyTorch and MATLAB: {diff_var}"


def test_matlab_fusion_model_files_presence():
    """Verify that both the MATLAB script and .mat weights for the teacher model exist."""
    mat_file = os.path.join(project_root, 'ml_pipeline', 'models', 'fusion_model_weights.mat')
    script_file = os.path.join(project_root, 'ml_pipeline', 'models', 'multibranch_fusion_net_matlab.m')
    onnx_file = os.path.join(project_root, 'ml_pipeline', 'models', 'teacher_model.onnx')

    assert os.path.exists(mat_file), "fusion_model_weights.mat is missing"
    assert os.path.getsize(mat_file) > 1000000, "fusion_model_weights.mat is too small"
    assert os.path.exists(script_file), "multibranch_fusion_net_matlab.m is missing"
    assert os.path.exists(onnx_file), "teacher_model.onnx is missing"

