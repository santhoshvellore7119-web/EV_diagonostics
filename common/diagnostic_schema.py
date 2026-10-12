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

class DataOriginEnum(str, Enum):
    LIVE = 'LIVE'
    FMU = 'FMU'
    FALLBACK = 'FALLBACK'
    THREED_SIM = '3D-SIM'
    GAZEBO = 'GAZEBO'
    SIMULINK = 'SIMULINK'

@dataclass
class DiagnosticFrame:
    # --- Identification & Metadata ---
    timestamp: float = field(default_factory=time.time)
    frameId: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = '3d'
    data_origin: str = 'LIVE'  # 'FMU', 'FALLBACK', '3D-SIM', 'GAZEBO', 'LIVE', 'SIMULINK'
    cellId: str = 'CELL_001'
    packId: str = 'PACK_001'

    # --- Multi-Chemistry & Format Metadata ---
    battery_chemistry: Optional[str] = 'nmc_811'
    battery_chemistry_name: Optional[str] = 'NMC 811 (LiNi0.8Mn0.1Co0.1O2)'
    battery_form_factor: Optional[str] = '21700_cylindrical'
    battery_form_factor_name: Optional[str] = '21700 Cylindrical'

    # --- Electrical Modality ---
    electrical_voltage: float = 3.70
    electrical_current: float = 0.00
    electrical_power: float = 0.00
    electrical_resistance: float = 0.045
    electrical_uncertainty: float = 0.010

    # --- Online 2-RC ECM / RLS / EKF Parameter Estimation ---
    ecm_r0_est: Optional[float] = None
    ecm_r1_est: Optional[float] = None
    ecm_c1_est: Optional[float] = None
    ecm_r2_est: Optional[float] = None
    ecm_c2_est: Optional[float] = None
    ecm_v_rc1: Optional[float] = None
    ecm_v_rc2: Optional[float] = None
    ecm_ocv_est: Optional[float] = None
    eis_spectrum: Optional[Dict[str, Any]] = None

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

    # --- State of Health (SOH) & RUL Inference ---
    stateOfHealth_value: float = 95.0
    stateOfHealth_confidenceInterval_lower: float = 93.0
    stateOfHealth_confidenceInterval_upper: float = 97.0
    stateOfHealth_uncertainty_std: float = 1.0
    stateOfHealth_method: str = 'multibranch_fusion'
    stateOfHealth_physical_ground_truth: Optional[float] = None
    rul_remaining_cycles: Optional[int] = None
    rul_knee_point_cycles: Optional[int] = None
    pinn_physics_residual: Optional[float] = None
    edge_inference_latency_ms: Optional[float] = None
    soh: Optional[float] = None

    # --- Degradation Mode Classification ---
    degradation_mode: str = 'healthy'
    degradation_mode_idx: int = 0
    degradation_probability: float = 0.95
    degradation_prob: Optional[float] = None
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
    rebalancing_active: bool = False
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
    zvs_efficiency_pct: float = 0.0

    # --- Simulation & Pack Metadata (Optional) ---
    simulation_soc: Optional[float] = None
    simulation_temp_amb: Optional[float] = None
    simulation_load_c: Optional[float] = None
    simulation_cycle_count: Optional[int] = None
    simulation_excitationAmplitude: Optional[float] = None
    simulation_noiseLevel: Optional[float] = None
    simulation_stepCount: Optional[int] = None
    ascan_waveform: Optional[Dict[str, Any]] = None
    machine_cycle: Optional[Dict[str, Any]] = None
    pack_cells: Optional[List[Dict[str, Any]]] = None

    _extra_fields: Dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        extra = d.pop('_extra_fields', {}) or {}
        v = d.get('electrical_voltage') if d.get('electrical_voltage') is not None else 0.0
        i = d.get('electrical_current') if d.get('electrical_current') is not None else 0.0
        d['electrical_power'] = float(v) * float(i)
        # Remove None optional fields only if they weren't explicitly provided in _extra_fields,
        # while keeping all canonical fields intact
        for k, val in extra.items():
            d[k] = val
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DiagnosticFrame':
        if data is None:
            return cls()
        valid_fields = {f for f in cls.__dataclass_fields__ if f != '_extra_fields'}
        filtered = {}
        extra = {}
        for k, v in data.items():
            if k in valid_fields:
                if v is not None or cls.__dataclass_fields__[k].default is None:
                    filtered[k] = v
            elif k != '_extra_fields':
                extra[k] = v
        obj = cls(**filtered)
        obj._extra_fields = extra
        return obj