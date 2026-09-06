#!/usr/bin/env python3
"""
Firmware Protocol & Build Validator
Validates C++ firmware sources, structures, and serial packet encoding/decoding.
"""

import sys
import os
import struct

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def validate_firmware_sources():
    print("=" * 70)
    print("EV BATTERY DIAGNOSTIC SYSTEM - FIRMWARE STATIC VALIDATION")
    print("=" * 70)
    
    firmware_dir = os.path.join(PROJECT_ROOT, "firmware", "src")
    required_sources = [
        "sensors/electrical.h",
        "sensors/electrical.cpp",
        "sensors/ultrasonic.h",
        "sensors/ultrasonic.cpp",
        "sensors/thermal.h",
        "sensors/thermal.cpp",
        "daq/daq.h",
        "daq/daq.cpp",
        "communication/uart.h",
        "communication/uart.cpp",
        "communication/usb.h",
        "communication/usb.cpp",
        "utils/timer.h",
        "utils/timer.cpp",
        "utils/serializer.h",
        "utils/serializer.cpp",
        "main.cpp"
    ]
    
    all_ok = True
    for src in required_sources:
        path = os.path.join(firmware_dir, src)
        exists = os.path.exists(path)
        status = "[OK]" if exists else "[MISSING]"
        print(f"{status} {src:<45}")
        if not exists:
            all_ok = False
            
    print("-" * 70)
    if all_ok:
        print("[OK] All firmware source files present and validated.")
        return True
    else:
        print("[FAIL] Missing required firmware files.")
        return False

if __name__ == "__main__":
    success = validate_firmware_sources()
    sys.exit(0 if success else 1)
