%% Debug the actual degradation_mode_library function
clear; close all; clc;

% Add necessary paths
addpath(genpath(pwd));
addpath(genpath(fullfile(pwd, 'matlab_simulink_demo')));

% Test the exact same input as in debug_test.m
modes = {struct('mode','li_plating','weight',0.4), ...
         struct('mode','active_material_loss','weight',0.6)};

fprintf('Testing parse_mode_input directly...\n');
fprintf('Input modes: ');
disp(modes);

% Call parse_mode_input directly to see what happens
try
    [mode_names, mode_weights] = parse_mode_input(modes);
    fprintf('SUCCESS!\n');
    fprintf('mode_names: %s\n', strjoin(mode_names, ', '));
    fprintf('mode_weights: [%f %f]\n', mode_weights(1), mode_weights(2));
catch ME
    fprintf('ERROR in parse_mode_input: %s\n', ME.message);
    fprintf('Location: %s\n', ME.stack(1).file);
    fprintf('Line: %d\n', ME.stack(1).line);

    % Let's manually trace through what should happen
    fprintf('\n--- Manual tracing ---\n');
    fprintf('Input is cell: %d\n', iscell(modes));

    % Test the string check
    string_check = all(cellfun(@(x) ischar(x) || isstring(x), modes));
    fprintf('All elements are strings: %d\n', string_check);

    % Test the struct check
    struct_check = all(cellfun(@isstruct, modes));
    fprintf('All elements are structs: %d\n', struct_check);

    if struct_check
        fprintf('Checking each element for .mode and .weight fields:\n');
        for i = 1:numel(modes)
            elem = modes{i};
            fprintf('  Element %d: ', i);
            if isstruct(elem)
                fprintf('is struct. ');
                has_mode = isfield(elem, 'mode');
                has_weight = isfield(elem, 'weight');
                fprintf('has mode=%d, has weight=%d\n', has_mode, has_weight);
                if has_mode && has_weight
                    fprintf('    mode=%s, weight=%f\n', char(elem.mode), elem.weight);
                end
            else
                fprintf('NOT A STRUCT!!!\n');
            end
        end
    end
end