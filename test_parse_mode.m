%% Test parse_mode_input function by calling degradation_mode_library which should call it
clear; close all; clc;

% Add necessary paths
addpath(genpath(pwd));
addpath(genpath(fullfile(pwd, 'matlab_simulink_demo')));

% Clear any cached versions of the function
if exist('parse_mode_input', 'file')
    clear parse_mode_input
end

% Test the exact same input as in debug_test.m
modes = {struct('mode','li_plating','weight',0.4), ...
         struct('mode','active_material_loss','weight',0.6)};

fprintf('Testing degradation_mode_library with mixed mode input...\n');
fprintf('Input modes: ');
disp(modes);

try
    [params, info] = degradation_mode_library(modes, 75.0);
    fprintf('SUCCESS!\n');
    fprintf('R0_scale = %.3f\n', params.R0_scale);
    fprintf('Detected modes: %s\n', strjoin(info.detected_modes, ', '));
    fprintf('Mode weights: [%f %f]\n', info.mode_weights(1), info.mode_weights(2));
catch ME
    fprintf('ERROR: %s\n', ME.message);
    fprintf('Location: %s\n', ME.stack(1).file);
    fprintf('Line: %d\n', ME.stack(1).line);

    % Let's also try to call parse_mode_input directly if we can
    if exist('parse_mode_input', 'file')
        fprintf('\nTrying direct call to parse_mode_input...\n');
        try
            [mode_names, mode_weights] = parse_mode_input(modes);
            fprintf('Direct call SUCCESS!\n');
            fprintf('mode_names: %s\n', strjoin(mode_names, ', '));
            fprintf('mode_weights: [%f %f]\n', mode_weights(1), mode_weights(2));
        catch ME2
            fprintf('Direct call FAILED: %s\n', ME2.message);
        end
    else
        fprintf('\nparse_mode_input function not found\n');
    end
end