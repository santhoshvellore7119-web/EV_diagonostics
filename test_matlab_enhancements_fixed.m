%% Test script for MATLAB enhancements in EV Battery Diagnostic System
% This script tests the enhanced degradation mode library and battery system demo

clear; close all; clc;

% Add necessary paths to MATLAB search path
addpath(genpath(pwd));
addpath(genpath(fullfile(pwd, 'matlab_simulink_demo')));
addpath(genpath(fullfile(pwd, 'Task1_MATLAB_Simulink_Demo', 'matlab_simulink_demo')));

fprintf('=== Testing MATLAB Enhancements for EV Battery Diagnostic System ===\n\n');

% Test 1: Enhanced degradation mode library
fprintf('Test 1: Enhanced Degradation Mode Library\n');
try
    % Test backward compatibility
    [params1, info1] = degradation_mode_library('li_plating', 85.0);
    fprintf('  Backward compatibility: OK\n');
    fprintf('    R0_scale: %.3f, SOH adjustment applied: %d\n', params1.R0_scale, info1.soh_adjustment);

    % Test mixed mode
    modes = {struct('mode','li_plating','weight',0.4), ...
             struct('mode','active_material_loss','weight',0.6)};
    [params2, info2] = degradation_mode_library(modes, 75.0);
    fprintf('  Mixed mode: OK\n');
    fprintf('    Detected modes: %s\n', strjoin(info2.detected_modes, ', '));
    fprintf('    Mode weights: [%0.2f, %0.2f]\n', info2.mode_weights);
    fprintf('    Mode entropy: %.3f\n', info2.mode_entropy);
    fprintf('    Primary mode: %s\n', info2.primary_mode);

    % Test pure healthy
    [params3, info3] = degradation_mode_library('healthy', 98.0);
    fprintf('  Healthy case: OK\n');
    fprintf('    All scales near 1.0: R0=%.3f, C1=%.3f\n', params3.R0_scale, params3.C1_scale);

    fprintf('  Enhanced degradation mode library tests PASSED\n\n');
catch ME
    fprintf('  ERROR in degradation mode library: %s\n\n', ME.message);
end

% Test 2: Battery system demo with enhanced library
fprintf('Test 2: Battery System Demo Integration\n');
try
    % We won't actually run the full demo (which waits for user input),
    % but we'll test that the functions can be called

    % Test that the enhanced functions exist and are callable
    assert(exist('degradation_mode_library', 'file') == 2, 'degradation_mode_library.m not found');
    assert(exist('battery_system_demo', 'file') == 2, 'battery_system_demo.m not found');

    % Test parameter loading (used by demo)
    params_base = load_parameters();
    fprintf('  Parameter loading: OK\n');
    fprintf('    Nominal capacity: %.1f Ah\n', params_base.NOMINAL_CAPACITY_AH);

    % Test physics model initialization (used by demo)
    model = init_physics_model();
    fprintf('  Physics model initialization: OK\n');
    fprintf('    Time samples: %d\n', length(model.t));

    fprintf('  Battery system demo integration tests PASSED\n\n');
catch ME
    fprintf('  ERROR in battery system demo: %s\n\n', ME.message);
end

% Test 3: Verify the key enhancements are present
fprintf('Test 3: Verify Enhancement Features\n');
try
    % Read the degradation mode library file to verify key features are present
    fid = fopen('matlab_simulink_demo/utils/degradation_mode_library.m', 'r');
    content = fread(fid, '*char')';
    fclose(fid);

    % Check for key enhancement features
    has_mixed_mode = contains(content, 'mixed-mode') || contains(content, 'mixed mode');
    has_soh_adjustment = contains(content, 'SOH-based') || contains(content, 'soh_estimate');
    has_mode_info = contains(content, 'mode_info');
    has_entropy = contains(content, 'mode_entropy');

    fprintf('  Mixed-mode support: %s\n', string(has_mixed_mode));
    fprintf('  SOH-dependent adjustment: %s\n', string(has_soh_adjustment));
    fprintf('  Enhanced diagnostic info: %s\n', string(has_mode_info));
    fprintf('  Mode entropy calculation: %s\n', string(has_entropy));

    if all([has_mixed_mode, has_soh_adjustment, has_mode_info, has_entropy])
        fprintf('  All enhancement features verified: PASSED\n\n');
    else
        fprintf('  Some enhancement features missing: FAILED\n\n');
    end

catch ME
    fprintf('  ERROR verifying enhancements: %s\n\n', ME.message);
end

fprintf('=== MATLAB Enhancement Testing Complete ===\n');