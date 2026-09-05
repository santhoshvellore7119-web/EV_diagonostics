"""
3D simulation ingestion module.

This module interfaces with the existing 3D simulation code (ev_battery_3d_simulation.py)
to extract sensor readings at each simulation step and publish DiagnosticFrame objects.
"""

import asyncio
import json
import uuid
import random
from datetime import datetime
from typing import Optional, Dict, Any
import sys
import os

# Add the simulation_3d_demo and common directories to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
sim_path = os.path.join(project_root, 'simulation_3d_demo')
if sim_path not in sys.path:
    sys.path.append(sim_path)

from common.diagnostic_schema import DiagnosticFrame

try:
    from ev_battery_3d_simulation import EVBattery3DSimulator
except ImportError as e:
    print(f"Warning: Could not import EVBattery3DSimulator: {e}")
    EVBattery3DSimulator = None


class ThreedIngestor:
    def __init__(self):
        """
        Initialize the 3D simulator ingestor.
        """
        self.simulator = None
        self.is_initialized = False
        self.frame_id_counter = 0

        # Default parameters (will be synced with frontend)
        self.soc = 0.5
        self.degradation_mode = 'healthy'
        self.noise_level = 0.1
        self.excitation_amplitude = 0.5

    async def initialize(self):
        """Initialize the 3D simulator."""
        if EVBattery3DSimulator is None:
            print("EVBattery3DSimulator not available. Using simulated 3D data.")
            self.is_initialized = True
            return

        try:
            self.simulator = EVBattery3DSimulator(headless=True)
            # Set initial parameters
            await self.set_parameters(
                soc=self.soc,
                degradation_mode=self.degradation_mode,
                noise_level=self.noise_level,
                excitation_amplitude=self.excitation_amplitude
            )
            # Trigger an initial update to set up the visualization (not strictly needed for data)
            # self.simulator.update_visualization()  # This would try to show GUI; skip for headless
            self.is_initialized = True
            print("3D simulator initialized")
        except Exception as e:
            print(f"Failed to initialize 3D simulator: {e}. Using simulated data.")
            self.is_initialized = True

    async def set_parameters(self, soc: Optional[float] = None,
                           degradation_mode: Optional[str] = None,
                           noise_level: Optional[float] = None,
                           excitation_amplitude: Optional[float] = None):
        """Update simulation parameters."""
        if soc is not None:
            self.soc = max(0.0, min(1.0, soc))
            if self.simulator:
                self.simulator.soc = self.soc
        if degradation_mode is not None:
            self.degradation_mode = degradation_mode
            if self.simulator:
                self.simulator.degradation_mode = self.degradation_mode
        if noise_level is not None:
            self.noise_level = max(0.0, min(1.0, noise_level))
            if self.simulator:
                self.simulator.noise_level = self.noise_level
        if excitation_amplitude is not None:
            self.excitation_amplitude = max(0.0, excitation_amplitude)
            if self.simulator:
                self.simulator.excitation_amplitude = self.excitation_amplitude
                self.simulator.params['pulse_amplitude_a'] = self.excitation_amplitude

    async def get_frame(self) -> Optional[Dict[str, Any]]:
        """
        Get a frame from the 3D simulator.
        Returns a DiagnosticFrame-compatible dictionary.
        """
        if not self.is_initialized:
            await self.initialize()

        if EVBattery3DSimulator is None or self.simulator is None:
            return self._simulate_frame()

        try:
            # Get sensor readings from the simulator
            readings = self.simulator.get_sensor_readings()
            # Get simulation state for DiagnosticFrame fields
            sim_state = self.simulator.get_simulation_state()
            # Convert to DiagnosticFrame
            return self._convert_to_diagnostic_frame(readings, sim_state)
        except Exception as e:
            print(f"Error getting frame from 3D simulator: {e}")
            return self._simulate_frame()

    def _convert_to_diagnostic_frame(self, readings: Dict[str, Any],
                                   sim_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert 3D simulator readings to DiagnosticFrame format.
        """
        frame = {
            "timestamp": sim_state.get('timestamp', datetime.now().timestamp()),
            "frameId": str(uuid.uuid4()),
            "source": "3d",
            "cellId": "cell_001",
            "packId": "pack_001",

            # Electrical data
            "electrical_voltage": readings.get('electrical', {}).get('voltage', 0.0),
            "electrical_current": readings.get('electrical', {}).get('current', 0.0),
            "electrical_power": readings.get('electrical', {}).get('power', 0.0),
            "electrical_resistance": 0.05,  # Placeholder; could compute from voltage/current if current != 0
            "electrical_uncertainty": 0.01,

            # Ultrasonic data
            "ultrasonic_timeOfFlight": readings.get('ultrasonic', {}).get('tof', 8.0) * 1e6,  # Convert seconds to microseconds
            "ultrasonic_amplitude": readings.get('ultrasonic', {}).get('amplitude', 1.0),
            "ultrasonic_phaseShift": readings.get('ultrasonic', {}).get('phase_shift', 0.0),
            "ultrasonic_speedOfSound": 2500.0,  # Placeholder; could compute from ToF and known path length
            "ultrasonic_uncertainty": 0.1,

            # Thermal data
            "thermal_temperature": readings.get('thermal', {}).get('temperature_rise', 0.0) + 25.0,  # Assuming base 25°C
            "thermal_tempGradient": readings.get('thermal', {}).get('dT_dt', 0.0),
            "thermal_heatFlux": 10.0,  # Placeholder
            "thermal_uncertainty": 0.5,

            # State of Health (placeholder - will be updated by ML pipeline)
            "stateOfHealth_value": 0.0,
            "stateOfHealth_confidenceInterval_lower": 0.0,
            "stateOfHealth_confidenceInterval_upper": 0.0,
            "stateOfHealth_method": "pending",

            # Degradation classification (we can use the simulator's degradation mode)
            "degradation_mode": sim_state.get('degradation_mode', self.degradation_mode),
            "degradation_probability": 0.9 if sim_state.get('degradation_mode', self.degradation_mode) != 'healthy' else 0.95,
            "degradation_perClass_healthy": 0.95 if sim_state.get('degradation_mode', self.degradation_mode) == 'healthy' else 0.02,
            "degradation_perClass_li_plating": 0.9 if sim_state.get('degradation_mode', self.degradation_mode) == 'li_plating' else 0.02,
            "degradation_perClass_active_material_loss": 0.9 if sim_state.get('degradation_mode', self.degradation_mode) == 'active_material_loss' else 0.02,
            "degradation_perClass_electrolyte_decomposition": 0.9 if sim_state.get('degradation_mode', self.degradation_mode) == 'electrolyte_decomposition' else 0.02,
            "degradation_perClass_gas_generation": 0.9 if sim_state.get('degradation_mode', self.degradation_mode) == 'gas_generation' else 0.02,
            "degradation_perClass_internal_short": 0.9 if sim_state.get('degradation_mode', self.degradation_mode) == 'internal_short' else 0.02,
            "degradation_entropy": 0.2 if sim_state.get('degradation_mode', self.degradation_mode) != 'healthy' else 0.05,

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
            "simulation_soc": sim_state.get('soc', self.soc),
            "simulation_excitationAmplitude": sim_state.get('excitation_amplitude', self.excitation_amplitude),
            "simulation_noiseLevel": sim_state.get('noise_level', self.noise_level),
            "simulation_stepCount": sim_state.get('step_count', 0)
        }

        # Calculate resistance if we have voltage and current (and current not zero)
        if frame["electrical_voltage"] != 0 and frame["electrical_current"] != 0:
            frame["electrical_resistance"] = frame["electrical_voltage"] / frame["electrical_current"]
        else:
            frame["electrical_resistance"] = 0.05

        # Calculate power if not provided (should be provided by readings)
        if frame["electrical_power"] == 0.0:
            frame["electrical_power"] = frame["electrical_voltage"] * frame["electrical_current"]

        # Estimate speed of sound from ToF if we have path length (0.02 m round trip? Actually path length is 0.01 m each way? In simulator, path length is 0.01 m)
        tof_seconds = frame["ultrasonic_timeOfFlight"] * 1e-6  # microseconds to seconds
        path_length = 0.01  # meters (one way? Actually ToF is round trip? In the simulator, ToF is time of flight, likely round trip)
        # Assuming Tof is round trip: distance = 2 * path_length
        if tof_seconds > 0:
            frame["ultrasonic_speedOfSound"] = (2 * 0.01) / tof_seconds
        else:
            frame["ultrasonic_speedOfSound"] = 2500.0

        return frame

    def _simulate_frame(self) -> Dict[str, Any]:
        """Simulate a frame when the 3D simulator is not available."""
        self.frame_id_counter += 1
        # Simulate based on parameters
        base_voltage = 3.0 + 0.5 * self.soc
        base_current = self.excitation_amplitude
        base_power = base_voltage * base_current
        base_resistance = 0.05 + (1 - self.soc) * 0.1

        # Degradation effects (simplified)
        deg_effects = {
            'healthy': {'electrical': 1.0, 'ultrasonic': 1.0, 'thermal': 1.0},
            'li_plating': {'electrical': 1.02, 'ultrasonic': 0.99, 'thermal': 1.05},
            'active_material_loss': {'electrical': 1.05, 'ultrasonic': 0.97, 'thermal': 1.1},
            'electrolyte_decomposition': {'electrical': 1.03, 'ultrasonic': 0.98, 'thermal': 1.05},
            'gas_generation': {'electrical': 1.08, 'ultrasonic': 0.93, 'thermal': 1.2},
            'internal_short': {'electrical': 1.15, 'ultrasonic': 0.85, 'thermal': 1.8}
        }
        effect = deg_effects.get(self.degradation_mode, deg_effects['healthy'])

        frame = {
            "timestamp": datetime.now().timestamp(),
            "frameId": str(uuid.uuid4()),
            "source": "3d",
            "cellId": "cell_001",
            "packId": "pack_001",

            # Electrical data
            "electrical_voltage": base_voltage * effect['electrical'] + random.uniform(-0.02, 0.02),
            "electrical_current": base_current + random.uniform(-0.02, 0.02),
            "electrical_power": 0.0,  # Will be calculated
            "electrical_resistance": base_resistance * effect['electrical'],
            "electrical_uncertainty": 0.01,

            # Ultrasonic data
            "ultrasonic_timeOfFlight": (8.0 / effect['ultrasonic']) + random.uniform(-0.5, 0.5),
            "ultrasonic_amplitude": 1.0 * effect['ultrasonic'] + random.uniform(-0.2, 0.2),
            "ultrasonic_phaseShift": 0.0 + random.uniform(-0.1, 0.1),
            "ultrasonic_speedOfSound": 2500.0 * effect['ultrasonic'] + random.uniform(-100, 100),
            "ultrasonic_uncertainty": 0.1,

            # Thermal data
            "thermal_temperature": (25.0 + (1 - self.soc) * 10) * effect['thermal'] + random.uniform(-5, 10),
            "thermal_tempGradient": (0.1 + (1 - self.soc) * 0.2) * effect['thermal'] + random.uniform(-0.05, 0.05),
            "thermal_heatFlux": (10.0 + (1 - self.soc) * 20) * effect['thermal'] + random.uniform(-5, 5),
            "thermal_uncertainty": 0.5,

            # State of Health (placeholder)
            "stateOfHealth_value": self.soc * 100 * effect['thermal'],  # Rough approximation
            "stateOfHealth_confidenceInterval_lower": max(0, self.soc * 100 - 5),
            "stateOfHealth_confidenceInterval_upper": min(100, self.soc * 100 + 5),
            "stateOfHealth_method": "fusion",

            # Degradation classification (reflecting the mode we set)
            "degradation_mode": self.degradation_mode,
            "degradation_probability": 0.8 + 0.2 * (1 - self.soc) if self.degradation_mode != 'healthy' else 0.95,
            "degradation_perClass_healthy": 0.95 if self.degradation_mode == 'healthy' else 0.02,
            "degradation_perClass_li_plating": 0.9 if self.degradation_mode == 'li_plating' else 0.02,
            "degradation_perClass_active_material_loss": 0.9 if self.degradation_mode == 'active_material_loss' else 0.02,
            "degradation_perClass_electrolyte_decomposition": 0.9 if self.degradation_mode == 'electrolyte_decomposition' else 0.02,
            "degradation_perClass_gas_generation": 0.9 if self.degradation_mode == 'gas_generation' else 0.02,
            "degradation_perClass_internal_short": 0.9 if self.degradation_mode == 'internal_short' else 0.02,
            "degradation_entropy": 0.3 if self.degradation_mode != 'healthy' else 0.05,

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
            "simulation_noiseLevel": self.noise_level,
            "simulation_stepCount": self.frame_id_counter
        }

        # Calculate power
        frame["electrical_power"] = frame["electrical_voltage"] * frame["electrical_current"]

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
        # Change parameters
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