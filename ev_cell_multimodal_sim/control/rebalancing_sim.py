"""
Simulator for the bidirectional DC-DC converter and active rebalancing process.
Updated to log confidence and simulate partial-failure scenarios.
"""

import numpy as np
from config import params as P
from control.decision_engine import RecoveryAction


class PIDController:
    """Simple PID controller for voltage or current regulation."""

    def __init__(self, Kp, Ki, Kd, setpoint=0, output_limits=(-100, 100)):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        self.output_limits = output_limits

        self._integral = 0
        self._prev_error = 0
        self._last_time = None

    def __call__(self, measurement, dt=None):
        if dt is None:
            if self._last_time is None:
                dt = 0
            else:
                dt = max(1e-6, 0.01)  # fallback to 10ms if time not provided

        error = self.setpoint - measurement

        # Proportional term
        P = self.Kp * error

        # Integral term
        self._integral += error * dt
        I = self.Ki * self._integral

        # Derivative term
        derivative = (error - self._prev_error) / dt if dt > 0 else 0
        D = self.Kd * derivative

        # Compute output
        output = P + I + D

        # Apply limits
        output = np.clip(output, self.output_limits[0], self.output_limits[1])

        # Update state
        self._prev_error = error
        self._last_time = dt  # store the dt used for next call (simplified)

        return output

    def reset(self):
        self._integral = 0
        self._prev_error = 0
        self._last_time = None


class RebalancingSimulator:
    """
    Simulates the application of recovery waveforms to a battery cell and
    estimates the resulting capacity recovery.
    Now includes confidence logging and partial-failure simulation.
    """

    def __init__(self):
        # Initialize controllers for different actions
        # These are simplified; in reality, we would have more detailed models.
        self.voltage_pid = PIDController(Kp=0.5, Ki=0.1, Kd=0.01, setpoint=0, output_limits=(-100, 100))
        self.current_pid = PIDController(Kp=0.4, Ki=0.05, Kd=0.005, setpoint=0, output_limits=(-100, 100))

    def apply_recovery_action(self, action, parameters, cell_soc, duration_s=None, confidence=None, fault_scenario=None):
        """
        Simulate the application of a recovery action to a cell with given SOC.
        Args:
            action: RecoveryAction enum
            parameters: dict of parameters for the action
            cell_soc: initial state of charge (fraction, 0-1)
            duration_s: duration of the action in seconds (optional, uses parameters or default)
            confidence: optional confidence value (0-1) from the model prediction, for logging
            fault_scenario: optional dict specifying a fault to simulate, e.g.,
                            {'sensor': 'ultrasonic', 'severity': 0.5}
                            where severity 0 is no fault, 1 is complete failure.
        Returns:
            dict: {
                'soc_change': change in SOC (positive for charging, negative for discharging),
                'capacity_recovered_ah': estimated capacity recovered (Ah),
                'energy_input_wh': energy input during recovery (Wh),
                'confidence': the input confidence value (if provided),
                'fault_scenario': the input fault scenario (if provided),
                'details': additional details about the simulation
            }
        """
        # If duration is not specified, use a default from parameters or a reasonable value
        if duration_s is None:
            duration_s = parameters.get('duration_s', 100)  # default 100 seconds

        # We'll simulate the cell's response to the applied current/voltage.
        # For simplicity, we'll use a simple Coulomb counting model for capacity change.
        # We'll also model the voltage response using a simple ECM, but we'll focus on the charge transfer.

        # Initialize
        dt = 0.1  # simulation time step (s)
        num_steps = int(duration_s / dt)
        time = np.arange(0, duration_s, dt)

        # Initialize SOC change
        soc_change = 0.0
        # Initialize energy input (Wh)
        energy_input_wh = 0.0

        # We'll simulate the current that flows into the cell based on the action type.
        current_a = np.zeros_like(time)  # current into the cell (positive for charging)

        if action == RecoveryAction.PULSE_DEPLATING:
            # Pulse deplating: a series of discharge pulses
            voltage = parameters.get('voltage', 4.2)  # V
            pulse_width_s = parameters.get('pulse_width_ms', 10) / 1000.0
            pulse_interval_s = parameters.get('pulse_interval_s', 1)
            num_pulses = parameters.get('num_pulses', 100)

            # We'll generate a pulse train
            for i in range(num_pulses):
                start_time = i * (pulse_width_s + pulse_interval_s)
                end_time = start_time + pulse_width_s
                if start_time >= duration_s:
                    break
                # Find indices for this pulse
                idx_start = int(start_time / dt)
                idx_end = int(end_time / dt)
                if idx_end > len(current_a):
                    idx_end = len(current_a)
                # During the pulse, we discharge at a constant current (negative)
                # We'll set the current based on the voltage and internal resistance?
                # For simplicity, we'll set a fixed discharge current.
                discharge_current = 2.0  # A (example)
                current_a[idx_start:idx_end] = -discharge_current

        elif action == RecoveryAction.EQUILIBRATION:
            # Constant current charging/discharging
            current = parameters.get('current', 0.5)  # A
            direction = parameters.get('direction', 'charge')
            if direction == 'charge':
                current_a.fill(current)
            else:
                current_a.fill(-current)

        elif action == RecoveryAction.GAS_RECOMBINATION:
            # Constant voltage charging (we'll simulate as constant current for simplicity, but note: it's not)
            voltage = parameters.get('voltage', 3.9)
            # We'll assume a current that decays as the cell charges, but for simplicity we'll use a constant current.
            current = parameters.get('current', 0.3)  # A
            current_a.fill(current)

        elif action == RecoveryAction.SHORT_ISOLATION:
            # Open circuit: no current
            current_a.fill(0.0)

        elif action == RecoveryAction.BALANCING:
            # PID control to maintain a target voltage
            target_voltage = parameters.get('target_voltage', 3.7)
            # We'll simulate the cell's voltage as a function of SOC (simplified OCV)
            # OCV = 3.0 + 0.5 * SOC (from params)
            # We'll use a simple feedback loop: if voltage < target, charge; else discharge.
            # We'll use the PID controller to determine the current.
            self.voltage_pid.setpoint = target_voltage
            self.voltage_pid.reset()
            for i in range(len(time)):
                # Estimate the cell's voltage based on current SOC (we don't have SOC dynamics yet, so we'll use initial SOC)
                # This is a simplification: we assume the voltage doesn't change significantly during the short balancing action.
                ocv = P.OCV_INTERCEPT + P.OCV_SLOPE * cell_soc
                # The terminal voltage under load: V = OCV - I * R0 (approximately)
                # We don't know I yet, so we'll use an iterative approach or assume I is small.
                # For simplicity, we'll use OCV as the voltage for feedback.
                voltage_estimate = ocv  # This is not accurate under load, but sufficient for demonstration.
                # Compute the PID output (which we interpret as a current command, scaled appropriately)
                pid_output = self.voltage_pid(voltage_estimate, dt)
                # Convert PID output to current: we'll assume a gain of 0.1 A per % output
                current_a[i] = pid_output * 0.1  # A
                # Update SOC based on this current (we'll do it after the loop)

        else:
            # Default: no action
            current_a.fill(0.0)

        # Now compute the SOC change and energy input by integrating the current and voltage.
        # We'll update SOC in steps using Coulomb counting: dSOC/dt = I / (NominalCapacity * 3600)  [if I in A, capacity in Ah]
        # Note: SOC change = (integral of I dt) / (NominalCapacity * 3600) * 100? Actually, SOC in percent:
        #   SOC_change_percent = (100 * integral(I dt)) / (NominalCapacity * 3600)
        # But we want the change in SOC as a fraction (0-1), so:
        #   SOC_change_fraction = (integral(I dt)) / (NominalCapacity * 3600)
        # We'll compute the integral of current over time.

        # We'll also compute the energy input: integrate V * I dt, where V is the terminal voltage.
        # We'll estimate the terminal voltage as OCV - I * R0 (ignoring polarization for simplicity).

        # Initialize
        soc_change_fraction = 0.0
        energy_input_j = 0.0  # Joules

        # Apply fault scenario if provided: we'll modify the cell parameters to simulate sensor degradation
        # For example, if the ultrasonic sensor is degraded, we might use a wrong SoS value in the OCV?
        # Actually, the OCV is not directly affected by ultrasonic sensor.
        # This simulator does not use ultrasonic sensor data, so we cannot simulate ultrasonic sensor fault here.
        # However, we can simulate a fault that affects the electrical sensor (e.g., wrong R0) which would affect the voltage estimate.
        # We'll adjust the R0 used in the voltage estimate based on the fault severity.
        # This is a simplified way to simulate sensor fault impact on the recovery action simulation.
        if fault_scenario is not None:
            # We'll simulate a fault in the electrical sensor (e.g., shunt measurement) by scaling R0
            # In a more complete simulator, we would have separate sensors for electrical, ultrasonic, thermal.
            # For demonstration, we'll assume the fault affects the electrical sensor reading used in the voltage estimate.
            fault_sensor = fault_scenario.get('sensor', 'electrical')
            fault_severity = fault_scenario.get('severity', 0.0)  # 0: no fault, 1: complete fault
            if fault_sensor == 'electrical':
                # Simulate an offset or gain error in the current sensor, which affects the R0 estimate
                # We'll scale the R0 used in the voltage calculation by (1 + fault_severity)
                # Note: this is a simplification.
                R0_faulty = P.R0 * (1.0 + fault_severity)
            else:
                # For other sensors, we don't have a direct model, so we ignore for now.
                R0_faulty = P.R0
        else:
            R0_faulty = P.R0

        for i in range(len(time)):
            # Current at this step
            i_t = current_a[i]
            # Estimate the terminal voltage: V = OCV - I * R0_faulty (if fault present)
            # We need the current SOC to compute OCV. We'll use the initial SOC plus the change so far.
            # This is a simplification: we assume the SOC doesn't change dramatically during the simulation.
            current_soc_estimate = cell_soc + soc_change_fraction
            if current_soc_estimate > 1.0:
                current_soc_estimate = 1.0
            if current_soc_estimate < 0.0:
                current_soc_estimate = 0.0
            ocv = P.OCV_INTERCEPT + P.OCV_SLOPE * current_soc_estimate
            v_t = ocv - i_t * R0_faulty  # V

            # Power: P = V * I (Watts)
            power_w = v_t * i_t
            # Energy for this step: E = P * dt (Joules)
            energy_input_j += power_w * dt

            # SOC change: dSOC = (I * dt) / (NominalCapacity * 3600)  [because NominalCapacity in Ah = NominalCapacity * 3600 in A*s]
            soc_change_fraction += (i_t * dt) / (P.NOMINAL_CAPACITY_AH * 3600.0)

        # Convert energy to Wh
        energy_input_wh = energy_input_j / 3600.0

        # Estimate capacity recovered: we assume that the SOC change is directly related to recoverable capacity.
        # In reality, not all SOC change leads to permanent capacity recovery, but for simulation we'll assume a fraction.
        # We'll assume that 50% of the SOC change during recovery translates to recovered capacity.
        recovery_efficiency = 0.5
        capacity_recovered_ah = abs(soc_change_fraction) * P.NOMINAL_CAPACITY_AH * recovery_efficiency

        # If the action was discharging (negative current), we might have removed capacity, but we are interested in the
        # recoverable capacity (which is positive). We'll take the absolute value for the recovered capacity.
        # However, note that for actions like pulse deplating, we are discharging to remove lithium, which can
        # recover capacity. So the capacity recovered is positive.

        result = {
            'soc_change': soc_change_fraction,  # fraction (0-1)
            'capacity_recovered_ah': capacity_recovered_ah,
            'energy_input_wh': energy_input_wh,
            'confidence': confidence,
            'fault_scenario': fault_scenario,
            'details': {
                'action': action.name if hasattr(action, 'name') else str(action),
                'duration_s': duration_s,
                'avg_current_a': np.mean(current_a),
                'energy_input_j': energy_input_j,
                'fault_applied': fault_scenario is not None
            }
        }

        return result


if __name__ == "__main__":
    # Simple test
    sim = RebalancingSimulator()
    # Test pulse deplating
    action = RecoveryAction.PULSE_DEPLATING
    params = {
        'voltage': 4.2,
        'pulse_width_ms': 10,
        'pulse_interval_s': 1,
        'num_pulses': 50
    }
    result = sim.apply_recovery_action(action, params, cell_soc=0.5, duration_s=100)
    print("Pulse deplating result:")
    print(f"  SOC change: {result['soc_change']:.4f}")
    print(f"  Capacity recovered (Ah): {result['capacity_recovered_ah']:.4f}")
    print(f"  Energy input (Wh): {result['energy_input_wh']:.2f}")
    print(f"  Confidence: {result['confidence']}")

    # Test equilibration
    action = RecoveryAction.EQUILIBRATION
    params = {
        'current': 0.5,
        'direction': 'charge',
        'duration_s': 300
    }
    result = sim.apply_recovery_action(action, params, cell_soc=0.5)
    print("\nEquilibration result:")
    print(f"  SOC change: {result['soc_change']:.4f}")
    print(f"  Capacity recovered (Ah): {result['capacity_recovered_ah']:.4f}")
    print(f"  Energy input (Wh): {result['energy_input_wh']:.2f}")

    # Test with fault scenario
    print("\n--- Testing with fault scenario ---")
    fault = {'sensor': 'electrical', 'severity': 0.5}  # 50% fault in electrical sensor
    result_fault = sim.apply_recovery_action(action, params, cell_soc=0.5, duration_s=100, confidence=0.8, fault_scenario=fault)
    print("Pulse deplating with electrical sensor fault (50% severity):")
    print(f"  SOC change: {result_fault['soc_change']:.4f}")
    print(f"  Capacity recovered (Ah): {result_fault['capacity_recovered_ah']:.4f}")
    print(f"  Energy input (Wh): {result_fault['energy_input_wh']:.2f}")
    print(f"  Confidence: {result_fault['confidence']}")
    print(f"  Fault applied: {result_fault['details']['fault_applied']}")