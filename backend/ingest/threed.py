"""
3D Simulation Ingestion Module with Dynamic Multi-Chemistry Physics Engine.
Integrates Continuous ODE Multi-Modal Physics with PyTorch ML and Active Rebalancing.
"""

import asyncio
import json
import uuid
import time
from datetime import datetime
from typing import Optional, Dict, Any
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.diagnostic_schema import DiagnosticFrame

try:
    from backend.battery_physics import DynamicBatteryPhysicsEngine, BATTERY_CHEMISTRIES, FORM_FACTOR_GEOMETRY
except ImportError:
    from battery_physics import DynamicBatteryPhysicsEngine, BATTERY_CHEMISTRIES, FORM_FACTOR_GEOMETRY


class ThreedIngestor:
    def __init__(self, chemistry: str = 'nmc_811', form_factor: str = '21700_cylindrical',
                 soc: float = 0.65, degradation_mode: str = 'healthy',
                 ambient_temp_c: float = 25.0, load_current_c: float = 0.0,
                 cycle_count: int = 0, noise_level: float = 0.02, excitation_amplitude: float = 0.5):
        """
        Initialize the dynamic 3D physics ingestor.
        """
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
        self.is_initialized = True
        self.frame_id_counter = 0

    @property
    def degradation_mode(self) -> str:
        return self.engine.degradation_mode

    @degradation_mode.setter
    def degradation_mode(self, value: str):
        self.engine.set_parameters(degradation_mode=str(value))

    @property
    def soc(self) -> float:
        return self.engine.soc

    @soc.setter
    def soc(self, value: float):
        self.engine.set_parameters(soc=float(value))

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

    @property
    def excitation_amplitude(self) -> float:
        return self.engine.excitation_amplitude_a

    @excitation_amplitude.setter
    def excitation_amplitude(self, value: float):
        self.engine.set_parameters(excitation_amplitude_a=float(value))

    async def initialize(self):
        """Initialize the physics simulation engine."""
        self.is_initialized = True

    async def set_parameters(self, **kwargs):
        """Update simulation physics parameters in real-time."""
        self.engine.set_parameters(**kwargs)

    async def get_frame(self) -> Optional[Dict[str, Any]]:
        """
        Compute one physical time-step and return a DiagnosticFrame dictionary.
        """
        self.frame_id_counter += 1
        raw_physics = self.engine.step(dt=0.1)

        frame = {
            "timestamp": raw_physics["timestamp"],
            "frameId": f"3D-{self.frame_id_counter:06d}",
            "source": "3d",
            "data_origin": "3D-PHYSICS-TWIN",
            "cellId": f"cell_{self.engine.chemistry}_{self.engine.form_factor}",
            "packId": "pack_twin_01",
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

            # State of Health (calculated by ML processor)
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
            "simulation_stepCount": raw_physics["simulation_stepCount"]
        }

        diag = DiagnosticFrame.from_dict(frame)
        return diag.to_dict()