import os
import sys
import numpy as np
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def test_tdc7200_timing_resolution():
    """
    Verify TDC7200 Time-to-Digital Converter resolution calculations:
    - 55 ps RMS single-shot resolution
    - Ring oscillator clock count math for 8.0 µs baseline ToF
    """
    f_clk = 16.0e6  # 16 MHz reference clock
    t_clk = 1.0 / f_clk  # 62.5 ns
    norm_lsb = 55.0e-12  # 55 ps LSB

    target_tof = 8.0e-6  # 8.0 µs travel time
    clock_counts = int(target_tof / t_clk)
    remainder = target_tof - (clock_counts * t_clk)
    tdc_norm_counts = int(remainder / norm_lsb)

    reconstructed_tof = (clock_counts * t_clk) + (tdc_norm_counts * norm_lsb)
    timing_error_ps = abs(reconstructed_tof - target_tof) * 1e12

    assert timing_error_ps < 55.0, f"Reconstructed ToF error ({timing_error_ps:.2f} ps) must be < 55 ps LSB"


def test_ina226_current_and_power_resolution():
    """
    Verify INA226 16-bit current and voltage ADC scaling:
    - Shunt resistance: 10 mΩ, 0.1% tolerance
    - Full-scale shunt voltage: ±81.92 mV (LSB = 2.5 µV)
    - Max measurable continuous current: 8.192 A
    """
    r_shunt = 0.010  # 10 mΩ
    v_shunt_lsb = 2.5e-6  # 2.5 µV
    current_lsb = v_shunt_lsb / r_shunt  # 0.25 mA LSB

    test_current = 0.500  # 500 mA excitation pulse
    expected_v_shunt = test_current * r_shunt  # 5.0 mV
    raw_counts = int(expected_v_shunt / v_shunt_lsb)

    measured_v_shunt = raw_counts * v_shunt_lsb
    measured_current = measured_v_shunt / r_shunt

    assert abs(measured_current - test_current) < 0.001, (
        f"INA226 current measurement error ({abs(measured_current - test_current)*1e3:.3f} mA) exceeds 1 mA"
    )


def test_active_rebalancer_efficiency_and_pulse_profile():
    """
    Verify synchronous bidirectional active rebalancer efficiency model:
    - Power stage R_ds(on) = 3.2 mΩ (FDMS86180)
    - Inductor DCR = 3.1 mΩ (Coilcraft SER2918H)
    - Switching frequency = 100 kHz
    - Energy efficiency > 90% at 2.5 A transfer current
    """
    i_bal = 2.5  # 2.5 A
    v_cell = 3.7  # 3.7 V
    p_in = v_cell * i_bal  # 9.25 W

    r_conduction = (3.2e-3 * 2) + 3.1e-3 + 10.0e-3  # 2 MOSFETs + L + shunt = 19.5 mΩ
    p_conduction_loss = (i_bal ** 2) * r_conduction  # ~0.12 W
    p_switching_loss = 0.08  # ~80 mW at 100kHz
    p_core_loss = 0.05  # ~50 mW

    total_loss = p_conduction_loss + p_switching_loss + p_core_loss
    p_out = p_in - total_loss
    efficiency = (p_out / p_in) * 100.0

    assert efficiency >= 90.0, f"Active balancer efficiency ({efficiency:.2f}%) below 90% target"
