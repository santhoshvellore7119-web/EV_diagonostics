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
    """

    def __init__(
        self,
        num_samples: int = 1000,
        seq_length: int = 256,
        soc_range: Tuple[float, float] = (0.05, 0.95),
        transform=None,
        seed: Optional[int] = None
    ):
        """
        Args:
            num_samples (int): Number of samples to generate.
            seq_length (int): Length of each signal sequence.
            soc_range (tuple): Range of SOC to draw from [min_soc, max_soc].
            transform (callable, optional): Optional transform.
            seed (int, optional): Random seed for reproducible dataset construction.
        """
        self.num_samples = num_samples
        self.seq_length = seq_length
        self.soc_range = soc_range
        self.transform = transform
        self.seed = seed
        self.degradation_modes = [
            'healthy', 'li_plating', 'active_material_loss',
            'electrolyte_decomposition', 'gas_generation', 'internal_short'
        ]
        self.num_classes = len(self.degradation_modes)

        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        # Select degradation mode regime
        mode_idx = idx % self.num_classes if self.seed is not None else random.randint(0, self.num_classes - 1)
        mode = self.degradation_modes[mode_idx]
        base_params = DEGRADATION_PHYSICS_PARAMS[mode]

        # Draw SOC within specified range
        soc = random.uniform(self.soc_range[0], self.soc_range[1])

        # Sample physical parameter distribution around nominal regime
        r0 = float(base_params['r0'] * (1.0 + random.uniform(-0.06, 0.06)))
        r1 = float(base_params['r1'] * (1.0 + random.uniform(-0.08, 0.08)))
        c1 = float(base_params['c1'] * (1.0 + random.uniform(-0.05, 0.05)))
        sos = float(base_params['sos'] + random.uniform(-30.0, 30.0))
        attenuation = float(np.clip(base_params['attenuation'] + random.uniform(-0.04, 0.04), 0.15, 1.05))
        r_th = float(base_params['r_th'] * (1.0 + random.uniform(-0.05, 0.05)))
        c_th = float(base_params['c_th'] * (1.0 + random.uniform(-0.05, 0.05)))
        phase_shift = float(base_params.get('phase_shift', 0.0) + random.uniform(-0.05, 0.05))
        gas_reverb = bool(base_params.get('gas_reverb', False))
        temp_ambient = 25.0 + random.uniform(0.0, 4.0) if mode != 'internal_short' else 35.0 + random.uniform(0.0, 8.0)

        # Synthesize waveforms purely through physics engine without passing degradation label
        sampling_rate_hz = 200000.0
        period_s = (self.seq_length) / sampling_rate_hz
        sim_res = simulate_cell_from_parameters(
            soc=soc,
            r0=r0,
            r1=r1,
            c1=c1,
            sos=sos,
            attenuation=attenuation,
            r_th=r_th,
            c_th=c_th,
            pulse_amp=0.5,
            pulse_width_s=10e-6,
            period_s=period_s,
            sampling_rate_hz=sampling_rate_hz,
            add_noise=True,
            phase_shift=phase_shift,
            gas_reverb=gas_reverb,
            temp_ambient=temp_ambient
        )

        voltage = sim_res['electrical']['voltage'][:self.seq_length]
        ultrasonic_sig = sim_res['ultrasonic']['signal'][:self.seq_length]
        temp_rise = sim_res['thermal']['temperature_rise'][:self.seq_length]

        # Standard physical scaling normalization
        electrical = (voltage - 3.0) / 1.5
        ultrasonic = ultrasonic_sig
        thermal = temp_rise / 20.0

        # Convert to torch tensors (1, seq_length)
        elec_tensor = torch.from_numpy(electrical).float().unsqueeze(0)
        ultra_tensor = torch.from_numpy(ultrasonic).float().unsqueeze(0)
        therm_tensor = torch.from_numpy(thermal).float().unsqueeze(0)

        # Compute ground truth continuous SOH derived from physical degradation state
        nominal_soh = base_params['nominal_soh']
        soh = float(np.clip(nominal_soh * (1.0 - 0.05 * (1.0 - soc)) + np.random.normal(0, 1.2), 0.0, 100.0))

        sample = {
            'electrical': elec_tensor,
            'ultrasonic': ultra_tensor,
            'thermal': therm_tensor,
            'degradation_mode': torch.tensor(mode_idx, dtype=torch.long),
            'soh': torch.tensor(soh, dtype=torch.float32),
            'soc': torch.tensor(soc, dtype=torch.float32),
            'r0': torch.tensor(r0, dtype=torch.float32),
            'sos': torch.tensor(sos, dtype=torch.float32)
        }

        if self.transform:
            sample = self.transform(sample)

        return sample