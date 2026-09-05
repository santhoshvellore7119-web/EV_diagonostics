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

try:
    import fmi
except ImportError:
    fmi = None
    print("Warning: fmi-python not installed. Simulink ingestor will run in simulation mode.")

class SimulinkIngestor:
    def __init__(self, fmu_path: str, soc: float = 0.5, excitation_amplitude: float = 0.5):
        """
        Initialize the Simulink ingestor.

        Args:
            fmu_path: Path to the exported FMU file.
            soc: Initial state of charge (0-1).
            excitation_amplitude: Excitation pulse amplitude (A).
        """
        self.fmu_path = fmu_path
        self.soc = soc
        self.excitation_amplitude = excitation_amplitude
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
        frame = {
            "timestamp": datetime.now().timestamp(),
            "frameId": str(uuid.uuid4()),
            "source": "simulink",
            "cellId": "cell_001",
            "packId": "pack_001",

            # Electrical data
            "electrical_voltage": outputs.get("voltage", 0.0),
            "electrical_current": outputs.get("current", 0.0),
            "electrical_power": outputs.get("power", 0.0),
            "electrical_resistance": outputs.get("resistance", 0.05),
            "electrical_uncertainty": 0.01,  # TODO: get from FMU if available

            # Ultrasonic data
            "ultrasonic_timeOfFlight": outputs.get("tof", 8.0),  # microseconds
            "ultrasonic_amplitude": outputs.get("amplitude", 1.0),
            "ultrasonic_phaseShift": outputs.get("phaseShift", 0.0),
            "ultrasonic_speedOfSound": outputs.get("speedOfSound", 2500.0),
            "ultrasonic_uncertainty": 0.1,

            # Thermal data
            "thermal_temperature": outputs.get("temperature", 25.0),
            "thermal_tempGradient": outputs.get("tempGradient", 0.1),
            "thermal_heatFlux": outputs.get("heatFlux", 10.0),
            "thermal_uncertainty": 0.5,

            # State of Health (placeholder - will be updated by ML pipeline)
            "stateOfHealth_value": 0.0,
            "stateOfHealth_confidenceInterval_lower": 0.0,
            "stateOfHealth_confidenceInterval_upper": 0.0,
            "stateOfHealth_method": "pending",

            # Degradation classification (placeholder)
            "degradation_mode": "unknown",
            "degradation_probability": 0.0,
            "degradation_perClass_healthy": 0.0,
            "degradation_perClass_li_plating": 0.0,
            "degradation_perClass_active_material_loss": 0.0,
            "degradation_perClass_electrolyte_decomposition": 0.0,
            "degradation_perClass_gas_generation": 0.0,
            "degradation_perClass_internal_short": 0.0,
            "degradation_entropy": 0.0,

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
            "simulation_noiseLevel": 0.1,  # Could be added as FMU output
            "simulation_stepCount": int(self.time / self.step_size)
        }

        # Calculate power if not provided
        if frame["electrical_power"] == 0.0:
            frame["electrical_power"] = frame["electrical_voltage"] * frame["electrical_current"]

        return frame

    def _simulate_frame(self) -> Dict[str, Any]:
        """Simulate a frame when FMU is not available."""
        self.frame_id_counter += 1
        # Simulate realistic values based on SOC and excitation
        # Simple SOC-dependent voltage
        base_voltage = 3.0 + 0.5 * self.soc  # Simplified OCV
        base_current = self.excitation_amplitude
        base_power = base_voltage * base_current
        base_resistance = 0.05 + (1 - self.soc) * 0.1  # Higher resistance as SOC decreases

        return {
            "timestamp": datetime.now().timestamp(),
            "frameId": str(uuid.uuid4()),
            "source": "simulink",
            "cellId": "cell_001",
            "packId": "pack_001",

            # Electrical data
            "electrical_voltage": base_voltage + random.uniform(-0.02, 0.02),
            "electrical_current": base_current + random.uniform(-0.02, 0.02),
            "electrical_power": base_power + random.uniform(-0.1, 0.1),
            "electrical_resistance": base_resistance,
            "electrical_uncertainty": 0.01,

            # Ultrasonic data
            "ultrasonic_timeOfFlight": 8.0 / (1 + 0.1 * (1 - self.soc)) + random.uniform(-0.5, 0.5),  # ToF increases as SOH decreases
            "ultrasonic_amplitude": 1.0 * (1 - 0.2 * (1 - self.soc)) + random.uniform(-0.2, 0.2),
            "ultrasonic_phaseShift": 0.0 + random.uniform(-0.1, 0.1),
            "ultrasonic_speedOfSound": 2500.0 * (1 - 0.05 * (1 - self.soc)) + random.uniform(-100, 100),
            "ultrasonic_uncertainty": 0.1,

            # Thermal data
            "thermal_temperature": 25.0 + (1 - self.soc) * 10 + random.uniform(-5, 10),
            "thermal_tempGradient": 0.1 + (1 - self.soc) * 0.2 + random.uniform(-0.05, 0.05),
            "thermal_heatFlux": 10.0 + (1 - self.soc) * 20 + random.uniform(-5, 5),
            "thermal_uncertainty": 0.5,

            # State of Health (placeholder)
            "stateOfHealth_value": self.soc * 100,  # Simplified: SOH = SOC * 100 (not realistic but for demo)
            "stateOfHealth_confidenceInterval_lower": max(0, self.soc * 100 - 5),
            "stateOfHealth_confidenceInterval_upper": min(100, self.soc * 100 + 5),
            "stateOfHealth_method": "fusion",

            # Degradation classification (placeholder - based on SOC)
            "degradation_mode": "healthy" if self.soc > 0.8 else "li_plating" if self.soc > 0.6 else "active_material_loss",
            "degradation_probability": 0.8 + 0.2 * (1 - self.soc),
            "degradation_perClass_healthy": max(0, 1 - 2 * (1 - self.soc)),
            "degradation_perClass_li_plating": max(0, 2 * (1 - self.soc) - 1) if self.soc > 0.4 else 0,
            "degradation_perClass_active_material_loss": max(0, 2 * (0.6 - self.soc)) if self.soc <= 0.6 else 0,
            "degradation_perClass_electrolyte_decomposition": 0.0,
            "degradation_perClass_gas_generation": 0.0,
            "degradation_perClass_internal_short": 0.0,
            "degradation_entropy": 0.3,

            # Rebalancing state (placeholder)
            "rebalancing_state": "idle",
            "rebalancing_selectedAction": "none",
            "rebalancing_actionReason": "No action required",
            "rebalancing_powerStage_targetCurrent": 0.0,
            "rebalancing_powerStage_actualCurrent": 0.0,
            "rebalancing_powerStage_targetVoltage": 0.0,
            "rebalancing_powerStage_actualVoltage": 0.0,
            "rebalancing_powerStage_pwmDutyCycle": 0.0,
            "rebalancing_executionTime": 0.0,

            # Simulation fields
            "simulation_soc": self.soc,
            "simulation_excitationAmplitude": self.excitation_amplitude,
            "simulation_noiseLevel": 0.1,
            "simulation_stepCount": int(self.time / self.step_size)
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