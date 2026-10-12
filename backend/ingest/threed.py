"""
3D simulation ingestion module.

This module interfaces with the existing 3D simulation code (ev_battery_3d_simulation.py)
and the 2-RC DynamicBatteryPhysicsEngine to extract sensor readings at each simulation step
and publish DiagnosticFrame objects with online RLS impedance, EIS, RUL, and 4S pack state.
"""

import asyncio
import json
import uuid
import random
from datetime import datetime
from typing import Optional, Dict, Any
import sys
import os
import numpy as np

# Add the simulation_3d_demo and common directories to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
sim_path = os.path.join(project_root, 'simulation_3d_demo')
if sim_path not in sys.path:
    sys.path.append(sim_path)

from common.diagnostic_schema import DiagnosticFrame

try:
    from backend.battery_physics import DynamicBatteryPhysicsEngine
except ImportError:
    from battery_physics import DynamicBatteryPhysicsEngine

try:
    from ev_battery_3d_simulation import EVBattery3DSimulator
except ImportError as e:
    print(f"Warning: Could not import EVBattery3DSimulator: {e}")
    EVBattery3DSimulator = None

try:
    from ev_cell_multimodal_sim.core.physics_engine import DEGRADATION_PHYSICS_PARAMS
except ImportError:
    from core.physics_engine import DEGRADATION_PHYSICS_PARAMS


class ThreedIngestor:
    def __init__(self, chemistry: str = 'nmc_811', form_factor: str = '18650_cylindrical',
                 soc: float = 0.5, degradation_mode: str = 'healthy',
                 ambient_temp_c: float = 25.0, load_current_c: float = 0.0,
                 cycle_count: int = 0, noise_level: float = 0.1,
                 excitation_amplitude: float = 0.5):
        """
        Initialize the 3D simulator ingestor with coupled 2-RC electro-thermal-acoustic physics.
        """
        self.simulator = None
        self.is_initialized = False
        self.frame_id_counter = 0

        self.engine = DynamicBatteryPhysicsEngine(chemistry=chemistry, form_factor=form_factor)
        self.engine.set_parameters(
            soc=soc,
            degradation_mode=degradation_mode,
            ambient_temp_c=ambient_temp_c,
            load_current_c=load_current_c,
            cycle_count=cycle_count,
            noise_level=noise_level,
            excitation_amplitude_a=excitation_amplitude,
        )

        # Default parameters (synced with frontend and engine)
        self.soc = soc
        self.degradation_mode = degradation_mode
        self.noise_level = noise_level
        self.excitation_amplitude = excitation_amplitude

    @property
    def chemistry(self) -> str:
        return self.engine.chemistry

    @chemistry.setter
    def chemistry(self, value: str):
        self.engine.set_parameters(chemistry=str(value))

    @property
    def form_factor(self) -> str:
        return self.engine.form_factor

    @form_factor.setter
    def form_factor(self, value: str):
        self.engine.set_parameters(form_factor=str(value))

    @property
    def ambient_temp_c(self) -> float:
        return self.engine.ambient_temp_c

    @ambient_temp_c.setter
    def ambient_temp_c(self, value: float):
        self.engine.set_parameters(ambient_temp_c=float(value))

    @property
    def load_current_c(self) -> float:
        return self.engine.load_current_c

    @load_current_c.setter
    def load_current_c(self, value: float):
        self.engine.set_parameters(load_current_c=float(value))

    @property
    def cycle_count(self) -> int:
        return self.engine.cycle_count

    @cycle_count.setter
    def cycle_count(self, value: int):
        self.engine.set_parameters(cycle_count=int(value))

    async def initialize(self):
        """Initialize the 3D simulator."""
        if EVBattery3DSimulator is None:
            print("EVBattery3DSimulator not available. Using simulated 3D data.")
            self.is_initialized = True
            return

        try:
            self.simulator = EVBattery3DSimulator(headless=True)
            await self.set_parameters(
                soc=self.soc,
                degradation_mode=self.degradation_mode,
                noise_level=self.noise_level,
                excitation_amplitude=self.excitation_amplitude
            )
            self.is_initialized = True
            print("3D simulator initialized")
        except Exception as e:
            print(f"Failed to initialize 3D simulator: {e}. Using simulated data.")
            self.is_initialized = True

    async def set_parameters(self, soc: Optional[float] = None,
                             degradation_mode: Optional[str] = None,
                             noise_level: Optional[float] = None,
                             excitation_amplitude: Optional[float] = None,
                             **kwargs):
        """Update simulation parameters across both 3D simulator and dynamic physics engine."""
        if soc is not None:
            self.soc = max(0.0, min(1.0, float(soc)))
            if self.simulator:
                self.simulator.soc = self.soc
        if degradation_mode is not None:
            self.degradation_mode = str(degradation_mode)
            if self.simulator:
                self.simulator.degradation_mode = self.degradation_mode
        if noise_level is not None:
            self.noise_level = max(0.0, min(1.0, float(noise_level)))
            if self.simulator:
                self.simulator.noise_level = self.noise_level
        if excitation_amplitude is not None:
            self.excitation_amplitude = max(0.0, float(excitation_amplitude))
            if self.simulator:
                self.simulator.excitation_amplitude = self.excitation_amplitude
                self.simulator.params['pulse_amplitude_a'] = self.excitation_amplitude

        engine_kwargs = dict(kwargs)
        if soc is not None:
            engine_kwargs['soc'] = self.soc
        if degradation_mode is not None:
            engine_kwargs['degradation_mode'] = self.degradation_mode
        if noise_level is not None:
            engine_kwargs['noise_level'] = self.noise_level
        if excitation_amplitude is not None:
            engine_kwargs['excitation_amplitude_a'] = self.excitation_amplitude
        self.engine.set_parameters(**engine_kwargs)

    async def get_frame(self) -> Optional[Dict[str, Any]]:
        """
        Get a frame from the 3D simulator coupled with the dynamic physics engine.
        Returns a DiagnosticFrame-compatible dictionary.
        """
        if not self.is_initialized:
            await self.initialize()

        # Propagate any direct attribute modifications on ingestor to simulator and physics engine
        if self.simulator is not None:
            self.simulator.soc = self.soc
            self.simulator.degradation_mode = self.degradation_mode
            self.simulator.noise_level = self.noise_level
            self.simulator.excitation_amplitude = self.excitation_amplitude
            self.simulator.params['pulse_amplitude_a'] = self.excitation_amplitude
        self.engine.set_parameters(
            soc=self.soc,
            degradation_mode=self.degradation_mode,
            noise_level=self.noise_level,
            excitation_amplitude_a=self.excitation_amplitude,
        )

        if EVBattery3DSimulator is None or self.simulator is None:
            return self._simulate_frame()

        try:
            readings = self.simulator.get_sensor_readings()
            sim_state = self.simulator.get_simulation_state()
            return self._convert_to_diagnostic_frame(readings, sim_state)
        except Exception as e:
            print(f"Error getting frame from 3D simulator: {e}")
            return self._simulate_frame()

    def _convert_to_diagnostic_frame(self, readings: Dict[str, Any],
                                     sim_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert 3D simulator readings and dynamic physics step to DiagnosticFrame format.
        """
        self.frame_id_counter += 1
        raw_physics = self.engine.step(dt=0.1)

        elec = readings.get('electrical', {})
        ultra = readings.get('ultrasonic', {})
        therm = readings.get('thermal', {})

        tof_s = float(ultra.get('tof', raw_physics["ultrasonic_timeOfFlight"] * 1e-6))
        tof_us = float(ultra.get('tof_us', tof_s * 1e6 if tof_s < 1.0 else tof_s))
        sos = float(ultra.get('speed_of_sound', raw_physics["ultrasonic_speedOfSound"]))
        phase_shift = float(ultra.get('phase_shift', raw_physics["ultrasonic_phaseShift"]))
        amplitude = float(ultra.get('amplitude', raw_physics["ultrasonic_amplitude"]))

        r0 = float(elec.get('resistance', elec.get('r0', raw_physics["electrical_resistance"])))
        v = float(elec.get('voltage', raw_physics["electrical_voltage"]))
        i = float(elec.get('current', raw_physics["electrical_current"]))
        power = float(elec.get('power', v * i))

        temp = float(therm.get('temperature', raw_physics["thermal_temperature"]))
        dT_dt = float(therm.get('dT_dt', raw_physics["thermal_tempGradient"]))

        mode = sim_state.get('degradation_mode', self.degradation_mode)
        ts = sim_state.get('timestamp') or datetime.now().timestamp()

        frame = {
            "timestamp": float(ts),
            "frameId": str(uuid.uuid4()),
            "source": "3d",
            "data_origin": "3D-VOXEL-PHYSICS",
            "cellId": f"cell_{self.engine.chemistry}_{self.engine.form_factor}",
            "packId": "pack_001",
            "battery_chemistry": raw_physics["chemistry"],
            "battery_chemistry_name": raw_physics["chemistry_name"],
            "battery_form_factor": raw_physics["form_factor"],
            "battery_form_factor_name": raw_physics["form_factor_name"],

            # Electrical data
            "electrical_voltage": v,
            "electrical_current": i,
            "electrical_power": power,
            "electrical_resistance": r0,
            "electrical_uncertainty": raw_physics["electrical_uncertainty"],

            # Ultrasonic data
            "ultrasonic_timeOfFlight": tof_us,
            "ultrasonic_amplitude": amplitude,
            "ultrasonic_phaseShift": phase_shift,
            "ultrasonic_speedOfSound": sos,
            "ultrasonic_uncertainty": raw_physics["ultrasonic_uncertainty"],

            # Thermal data
            "thermal_temperature": temp,
            "thermal_tempGradient": dT_dt,
            "thermal_heatFlux": raw_physics["thermal_heatFlux"],
            "thermal_uncertainty": raw_physics["thermal_uncertainty"],

            # State of Health
            "stateOfHealth_value": raw_physics["stateOfHealth_physical_ground_truth"],
            "stateOfHealth_confidenceInterval_lower": max(0.0, raw_physics["stateOfHealth_physical_ground_truth"] - 2.5),
            "stateOfHealth_confidenceInterval_upper": min(100.0, raw_physics["stateOfHealth_physical_ground_truth"] + 2.5),
            "stateOfHealth_method": "pending",

            # Degradation classification
            "degradation_mode": mode,
            "degradation_probability": 0.95,
            "degradation_perClass_healthy": 0.95 if mode == 'healthy' else 0.02,
            "degradation_perClass_li_plating": 0.95 if mode == 'li_plating' else 0.02,
            "degradation_perClass_active_material_loss": 0.95 if mode == 'active_material_loss' else 0.02,
            "degradation_perClass_electrolyte_decomposition": 0.95 if mode == 'electrolyte_decomposition' else 0.02,
            "degradation_perClass_gas_generation": 0.95 if mode == 'gas_generation' else 0.02,
            "degradation_perClass_internal_short": 0.95 if mode == 'internal_short' else 0.02,
            "degradation_entropy": 0.05,

            # Rebalancing state
            "rebalancing_state": "idle",
            "rebalancing_selectedAction": "none",
            "rebalancing_actionReason": "Pending ML results",
            "rebalancing_powerStage_targetCurrent": 0.0,
            "rebalancing_powerStage_actualCurrent": 0.0,
            "rebalancing_powerStage_targetVoltage": 0.0,
            "rebalancing_powerStage_actualVoltage": 0.0,
            "rebalancing_powerStage_pwmDutyCycle": 0.0,
            "rebalancing_executionTime": 0.0,

            # Online 2-RC ECM, EIS, RUL & 4S Pack telemetry
            "ecm_r0_est": raw_physics["ecm_r0_est"],
            "ecm_r1_est": raw_physics["ecm_r1_est"],
            "ecm_c1_est": raw_physics["ecm_c1_est"],
            "ecm_r2_est": raw_physics["ecm_r2_est"],
            "ecm_c2_est": raw_physics["ecm_c2_est"],
            "ecm_v_rc1": raw_physics["ecm_v_rc1"],
            "ecm_v_rc2": raw_physics["ecm_v_rc2"],
            "ecm_ocv_est": raw_physics["ecm_ocv_est"],
            "eis_spectrum": raw_physics["eis_spectrum"],
            "rul_remaining_cycles": raw_physics["rul_remaining_cycles"],
            "rul_knee_point_cycles": raw_physics["rul_knee_point_cycles"],
            "pack_cells": raw_physics["pack_cells"],

            # Simulation fields
            "simulation_soc": raw_physics["simulation_soc"],
            "simulation_temp_amb": raw_physics["simulation_temp_amb"],
            "simulation_load_c": raw_physics["simulation_load_c"],
            "simulation_cycle_count": raw_physics["simulation_cycle_count"],
            "simulation_excitationAmplitude": sim_state.get('excitation_amplitude', self.excitation_amplitude),
            "simulation_noiseLevel": sim_state.get('noise_level', self.noise_level),
            "simulation_stepCount": sim_state.get('step_count', self.frame_id_counter)
        }

        diag = DiagnosticFrame.from_dict(frame)
        return diag.to_dict()

    def _simulate_frame(self) -> Dict[str, Any]:
        """Simulate a frame when the 3D simulator is not available using the 2-RC physics engine."""
        self.frame_id_counter += 1
        raw_physics = self.engine.step(dt=0.1)
        mode = raw_physics["degradation_mode"]

        frame = {
            "timestamp": raw_physics["timestamp"],
            "frameId": str(uuid.uuid4()),
            "source": "3d",
            "data_origin": "3D-PHYSICS-TWIN",
            "cellId": f"cell_{self.engine.chemistry}_{self.engine.form_factor}",
            "packId": "pack_001",
            "battery_chemistry": raw_physics["chemistry"],
            "battery_chemistry_name": raw_physics["chemistry_name"],
            "battery_form_factor": raw_physics["form_factor"],
            "battery_form_factor_name": raw_physics["form_factor_name"],

            # Electrical data
            "electrical_voltage": raw_physics["electrical_voltage"],
            "electrical_current": raw_physics["electrical_current"],
            "electrical_power": raw_physics["electrical_power"],
            "electrical_resistance": raw_physics["electrical_resistance"],
            "electrical_uncertainty": raw_physics["electrical_uncertainty"],

            # Ultrasonic data
            "ultrasonic_timeOfFlight": raw_physics["ultrasonic_timeOfFlight"],
            "ultrasonic_amplitude": raw_physics["ultrasonic_amplitude"],
            "ultrasonic_phaseShift": raw_physics["ultrasonic_phaseShift"],
            "ultrasonic_speedOfSound": raw_physics["ultrasonic_speedOfSound"],
            "ultrasonic_uncertainty": raw_physics["ultrasonic_uncertainty"],

            # Thermal data
            "thermal_temperature": raw_physics["thermal_temperature"],
            "thermal_tempGradient": raw_physics["thermal_tempGradient"],
            "thermal_heatFlux": raw_physics["thermal_heatFlux"],
            "thermal_uncertainty": raw_physics["thermal_uncertainty"],

            # State of Health
            "stateOfHealth_value": raw_physics["stateOfHealth_physical_ground_truth"],
            "stateOfHealth_confidenceInterval_lower": max(0.0, raw_physics["stateOfHealth_physical_ground_truth"] - 2.5),
            "stateOfHealth_confidenceInterval_upper": min(100.0, raw_physics["stateOfHealth_physical_ground_truth"] + 2.5),
            "stateOfHealth_method": "pending",

            # Degradation classification
            "degradation_mode": mode,
            "degradation_probability": 0.95,
            "degradation_perClass_healthy": 0.95 if mode == 'healthy' else 0.02,
            "degradation_perClass_li_plating": 0.95 if mode == 'li_plating' else 0.02,
            "degradation_perClass_active_material_loss": 0.95 if mode == 'active_material_loss' else 0.02,
            "degradation_perClass_electrolyte_decomposition": 0.95 if mode == 'electrolyte_decomposition' else 0.02,
            "degradation_perClass_gas_generation": 0.95 if mode == 'gas_generation' else 0.02,
            "degradation_perClass_internal_short": 0.95 if mode == 'internal_short' else 0.02,
            "degradation_entropy": 0.05,

            # Rebalancing state
            "rebalancing_state": "idle",
            "rebalancing_selectedAction": "none",
            "rebalancing_actionReason": "Pending ML results",
            "rebalancing_powerStage_targetCurrent": 0.0,
            "rebalancing_powerStage_actualCurrent": 0.0,
            "rebalancing_powerStage_targetVoltage": 0.0,
            "rebalancing_powerStage_actualVoltage": 0.0,
            "rebalancing_powerStage_pwmDutyCycle": 0.0,
            "rebalancing_executionTime": 0.0,

            # Online 2-RC ECM, EIS, RUL & 4S Pack telemetry
            "ecm_r0_est": raw_physics["ecm_r0_est"],
            "ecm_r1_est": raw_physics["ecm_r1_est"],
            "ecm_c1_est": raw_physics["ecm_c1_est"],
            "ecm_r2_est": raw_physics["ecm_r2_est"],
            "ecm_c2_est": raw_physics["ecm_c2_est"],
            "ecm_v_rc1": raw_physics["ecm_v_rc1"],
            "ecm_v_rc2": raw_physics["ecm_v_rc2"],
            "ecm_ocv_est": raw_physics["ecm_ocv_est"],
            "eis_spectrum": raw_physics["eis_spectrum"],
            "rul_remaining_cycles": raw_physics["rul_remaining_cycles"],
            "rul_knee_point_cycles": raw_physics["rul_knee_point_cycles"],
            "pack_cells": raw_physics["pack_cells"],

            # Simulation fields
            "simulation_soc": raw_physics["simulation_soc"],
            "simulation_temp_amb": raw_physics["simulation_temp_amb"],
            "simulation_load_c": raw_physics["simulation_load_c"],
            "simulation_cycle_count": raw_physics["simulation_cycle_count"],
            "simulation_excitationAmplitude": raw_physics["simulation_excitationAmplitude"],
            "simulation_noiseLevel": raw_physics["simulation_noiseLevel"],
            "simulation_stepCount": self.frame_id_counter
        }

        diag = DiagnosticFrame.from_dict(frame)
        return diag.to_dict()


# For testing standalone
async def test_threed_ingestor():
    ingestor = ThreedIngestor()
    await ingestor.initialize()
    try:
        for i in range(5):
            frame = await ingestor.get_frame()
            if frame:
                print(f"3D frame {i}: Voltage={frame['electrical_voltage']:.2f}V, "
                      f"Degradation={frame['degradation_mode']}")
            await asyncio.sleep(0.1)
        await ingestor.set_parameters(soc=0.8, degradation_mode='li_plating', noise_level=0.2)
        for i in range(5):
            frame = await ingestor.get_frame()
            if frame:
                print(f"3D frame {i+5}: Voltage={frame['electrical_voltage']:.2f}V, "
                      f"Degradation={frame['degradation_mode']}, SOC={frame['simulation_soc']:.2f}")
            await asyncio.sleep(0.1)
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(test_threed_ingestor())