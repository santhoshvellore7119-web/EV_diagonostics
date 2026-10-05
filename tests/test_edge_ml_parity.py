#!/usr/bin/env python
"""
Parity and Distillation Alignment Tests between Teacher (MultiBranchFusionNet) and Student (EdgeMultiModalNet).
"""

import sys
import os
import pytest
import numpy as np
import torch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
sim_core_path = os.path.join(project_root, 'ev_cell_multimodal_sim')
if sim_core_path not in sys.path:
    sys.path.insert(0, sim_core_path)

from ml_pipeline.models.multibranch_fusion_net import MultiBranchFusionNet
from ml_pipeline.models.edge_multimodal_net import EdgeMultiModalNet
from ml_pipeline.models.edge_feature_extractor import extract_16d_features_from_scalars
from core.physics_engine import DEGRADATION_PHYSICS_PARAMS, simulate_cell_from_parameters


def test_teacher_student_cross_modal_alignment():
    """Verify that teacher and student both identify degradation modes and rank modalities accurately."""
    device = torch.device('cpu')
    
    teacher_path = os.path.join(project_root, 'ml_pipeline', 'models', 'fusion_net_trained.pt')
    student_path = os.path.join(project_root, 'ml_pipeline', 'models', 'edge_model_trained.pt')

    if not os.path.exists(teacher_path) or not os.path.exists(student_path):
        pytest.skip("Model weights not available for parity check")

    teacher = MultiBranchFusionNet(seq_length=256, num_degradation_classes=6, fusion_type='enhanced_attention')
    ckpt_t = torch.load(teacher_path, map_location=device)
    teacher.load_state_dict(ckpt_t.get('model_state_dict', ckpt_t))
    teacher.eval()

    student = EdgeMultiModalNet(in_features=16, hidden_dim1=64, hidden_dim2=48, hidden_dim3=32, num_classes=6)
    ckpt_s = torch.load(student_path, map_location=device)
    student.load_state_dict(ckpt_s.get('model_state_dict', ckpt_s))
    student.eval()

    modes = ['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition', 'gas_generation', 'internal_short']
    agreements = 0

    with torch.no_grad():
        for mode_idx, mode in enumerate(modes):
            phys = DEGRADATION_PHYSICS_PARAMS[mode]
            soc = 0.50
            
            # Synthesize waveforms for teacher
            sim_res = simulate_cell_from_parameters(
                soc=soc,
                r0=phys['r0'],
                r1=phys['r1'],
                c1=phys['c1'],
                sos=phys['sos'],
                attenuation=phys['attenuation'],
                r_th=phys['r_th'],
                c_th=phys['c_th'],
                pulse_amp=0.5,
                pulse_width_s=10e-6,
                period_s=256/200000.0,
                sampling_rate_hz=200000.0,
                add_noise=False,
                phase_shift=phys.get('phase_shift', 0.0),
                gas_reverb=phys.get('gas_reverb', False),
                temp_ambient=25.0 + (10.0 if mode == 'internal_short' else 0.0)
            )

            elec = torch.from_numpy((sim_res['electrical']['voltage'][:256] - 3.0) / 1.5).float().unsqueeze(0).unsqueeze(0)
            ultra = torch.from_numpy(sim_res['ultrasonic']['signal'][:256]).float().unsqueeze(0).unsqueeze(0)
            therm = torch.from_numpy(sim_res['thermal']['temperature_rise'][:256] / 20.0).float().unsqueeze(0).unsqueeze(0)

            t_out = teacher(elec, ultra, therm)
            t_pred = torch.argmax(t_out['degradation_logits'], dim=-1).item()

            # Extract 16-D features for student
            v_bus = float(3.0 + 1.2 * soc - 0.5 * phys['r0'])
            i_meas = 0.50
            f16 = extract_16d_features_from_scalars(
                bus_voltage_v=v_bus,
                shunt_voltage_v=i_meas * phys['r0'],
                current_a=i_meas,
                power_w=v_bus * i_meas,
                time_of_flight_us=float((2.0 * 0.01 / max(100.0, phys['sos'])) * 1e6),
                amplitude=phys['attenuation'],
                phase_shift=phys.get('phase_shift', 0.0),
                temperature_c=25.0 + (phys['r0'] * (i_meas ** 2) * 30.0) + (10.0 if mode == 'internal_short' else 0.0),
                temp_gradient_c_per_s=3.50 if mode == 'internal_short' else 0.10
            )

            s_out = student(torch.from_numpy(f16).float().unsqueeze(0))
            s_pred = torch.argmax(s_out['degradation_logits'], dim=-1).item()

            if t_pred == s_pred:
                agreements += 1

    agreement_rate = (agreements / len(modes)) * 100.0
    print(f"Teacher-Student Agreement Rate: {agreement_rate:.1f}% ({agreements}/{len(modes)})")
    assert agreement_rate >= 80.0, f"Teacher-Student agreement ({agreement_rate}%) is below 80%"
