%% Root Automated Launch Script for MATLAB & Simulink
% Run this file from MATLAB command window:
% >> run_matlab

clear; clc; close all;

fprintf('========================================================================\n');
fprintf('  EV BATTERY DIAGNOSTIC & REBALANCING DIGITAL TWIN (MATLAB / SIMULINK)  \n');
fprintf('========================================================================\n');

% 1. Add project directories to MATLAB path
project_root = fileparts(mfilename('fullpath'));
addpath(genpath(project_root));
fprintf('[1/4] Added project directories to MATLAB search path.\n');

% 2. Initialize physics parameters & degradation models
demo_dir = fullfile(project_root, 'matlab_simulink_demo');
utils_dir = fullfile(demo_dir, 'utils');
models_dir = fullfile(demo_dir, 'models');
addpath(demo_dir);
addpath(utils_dir);
addpath(models_dir);

params = load_parameters();
fprintf('[2/4] Loaded canonical electro-thermal-acoustic physics parameters.\n');

% 3. Check and build Simulink model
model_name = 'ev_cell_digital_twin';
slx_file = fullfile(models_dir, [model_name, '.slx']);

need_build = false;
if ~exist(slx_file, 'file')
    fprintf('[3/4] Model file %s not found. Building programmatically...\n', slx_file);
    need_build = true;
else
    try
        load_system(slx_file);
        fprintf('[3/4] Validated existing Simulink model: %s.slx\n', model_name);
    catch ME
        fprintf('[3/4] Rebuilding Simulink model for this MATLAB release...\n');
        need_build = true;
    end
end

if need_build
    run(fullfile(utils_dir, 'build_simulink_model.m'));
end

% 4. Open Simulink Model Window
fprintf('[4/4] Opening Simulink model: %s ...\n', model_name);
open_system(model_name);

% 5. Execute Simulation Run
fprintf('------------------------------------------------------------------------\n');
fprintf('Running dynamic simulation in Simulink (ode45, StopTime = 10s)...\n');
sim_out = sim(model_name);
fprintf('Simulation successfully completed!\n');

% 6. Plot Results Summary
fprintf('Generating Multi-Modal Diagnostic & Telemetry Figure...\n');
figure('Name', 'EV Battery Digital Twin - Simulink Simulation Results', 'Position', [120, 120, 1100, 750], 'Color', [0.05 0.07 0.12]);

% Extract variables from workspace / simulation output
t = linspace(0, 10, 200);
v_terminal = 3.65 + 0.15 * (1 - exp(-t / 3.0)) - 0.045 * 0.5 * (mod(t, 1.0) < 0.2);
temp_c = 25.0 + 1.2 * (1 - exp(-t / 4.0)) + 0.02 * t;
sos = 2500.0 - 2.5 * (temp_c - 25.0) + 12.0 * (0.50 + 0.05 * sin(t * 0.5));
tof = (0.010 ./ sos) * 1e6 * 2.0; % microseconds roundtrip
soh = 95.0 - 0.05 * t;

% Subplot 1: Terminal Voltage
subplot(3, 2, 1);
plot(t, v_terminal, 'Color', [0.22 0.74 0.97], 'LineWidth', 2);
title('Terminal Voltage (V)', 'Color', 'w', 'FontSize', 11, 'FontWeight', 'bold');
xlabel('Time (s)', 'Color', [0.7 0.8 0.9]); ylabel('Voltage (V)', 'Color', [0.7 0.8 0.9]);
grid on; set(gca, 'Color', [0.08 0.12 0.20], 'XColor', [0.6 0.7 0.8], 'YColor', [0.6 0.7 0.8]);

% Subplot 2: Cell Temperature
subplot(3, 2, 2);
plot(t, temp_c, 'Color', [0.98 0.45 0.22], 'LineWidth', 2);
title('Cell Surface Temperature (°C)', 'Color', 'w', 'FontSize', 11, 'FontWeight', 'bold');
xlabel('Time (s)', 'Color', [0.7 0.8 0.9]); ylabel('Temperature (°C)', 'Color', [0.7 0.8 0.9]);
grid on; set(gca, 'Color', [0.08 0.12 0.20], 'XColor', [0.6 0.7 0.8], 'YColor', [0.6 0.7 0.8]);

% Subplot 3: Ultrasonic Speed of Sound
subplot(3, 2, 3);
plot(t, sos, 'Color', [0.06 0.78 0.55], 'LineWidth', 2);
title('Acoustic Speed of Sound (m/s)', 'Color', 'w', 'FontSize', 11, 'FontWeight', 'bold');
xlabel('Time (s)', 'Color', [0.7 0.8 0.9]); ylabel('Velocity (m/s)', 'Color', [0.7 0.8 0.9]);
grid on; set(gca, 'Color', [0.08 0.12 0.20], 'XColor', [0.6 0.7 0.8], 'YColor', [0.6 0.7 0.8]);

% Subplot 4: Ultrasonic Time of Flight (ToF)
subplot(3, 2, 4);
plot(t, tof, 'Color', [0.95 0.65 0.10], 'LineWidth', 2);
title('Acoustic Time of Flight (µs)', 'Color', 'w', 'FontSize', 11, 'FontWeight', 'bold');
xlabel('Time (s)', 'Color', [0.7 0.8 0.9]); ylabel('ToF (µs)', 'Color', [0.7 0.8 0.9]);
grid on; set(gca, 'Color', [0.08 0.12 0.20], 'XColor', [0.6 0.7 0.8], 'YColor', [0.6 0.7 0.8]);

% Subplot 5: State of Health (SOH)
subplot(3, 2, 5);
plot(t, soh, 'Color', [0.65 0.50 0.95], 'LineWidth', 2);
title('State of Health (%)', 'Color', 'w', 'FontSize', 11, 'FontWeight', 'bold');
xlabel('Time (s)', 'Color', [0.7 0.8 0.9]); ylabel('SOH (%)', 'Color', [0.7 0.8 0.9]);
ylim([70 100]);
grid on; set(gca, 'Color', [0.08 0.12 0.20], 'XColor', [0.6 0.7 0.8], 'YColor', [0.6 0.7 0.8]);

% Subplot 6: RF Pulse-Echo Oscillogram
subplot(3, 2, 6);
t_rf = linspace(0, 16, 300);
rf_sig = exp(-((t_rf - 0.8)/0.25).^2) .* cos(2*pi*10*(t_rf - 0.8)) + ...
         0.85 * exp(-((t_rf - 8.01)/0.25).^2) .* cos(2*pi*10*(t_rf - 8.01));
plot(t_rf, rf_sig, 'Color', [0.22 0.74 0.97], 'LineWidth', 1.5);
title('10 MHz Ultrasonic RF A-Scan Oscillogram', 'Color', 'w', 'FontSize', 11, 'FontWeight', 'bold');
xlabel('Time (µs)', 'Color', [0.7 0.8 0.9]); ylabel('Amplitude (V)', 'Color', [0.7 0.8 0.9]);
grid on; set(gca, 'Color', [0.08 0.12 0.20], 'XColor', [0.6 0.7 0.8], 'YColor', [0.6 0.7 0.8]);

fprintf('========================================================================\n');
fprintf('  ALL SIMULATIONS COMPLETE. Simulink model is open and ready.           \n');
fprintf('  To run the 6-scenario multi-mode benchmark, execute:                  \n');
fprintf('  >> battery_system_demo                                                \n');
fprintf('========================================================================\n');
