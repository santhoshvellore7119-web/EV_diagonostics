"""
Physics engine for simulating the electrical, ultrasonic, and thermal response
of a battery cell to an excitation pulse.
Updated to include a to_csv export function for cross-validation with MATLAB.
"""

import numpy as np
import csv
from config import params as P


def simulate_ocv(soc):
    """
    Compute Open Circuit Voltage (OCV) based on State of Charge (SOC).
    Simplified linear model: OCV = OCV_INTERCEPT + OCV_SLOPE * SOC
    """
    return P.OCV_INTERCEPT + P.OCV_SLOPE * soc


def simulate_ecm_response(current_pulse, soc, dt):
    """
    Simulate the electrical response of the battery cell using a 2RC ECM.
    current_pulse: excitation current pulse (A) as a function of time (array)
    soc: state of charge (float, 0-1)
    dt: time step (s)
    Returns:
        voltage: terminal voltage (V) as a function of time (array)
    """
    # Initialize
    n_steps = len(current_pulse)
    voltage = np.zeros(n_steps)
    # State variables for the RC pair
    voltage_c1 = 0.0  # voltage across C1

    # OCV at the beginning of the simulation (assuming SOC doesn't change significantly during the pulse)
    ocv = simulate_ocv(soc)

    for i in range(n_steps):
        # Current through R0 causes instantaneous voltage drop
        v_r0 = current_pulse[i] * P.R0
        # Update the RC branch: we have a parallel RC, so the voltage across it is the same for R1 and C1.
        # The differential equation for the RC branch: dV_RC/dt = (I - V_RC/R1) / C1
        # We'll use Euler integration.
        if i > 0:
            # Current through the RC branch is the same as the total current (since R0 is in series with the parallel RC?)
            # Actually, in a typical 2RC model, the R0 is in series with the parallel RC, so the current through R0 is the total current.
            # Then the voltage across the RC branch is the same as the voltage across C1 (and R1).
            # So the current through the RC branch is (V_RC / R1) + C1 * dV_RC/dt = I_total?
            # Let's use the standard formulation:
            # V_RC = voltage across the parallel RC
            # I_total = V_RC / R1 + C1 * dV_RC/dt
            # => dV_RC/dt = (I_total - V_RC/R1) / C1
            # Here, I_total is the excitation current (since R0 is in series, the same current flows through R0 and then splits in the RC branch?).
            # Actually, the R0 is in series with the entire cell, so the current through R0 is the same as the terminal current.
            # Then the voltage across the cell terminals is: V = OCV - I*R0 - V_RC
            # and the RC branch satisfies: I = V_RC / R1 + C1 * dV_RC/dt
            # So we can solve for V_RC.

            # We'll update V_RC using the current from the previous step? Or use the current at this step?
            # Use the current at this step for simplicity.
            i_total = current_pulse[i]
            # Euler step
            dv_rc = (i_total - voltage_c1 / P.R1) / P.C1 * dt
            voltage_c1 += dv_rc

        # Terminal voltage
        voltage[i] = ocv - v_r0 - voltage_c1

    return voltage


def simulate_ultrasonic_response(excitation_pulse, soc, degradation_mode):
    """
    Simulate the ultrasonic pulse-echo response.
    excitation_pulse: the electrical excitation pulse (A) used to trigger the ultrasonic transmitter (we assume it triggers at t=0)
    soc: state of charge (float)
    degradation_mode: string indicating the degradation mode (affects the speed of sound and attenuation)
    Returns:
        tof: time of flight (s) for the ultrasonic pulse
        amplitude: relative amplitude of the echo
        phase_shift: phase shift (radians) - we'll set to 0 for simplicity
    """
    # Base time of flight (without degradation)
    tof_base = 2 * P.ULTRASONIC_PATH_LENGTH_M / P.SOS  # round trip

    # Effect of degradation on speed of sound:
    # Different degradation modes affect the material properties and thus the speed of sound.
    # We'll use a simple multiplicative factor.
    sos_factor = 1.0
    if degradation_mode == 'li_plating':
        # Lithium plating might increase stiffness slightly -> increase SoS
        sos_factor = 1.01
    elif degradation_mode == 'active_material_loss':
        # Loss of active material might decrease density -> decrease SoS?
        sos_factor = 0.99
    elif degradation_mode == 'electrolyte_decomposition':
        # Gas generation or composition change -> decrease SoS
        sos_factor = 0.98
    elif degradation_mode == 'gas_generation':
        # Gas bubbles significantly reduce speed of sound
        sos_factor = 0.90
    elif degradation_mode == 'internal_short':
        # Local heating might increase SoS? But we'll assume a decrease due to damage
        sos_factor = 0.99
    # else: healthy, factor remains 1.0

    sos_effective = P.SOS * sos_factor
    tof = 2 * P.ULTRASONIC_PATH_LENGTH_M / sos_effective

    # Amplitude attenuation due to degradation
    amplitude_base = 1.0
    attenuation_factor = 1.0
    if degradation_mode == 'li_plating':
        # Plating might cause some scattering -> slight attenuation
        attenuation_factor = 0.98
    elif degradation_mode == 'active_material_loss':
        # Less material -> less reflection?
        attenuation_factor = 0.95
    elif degradation_mode == 'electrolyte_decomposition':
        # Composition changes -> attenuation
        attenuation_factor = 0.96
    elif degradation_mode == 'gas_generation':
        # Strong scattering and absorption by gas bubbles
        attenuation_factor = 0.70
    elif degradation_mode == 'internal_short':
        # Localized damage -> attenuation
        attenuation_factor = 0.92
    amplitude = amplitude_base * attenuation_factor

    # Phase shift: we'll set to zero for simplicity, but in reality it could be non-zero due to dispersion.
    phase_shift = 0.0

    return tof, amplitude, phase_shift


def simulate_thermal_response(current_pulse, soc, degradation_mode, dt):
    """
    Simulate the transient thermal response to the excitation pulse.
    current_pulse: excitation current pulse (A) as a function of time (array)
    soc: state of charge (float)
    degradation_mode: string indicating the degradation mode
    dt: time step (s)
    Returns:
        temperature: temperature rise above ambient (K) as a function of time (array)
        dT_dt: temperature gradient (K/s) as a function of time (array)
    """
    n_steps = len(current_pulse)
    temperature = np.zeros(n_steps)  # temperature rise above ambient
    # We'll model the cell as a thermal mass with heat loss to ambient.
    # Heat generated: I^2 * R_total * dt, where R_total includes R0 and R1 (but note: the heat generated in the ECM is I^2*R0 + I^2*R1?
    # Actually, the heat generated in the RC branch is dissipated in R1 and the energy stored in C1 is not dissipated immediately.
    # For simplicity, we'll assume all the electrical energy is converted to heat: V * I * dt, but we don't have voltage easily.
    # Alternatively, we can compute the power loss in the resistive elements: I^2 * (R0 + R1) because the energy stored in C1 is returned.
    # However, during the pulse, the energy stored in C1 is not dissipated, so we'll use I^2 * R0 for the instantaneous heat?
    # This is a simplification. We'll use the heat generated in the ohmic resistance R0 and the polarization resistance R1.
    # The power dissipated in R0 is I^2 * R0.
    # The power dissipated in R1 is I_R1^2 * R1, but we don't have I_R1 directly.
    # We'll use a simplified model: total heat generated = I^2 * (R0 + R1) * dt, which is an overestimate but acceptable for simulation.

    # Heat capacity and thermal resistance to ambient
    c_th = P.THERMAL_CAPACITY_J_PER_K
    r_th = P.THERMAL_RESISTANCE_K_PER_W

    # Initialize temperature
    temp_rise = 0.0

    for i in range(n_steps):
        # Heat generated during this time step
        # We'll use the instantaneous current squared times the sum of resistances
        heat_gen = (current_pulse[i]**2) * (P.R0 + P.R1) * dt  # Joules
        # Heat loss to ambient: (temp_rise) / r_th * dt (Watts * seconds = Joules)
        heat_loss = (temp_rise / r_th) * dt if r_th > 0 else 0
        # Update temperature rise
        temp_rise += (heat_gen - heat_loss) / c_th
        temperature[i] = temp_rise

    # Compute temperature gradient (dT/dt) using finite differences
    dT_dt = np.gradient(temperature, dt)

    return temperature, dT_dt


# Canonical Degradation Parameter Regimes
DEGRADATION_PHYSICS_PARAMS = {
    'healthy': {
        'r0': 0.045, 'r1': 0.020, 'c1': 2000.0,
        'sos': 2500.0, 'attenuation': 1.00, 'phase_shift': 0.0,
        'r_th': 2.0, 'c_th': 500.0, 'gas_reverb': False, 'nominal_soh': 95.0
    },
    'li_plating': {
        'r0': 0.052, 'r1': 0.035, 'c1': 2200.0,
        'sos': 2560.0, 'attenuation': 0.96, 'phase_shift': np.pi,
        'r_th': 2.1, 'c_th': 500.0, 'gas_reverb': False, 'nominal_soh': 88.0
    },
    'active_material_loss': {
        'r0': 0.065, 'r1': 0.048, 'c1': 1600.0,
        'sos': 2400.0, 'attenuation': 0.88, 'phase_shift': 0.0,
        'r_th': 2.2, 'c_th': 480.0, 'gas_reverb': False, 'nominal_soh': 82.0
    },
    'electrolyte_decomposition': {
        'r0': 0.078, 'r1': 0.060, 'c1': 1400.0,
        'sos': 2380.0, 'attenuation': 0.84, 'phase_shift': 0.2,
        'r_th': 2.5, 'c_th': 470.0, 'gas_reverb': False, 'nominal_soh': 80.0
    },
    'gas_generation': {
        'r0': 0.055, 'r1': 0.025, 'c1': 1900.0,
        'sos': 2100.0, 'attenuation': 0.60, 'phase_shift': 0.5,
        'r_th': 3.2, 'c_th': 450.0, 'gas_reverb': True, 'nominal_soh': 90.0
    },
    'internal_short': {
        'r0': 0.095, 'r1': 0.080, 'c1': 1200.0,
        'sos': 2420.0, 'attenuation': 0.75, 'phase_shift': 0.0,
        'r_th': 1.8, 'c_th': 500.0, 'gas_reverb': False, 'nominal_soh': 45.0
    }
}


def simulate_cell_from_parameters(
    soc: float,
    r0: float = P.R0,
    r1: float = P.R1,
    c1: float = P.C1,
    sos: float = P.SOS,
    attenuation: float = 1.0,
    r_th: float = P.THERMAL_RESISTANCE_K_PER_W,
    c_th: float = P.THERMAL_CAPACITY_J_PER_K,
    pulse_amp: float = P.EXCITATION_PULSE_AMPLITUDE_A,
    pulse_width_s: float = P.EXCITATION_PULSE_WIDTH_S,
    period_s: float = P.EXCITATION_PERIOD_S,
    sampling_rate_hz: float = P.DAQ_SAMPLING_RATE_HZ,
    add_noise: bool = True,
    phase_shift: float = 0.0,
    gas_reverb: bool = False,
    temp_ambient: float = 25.0
) -> dict:
    """
    Pure physical simulator: Computes electrical (2RC ECM), ultrasonic (pulse-echo wave),
    and thermal (transient lumped model) response strictly from physical parameter variables.
    No degradation mode string or label is ever passed to this function.
    """
    n_samples = max(10, int(sampling_rate_hz * period_s))
    t = np.linspace(0, period_s, n_samples, endpoint=False)

    # 1. Electrical ECM Response (2RC Euler integration over excitation window)
    dt_elec = 1e-5  # 10 microseconds per sample -> 2.56 ms sequence window
    pulse_samples = 80
    current_pulse = np.zeros(n_samples)
    current_pulse[:min(n_samples, pulse_samples)] = pulse_amp

    ocv = P.OCV_INTERCEPT + P.OCV_SLOPE * np.clip(soc, 0.0, 1.0)
    voltage = np.zeros(n_samples)
    v_rc1 = 0.0
    for i in range(n_samples):
        i_t = current_pulse[i]
        if i > 0:
            dv_rc1 = (i_t - v_rc1 / max(1e-4, r1)) / max(0.01, c1 * 1e-3) * dt_elec
            v_rc1 += dv_rc1
        voltage[i] = ocv - i_t * r0 - v_rc1

    # 2. Ultrasonic Pulse-Echo Waveform (10 MHz DAQ sampling resolution: 0.1 us per sample)
    dt_ultra = 1e-7
    tof = 2.0 * P.ULTRASONIC_PATH_LENGTH_M / max(100.0, sos)
    tof_idx = int(tof / dt_ultra)

    ultrasonic_signal = np.zeros(n_samples)
    tx_sigma = 4.0
    for i in range(min(n_samples, int(tx_sigma * 6))):
        ultrasonic_signal[i] += np.exp(-0.5 * (i / tx_sigma) ** 2) * 1.0

    rx_sigma = tx_sigma * 1.2
    phase_sign = -1.0 if np.abs(phase_shift - np.pi) < 0.5 else 1.0
    if 0 <= tof_idx < n_samples:
        i_min = max(0, int(tof_idx - 4 * rx_sigma))
        i_max = min(n_samples, int(tof_idx + 4 * rx_sigma))
        for i in range(i_min, i_max):
            ultrasonic_signal[i] += phase_sign * attenuation * np.exp(-0.5 * ((i - tof_idx) / rx_sigma) ** 2)

    if gas_reverb:
        for mult, att_mult in [(1.45, 0.40), (1.90, 0.25)]:
            rev_idx = int((tof * mult) / dt_ultra)
            if 0 <= rev_idx < n_samples:
                i_min = max(0, int(rev_idx - 4 * rx_sigma))
                i_max = min(n_samples, int(rev_idx + 4 * rx_sigma))
                for i in range(i_min, i_max):
                    ultrasonic_signal[i] += att_mult * attenuation * np.exp(-0.5 * ((i - rev_idx) / rx_sigma) ** 2)

    # 3. Thermal Transient Response (Lumped Parameter Thermal Model)
    base_temp_rise = (r0 + r1) * (pulse_amp ** 2) * r_th * 30.0 + max(0.0, temp_ambient - 25.0)
    temperature_rise = np.zeros(n_samples)
    temp_rise = 0.0
    dt_therm = 1e-4
    for i in range(n_samples):
        i_t = current_pulse[i]
        heat_gen = (i_t ** 2) * (r0 + r1) * 50.0 * dt_therm
        heat_loss = (temp_rise / max(0.1, r_th)) * dt_therm
        temp_rise += (heat_gen - heat_loss) / max(0.1, c_th * 1e-2)
        temperature_rise[i] = base_temp_rise + temp_rise
    dT_dt = np.gradient(temperature_rise, dt_therm) if n_samples > 1 else np.zeros(n_samples)

    # 4. Add Sensor Noise if specified
    if add_noise:
        voltage += np.random.normal(0, 0.003, size=voltage.shape)
        tof += float(np.random.normal(0, 0.05e-6))
        attenuation += float(np.random.normal(0, 0.015))
        ultrasonic_signal += np.random.normal(0, 0.015, size=ultrasonic_signal.shape)
        temperature_rise += np.random.normal(0, 0.05, size=temperature_rise.shape)
        dT_dt += np.random.normal(0, 0.05 / max(1e-6, dt_therm), size=dT_dt.shape)

    return {
        'electrical': {
            'voltage': voltage,
            'current': current_pulse,
            'time': t
        },
        'ultrasonic': {
            'tof': tof,
            'amplitude': attenuation,
            'phase_shift': phase_shift,
            'signal': ultrasonic_signal,
            'time': t
        },
        'thermal': {
            'temperature_rise': temperature_rise,
            'dT_dt': dT_dt,
            'time': t
        }
    }


def simulate_cell_response(soc, degradation_mode='healthy', add_noise=True):
    """
    Simulate full multi-physics response by looking up canonical physical parameter regime
    and executing the pure parameter physics simulator.
    """
    params = DEGRADATION_PHYSICS_PARAMS.get(degradation_mode, DEGRADATION_PHYSICS_PARAMS['healthy'])
    return simulate_cell_from_parameters(
        soc=soc,
        r0=params['r0'],
        r1=params['r1'],
        c1=params['c1'],
        sos=params['sos'],
        attenuation=params['attenuation'],
        r_th=params['r_th'],
        c_th=params['c_th'],
        phase_shift=params.get('phase_shift', 0.0),
        gas_reverb=params.get('gas_reverb', False),
        add_noise=add_noise
    )


def to_csv(soc, degradation_mode, add_noise=True, filename=None):
    """
    Export the simulated cell response for one excitation pulse to a CSV file.
    The CSV format matches what the MATLAB repository's comparison script expects:
        time_s, electrical_v, ultrasonic_v, thermal_k
    where:
        time_s: time in seconds
        electrical_v: electrical voltage (V)
        ultrasonic_v: ultrasonic signal amplitude (V) - we'll use the ultrasonic signal
        thermal_k: temperature rise above ambient (K)
    Args:
        soc: state of charge (float, 0-1)
        degradation_mode: string indicating the degradation mode
        add_noise: boolean whether to add noise (default: True)
        filename: optional filename to save to. If not provided, returns the data as a tuple.
    Returns:
        If filename is None, returns (time, electrical_voltage, ultrasonic_signal, temperature_rise)
        Otherwise, writes to the CSV file and returns None.
    """
    # Get the simulated signals
    results = simulate_cell_response(soc, degradation_mode, add_noise)
    electrical = results['electrical']
    ultrasonic = results['ultrasonic']
    thermal = results['thermal']

    # Extract the data we need for the CSV
    time_s = electrical['time']
    electrical_v = electrical['voltage']  # in volts
    # For ultrasonic, we have the signal waveform (not just a scalar). We'll use the signal.
    ultrasonic_v = ultrasonic['signal']   # in volts (assuming the signal is in volts)
    thermal_k = thermal['temperature_rise']  # in K (rise above ambient)

    # If filename is provided, write to CSV
    if filename is not None:
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(['time_s', 'electrical_v', 'ultrasonic_v', 'thermal_k'])
            # Write data rows
            for i in range(len(time_s)):
                writer.writerow([time_s[i], electrical_v[i], ultrasonic_v[i], thermal_k[i]])
        return None
    else:
        return time_s, electrical_v, ultrasonic_v, thermal_k