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

# Add project root to sys.path for common imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.diagnostic_schema import DiagnosticFrame

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
    def __init__(self):
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
        self.latest_soc = 0.5
        self.latest_degradation_mode = 'healthy'
        self.latest_noise_level = 0.1
        self.latest_excitation_amplitude = 0.5

        # Default parameters
        self.soc = 0.5
        self.degradation_mode = 'healthy'
        self.noise_level = 0.1
        self.excitation_amplitude = 0.5

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
        frame = {
            "timestamp": datetime.now().timestamp(),
            "frameId": str(uuid.uuid4()),
            "source": "gazebo",
            "cellId": "cell_001",
            "packId": "pack_001",

            # Electrical data
            "electrical_voltage": self.latest_voltage,
            "electrical_current": self.latest_current,
            "electrical_power": self.latest_voltage * self.latest_current,
            "electrical_resistance": 0.05,  # Will calculate if current != 0
            "electrical_uncertainty": 0.01,

            # Ultrasonic data
            "ultrasonic_timeOfFlight": self.latest_time_of_flight * 1e6,  # Convert seconds to microseconds
            "ultrasonic_amplitude": self.latest_ultrasonic_amplitude,
            "ultrasonic_phaseShift": self.latest_ultrasonic_phase_shift,
            "ultrasonic_speedOfSound": 2500.0,  # Placeholder - calculate from ToF if path length known
            "ultrasonic_uncertainty": 0.1,

            # Thermal data
            "thermal_temperature": self.latest_temperature,
            "thermal_tempGradient": 0.0,  # Placeholder - would need multiple temperature sensors
            "thermal_heatFlux": self.latest_heat_flux,
            "thermal_uncertainty": 0.5,

            # State of Health (placeholder - will be updated by ML pipeline)
            "stateOfHealth_value": 0.0,
            "stateOfHealth_confidenceInterval_lower": 0.0,
            "stateOfHealth_confidenceInterval_upper": 0.0,
            "stateOfHealth_method": "pending",

            # Degradation classification
            "degradation_mode": self.latest_degradation_mode,
            "degradation_probability": 0.9 if self.latest_degradation_mode != 'healthy' else 0.95,
            "degradation_perClass_healthy": 0.95 if self.latest_degradation_mode == 'healthy' else 0.02,
            "degradation_perClass_li_plating": 0.9 if self.latest_degradation_mode == 'li_plating' else 0.02,
            "degradation_perClass_active_material_loss": 0.9 if self.latest_degradation_mode == 'active_material_loss' else 0.02,
            "degradation_perClass_electrolyte_decomposition": 0.9 if self.latest_degradation_mode == 'electrolyte_decomposition' else 0.02,
            "degradation_perClass_gas_generation": 0.9 if self.latest_degradation_mode == 'gas_generation' else 0.02,
            "degradation_perClass_internal_short": 0.9 if self.latest_degradation_mode == 'internal_short' else 0.02,
            "degradation_entropy": 0.2 if self.latest_degradation_mode != 'healthy' else 0.05,

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

        # Calculate resistance if we have voltage and current (and current not zero)
        if frame["electrical_voltage"] != 0 and frame["electrical_current"] != 0:
            frame["electrical_resistance"] = frame["electrical_voltage"] / frame["electrical_current"]
        else:
            frame["electrical_resistance"] = 0.05

        # Calculate power if not already done (should be done above)
        if frame["electrical_power"] == 0.0:
            frame["electrical_power"] = frame["electrical_voltage"] * frame["electrical_current"]

        # Estimate speed of sound from ToF if we have path length (0.01 m one way, 0.02 m round trip)
        tof_seconds = frame["ultrasonic_timeOfFlight"] * 1e-6  # microseconds to seconds
        path_length = 0.01  # meters (one way)
        # Assuming ToF is round trip: distance = 2 * path_length
        if tof_seconds > 0:
            frame["ultrasonic_speedOfSound"] = (2 * 0.01) / tof_seconds
        else:
            frame["ultrasonic_speedOfSound"] = 2500.0

        self.frame_id_counter += 1
        return frame

    def _simulate_frame(self) -> Dict[str, Any]:
        """Simulate a frame when Gazebo/ROS 2 is not available."""
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
            "source": "gazebo",
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