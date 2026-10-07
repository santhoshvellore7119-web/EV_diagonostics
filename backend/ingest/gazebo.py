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
    from backend.battery_physics import DynamicBatteryPhysicsEngine, BATTERY_CHEMISTRIES, FORM_FACTOR_GEOMETRY
except ImportError:
    from battery_physics import DynamicBatteryPhysicsEngine, BATTERY_CHEMISTRIES, FORM_FACTOR_GEOMETRY

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
    def __init__(self, chemistry: str = 'nmc_811', form_factor: str = '21700_cylindrical',
                 soc: float = 0.5, degradation_mode: str = 'healthy',
                 ambient_temp_c: float = 25.0, load_current_c: float = 0.0,
                 cycle_count: int = 0, noise_level: float = 0.05, excitation_amplitude: float = 0.5):
        """
        Initialize the Gazebo/ROS 2 ingestor with dynamic multi-chemistry physics.
        """
        self.node = None
        self.is_initialized = False
        self.frame_id_counter = 0

        # Continuous physics engine for non-hardcoded multi-chemistry dynamics
        self.engine = DynamicBatteryPhysicsEngine(chemistry=chemistry, form_factor=form_factor)
        self.engine.set_parameters(
            soc=soc,
            degradation_mode=degradation_mode,
            ambient_temp_c=ambient_temp_c,
            load_current_c=load_current_c,
            cycle_count=cycle_count,
            noise_level=noise_level,
            excitation_amplitude_a=excitation_amplitude
        )

        # Latest sensor data from ROS topics if ROS2 is present
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

    @property
    def degradation_mode(self) -> str:
        return self.engine.degradation_mode

    @degradation_mode.setter
    def degradation_mode(self, value: str):
        self.engine.set_parameters(degradation_mode=str(value))
        self.latest_degradation_mode = str(value)

    @property
    def soc(self) -> float:
        return self.engine.soc

    @soc.setter
    def soc(self, value: float):
        self.engine.set_parameters(soc=float(value))
        self.latest_soc = float(value)

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

    @property
    def noise_level(self) -> float:
        return self.engine.noise_level

    @noise_level.setter
    def noise_level(self, value: float):
        self.engine.set_parameters(noise_level=float(value))
        self.latest_noise_level = float(value)

    @property
    def excitation_amplitude(self) -> float:
        return self.engine.excitation_amplitude_a

    @excitation_amplitude.setter
    def excitation_amplitude(self, value: float):
        self.engine.set_parameters(excitation_amplitude_a=float(value))
        self.latest_excitation_amplitude = float(value)

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

    async def set_parameters(self, **kwargs):
        """Update simulation parameters dynamically in physics engine."""
        self.engine.set_parameters(**kwargs)
        if 'soc' in kwargs:
            self.latest_soc = float(kwargs['soc'])
        if 'degradation_mode' in kwargs:
            self.latest_degradation_mode = str(kwargs['degradation_mode'])
        if 'noise_level' in kwargs:
            self.latest_noise_level = float(kwargs['noise_level'])
        if 'excitation_amplitude' in kwargs:
            self.latest_excitation_amplitude = float(kwargs['excitation_amplitude'])

    async def get_frame(self) -> Optional[Dict[str, Any]]:
        """
        Get a frame from Gazebo/ROS 2 or Dynamic Physics Twin.
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
        self.frame_id_counter += 1
        raw_physics = self.engine.step(dt=0.1)
        r0 = float(self.engine.r0)

        tof_us = self.latest_time_of_flight * 1e6 if self.latest_time_of_flight > 0 else raw_physics["ultrasonic_timeOfFlight"]
        sos = (2.0 * self.engine.acoustic_path_m) / (self.latest_time_of_flight) if self.latest_time_of_flight > 0 else raw_physics["ultrasonic_speedOfSound"]
        mode = self.latest_degradation_mode

        frame = {
            "timestamp": datetime.now().timestamp(),
            "frameId": f"GZ-{self.frame_id_counter:06d}",
            "source": "gazebo",
            "data_origin": "GAZEBO-ROS2",
            "cellId": f"cell_{self.engine.chemistry}_{self.engine.form_factor}",
            "packId": "pack_gazebo_01",
            "battery_chemistry": raw_physics["chemistry"],
            "battery_chemistry_name": raw_physics["chemistry_name"],
            "battery_form_factor": raw_physics["form_factor"],
            "battery_form_factor_name": raw_physics["form_factor_name"],

            # Electrical data
            "electrical_voltage": float(self.latest_voltage if self.latest_voltage > 0 else raw_physics["electrical_voltage"]),
            "electrical_current": float(self.latest_current if self.latest_current > 0 else raw_physics["electrical_current"]),
            "electrical_power": float(self.latest_voltage * self.latest_current if self.latest_voltage > 0 else raw_physics["electrical_power"]),
            "electrical_resistance": raw_physics["electrical_resistance"],
            "electrical_uncertainty": raw_physics["electrical_uncertainty"],

            # Ultrasonic data
            "ultrasonic_timeOfFlight": float(tof_us),
            "ultrasonic_amplitude": float(self.latest_ultrasonic_amplitude if self.latest_ultrasonic_amplitude > 0 else raw_physics["ultrasonic_amplitude"]),
            "ultrasonic_phaseShift": float(self.latest_ultrasonic_phase_shift if abs(self.latest_ultrasonic_phase_shift) > 0.001 else raw_physics["ultrasonic_phaseShift"]),
            "ultrasonic_speedOfSound": float(sos),
            "ultrasonic_uncertainty": raw_physics["ultrasonic_uncertainty"],

            # Thermal data
            "thermal_temperature": float(self.latest_temperature if self.latest_temperature > 20.0 else raw_physics["thermal_temperature"]),
            "thermal_tempGradient": raw_physics["thermal_tempGradient"],
            "thermal_heatFlux": float(self.latest_heat_flux if self.latest_heat_flux > 0 else raw_physics["thermal_heatFlux"]),
            "thermal_uncertainty": raw_physics["thermal_uncertainty"],

            # State of Health (calculated by ML)
            "stateOfHealth_value": raw_physics["stateOfHealth_physical_ground_truth"],
            "stateOfHealth_confidenceInterval_lower": max(0.0, raw_physics["stateOfHealth_physical_ground_truth"] - 3.0),
            "stateOfHealth_confidenceInterval_upper": min(100.0, raw_physics["stateOfHealth_physical_ground_truth"] + 3.0),
            "stateOfHealth_method": "multi_modal_fusion",

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
            "rebalancing_state": "monitoring",
            "rebalancing_selectedAction": "none",
            "rebalancing_actionReason": "Nominal telemetry",
            "rebalancing_powerStage_targetCurrent": 0.0,
            "rebalancing_powerStage_actualCurrent": 0.0,
            "rebalancing_powerStage_targetVoltage": 0.0,
            "rebalancing_powerStage_actualVoltage": 0.0,
            "rebalancing_powerStage_pwmDutyCycle": 0.0,
            "rebalancing_executionTime": 0.0,

            # Simulation fields
            "simulation_soc": raw_physics["simulation_soc"],
            "simulation_temp_amb": raw_physics["simulation_temp_amb"],
            "simulation_load_c": raw_physics["simulation_load_c"],
            "simulation_cycle_count": raw_physics["simulation_cycle_count"],
            "simulation_noiseLevel": raw_physics["simulation_noiseLevel"],
            "simulation_excitationAmplitude": raw_physics["simulation_excitationAmplitude"],
            "simulation_stepCount": self.frame_id_counter
        }

        diag = DiagnosticFrame.from_dict(frame)
        return diag.to_dict()

    def _simulate_frame(self) -> Dict[str, Any]:
        """Simulate a frame when Gazebo/ROS 2 is not available using the dynamic physics model."""
        self.frame_id_counter += 1
        raw_physics = self.engine.step(dt=0.1)

        frame = {
            "timestamp": raw_physics["timestamp"],
            "frameId": f"GZ-SIM-{self.frame_id_counter:06d}",
            "source": "gazebo",
            "data_origin": "GAZEBO-PHYSICS-TWIN",
            "cellId": f"cell_{self.engine.chemistry}_{self.engine.form_factor}",
            "packId": "pack_gazebo_01",
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
            "stateOfHealth_confidenceInterval_lower": max(0.0, raw_physics["stateOfHealth_physical_ground_truth"] - 3.0),
            "stateOfHealth_confidenceInterval_upper": min(100.0, raw_physics["stateOfHealth_physical_ground_truth"] + 3.0),
            "stateOfHealth_method": "multi_modal_fusion",

            # Degradation classification
            "degradation_mode": raw_physics["degradation_mode"],
            "degradation_probability": 0.95,
            "degradation_perClass_healthy": 0.95 if raw_physics["degradation_mode"] == 'healthy' else 0.01,
            "degradation_perClass_li_plating": 0.95 if raw_physics["degradation_mode"] == 'li_plating' else 0.01,
            "degradation_perClass_active_material_loss": 0.95 if raw_physics["degradation_mode"] == 'active_material_loss' else 0.01,
            "degradation_perClass_electrolyte_decomposition": 0.95 if raw_physics["degradation_mode"] == 'electrolyte_decomposition' else 0.01,
            "degradation_perClass_gas_generation": 0.95 if raw_physics["degradation_mode"] == 'gas_generation' else 0.01,
            "degradation_perClass_internal_short": 0.95 if raw_physics["degradation_mode"] == 'internal_short' else 0.01,
            "degradation_entropy": 0.05,

            # Rebalancing state
            "rebalancing_state": "monitoring",
            "rebalancing_selectedAction": "none",
            "rebalancing_actionReason": "Nominal telemetry",
            "rebalancing_powerStage_targetCurrent": 0.0,
            "rebalancing_powerStage_actualCurrent": 0.0,
            "rebalancing_powerStage_targetVoltage": 0.0,
            "rebalancing_powerStage_actualVoltage": 0.0,
            "rebalancing_powerStage_pwmDutyCycle": 0.0,
            "rebalancing_executionTime": 0.0,

            # Controllable simulation parameters
            "simulation_soc": raw_physics["simulation_soc"],
            "simulation_temp_amb": raw_physics["simulation_temp_amb"],
            "simulation_load_c": raw_physics["simulation_load_c"],
            "simulation_cycle_count": raw_physics["simulation_cycle_count"],
            "simulation_noiseLevel": raw_physics["simulation_noiseLevel"],
            "simulation_excitationAmplitude": raw_physics["simulation_excitationAmplitude"],
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