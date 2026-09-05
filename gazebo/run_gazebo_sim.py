#!/usr/bin/env python3
"""
Gazebo Multi-Physics Simulation Runner
Launches Gazebo world or starts the high-fidelity Gazebo physics sensor bridge.
"""

import argparse
import sys
import os
import time
import json
import shutil
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from gazebo.gazebo_battery_bridge import GazeboBatteryBridge

def check_gazebo_installed() -> bool:
    """Check if Gazebo / Ign / Gz command is available in PATH."""
    return any(shutil.which(cmd) is not None for cmd in ["gz", "ign", "gazebo"])

def launch_native_gazebo(world_path: str):
    """Launch native Gazebo GUI with the battery thermal world."""
    print(f"[*] Native Gazebo detected. Launching world: {world_path}")
    if shutil.which("gz"):
        subprocess.run(["gz", "sim", world_path])
    elif shutil.which("ign"):
        subprocess.run(["ign", "gazebo", world_path])
    elif shutil.which("gazebo"):
        subprocess.run(["gazebo", world_path])

def main():
    parser = argparse.ArgumentParser(description="EV Battery Gazebo Multi-Physics Simulation Runner")
    parser.add_argument("--mode", choices=["auto", "bridge", "native"], default="auto",
                        help="Execution mode: 'auto' (native if installed, else bridge), 'bridge' (standalone sensor streamer), 'native' (launch Gazebo 3D world)")
    parser.add_argument("--rate", type=float, default=10.0, help="Bridge update rate in Hz (default: 10.0)")
    parser.add_argument("--duration", type=float, default=0.0, help="Run duration in seconds (0 = continuous)")
    parser.add_argument("--json-out", action="store_true", help="Output raw JSON stream to stdout")
    args = parser.parse_args()

    world_path = os.path.join(PROJECT_ROOT, "gazebo", "worlds", "ev_battery_thermal_world.sdf")

    if args.mode == "native" or (args.mode == "auto" and check_gazebo_installed() and not args.json_out):
        if check_gazebo_installed():
            launch_native_gazebo(world_path)
            return
        elif args.mode == "native":
            print("[!] Native Gazebo executable (gz/ign/gazebo) not found on PATH. Falling back to multi-physics bridge.")

    print("=" * 70)
    print("EV BATTERY DIAGNOSTIC SYSTEM - GAZEBO MULTI-PHYSICS SIMULATION")
    print("=" * 70)
    print(f"Mode: Multi-Physics Sensor Bridge ({args.rate} Hz)")
    print(f"World SDF: {world_path}")
    print("Simulating Coupled Thermal-Mechanical-Electrical Battery Dynamics...")
    print("Press Ctrl+C to terminate.\n")

    bridge = GazeboBatteryBridge(update_rate_hz=args.rate)
    try:
        for packet in bridge.stream_telemetry(duration_s=args.duration):
            if args.json_out:
                print(json.dumps(packet))
            else:
                el = packet['electrical']
                th = packet['thermal']
                mc = packet['mechanical']
                print(f"[T={packet['timestamp']:.2f} | Frame #{packet['frameId']:04d}] "
                      f"V: {el['voltage_v']:6.3f}V | I: {el['current_a']:6.2f}A | "
                      f"T_core: {th['core_temperature_c']:5.1f}C | Stress: {mc['stress_kpa']:5.1f}kPa | "
                      f"TOF: {mc['time_of_flight_us']:6.2f}us | Status: {packet['diagnostics']['thermal_status']}")
    except KeyboardInterrupt:
        print("\n[*] Gazebo simulation session closed cleanly.")

if __name__ == "__main__":
    main()
