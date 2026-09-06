"""
Gazebo ingestion module.

This module interfaces with Gazebo (via ROS 2) to extract sensor readings
and publish DiagnosticFrame objects.
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

# Add project root to sys.path for common imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.diagnostic_schema import DiagnosticFrame

try:
    from ev_cell_multimodal_sim.core.physics_engine import DEGRADATION_PHYSICS_PARAMS
except ImportError:
    from core.physics_engine import DEGRADATION_PHYSICS_PARAMS

# Try to import ROS 2 libraries
try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import BatteryState, Temperature, FluidPressure
    from std_msgs.msg import Float64
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    print("Warning: ROS 2 libraries not available. Using simulated Gazebo data.")


class GazeboIngestor:
    def __init__(self, soc: float = 0.5, degradation_mode: str = 'healthy',
                 noise_level: float = 0.1, excitation_amplitude: float = 0.5):
        """
        Initialize the Gazebo/ROS 2 ingestor.
        """
        self.node = None
        self.is_initialized = False
        self.frame_id_counter = 0

        # Latest sensor data from ROS topics
        self.latest_voltage = 0.0
        self.latest_current = 0.0
        self.latest_temperature = 25.0  # Celsius
        self.latest_time_of_flight = 8.0e-6  # seconds
        self.latest_ultrasonic_amplitude = 1.0
        self.latest_ultrasonic_phase_shift = 0.0
        self.latest_heat_flux = 10.0  # W/m^2
        self.latest_soc = soc
        self.latest_degradation_mode = degradation_mode
        self.latest_noise_level = noise_level
        self.latest_excitation_amplitude = excitation_amplitude

        # Default parameters
        self.soc = soc
        self.degradation_mode = degradation_mode
        self.noise_level = noise_level
        self.excitation_amplitude = excitation_amplitude

    async def initialize(self):
        """Initialize the ROS 2 node and subscribers."""
        if not ROS2_AVAILABLE:
            print("ROS 2 not available. Using simulated Gazebo data.")
            self.is_initialized = True
            return

        try:
            # Initialize ROS 2
            rclpy.init()

            # Create node
            self.node = Node('ev_battery_diagnostic_gazebo_ingestor')

            # Create subscribers for battery sensor data
            # These topic names are assumptions - adjust based on actual Gazebo setup
            self.voltage_sub = self.node.create_subscription(
                Float64,
                '/battery/voltage',
                self._voltage_callback,
                10
            )

            self.current_sub = self.node.create_subscription(
                Float64,
                '/battery/current',
                self._current_callback,
                10
            )

            self.temperature_sub = self.node.create_subscription(
                Temperature,
                '/battery/temperature',
                self._temperature_callback,
                10
            )

            # Ultrasonic sensor (time of flight)
            self.tof_sub = self.node.create_subscription(
                Float64,
                '/ultrasonic/time_of_flight',
                self._tof_callback,
                10
            )

            self.ultrasonic_amplitude_sub = self.node.create_subscription(
                Float64,
                '/ultrasonic/amplitude',
                self._ultrasonic_amplitude_callback,
                10
            )

            self.ultrasonic_phase_sub = self.node.create_subscription(
                Float64,
                '/ultrasonic/phase_shift',
                self._ultrasonic_phase_callback,
                10
            )

            # Thermal heat flux
            self.heat_flux_sub = self.node.create_subscription(
                Float64,
                '/thermal/heat_flux',
                self._heat_flux_callback,
                10
            )

            # State of Charge
            self.soc_sub = self.node.create_subscription(
                Float64,
                '/battery/soc',
                self._soc_callback,
                10
            )

            # Degradation mode (as string)
            self.degradation_sub = self.node.create_subscription(
                Float64,  # Using Float64 for simplicity - could use String message
                '/battery/degradation_mode',
                self._degradation_callback,
                10
            )

            # Start spinning the node in a background task
            self.spin_task = asyncio.create_task(self._spin_node())

            self.is_initialized = True
            print("Gazebo/ROS 2 ingestor initialized")

        except Exception as e:
            print(f"Failed to initialize Gazebo/ROS 2 ingestor: {e}. Using simulated data.")
            self.is_initialized = True

    async def _spin_node(self):
        """Spin the ROS 2 node to process callbacks."""
        while rclpy.ok() and self.node:
            rclpy.spin_once(self.node, timeout_sec=0.1)
            await asyncio.sleep(0.01)  # Yield control

    def _voltage_callback(self, msg):
        """Callback for voltage topic."""
        self.latest_voltage = msg.data

    def _current_callback(self, msg):
        """Callback for current topic."""
        self.latest_current = msg.data

    def _temperature_callback(self, msg):
        """Callback for temperature topic."""
        self.latest_temperature = msg.data  # Assuming this is in Celsius

    def _tof_callback(self, msg):
        """Callback for time of flight topic."""
        self.latest_time_of_flight = msg.data  # Assuming this is in seconds

    def _ultrasonic_amplitude_callback(self, msg):
        """Callback for ultrasonic amplitude topic."""
        self.latest_ultrasonic_amplitude = msg.data

    def _ultrasonic_phase_callback(self, msg):
        """Callback for ultrasonic phase shift topic."""
        self.latest_ultrasonic_phase_shift = msg.data

    def _heat_flux_callback(self, msg):
        """Callback for heat flux topic."""
        self.latest_heat_flux = msg.data

    def _soc_callback(self, msg):
        """Callback for state of charge topic."""
        self.latest_soc = max(0.0, min(1.0, msg.data))

    def _degradation_callback(self, msg):
        """Callback for degradation mode topic."""
        # Map numeric codes to degradation modes (this is an example mapping)
        mode_map = {
            0.0: 'healthy',
            1.0: 'li_plating',
            2.0: 'active_material_loss',
            3.0: 'electrolyte_decomposition',
            4.0: 'gas_generation',
            5.0: 'internal_short'
        }
        # Round to nearest integer for mapping
        mode_int = int(round(msg.data))
        self.latest_degradation_mode = mode_map.get(mode_int, 'healthy')

    async def set_parameters(self, soc: Optional[float] = None,
                           degradation_mode: Optional[str] = None,
                           noise_level: Optional[float] = None,
                           excitation_amplitude: Optional[float] = None):
        """Update simulation parameters (for compatibility with interface)."""
        if soc is not None:
            self.soc = max(0.0, min(1.0, soc))
        # Note: In a real Gazebo setup, these would be set via Gazebo parameters or ROS parameters
        # For now, we just store them for compatibility
        if degradation_mode is not None:
            self.degradation_mode = degradation_mode
        if noise_level is not None:
            self.noise_level = max(0.0, min(1.0, noise_level))
        if excitation_amplitude is not None:
            self.excitation_amplitude = max(0.0, excitation_amplitude)

    async def get_frame(self) -> Optional[Dict[str, Any]]:
        """
        Get a frame from Gazebo/ROS 2.
        Returns a DiagnosticFrame-compatible dictionary.
        """
        if not self.is_initialized:
            await self.initialize()

        if not ROS2_AVAILABLE or not self.node:
            return self._simulate_frame()

        try:
            # Convert latest sensor data to DiagnosticFrame
            return self._convert_to_diagnostic_frame()
        except Exception as e:
            print(f"Error getting frame from Gazebo/ROS 2: {e}")
            return self._simulate_frame()

    def _convert_to_diagnostic_frame(self) -> Dict[str, Any]:
        """
        Convert Gazebo/ROS 2 sensor readings to DiagnosticFrame format.
        """
        phys = DEGRADATION_PHYSICS_PARAMS.get(self.latest_degradation_mode, DEGRADATION_PHYSICS_PARAMS['healthy'])
        r0 = float(phys['r0'])

        tof_us = self.latest_time_of_flight * 1e6
        sos = (2.0 * 0.01) / (self.latest_time_of_flight) if self.latest_time_of_flight > 0 else float(phys['sos'])
        mode = self.latest_degradation_mode

        frame = {
            "timestamp": datetime.now().timestamp(),
            "frameId": str(uuid.uuid4()),
            "source": "gazebo",
            "cellId": "cell_001",
            "packId": "pack_001",

            # Electrical data
            "electrical_voltage": float(self.latest_voltage if self.latest_voltage > 0 else 3.0 + 1.2 * self.latest_soc - 0.5 * r0),
            "electrical_current": float(self.latest_current if self.latest_current > 0 else self.latest_excitation_amplitude),
            "electrical_power": float(self.latest_voltage * self.latest_current if self.latest_voltage > 0 else 1.85),
            "electrical_resistance": r0,
            "electrical_uncertainty": 0.01,

            # Ultrasonic data
            "ultrasonic_timeOfFlight": float(tof_us if tof_us > 0 else (2.0 * 0.01 / float(phys['sos'])) * 1e6),
            "ultrasonic_amplitude": float(self.latest_ultrasonic_amplitude if self.latest_ultrasonic_amplitude > 0 else phys['attenuation']),
            "ultrasonic_phaseShift": float(self.latest_ultrasonic_phase_shift if abs(self.latest_ultrasonic_phase_shift) > 0.001 else phys.get('phase_shift', 0.0)),
            "ultrasonic_speedOfSound": float(sos),
            "ultrasonic_uncertainty": 0.1,

            # Thermal data
            "thermal_temperature": float(self.latest_temperature if self.latest_temperature > 20.0 else 25.0 + (10.0 if mode == 'internal_short' else 1.5)),
            "thermal_tempGradient": 0.15 if mode != 'internal_short' else 3.5,
            "thermal_heatFlux": float(self.latest_heat_flux),
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

            # Simulation fields (from latest parameters)
            "simulation_soc": self.latest_soc,
            "simulation_excitationAmplitude": self.latest_excitation_amplitude,
            "simulation_noiseLevel": self.latest_noise_level,
            "simulation_stepCount": self.frame_id_counter
        }

        self.frame_id_counter += 1
        diag = DiagnosticFrame.from_dict(frame)
        return diag.to_dict()

    def _simulate_frame(self) -> Dict[str, Any]:
        """Simulate a frame when Gazebo/ROS 2 is not available."""
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
            "source": "gazebo",
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

    async def cleanup(self):
        """Clean up ROS 2 resources."""
        if ROS2_AVAILABLE and self.node:
            self.spin_task.cancel()
            try:
                await self.spin_task
            except asyncio.CancelledError:
                pass
            self.node.destroy_node()
            rclpy.shutdown()


# For testing standalone
async def test_gazebo_ingestor():
    ingestor = GazeboIngestor()
    await ingestor.initialize()
    try:
        for i in range(5):
            frame = await ingestor.get_frame()
            if frame:
                print(f"Gazebo frame {i}: Voltage={frame['electrical_voltage']:.2f}V, "
                      f"Degradation={frame['degradation_mode']}")
            await asyncio.sleep(0.1)
        # Change parameters
        await ingestor.set_parameters(soc=0.8, degradation_mode='li_plating', noise_level=0.2)
        for i in range(5):
            frame = await ingestor.get_frame()
            if frame:
                print(f"Gazebo frame {i+5}: Voltage={frame['electrical_voltage']:.2f}V, "
                      f"Degradation={frame['degradation_mode']}, SOC={frame['simulation_soc']:.2f}")
            await asyncio.sleep(0.1)
    finally:
        await ingestor.cleanup()


if __name__ == "__main__":
    asyncio.run(test_gazebo_ingestor())