#!/usr/bin/env python3
"""
EV Battery Diagnostic Host Application Runner
Supports interactive Desktop GUI mode or Headless Data Replay & Structured Logging mode.
"""

import argparse
import sys
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from host_application.src.logger import setup_logger, get_logger
from host_application.src.data_manager import DataManager
from host_application.src.ml_handler import MLHandler


def run_headless_host(duration_s: float = 1.0, samples: int = 10):
    """Run headless data buffering, ML processing, and structured logging test."""
    logger = setup_logger("ev_battery_host_cli", log_level=20)
    print("=" * 70)
    print("EV BATTERY DIAGNOSTIC SYSTEM - HOST DATA MANAGER & LOGGER")
    print("=" * 70)
    print("Initializing DataManager, MLHandler, and Structured Replay Logger...")
    
    dm = DataManager(max_buffer_size=500, record_dir="recordings")
    ml = MLHandler()
    
    print(f"Streaming and buffering multi-modal telemetry ({samples} sample frames)...\n")
    
    for count in range(1, samples + 1):
        ts = time.time()
        v = 3.82 + count * 0.001
        tof = 38.65 + (count % 3) * 0.05
        temp = 26.5 + (count % 2) * 0.1
        
        dm.add_sample(ts, v, tof, temp)
        ml.update_ml_results(mode_index=0, probability=0.98, soh=97.5)
        
        if samples > 0 and duration_s > 0:
            time.sleep(duration_s / samples)
        
    t_buf, e_buf, u_buf, th_buf = dm.get_buffers()
    print(f"[OK] Buffered {len(t_buf)} data points into circular memory.")
    ml_res = ml.get_ml_results()
    print(f"[OK] ML state: {ml_res['degradation_mode']} (SOH: {ml_res['state_of_health']:.1f}%)")
    print("[OK] Host application session completed successfully.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="EV Battery Host Application Runner")
    parser.add_argument("--gui", action="store_true", help="Launch interactive PyQt5 desktop GUI")
    parser.add_argument("--headless", action="store_true", help="Run headless telemetry buffering (default)")
    parser.add_argument("--duration", type=float, default=1.0, help="Headless test duration in seconds")
    parser.add_argument("--samples", type=int, default=10, help="Number of sample frames to process")
    args = parser.parse_args()

    if args.gui:
        try:
            from PyQt5 import QtWidgets
            from host_application.src.host_app import HostApp
            app = QtWidgets.QApplication(sys.argv)
            win = HostApp()
            win.show()
            sys.exit(app.exec_())
        except ImportError:
            print("[!] PyQt5 not installed in current environment. Running in headless mode.")
            run_headless_host(duration_s=args.duration, samples=args.samples)
    else:
        run_headless_host(duration_s=args.duration, samples=args.samples)


if __name__ == "__main__":
    main()
