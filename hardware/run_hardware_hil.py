#!/usr/bin/env python3
"""
Hardware-in-the-Loop (HIL) & ESP32 Firmware Telemetry Test Bench
Simulates physical AFE (Analog Front End), ultrasonic piezoceramic pulser-receiver,
and ESP32 FreeRTOS communication interface.
"""

import argparse
import sys
import os
import time
import struct
import random
import math
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

class HardwareHILTestBench:
    def __init__(self, port: str = "VIRTUAL_COM1", baud: int = 115200, rate_hz: float = 10.0):
        self.port = port
        self.baud = baud
        self.rate_hz = rate_hz
        self.interval = 1.0 / rate_hz
        self.frame_id = 0
        
        # AFE and physical states
        self.v_cell = 3.850 # V
        self.i_cell = 2.450 # A
        self.t_ntc1 = 28.40 # C
        self.t_ntc2 = 27.90 # C
        self.tof_us = 38.65 # us
        self.amplitude_v = 1.15 # V
        self.rebalancing_active = False
        self.active_pwm_duty = 0

    def process_command(self, cmd_str: str) -> str:
        """Process incoming serial command from host application or backend."""
        cmd = cmd_str.strip().upper()
        if "REBALANCE_ON" in cmd:
            self.rebalancing_active = True
            self.active_pwm_duty = 45
            return "[HIL_ACK] Active rebalancing power stage ENGAGED (PWM: 45%)"
        elif "REBALANCE_OFF" in cmd:
            self.rebalancing_active = False
            self.active_pwm_duty = 0
            return "[HIL_ACK] Active rebalancing power stage DISENGAGED"
        elif "RESET_AFE" in cmd:
            self.v_cell = 3.850
            self.i_cell = 0.0
            return "[HIL_ACK] AFE hardware registers reset to default"
        return f"[HIL_ERR] Unknown command: {cmd}"

    def step_telemetry(self) -> dict:
        """Generate one physical telemetry frame with realistic ADC noise and quantization."""
        self.frame_id += 1
        t = self.frame_id * self.interval
        
        # Simulated electrical load
        self.i_cell = 3.5 * math.sin(t * 0.3) + random.gauss(0, 0.05)
        self.v_cell = 3.85 - (self.i_cell * 0.028) + random.gauss(0, 0.003)
        
        # Temperature sensor drift (NTC Thermistors)
        self.t_ntc1 += (abs(self.i_cell) * 0.015 - 0.01 * (self.t_ntc1 - 25.0)) * self.interval
        self.t_ntc2 = self.t_ntc1 - 0.4 + random.gauss(0, 0.02)
        
        # Ultrasonic transducer response
        self.tof_us = 38.50 + (self.t_ntc1 - 25.0) * 0.08 + random.gauss(0, 0.01)
        self.amplitude_v = 1.20 - (self.t_ntc1 - 25.0) * 0.005 + random.gauss(0, 0.01)

        packet = {
            "source": "esp32_hardware_hil",
            "frameId": self.frame_id,
            "timestamp": time.time(),
            "port": self.port,
            "baudrate": self.baud,
            "afe_status": {
                "voltage_v": round(self.v_cell, 4),
                "current_a": round(self.i_cell, 4),
                "temperature_ntc1_c": round(self.t_ntc1, 2),
                "temperature_ntc2_c": round(self.t_ntc2, 2),
                "adc_raw_v": int((self.v_cell / 5.0) * 4095),
                "adc_raw_i": int(((self.i_cell + 20.0) / 40.0) * 4095)
            },
            "ultrasonic_afe": {
                "tof_us": round(self.tof_us, 3),
                "amplitude_v": round(self.amplitude_v, 3),
                "phase_deg": round(45.2 + math.sin(t * 0.1) * 2.0, 2),
                "pulse_frequency_khz": 1000.0
            },
            "power_stage": {
                "rebalancing_active": self.rebalancing_active,
                "pwm_duty_percent": self.active_pwm_duty,
                "switching_freq_khz": 100.0
            }
        }
        return packet

def run_hil_session(duration_s: float = 0.0, rate_hz: float = 10.0, json_out: bool = False):
    """Run interactive Hardware-in-the-Loop test bench session."""
    print("=" * 75)
    print("EV BATTERY DIAGNOSTIC SYSTEM - HARDWARE-IN-THE-LOOP (HIL) TEST BENCH")
    print("=" * 75)
    print(f"Target Hardware: ESP32-WROOM-32 (Dual Core 240MHz, FreeRTOS)")
    print(f"AFE Emulation: TI ADS1115 (16-bit ADC) + AD8302 Ultrasonic Phase Detector")
    print(f"Sampling Frequency: {rate_hz} Hz | Baud Rate: 115200 bps")
    print("Press Ctrl+C to terminate.\n")

    hil = HardwareHILTestBench(rate_hz=rate_hz)
    start_time = time.time()
    
    try:
        while True:
            if duration_s > 0 and (time.time() - start_time) > duration_s:
                break
            
            frame = hil.step_telemetry()
            if json_out:
                print(json.dumps(frame))
            else:
                afe = frame["afe_status"]
                us = frame["ultrasonic_afe"]
                pwr = frame["power_stage"]
                print(f"[T={frame['timestamp']:.2f} | Frame #{frame['frameId']:04d}] "
                      f"V_cell: {afe['voltage_v']:6.3f}V | I_cell: {afe['current_a']:6.2f}A | "
                      f"T1: {afe['temperature_ntc1_c']:5.1f}C | TOF: {us['tof_us']:6.2f}us | "
                      f"Ampl: {us['amplitude_v']:5.2f}V | Rebal: {'ACTIVE' if pwr['rebalancing_active'] else 'IDLE'}")
            
            time.sleep(hil.interval)
    except KeyboardInterrupt:
        print("\n[*] Hardware-in-the-Loop session completed cleanly.")

def main():
    parser = argparse.ArgumentParser(description="EV Battery Hardware-in-the-Loop (HIL) Runner")
    parser.add_argument("--rate", type=float, default=10.0, help="AFE sampling rate in Hz (default: 10.0)")
    parser.add_argument("--duration", type=float, default=0.0, help="Run duration in seconds (0 = continuous)")
    parser.add_argument("--json-out", action="store_true", help="Output raw JSON serial packet stream")
    args = parser.parse_args()

    run_hil_session(duration_s=args.duration, rate_hz=args.rate, json_out=args.json_out)

if __name__ == "__main__":
    main()
