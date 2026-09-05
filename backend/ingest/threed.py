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

try:
    from ev_cell_multimodal_sim.core.physics_engine import DEGRADATION_PHYSICS_PARAMS
except ImportError:
    from core.physics_engine import DEGRADATION_PHYSICS_PARAMS


class ThreedIngestor:
    def __init__(self, soc: float = 0.5, degradation_mode: str = 'healthy',
                 noise_level: float = 0.1, excitation_amplitude: float = 0.5):
        """
        Initialize the 3D simulator ingestor.
        """
        self.simulator = None
        self.is_initialized = False
        self.frame_id_counter = 0

        # Default parameters (will be synced with frontend)
        self.soc = soc
        self.degradation_mode = degradation_mode
        self.noise_level = noise_level
        self.excitation_amplitude = excitation_amplitude

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
        elec = readings.get('electrical', {})
        ultra = readings.get('ultrasonic', {})
        therm = readings.get('thermal', {})

        tof_s = float(ultra.get('tof', 8.0e-6))
        tof_us = float(ultra.get('tof_us', tof_s * 1e6 if tof_s < 1.0 else tof_s))
        sos = float(ultra.get('speed_of_sound', (2.0 * 0.01) / (tof_us * 1e-6) if tof_us > 0 else 2500.0))
        phase_shift = float(ultra.get('phase_shift', 0.0))
        amplitude = float(ultra.get('amplitude', 1.0))

        r0 = float(elec.get('resistance', elec.get('r0', 0.045)))
        v = float(elec.get('voltage', 3.7))
        i = float(elec.get('current', 0.5))
        power = float(elec.get('power', v * i))

        temp = float(therm.get('temperature', 25.0 + therm.get('temperature_rise', 0.0)))
        dT_dt = float(therm.get('dT_dt', 0.15))

        mode = sim_state.get('degradation_mode', self.degradation_mode)

        frame = {
            "timestamp": sim_state.get('timestamp', datetime.now().timestamp()),
            "frameId": str(uuid.uuid4()),
            "source": "3d",
            "cellId": "cell_001",
            "packId": "pack_001",

            # Electrical data
            "electrical_voltage": v,
            "electrical_current": i,
            "electrical_power": power,
            "electrical_resistance": r0,
            "electrical_uncertainty": 0.01,

            # Ultrasonic data
            "ultrasonic_timeOfFlight": tof_us,
            "ultrasonic_amplitude": amplitude,
            "ultrasonic_phaseShift": phase_shift,
            "ultrasonic_speedOfSound": sos,
            "ultrasonic_uncertainty": 0.1,

            # Thermal data
            "thermal_temperature": temp,
            "thermal_tempGradient": dT_dt,
            "thermal_heatFlux": 10.0,
            "thermal_uncertainty": 0.5,

            # State of Health (placeholder - will be updated by ML pipeline)
            "stateOfHealth_value": 0.0,
            "stateOfHealth_confidenceInterval_lower": 0.0,
            "stateOfHealth_confidenceInterval_upper": 0.0,
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

        diag = DiagnosticFrame.from_dict(frame)
        return diag.to_dict()

    def _simulate_frame(self) -> Dict[str, Any]:
        """Simulate a frame when the 3D simulator is not available."""
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
        dT_dt = float((i_pulse ** 2) * (r0 + r1) * 50.0 / (c_th * 1e-2) + random.uniform(-0.01, 0.01) * noise_factor)

        frame = {
            "timestamp": datetime.now().timestamp(),
            "frameId": str(uuid.uuid4()),
            "source": "3d",
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
            "thermal_tempGradient": dT_dt,
            "thermal_heatFlux": 10.0,
            "thermal_uncertainty": 0.5,

            # State of Health (placeholder)
            "stateOfHealth_value": 0.0,
            "stateOfHealth_confidenceInterval_lower": 0.0,
            "stateOfHealth_confidenceInterval_upper": 0.0,
            "stateOfHealth_method": "pending",

            # Degradation classification
            "degradation_mode": self.degradation_mode,
            "degradation_probability": 0.95,
            "degradation_perClass_healthy": 0.95 if self.degradation_mode == 'healthy' else 0.02,
            "degradation_perClass_li_plating": 0.95 if self.degradation_mode == 'li_plating' else 0.02,
            "degradation_perClass_active_material_loss": 0.95 if self.degradation_mode == 'active_material_loss' else 0.02,
            "degradation_perClass_electrolyte_decomposition": 0.95 if self.degradation_mode == 'electrolyte_decomposition' else 0.02,
            "degradation_perClass_gas_generation": 0.95 if self.degradation_mode == 'gas_generation' else 0.02,
            "degradation_perClass_internal_short": 0.95 if self.degradation_mode == 'internal_short' else 0.02,
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