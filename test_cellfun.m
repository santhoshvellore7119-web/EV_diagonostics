%% Test cellfun and isstruct behavior
clear; close all; clc;

% Create test data similar to what's in the debug test
modes = {struct('mode','li_plating','weight',0.4), ...
         struct('mode','active_material_loss','weight',0.6)};

fprintf('Testing modes variable:\n');
fprintf('  Type: %s\n', class(modes));
fprintf('  Size: %dx%d\n', size(modes,1), size(modes,2));
fprintf('  Contents:\n');
for i = 1:numel(modes)
    fprintf('    Element %d: ', i);
    if isstruct(modes{i})
        fprintf('struct with fields: ');
        fields = fieldnames(modes{i});
        for j = 1:numel(fields)
            fprintf('%s ', fields{j});
        end
        fprintf('\n');
    else
        fprintf('NOT A STRUCT\n');
    end
end

% Test cellfun with isstruct
fprintf('\nTesting cellfun(@isstruct, modes):\n');
result = cellfun(@isstruct, modes);
fprintf('  Result: [%d %d]\n', result(1), result(2));
fprintf('  all(result): %d\n', all(result));

% Test what happens with isfield on the elements
fprintf('\nTesting isfield on elements:\n');
for i = 1:numel(modes)
    fprintf('  Element %d: ', i);
    has_mode = isfield(modes{i}, 'mode');
    has_weight = isfield(modes{i}, 'weight');
    fprintf('has mode=%d, has weight=%d\n', has_mode, has_weight);
end