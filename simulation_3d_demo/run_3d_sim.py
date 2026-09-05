#!/usr/bin/env python3
"""
3D Battery Physical Simulator Standalone Runner
Runs either interactive 3D Matplotlib/VTK physical simulation or headless background calculation.
"""

import argparse
import sys
import os
import time
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from simulation_3d_demo.ev_battery_3d_simulation import EVBattery3DSimulator

def main():
    parser = argparse.ArgumentParser(description="EV Battery 3D Physical Simulation Runner")
    parser.add_argument("--gui", action="store_true", help="Launch interactive 3D GUI window")
    parser.add_argument("--duration", type=float, default=5.0, help="Run duration in seconds (default: 5.0, 0 = infinite)")
    parser.add_argument("--json-out", action="store_true", help="Output raw JSON telemetry stream to stdout")
    args = parser.parse_args()

    headless = not args.gui
    print("=" * 70)
    print("EV BATTERY DIAGNOSTIC SYSTEM - 3D MULTI-MODAL PHYSICAL SIMULATOR")
    print("=" * 70)
    print(f"Mode: {'Interactive GUI' if args.gui else 'Headless Telemetry Engine'}")
    print("Coupled 3D Anisotropic Thermal, Elastic Stress & Acoustic Wave Propagation")
    print("=" * 70 + "\n")

    sim = EVBattery3DSimulator(headless=headless)

    if args.gui:
        print("[*] Launching interactive 3D Matplotlib visualizer...")
        sim.update_visualization()
        import matplotlib.pyplot as plt
        plt.show()
    else:
        start_time = time.time()
        step = 0
        try:
            while True:
                if args.duration > 0 and (time.time() - start_time) > args.duration:
                    break
                
                step += 1
                sim._step_count = step
                readings = sim.get_sensor_readings()
                state = sim.get_simulation_state()
                
                if args.json_out:
                    print(json.dumps({"readings": readings, "state": state}))
                else:
                    el = readings.get("electrical", {})
                    th = readings.get("thermal", {})
                    us = readings.get("ultrasonic", {})
                    print(f"[Step #{step:04d} | SOC={state.get('soc', 0.5)*100:4.1f}%] "
                          f"V: {el.get('voltage_v', 3.7):6.3f}V | I: {el.get('current_a', 0.0):6.2f}A | "
                          f"T_max: {th.get('temperature_c', 25.0):5.1f}C | "
                          f"TOF: {us.get('time_of_flight_us', 38.0):6.2f}us | "
                          f"Degradation: {state.get('degradation_mode', 'healthy')}")
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[*] 3D physical simulation stopped cleanly.")

    print("\n[OK] 3D simulation session completed successfully.")

if __name__ == "__main__":
    main()
