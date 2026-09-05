"""
Simulink ingestion module using FMI library for co-simulation FMU.

This module loads an exported FMU from Simulink, steps through the simulation,
and converts output variables to DiagnosticFrame objects.
"""

import asyncio
import json
import uuid
import random
from datetime import datetime
from typing import Optional, Dict, Any
import numpy as np
import os, sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.diagnostic_schema import DiagnosticFrame
from ev_cell_multimodal_sim.core.physics_engine import DEGRADATION_PHYSICS_PARAMS

try:
    import fmi
except ImportError:
    fmi = None
    print("Warning: fmi-python not installed. Simulink ingestor will run in simulation mode.")

class SimulinkIngestor:
    def __init__(self, fmu_path: str, soc: float = 0.5, excitation_amplitude: float = 0.5,
                 degradation_mode: str = "healthy", noise_level: float = 0.05):
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
        self.soc = soc
        self.excitation_amplitude = excitation_amplitude
        self.degradation_mode = degradation_mode
        self.noise_level = noise_level
        self.fmu = None
        self.is_initialized = False
        self.time = 0.0
        self.step_size = 0.00001  # 10 µs step (adjust based on FMU)
        self.frame_id_counter = 0

        # Variables to store latest outputs from FMU
        self.latest_outputs = {}

    async def initialize(self):
        """Initialize the FMU."""
        if fmi is None:
            print("fmi-python not available. Using simulated Simulink data.")
            self.is_initialized = True
            return

        if not os.path.exists(self.fmu_path):
            print(f"FMU file not found: {self.fmu_path}. Using simulated data.")
            self.is_initialized = True
            return

        try:
            # Load the FMU for co-simulation
            self.fmu = fmi.FMUModelME2(self.fmu_path)
            # Get value references for outputs we need
            # These would need to be determined from the FMU's model description
            # For now, we'll use placeholder names; in practice, we'd parse the XML
            self.vr_voltage = self.fmu.getValueReference("voltage")
            self.vr_current = self.fmu.getValueReference("current")
            self.vr_power = self.fmu.getValueReference("power")
            self.vr_resistance = self.fmu.getValueReference("resistance")
            self.vr_tof = self.fmu.getValueReference("timeOfFlight")
            self.vr_amplitude = self.fmu.getValueReference("amplitude")
            self.vr_phaseShift = self.fmu.getValueReference("phaseShift")
            self.vr_speedOfSound = self.fmu.getValueReference("speedOfSound")
            self.vr_temperature = self.fmu.getValueReference("temperature")
            self.vr_tempGradient = self.fmu.getValueReference("tempGradient")
            self.vr_heatFlux = self.fmu.getValueReference("heatFlux")
            # Initialize
            self.fmu.instantiate()
            self.fmu.setupExperiment(startTime=0.0, stopTime=0.0, tolerance=1e-4)
            self.fmu.enterInitializationMode()
            self.fmu.exitInitializationMode()
            self.is_initialized = True
            print(f"FMU initialized from {self.fmu_path}")
        except Exception as e:
            print(f"Failed to initialize FMU: {e}. Using simulated data.")
            self.is_initialized = True  # Still mark as initialized so we can simulate

    async def terminate(self):
        """Terminate the FMU."""
        if self.fmu is not None:
            try:
                self.fmu.terminate()
                self.fmu.freeInstance()
            except:
                pass
        self.is_initialized = False

    async def step(self) -> Optional[Dict[str, Any]]:
        """
        Perform one simulation step and return a DiagnosticFrame.
        Returns None if not ready.
        """
        if not self.is_initialized:
            await self.initialize()

        if fmi is None or self.fmu is None:
            # Simulated data
            return self._simulate_frame()

        try:
            # Do one step
            self.fmu.doStep(currentCommunicationPoint=self.time,
                            communicationStepSize=self.step_size,
                            noSetFMUStatePriorToCurrentPoint=False)
            self.time += self.step_size

            # Retrieve outputs
            outputs = {}
            if hasattr(self, 'vr_voltage'):
                outputs['voltage'] = self.fmu.getReal([self.vr_voltage])[0]
            if hasattr(self, 'vr_current'):
                outputs['current'] = self.fmu.getReal([self.vr_current])[0]
            if hasattr(self, 'vr_power'):
                outputs['power'] = self.fmu.getReal([self.vr_power])[0]
            if hasattr(self, 'vr_resistance'):
                outputs['resistance'] = self.fmu.getReal([self.vr_resistance])[0]
            if hasattr(self, 'vr_tof'):
                outputs['tof'] = self.fmu.getReal([self.vr_tof])[0]
            if hasattr(self, 'vr_amplitude'):
                outputs['amplitude'] = self.fmu.getReal([self.vr_amplitude])[0]
            if hasattr(self, 'vr_phaseShift'):
                outputs['phaseShift'] = self.fmu.getReal([self.vr_phaseShift])[0]
            if hasattr(self, 'vr_speedOfSound'):
                outputs['speedOfSound'] = self.fmu.getReal([self.vr_speedOfSound])[0]
            if hasattr(self, 'vr_temperature'):
                outputs['temperature'] = self.fmu.getReal([self.vr_temperature])[0]
            if hasattr(self, 'vr_tempGradient'):
                outputs['tempGradient'] = self.fmu.getReal([self.vr_tempGradient])[0]
            if hasattr(self, 'vr_heatFlux'):
                outputs['heatFlux'] = self.fmu.getReal([self.vr_heatFlux])[0]

            self.latest_outputs = outputs
            return self._convert_to_diagnostic_frame(outputs)
        except Exception as e:
            print(f"Error during FMU step: {e}")
            return self._simulate_frame()

    def _convert_to_diagnostic_frame(self, outputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert FMU outputs to DiagnosticFrame format.
        """
        mode = self.degradation_mode
        phys = DEGRADATION_PHYSICS_PARAMS.get(mode, DEGRADATION_PHYSICS_PARAMS['healthy'])
        r0 = float(outputs.get("resistance", phys['r0']))
        tof_us = float(outputs.get("tof", (2.0 * 0.01 / phys['sos']) * 1e6))
        sos = float(outputs.get("speedOfSound", phys['sos']))

        frame = {
            "timestamp": datetime.now().timestamp(),
            "frameId": str(uuid.uuid4()),
            "source": "simulink",
            "cellId": "cell_001",
            "packId": "pack_001",

            # Electrical data
            "electrical_voltage": float(outputs.get("voltage", 3.0 + 1.2 * self.soc - self.excitation_amplitude * r0)),
            "electrical_current": float(outputs.get("current", self.excitation_amplitude)),
            "electrical_power": float(outputs.get("power", 0.0)),
            "electrical_resistance": r0,
            "electrical_uncertainty": 0.01,

            # Ultrasonic data
            "ultrasonic_timeOfFlight": tof_us,
            "ultrasonic_amplitude": float(outputs.get("amplitude", phys['attenuation'])),
            "ultrasonic_phaseShift": float(outputs.get("phaseShift", phys.get('phase_shift', 0.0))),
            "ultrasonic_speedOfSound": sos,
            "ultrasonic_uncertainty": 0.1,

            # Thermal data
            "thermal_temperature": float(outputs.get("temperature", 25.0 + (10.0 if mode == 'internal_short' else 1.5))),
            "thermal_tempGradient": float(outputs.get("tempGradient", 0.15 if mode != 'internal_short' else 3.5)),
            "thermal_heatFlux": float(outputs.get("heatFlux", 10.0)),
            "thermal_uncertainty": 0.5,

            # State of Health (placeholder - will be updated by ML pipeline)
            "stateOfHealth_value": 0.0,
            "stateOfHealth_confidenceInterval_lower": 0.0,
            "stateOfHealth_confidenceInterval_upper": 0.0,
            "stateOfHealth_method": "pending",

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

            # Rebalancing state (placeholder)
            "rebalancing_state": "idle",
            "rebalancing_selectedAction": "none",
            "rebalancing_actionReason": "Pending ML results",
            "rebalancing_powerStage_targetCurrent": 0.0,
            "rebalancing_powerStage_actualCurrent": 0.0,
            "rebalancing_powerStage_targetVoltage": 0.0,
            "rebalancing_powerStage_actualVoltage": 0.0,
            "rebalancing_powerStage_pwmDutyCycle": 0.0,
            "rebalancing_executionTime": 0.0,

            # Simulation fields
            "simulation_soc": self.soc,
            "simulation_excitationAmplitude": self.excitation_amplitude,
            "simulation_noiseLevel": self.noise_level,
            "simulation_stepCount": int(self.time / self.step_size) if self.step_size > 0 else self.frame_id_counter
        }

        # Calculate power if not provided
        if frame["electrical_power"] == 0.0:
            frame["electrical_power"] = frame["electrical_voltage"] * frame["electrical_current"]

        diag = DiagnosticFrame.from_dict(frame)
        return diag.to_dict()

    def _simulate_frame(self) -> Dict[str, Any]:
        """Simulate a frame when FMU is not available."""
        self.frame_id_counter += 1
        phys = DEGRADATION_PHYSICS_PARAMS.get(self.degradation_mode, DEGRADATION_PHYSICS_PARAMS['healthy'])
        noise_factor = float(self.noise_level)

        r0 = float(phys['r0'] * (1.0 + random.uniform(-0.02, 0.02) * noise_factor))
        r1 = float(phys['r1'] * (1.0 + random.uniform(-0.02, 0.02) * noise_factor))
        sos = float(phys['sos'] + random.uniform(-10.0, 10.0) * noise_factor)
        attenuation = float(np.clip(phys['attenuation'] + random.uniform(-0.015, 0.015) * noise_factor, 0.15, 1.15))
        phase_shift = float(phys.get('phase_shift', 0.0) + random.uniform(-0.02, 0.02) * noise_factor)
        r_th = float(phys.get('r_th', 2.0) * (1.0 + random.uniform(-0.02, 0.02) * noise_factor))
        c_th = float(phys.get('c_th', 500.0) * (1.0 + random.uniform(-0.02, 0.02) * noise_factor))

        i_pulse = float(self.excitation_amplitude)
        ocv = float(3.0 + 1.2 * np.clip(self.soc, 0.0, 1.0))
        voltage = float(ocv - i_pulse * r0 + random.uniform(-0.002, 0.002) * noise_factor)
        current = float(i_pulse + random.uniform(-0.005, 0.005) * noise_factor)
        power = float(voltage * current)

        tof_s = float(2.0 * 0.01 / max(100.0, sos))
        tof_us = float(tof_s * 1e6)

        ambient_temp = 25.0 + (10.0 if self.degradation_mode == 'internal_short' else 0.0)
        temp_rise = float((r0 + r1) * (i_pulse ** 2) * r_th * 30.0 + max(0.0, ambient_temp - 25.0) + random.uniform(-0.05, 0.05) * noise_factor)
        temperature = float(25.0 + temp_rise)
        temp_gradient = float(0.15 + (3.35 if self.degradation_mode == 'internal_short' else 0.0) + random.uniform(-0.02, 0.02) * noise_factor)
        heat_flux = float((i_pulse ** 2) * (r0 + r1) * 50.0 + (15.0 if self.degradation_mode == 'internal_short' else 0.0) + random.uniform(-0.1, 0.1) * noise_factor)

        mode = self.degradation_mode
        frame = {
            "timestamp": datetime.now().timestamp(),
            "frameId": str(uuid.uuid4()),
            "source": "simulink",
            "cellId": "cell_001",
            "packId": "pack_001",

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
            "ultrasonic_uncertainty": 0.1,

            # Thermal data
            "thermal_temperature": temperature,
            "thermal_tempGradient": temp_gradient,
            "thermal_heatFlux": heat_flux,
            "thermal_uncertainty": 0.5,

            # State of Health (placeholder)
            "stateOfHealth_value": 0.0,
            "stateOfHealth_confidenceInterval_lower": 0.0,
            "stateOfHealth_confidenceInterval_upper": 0.0,
            "stateOfHealth_method": "pending",

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

            # Rebalancing state (placeholder)
            "rebalancing_state": "idle",
            "rebalancing_selectedAction": "none",
            "rebalancing_actionReason": "Pending ML results",
            "rebalancing_powerStage_targetCurrent": 0.0,
            "rebalancing_powerStage_actualCurrent": 0.0,
            "rebalancing_powerStage_targetVoltage": 0.0,
            "rebalancing_powerStage_actualVoltage": 0.0,
            "rebalancing_powerStage_pwmDutyCycle": 0.0,
            "rebalancing_executionTime": 0.0,

            # Simulation fields
            "simulation_soc": self.soc,
            "simulation_excitationAmplitude": self.excitation_amplitude,
            "simulation_noiseLevel": self.noise_level,
            "simulation_stepCount": self.frame_id_counter
        }
        diag = DiagnosticFrame.from_dict(frame)
        return diag.to_dict()


# For testing standalone
async def test_simulink_ingestor():
    # Use a dummy path; in reality, point to exported FMU
    ingestor = SimulinkIngestor(fmu_path="../models/ev_cell_digital_twin.fmu", soc=0.5, excitation_amplitude=0.5)
    await ingestor.initialize()
    try:
        for i in range(10):
            frame = await ingestor.step()
            if frame:
                print(f"Simulink frame {i}: Voltage={frame['electrical_voltage']:.2f}V, "
                      f"SOC={frame['simulation_soc']:.2f}")
            await asyncio.sleep(0.01)  # Simulate faster than real-time for testing
    finally:
        await ingestor.terminate()


if __name__ == "__main__":
    import random
    asyncio.run(test_simulink_ingestor())