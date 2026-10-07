"""
EV Battery Diagnostics & Digital Twin - Shared Canonical Physics Constants
===========================================================================
Unified source of truth for:
1. Electrical 2-RC ECM parameters (OCV slope/intercept, R0, R1, C1).
2. Acoustic wave propagation parameters (speed of sound, path length, ToF).
3. Lumped thermal dynamics (thermal capacitance, thermal resistance, ambient temp).
4. Canonical degradation mode regimes & parameter scaling.
5. Standard unit definitions and safety interlock bounds.
"""

from typing import Dict, Any, List

# =========================================================================
# 1. ELECTRICAL EQUIVALENT CIRCUIT MODEL (ECM)
# =========================================================================
# Open Circuit Voltage (OCV) canonical model:
# OCV(SOC) = OCV_BASE + OCV_SLOPE * SOC
# At SOC=0.50 -> OCV = 3.00 + 1.20 * 0.50 = 3.600 V
OCV_BASE: float = 3.00       # V (OCV intercept at SOC = 0.0)
OCV_SLOPE: float = 1.20      # V/SOC (OCV slope)
OCV_INTERCEPT: float = OCV_BASE # Alias for backward compatibility

# Nominal Healthy ECM Parameters
R0_NOMINAL: float = 0.045    # Ohms (Ohmic resistance)
R1_NOMINAL: float = 0.025    # Ohms (Polarization resistance)
C1_NOMINAL: float = 1800.0   # Farads (Polarization capacitance)
NOMINAL_CAPACITY_AH: float = 2.5 # Ah

# Aliases for backward compatibility
R0: float = R0_NOMINAL
R1: float = R1_NOMINAL
C1: float = C1_NOMINAL

# =========================================================================
# 2. ACOUSTIC & ULTRASONIC PARAMETERS
# =========================================================================
# Sound speed in healthy cell medium at 25°C and SOC=0.5
SOS_NOMINAL: float = 2500.0          # m/s
SOS_BASE: float = 2440.0             # m/s (base velocity)
SOS_SOC_COEFF: float = 120.0         # (m/s)/SOC unit
SOS_TEMP_COEFF: float = 2.80         # (m/s)/°C

# Ultrasonic transducer path geometry
ULTRASONIC_PATH_LENGTH_M: float = 0.010   # 10 mm (1 cm one-way cell thickness)
ULTRASONIC_ROUND_TRIP_M: float = 0.020    # 20 mm round-trip path
ULTRASONIC_TOF_NOMINAL_US: float = 8.000  # 8.00 µs nominal ToF (= 2d / c * 1e6)
ULTRASONIC_FREQ_HZ: float = 10.0e6        # 10 MHz center frequency
ULTRASONIC_BANDWIDTH_HZ: float = 2.5e6    # 2.5 MHz bandwidth
SOS: float = SOS_NOMINAL

# =========================================================================
# 3. THERMAL DYNAMICS PARAMETERS
# =========================================================================
THERMAL_CAPACITY_J_PER_K: float = 500.0    # J/K (Cell lumped heat capacity)
THERMAL_RESISTANCE_K_PER_W: float = 2.00   # K/W (Cell to ambient thermal resistance)
AMBIENT_TEMPERATURE_C: float = 25.0        # °C
AMBIENT_TEMPERATURE_K: float = 298.15      # K (25°C)

# =========================================================================
# 4. EXCITATION PULSE & DAQ SAMPLING
# =========================================================================
EXCITATION_PULSE_WIDTH_S: float = 10.0e-6  # 10 microseconds
EXCITATION_PULSE_AMPLITUDE_A: float = 0.50 # 500 mA
EXCITATION_PERIOD_S: float = 0.10          # 10 Hz repetition rate
DAQ_SAMPLING_RATE_HZ: float = 200.0e3      # 200 kHz DAQ rate
SAMPLES_PER_CYCLE: int = int(DAQ_SAMPLING_RATE_HZ * EXCITATION_PERIOD_S) # 20,000

# =========================================================================
# 5. STATE OF HEALTH (SOH) & HEALTH STANDARDS
# =========================================================================
NOMINAL_SOH: float = 95.0                  # % nominal SOH for healthy cell
SOH_THRESHOLD_RECOVERABLE: float = 80.0    # %
SOH_THRESHOLD_SEVERE: float = 60.0         # %
DEGRADATION_PROB_THRESHOLD: float = 0.60

# Safety Operating Limits & Interlock Bounds
VOLTAGE_MIN_SAFE: float = 2.50             # V (under-voltage cutoff)
VOLTAGE_MAX_SAFE: float = 4.25             # V (over-voltage cutoff)
TEMP_MAX_SAFE: float = 45.0                # °C (maximum safe cell temperature)
TEMP_MIN_SAFE: float = 0.0                 # °C (minimum safe cell temperature)

# =========================================================================
# 6. CANONICAL DEGRADATION MODES & MULTI-PHYSICS MAPPING
# =========================================================================
DEGRADATION_MODES: List[str] = [
    'healthy',
    'li_plating',
    'active_material_loss',
    'electrolyte_decomposition',
    'gas_generation',
    'internal_short'
]

DEGRADATION_PHYSICS_PARAMS: Dict[str, Dict[str, Any]] = {
    'healthy': {
        'r0': 0.045, 'r1': 0.025, 'c1': 1800.0,
        'sos': 2500.0, 'attenuation': 1.00, 'phase_shift': 0.0,
        'r_th': 2.0, 'c_th': 500.0, 'gas_reverb': False, 'nominal_soh': 95.0
    },
    'li_plating': {
        'r0': 0.052, 'r1': 0.035, 'c1': 2200.0,
        'sos': 2560.0, 'attenuation': 0.96, 'phase_shift': 3.14159,
        'r_th': 2.1, 'c_th': 500.0, 'gas_reverb': False, 'nominal_soh': 88.0
    },
    'active_material_loss': {
        'r0': 0.060, 'r1': 0.048, 'c1': 1600.0,
        'sos': 2400.0, 'attenuation': 0.92, 'phase_shift': 0.0,
        'r_th': 2.2, 'c_th': 480.0, 'gas_reverb': False, 'nominal_soh': 82.0
    },
    'electrolyte_decomposition': {
        'r0': 0.088, 'r1': 0.060, 'c1': 1400.0,
        'sos': 2380.0, 'attenuation': 0.78, 'phase_shift': 0.2,
        'r_th': 2.5, 'c_th': 470.0, 'gas_reverb': False, 'nominal_soh': 80.0
    },
    'gas_generation': {
        'r0': 0.055, 'r1': 0.025, 'c1': 1900.0,
        'sos': 2100.0, 'attenuation': 0.60, 'phase_shift': 0.5,
        'r_th': 3.2, 'c_th': 450.0, 'gas_reverb': True, 'nominal_soh': 90.0
    },
    'internal_short': {
        'r0': 0.095, 'r1': 0.080, 'c1': 1200.0,
        'sos': 2420.0, 'attenuation': 0.75, 'phase_shift': 0.0,
        'r_th': 1.8, 'c_th': 500.0, 'gas_reverb': False, 'nominal_soh': 45.0
    }
}

# =========================================================================
# 7. MULTI-FORMAT CELL GEOMETRIES & INDUSTRIAL MACHINE SPECIFICATIONS
# =========================================================================
CELL_FORM_FACTORS: Dict[str, Dict[str, Any]] = {
    '18650_cylindrical': {
        'name': '18650 Cylindrical Cell',
        'type': 'cylindrical',
        'diameter_mm': 18.0,
        'height_mm': 65.0,
        'nominal_capacity_ah': 2.5,
        'nominal_r0': 0.045,
        'path_length_m': 0.010,
        'clamping_force_n': 120.0,
        'thermal_mass_j_per_k': 500.0,
        'jellyroll_turns': 18,
        'description': 'Standard 18650 spiral-wound cylindrical lithium-ion cell'
    },
    '21700_cylindrical': {
        'name': '21700 High-Power Cell',
        'type': 'cylindrical',
        'diameter_mm': 21.0,
        'height_mm': 70.0,
        'nominal_capacity_ah': 5.0,
        'nominal_r0': 0.022,
        'path_length_m': 0.012,
        'clamping_force_n': 180.0,
        'thermal_mass_j_per_k': 850.0,
        'jellyroll_turns': 24,
        'description': 'Automotive-grade high-power 21700 cylindrical format'
    },
    'prismatic_100ah': {
        'name': 'Prismatic 100Ah EV Block',
        'type': 'prismatic',
        'width_mm': 148.0,
        'thickness_mm': 52.0,
        'height_mm': 98.0,
        'nominal_capacity_ah': 100.0,
        'nominal_r0': 0.0045,
        'path_length_m': 0.026,
        'clamping_force_n': 450.0,
        'thermal_mass_j_per_k': 4200.0,
        'electrode_layers': 42,
        'description': 'Heavy EV laser-welded aluminum prismatic block with burst vent'
    },
    'pouch_60ah': {
        'name': 'Automotive 60Ah Pouch Cell',
        'type': 'pouch',
        'width_mm': 120.0,
        'length_mm': 290.0,
        'thickness_mm': 9.5,
        'nominal_capacity_ah': 60.0,
        'nominal_r0': 0.0075,
        'path_length_m': 0.0095,
        'clamping_force_n': 300.0,
        'thermal_mass_j_per_k': 2800.0,
        'electrode_layers': 36,
        'description': 'Flexible polymer-laminated pouch cell with thickness swelling measurement'
    }
}

# Machine Automated Diagnostic Test Cycle Stages
MACHINE_CYCLE_STAGES: List[str] = [
    'IDLE',
    'CLAMPING_ENGAGED',
    'ACOUSTIC_COUPLING_CHECK',
    'TRI_MODAL_PULSE_SCAN',
    'AI_FUSION_INFERENCE',
    'ACTIVE_REBALANCING_EXECUTION',
    'HEALTH_CERTIFICATION'
]

# Layer Acoustic Characteristic Impedances (Z in MRayl = 10^6 kg/(m^2·s))
ACOUSTIC_LAYER_IMPEDANCES: Dict[str, float] = {
    'aluminum_casing': 17.10,     # MRayl
    'copper_current_collector': 41.80, # MRayl
    'electrolyte_liquid': 1.62,   # MRayl
    'graphite_anode': 3.45,       # MRayl
    'separator_polyolefin': 1.85, # MRayl
    'nmc_cathode': 7.20,          # MRayl
    'metallic_li_plating': 3.65,  # MRayl (Distinct signature at separator interface)
    'gas_delamination_void': 0.0004 # MRayl (Near-total reflection R -> 1.0)
}
