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


def simulate_cell_response(soc, degradation_mode, add_noise=True):
    """
    Simulate the full multi-physics response of the cell to a single excitation pulse.
    Returns dictionaries containing the simulated signals for electrical, ultrasonic, and thermal.
    """
    # Time vector for one excitation cycle
    t = np.arange(0, P.EXCITATION_PERIOD_S, 1/P.DAQ_SAMPLING_RATE_HZ)
    # Ensure we have exactly SAMPLES_PER_CYCLE points
    if len(t) > P.SAMPLES_PER_CYCLE:
        t = t[:P.SAMPLES_PER_CYCLE]
    elif len(t) < P.SAMPLES_PER_CYCLE:
        # Pad with zeros if necessary (should not happen with exact division)
        t = np.pad(t, (0, P.SAMPLES_PER_CYCLE - len(t)), 'constant')

    # Generate excitation pulse: a square pulse of current
    excitation_pulse = np.zeros_like(t)
    pulse_width_samples = int(P.EXCITATION_PULSE_WIDTH_S * P.DAQ_SAMPLING_RATE_HZ)
    if pulse_width_samples > 0:
        excitation_pulse[:pulse_width_samples] = P.EXCITATION_PULSE_AMPLITUDE_A

    # Electrical response: terminal voltage
    electrical_voltage = simulate_ecm_response(excitation_pulse, soc, t[1]-t[0])  # assume uniform dt
    # We'll also return the current for completeness (though it's known)
    electrical_current = excitation_pulse

    # Ultrasonic response: triggered at the start of the excitation pulse
    tof, amplitude, phase_shift = simulate_ultrasonic_response(
        excitation_pulse, soc, degradation_mode
    )
    # We'll simulate the entire ultrasonic waveform as a simple pulse echo for the purpose of having a signal.
    # Generate a base ultrasonic pulse (modulated Gaussian)
    # We'll create a signal that is zero except around the expected ToF.
    ultrasonic_signal = np.zeros_like(t)
    # The pulse is transmitted at t=0 and received at t=tof.
    # We'll create a pulse centered at the expected ToF with a width related to the bandwidth.
    pulse_width_samples = int(1 / P.ULTRASONIC_BANDWIDTH_HZ * P.DAQ_SAMPLING_RATE_HZ)
    pulse_width_samples = max(1, pulse_width_samples)
    tof_index = int(tof * P.DAQ_SAMPLING_RATE_HZ)
    if 0 <= tof_index < len(ultrasonic_signal):
        # Create a simple pulse: a Gaussian window
        sigma = pulse_width_samples / 4.0  # spread
        for i in range(len(ultrasonic_signal)):
            ultrasonic_signal[i] = np.exp(-0.5 * ((i - tof_index) / sigma)**2) * amplitude
    else:
        # If ToF is out of range, leave as zeros
        pass

    # Thermal response: we need to simulate the thermal transient over the excitation period
    # Note: the thermal response is slower, so we might see only the beginning of the transient.
    temperature_rise, dT_dt = simulate_thermal_response(
        excitation_pulse, soc, degradation_mode, t[1]-t[0]
    )

    # Add noise if requested
    if add_noise:
        # Electrical noise: add to voltage
        electrical_voltage += np.random.normal(0, P.ELECTRICAL_NOISE_STD_V, size=electrical_voltage.shape)
        # Ultrasonic noise: add jitter to ToF and noise to amplitude
        tof += np.random.normal(0, P.ULTRASONIC_TOF_NOISE_STD_S)
        amplitude += np.random.normal(0, 0.01)  # small noise on amplitude
        # Thermal noise: add to temperature rise
        temperature_rise += np.random.normal(0, P.THERMAL_NOISE_STD_K, size=temperature_rise.shape)
        dT_dt += np.random.normal(0, P.THERMAL_NOISE_STD_K / (t[1]-t[0]), size=dT_dt.shape)  # approximate

    # Prepare outputs
    electrical_signal = {
        'voltage': electrical_voltage,
        'current': electrical_current,
        'time': t
    }
    ultrasonic_signal = {
        'tof': tof,
        'amplitude': amplitude,
        'phase_shift': phase_shift,
        'signal': ultrasonic_signal,  # the full waveform
        'time': t
    }
    thermal_signal = {
        'temperature_rise': temperature_rise,
        'dT_dt': dT_dt,
        'time': t
    }

    return {
        'electrical': electrical_signal,
        'ultrasonic': ultrasonic_signal,
        'thermal': thermal_signal
    }


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