%% Automated Launch Script for Simulink & MATLAB Battery Diagnostic Digital Twin
% Run this file from MATLAB:
% >> launch_simulink

clear; clc; close all;

fprintf('========================================================================\n');
fprintf(' [SIMULINK LAUNCHER] Initializing Multi-Modal Battery Digital Twin...\n');
fprintf('========================================================================\n');

% 1. Add project directories to MATLAB search path
demo_dir = fileparts(mfilename('fullpath'));
project_root = fullfile(demo_dir, '..');
addpath(genpath(project_root));
addpath(genpath(demo_dir));
models_dir = fullfile(demo_dir, 'models');
utils_dir = fullfile(demo_dir, 'utils');
addpath(models_dir);
addpath(utils_dir);

model_name = 'ev_cell_digital_twin';
slx_file = fullfile(models_dir, [model_name, '.slx']);

% 2. Check if model can be opened, or build natively if needed
need_build = false;
if ~exist(slx_file, 'file')
    fprintf('[SIMULINK LAUNCHER] %s not found. Triggering automated build...\n', slx_file);
    need_build = true;
else
    try
        load_system(slx_file);
        fprintf('[SIMULINK LAUNCHER] %s successfully validated.\n', slx_file);
    catch ME
        fprintf('[SIMULINK LAUNCHER] Rebuilding model for this MATLAB release (%s)...\n', version);
        need_build = true;
    end
end

if need_build
    run(fullfile(utils_dir, 'build_simulink_model.m'));
end

% 3. Open the Simulink model
fprintf('[SIMULINK LAUNCHER] Opening %s in Simulink...\n', model_name);
open_system(model_name);

% 4. Run dynamic simulation
fprintf('[SIMULINK LAUNCHER] Executing simulation...\n');
sim_out = sim(model_name);
fprintf('[SIMULINK LAUNCHER] Simulation completed successfully!\n');

fprintf('\n>>> Ready! Model is open in Simulink.\n');
fprintf('>>> To test all degradation modes and generate comparison plots, run:\n');
fprintf('    battery_system_demo\n\n');
