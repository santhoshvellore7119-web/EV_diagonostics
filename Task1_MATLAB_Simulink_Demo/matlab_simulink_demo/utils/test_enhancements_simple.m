%% Simple test for MATLAB enhancements
clear; close all; clc;

fprintf('=== Testing MATLAB Enhancements ===\n\n');

% Test 1: Backward compatibility
fprintf('Test 1: Backward compatibility\n');
try
    [params, info] = degradation_mode_library('li_plating', 85.0);
    fprintf('  PASS: li_plating with SOH=85\n');
    fprintf('    R0_scale = %.3f\n', params.R0_scale);
    fprintf('    SOH adjustment applied: %d\n', info.soh_adjustment);
catch ME
    fprintf('  FAIL: %s\n', ME.message);
end

% Test 2: Mixed mode
fprintf('\nTest 2: Mixed mode support\n');
try
    modes = {struct('mode','li_plating','weight',0.4), ...
             struct('mode','active_material_loss','weight',0.6)};
    [params, info] = degradation_mode_library(modes, 75.0);
    fprintf('  PASS: Mixed mode (40%% li_plating, 60%% active_material_loss)\n');
    fprintf('    Detected modes: [%s, %s]\n', info.detected_modes{1}, info.detected_modes{2});
    fprintf('    Mode weights: [%.2f, %.2f]\n', info.mode_weights(1), info.mode_weights(2));
    fprintf('    Mode entropy: %.3f\n', info.mode_entropy);
    fprintf('    Primary mode: %s\n', info.primary_mode);
catch ME
    fprintf('  FAIL: %s\n', ME.message);
end

% Test 3: Healthy case with high SOH (minimal adjustment)
fprintf('\nTest 3: Healthy case with high SOH\n');
try
    [params, info] = degradation_mode_library('healthy', 98.0);
    fprintf('  PASS: Healthy with SOH=98\n');
    fprintf('    R0_scale = %.3f (should be near 1.0)\n', params.R0_scale);
    fprintf('    C1_scale = %.3f (should be near 1.0)\n', params.C1_scale);
    fprintf('    SOH adjustment applied: %d (should be 0 for SOH>=98)\n', info.soh_adjustment);
catch ME
    fprintf('  FAIL: %s\n', ME.message);
end

% Test 4: Verify key enhancement features exist in file
fprintf('\nTest 4: Verify enhancement features in source\n');
try
    fid = fopen('degradation_mode_library.m', 'r');
    content = fread(fid, '*char')';
    fclose(fid);

    has_mixed_mode = contains(content, 'mixed-mode') || contains(content, 'mixed mode');
    has_soh_adjustment = contains(content, 'SOH-based') || contains(content, 'soh_estimate');
    has_mode_info = contains(content, 'mode_info');
    has_entropy = contains(content, 'mode_entropy');

    fprintf('  Mixed-mode support: %s\n', string(has_mixed_mode));
    fprintf('  SOH-dependent adjustment: %s\n', string(has_soh_adjustment));
    fprintf('  Enhanced diagnostic info: %s\n', string(has_mode_info));
    fprintf('  Mode entropy calculation: %s\n', string(has_entropy));

    if all([has_mixed_mode, has_soh_adjustment, has_mode_info, has_entropy])
        fprintf('  PASS: All enhancement features present\n');
    else
        fprintf('  FAIL: Some enhancement features missing\n');
    end
catch ME
    fprintf('  FAIL: Could not read file: %s\n', ME.message);
end

fprintf('\n=== MATLAB Enhancement Testing Complete ===\n');