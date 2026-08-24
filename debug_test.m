%% Debug test for degradation_mode_library
clear; close all; clc;

fprintf('Testing degradation_mode_library...\n');

% Add necessary paths
addpath(genpath(pwd));
addpath(genpath(fullfile(pwd, 'matlab_simulink_demo')));

try
    % Test basic functionality
    fprintf('Test 1: Basic call...\n');
    [params, info] = degradation_mode_library('li_plating', 85.0);
    fprintf('  Success!\n');
    fprintf('  R0_scale = %.3f\n', params.R0_scale);

    % Test mixed mode
    fprintf('Test 2: Mixed mode...\n');
    modes = {struct('mode','li_plating','weight',0.4), ...
             struct('mode','active_material_loss','weight',0.6)};
    [params2, info2] = degradation_mode_library(modes, 75.0);
    fprintf('  Success!\n');
    fprintf('  R0_scale = %.3f\n', params2.R0_scale);

    % Test healthy
    fprintf('Test 3: Healthy case...\n');
    [params3, info3] = degradation_mode_library('healthy', 98.0);
    fprintf('  Success!\n');
    fprintf('  R0_scale = %.3f\n', params3.R0_scale);

catch ME
    fprintf('Error: %s\n', ME.message);
    fprintf('Location: %s\n', ME.stack(1).file);
    fprintf('Line: %d\n', ME.stack(1).line);
end