"""
Synthetic data generation for multi-modal battery diagnostic system.
Generates simulated electrical, ultrasonic, and thermal signals strictly from physical ODE models.
Guarantees zero label leakage into waveform synthesis.
"""

import os
import sys
import random
from typing import Optional, Tuple
import numpy as np
import torch
from torch.utils.data import Dataset

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
sim_core_path = os.path.join(project_root, 'ev_cell_multimodal_sim')
if sim_core_path not in sys.path:
    sys.path.insert(0, sim_core_path)

from core.physics_engine import simulate_cell_from_parameters, DEGRADATION_PHYSICS_PARAMS


class MultiModalBatteryDataset(Dataset):
    """
    Parameter-driven multi-modal battery dataset with zero label leakage.
    Each waveform is synthesized strictly via physical ODE integration from physical state parameters.
    Supports continuous degradation severity per mode, cell-to-cell variation,
    sensor drift, noise corruption sweeps, modality dropout, and split selection.
    """

    DEGRADATION_MODES = [
        'healthy', 'li_plating', 'active_material_loss',
        'electrolyte_decomposition', 'gas_generation', 'internal_short'
    ]

    def __init__(
        self,
        num_samples: int = 1000,
        seq_length: int = 256,
        soc_range: Tuple[float, float] = (0.05, 0.95),
        temp_range: Tuple[float, float] = (20.0, 45.0),
        severity_range: Tuple[float, float] = (0.75, 1.0),
        num_cells: int = 50,
        samples_per_cell: int = 20,
        transform=None,
        seed: Optional[int] = None,
        hold_out_soc_range: Optional[Tuple[float, float]] = None,
        hold_out_temp_range: Optional[Tuple[float, float]] = None,
        hold_out_severity_threshold: Optional[float] = None,
        mode: str = 'train',
        split: Optional[str] = None,
        val_split: float = 0.1,
        test_split: float = 0.1,
        noise_multiplier: float = 1.0,
        dropout_modality: Optional[str] = None,
    ):
        self.num_samples = num_samples
        self.seq_length = seq_length
        self.soc_range = soc_range
        self.temp_range = temp_range
        self.severity_range = severity_range
        self.num_cells = max(1, num_cells)
        self.samples_per_cell = samples_per_cell
        self.transform = transform
        self.seed = seed
        if split is not None:
            if 'val' in split:
                mode = 'val'
            elif 'test' in split:
                mode = 'test'
            else:
                mode = 'train'
        self.mode = mode
        self.val_split = val_split
        self.test_split = test_split
        self.hold_out_soc_range = hold_out_soc_range
        self.hold_out_temp_range = hold_out_temp_range
        self.hold_out_severity_threshold = hold_out_severity_threshold
        self.noise_multiplier = float(noise_multiplier)
        self.dropout_modality = dropout_modality

        def _compute_raw_target():
            R = max(10, self.num_samples)
            while True:
                n_val = int(R * self.val_split)
                n_test = int(R * self.test_split)
                n_train = R - n_val - n_test
                if self.mode == 'train' and n_train >= self.num_samples:
                    return R
                elif self.mode == 'val' and n_val >= self.num_samples:
                    return R
                elif self.mode == 'test' and n_test >= self.num_samples:
                    return R
                R += 1

        self._raw_target = _compute_raw_target()

        self.degradation_modes = list(self.DEGRADATION_MODES)
        self.num_classes = len(self.degradation_modes)

        # Compute healthy parameters and deltas for each mode
        self.healthy_params = DEGRADATION_PHYSICS_PARAMS['healthy']
        self.mode_deltas = {}
        for deg_mode in self.degradation_modes:
            if deg_mode == 'healthy':
                continue
            delta = {}
            for key in self.healthy_params:
                if key in DEGRADATION_PHYSICS_PARAMS[deg_mode]:
                    if isinstance(self.healthy_params[key], bool):
                        delta[key] = float(DEGRADATION_PHYSICS_PARAMS[deg_mode][key]) - float(self.healthy_params[key])
                    else:
                        delta[key] = DEGRADATION_PHYSICS_PARAMS[deg_mode][key] - self.healthy_params[key]
                else:
                    delta[key] = 0.0
            self.mode_deltas[deg_mode] = delta

        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)

        self.samples = self._generate_all_samples()
        self._split_samples()

    def _sample_continuous_physics(self, dominant_mode_idx: int):
        """Sample physical state parameters and severity vector xi for a given dominant mode index."""
        dominant_mode = self.degradation_modes[dominant_mode_idx]
        base_params = {}
        for key, healthy_val in self.healthy_params.items():
            if isinstance(healthy_val, bool):
                base_params[key] = healthy_val
            else:
                variation = random.uniform(-0.04, 0.04)
                base_params[key] = healthy_val * (1.0 + variation)

        low_s = max(0.42, self.severity_range[0])
        high_s = max(low_s + 0.15, self.severity_range[1])
        primary_sev = random.uniform(low_s, high_s) if dominant_mode != 'healthy' else 0.0

        xi = np.zeros(5, dtype=np.float32)
        if dominant_mode_idx > 0:
            xi[dominant_mode_idx - 1] = float(primary_sev)
            # Realistic secondary co-occurring degradation (up to 22% of primary severity)
            other_indices = [idx for idx in range(1, 6) if idx != dominant_mode_idx]
            sec_idx = random.choice(other_indices)
            sec_sev = random.uniform(0.0, 0.22 * primary_sev)
            xi[sec_idx - 1] = float(sec_sev)

        params = base_params.copy()
        if dominant_mode != 'healthy':
            for m_idx in range(1, 6):
                sev_val = float(xi[m_idx - 1])
                if sev_val <= 0.0:
                    continue
                m_name = self.degradation_modes[m_idx]
                delta = self.mode_deltas[m_name]
                for key, val in delta.items():
                    if key in ('gas_reverb', 'phase_shift'):
                        continue
                    params[key] = params[key] + sev_val * val
            params['gas_reverb'] = bool(DEGRADATION_PHYSICS_PARAMS[dominant_mode]['gas_reverb'])
            params['phase_shift'] = float(DEGRADATION_PHYSICS_PARAMS[dominant_mode]['phase_shift']) * primary_sev + random.uniform(-0.08, 0.08)
        else:
            params['gas_reverb'] = False
            params['phase_shift'] = random.uniform(-0.06, 0.06)

        params['r0'] = float(np.clip(params['r0'], 0.015, 0.160))
        params['r1'] = float(np.clip(params['r1'], 0.008, 0.120))
        params['c1'] = float(np.clip(params['c1'], 600.0, 3200.0))
        params['sos'] = float(np.clip(params['sos'], 1850.0, 2950.0))
        params['attenuation'] = float(np.clip(params['attenuation'], 0.25, 1.15))
        params['r_th'] = float(np.clip(params['r_th'], 1.0, 4.5))
        params['c_th'] = float(np.clip(params['c_th'], 300.0, 750.0))
        params['nominal_soh'] = float(np.clip(params['nominal_soh'], 35.0, 100.0))
        params['soh'] = float(np.clip(params['nominal_soh'] + random.uniform(-0.8, 0.8), 35.0, 100.0))
        params['temp_ambient'] = random.uniform(self.temp_range[0], self.temp_range[1])
        return xi, params

    def _generate_all_samples(self):
        """Generate balanced, physically distinct multi-modal samples across all 6 degradation regimes."""
        all_samples = []

        for sample_idx in range(self._raw_target):
            cell_idx = sample_idx % self.num_cells
            dominant_mode_idx = sample_idx % self.num_classes
            dominant_mode = self.degradation_modes[dominant_mode_idx]

            xi, params = self._sample_continuous_physics(dominant_mode_idx)
            soc = random.uniform(self.soc_range[0], self.soc_range[1])
            temp_ambient = params['temp_ambient']

            mode_severities = {m: 0.0 for m in self.degradation_modes}
            if dominant_mode != 'healthy':
                mode_severities[dominant_mode] = float(xi[dominant_mode_idx - 1])

            drift_freq = random.uniform(0.01, 0.1)
            drift_amp_voltage = random.uniform(-0.001, 0.001)
            drift_amp_ultrasonic = random.uniform(-0.005, 0.005)
            drift_amp_thermal = random.uniform(-0.02, 0.02)

            add_noise = (random.random() > 0.05) and (self.noise_multiplier > 0.0)

            sample_info = {
                'cell_idx': cell_idx,
                'soc': soc,
                'temp_ambient': temp_ambient,
                'dominant_mode': dominant_mode,
                'dominant_mode_idx': dominant_mode_idx,
                'mode_severities': mode_severities,
                'xi': xi,
                'params': params,
                'drift_freq': drift_freq,
                'drift_amp_voltage': drift_amp_voltage,
                'drift_amp_ultrasonic': drift_amp_ultrasonic,
                'drift_amp_thermal': drift_amp_thermal,
                'add_noise': add_noise,
            }
            all_samples.append(sample_info)

        return all_samples

    def _split_samples(self):
        """Split samples into train, val, test based on holdout criteria and random split."""
        filtered_samples = []
        for sample in self.samples:
            soc = sample['soc']
            temp = sample['temp_ambient']
            max_severity = max(sample['mode_severities'].values()) if self.num_classes > 1 else 0.0

            holdout = False
            if self.hold_out_soc_range and self.hold_out_soc_range[0] <= soc <= self.hold_out_soc_range[1]:
                holdout = True
            if self.hold_out_temp_range and self.hold_out_temp_range[0] <= temp <= self.hold_out_temp_range[1]:
                holdout = True
            if self.hold_out_severity_threshold is not None and max_severity >= self.hold_out_severity_threshold:
                holdout = True

            if not holdout:
                filtered_samples.append(sample)

        random.shuffle(filtered_samples)
        n_total = len(filtered_samples)
        n_val = int(n_total * self.val_split)
        n_test = int(n_total * self.test_split)
        n_train = n_total - n_val - n_test

        if self.mode == 'train':
            self.samples = filtered_samples[:max(1, min(self.num_samples, n_train))]
        elif self.mode == 'val':
            self.samples = filtered_samples[n_train:n_train + max(1, min(self.num_samples, n_val))]
        elif self.mode == 'test':
            self.samples = filtered_samples[n_train + n_val:n_train + n_val + max(1, min(self.num_samples, n_test))]
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample_info = self.samples[idx]

        # Synthesize waveforms purely through physics engine without passing degradation label
        sampling_rate_hz = 200000.0
        period_s = (self.seq_length) / sampling_rate_hz
        sim_res = simulate_cell_from_parameters(
            soc=sample_info['soc'],
            r0=sample_info['params']['r0'],
            r1=sample_info['params']['r1'],
            c1=sample_info['params']['c1'],
            sos=sample_info['params']['sos'],
            attenuation=sample_info['params']['attenuation'],
            r_th=sample_info['params']['r_th'],
            c_th=sample_info['params']['c_th'],
            pulse_amp=0.5,
            pulse_width_s=10e-6,
            period_s=period_s,
            sampling_rate_hz=sampling_rate_hz,
            add_noise=sample_info['add_noise'],
            phase_shift=float(sample_info['params'].get('phase_shift', 0.0)),
            gas_reverb=bool(sample_info['params'].get('gas_reverb', False)),
            temp_ambient=sample_info['temp_ambient']
        )

        voltage = sim_res['electrical']['voltage'][:self.seq_length]
        ultrasonic_sig = sim_res['ultrasonic']['signal'][:self.seq_length]
        temp_rise = sim_res['thermal']['temperature_rise'][:self.seq_length]

        # Apply sensor drift (low-frequency sinusoidal offset)
        t = np.arange(self.seq_length) / sampling_rate_hz
        voltage = voltage + sample_info['drift_amp_voltage'] * np.sin(2 * np.pi * sample_info['drift_freq'] * t)
        ultrasonic_sig = ultrasonic_sig + sample_info['drift_amp_ultrasonic'] * np.sin(2 * np.pi * sample_info['drift_freq'] * t)
        temp_rise = temp_rise + sample_info['drift_amp_thermal'] * np.sin(2 * np.pi * sample_info['drift_freq'] * t)

        # Standard physical scaling normalization
        electrical = (voltage - 3.0) / 1.5
        ultrasonic = ultrasonic_sig
        thermal = temp_rise / 20.0

        # Apply extra noise multiplier if > 1.0 (for robustness sweeps)
        if self.noise_multiplier > 1.0:
            extra_std = 0.02 * (self.noise_multiplier - 1.0)
            electrical = electrical + np.random.normal(0, extra_std, size=electrical.shape)
            ultrasonic = ultrasonic + np.random.normal(0, extra_std, size=ultrasonic.shape)
            thermal = thermal + np.random.normal(0, extra_std, size=thermal.shape)

        # Convert to torch tensors (1, seq_length)
        elec_tensor = torch.from_numpy(electrical).float().unsqueeze(0)
        ultra_tensor = torch.from_numpy(ultrasonic).float().unsqueeze(0)
        therm_tensor = torch.from_numpy(thermal).float().unsqueeze(0)

        # Apply modality dropout if requested
        if self.dropout_modality == 'electrical':
            elec_tensor = torch.zeros_like(elec_tensor)
        elif self.dropout_modality == 'ultrasonic':
            ultra_tensor = torch.zeros_like(ultra_tensor)
        elif self.dropout_modality == 'thermal':
            therm_tensor = torch.zeros_like(therm_tensor)

        # Compute ground truth continuous SOH derived from the sample's mode-specific nominal_soh
        mode_nominal_soh = float(sample_info['params']['nominal_soh'])
        soh = float(np.clip(mode_nominal_soh - 1.5 * (1.0 - sample_info['soc']) + np.random.normal(0, 0.8), 35.0, 100.0))

        mode_idx = int(sample_info['dominant_mode_idx'])

        sample = {
            'electrical': elec_tensor,
            'ultrasonic': ultra_tensor,
            'thermal': therm_tensor,
            'degradation_mode': torch.tensor(mode_idx, dtype=torch.long),
            'soh': torch.tensor(soh, dtype=torch.float32),
            'soc': torch.tensor(sample_info['soc'], dtype=torch.float32),
            'xi': torch.from_numpy(sample_info['xi']).float(),
            'r0': torch.tensor(sample_info['params']['r0'], dtype=torch.float32),
            'r1': torch.tensor(sample_info['params']['r1'], dtype=torch.float32),
            'r_th': torch.tensor(sample_info['params']['r_th'], dtype=torch.float32),
            'c_th': torch.tensor(sample_info['params']['c_th'], dtype=torch.float32),
            'sos': torch.tensor(sample_info['params']['sos'], dtype=torch.float32),
            'attenuation': torch.tensor(sample_info['params']['attenuation'], dtype=torch.float32),
            'phase_shift': torch.tensor(float(sample_info['params'].get('phase_shift', 0.0)), dtype=torch.float32),
            'temp_ambient': torch.tensor(sample_info['temp_ambient'], dtype=torch.float32),
            'temp_rise_c': torch.tensor(float(np.mean(temp_rise)), dtype=torch.float32),
            'gas_reverb': bool(sample_info['params'].get('gas_reverb', False)),
        }

        if self.transform:
            sample = self.transform(sample)

        return sample


# Alias for backward compatibility with benchmarks/ablation_study.py
ContinuousMultiModalBatteryDataset = MultiModalBatteryDataset