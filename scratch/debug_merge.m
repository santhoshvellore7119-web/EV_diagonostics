clear; close all; clc;
addpath(genpath(pwd));
addpath(genpath(fullfile(pwd, 'matlab_simulink_demo')));
addpath(genpath(fullfile(pwd, 'Task1_MATLAB_Simulink_Demo', 'matlab_simulink_demo')));

% Simulate what happens in the battery_system_demo.m loop
scenarios = {
    'Healthy Cell',
    'Li Plating (Recoverable)',
    'Severe Li Plating (Not Recoverable)',
    'Active Material Loss',
    'Gas Generation',
    'Internal Short'
};

degradation_modes = {
    'healthy',
    'li_plating',
    'li_plating',
    'active_material_loss',
    'electrolyte_decomposition',
    'gas_generation',
    'internal_short'
};

soc_values = [0.5, 0.4, 0.3, 0.6, 0.7, 0.2];
soh_values = [95.0, 88.0, 55.0, 82.0, 90.0, 45.0];

% Load base params
params = load_parameters();
fprintf('Initial params struct:\n');
disp(params);
fprintf('\nInitial field names:\n');
initial_fields = fieldnames(params);
for i = 1:numel(initial_fields)
    fprintf('  %d: ''%s''\n', i, initial_fields{i});
end

% Test first iteration
i = 1;
fprintf('\n=== Testing iteration %d (%s) ===\n', i, scenarios{i});
fprintf('Setting params.current_soc = %.2f\n', soc_values(i));
params.current_soc = soc_values(i);
fprintf('Setting params.current_degradation = ''%s''\n', degradation_modes{i});
params.current_degradation = degradation_modes{i};
fprintf('Setting params.current_soh = %.1f\n', soh_values(i));
params.current_soh = soh_values(i);

fprintf('\nParams after setting scenario fields:\n');
disp(params);
fprintf('\nField names after setting scenario fields:\n');
fields_after_setup = fieldnames(params);
for i = 1:numel(fields_after_setup)
    fprintf('  %d: ''%s''\n', i, fields_after_setup{i});
end

% Call degradation_mode_library
fprintf('\nCalling degradation_mode_library(''%s'', %.1f)...\n', degradation_modes{i}, soh_values(i));
[degradation_params, mode_info] = degradation_mode_library(degradation_modes{i}, soh_values(i));
fprintf('degradation_params:\n');
disp(degradation_params);
fprintf('\nDegradation field names:\n');
deg_fields = fieldnames(degradation_params);
for i = 1:numel(deg_fields)
    fprintf('  %d: ''%s''\n', i, deg_fields{i});
end

% Try the struct merge
fprintf('\nAttempting: params = struct(params, degradation_params)...\n');
try
    params = struct(params, degradation_params);
    fprintf('SUCCESS! Merged params:\n');
    disp(params);
catch ME
    fprintf('FAILED: %s\n', ME.message);
    fprintf('Location: %s\n', ME.stack(1).file);
    fprintf('Line: %d\n', ME.stack(1).line);
end
end

function params = load_parameters()
%LOAD_PARAMETERS Load system parameters
    params = struct();
    params.NOMINAL_CAPACITY_AH = 2.5;
    params.R0 = 0.02;
    params.R1 = 0.01;
    params.C1 = 1000.0;
    params.OCV_SLOPE = 0.5;
    params.OCV_INTERCEPT = 3.0;
    params.EXCITATION_PULSE_WIDTH_S = 10e-6;
    params.EXCITATION_PULSE_AMPLITUDE_A = 0.5;
    params.EXCITATION_PERIOD_S = 0.1;
    params.SOS = 2500.0;
    params.ULTRASONIC_PATH_LENGTH_M = 0.01;
    params.ULTRASONIC_FREQ_HZ = 40e3;
    params.ULTRASONIC_BANDWIDTH_HZ = 5e3;
    params.THERMAL_CAPACITY_J_PER_K = 500.0;
    params.THERMAL_RESISTANCE_K_PER_W = 2.0;
    params.AMBIENT_TEMPERATURE_K = 298.15;
    params.DAQ_SAMPLING_RATE_HZ = 200e3;
    params.SAMPLES_PER_CYCLE = round(params.DAQ_SAMPLING_RATE_HZ * params.EXCITATION_PERIOD_S);
    params.ADC_BITS = 12;
    params.ADC_FS_V = 5.0;
    params.ADC_Q = params.ADC_FS_V / (2^params.ADC_BITS);
    params.ELECTRICAL_NOISE_STD_V = 0.001;
    params.ULTRASONIC_TOF_NOISE_STD_S = 1e-9;
    params.THERMAL_NOISE_STD_K = 0.01;
    params.SEQ_LENGTH = params.SAMPLES_PER_CYCLE;
    params.NUM_DEGRADATION_MODES = 6;
    params.BATCH_SIZE = 32;
    params.NUM_EPOCHS = 50;
    params.LEARNING_RATE = 0.001;
    params.VALIDATION_SPLIT = 0.2;
    params.SOH_THRESHOLD_RECOVERABLE = 80.0;
    params.DEGRADATION_PROB_THRESHOLD = 0.6;
    params.SOH_THRESHOLD_SEVERE = 60.0;
    params.MAX_RECOVERY_TIME_S = 300.0;
    params.current_soc = 0.5;
    params.current_degradation = 'Healthy';
    params.noise_level = 0.1;
    params.excitation_amplitude = 0.5;
end