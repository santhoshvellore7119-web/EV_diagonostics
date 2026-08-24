import sys
import os
import os.path

base = os.path.join(os.path.dirname(__file__), '..', 'firmware', 'src')

def check_file_exists(path):
    full_path = os.path.join(base, path)
    if os.path.isfile(full_path):
        size = os.path.getsize(full_path)
        if size > 0:
            return True, f"OK ({size} bytes)"
        else:
            return False, "File is empty"
    else:
        return False, "File does not exist"

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

print("Checking existence and size of firmware source files:")
all_ok = True
for f in files_to_check:
    ok, msg = check_file_exists(f)
    if ok:
        print(f"  {f}: {msg}")
    else:
        print(f"  {f}: FAIL - {msg}")
        all_ok = False

if all_ok:
    print("\nAll firmware source files exist and are non-empty.")
else:
    print("\nSome firmware source files are missing or empty.")
    sys.exit(1)
