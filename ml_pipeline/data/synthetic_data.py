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
        # Simulate a double exponential decay (typical battery response)
        signal = np.exp(-t / 0.1) - 0.5 * np.exp(-t / 0.01)
        return signal

    def _generate_ultrasonic_base(self):
        """Generate a simulated ultrasonic pulse-echo waveform."""
        t = np.linspace(0, 1, self.seq_length)
        # Simulate a transmitted pulse and an echo
        pulse = np.exp(-((t - 0.3) ** 2) / (2 * 0.02 ** 2))  # Main pulse
        echo = 0.6 * np.exp(-((t - 0.6) ** 2) / (2 * 0.015 ** 2))  # Echo
        signal = pulse + echo
        return signal

    def _generate_thermal_base(self):
        """Generate a simulated thermal transient response."""
        t = np.linspace(0, 1, self.seq_length)
        # Simulate a rapid heating and slower cooling
        signal = np.exp(-t / 0.2) * (1 - np.exp(-t / 0.05))
        return signal

    def _apply_lithium_plating(self, electrical, ultrasonic, thermal):
        """Modify signals to simulate lithium plating."""
        # Li plating increases resistance -> higher voltage drop, slower response
        electrical = electrical * 1.2  # Increase amplitude
        electrical = np.convolve(electrical, np.ones(5)/5, mode='same')  # Slightly smear (slow down)
        # Ultrasonic: plating may increase stiffness -> slight change in ToF
        ultrasonic = np.roll(ultrasonic, shift=2)  # Delay echo slightly
        # Thermal: plating may affect heat dissipation
        thermal = thermal * 0.9  # Slightly lower thermal response
        return electrical, ultrasonic, thermal

    def _apply_active_material_loss(self, electrical, ultrasonic, thermal):
        """Modify signals to simulate active material loss."""
        # Active material loss reduces capacity -> lower voltage signal
        electrical = electrical * 0.8
        # Ultrasonic: material loss may change density -> affect speed of sound
        ultrasonic = ultrasonic * 0.9  # Reduce amplitude
        # Thermal: less material -> lower thermal mass -> faster response
        thermal = np.convolve(thermal, np.ones(3)/3, mode='same')  # Slightly sharper
        return electrical, ultrasonic, thermal

    def _apply_electrolyte_decomposition(self, electrical, ultrasonic, thermal):
        """Modify signals to simulate electrolyte decomposition."""
        # Electrolyte decomposition increases impedance and may cause gas
        electrical = electrical * 1.1 + 0.05 * np.random.randn(self.seq_length)  # Increase impedance and noise
        # Ultrasonic: gas bubbles scatter sound -> attenuate signal
        attenuation = np.exp(-np.linspace(0, 0.5, self.seq_length))
        ultrasonic = ultrasonic * attenuation
        # Thermal: decomposition may be exothermic/endothermic
        thermal = thermal + 0.1 * np.sin(np.linspace(0, 4*np.pi, self.seq_length))  # Add oscillation
        return electrical, ultrasonic, thermal

    def _apply_gas_generation(self, electrical, ultrasonic, thermal):
        """Modify signals to simulate gas generation."""
        # Gas generation increases internal pressure, may affect electrical contacts slightly
        electrical = electrical * 0.95  # Slight increase in resistance
        # Ultrasonic: gas layers reflect/scatter -> strong attenuation and multiple echoes
        attenuation = np.exp(-np.linspace(0, 1, self.seq_length) * 0.7)
        ultrasonic = ultrasonic * attenuation
        # Add a secondary echo from gas layer
        echo_delay = int(0.2 * self.seq_length)
        if echo_delay < self.seq_length:
            ultrasonic[echo_delay:] += 0.3 * ultrasonic[:self.seq_length - echo_delay]
        # Thermal: gas generation may affect thermal conductivity
        thermal = thermal * 0.9
        return electrical, ultrasonic, thermal

    def _apply_internal_short(self, electrical, ultrasonic, thermal):
        """Modify signals to simulate internal short."""
        # Internal short causes self-discharge, voltage drop
        electrical = electrical * 0.7  # Significant voltage drop
        # Add high frequency noise from short bursts
        electrical += 0.1 * np.random.randn(self.seq_length)
        # Ultrasonic: short may cause mechanical vibration or temperature spike
        ultrasonic = ultrasonic * 1.1  # Slight increase in amplitude due to vibration
        # Thermal: short causes local heating
        thermal = thermal + 0.3 * np.exp(-np.linspace(0, 5, self.seq_length))  # Add heating transient
        return electrical, ultrasonic, thermal

    def _add_noise(self, signal, noise_level=0.02):
        """Add Gaussian noise to signal."""
        noise = np.random.randn(len(signal)) * noise_level
        return signal + noise