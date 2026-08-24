addpath(genpath(pwd));
addpath(genpath(fullfile(pwd, 'matlab_simulink_demo')));
addpath(genpath(fullfile(pwd, 'Task1_MATLAB_Simulink_Demo', 'matlab_simulink_demo')));
params = load_parameters();
params.current_soc = 0.5;
params.current_degradation = 'li_plating';
params.current_soh = 95.0;
[degradation_params, mode_info] = degradation_mode_library('li_plating', 95.0);
deg_fields = fieldnames(degradation_params);
for i = 1:numel(deg_fields)
    params.(deg_fields{i}) = degradation_params.(deg_fields{i});
end
P = params;
fprintf('Is struct: %d\n', isstruct(P));
fprintf('Field names:\n');
names = fieldnames(P);
for i = 1:numel(names)
    fprintf('  %d: ''%s''\n', i, names{i});
end
try
    v = getfield(P, 'R0_scale', 1.0);
    fprintf('getfield success: %s\n', mat2str(v));
catch
    fprintf('getfield failed\n');
end
try
    v2 = P.R0_scale;
    fprintf('direct access success: %s\n', mat2str(v2));
catch
    fprintf('direct access failed\n');
end
exit;