clear; close all; clc;
addpath(genpath(pwd));
addpath(genpath(fullfile(pwd, 'matlab_simulink_demo')));
addpath(genpath(fullfile(pwd, 'Task1_MATLAB_Simulink_Demo', 'matlab_simulink_demo')));

% Simulate the first iteration of the loop
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

i = 1; % first iteration
fprintf('Testing iteration %d: %s\n', i, scenarios{i});
fprintf('Mode: %s, SOH: %.1f, SOC: %.2f\n', degradation_modes{i}, soh_values(i), soc_values(i));

% Load base params
params = load_parameters();
% Set scenario fields
params.current_soc = soc_values(i);
params.current_degradation = degradation_modes{i};
params.current_soh = soh_values(i);
fprintf('Params after setting scenario fields:\n');
fprintf('  current_soc: %.2f\n', params.current_soc);
fprintf('  current_degradation: %s\n', params.current_degradation);
fprintf('  current_soh: %.1f\n', params.current_soh);

% Call degradation_mode_library
[degradation_params, mode_info] = degradation_mode_library(degradation_modes{i}, soh_values(i));
fprintf('Degradation params returned:\n');
disp(degradation_params);

% Merge into params using our new method
deg_fields = fieldnames(degradation_params);
for j = 1:numel(deg_fields)
    field_name = deg_fields{j};
    params.(field_name) = degradation_params.(field_name);
end
fprintf('Params after merging degradation params (showing new fields):\n');
for j = 1:numel(deg_fields)
    field_name = deg_fields{j};
    fprintf('  %s: %s\n', field_name, mat2str(params.(field_name)));
end

% Now check if P (which is params) is a struct and has the fields
P = params;
fprintf('\nChecking P:\n');
fprintf('  Is P a struct? %d\n', isstruct(P));
fprintf('  Field names of P:\n');
names = fieldnames(P);
for j = 1:numel(names)
    fprintf('    %d: ''%s''\n', j, names{j});
end

% Now try getfield for R0_scale
fprintf('\nTrying getfield(P, ''R0_scale'', 1.0):\n');
try
    val = getfield(P, 'R0_scale', 1.0);
    fprintf('  Success: %s\n', mat2str(val));
catch ME
    fprintf('  Failed: %s\n', ME.message);
end

% Try accessing via dynamic field
fprintf('Trying P.R0_scale:\n');
try
    val2 = P.R0_scale;
    fprintf('  Success: %s\n', mat2str(val2));
catch ME2
    fprintf('  Failed: %s\n', ME2.message);
end

% Check if the field exists
fprintf('isfield(P, ''R0_scale''): %d\n', isfield(P, 'R0_scale'));
if isfield(P, 'R0_scale')
    fprintf('  P.R0_scale = %s\n', mat2str(P.R0_scale));
end
end