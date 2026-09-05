"""
Synthetic data generation for multi-modal battery diagnostic system.
Generates simulated electrical, ultrasonic, and thermal signals for various degradation modes.
"""

import numpy as np
import torch
from torch.utils.data import Dataset
import random


class MultiModalBatteryDataset(Dataset):
    """
    Dataset for multi-modal battery diagnostic data.
    Each sample consists of:
        - Electrical signal: simulated EIS/pulse response (1D vector)
        - Ultrasonic signal: simulated pulse-echo waveform (1D vector)
        - Thermal signal: simulated transient temperature response (1D vector)
    Labels:
        - Degradation mode classification (0: healthy, 1: Li plating, 2: active material loss, 3: electrolyte decomposition, 4: gas generation, 5: internal short)
        - State of Health (SOH) regression (0-100%)
    """

    def __init__(self, num_samples=1000, seq_length=256, transform=None):
        """
        Args:
            num_samples (int): Number of samples to generate.
            seq_length (int): Length of each signal sequence.
            transform (callable, optional): Optional transform to be applied on a sample.
        """
        self.num_samples = num_samples
        self.seq_length = seq_length
        self.transform = transform
        self.degradation_modes = ['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition', 'gas_generation', 'internal_short']
        self.num_classes = len(self.degradation_modes)

        # Pre-generate all data for faster access (optional, but we'll generate on the fly in __getitem__ for flexibility)
        # We'll generate on the fly to allow for random augmentations each time.

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        # Randomly select a degradation mode
        mode_idx = random.randint(0, self.num_classes - 1)
        mode = self.degradation_modes[mode_idx]

        # Generate base signals (healthy)
        electrical = self._generate_electrical_base()
        ultrasonic = self._generate_ultrasonic_base()
        thermal = self._generate_thermal_base()

        # Apply degradation-specific modifications
        if mode == 'li_plating':
            electrical, ultrasonic, thermal = self._apply_lithium_plating(electrical, ultrasonic, thermal)
        elif mode == 'active_material_loss':
            electrical, ultrasonic, thermal = self._apply_active_material_loss(electrical, ultrasonic, thermal)
        elif mode == 'electrolyte_decomposition':
            electrical, ultrasonic, thermal = self._apply_electrolyte_decomposition(electrical, ultrasonic, thermal)
        elif mode == 'gas_generation':
            electrical, ultrasonic, thermal = self._apply_gas_generation(electrical, ultrasonic, thermal)
        elif mode == 'internal_short':
            electrical, ultrasonic, thermal = self._apply_internal_short(electrical, ultrasonic, thermal)
        # else: healthy, no modifications

        # Add noise
        electrical = self._add_noise(electrical, noise_level=0.02)
        ultrasonic = self._add_noise(ultrasonic, noise_level=0.03)
        thermal = self._add_noise(thermal, noise_level=0.015)

        # Normalize to zero mean, unit variance (per sample)
        electrical = (electrical - np.mean(electrical)) / (np.std(electrical) + 1e-8)
        ultrasonic = (ultrasonic - np.mean(ultrasonic)) / (np.std(ultrasonic) + 1e-8)
        thermal = (thermal - np.mean(thermal)) / (np.std(thermal) + 1e-8)

        # Convert to torch tensors
        electrical = torch.from_numpy(electrical).float().unsqueeze(0)  # Add channel dimension (1, seq_len)
        ultrasonic = torch.from_numpy(ultrasonic).float().unsqueeze(0)
        thermal = torch.from_numpy(thermal).float().unsqueeze(0)

        # Generate SOH label (inverse correlation with degradation severity)
        # Healthy: SOH ~ 95-100%, degradation reduces SOH
        base_soh = 100.0
        degradation_severity = {
            'healthy': 0.0,
            'li_plating': 0.1,
            'active_material_loss': 0.2,
            'electrolyte_decomposition': 0.15,
            'gas_generation': 0.05,
            'internal_short': 0.3
        }[mode]
        soh = base_soh * (1 - degradation_severity) + np.random.uniform(-2, 2)  # Add some variance
        soh = np.clip(soh, 0, 100)

        sample = {
            'electrical': electrical,
            'ultrasonic': ultrasonic,
            'thermal': thermal,
            'degradation_mode': torch.tensor(mode_idx, dtype=torch.long),
            'soh': torch.tensor(soh, dtype=torch.float)
        }

        if self.transform:
            sample = self.transform(sample)

        return sample

    def _generate_electrical_base(self):
        """Generate a simulated electrical signal (e.g., voltage response to current pulse)."""
        t = np.linspace(0, 1, self.seq_length)
        signal = np.exp(-t / 0.12) - 0.4 * np.exp(-t / 0.015)
        return signal

    def _generate_ultrasonic_base(self):
        """Generate a simulated ultrasonic pulse-echo waveform."""
        t = np.linspace(0, 1, self.seq_length)
        pulse = np.exp(-((t - 0.25) ** 2) / (2 * 0.02 ** 2))
        echo = 0.70 * np.exp(-((t - 0.60) ** 2) / (2 * 0.018 ** 2))
        return pulse + echo

    def _generate_thermal_base(self):
        """Generate a simulated thermal transient response."""
        t = np.linspace(0, 1, self.seq_length)
        signal = np.exp(-t / 0.25) * (1 - np.exp(-t / 0.06))
        return signal

    def _apply_lithium_plating(self, electrical, ultrasonic, thermal):
        """Modify signals to simulate lithium plating (anode diffusion tail, ToF advance + phase flip)."""
        t = np.linspace(0, 1, self.seq_length)
        electrical = np.exp(-t / 0.28) - 0.35 * np.exp(-t / 0.02) + 0.15 * np.exp(-t / 0.8)
        pulse = np.exp(-((t - 0.25) ** 2) / (2 * 0.02 ** 2))
        echo = -0.65 * np.exp(-((t - 0.56) ** 2) / (2 * 0.018 ** 2))  # Earlier ToF & phase flip
        ultrasonic = pulse + echo
        thermal = np.exp(-t / 0.35) * (1 - np.exp(-t / 0.05))
        return electrical, ultrasonic, thermal

    def _apply_active_material_loss(self, electrical, ultrasonic, thermal):
        """Modify signals to simulate active material loss (fast depletion, delayed & attenuated ToF)."""
        t = np.linspace(0, 1, self.seq_length)
        electrical = np.exp(-t / 0.04) - 0.60 * np.exp(-t / 0.008)
        pulse = np.exp(-((t - 0.25) ** 2) / (2 * 0.02 ** 2))
        echo = 0.35 * np.exp(-((t - 0.66) ** 2) / (2 * 0.025 ** 2))  # Delayed ToF & attenuation
        ultrasonic = pulse + echo
        thermal = (1 - np.exp(-t / 0.015)) * np.exp(-t / 0.15)  # Fast heating
        return electrical, ultrasonic, thermal

    def _apply_electrolyte_decomposition(self, electrical, ultrasonic, thermal):
        """Modify signals to simulate electrolyte decomposition (high impedance, acoustic scattering, Joule heating)."""
        t = np.linspace(0, 1, self.seq_length)
        electrical = np.exp(-t / 0.08) + 0.30 * np.exp(-t / 0.40) + 0.08 * np.sin(12 * np.pi * t) * np.exp(-3 * t)
        pulse = np.exp(-((t - 0.25) ** 2) / (2 * 0.02 ** 2))
        echo = 0.40 * np.exp(-((t - 0.62) ** 2) / (2 * 0.035 ** 2)) + 0.06 * np.sin(30 * np.pi * t)
        ultrasonic = pulse + echo
        thermal = (1 - np.exp(-t / 0.04)) * np.exp(-t / 0.40) + 0.12 * np.sin(2 * np.pi * t)
        return electrical, ultrasonic, thermal

    def _apply_gas_generation(self, electrical, ultrasonic, thermal):
        """Modify signals to simulate gas generation (multiple echo reverberation, thermal insulation)."""
        t = np.linspace(0, 1, self.seq_length)
        electrical = np.exp(-t / 0.12) - 0.40 * np.exp(-t / 0.015) + 0.04 * np.sin(6 * np.pi * t)
        pulse = np.exp(-((t - 0.25) ** 2) / (2 * 0.02 ** 2))
        echo1 = 0.12 * np.exp(-((t - 0.60) ** 2) / (2 * 0.015 ** 2))
        rev1 = 0.25 * np.exp(-((t - 0.42) ** 2) / (2 * 0.02 ** 2))
        rev2 = 0.18 * np.exp(-((t - 0.72) ** 2) / (2 * 0.02 ** 2))
        ultrasonic = pulse + echo1 + rev1 + rev2
        thermal = np.zeros_like(t)
        thermal[t > 0.05] = (1 - np.exp(-(t[t > 0.05] - 0.05) / 0.15)) * np.exp(-t[t > 0.05] / 0.35)
        return electrical, ultrasonic, thermal

    def _apply_internal_short(self, electrical, ultrasonic, thermal):
        """Modify signals to simulate internal short (severe self-discharge, acoustic emission, rapid heating)."""
        t = np.linspace(0, 1, self.seq_length)
        electrical = -0.80 * (1 - np.exp(-t / 0.05)) + np.exp(-t / 0.02)
        burst1 = 0.80 * np.exp(-((t - 0.15) ** 2) / (2 * 0.01 ** 2))
        burst2 = 0.60 * np.exp(-((t - 0.48) ** 2) / (2 * 0.015 ** 2))
        ultrasonic = burst1 + burst2
        thermal = (1 - np.exp(-t / 0.02)) + 0.80 * (t ** 2)
        return electrical, ultrasonic, thermal

    def _add_noise(self, signal, noise_level=0.02):
        """Add Gaussian noise to signal."""
        noise = np.random.randn(len(signal)) * noise_level
        return signal + noise