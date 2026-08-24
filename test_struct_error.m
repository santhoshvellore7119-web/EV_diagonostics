clear; close all; clc;
addpath(genpath(pwd));
addpath(genpath(fullfile(pwd, 'matlab_simulink_demo')));
addpath(genpath(fullfile(pwd, 'Task1_MATLAB_Simulink_Demo', 'matlab_simulink_demo')));

% Reproduce the exact scenario from battery_system_demo.m
params = load_parameters();
params.current_soc = 0.5;
params.current_degradation = 'li_plating';
params.current_soh = 95.0;

fprintf('Params before degradation_mode_library:\n');
disp(params);
fprintf('Params field names:\n');
names = fieldnames(params);
for i = 1:numel(names)
    fprintf('  %d: ''%s'' (length=%d, ischar=%d)\n', i, names{i}, length(names{i}), ischar(names{i}));
    if ~ischar(names{i}) || isempty(names{i})
        fprintf('    ^^^ INVALID FIELD NAME ^^^\n');
    end
end

% Get degradation parameters
[degradation_params, mode_info] = degradation_mode_library('li_plating', 95.0);
fprintf('\nDegradation params:\n');
disp(degradation_params);
fprintf('Degradation param field names:\n');
deg_names = fieldnames(degradation_params);
for i = 1:numel(deg_names)
    fprintf('  %d: ''%s'' (length=%d, ischar=%d)\n', i, deg_names{i}, length(deg_names{i}), ischar(deg_names{i}));
    if ~ischar(deg_names{i}) || isempty(deg_names{i})
        fprintf('    ^^^ INVALID FIELD NAME ^^^\n');
    end
end

% Try the struct merge that's failing
fprintf('\nTrying: params = struct(params, degradation_params)...\n');
try
    params_merged = struct(params, degradation_params);
    fprintf('SUCCESS!\n');
    disp(params_merged);
catch ME
    fprintf('FAILED: %s\n', ME.message);
    fprintf('This is the error we need to fix!\n');

    % Let's try a workaround - manually copy the fields
    fprintf('\nTrying workaround: create new struct and copy fields...\n');
    params_workaround = params;
    deg_fields = fieldnames(degradation_params);
    for i = 1:numel(deg_fields)
        field_name = deg_names{i};
        params_workaround.(field_name) = degradation_params.(field_name);
        fprintf('  Copied field: %s\n', field_name);
    end
    fprintf('Workaround SUCCESS!\n');
    disp(params_workaround);
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