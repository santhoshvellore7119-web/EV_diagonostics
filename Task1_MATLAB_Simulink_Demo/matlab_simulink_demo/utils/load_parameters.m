function params = load_parameters()
%LOAD_PARAMETERS Load system parameters for the battery diagnostic demo
%
%   PARAMS = LOAD_PARAMETERS() returns a struct with all necessary
%   parameters for simulating the multi-modal battery diagnostic system.

    params = struct();

    % ============ Cell Physical Parameters ============
    params.NOMINAL_CAPACITY_AH = 2.5; % Ah

    % Electrical parameters (ECM) - Nominal/Healthy values
    params.R0_NOMINAL = 0.02; % Ohmic resistance (ohm)
    params.R1_NOMINAL = 0.01; % Polarization resistance (ohm)
    params.C1_NOMINAL = 1000.0; % Polarization capacitance (F)

    % OCV vs SOC: OCV = 3.0 + 0.5 * SOC
    params.OCV_SLOPE = 0.5; % V per SOC unit
    params.OCV_INTERCEPT = 3.0; % V at SOC=0

    % ============ Excitation Pulse Parameters ============
    params.EXCITATION_PULSE_WIDTH_S = 10e-6; % 10 microseconds
    params.EXCITATION_PULSE_AMPLITUDE_A = 0.5; % 500 mA
    params.EXCITATION_PERIOD_S = 0.1; % 10 Hz

    % ============ Ultrasonic Parameters ============
    params.SOS = 2500.0; % Speed of sound (m/s)
    params.ULTRASONIC_PATH_LENGTH_M = 0.01; % 1 cm one-way
    params.ULTRASONIC_FREQ_HZ = 40e3; % 40 kHz
    params.ULTRASONIC_BANDWIDTH_HZ = 5e3; % 5 kHz

    % ============ Thermal Parameters ============
    params.THERMAL_CAPACITY_J_PER_K = 500.0; % J/K
    params.THERMAL_RESISTANCE_K_PER_W = 2.0; % K/W
    params.AMBIENT_TEMPERATURE_K = 298.15; % 25°C

    % ============ Sampling and Noise Parameters ============
    params.DAQ_SAMPLING_RATE_HZ = 200e3; % 200 kHz
    params.SAMPLES_PER_CYCLE = round(params.DAQ_SAMPLING_RATE_HZ * params.EXCITATION_PERIOD_S);

    params.ADC_BITS = 12;
    params.ADC_FS_V = 5.0;
    params.ADC_Q = params.ADC_FS_V / (2^params.ADC_BITS);

    % Noise levels
    params.ELECTRICAL_NOISE_STD_V = 0.001; % 1 mV
    params.ULTRASONIC_TOF_NOISE_STD_S = 1e-9; % 1 ns
    params.THERMAL_NOISE_STD_K = 0.01; % 0.01 K

    % ============ Machine Learning Parameters ============
    params.SEQ_LENGTH = params.SAMPLES_PER_CYCLE;
    params.NUM_DEGRADATION_MODES = 6;
    params.BATCH_SIZE = 32;
    params.NUM_EPOCHS = 50;
    params.LEARNING_RATE = 0.001;
    params.VALIDATION_SPLIT = 0.2;

    % ============ Control Parameters ============
    params.SOH_THRESHOLD_RECOVERABLE = 80.0; %
    params.DEGRADATION_PROB_THRESHOLD = 0.6;
    params.SOH_THRESHOLD_SEVERE = 60.0; %
    params.MAX_RECOVERY_TIME_S = 300.0; % 5 minutes

    % ============ Simulation Control ============
    params.current_soc = 0.5;
    params.current_degradation = 'healthy';
    params.noise_level = 0.1;
    params.excitation_amplitude = 0.5;

    % ============ Degradation Mode Parameters ============
    % Current degradation mode scaling factors (applied to nominal values)
    params.R0_scale = 1.0;
    params.R1_scale = 1.0;
    params.C1_scale = 1.0;
    params.sos_factor = 1.0;         % Speed of sound factor
    params.attenuation_factor = 1.0; % Ultrasonic attenuation
    params.phase_factor = 0.0;       % Ultrasonic phase shift (rad)
    params.R_th_scale = 1.0;         % Thermal resistance
    params.C_th_scale = 1.0;         % Thermal capacitance
    params.heat_factor = 1.0;        % Heat generation factor

    % Effective parameters (nominal * scale)
    params.R0 = params.R0_NOMINAL * params.R0_scale;
    params.R1 = params.R1_NOMINAL * params.R1_scale;
    params.C1 = params.C1_NOMINAL * params.C1_scale;
end

% Function to update degradation mode parameters
function update_degradation_mode(params, mode)
%UPDATE_DEGRADATION_MODE Update parameters based on degradation mode
%   UPDATE_DEGRADATION_MODE(PARAMS, MODE) updates the PARAMS struct
%   with scaling factors for the specified degradation mode.
%
%   Supported modes: 'healthy', 'li_plating', 'severe_li_plating',
%   'active_material_loss', 'gas_generation', 'internal_short'

    % Get degradation mode scaling factors
    mode_params = degradation_mode_library(mode);

    % Update scale factors
    params.R0_scale = mode_params.R0_scale;
    params.R1_scale = mode_params.R1_scale;
    params.C1_scale = mode_params.C1_scale;
    params.sos_factor = mode_params.sos_factor;
    params.attenuation_factor = mode_params.attenuation_factor;
    params.phase_factor = mode_params.phase_factor;
    params.R_th_scale = mode_params.R_th_scale;
    params.C_th_scale = mode_params.C_th_scale;
    params.heat_factor = mode_params.heat_factor;

    % Recalculate effective parameters
    params.R0 = params.R0_NOMINAL * params.R0_scale;
    params.R1 = params.R1_NOMINAL * params.R1_scale;
    params.C1 = params.C1_NOMINAL * params.C1_scale;

    % Update current degradation mode for reference
    params.current_degradation = mode;
end