%% Replicate Test 1 from test_matlab_enhancements_fixed.m
clear; close all; clc;

% Add necessary paths to MATLAB search path
addpath(genpath(pwd));
addpath(genpath(fullfile(pwd, 'matlab_simulink_demo')));
addpath(genpath(fullfile(pwd, 'Task1_MATLAB_Simulink_Demo', 'matlab_simulink_demo')));

fprintf('=== Replicating Test 1: Enhanced Degradation Mode Library ===\n');

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
    fprintf('Location: %s\n', ME.stack(1).file);
    fprintf('Line: %d\n', ME.stack(1).line);
end