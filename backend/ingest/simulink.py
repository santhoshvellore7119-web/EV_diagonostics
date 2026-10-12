"""
Simulink ingestion module using FMI/FMPy library for co-simulation FMU.

This module loads an exported FMU from Simulink, steps through the simulation,
and converts output variables to DiagnosticFrame objects.
Supports genuine FMU co-simulation execution (FMU2Slave) and coupled 2-RC physical mode.
"""

import asyncio
import json
import uuid
import random
from datetime import datetime
from typing import Optional, Dict, Any, List
import numpy as np
import os, sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.diagnostic_schema import DiagnosticFrame
from backend.physics_constants import (
    DEGRADATION_PHYSICS_PARAMS, OCV_BASE, OCV_SLOPE,
    R0_NOMINAL, R1_NOMINAL, C1_NOMINAL,
    SOS_NOMINAL, ULTRASONIC_PATH_LENGTH_M,
    THERMAL_CAPACITY_J_PER_K, THERMAL_RESISTANCE_K_PER_W
)

try:
    from backend.battery_physics import DynamicBatteryPhysicsEngine
except ImportError:
    from battery_physics import DynamicBatteryPhysicsEngine

try:
    import fmpy
    from fmpy import read_model_description, extract
    from fmpy.fmi2 import FMU2Slave
except ImportError:
    fmpy = None


class SimulinkIngestor:
    def __init__(self, fmu_path: str = "", soc: float = 0.5, excitation_amplitude: float = 0.5,
                 degradation_mode: str = "healthy", noise_level: float = 0.05,
                 chemistry: str = "nmc_811", form_factor: str = "18650_cylindrical",
                 ambient_temp_c: float = 25.0, load_current_c: float = 0.0,
                 cycle_count: int = 0):
        """
        Initialize the Simulink ingestor.

        Args:
            fmu_path: Path to the exported FMU file.
            soc: Initial state of charge (0-1).
            excitation_amplitude: Excitation pulse amplitude (A).
            degradation_mode: Simulated degradation mode.
            noise_level: Gaussian noise factor.
        """
        self.fmu_path = fmu_path
        self._soc = soc
        self._excitation_amplitude = excitation_amplitude
        self._degradation_mode = degradation_mode
        self._noise_level = noise_level
        self.fmu = None
        self.unzipdir = None
        self.model_description = None
        self.value_references = {}
        self.is_initialized = False
        self.time = 0.0
        self.step_size = 0.005  # 5 ms step
        self.frame_id_counter = 0
        self.data_origin = "FALLBACK"

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

        # Variables to store latest outputs from FMU
        self.latest_outputs = {}

    @property
    def degradation_mode(self) -> str:
        return self._degradation_mode

    @degradation_mode.setter
    def degradation_mode(self, value: str):
        self._degradation_mode = str(value)
        self.engine.set_parameters(degradation_mode=str(value))

    @property
    def soc(self) -> float:
        return self._soc

    @soc.setter
    def soc(self, value: float):
        self._soc = max(0.0, min(1.0, float(value)))
        self.engine.set_parameters(soc=self._soc)

    @property
    def noise_level(self) -> float:
        return self._noise_level

    @noise_level.setter
    def noise_level(self, value: float):
        self._noise_level = max(0.0, min(1.0, float(value)))
        self.engine.set_parameters(noise_level=self._noise_level)

    @property
    def excitation_amplitude(self) -> float:
        return self._excitation_amplitude

    @excitation_amplitude.setter
    def excitation_amplitude(self, value: float):
        self._excitation_amplitude = max(0.0, float(value))
        self.engine.set_parameters(excitation_amplitude_a=self._excitation_amplitude)

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

    async def set_parameters(self, **kwargs):
        """Update Simulink simulation parameters dynamically."""
        if 'soc' in kwargs and kwargs['soc'] is not None:
            self.soc = float(kwargs['soc'])
        if 'degradation_mode' in kwargs and kwargs['degradation_mode'] is not None:
            self.degradation_mode = str(kwargs['degradation_mode'])
        if 'noise_level' in kwargs and kwargs['noise_level'] is not None:
            self.noise_level = float(kwargs['noise_level'])
        if 'excitation_amplitude' in kwargs and kwargs['excitation_amplitude'] is not None:
            self.excitation_amplitude = float(kwargs['excitation_amplitude'])
        self.engine.set_parameters(**kwargs)

    async def initialize(self):
        """Initialize the FMU co-simulation instance or physical fallback."""
        if not self.fmu_path or not os.path.exists(self.fmu_path):
            self.data_origin = "FALLBACK"
            self.is_initialized = True
            return

        if fmpy is None:
            self.data_origin = "FALLBACK"
            self.is_initialized = True
            return

        try:
            self.model_description = read_model_description(self.fmu_path)
            self.unzipdir = extract(self.fmu_path)

            # Map scalar variables from modelDescription.xml
            for variable in self.model_description.modelVariables:
                self.value_references[variable.name] = variable.valueReference

            # Instantiate FMU co-simulation slave
            self.fmu = FMU2Slave(
                guid=self.model_description.guid,
                unzipDirectory=self.unzipdir,
                modelIdentifier=self.model_description.coSimulation.modelIdentifier,
                instanceName='ev_cell_digital_twin_slave'
            )
            self.fmu.instantiate()
            self.fmu.setupExperiment(startTime=0.0, stopTime=100.0, tolerance=1e-4)
            self.fmu.enterInitializationMode()
            self.fmu.exitInitializationMode()
            self.data_origin = "FMU"
            self.is_initialized = True
        except Exception:
            self.data_origin = "FALLBACK"
            self.is_initialized = True

    async def terminate(self):
        """Terminate the FMU instance."""
        if self.fmu is not None:
            try:
                self.fmu.terminate()
                self.fmu.freeInstance()
            except Exception:
                pass
            self.fmu = None
        self.is_initialized = False

    async def step(self) -> Optional[Dict[str, Any]]:
        """
        Perform one simulation step and return a DiagnosticFrame.
        """
        if not self.is_initialized:
            await self.initialize()

        if self.fmu is None or self.data_origin == "FALLBACK":
            return self._simulate_frame()

        try:
            # Step the real FMU co-simulation model
            self.fmu.doStep(
                currentCommunicationPoint=self.time,
                communicationStepSize=self.step_size
            )
            self.time += self.step_size

            # Extract variable outputs
            outputs = {}
            for name, vr in self.value_references.items():
                val = self.fmu.getReal([vr])[0]
                outputs[name] = val

            self.latest_outputs = outputs
            return self._convert_to_diagnostic_frame(outputs)
        except Exception:
            return self._simulate_frame()

    def _convert_to_diagnostic_frame(self, outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Convert FMU outputs to DiagnosticFrame format."""
        raw_physics = self.engine.step(dt=self.step_size)
        mode = self.degradation_mode
        phys = DEGRADATION_PHYSICS_PARAMS.get(mode, DEGRADATION_PHYSICS_PARAMS['healthy'])
        r0 = float(outputs.get("r0_cell", outputs.get("r0", phys['r0'])))
        tof_us = float(outputs.get("tof_cell", (2.0 * ULTRASONIC_PATH_LENGTH_M / phys['sos']) * 1e6))
        sos = float(outputs.get("c_cell", phys['sos']))
        temp = float(outputs.get("t_cell", 25.0))
        volt = float(outputs.get("v_cell", OCV_BASE + OCV_SLOPE * self.soc - self.excitation_amplitude * r0))

        frame = {
            "timestamp": datetime.now().timestamp(),
            "frameId": str(uuid.uuid4()),
            "source": "simulink",
            "data_origin": "FMU",
            "cellId": f"cell_{self.engine.chemistry}_{self.engine.form_factor}",
            "packId": "pack_001",
            "battery_chemistry": raw_physics["chemistry"],
            "battery_chemistry_name": raw_physics["chemistry_name"],
            "battery_form_factor": raw_physics["form_factor"],
            "battery_form_factor_name": raw_physics["form_factor_name"],

            # Electrical data
            "electrical_voltage": volt,
            "electrical_current": float(self.excitation_amplitude),
            "electrical_power": float(volt * self.excitation_amplitude),
            "electrical_resistance": r0,
            "electrical_uncertainty": 0.01,

            # Ultrasonic data
            "ultrasonic_timeOfFlight": tof_us,
            "ultrasonic_amplitude": float(phys['attenuation']),
            "ultrasonic_phaseShift": float(phys.get('phase_shift', 0.0)),
            "ultrasonic_speedOfSound": sos,
            "ultrasonic_uncertainty": 0.05,

            # Thermal data
            "thermal_temperature": temp,
            "thermal_tempGradient": float(0.15 if mode != 'internal_short' else 3.5),
            "thermal_heatFlux": float((self.excitation_amplitude ** 2) * r0),
            "thermal_uncertainty": 0.20,

            # State of Health
            "stateOfHealth_value": float(phys.get('nominal_soh', 95.0)),
            "stateOfHealth_confidenceInterval_lower": float(phys.get('nominal_soh', 95.0) - 2.0),
            "stateOfHealth_confidenceInterval_upper": float(phys.get('nominal_soh', 95.0) + 2.0),
            "stateOfHealth_method": "multibranch_fusion",

            # Degradation classification
            "degradation_mode": mode,
            "degradation_probability": 0.95,
            "degradation_perClass_healthy": 0.95 if mode == 'healthy' else 0.01,
            "degradation_perClass_li_plating": 0.95 if mode == 'li_plating' else 0.01,
            "degradation_perClass_active_material_loss": 0.95 if mode == 'active_material_loss' else 0.01,
            "degradation_perClass_electrolyte_decomposition": 0.95 if mode == 'electrolyte_decomposition' else 0.01,
            "degradation_perClass_gas_generation": 0.95 if mode == 'gas_generation' else 0.01,
            "degradation_perClass_internal_short": 0.95 if mode == 'internal_short' else 0.01,
            "degradation_entropy": 0.05,

            # Rebalancing state
            "rebalancing_state": "IDLE",
            "rebalancing_active": False,
            "rebalancing_selectedAction": "none",
            "rebalancing_actionReason": "Nominal",
            "rebalancing_powerStage_targetCurrent": 0.0,
            "rebalancing_powerStage_actualCurrent": 0.0,
            "rebalancing_powerStage_targetVoltage": 0.0,
            "rebalancing_powerStage_actualVoltage": 0.0,
            "rebalancing_powerStage_pwmDutyCycle": 0.0,
            "rebalancing_executionTime": 0.0,
            "zvs_efficiency_pct": 0.0,

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
            "simulation_soc": self.soc,
            "simulation_temp_amb": raw_physics["simulation_temp_amb"],
            "simulation_load_c": raw_physics["simulation_load_c"],
            "simulation_cycle_count": raw_physics["simulation_cycle_count"],
            "simulation_excitationAmplitude": self.excitation_amplitude,
            "simulation_noiseLevel": self.noise_level,
            "simulation_stepCount": int(self.time / self.step_size) if self.step_size > 0 else self.frame_id_counter
        }
        diag = DiagnosticFrame.from_dict(frame)
        return diag.to_dict()

    def _simulate_frame(self) -> Dict[str, Any]:
        """Physical fallback generator with 2-RC electro-thermal-acoustic dynamics."""
        self.frame_id_counter += 1
        raw_physics = self.engine.step(dt=0.1)
        phys = DEGRADATION_PHYSICS_PARAMS.get(self.degradation_mode, DEGRADATION_PHYSICS_PARAMS['healthy'])
        noise_factor = float(self.noise_level)

        r0 = float(phys['r0'] * (1.0 + random.uniform(-0.01, 0.01) * noise_factor))
        sos = float(phys['sos'] + random.uniform(-5.0, 5.0) * noise_factor)
        attenuation = float(np.clip(phys['attenuation'] + random.uniform(-0.01, 0.01) * noise_factor, 0.15, 1.15))
        phase_shift = float(phys.get('phase_shift', 0.0) + random.uniform(-0.01, 0.01) * noise_factor)
        r_th = float(phys.get('r_th', 2.0))

        i_pulse = float(self.excitation_amplitude)
        ocv = float(OCV_BASE + OCV_SLOPE * np.clip(self.soc, 0.0, 1.0))
        voltage = float(ocv - i_pulse * r0 - raw_physics["ecm_v_rc1"] - raw_physics["ecm_v_rc2"] + random.uniform(-0.001, 0.001) * noise_factor)
        current = float(i_pulse + random.uniform(-0.002, 0.002) * noise_factor)
        power = float(voltage * current)

        # 8.00 µs nominal for 2 * 0.010 m path at 2500 m/s
        tof_s = float(2.0 * ULTRASONIC_PATH_LENGTH_M / max(100.0, sos))
        tof_us = float(tof_s * 1e6)

        ambient_temp = float(self.engine.ambient_temp_c + (10.0 if self.degradation_mode == 'internal_short' else 0.0))
        p_dissipated = (i_pulse ** 2) * r0 + (5.0 if self.degradation_mode == 'internal_short' else 0.0)
        temp_rise = float(p_dissipated * r_th + random.uniform(-0.02, 0.02) * noise_factor)
        temperature = float(ambient_temp + temp_rise)
        temp_gradient = float(0.15 + (3.35 if self.degradation_mode == 'internal_short' else 0.0) + random.uniform(-0.01, 0.01) * noise_factor)
        heat_flux = float(p_dissipated + random.uniform(-0.05, 0.05) * noise_factor)

        mode = self.degradation_mode
        nominal_soh = float(phys.get('nominal_soh', 95.0))
        frame = {
            "timestamp": datetime.now().timestamp(),
            "frameId": str(uuid.uuid4()),
            "source": "simulink",
            "data_origin": "FALLBACK",
            "cellId": f"cell_{self.engine.chemistry}_{self.engine.form_factor}",
            "packId": "pack_001",
            "battery_chemistry": raw_physics["chemistry"],
            "battery_chemistry_name": raw_physics["chemistry_name"],
            "battery_form_factor": raw_physics["form_factor"],
            "battery_form_factor_name": raw_physics["form_factor_name"],

            # Electrical data
            "electrical_voltage": voltage,
            "electrical_current": current,
            "electrical_power": power,
            "electrical_resistance": r0,
            "electrical_uncertainty": 0.01,

            # Ultrasonic data
            "ultrasonic_timeOfFlight": tof_us,
            "ultrasonic_amplitude": attenuation,
            "ultrasonic_phaseShift": phase_shift,
            "ultrasonic_speedOfSound": sos,
            "ultrasonic_uncertainty": 0.05,

            # Thermal data
            "thermal_temperature": temperature,
            "thermal_tempGradient": temp_gradient,
            "thermal_heatFlux": heat_flux,
            "thermal_uncertainty": 0.20,

            # State of Health
            "stateOfHealth_value": nominal_soh,
            "stateOfHealth_confidenceInterval_lower": nominal_soh - 2.0,
            "stateOfHealth_confidenceInterval_upper": nominal_soh + 2.0,
            "stateOfHealth_method": "multibranch_fusion",

            # Degradation classification
            "degradation_mode": mode,
            "degradation_probability": 0.95,
            "degradation_perClass_healthy": 0.95 if mode == 'healthy' else 0.01,
            "degradation_perClass_li_plating": 0.95 if mode == 'li_plating' else 0.01,
            "degradation_perClass_active_material_loss": 0.95 if mode == 'active_material_loss' else 0.01,
            "degradation_perClass_electrolyte_decomposition": 0.95 if mode == 'electrolyte_decomposition' else 0.01,
            "degradation_perClass_gas_generation": 0.95 if mode == 'gas_generation' else 0.01,
            "degradation_perClass_internal_short": 0.95 if mode == 'internal_short' else 0.01,
            "degradation_entropy": 0.05,

            # Rebalancing state
            "rebalancing_state": "IDLE",
            "rebalancing_active": False,
            "rebalancing_selectedAction": "none",
            "rebalancing_actionReason": "Physical simulation fallback active",
            "rebalancing_powerStage_targetCurrent": 0.0,
            "rebalancing_powerStage_actualCurrent": 0.0,
            "rebalancing_powerStage_targetVoltage": 0.0,
            "rebalancing_powerStage_actualVoltage": 0.0,
            "rebalancing_powerStage_pwmDutyCycle": 0.0,
            "rebalancing_executionTime": 0.0,
            "zvs_efficiency_pct": 0.0,

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
            "simulation_soc": self.soc,
            "simulation_temp_amb": raw_physics["simulation_temp_amb"],
            "simulation_load_c": raw_physics["simulation_load_c"],
            "simulation_cycle_count": raw_physics["simulation_cycle_count"],
            "simulation_excitationAmplitude": self.excitation_amplitude,
            "simulation_noiseLevel": self.noise_level,
            "simulation_stepCount": self.frame_id_counter
        }
        diag = DiagnosticFrame.from_dict(frame)
        return diag.to_dict()


async def test_simulink_ingestor():
    ingestor = SimulinkIngestor(fmu_path="../models/ev_cell_digital_twin.fmu", soc=0.5, excitation_amplitude=0.5)
    await ingestor.initialize()
    try:
        for i in range(5):
            frame = await ingestor.step()
            if frame:
                print(f"Simulink frame {i} [{frame['data_origin']}]: Voltage={frame['electrical_voltage']:.3f}V, ToF={frame['ultrasonic_timeOfFlight']:.2f}us")
            await asyncio.sleep(0.01)
    finally:
        await ingestor.terminate()


if __name__ == "__main__":
    asyncio.run(test_simulink_ingestor())