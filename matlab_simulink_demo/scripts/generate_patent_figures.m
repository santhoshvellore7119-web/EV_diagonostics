% GENERATE_PATENT_FIGURES Create publication-quality figures for patent drawings
%
%   GENERATE_PATENT_FIGURES() generates the figures referenced in the patent
%   application for the Low-Cost Multi-Modal Diagnostic System.
%   These include:
%   FIG. 1: System block diagram
%   FIG. 2: Adaptive excitation control loop timing diagram
%   FIG. 3: Multi-modal fusion architecture (reference - see Python repo)
%   FIG. 4: Decision engine stateflow chart
%   FIG. 5: Recovery waveforms

clear; close all; clc;

fprintf('Generating patent figures for EV Battery Diagnostic System...\n\n');

% Create figures directory if it doesn't exist
figures_dir = fullfile(pwd, 'figures');
if ~exist(figures_dir, 'dir')
    mkdir(figures_dir);
    fprintf('Created figures directory: %s\n', figures_dir);
end

% Figure 1: System Block Diagram
fprintf('Generating FIG. 1: System Block Diagram...\n');
fig1 = figure('Position', [100 100 1000 800], 'Color', 'white');
axes1 = axes('Position', [0.1 0.1 0.8 0.8], 'Box', 'on');

% Define system components and their positions
components = struct();
components.excitation_gen  = struct('pos', [0.1 0.6 0.15 0.1], 'label', sprintf('Excitation\nGenerator'),     'color', [0.2 0.6 0.8]);
components.cell_model      = struct('pos', [0.3 0.6 0.15 0.1], 'label', sprintf('Battery Cell\nModel'),       'color', [0.8 0.6 0.2]);
components.sensing         = struct('pos', [0.5 0.6 0.15 0.1], 'label', sprintf('Multi-Modal\nSensing'),      'color', [0.2 0.8 0.2]);
components.param_estimator = struct('pos', [0.7 0.6 0.15 0.1], 'label', sprintf('Parameter\nEstimator'),      'color', [0.8 0.2 0.6]);
components.excitation_ctrl = struct('pos', [0.7 0.3 0.15 0.1], 'label', sprintf('Excitation\nController'),    'color', [0.8 0.4 0.2]);
components.decision_engine = struct('pos', [0.4 0.3 0.15 0.1], 'label', sprintf('Decision\nEngine'),          'color', [0.4 0.2 0.8]);
components.recovery_stage  = struct('pos', [0.1 0.3 0.15 0.1], 'label', sprintf('Recovery Power\nStage'),     'color', [0.6 0.4 0.2]);

% Draw components as boxes
comp_names = fieldnames(components);
for i = 1:numel(comp_names)
    comp = components.(comp_names{i});
    rectangle('Position', comp.pos, 'EdgeColor', 'black', 'LineWidth', 2, ...
              'FaceColor', comp.color);
    text(comp.pos(1) + comp.pos(3)/2, comp.pos(2) + comp.pos(4)/2, comp.label, ...
         'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
         'FontWeight', 'bold', 'FontSize', 10);
end

% Draw connections with arrows
annotation('arrow', [0.25 0.30], [0.65 0.65], 'HeadLength', 8, 'HeadWidth', 6, 'Color', 'black');
annotation('arrow', [0.45 0.50], [0.65 0.65], 'HeadLength', 8, 'HeadWidth', 6, 'Color', 'black');
annotation('arrow', [0.65 0.70], [0.65 0.65], 'HeadLength', 8, 'HeadWidth', 6, 'Color', 'black');
annotation('arrow', [0.775 0.775], [0.60 0.40], 'HeadLength', 8, 'HeadWidth', 6, 'Color', 'blue', 'LineStyle', '--');
annotation('arrow', [0.70 0.25], [0.35 0.35], 'HeadLength', 8, 'HeadWidth', 6, 'Color', 'blue', 'LineStyle', '--');
annotation('arrow', [0.70 0.55], [0.60 0.35], 'HeadLength', 8, 'HeadWidth', 6, 'Color', 'black');
annotation('arrow', [0.40 0.25], [0.35 0.35], 'HeadLength', 8, 'HeadWidth', 6, 'Color', 'black');
annotation('arrow', [0.175 0.30], [0.40 0.60], 'HeadLength', 8, 'HeadWidth', 6, 'Color', [0 0.6 0], 'LineStyle', ':');

title('FIG. 1: System Block Diagram - Low-Cost Multi-Modal Diagnostic System', ...
      'FontSize', 14, 'FontWeight', 'bold');
xlabel('(a) Overall system architecture showing excitation, sensing, estimation, control, and recovery subsystems');

png_file1 = fullfile(figures_dir, 'FIG1_System_Block_Diagram.png');
saveas(fig1, png_file1);
fprintf('Saved: %s\n', png_file1);
close(fig1);

% Figure 2: Adaptive Excitation Control Loop Timing Diagram
fprintf('Generating FIG. 2: Adaptive Excitation Control Loop Timing Diagram...\n');
fig2 = figure('Position', [100 100 1200 600], 'Color', 'white');
axes2 = axes('Position', [0.1 0.2 0.8 0.6], 'Box', 'on', 'XGrid', 'on', 'YGrid', 'on');

t_max = 100e-3;
t = linspace(0, t_max, 1000);
pulse_width = 10e-6;
pulse_period = 10e-3;
excitation = zeros(size(t));

uncertainty = linspace(0.8, 0.2, floor(t_max/pulse_period));
for i = 1:floor(t_max/pulse_period)
    start_idx = round(i * pulse_period / t_max * numel(t));
    base_width_idx = round(pulse_width / t_max * numel(t));
    width_factor = 0.5 + 0.5 * uncertainty(i);
    width_idx = round(base_width_idx * width_factor);
    if start_idx + width_idx <= numel(t)
        excitation(start_idx:start_idx+width_idx) = 0.5 * width_factor;
    end
end

plot(t*1000, excitation, 'b-', 'LineWidth', 2);
xlabel('Time (ms)');
ylabel('Excitation Current (A)');
title('FIG. 2: Adaptive Excitation Control Loop Timing Diagram', 'FontSize', 14, 'FontWeight', 'bold');
grid on;

png_file2 = fullfile(figures_dir, 'FIG2_Adaptive_Excitation_Timing.png');
saveas(fig2, png_file2);
fprintf('Saved: %s\n', png_file2);
close(fig2);

% Figure 4: Decision Engine Stateflow Diagram
fprintf('Generating FIG. 4: Decision Engine Stateflow...\n');
fig4 = figure('Position', [100 100 1000 700], 'Color', 'white');
axes4 = axes('Position', [0.1 0.1 0.8 0.8], 'Box', 'on');

states = struct();
states.idle        = struct('pos', [0.4 0.8 0.2 0.1], 'label', 'IDLE / SENSING',          'color', [0.8 0.8 0.8]);
states.diagnosing  = struct('pos', [0.4 0.6 0.2 0.1], 'label', 'DIAGNOSING',              'color', [0.9 0.9 0.6]);
states.evaluating  = struct('pos', [0.4 0.4 0.2 0.1], 'label', 'EVALUATING SOH',          'color', [0.7 0.9 0.7]);
states.rebalancing = struct('pos', [0.1 0.2 0.25 0.1], 'label', 'ACTIVE REBALANCING',      'color', [0.6 0.8 1.0]);
states.resensing   = struct('pos', [0.4 0.2 0.2 0.1], 'label', 'RE-SENSING (ACE-OPI)',    'color', [1.0 0.8 0.6]);
states.alarm       = struct('pos', [0.7 0.2 0.2 0.1], 'label', 'ALARM / ISOLATION',       'color', [1.0 0.6 0.6]);

st_names = fieldnames(states);
for i = 1:numel(st_names)
    st = states.(st_names{i});
    rectangle('Position', st.pos, 'EdgeColor', 'black', 'LineWidth', 2, 'FaceColor', st.color);
    text(st.pos(1) + st.pos(3)/2, st.pos(2) + st.pos(4)/2, st.label, ...
         'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', 'FontWeight', 'bold', 'FontSize', 9);
end

title('FIG. 4: Decision Engine Stateflow Diagram', 'FontSize', 14, 'FontWeight', 'bold');
png_file4 = fullfile(figures_dir, 'FIG4_Decision_Engine_Stateflow.png');
saveas(fig4, png_file4);
fprintf('Saved: %s\n', png_file4);
close(fig4);

% Figure 5: Recovery Waveforms
fprintf('Generating FIG. 5: Recovery Waveforms...\n');
fig5 = figure('Position', [100 100 1000 600], 'Color', 'white');

recovery_actions = {'Depolleting', 'Equilibration', 'Gas Recombination', 'Short Isolation'};
colors = lines(numel(recovery_actions));

for i = 1:numel(recovery_actions)
    subplot(2, 2, i);
    t_rec = linspace(0, 10, 1000);
    switch lower(recovery_actions{i})
        case 'depolleting'
            carrier = sin(2*pi*50*t_rec);
            envelope = exp(-t_rec/2) .* (1 - exp(-t_rec*5));
            waveform = carrier .* envelope;
        case 'equilibration'
            waveform = 0.5 * (1 - exp(-t_rec/3));
        case 'gas recombination'
            carrier = sign(sin(2*pi*0.5*t_rec));
            envelope = exp(-t_rec/5);
            waveform = carrier .* envelope .* 0.4;
        case 'short isolation'
            waveform = 0.6 * exp(-t_rec*10);
        otherwise
            waveform = zeros(size(t_rec));
    end

    plot(t_rec, waveform, 'Color', colors(i,:), 'LineWidth', 2);
    title(recovery_actions{i}, 'FontWeight', 'bold');
    grid on;
    xlabel('Time (s)');
    ylabel('Current (A)');
end

png_file5 = fullfile(figures_dir, 'FIG5_Recovery_Waveforms.png');
saveas(fig5, png_file5);
fprintf('Saved: %s\n', png_file5);
close(fig5);

fprintf('\nPatent figure generation complete!\n');
fprintf('Figures saved in: %s\n', figures_dir);