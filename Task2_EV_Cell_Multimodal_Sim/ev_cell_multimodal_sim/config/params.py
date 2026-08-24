"""
Configuration parameters for the EV battery cell simulation.
"""

import numpy as np

# ============ Cell Physical Parameters ============
# Nominal capacity (Ah)
NOMINAL_CAPACITY_AH = 2.5

# Electrical parameters (Equivalent Circuit Model - ECM)
# R0: Ohmic resistance (ohm)
R0 = 0.02
# R1: Polarization resistance (ohm)
R1 = 0.01
# C1: Polarization capacitance (F)
C1 = 1000.0

# Open Circuit Voltage (OCV) vs State of Charge (SOC) relationship
# Simplified: OCV = 3.0 + 0.5 * SOC (for SOC in [0,1])
# In reality, this is a lookup table, but we use a linear approximation for simplicity.
OCV_SLOPE = 0.5  # V per SOC unit
OCV_INTERCEPT = 3.0  # V at SOC=0

# ============ Excitation Pulse Parameters ============
# Pulse width (seconds)
EXCITATION_PULSE_WIDTH_S = 10e-6  # 10 microseconds
# Pulse amplitude (current in Amperes)
EXCITATION_PULSE_AMPLITUDE_A = 0.5  # 500 mA
# Pulse repetition period (seconds)
EXCITATION_PERIOD_S = 0.1  # 10 Hz

# ============ Ultrasonic Parameters ============
# Speed of sound in the battery material (m/s)
# Typical for battery materials: around 2000-3000 m/s, we use 2500 m/s
SOS = 2500.0
# Distance between transducer and reflector (m) - one way
# For a typical cell, we might have 0.01 m (1 cm) as an example
ULTRASONIC_PATH_LENGTH_M = 0.01
# Center frequency of the ultrasonic pulse (Hz)
ULTRASONIC_FREQ_HZ = 40e3  # 40 kHz
# Bandwidth of the ultrasonic pulse (Hz)
ULTRASONIC_BANDWIDTH_HZ = 5e3  # 5 kHz

# ============ Thermal Parameters ============
# Thermal capacitance (J/K)
THERMAL_CAPACITY_J_PER_K = 500.0
# Thermal resistance to ambient (K/W)
THERMAL_RESISTANCE_K_PER_W = 2.0
# Ambient temperature (K)
AMBIENT_TEMPERATURE_K = 298.15  # 25°C
# Heat generated during excitation (J) - simplified as I^2 * R0 * pulse_width
# We'll compute this in the physics engine, but we can set a base value.

# ============ Sampling and Noise Parameters ============
# Sampling rate for DAQ (Hz)
DAQ_SAMPLING_RATE_HZ = 200e3  # 200 kHz
# Number of samples per excitation cycle
SAMPLES_PER_CYCLE = int(DAQ_SAMPLING_RATE_HZ * EXCITATION_PERIOD_S)

# ADC resolution (bits)
ADC_BITS = 12
# ADC full-scale voltage (V) - for electrical sensing, we assume we measure voltage up to 5V
ADC_FS_V = 5.0
# ADC quantization step (V)
ADC_Q = ADC_FS_V / (2**ADC_BITS)

# Noise levels (standard deviation)
# Electrical noise (V)
ELECTRICAL_NOISE_STD_V = 0.001  # 1 mV
# Ultrasonic ToF noise (s)
ULTRASONIC_TOF_NOISE_STD_S = 1e-9  # 1 ns
# Thermal noise (K)
THERMAL_NOISE_STD_K = 0.01  # 0.01 K

# ============ Machine Learning Parameters ============
# Sequence length for ML models (should match SAMPLES_PER_CYCLE or a fraction)
# We'll use the same as samples per cycle for simplicity, but in practice we might use a window.
SEQ_LENGTH = SAMPLES_PER_CYCLE
# Number of degradation modes (including healthy)
NUM_DEGRADATION_MODES = 6  # healthy, li_plating, active_material_loss, electrolyte_decomposition, gas_generation, internal_short
# Batch size for training
BATCH_SIZE = 32
# Number of epochs
NUM_EPOCHS = 50
# Learning rate
LEARNING_RATE = 0.001
# Validation split
VALIDATION_SPLIT = 0.2

# ============ Control Parameters ============
# SOH threshold for considering recovery (percentage)
SOH_THRESHOLD_RECOVERABLE = 80.0
# Probability threshold for trusting degradation classification
DEGRADATION_PROB_THRESHOLD = 0.6
# Maximum recovery time (seconds)
# SOH threshold for severe degradation (percentage)
SOH_THRESHOLD_SEVERE = 60.0  # If SOH < 60%, severe degradation

MAX_RECOVERY_TIME_S = 300.0  # 5 minutes

# ============ Miscellaneous ============
# Random seed for reproducibility
RANDOM_SEED = 42

# Set random seeds for numpy and torch
np.random.seed(RANDOM_SEED)
try:
    import torch
    torch.manual_seed(RANDOM_SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(RANDOM_SEED)
except ImportError:
    pass  # torch not installed yet, but we'll handle it in the code# ============ Control Parameters ============
