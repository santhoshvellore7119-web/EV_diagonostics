"""
capture_all_ui_features.py
Captures high-resolution 1920x1080 screenshots of each running feature view in the EV Diagnostics workstation.
"""

import os
import subprocess
import shutil
import time

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'ui_screenshots')
TEMP_PATH = r"C:\Users\Santhosh\AppData\Local\Temp\ui_capture_temp.png"

os.makedirs(OUTPUT_DIR, exist_ok=True)

TABS = [
    ("cockpit", "feature1_cockpit_overview.png", "Live Cockpit & Vector Scopes"),
    ("spme_drive_cycles", "feature2_spme_drive_cycles.png", "SPMe Radial Solid Diffusion & Drive Cycles"),
    ("tomography_pinn", "feature3_tomography_pinn.png", "2D Ultrasonic SAFT & SART Tomography"),
    ("eis_nyquist", "feature4_eis_nyquist.png", "Dynamic EIS Nyquist & DRT Tracking"),
    ("acoustic_cwi", "feature5_acoustic_cwi.png", "TDC7200 Picosecond Timing & RF Microstrip"),
    ("pack_matrix", "feature6_pack_matrix.png", "4S Pack Topology & Active Charge Shuttling"),
    ("three_d", "feature7_three_d_twin.png", "3D Thermal Cylindrical Field"),
    ("simulink", "feature8_simulink_cosim.png", "MATLAB Simulink Digital Twin"),
]

def capture_tab(hash_name, filename, label):
    url = f"http://127.0.0.1:8000/#{hash_name}"
    dest_path = os.path.join(OUTPUT_DIR, filename)
    
    if os.path.exists(TEMP_PATH):
        try:
            os.remove(TEMP_PATH)
        except Exception:
            pass

    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        f"--screenshot={TEMP_PATH}",
        "--window-size=1920,1080",
        "--virtual-time-budget=4000",
        url
    ]
    
    print(f"Capturing: {label} ({url})...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    time.sleep(1)
    if os.path.exists(TEMP_PATH):
        shutil.copyfile(TEMP_PATH, dest_path)
        size = os.path.getsize(dest_path)
        print(f"  -> Successfully captured {filename} ({size/1024:.1f} KB)")
    else:
        print(f"  -> Warning: failed to capture {filename}. Stderr: {res.stderr[:200]}")

if __name__ == "__main__":
    for hash_name, filename, label in TABS:
        capture_tab(hash_name, filename, label)
    print("All UI feature captures completed!")
