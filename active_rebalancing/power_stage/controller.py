"""
Power stage controller for bidirectional DC-DC converter.
Implements PID control for voltage or current regulation during recovery actions.
"""

import numpy as np
import time


class PID:
    """
    Simple PID controller.
    """

    def __init__(self, Kp, Ki, Kd, setpoint=0, output_limits=(0, 100)):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        self.output_limits = output_limits

        self._integral = 0
        self._prev_error = 0
        self._last_time = None

    def __call__(self, measurement, dt=None):
        """
        Calculate PID output.
        Args:
            measurement: Current process variable.
            dt: Time since last call (if None, uses internal time tracking).
        Returns:
            Control output.
        """
        if dt is None:
            if self._last_time is None:
                dt = 0
            else:
                dt = time.time() - self._last_time
                if dt <= 0:
                    dt = 1e-6

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
        self._last_time = time.time()

        return output

    def reset(self):
        """Reset controller state."""
        self._integral = 0
        self._prev_error = 0
        self._last_time = None


class BidirectionalController:
    """
    Controller for a bidirectional DC-DC converter (buck-boost).
    Can control either voltage or current, depending on the mode.
    """

    def __init__(self, voltage_pid_params=None, current_pid_params=None):
        """
        Initialize controllers.
        Args:
            voltage_pid_params: Tuple (Kp, Ki, Kd) for voltage control.
            current_pid_params: Tuple (Kp, Ki, Kd) for current control.
        """
        # Default tuning parameters (these would need to be tuned for specific hardware)
        if voltage_pid_params is None:
            voltage_pid_params = (0.5, 0.1, 0.01)
        if current_pid_params is None:
            current_pid_params = (0.4, 0.05, 0.005)

        self.voltage_pid = PID(*voltage_pid_params, setpoint=0, output_limits=(-100, 100))
        self.current_pid = PID(*current_pid_params, setpoint=0, output_limits=(-100, 100))

        # Output limits represent duty cycle percentage (-100% to 100% for bidirectional)
        # Negative duty cycle could mean reverse current direction (boost vs buck)

        self.mode = "voltage"  # or "current"
        self.enabled = False

    def set_setpoint(self, setpoint, mode="voltage"):
        """
        Set the target setpoint and control mode.
        Args:
            setpoint: Target value (voltage in volts or current in amps).
            mode: Either "voltage" or "current".
        """
        self.mode = mode
        if mode == "voltage":
            self.voltage_pid.setpoint = setpoint
            self.current_pid.setpoint = 0  # Not used, but reset
        else:
            self.current_pid.setpoint = setpoint
            self.voltage_pid.setpoint = 0

    def enable(self):
        """Enable the controller."""
        self.enabled = True
        self.voltage_pid.reset()
        self.current_pid.reset()

    def disable(self):
        """Disable the controller."""
        self.enabled = False

    def compute(self, measured_voltage, measured_current, dt=None):
        """
        Compute control output based on measurements.
        Args:
            measured_voltage: Measured voltage (V).
            measured_current: Measured current (A). Note: sign convention important.
            dt: Time step since last call (seconds). If None, computed internally.
        Returns:
            duty_cycle: Control output (-100 to 100) for the bidirectional converter.
        """
        if not self.enabled:
            return 0.0

        if self.mode == "voltage":
            output = self.voltage_pid(measured_voltage, dt)
        else:
            output = self.current_pid(measured_current, dt)

        return output

    def get_status(self):
        """Get controller status."""
        return {
            'enabled': self.enabled,
            'mode': self.mode,
            'voltage_setpoint': self.voltage_pid.setpoint,
            'current_setpoint': self.current_pid.setpoint,
            'voltage_integral': self.voltage_pid._integral,
            'current_integral': self.current_pid._integral
        }


# Example usage and simple test
if __name__ == "__main__":
    controller = BidirectionalController()
    controller.set_setpoint(3.7, mode="voltage")
    controller.enable()

    # Simulate a system where we measure voltage and adjust
    measured_voltage = 3.5
    measured_current = 0.0  # Assume we can measure current

    for i in range(20):
        duty = controller.compute(measured_voltage, measured_current)
        print(f"Step {i}: Measured V={measured_voltage:.2f}V, Duty={duty:.2f}%")
        # Simulate system response: voltage increases with positive duty (buck mode)
        # This is a very naive simulation
        measured_voltage += duty * 0.01  # Simplified
        if measured_voltage > 4.2:
            measured_voltage = 4.2
        time.sleep(0.1)