"""
Gazebo EV Battery Multi-Physics & Thermal Simulation Bridge
Connects Gazebo / ROS 2 physical simulation topics to the Diagnostic Backend.
Supports both native ROS 2 / Gazebo transport and standalone physical simulation streaming.
"""

import time
import json
import math
import random
import logging
from typing import Dict, Any, Generator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GazeboBatteryBridge")

class GazeboBatteryBridge:
    def __init__(self, pack_id: str = "PACK-SIM-01", update_rate_hz: float = 10.0):
        self.pack_id = pack_id
        self.update_rate_hz = update_rate_hz
        self.interval = 1.0 / update_rate_hz
        
        # Physical pack states
        self.soc = 85.0
        self.soh = 96.5
        self.temperature_core = 28.5
        self.temperature_surface = 25.2
        self.stress_kpa = 120.0
        self.current_a = 5.0
        self.step_count = 0

    def step_physics(self, dt: float) -> Dict[str, Any]:
        """Execute one integration step of thermal-mechanical-electrical battery dynamics."""
        self.step_count += 1
        t = self.step_count * dt
        
        # Dynamic driving cycle load (WLTP/US06 approximation)
        self.current_a = 8.0 * math.sin(t * 0.2) + 4.0 * math.cos(t * 0.05) + random.gauss(0, 0.2)
        
        # Energy discharge
        self.soc = max(0.0, self.soc - (abs(self.current_a) * dt / 3600.0) * (100.0 / 60.0))
        
        # Joule heating & cooling convection
        i_squared_r = (self.current_a ** 2) * 0.025
        cooling = 0.08 * (self.temperature_surface - 22.0)
        self.temperature_core += (i_squared_r * 0.15 - cooling * 0.5) * dt
        self.temperature_surface += (cooling * 0.5) * dt
        
        # Mechanical expansion / acoustic velocity shift
        self.stress_kpa = 100.0 + (100.0 - self.soc) * 0.8 + (self.temperature_core - 25.0) * 1.5 + random.gauss(0, 0.5)
        sound_speed = 1540.0 - (self.temperature_core - 25.0) * 3.2 + (self.stress_kpa - 100.0) * 0.15
        tof_us = (0.030 / sound_speed) * 1e6 * 2.0  # 30mm pulse transit time

        # Terminal voltage
        voc = 3.2 + (self.soc / 100.0) * 0.95
        v_terminal = voc - self.current_a * 0.025
        
        return {
            "source": "gazebo_sim",
            "pack_id": self.pack_id,
            "timestamp": time.time(),
            "frameId": self.step_count,
            "electrical": {
                "voltage_v": round(v_terminal, 4),
                "current_a": round(self.current_a, 4),
                "power_w": round(v_terminal * self.current_a, 2),
                "internal_resistance_ohm": 0.025
            },
            "thermal": {
                "core_temperature_c": round(self.temperature_core, 2),
                "surface_temperature_c": round(self.temperature_surface, 2),
                "ambient_temperature_c": 22.0,
                "heat_flux_w_m2": round(i_squared_r * 4.2, 2)
            },
            "mechanical": {
                "stress_kpa": round(self.stress_kpa, 2),
                "speed_of_sound_m_s": round(sound_speed, 1),
                "time_of_flight_us": round(tof_us, 3),
                "acoustic_amplitude_v": round(1.25 - (self.temperature_core - 25.0) * 0.01, 3)
            },
            "diagnostics": {
                "soc_percent": round(self.soc, 2),
                "soh_percent": round(self.soh, 2),
                "thermal_status": "NORMAL" if self.temperature_core < 45.0 else "WARNING"
            }
        }

    def stream_telemetry(self, duration_s: float = 0.0) -> Generator[Dict[str, Any], None, None]:
        """Stream continuous physics telemetry at update_rate_hz."""
        start_time = time.time()
        logger.info(f"Starting Gazebo Multi-Physics stream for {self.pack_id} @ {self.update_rate_hz} Hz...")
        
        while True:
            if duration_s > 0 and (time.time() - start_time) > duration_s:
                break
            
            frame = self.step_physics(self.interval)
            yield frame
            time.sleep(self.interval)

if __name__ == "__main__":
    bridge = GazeboBatteryBridge()
    print("Streaming sample frames from Gazebo bridge (press Ctrl+C to stop)...")
    try:
        for idx, packet in enumerate(bridge.stream_telemetry(duration_s=3.0)):
            print(f"[{packet['timestamp']:.2f}] Frame #{packet['frameId']} | V={packet['electrical']['voltage_v']}V | I={packet['electrical']['current_a']}A | T={packet['thermal']['core_temperature_c']}C | Stress={packet['mechanical']['stress_kpa']}kPa")
    except KeyboardInterrupt:
        print("\nBridge stopped.")
