import time, uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum

class DegradationModeEnum(str, Enum):
    HEALTHY = 'healthy'
    LI_PLATING = 'li_plating'
    ACTIVE_MATERIAL_LOSS = 'active_material_loss'
    ELECTROLYTE_DECOMPOSITION = 'electrolyte_decomposition'
    GAS_GENERATION = 'gas_generation'
    INTERNAL_SHORT = 'internal_short'

class RebalancingActionEnum(str, Enum):
    NONE = 'none'
    PULSE_DEPLATING = 'pulse_deplating'
    EQUILIBRATION = 'equilibration'
    GAS_RECOMBINATION = 'gas_recombination'
    SHORT_ISOLATION = 'short_isolation'
    BALANCING = 'balancing'

class SafetyStatusEnum(str, Enum):
    SAFE_TO_OPERATE = 'SAFE_TO_OPERATE'
    WARNING_ELEVATED_RISK = 'WARNING_ELEVATED_RISK'
    CRITICAL_LOCKOUT_ISOLATED = 'CRITICAL_LOCKOUT_ISOLATED'

@dataclass
class DiagnosticFrame:
    # --- Identification & Metadata ---
    timestamp: float = field(default_factory=time.time)
    frameId: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = '3d'
    cellId: str = 'CELL_001'
    packId: str = 'PACK_001'

    # --- Electrical Modality ---
    electrical_voltage: float = 3.70
    electrical_current: float = 0.00
    electrical_power: float = 0.00
    electrical_resistance: float = 0.045
    electrical_uncertainty: float = 0.010

    # --- Ultrasonic Modality ---
    ultrasonic_timeOfFlight: float = 8.000
    ultrasonic_amplitude: float = 1.000
    ultrasonic_phaseShift: float = 0.000
    ultrasonic_speedOfSound: float = 2500.0
    ultrasonic_uncertainty: float = 0.050

    # --- Thermal Modality ---
    thermal_temperature: float = 25.0
    thermal_tempGradient: float = 0.10
    thermal_heatFlux: float = 5.00
    thermal_uncertainty: float = 0.20

    # --- State of Health (SOH) Inference ---
    stateOfHealth_value: float = 95.0
    stateOfHealth_confidenceInterval_lower: float = 93.0
    stateOfHealth_confidenceInterval_upper: float = 97.0
    stateOfHealth_uncertainty_std: float = 1.0
    stateOfHealth_method: str = 'multibranch_fusion'

    # --- Degradation Mode Classification ---
    degradation_mode: str = 'healthy'
    degradation_probability: float = 0.95
    degradation_entropy: float = 0.15
    degradation_perClass_healthy: float = 0.95
    degradation_perClass_li_plating: float = 0.01
    degradation_perClass_active_material_loss: float = 0.01
    degradation_perClass_electrolyte_decomposition: float = 0.01
    degradation_perClass_gas_generation: float = 0.01
    degradation_perClass_internal_short: float = 0.01

    # --- Learned Modality Attention Weights ---
    attention_weight_electrical: float = 0.40
    attention_weight_ultrasonic: float = 0.40
    attention_weight_thermal: float = 0.20

    # --- Active Rebalancing & Power Stage ---
    rebalancing_state: str = 'IDLE'
    rebalancing_selectedAction: str = 'none'
    rebalancing_actionReason: str = 'System operating nominally'
    rebalancing_safetyInterlock_engaged: bool = False
    rebalancing_safetyStatus: str = 'SAFE_TO_OPERATE'
    rebalancing_powerStage_targetCurrent: float = 0.0
    rebalancing_powerStage_actualCurrent: float = 0.0
    rebalancing_powerStage_targetVoltage: float = 0.0
    rebalancing_powerStage_actualVoltage: float = 0.0
    rebalancing_powerStage_pwmDutyCycle: float = 0.0
    rebalancing_executionTime: float = 0.0

    # --- Simulation Metadata (Optional) ---
    simulation_soc: Optional[float] = None
    simulation_excitationAmplitude: Optional[float] = None
    simulation_noiseLevel: Optional[float] = None
    simulation_stepCount: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['electrical_power'] = d['electrical_voltage'] * d['electrical_current']
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DiagnosticFrame':
        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)