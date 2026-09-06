#!/usr/bin/env python
"""
Static verification of firmware source tree and headers.
"""

import sys
import os
import pytest

base = os.path.join(os.path.dirname(__file__), '..', 'firmware', 'src')

files_to_check = [
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
    "main.cpp",
]


@pytest.mark.parametrize("rel_path", files_to_check)
def test_firmware_file_exists_and_non_empty(rel_path):
    """Ensure each canonical firmware source file exists and has size > 0."""
    full_path = os.path.join(base, rel_path)
    assert os.path.isfile(full_path), f"Firmware file missing: {rel_path}"
    assert os.path.getsize(full_path) > 0, f"Firmware file empty: {rel_path}"


if __name__ == '__main__':
    print("Checking existence and size of firmware source files:")
    all_ok = True
    for f in files_to_check:
        try:
            test_firmware_file_exists_and_non_empty(f)
            print(f"  [OK] {f}")
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            all_ok = False
    if all_ok:
        print("\nAll firmware source files exist and are non-empty.")
    else:
        sys.exit(1)
