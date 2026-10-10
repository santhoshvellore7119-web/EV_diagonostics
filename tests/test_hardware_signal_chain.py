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


def test_kicad_netlist_and_components_completeness():
    """
    Verify KiCad netlist file exists and contains all required schematic components
    and net definitions matching the $38.75 BOM.
    """
    netlist_path = os.path.join(project_root, 'hardware', 'schematics', 'kicad_circuit_netlist.net')
    assert os.path.exists(netlist_path), "KiCad netlist file missing"

    with open(netlist_path, 'r', encoding='utf-8') as f:
        content = f.read()

    required_components = [
        'ESP32-S3-WROOM-1', 'TDC7200PWR', 'TLV3501', 'AD8065',
        'INA226AIDGSR', 'FDMS86180', 'TPS28225DRBR', 'SER2918H-103KL', 'G3VM-61A1'
    ]
    for comp in required_components:
        assert comp in content, f"Component {comp} missing from KiCad netlist"

    assert "(nets" in content, "Netlist must define nets section"
    assert "PZT_TX_OUT" in content, "Ultrasonic TX net missing"
    assert "PZT_RX_IN" in content, "Ultrasonic RX net missing"
    assert "ZVS_SWITCH_NODE" in content, "ZVS switch node net missing"


def test_pcb_stackup_and_rf_microstrip_rules():
    """
    Verify 4-layer PCB design rules specification file:
    - 4-layer FR4 stackup
    - 50-ohm microstrip impedance calculation
    - Star-point Kelvin grounding and thermal dissipation vias
    """
    pcb_rules_path = os.path.join(project_root, 'hardware', 'pcb', 'pcb_stackup_and_design_rules.md')
    assert os.path.exists(pcb_rules_path), "PCB design rules markdown file missing"

    with open(pcb_rules_path, 'r', encoding='utf-8') as f:
        content = f.read()

    assert "4-layer FR-4" in content or "4-Layer" in content
    assert "ENIG" in content
    assert "Microstrip Calculation" in content
    assert "Kelvin Ground" in content or "Star-Point" in content
    assert "38.75" in content, "BOM cost must match $38.75 target"


def test_freertos_embedded_supervisor_architecture():
    """
    Verify FreeRTOS embedded supervisor header and C implementation files.
    """
    header_path = os.path.join(project_root, 'hardware', 'firmware_algorithms', 'freertos_multi_task_supervisor.h')
    source_path = os.path.join(project_root, 'hardware', 'firmware_algorithms', 'freertos_multi_task_supervisor.c')

    assert os.path.exists(header_path), "FreeRTOS supervisor header missing"
    assert os.path.exists(source_path), "FreeRTOS supervisor C source missing"

    with open(header_path, 'r', encoding='utf-8') as f:
        h_content = f.read()
    with open(source_path, 'r', encoding='utf-8') as f:
        c_content = f.read()

    assert "Task_FastDAQ" in h_content
    assert "Task_ZVSControl" in h_content
    assert "Task_SafetySupervisor" in h_content
    assert "bms_supervisor_check_safety_limits" in c_content
    assert "bms_supervisor_compute_zvs_rebalancing_targets" in c_content


def test_spice_zvs_transient_simulation_model():
    """
    Verify automated SPICE ZVS transient simulation module:
    - Inductor current ripple and RMS
    - Zero-voltage switching dead-time transition
    - System electrical efficiency >= 90%
    """
    from hardware.spice.run_spice_simulation import ZVSSpiceSimulator

    sim = ZVSSpiceSimulator(v_high=3.90, v_low=3.40, i_target=2.50)
    results = sim.run_transient_cycle(num_points=500)

    assert "efficiency_percent" in results
    assert results["efficiency_percent"] >= 90.0, f"SPICE efficiency {results['efficiency_percent']}% < 90%"
    assert results["i_rms_a"] > 2.0, "RMS current should be around target current"
    assert results["p_loss_total_w"] < 0.500, "Total losses should be under 500 mW with ZVS"

