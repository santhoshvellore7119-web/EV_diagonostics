clear; close all; clc;
addpath(genpath(pwd));
addpath(genpath(fullfile(pwd, 'matlab_simulink_demo')));
addpath(genpath(fullfile(pwd, 'Task1_MATLAB_Simulink_Demo', 'matlab_simulink_demo')));

% Test what the function returns
[degradation_params, mode_info] = degradation_mode_library('li_plating', 85.0);
fprintf('degradation_params:\n');
disp(degradation_params);
fprintf('\nField names:\n');
f = fieldnames(degradation_params);
for i = 1:numel(f)
    fprintf('  %d: ''%s''\n', i, f{i});
end

% Check if any field names are empty or invalid
for i = 1:numel(f)
    if isempty(f{i}) || ~ischar(f{i})
        fprintf('ERROR: Field %d is invalid: ''%s''\n', i, f{i});
    end
end