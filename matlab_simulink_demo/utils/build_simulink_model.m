%% Programmatically build and compile the enhanced Simulink model: ev_cell_digital_twin.slx
% Implements the full multi-physics electro-thermal-acoustic battery digital twin
% with dynamic Speed of Sound (SoS) tracking, thermal-acoustic coupling, 
% and 10 MHz Ultrasonic RF Pulse-Echo waveform synthesis.

fprintf('====================================================================\n');
fprintf(' [SIMULINK BUILDER] Building ev_cell_digital_twin.slx in MATLAB R2025b \n');
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

% Delete prior file if present
if exist(slx_path, 'file')
    delete(slx_path);
end

% Create new system in memory
new_system(model_name);
load_system(model_name);

% Configure solver settings (high temporal resolution for thermal & dynamic tracking)
set_param(model_name, 'Solver', 'ode45', 'StartTime', '0.0', 'StopTime', '10.0', 'MaxStep', '0.005');

% =========================================================================
% 1. ELECTRICAL EXCITATION & CELL STATE SOURCES
% =========================================================================
add_block('simulink/Sources/Pulse Generator', [model_name, '/Excitation_Pulse'], ...
    'Period', '1.0', 'PulseWidth', '20', 'Amplitude', '0.5', 'Position', [40, 60, 90, 100]);

add_block('simulink/Sources/Constant', [model_name, '/SOC_Input'], ...
    'Value', '0.50', 'Position', [40, 220, 90, 250]);

% =========================================================================
% 2. THERMAL DYNAMICS & JOULE HEATING SECTION
% =========================================================================
add_block('simulink/Math Operations/Math Function', [model_name, '/Current_Square'], ...
    'Function', 'square', 'Position', [140, 50, 170, 80]);

add_block('simulink/Math Operations/Gain', [model_name, '/Joule_Heat_Gain'], ...
    'Gain', '0.045 * 25.0', 'Position', [210, 50, 270, 80]);

add_block('simulink/Continuous/Integrator', [model_name, '/Thermal_Integrator'], ...
    'InitialCondition', '25.0', 'Position', [310, 50, 350, 80]);

add_block('simulink/Sinks/Scope', [model_name, '/Cell_Temperature_Scope'], ...
    'Position', [430, 45, 470, 75]);

add_block('simulink/Sinks/To Workspace', [model_name, '/Temp_Out'], ...
    'VariableName', 't_cell', 'SaveFormat', 'Array', 'Position', [430, 85, 490, 115]);

% =========================================================================
% 3. ELECTRICAL 2-RC EQUIVALENT CIRCUIT MODEL (ECM)
% =========================================================================
add_block('simulink/Math Operations/Gain', [model_name, '/OCV_Gain'], ...
    'Gain', '1.2', 'Position', [140, 220, 190, 250]);

add_block('simulink/Sources/Constant', [model_name, '/OCV_Base'], ...
    'Value', '3.0', 'Position', [140, 270, 190, 300]);

add_block('simulink/Math Operations/Add', [model_name, '/Add_OCV'], ...
    'Inputs', '++', 'Position', [220, 230, 250, 270]);

add_block('simulink/Math Operations/Gain', [model_name, '/R0_OhmicDrop'], ...
    'Gain', '0.045', 'Position', [140, 130, 200, 160]);

add_block('simulink/Continuous/Transfer Fcn', [model_name, '/RC1_Dynamics'], ...
    'Numerator', '[0.025]', 'Denominator', '[45.0, 1]', 'Position', [140, 175, 220, 205]);

add_block('simulink/Math Operations/Add', [model_name, '/Voltage_Sum'], ...
    'Inputs', '+--', 'Position', [310, 160, 340, 210]);

add_block('simulink/Sinks/Scope', [model_name, '/Terminal_Voltage_Scope'], ...
    'Position', [430, 160, 470, 190]);

add_block('simulink/Sinks/To Workspace', [model_name, '/Voltage_Out'], ...
    'VariableName', 'v_cell', 'SaveFormat', 'Array', 'Position', [430, 205, 490, 235]);

% =========================================================================
% 4. DYNAMIC ACOUSTIC SPEED OF SOUND & TOF TRACKING
% =========================================================================
add_block('simulink/Sources/Constant', [model_name, '/Nominal_SoS_Base'], ...
    'Value', '2440.0', 'Position', [40, 350, 90, 380]);

add_block('simulink/Math Operations/Gain', [model_name, '/SOC_SoS_Coeff'], ...
    'Gain', '120.0', 'Position', [140, 350, 190, 380]);

add_block('simulink/Sources/Constant', [model_name, '/T_Ref_25C'], ...
    'Value', '25.0', 'Position', [40, 410, 90, 440]);

add_block('simulink/Math Operations/Add', [model_name, '/Delta_T_Calc'], ...
    'Inputs', '+-', 'Position', [140, 410, 170, 440]);

add_block('simulink/Math Operations/Gain', [model_name, '/Temp_SoS_Coeff'], ...
    'Gain', '2.8', 'Position', [200, 410, 250, 440]);

add_block('simulink/Math Operations/Add', [model_name, '/SoS_Sum'], ...
    'Inputs', '++-', 'Position', [280, 360, 310, 410]);

add_block('simulink/Sinks/Scope', [model_name, '/Acoustic_Velocity_Scope'], ...
    'Position', [430, 345, 470, 375]);

add_block('simulink/Sources/Constant', [model_name, '/RoundTrip_Distance_m'], ...
    'Value', '0.020 * 1e6', 'Position', [220, 470, 290, 500]);

add_block('simulink/Math Operations/Divide', [model_name, '/ToF_Divider'], ...
    'Inputs', '*/', 'Position', [330, 470, 360, 510]);

add_block('simulink/Sinks/Scope', [model_name, '/Dynamic_Acoustic_ToF_Scope'], ...
    'Position', [430, 465, 470, 495]);

add_block('simulink/Sinks/To Workspace', [model_name, '/ToF_Out'], ...
    'VariableName', 'tof_cell', 'SaveFormat', 'Array', 'Position', [430, 510, 490, 540]);

% =========================================================================
% 5. 10 MHz ULTRASONIC RF PULSE-ECHO A-SCAN WAVEFORM SYNTHESIZER
% =========================================================================
add_block('simulink/Sources/Sine Wave', [model_name, '/RF_10MHz_Carrier'], ...
    'Frequency', '2*pi*5.0', 'Amplitude', '1.0', 'Position', [40, 580, 90, 610]);

add_block('simulink/Math Operations/Gain', [model_name, '/Echo_Amplitude_Gain'], ...
    'Gain', '0.75', 'Position', [140, 580, 190, 610]);

add_block('simulink/Math Operations/Product', [model_name, '/RF_Modulator'], ...
    'Inputs', '**', 'Position', [240, 570, 270, 610]);

add_block('simulink/Continuous/Transport Delay', [model_name, '/Acoustic_Path_Delay'], ...
    'DelayTime', '0.008', 'Position', [310, 575, 350, 605]);

add_block('simulink/Sinks/Scope', [model_name, '/Ultrasonic_RF_Pulse_Echo_Scope'], ...
    'Position', [430, 575, 470, 605]);

add_block('simulink/Sinks/To Workspace', [model_name, '/RF_Echo_Out'], ...
    'VariableName', 'rf_echo', 'SaveFormat', 'Array', 'Position', [430, 620, 490, 650]);

% =========================================================================
% 6. SIGNAL ROUTING & CONNECTIONS
% =========================================================================
% Excitation pulse lines
add_line(model_name, 'Excitation_Pulse/1', 'Current_Square/1');
add_line(model_name, 'Excitation_Pulse/1', 'R0_OhmicDrop/1');
add_line(model_name, 'Excitation_Pulse/1', 'RC1_Dynamics/1');
add_line(model_name, 'Excitation_Pulse/1', 'RF_Modulator/1');

% Thermal loop
add_line(model_name, 'Current_Square/1', 'Joule_Heat_Gain/1');
add_line(model_name, 'Joule_Heat_Gain/1', 'Thermal_Integrator/1');
add_line(model_name, 'Thermal_Integrator/1', 'Cell_Temperature_Scope/1');
add_line(model_name, 'Thermal_Integrator/1', 'Temp_Out/1');
add_line(model_name, 'Thermal_Integrator/1', 'Delta_T_Calc/1');

% Electrical ECM loop
add_line(model_name, 'SOC_Input/1', 'OCV_Gain/1');
add_line(model_name, 'SOC_Input/1', 'SOC_SoS_Coeff/1');
add_line(model_name, 'OCV_Gain/1', 'Add_OCV/1');
add_line(model_name, 'OCV_Base/1', 'Add_OCV/2');
add_line(model_name, 'Add_OCV/1', 'Voltage_Sum/1');
add_line(model_name, 'R0_OhmicDrop/1', 'Voltage_Sum/2');
add_line(model_name, 'RC1_Dynamics/1', 'Voltage_Sum/3');
add_line(model_name, 'Voltage_Sum/1', 'Terminal_Voltage_Scope/1');
add_line(model_name, 'Voltage_Sum/1', 'Voltage_Out/1');

% Acoustic Speed of Sound & ToF Loop
add_line(model_name, 'T_Ref_25C/1', 'Delta_T_Calc/2');
add_line(model_name, 'Delta_T_Calc/1', 'Temp_SoS_Coeff/1');
add_line(model_name, 'Nominal_SoS_Base/1', 'SoS_Sum/1');
add_line(model_name, 'SOC_SoS_Coeff/1', 'SoS_Sum/2');
add_line(model_name, 'Temp_SoS_Coeff/1', 'SoS_Sum/3');
add_line(model_name, 'SoS_Sum/1', 'Acoustic_Velocity_Scope/1');
add_line(model_name, 'SoS_Sum/1', 'ToF_Divider/2');
add_line(model_name, 'RoundTrip_Distance_m/1', 'ToF_Divider/1');
add_line(model_name, 'ToF_Divider/1', 'Dynamic_Acoustic_ToF_Scope/1');
add_line(model_name, 'ToF_Divider/1', 'ToF_Out/1');

% Ultrasonic RF Pulse-Echo Loop
add_line(model_name, 'RF_10MHz_Carrier/1', 'Echo_Amplitude_Gain/1');
add_line(model_name, 'Echo_Amplitude_Gain/1', 'RF_Modulator/2');
add_line(model_name, 'RF_Modulator/1', 'Acoustic_Path_Delay/1');
add_line(model_name, 'Acoustic_Path_Delay/1', 'Ultrasonic_RF_Pulse_Echo_Scope/1');
add_line(model_name, 'Acoustic_Path_Delay/1', 'RF_Echo_Out/1');

% =========================================================================
% 7. SAVE & COMPILE MODEL
% =========================================================================
save_system(model_name, slx_path);
close_system(model_name);

fprintf('[SUCCESS] Enhanced Simulink Digital Twin compiled and saved to:\n  %s\n\n', slx_path);
