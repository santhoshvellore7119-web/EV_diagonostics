"""
Advanced RF Ultrasonic A-Scan Pulse-Echo Waveform Synthesizer
=============================================================
Synthesizes true 10 MHz RF ultrasonic A-scan oscillograms with:
1. Front-Wall reflection (E1 at transducer-can acoustic impedance boundary).
2. Internal Multi-Layer / Jelly-Roll reflections (E_core).
3. Localized Defect Echo Peak (E_defect: Li-plating phase inversion, gas delamination, short).
4. Back-Wall reflection (E2 at opposite wall boundary: t = ToF).
5. Analytic Envelope detection for peak timing and attenuation characterization.
"""

from typing import Dict, Any, Tuple
import numpy as np
from backend.physics_constants import (
    ULTRASONIC_FREQ_HZ,
    ULTRASONIC_PATH_LENGTH_M,
    SOS_NOMINAL,
    DEGRADATION_PHYSICS_PARAMS,
    ACOUSTIC_LAYER_IMPEDANCES
)


def compute_layer_reflection_coefficient(medium_1: str, medium_2: str) -> float:
    """
    Computes ultrasonic reflection coefficient R = (Z2 - Z1) / (Z2 + Z1)
    between two acoustic media layers based on characteristic acoustic impedance Z (MRayl).
    """
    z1 = ACOUSTIC_LAYER_IMPEDANCES.get(medium_1, 1.5)
    z2 = ACOUSTIC_LAYER_IMPEDANCES.get(medium_2, 1.5)
    if (z2 + z1) == 0:
        return 0.0
    return float((z2 - z1) / (z2 + z1))



def synthesize_rf_ascan_waveform(
    tof_us: float = 8.00,
    sos: float = 2500.0,
    degradation_mode: str = 'healthy',
    attenuation: float = 1.00,
    cell_format: str = '18650_cylindrical',
    num_samples: int = 256,
    time_max_us: float = 12.0
) -> Dict[str, Any]:
    """
    Generate an RF ultrasonic A-scan waveform and analytic envelope.
    """
    t_us = np.linspace(0.0, time_max_us, num_samples, dtype=np.float32)
    f_rf_mhz = ULTRASONIC_FREQ_HZ * 1e-6 # 10.0 MHz
    
    # Pulse width sigma
    pulse_sigma_us = 0.22 # 220 ns Gaussian pulse duration

    # 1. Front-wall echo (E1) - Transducer into metal casing boundary
    t_front_us = 0.85
    amp_front = 0.90
    e_front = amp_front * np.exp(-0.5 * ((t_us - t_front_us) / pulse_sigma_us) ** 2) * np.cos(2.0 * np.pi * f_rf_mhz * (t_us - t_front_us))

    # 2. Back-wall echo (E2) - Arrives at t = ToF
    t_back_us = max(2.0, min(time_max_us - 0.5, tof_us))
    amp_back = float(0.75 * attenuation)
    phase_back = 0.0
    if degradation_mode == 'li_plating':
        phase_back = np.pi # Phase inversion due to metallic Li layer acoustic impedance

    e_back = amp_back * np.exp(-0.5 * ((t_us - t_back_us) / pulse_sigma_us) ** 2) * np.cos(2.0 * np.pi * f_rf_mhz * (t_us - t_back_us) + phase_back)

    # 3. Internal multi-layer / jelly-roll reflections
    num_layers = 12 if 'cylindrical' in cell_format else 20
    e_internal = np.zeros_like(t_us)
    for k in range(1, num_layers):
        frac = k / num_layers
        t_k = t_front_us + frac * (t_back_us - t_front_us)
        amp_k = 0.08 * (1.0 - 0.5 * frac) * attenuation
        e_internal += amp_k * np.exp(-0.5 * ((t_us - t_k) / (pulse_sigma_us * 0.8)) ** 2) * np.sin(2.0 * np.pi * f_rf_mhz * (t_us - t_k) + k * 0.4)

    # 4. Defect Echo Peaks (Specific to degradation mode)
    e_defect = np.zeros_like(t_us)
    defect_info = {"has_defect_echo": False, "defect_type": "none", "peak_location_us": 0.0}

    if degradation_mode == 'gas_generation':
        # Gas delamination pocket creates a strong intermediate reflection and reverberation
        t_gas_us = t_front_us + 0.45 * (t_back_us - t_front_us)
        amp_gas = 0.85 # Strong acoustic impedance mismatch
        e_defect += amp_gas * np.exp(-0.5 * ((t_us - t_gas_us) / (pulse_sigma_us * 1.2)) ** 2) * np.cos(2.0 * np.pi * f_rf_mhz * (t_us - t_gas_us))
        # Reverberation tail
        e_defect += 0.45 * np.exp(-0.5 * ((t_us - (t_gas_us + 0.6)) / pulse_sigma_us) ** 2) * np.cos(2.0 * np.pi * f_rf_mhz * (t_us - (t_gas_us + 0.6)))
        defect_info = {"has_defect_echo": True, "defect_type": "Gas Delamination Pouch", "peak_location_us": float(t_gas_us)}

    elif degradation_mode == 'li_plating':
        # Metallic lithium plating deposit layer at anode/separator boundary
        t_li_us = t_front_us + 0.35 * (t_back_us - t_front_us)
        amp_li = 0.55
        e_defect += amp_li * np.exp(-0.5 * ((t_us - t_li_us) / pulse_sigma_us) ** 2) * np.cos(2.0 * np.pi * f_rf_mhz * (t_us - t_li_us) + np.pi)
        defect_info = {"has_defect_echo": True, "defect_type": "Metallic Li Dendrite Layer", "peak_location_us": float(t_li_us)}

    elif degradation_mode == 'internal_short':
        # Conductive micro-short hot spot
        t_short_us = t_front_us + 0.50 * (t_back_us - t_front_us)
        amp_short = 0.40
        e_defect += amp_short * np.exp(-0.5 * ((t_us - t_short_us) / pulse_sigma_us) ** 2) * np.cos(2.0 * np.pi * f_rf_mhz * (t_us - t_short_us))
        defect_info = {"has_defect_echo": True, "defect_type": "Conductive Short Bridge", "peak_location_us": float(t_short_us)}

    # Total RF signal + low noise floor
    noise_floor = np.random.normal(0, 0.015, num_samples).astype(np.float32)
    rf_total = (e_front + e_internal + e_defect + e_back + noise_floor).clip(-1.2, 1.2)

    # Analytic Envelope (Simple rolling absolute peak envelope)
    envelope = np.abs(rf_total)
    # Smooth envelope
    kernel = np.ones(5) / 5.0
    envelope_smooth = np.convolve(envelope, kernel, mode='same').astype(np.float32)

    return {
        "time_us": t_us.tolist(),
        "rf_signal": rf_total.tolist(),
        "envelope": envelope_smooth.tolist(),
        "front_wall_us": float(t_front_us),
        "back_wall_us": float(t_back_us),
        "tof_us": float(tof_us),
        "sos_m_per_s": float(sos),
        "defect_info": defect_info
    }
