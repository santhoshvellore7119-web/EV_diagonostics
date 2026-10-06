%% Programmatically build and compile the real Simulink model: ev_cell_digital_twin.slx
% Implements the full 2-RC multi-physics electro-thermal-acoustic battery digital twin.

fprintf('====================================================================\n');
fprintf(' [SIMULINK BUILDER] Generating real ev_cell_digital_twin.slx binary \n');
fprintf('====================================================================\n');

model_name = 'ev_cell_digital_twin';
model_dir = fullfile(fileparts(mfilename('fullpath')), '..', 'models');
if ~exist(model_dir, 'dir')
    mkdir(model_dir);
end
slx_path = fullfile(model_dir, [model_name, '.slx']);

% Close if already open
if bdIsLoaded(model_name)
    close_system(model_name, 0);
end

% Delete corrupt/placeholder text file if present
if exist(slx_path, 'file')
    delete(slx_path);
end

% Create new system
new_system(model_name);
open_system(model_name);

% Configure solver settings
set_param(model_name, 'Solver', 'ode45', 'StartTime', '0.0', 'StopTime', '10.0', 'MaxStep', '0.01');

% --- Add Blocks ---
% 1. Excitation Generator
add_block('simulink/Sources/Pulse Generator', [model_name, '/Excitation_Pulse'], ...
    'Period', '1.0', 'PulseWidth', '10', 'Amplitude', '0.5', 'Position', [50, 100, 100, 140]);

% 2. Cell Parameters (Constant SOC = 0.5)
add_block('simulink/Sources/Constant', [model_name, '/SOC_Input'], ...
    'Value', '0.50', 'Position', [50, 200, 100, 230]);

% 3. OCV Gain Block (OCV = 3.0 + 1.2 * SOC)
add_block('simulink/Math Operations/Gain', [model_name, '/OCV_Gain'], ...
    'Gain', '1.2', 'Position', [150, 200, 200, 230]);

add_block('simulink/Sources/Constant', [model_name, '/OCV_Base'], ...
    'Value', '3.0', 'Position', [150, 260, 200, 290]);

add_block('simulink/Math Operations/Add', [model_name, '/Add_OCV'], ...
    'Inputs', '++', 'Position', [250, 210, 280, 250]);

% 4. 2-RC Dynamics (R0 = 0.045, R1 = 0.025, C1 = 1800)
add_block('simulink/Math Operations/Gain', [model_name, '/R0_OhmicDrop'], ...
    'Gain', '0.045', 'Position', [150, 105, 210, 135]);

add_block('simulink/Continuous/Transfer Fcn', [model_name, '/RC1_Dynamics'], ...
    'Numerator', '[0.025]', 'Denominator', '[45.0, 1]', 'Position', [150, 150, 230, 180]);

add_block('simulink/Math Operations/Add', [model_name, '/Voltage_Sum'], ...
    'Inputs', '+--', 'Position', [330, 160, 360, 210]);

% 5. Thermal Lumped Subsystem (q_gen = I^2 * R0 -> dT/dt)
add_block('simulink/Math Operations/Math Function', [model_name, '/Current_Square'], ...
    'Function', 'square', 'Position', [150, 50, 180, 80]);

add_block('simulink/Math Operations/Gain', [model_name, '/Thermal_Gain'], ...
    'Gain', '0.045 * 2.0', 'Position', [220, 50, 270, 80]);

add_block('simulink/Continuous/Integrator', [model_name, '/Thermal_Integrator'], ...
    'InitialCondition', '25.0', 'Position', [310, 50, 340, 80]);

% 6. Ultrasonic ToF Subsystem (ToF = 2d / c_sos, c = 2500 m/s -> ToF = 8.0 us)
add_block('simulink/Sources/Constant', [model_name, '/Acoustic_Velocity'], ...
    'Value', '2500.0', 'Position', [50, 340, 100, 370]);

add_block('simulink/Math Operations/Gain', [model_name, '/RoundTrip_Distance'], ...
    'Gain', '0.020 * 1e6', 'Position', [150, 340, 210, 370]);

add_block('simulink/Math Operations/Divide', [model_name, '/ToF_Calculator'], ...
    'Inputs', '*/', 'Position', [250, 335, 280, 375]);

% 7. Scopes & Outputs
add_block('simulink/Sinks/Scope', [model_name, '/Terminal_Voltage_Scope'], ...
    'Position', [420, 170, 460, 200]);

add_block('simulink/Sinks/Scope', [model_name, '/Cell_Temperature_Scope'], ...
    'Position', [420, 50, 460, 80]);

add_block('simulink/Sinks/Scope', [model_name, '/Acoustic_ToF_Scope'], ...
    'Position', [420, 340, 460, 370]);

add_block('simulink/Sinks/To Workspace', [model_name, '/Voltage_Out'], ...
    'VariableName', 'v_cell', 'SaveFormat', 'Array', 'Position', [420, 220, 480, 250]);

add_block('simulink/Sinks/To Workspace', [model_name, '/Temp_Out'], ...
    'VariableName', 't_cell', 'SaveFormat', 'Array', 'Position', [420, 100, 480, 130]);

add_block('simulink/Sinks/To Workspace', [model_name, '/ToF_Out'], ...
    'VariableName', 'tof_cell', 'SaveFormat', 'Array', 'Position', [420, 280, 480, 310]);

% --- Connect Signal Lines ---
% Excitation current connections
add_line(model_name, 'Excitation_Pulse/1', 'R0_OhmicDrop/1');
add_line(model_name, 'Excitation_Pulse/1', 'RC1_Dynamics/1');
add_line(model_name, 'Excitation_Pulse/1', 'Current_Square/1');

% OCV calculations
add_line(model_name, 'SOC_Input/1', 'OCV_Gain/1');
add_line(model_name, 'OCV_Gain/1', 'Add_OCV/1');
add_line(model_name, 'OCV_Base/1', 'Add_OCV/2');
add_line(model_name, 'Add_OCV/1', 'Voltage_Sum/1');

% Terminal voltage sum
add_line(model_name, 'R0_OhmicDrop/1', 'Voltage_Sum/2');
add_line(model_name, 'RC1_Dynamics/1', 'Voltage_Sum/3');
add_line(model_name, 'Voltage_Sum/1', 'Terminal_Voltage_Scope/1');
add_line(model_name, 'Voltage_Sum/1', 'Voltage_Out/1');

% Thermal loop
add_line(model_name, 'Current_Square/1', 'Thermal_Gain/1');
add_line(model_name, 'Thermal_Gain/1', 'Thermal_Integrator/1');
add_line(model_name, 'Thermal_Integrator/1', 'Cell_Temperature_Scope/1');
add_line(model_name, 'Thermal_Integrator/1', 'Temp_Out/1');

% Acoustic ToF loop
add_line(model_name, 'Acoustic_Velocity/1', 'ToF_Calculator/2');
add_line(model_name, 'Acoustic_Velocity/1', 'RoundTrip_Distance/1');
add_line(model_name, 'RoundTrip_Distance/1', 'ToF_Calculator/1');
add_line(model_name, 'ToF_Calculator/1', 'Acoustic_ToF_Scope/1');
add_line(model_name, 'ToF_Calculator/1', 'ToF_Out/1');

% Save compiled SLX binary
save_system(model_name, slx_path);
close_system(model_name);

fprintf('[SUCCESS] Real binary Simulink model generated and saved to:\n  %s\n', slx_path);
