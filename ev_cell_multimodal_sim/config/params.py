"""
Configuration parameters for the EV battery cell simulation.
Unified with backend.physics_constants.
"""

import numpy as np
import sys
import os

# Ensure backend constants are importable
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.physics_constants import (
    OCV_BASE, OCV_SLOPE, OCV_INTERCEPT,
    R0_NOMINAL, R1_NOMINAL, C1_NOMINAL, NOMINAL_CAPACITY_AH,
    R0, R1, C1,
    SOS_NOMINAL, SOS_BASE, SOS_SOC_COEFF, SOS_TEMP_COEFF,
    ULTRASONIC_PATH_LENGTH_M, ULTRASONIC_ROUND_TRIP_M, ULTRASONIC_TOF_NOMINAL_US,
    ULTRASONIC_FREQ_HZ, ULTRASONIC_BANDWIDTH_HZ, SOS,
    THERMAL_CAPACITY_J_PER_K, THERMAL_RESISTANCE_K_PER_W,
    AMBIENT_TEMPERATURE_C, AMBIENT_TEMPERATURE_K,
    EXCITATION_PULSE_WIDTH_S, EXCITATION_PULSE_AMPLITUDE_A, EXCITATION_PERIOD_S,
    DAQ_SAMPLING_RATE_HZ, SAMPLES_PER_CYCLE,
    NOMINAL_SOH, SOH_THRESHOLD_RECOVERABLE, SOH_THRESHOLD_SEVERE, DEGRADATION_PROB_THRESHOLD,
    DEGRADATION_MODES, DEGRADATION_PHYSICS_PARAMS
)

# ============ Sampling and Noise Parameters ============
ADC_BITS = 12
ADC_FS_V = 5.0
ADC_Q = ADC_FS_V / (2 ** ADC_BITS)

ELECTRICAL_NOISE_STD_V = 0.001  # 1 mV
ULTRASONIC_TOF_NOISE_STD_S = 1e-9  # 1 ns
THERMAL_NOISE_STD_K = 0.01  # 0.01 K

# ============ Machine Learning Parameters ============
SEQ_LENGTH = SAMPLES_PER_CYCLE
NUM_DEGRADATION_MODES = len(DEGRADATION_MODES)  # 6
BATCH_SIZE = 32
NUM_EPOCHS = 50
LEARNING_RATE = 0.001
VALIDATION_SPLIT = 0.2

# ============ Control Parameters ============
MAX_RECOVERY_TIME_S = 300.0  # 5 minutes

# ============ Miscellaneous ============
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
try:
    import torch
    torch.manual_seed(RANDOM_SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(RANDOM_SEED)
except ImportError:
    pass
