"""
Gazebo EV Battery Multi-Physics & Thermal Simulation Bridge
===========================================================
High-fidelity bridge connecting Gazebo / ROS 2 physical simulation topics to the Diagnostic Backend.
Simulates 4S1P cylindrical battery module coupled electro-thermal-acoustic dynamics, environmental disturbances
(ambient thermal transients, road vibration, contact degradation), and active rebalancing current shuttling.
"""

import sys
import os
import time
import json
import math
import random
import logging
from typing import Dict, Any, Generator, List, Optional

# Add project root and simulation paths to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
sim_dir = os.path.join(project_root, 'ev_cell_multimodal_sim')
if sim_dir not in sys.path:
    sys.path.insert(0, sim_dir)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GazeboBatteryBridge")

try:
    from common.diagnostic_schema import DiagnosticFrame
except ImportError:
    from common.diagnostic_schema import DiagnosticFrame

try:
    from ev_cell_multimodal_sim.core.physics_engine import DEGRADATION_PHYSICS_PARAMS
except ImportError:
    from core.physics_engine import DEGRADATION_PHYSICS_PARAMS


class GazeboCellState:
    """State of an individual 18650 cell within the Gazebo pack module."""
    def __init__(self, cell_id: str, soc: float = 0.50, soh: float = 98.0, degradation_mode: str = 'healthy'):
        self.cell_id = cell_id
        self.soc = soc
        self.soh = soh
        self.degradation_mode = degradation_mode
        self.temp_core = 25.0
        self.temp_surface = 25.0
        self.stress_kpa = 110.0
        self.r0 = 0.045
        self.v_terminal = 3.70
        self.current_a = 0.0
        self.tof_us = 8.0
        self.speed_of_sound = 2500.0
        self.attenuation = 1.0


class GazeboBatteryBridge:
    def __init__(self, pack_id: str = "PACK-4S1P-01", update_rate_hz: float = 10.0, ambient_temp_c: float = 25.0):
        self.pack_id = pack_id
        self.update_rate_hz = update_rate_hz
        self.interval = 1.0 / update_rate_hz
        self.ambient_temp_c = ambient_temp_c
        self.step_count = 0

        # Environmental disturbances
        self.vibration_accel_g = 0.0
        self.contact_resistance_drift = 0.001  # Ohm

        # 4S1P Battery Module Cells
        self.cells: List[GazeboCellState] = [
            GazeboCellState("CELL-01", soc=0.82, soh=97.5, degradation_mode='healthy'),
            GazeboCellState("CELL-02", soc=0.68, soh=94.0, degradation_mode='healthy'),
            GazeboCellState("CELL-03", soc=0.55, soh=91.0, degradation_mode='healthy'),
            GazeboCellState("CELL-04", soc=0.38, soh=86.5, degradation_mode='healthy')
        ]

        # Active Rebalancing Shuttle state
        self.balancing_active = True
        self.shuttle_current_a = 1.85  # A transferred from highest to lowest cell

    def set_cell_degradation(self, cell_idx: int, degradation_mode: str):
        """Inject specific degradation mode into a cell in the pack."""
        if 0 <= cell_idx < len(self.cells):
            self.cells[cell_idx].degradation_mode = degradation_mode
            logger.info(f"Gazebo Cell {self.cells[cell_idx].cell_id} set to mode: {degradation_mode}")

    def step_physics(self, dt: float) -> Dict[str, Any]:
        """Execute one integration step of coupled 4S thermal-mechanical-electrical battery dynamics."""
        self.step_count += 1
        t = self.step_count * dt

        # Dynamic ambient temperature cycling (e.g. diurnal or environmental drive cycle)
        ambient_temp = self.ambient_temp_c + 3.0 * math.sin(t * 0.02)
        
        # Mechanical road vibration (ISO 8608 profile approximation)
        self.vibration_accel_g = 0.15 * math.sin(t * 12.5) + 0.08 * math.cos(t * 35.0) + random.gauss(0, 0.02)

        # Pack-level dynamic load current (WLTP drive cycle profile)
        pack_load_current = 6.0 * math.sin(t * 0.15) + 3.0 * math.cos(t * 0.04) + random.gauss(0, 0.1)

        # Find highest and lowest SOC cells for active rebalancing
        soc_list = [c.soc for c in self.cells]
        idx_high = int(max(range(len(soc_list)), key=lambda i: soc_list[i]))
        idx_low = int(min(range(len(soc_list)), key=lambda i: soc_list[i]))
        delta_soc = soc_list[idx_high] - soc_list[idx_low]

        rebalancing_current = self.shuttle_current_a if (self.balancing_active and delta_soc > 0.05) else 0.0

        pack_voltage = 0.0

        for i, cell in enumerate(self.cells):
            # Degradation parameters from canonical physics
            params = DEGRADATION_PHYSICS_PARAMS.get(cell.degradation_mode, DEGRADATION_PHYSICS_PARAMS['healthy'])
            r0_base = params['r0'] + self.contact_resistance_drift
            sos_canonical = params['sos']
            atten_canonical = params['attenuation']

            # Cell current = load current + rebalancing shuttle current
            i_shuttle = 0.0
            if i == idx_high:
                i_shuttle = -rebalancing_current
            elif i == idx_low:
                i_shuttle = rebalancing_current * 0.924  # 92.4% ZVS converter efficiency

            cell.current_a = pack_load_current + i_shuttle

            # SOC integration (Coulomb counting with capacity = 3.0 Ah)
            cap_as = 3.0 * 3600.0
            cell.soc = max(0.01, min(0.99, cell.soc - (cell.current_a * dt) / cap_as))

            # Terminal voltage (OCV curve + IR drop + overpotential)
            voc = 3.20 + 0.95 * cell.soc - 0.15 * (1.0 - cell.soc)**2
            cell.v_terminal = voc - cell.current_a * r0_base
            cell.r0 = r0_base
            pack_voltage += cell.v_terminal

            # Coupled Thermal Dynamics: Joule heating + Rebalancing losses + Convection
            i_sq_r = (cell.current_a ** 2) * r0_base
            rebal_loss = (rebalancing_current ** 2) * 0.012 if (i == idx_high or i == idx_low) else 0.0
            total_heat_w = i_sq_r + rebal_loss

            cooling = 0.12 * (cell.temp_surface - ambient_temp)
            # Internal heat conduction to surface
            d_t_core = (total_heat_w * 0.22 - 0.08 * (cell.temp_core - cell.temp_surface)) * dt
            d_t_surf = (0.08 * (cell.temp_core - cell.temp_surface) - cooling) * dt

            if cell.degradation_mode == 'internal_short':
                d_t_core += 1.8 * dt  # Micro-short exothermic heating

            cell.temp_core += d_t_core
            cell.temp_surface += d_t_surf

            # Mechanical stress & ultrasonic acoustic wave velocity
            cell.stress_kpa = 110.0 + (1.0 - cell.soc) * 45.0 + (cell.temp_core - 25.0) * 1.8 + abs(self.vibration_accel_g) * 5.0
            cell.speed_of_sound = sos_canonical - (cell.temp_core - 25.0) * 4.5 + (cell.stress_kpa - 100.0) * 0.25
            cell.tof_us = (0.020 / max(500.0, cell.speed_of_sound)) * 1e6
            cell.attenuation = max(0.05, min(1.0, atten_canonical * (1.0 - (cell.temp_core - 25.0) * 0.008)))

            # Primary cell telemetry for DiagnosticFrame (Cell 0 or focus cell)
        primary_cell = self.cells[0]

        # Multi-Layer Acoustic Boundary Transfer Calculation (7 Layers)
        layers_z = [46.5, 1.5, 41.8, 5.2, 1.9, 12.8, 17.3]
        total_p_trans = 1.0
        for ib in range(len(layers_z) - 1):
            z1 = layers_z[ib]
            z2 = layers_z[ib + 1]
            r_ij = (z2 - z1) / (z2 + z1)
            total_p_trans *= max(1e-6, 1.0 - (r_ij ** 2))

        # Von Mises 3D Elastic Stress (Intercalation + Thermal Expansion)
        sigma_vm_kpa = primary_cell.stress_kpa * 1.08

        return {
            "source": "gazebo_sim",
            "pack_id": self.pack_id,
            "timestamp": time.time(),
            "frameId": self.step_count,
            "electrical": {
                "voltage_v": round(primary_cell.v_terminal, 4),
                "pack_voltage_v": round(pack_voltage, 3),
                "current_a": round(primary_cell.current_a, 4),
                "pack_current_a": round(pack_load_current, 3),
                "power_w": round(primary_cell.v_terminal * primary_cell.current_a, 2),
                "internal_resistance_ohm": round(primary_cell.r0, 5)
            },
            "thermal": {
                "core_temperature_c": round(primary_cell.temp_core, 2),
                "surface_temperature_c": round(primary_cell.temp_surface, 2),
                "ambient_temperature_c": round(ambient_temp, 2),
                "heat_flux_w_m2": round((primary_cell.current_a ** 2) * primary_cell.r0 * 5.0, 2)
            },
            "mechanical": {
                "stress_kpa": round(primary_cell.stress_kpa, 2),
                "sigma_von_mises_kpa": round(sigma_vm_kpa, 2),
                "speed_of_sound_m_s": round(primary_cell.speed_of_sound, 1),
                "time_of_flight_us": round(primary_cell.tof_us, 3),
                "acoustic_amplitude_v": round(primary_cell.attenuation, 3),
                "acoustic_power_throughput_pct": round(total_p_trans * 100.0, 3),
                "vibration_accel_g": round(self.vibration_accel_g, 3)
            },
            "rebalancing": {
                "active": self.balancing_active,
                "shuttle_current_a": round(rebalancing_current, 3),
                "source_cell": self.cells[idx_high].cell_id,
                "target_cell": self.cells[idx_low].cell_id,
                "delta_soc": round(delta_soc, 4),
                "efficiency_percent": 98.02
            },
            "cells": [
                {
                    "cell_id": c.cell_id,
                    "soc": round(c.soc, 3),
                    "soh": round(c.soh, 2),
                    "voltage_v": round(c.v_terminal, 3),
                    "temp_c": round(c.temp_surface, 1),
                    "stress_kpa": round(c.stress_kpa, 1),
                    "degradation_mode": c.degradation_mode
                }
                for c in self.cells
            ],
            "diagnostics": {
                "soc_percent": round(primary_cell.soc * 100.0, 2),
                "soh_percent": round(primary_cell.soh, 2),
                "thermal_status": "NORMAL" if primary_cell.temp_core < 45.0 else "WARNING"
            }
        }

    def to_ros2_topics(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Convert multi-physics packet to ROS 2 standard topics format."""
        return {
            "/ev_battery/telemetry": {
                "header": {"stamp": packet["timestamp"], "frame_id": "battery_chassis"},
                "voltage": packet["electrical"]["voltage_v"],
                "current": packet["electrical"]["current_a"],
                "temperature": packet["thermal"]["surface_temperature_c"],
                "percentage": packet["diagnostics"]["soc_percent"] / 100.0
            },
            "/ev_battery/spatial_3d_stress": {
                "stress_kpa": packet["mechanical"]["stress_kpa"],
                "sigma_vm_kpa": packet["mechanical"]["sigma_von_mises_kpa"]
            },
            "/ev_battery/acoustic_echo": {
                "time_of_flight_us": packet["mechanical"]["time_of_flight_us"],
                "amplitude_v": packet["mechanical"]["acoustic_amplitude_v"],
                "throughput_pct": packet["mechanical"]["acoustic_power_throughput_pct"]
            },
            "/ev_battery/zvs_rebalancing": {
                "active": packet["rebalancing"]["active"],
                "shuttle_current_a": packet["rebalancing"]["shuttle_current_a"],
                "efficiency_pct": packet["rebalancing"]["efficiency_percent"]
            }
        }

    def export_matlab_telemetry(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Format telemetry packet for MATLAB workspace ingestion."""
        return {
            "timestamp": packet["timestamp"],
            "V_pack": packet["electrical"]["pack_voltage_v"],
            "I_pack": packet["electrical"]["pack_current_a"],
            "T_core": packet["thermal"]["core_temperature_c"],
            "T_surf": packet["thermal"]["surface_temperature_c"],
            "Stress_VM_kPa": packet["mechanical"]["sigma_von_mises_kpa"],
            "ToF_us": packet["mechanical"]["time_of_flight_us"],
            "P_acoustic_pct": packet["mechanical"]["acoustic_power_throughput_pct"],
            "Rebal_Current_A": packet["rebalancing"]["shuttle_current_a"],
            "Cell_SOCs": [c["soc"] for c in packet["cells"]],
            "Cell_Voltages": [c["voltage_v"] for c in packet["cells"]],
        }

    def stream_telemetry(self, duration_s: float = 0.0) -> Generator[Dict[str, Any], None, None]:
        """Stream continuous physics telemetry at update_rate_hz."""
        start_time = time.time()
        logger.info(f"Starting Gazebo Coupled Multi-Physics stream for {self.pack_id} @ {self.update_rate_hz} Hz...")

        while True:
            if duration_s > 0 and (time.time() - start_time) > duration_s:
                break

            frame = self.step_physics(self.interval)
            yield frame
            time.sleep(self.interval)


if __name__ == "__main__":
    bridge = GazeboBatteryBridge()
    print("Streaming sample multi-cell frames from Gazebo bridge (press Ctrl+C to stop)...")
    try:
        for idx, packet in enumerate(bridge.stream_telemetry(duration_s=2.0)):
            print(f"[{packet['timestamp']:.2f}] Frame #{packet['frameId']} | V_pack={packet['electrical']['pack_voltage_v']}V | I_rebal={packet['rebalancing']['shuttle_current_a']}A ({packet['rebalancing']['source_cell']} -> {packet['rebalancing']['target_cell']}) | T_core={packet['thermal']['core_temperature_c']}C | Stress_VM={packet['mechanical']['sigma_von_mises_kpa']}kPa")
    except KeyboardInterrupt:
        print("\nBridge stopped.")
