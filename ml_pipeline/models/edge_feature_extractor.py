"""
Physics-informed feature extractor for Edge Multi-Modal Battery Diagnostics.
Converts 8 raw hardware DAQ scalars into a 16-dimensional standardized physical feature vector.
Guarantees ZERO label leakage: strictly uses measurable sensor parameters.
"""

import math
from typing import Dict, Any, List, Union
import numpy as np
import torch

FEATURE_NAMES = [
    'bus_voltage_norm',         # 0: (V_bus - 3.0) / 1.2
    'current_norm',             # 1: I / 1.0
    'power_norm',               # 2: P / 4.0
    'r0_dynamic',               # 3: V_shunt / I_meas or R0 measured
    'time_of_flight_us',        # 4: ToF / 50.0 us
    'echo_amplitude',           # 5: Ultrasonic amplitude [0, 1.2]
    'phase_shift_rad',          # 6: Phase shift in radians [-pi, pi]
    'temperature_c_norm',       # 7: (T - 25.0) / 30.0
    'speed_of_sound_norm',      # 8: c_sos = (2 * 0.01 / ToF) / 3000.0
    'arrhenius_r0_norm',        # 9: R0 * exp(-Ea / (R * T)) normalized
    'acoustic_impedance_proxy', # 10: rho * c_sos * Amplitude
    'thermal_joule_ratio',      # 11: (I^2 * R0) / (dT + 0.1)
    'soc_proxy',                # 12: Estimated SOC from OCV
    'echo_energy_proxy',        # 13: Amplitude^2 * cos(phase)
    'phase_attenuation_ratio',  # 14: phase / (amplitude + 0.05)
    'temp_gradient_norm'        # 15: dT/dt / 5.0 C/s
]


def extract_16d_features_from_scalars(
    bus_voltage_v: float,
    shunt_voltage_v: float,
    current_a: float,
    power_w: float,
    time_of_flight_us: float,
    amplitude: float,
    phase_shift: float,
    temperature_c: float,
    temp_gradient_c_per_s: float = 0.10,
    cell_thickness_m: float = 0.010,
    rho_density_kg_m3: float = 2300.0
) -> np.ndarray:
    """
    Extract 16 standardized physical features from raw DAQ scalars.
    Returns:
        np.ndarray of shape (16,) with dtype float32.
    """
    # 0. Normalized bus voltage
    v_norm = (bus_voltage_v - 3.0) / 1.2
    
    # 1. Normalized current
    i_norm = current_a / 1.0
    
    # 2. Normalized power
    p_calc = power_w if abs(power_w) > 1e-4 else (bus_voltage_v * current_a)
    p_norm = p_calc / 4.0
    
    # 3. Instantaneous dynamic resistance R0 (Ohms)
    if abs(current_a) > 1e-3:
        r0 = abs(shunt_voltage_v) / abs(current_a) if abs(shunt_voltage_v) > 1e-6 else 0.045
    else:
        r0 = 0.045
    r0_clipped = float(np.clip(r0, 0.010, 0.350))
    r0_norm = (r0_clipped - 0.030) / 0.150
    
    # 4. Normalized Time of Flight
    tof_clipped = float(np.clip(time_of_flight_us, 1.0, 100.0))
    tof_norm = tof_clipped / 50.0
    
    # 5. Echo amplitude
    amp_clipped = float(np.clip(amplitude, 0.05, 1.30))
    
    # 6. Phase shift
    phase_clipped = float(np.clip(phase_shift, -3.14159, 3.14159))
    
    # 7. Normalized temperature
    temp_clipped = float(np.clip(temperature_c, 10.0, 70.0))
    temp_norm = (temp_clipped - 25.0) / 30.0
    
    # 8. Speed of Sound (m/s)
    # c = 2 * d / ToF
    sos = (2.0 * cell_thickness_m) / (tof_clipped * 1e-6)
    sos_clipped = float(np.clip(sos, 500.0, 3500.0))
    sos_norm = (sos_clipped - 1500.0) / 1500.0
    
    # 9. Arrhenius temperature-compensated resistance
    # R_scaled = R0 * exp(-Ea / (R_gas * (T + 273.15)))
    # With Ea / R_gas ~ 2500 K for Li-ion SEI / charge transfer
    t_kelvin = temp_clipped + 273.15
    arrhenius_factor = math.exp(-2500.0 / t_kelvin)
    arrhenius_r0 = r0_clipped * (arrhenius_factor / math.exp(-2500.0 / 298.15))
    arrhenius_norm = (arrhenius_r0 - 0.030) / 0.150
    
    # 10. Acoustic impedance index Z = rho * c * Amplitude
    z_ac = (rho_density_kg_m3 * sos_clipped * amp_clipped) / 1e6  # MRayl
    z_norm = (z_ac - 3.0) / 4.0
    
    # 11. Joule heating to thermal gradient ratio
    delta_t = max(0.1, temp_clipped - 25.0)
    joule_heat = (current_a ** 2) * r0_clipped
    joule_ratio = float(np.clip(joule_heat / delta_t, 0.0, 5.0)) / 2.5
    
    # 12. SOC proxy from voltage
    soc_est = float(np.clip(v_norm, 0.0, 1.0))
    
    # 13. Coherent echo energy
    echo_energy = (amp_clipped ** 2) * math.cos(phase_clipped)
    
    # 14. Phase to attenuation ratio
    phase_atten_ratio = phase_clipped / (amp_clipped + 0.05)
    
    # 15. Temperature gradient
    grad_clipped = float(np.clip(temp_gradient_c_per_s, -1.0, 10.0))
    grad_norm = grad_clipped / 5.0
    
    features = np.array([
        v_norm,
        i_norm,
        p_norm,
        r0_norm,
        tof_norm,
        amp_clipped,
        phase_clipped,
        temp_norm,
        sos_norm,
        arrhenius_norm,
        z_norm,
        joule_ratio,
        soc_est,
        echo_energy,
        phase_atten_ratio,
        grad_norm
    ], dtype=np.float32)
    
    return features


def extract_features_from_dict(frame: Dict[str, Any]) -> np.ndarray:
    """Extract 16-D feature vector from diagnostic frame dictionary."""
    v_bus = float(frame.get('electrical_voltage', 3.70))
    i_meas = float(frame.get('electrical_current', 0.50))
    p_meas = float(frame.get('electrical_power', v_bus * i_meas))
    r_meas = float(frame.get('electrical_resistance', 0.045))
    v_shunt = i_meas * r_meas
    
    tof_us = float(frame.get('ultrasonic_timeOfFlight', 8.00))
    amp = float(frame.get('ultrasonic_amplitude', 1.00))
    phase = float(frame.get('ultrasonic_phaseShift', 0.00))
    
    temp = float(frame.get('thermal_temperature', 25.0))
    dT_dt = float(frame.get('thermal_tempGradient', 0.10))
    
    return extract_16d_features_from_scalars(
        bus_voltage_v=v_bus,
        shunt_voltage_v=v_shunt,
        current_a=i_meas,
        power_w=p_meas,
        time_of_flight_us=tof_us,
        amplitude=amp,
        phase_shift=phase,
        temperature_c=temp,
        temp_gradient_c_per_s=dT_dt
    )
