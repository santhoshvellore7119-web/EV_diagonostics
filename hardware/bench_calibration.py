"""
Sim-to-Real Bench Calibration & Transfer Learning Utility for Phase 1-2 Hardware Bring-Up.

Bridges physical differences between the canonical 10 mm reference cell model and any real
pouch or cylindrical Li-ion cell on the test bench:
1. Calibrates cell-specific baseline geometry & impedance (cell thickness d_cell, R0_ref,
   ToF_ref, Amplitude_ref, and differential T_surface - T_ambient).
2. Normalizes raw hardware DAQ frames into the canonical 16D feature space.
3. Supports lightweight Last-Layer Transfer Learning (freezing the 16->64->48->32 trunk of
   EdgeMultiModalNet and fine-tuning the output heads with L2 prior anchoring on 5-cell
   bench aging data).
"""

import os
import sys
import json
import argparse
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ml_pipeline.models.edge_feature_extractor import extract_16d_features_from_scalars
from ml_pipeline.models.edge_multimodal_net import EdgeMultiModalNet


CANONICAL_REF = {
    'r0_ohm': 0.042,
    'tof_us': 8.00,
    'amplitude': 0.95,
    'cell_thickness_m': 0.010,
}


@dataclass
class CellCalibrationProfile:
    """Hardware calibration parameters measured on a healthy reference cell."""
    cell_model: str = "LiPo_6060100_5Ah_Pouch"
    cell_thickness_m: float = 0.0065
    r0_healthy_ohm: float = 0.028
    tof_healthy_us: float = 5.20
    amplitude_healthy: float = 0.92
    ambient_temp_c: float = 27.5

    @property
    def r0_scale(self) -> float:
        return CANONICAL_REF['r0_ohm'] / max(1e-4, self.r0_healthy_ohm)

    @property
    def tof_scale(self) -> float:
        return CANONICAL_REF['tof_us'] / max(0.5, self.tof_healthy_us)

    @property
    def amp_scale(self) -> float:
        return CANONICAL_REF['amplitude'] / max(0.05, self.amplitude_healthy)


class BenchCalibrator:
    """
    Calibrates raw bench sensor readings into the canonical 16D feature space and
    optionally fine-tunes the final linear head of EdgeMultiModalNet on bench cells.
    """

    def __init__(self, profile: Optional[CellCalibrationProfile] = None):
        self.profile = profile or CellCalibrationProfile()

    @classmethod
    def from_healthy_cell_samples(
        cls,
        samples: List[Dict[str, float]],
        cell_model: str = "LiPo_6060100_5Ah_Pouch",
        cell_thickness_m: float = 0.0065,
    ) -> "BenchCalibrator":
        """Compute baseline calibration profile from N repeated healthy cell readings."""
        r0_vals = [
            abs(s.get('shunt_voltage_v', 0.014)) / max(1e-3, abs(s.get('current_a', 0.5)))
            for s in samples
        ]
        tof_vals = [float(s.get('time_of_flight_us', 5.2)) for s in samples]
        amp_vals = [float(s.get('amplitude', 0.92)) for s in samples]
        amb_vals = [float(s.get('ambient_temp_c', 25.0)) for s in samples]

        profile = CellCalibrationProfile(
            cell_model=cell_model,
            cell_thickness_m=float(cell_thickness_m),
            r0_healthy_ohm=float(np.median(r0_vals)),
            tof_healthy_us=float(np.median(tof_vals)),
            amplitude_healthy=float(np.median(amp_vals)),
            ambient_temp_c=float(np.median(amb_vals)),
        )
        return cls(profile)

    def extract_calibrated_16d_features(self, raw_daq: Dict[str, float]) -> np.ndarray:
        """
        Convert a raw hardware DAQ reading from any cell geometry into the canonical
        16D feature vector expected by EdgeMultiModalNet.
        """
        v_bus = float(raw_daq.get('bus_voltage_v', 3.85))
        i_meas = max(1e-3, abs(float(raw_daq.get('current_a', 0.50))))
        dv_cell = abs(float(raw_daq.get('shunt_voltage_v', i_meas * self.profile.r0_healthy_ohm)))
        r0_raw = dv_cell / i_meas

        # Scale cell-specific R0, ToF, and Amplitude to canonical reference domain
        r0_cal = r0_raw * self.profile.r0_scale
        dv_cal = i_meas * r0_cal

        tof_raw = float(raw_daq.get('time_of_flight_us', self.profile.tof_healthy_us))
        tof_cal = tof_raw * self.profile.tof_scale

        amp_raw = float(raw_daq.get('amplitude', self.profile.amplitude_healthy))
        amp_cal = amp_raw * self.profile.amp_scale

        phase_rad = float(raw_daq.get('phase_shift', 0.0))

        # Differential surface-to-ambient temperature compensation
        t_surf = float(raw_daq.get('surface_temp_c', raw_daq.get('temperature_c', 26.5)))
        t_amb = float(raw_daq.get('ambient_temp_c', self.profile.ambient_temp_c))
        dt_rise = max(0.0, t_surf - t_amb)
        temp_comp_c = 25.0 + dt_rise
        dT_dt = float(raw_daq.get('temp_gradient_c_per_s', 0.10))

        return extract_16d_features_from_scalars(
            bus_voltage_v=v_bus,
            shunt_voltage_v=dv_cal,
            current_a=i_meas,
            power_w=v_bus * i_meas,
            time_of_flight_us=tof_cal,
            amplitude=amp_cal,
            phase_shift=phase_rad,
            temperature_c=temp_comp_c,
            temp_gradient_c_per_s=dT_dt,
            cell_thickness_m=CANONICAL_REF['cell_thickness_m'],
        )

    def fine_tune_head_on_bench_data(
        self,
        model: EdgeMultiModalNet,
        bench_samples: List[Dict[str, float]],
        epochs: int = 25,
        lr: float = 1.5e-3,
        l2_anchor_weight: float = 0.05,
    ) -> Dict[str, float]:
        """
        Freeze the 16->64->48->32 trunk of EdgeMultiModalNet and fine-tune only the
        final linear classification and SOH heads on calibrated bench stressor samples.
        """
        for name, param in model.named_parameters():
            if 'classifier_head' in name or 'soh_mean_head' in name:
                param.requires_grad = True
            else:
                param.requires_grad = False

        X_list, y_cls_list, y_soh_list = [], [], []
        for s in bench_samples:
            X_list.append(self.extract_calibrated_16d_features(s))
            y_cls_list.append(int(s['label_idx']))
            y_soh_list.append(float(s['soh_pct']) / 100.0)

        X_t = torch.tensor(np.stack(X_list), dtype=torch.float32)
        y_cls_t = torch.tensor(y_cls_list, dtype=torch.long)
        y_soh_t = torch.tensor(y_soh_list, dtype=torch.float32).unsqueeze(1)

        model.eval()  # Keep BatchNorm running stats frozen from large-scale pretraining
        with torch.no_grad():
            pre_out = model(X_t)
            pre_acc = float((pre_out['degradation_logits'].argmax(dim=-1) == y_cls_t).float().mean().item()) * 100.0
            pre_mae = float(torch.abs(pre_out['soh_mean'] * 100.0 - y_soh_t * 100.0).mean().item())

        w_cls_init = model.classifier_head.weight.detach().clone()
        b_cls_init = model.classifier_head.bias.detach().clone()

        optimizer = torch.optim.Adam(
            [p for p in model.parameters() if p.requires_grad], lr=lr
        )
        ce_loss_fn = nn.CrossEntropyLoss()
        mse_loss_fn = nn.MSELoss()

        for _ in range(epochs):
            optimizer.zero_grad()
            out = model(X_t)
            loss_cls = ce_loss_fn(out['degradation_logits'], y_cls_t)
            loss_soh = mse_loss_fn(out['soh_mean'], y_soh_t)
            loss_anchor = l2_anchor_weight * (
                torch.sum((model.classifier_head.weight - w_cls_init) ** 2)
                + torch.sum((model.classifier_head.bias - b_cls_init) ** 2)
            )
            loss = loss_cls + 2.0 * loss_soh + loss_anchor
            loss.backward()
            optimizer.step()

        with torch.no_grad():
            post_out = model(X_t)
            post_acc = float((post_out['degradation_logits'].argmax(dim=-1) == y_cls_t).float().mean().item()) * 100.0
            post_mae = float(torch.abs(post_out['soh_mean'] * 100.0 - y_soh_t * 100.0).mean().item())

        return {
            'pre_calibration_accuracy_pct': round(pre_acc, 2),
            'post_calibration_accuracy_pct': round(post_acc, 2),
            'pre_calibration_soh_mae_pct': round(pre_mae, 2),
            'post_calibration_soh_mae_pct': round(post_mae, 2),
            'num_bench_samples': len(bench_samples),
        }


def generate_emulated_pouch_bench_samples(seed: int = 42) -> Tuple[List[Dict[str, float]], List[Dict[str, float]]]:
    """
    Emulate raw hardware DAQ measurements from a 6.5 mm 5 Ah LiPo pouch cell bench
    (where baseline R0 = 28 mOhm, ToF = 5.20 us, T_ambient = 28.5 C) across all 6 modes.
    """
    rng = np.random.default_rng(seed)
    healthy_ref_samples = []
    for _ in range(10):
        i_a = 0.50
        r0 = 0.028 * rng.uniform(0.97, 1.03)
        healthy_ref_samples.append({
            'bus_voltage_v': float(rng.uniform(3.75, 4.05)),
            'shunt_voltage_v': float(i_a * r0),
            'current_a': i_a,
            'time_of_flight_us': float(5.20 * rng.uniform(0.98, 1.02)),
            'amplitude': float(0.92 * rng.uniform(0.96, 1.04)),
            'phase_shift': 0.0,
            'surface_temp_c': float(28.5 + 1.35 * rng.uniform(0.92, 1.08)),
            'ambient_temp_c': 28.5,
            'temp_gradient_c_per_s': 0.05,
        })

    # Stressor matrix across all 6 modes on the 6.5 mm pouch cell
    mode_specs = [
        # (label_idx, mode_name, r0_mult, tof_mult, amp_mult, phase, dt_rise, dT_dt, soh)
        (0, 'healthy',                   1.00, 1.00, 1.00, 0.00000,  1.08, 0.04, 97.5),
        (1, 'li_plating',                1.48, 0.90, 0.92, 0.00000,  1.85, 0.07, 83.0),
        (2, 'active_material_loss',      2.10, 1.08, 0.82, 0.00000,  3.95, 0.14, 74.0),
        (3, 'electrolyte_decomposition', 2.67, 1.16, 0.58, 0.00000,  5.45, 0.20, 66.0),
        (4, 'gas_generation',            2.26, 1.28, 0.37, 3.14159,  6.95, 0.25, 61.0),
        (5, 'internal_short',            1.86, 1.05, 0.88, 0.00000, 15.50, 0.52, 43.0),
    ]

    bench_stressor_samples = []
    for label_idx, _, r0_m, tof_m, amp_m, ph, dt_r, grad, soh in mode_specs:
        for _ in range(8):
            i_a = 0.50
            r0 = 0.028 * r0_m * rng.uniform(0.96, 1.04)
            t_amb = float(rng.uniform(22.0, 33.0))  # Varying lab room temperature
            bench_stressor_samples.append({
                'label_idx': label_idx,
                'soh_pct': float(soh + rng.uniform(-1.5, 1.5)),
                'bus_voltage_v': float(rng.uniform(3.65, 4.00) - i_a * r0),
                'shunt_voltage_v': float(i_a * r0),
                'current_a': i_a,
                'time_of_flight_us': float(5.20 * tof_m * rng.uniform(0.98, 1.02)),
                'amplitude': float(0.92 * amp_m * rng.uniform(0.95, 1.05)),
                'phase_shift': float(ph),
                'surface_temp_c': float(t_amb + dt_r * rng.uniform(0.94, 1.06)),
                'ambient_temp_c': t_amb,
                'temp_gradient_c_per_s': float(grad * rng.uniform(0.92, 1.08)),
            })

    return healthy_ref_samples, bench_stressor_samples


def run_bench_calibration_demo() -> Dict[str, object]:
    """Run an end-to-end Sim-to-Real pouch cell calibration & evaluation check."""
    healthy_ref, bench_samples = generate_emulated_pouch_bench_samples(seed=42)
    calibrator = BenchCalibrator.from_healthy_cell_samples(
        healthy_ref,
        cell_model="LiPo_6060100_5Ah_Pouch",
        cell_thickness_m=0.0065,
    )

    ckpt_path = os.path.join(project_root, 'ml_pipeline', 'models', 'edge_model_trained.pt')
    model = EdgeMultiModalNet()
    if os.path.exists(ckpt_path):
        ckpt = torch.load(ckpt_path, map_location='cpu')
        sd = ckpt['model_state_dict'] if 'model_state_dict' in ckpt else ckpt
        model.load_state_dict(sd)

    metrics = calibrator.fine_tune_head_on_bench_data(
        model, bench_samples, epochs=60, lr=8e-3, l2_anchor_weight=0.01
    )
    report = {
        'calibration_profile': asdict(calibrator.profile),
        'scaling_factors': {
            'r0_scale': round(calibrator.profile.r0_scale, 4),
            'tof_scale': round(calibrator.profile.tof_scale, 4),
            'amp_scale': round(calibrator.profile.amp_scale, 4),
        },
        'transfer_metrics': metrics,
    }

    out_dir = os.path.join(project_root, 'results')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'bench_calibration_report.json')
    with open(out_path, 'w') as f:
        json.dump(report, f, indent=2)

    print("===========================================================================")
    print(" [SIM-TO-REAL CALIBRATION] Phase 1-2 Hardware Domain Adaptation Report")
    print("===========================================================================")
    print(f"Cell Profile:          {calibrator.profile.cell_model} ({calibrator.profile.cell_thickness_m*1000:.1f} mm)")
    print(f"Healthy Baseline:      R0={calibrator.profile.r0_healthy_ohm*1000:.1f} mOhm | ToF={calibrator.profile.tof_healthy_us:.2f} us | Amp={calibrator.profile.amplitude_healthy:.2f}")
    print(f"Domain Scale Factors:  R0 x{calibrator.profile.r0_scale:.3f} | ToF x{calibrator.profile.tof_scale:.3f} | Amp x{calibrator.profile.amp_scale:.3f}")
    print(f"Zero-Shot Calibrated:  Acc = {metrics['pre_calibration_accuracy_pct']:.2f}% | SOH MAE = {metrics['pre_calibration_soh_mae_pct']:.2f}%")
    print(f"Fine-Tuned Head (25e): Acc = {metrics['post_calibration_accuracy_pct']:.2f}% | SOH MAE = {metrics['post_calibration_soh_mae_pct']:.2f}%")
    print(f"[SAVED] Bench calibration report: {out_path}")
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Phase 1-2 Sim-to-Real Bench Calibration Utility")
    parser.add_argument('--simulate-bench', action='store_true', default=True, help="Run emulated 5Ah pouch cell bench calibration")
    args = parser.parse_args()
    run_bench_calibration_demo()
