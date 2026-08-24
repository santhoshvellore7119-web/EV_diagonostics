"""
Virtual Data Acquisition (DAQ) simulator.
Updated to include configurable sensor noise and dropout/models for fault injection.
"""

import numpy as np
from config import params as P


class VirtualDAQ:
    """
    Simulates a synchronized DAQ system that samples electrical, ultrasonic,
    and thermal signals in response to an excitation pulse.
    Now includes configurable noise and fault injection for robustness testing.
    """

    def __init__(self,
                 electrical_noise_std=P.ELECTRICAL_NOISE_STD_V,
                 ultrasonic_tof_noise_std=P.ULTRASONIC_TOF_NOISE_STD_S,
                 ultrasonic_amplitude_noise_std=0.01,
                 thermal_noise_std=P.THERMAL_NOISE_STD_K,
                 dropout_probability=0.0,
                 stuck_value_probability=0.0,
                 stuck_value=0.0,
                 enable_dropout=False,
                 enable_stuck=False,
                 seed=None):
        """
        Initialize the VirtualDAQ with noise and fault injection parameters.

        Args:
            electrical_noise_std: std of Gaussian noise added to electrical voltage (V)
            ultrasonic_tof_noise_std: std of jitter in ToF measurement (s)
            ultrasonic_amplitude_noise_std: std of noise in ultrasonic amplitude (unitless)
            thermal_noise_std: std of Gaussian noise added to temperature rise (K)
            dropout_probability: probability that a sample is dropped (set to zero or previous value)
            stuck_value_probability: probability that the signal is stuck at a fixed value
            stuck_value: the value to which the signal sticks when stuck fault occurs
            enable_dropout: whether to apply dropout faults
            enable_stuck: whether to apply stuck-at-value faults
            seed: random seed for reproducibility
        """
        self.sample_rate = P.DAQ_SAMPLING_RATE_HZ
        self.adc_bits = P.ADC_BITS
        self.adc_fs_v = P.ADC_FS_V
        self.adc_q = P.ADC_Q
        self.samples_per_cycle = P.SAMPLES_PER_CYCLE

        # Noise parameters
        self.electrical_noise_std = electrical_noise_std
        self.ultrasonic_tof_noise_std = ultrasonic_tof_noise_std
        self.ultrasonic_amplitude_noise_std = ultrasonic_amplitude_noise_std
        self.thermal_noise_std = thermal_noise_std

        # Fault injection parameters
        self.dropout_probability = dropout_probability
        self.stuck_value_probability = stuck_value_probability
        self.stuck_value = stuck_value
        self.enable_dropout = enable_dropout
        self.enable_stuck = enable_stuck

        # Set random seed if provided
        if seed is not None:
            np.random.seed(seed)

        # State for dropout: we need to remember the last good value for hold-type dropout
        self._last_good_electrical = None
        self._last_good_ultrasonic_signal = None
        self._last_good_thermal = None

    def _apply_dropout(self, signal, last_good):
        """
        Apply dropout to a signal: with probability dropout_probability, set the sample to zero
        or hold the last good value (if we choose hold dropout). For simplicity, we'll set to zero.
        """
        if not self.enable_dropout or len(signal) == 0:
            return signal, last_good

        # We'll apply dropout independently to each sample
        dropped_signal = np.copy(signal)
        dropout_mask = np.random.random(len(signal)) < self.dropout_probability
        dropped_signal[dropout_mask] = 0.0  # set to zero (could also hold last value)

        # Update last_good: where we didn't drop, update last_good to the current value
        # For simplicity, we'll update last_good to the current signal where not dropped
        # But note: we are processing in real-time, so we should update as we go.
        # However, since we are processing the whole signal at once, we can simulate:
        last_good = signal.copy()
        last_good[dropout_mask] = np.nan  # mark dropped samples as not good
        # We'll return the dropped signal and the last_good (for next call) is not needed for batch processing.
        # For real-time, we would need to maintain state. We'll assume batch processing for simplicity.
        return dropped_signal, last_good

    def _apply_stuck(self, signal, value):
        """
        Apply stuck-at-value fault: with probability stuck_value_probability, set the sample to the stuck value.
        """
        if not self.enable_stuck or len(signal) == 0:
            return signal

        stuck_signal = np.copy(signal)
        stuck_mask = np.random.random(len(signal)) < self.stuck_value_probability
        stuck_signal[stuck_mask] = value
        return stuck_signal

    def sample_electrical(self, voltage_signal, current_signal=None):
        """
        Sample the electrical voltage (and optionally current) signals.
        Applies ADC quantization, configurable noise, and fault injection.
        """
        # We assume the voltage_signal is already in volts and may have noise from physics engine.
        # Apply additional configurable noise
        noisy_v = voltage_signal + np.random.normal(0, self.electrical_noise_std, size=voltage_signal.shape)

        # Apply fault injection (dropout and stuck) to the voltage signal
        if self.enable_dropout or self.enable_stuck:
            noisy_v, _ = self._apply_dropout(noisy_v, self._last_good_electrical)
            if self.enable_stuck:
                noisy_v = self._apply_stuck(noisy_v, self.stuck_value)

        # Quantize the voltage signal
        quantized_v = np.round(noisy_v / self.adc_q) * self.adc_q
        # Clip to ADC range
        quantized_v = np.clip(quantized_v, 0, self.adc_fs_v)

        if current_signal is not None:
            # For current, we apply similar noise and fault injection if needed
            noisy_i = current_signal + np.random.normal(0, self.electrical_noise_std, size=current_signal.shape)
            if self.enable_dropout or self.enable_stuck:
                noisy_i, _ = self._apply_dropout(noisy_i, self._last_good_electrical)
                if self.enable_stuck:
                    noisy_i = self._apply_stuck(noisy_i, self.stuck_value)
            # We'll skip quantization for current and just return it (as before)
            quantized_i = noisy_i
        else:
            quantized_i = None

        return quantized_v, quantized_i

    def sample_ultrasonic(self, tof, amplitude, phase_shift, ultrasonic_signal=None):
        """
        Sample the ultrasonic measurements.
        We model the ToF measurement as having jitter and the amplitude as having noise.
        Now includes configurable noise and fault injection.
        """
        # ToF: add quantization error due to sampling interval and configurable jitter
        tof_jittered = tof + np.random.normal(0, self.ultrasonic_tof_noise_std)
        tof_quantized = np.round(tof_jittered / (1/self.sample_rate)) * (1/self.sample_rate)
        # Amplitude: we assume it's measured via peak detection, so we add noise
        amplitude_noisy = amplitude + np.random.normal(0, self.ultrasonic_amplitude_noise_std)
        # Phase shift: we'll add small noise
        phase_shift_noisy = phase_shift + np.random.normal(0, 0.01)

        # Apply fault injection to the full ultrasonic signal if provided
        if ultrasonic_signal is not None:
            if self.enable_dropout or self.enable_stuck:
                ultrasonic_signal, _ = self._apply_dropout(ultrasonic_signal, self._last_good_ultrasonic_signal)
                if self.enable_stuck:
                    ultrasonic_signal = self._apply_stuck(ultrasonic_signal, self.stuck_value)

        # If we have the full signal, we could sample it, but we don't need to for this simulation.
        return tof_quantized, amplitude_noisy, phase_shift_noisy, ultrasonic_signal

    def sample_thermal(self, temperature_rise, dT_dt):
        """
        Sample the thermal signal.
        We assume we sample the temperature rise and compute the gradient from samples.
        Now includes configurable noise and fault injection.
        """
        # Apply configurable noise to the temperature rise
        noisy_temp = temperature_rise + np.random.normal(0, self.thermal_noise_std, size=temperature_rise.shape)
        if self.enable_dropout or self.enable_stuck:
            noisy_temp, _ = self._apply_dropout(noisy_temp, self._last_good_thermal)
            if self.enable_stuck:
                noisy_temp = self._apply_stuck(noisy_temp, self.stuck_value)

        # Quantize the temperature rise (assuming we have a temperature sensor with its own ADC)
        # For simplicity, we'll assume a temperature sensor with 12-bit resolution over a range of, say, -40 to 85°C.
        # But we are only simulating the rise, so we'll assume a sensor that measures 0 to 50°C rise with 12 bits.
        temp_sensor_fs_k = 50.0  # 50 K rise full scale
        temp_sensor_q = temp_sensor_fs_k / (2**self.adc_bits)
        quantized_temp = np.round(noisy_temp / temp_sensor_q) * temp_sensor_q
        quantized_temp = np.clip(quantized_temp, 0, temp_sensor_fs_k)

        # Compute gradient from the quantized temperature (using finite differences)
        # We'll use the same time step as before
        dt = 1 / self.sample_rate
        dT_dt_quantized = np.gradient(quantized_temp, dt)

        # Apply noise and fault injection to dT_dt? We'll skip for simplicity, but we could.
        # We'll just return the gradient as is (it's derived from the quantized temperature).

        return quantized_temp, dT_dt_quantized

    def process_cycle(self, raw_signals):
        """
        Process a full cycle of raw signals from the physics engine.
        Returns a dictionary of sampled and quantized signals ready for ML processing.
        Now passes through the fault injection and noise models in the individual sample methods.
        """
        # Electrical
        v_sampled, i_sampled = self.sample_electrical(
            raw_signals['electrical']['voltage'],
            raw_signals['electrical']['current']
        )
        # Ultrasonic
        tof_sampled, amp_sampled, phase_sampled, us_signal = self.sample_ultrasonic(
            raw_signals['ultrasonic']['tof'],
            raw_signals['ultrasonic']['amplitude'],
            raw_signals['ultrasonic']['phase_shift'],
            raw_signals['ultrasonic'].get('signal')
        )
        # Thermal
        temp_sampled, dT_dt_sampled = self.sample_thermal(
            raw_signals['thermal']['temperature_rise'],
            raw_signals['thermal']['dT_dt']
        )

        # Construct the output dictionary
        processed = {
            'electrical': {
                'voltage': v_sampled,
                'current': i_sampled,
                'time': raw_signals['electrical']['time']
            },
            'ultrasonic': {
                'tof': tof_sampled,
                'amplitude': amp_sampled,
                'phase_shift': phase_sampled,
                'signal': us_signal  # we keep the (potentially faulted) signal for ML if needed
            },
            'thermal': {
                'temperature_rise': temp_sampled,
                'dT_dt': dT_dt_sampled,
                'time': raw_signals['thermal']['time']
            }
        }

        return processed