%% Test specific case that's failing
clear; close all; clc;

% Add necessary paths
addpath(genpath(pwd));
addpath(genpath(fullfile(pwd, 'matlab_simulink_demo')));

fprintf('Testing specific case from Test 1...\n');

try
    fprintf('Calling degradation_mode_library(''li_plating'', 85.0)...\n');
    [params1, info1] = degradation_mode_library('li_plating', 85.0);
    fprintf('Success!\n');
    fprintf('params1 = \n');
    disp(params1);
    fprintf('info1 = \n');
    disp(info1);
    fprintf('R0_scale: %.3f\n', params1.R0_scale);
    fprintf('SOH adjustment applied: %d\n', info1.soh_adjustment);
catch ME
    fprintf('ERROR: %s\n', ME.message);
    fprintf('Location: %s\n', ME.stack(1).file);
    fprintf('Line: %d\n', ME.stack(1).line);

    % Let's also check if the params1 struct has the expected fields
    if exist('params1', 'var')
        fprintf('Checking params1 fields:\n');
        fields = fieldnames(params1);
        for i = 1:numel(fields)
            fprintf('  %s\n', fields{i});
        end
    end
end