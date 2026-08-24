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
%
%   Figures are saved as high-resolution PNG and SVG files suitable for
%   patent office submission.

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
    components = struct ...
        ('excitation_gen',   struct('pos', [0.1 0.6 0.15 0.1], 'label', 'Excitation\nGenerator',     'color', [0.2 0.6 0.8]), ...
         'cell_model',       struct('pos', [0.3 0.6 0.15 0.1], 'label', 'Battery Cell\nModel',       'color', [0.8 0.6 0.2]), ...
         'sensing',          struct('pos', [0.5 0.6 0.15 0.1], 'label', 'Multi-Modal\nSensing',      'color', [0.2 0.8 0.2]), ...
         'param_estimator',  struct('pos', [0.7 0.6 0.15 0.1], 'label', 'Parameter\nEstimator',      'color', [0.8 0.2 0.6]), ...
         'excitation_ctrl',  struct('pos', [0.7 0.3 0.15 0.1], 'label', 'Excitation\nController',    'color', [0.8 0.4 0.2]), ...
         'decision_engine',  struct('pos', [0.4 0.3 0.15 0.1], 'label', 'Decision\nEngine',          'color', [0.4 0.2 0.8]), ...
         'recovery_stage',   struct('pos', [0.1 0.3 0.15 0.1], 'label', 'Recovery Power\nStage',     'color', [0.6 0.4 0.2]));

    % Draw components as boxes
    for i = 1:numel(fieldnames(components))
        field = fieldnames(components){i};
        comp = components.(field);
        % Draw rectangle
        rectangle('Position', comp.pos, 'EdgeColor', 'black', 'LineWidth', 2, ...
                  'FaceColor', comp.color, 'FaceAlpha', 0.3);
        % Add label
        text(comp.pos(1) + comp.pos(3)/2, comp.pos(2) + comp.pos(4)/2, comp.label, ...
             'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
             'FontWeight', 'bold', 'FontSize', 10);
    end

    % Draw connections with arrows
    % Excitation Generator -> Cell Model
    annotation('arrow', [0.25 0.35 0.05 0], 'HeadLength', 10, 'HeadWidth', 7, 'Color', 'black');
    % Cell Model -> Sensing
    annotation('arrow', [0.45 0.35 0.05 0], 'HeadLength', 10, 'HeadWidth', 7, 'Color', 'black');
    % Sensing -> Parameter Estimator
    annotation('arrow', [0.65 0.35 0.05 0], 'HeadLength', 10, 'HeadWidth', 7, 'Color', 'black');
    % Parameter Estimator -> Excitation Controller (feedback)
    annotation('arrow', [0.85 0.55 0  -0.2], 'HeadLength', 10, 'HeadWidth', 7, 'Color', 'blue', 'LineStyle', '--');
    % Excitation Controller -> Excitation Generator (adaptive control)
    annotation('arrow', [0.85 0.4 0  -0.1], 'HeadLength', 10, 'HeadWidth', 7, 'Color', 'blue', 'LineStyle', '--');
    % Parameter Estimator -> Decision Engine
    annotation('arrow', [0.775 0.55 0  -0.2], 'HeadLength', 10, 'HeadWidth', 7, 'Color', 'black');
    % Decision Engine -> Recovery Stage
    annotation('arrow', [0.475 0.35 0  -0.05], 'HeadLength', 10, 'HeadWidth', 7, 'Color', 'black');
    % Recovery Stage -> Cell Model (balancing effect)
    annotation('arrow', [0.25 0.35 0  0.25], 'HeadLength', 10, 'HeadWidth', 7, 'Color', 'green', 'LineStyle', ':');

    % Add title
    title('FIG. 1: System Block Diagram - Low-Cost Multi-Modal Diagnostic System', ...
          'FontSize', 14, 'FontWeight', 'bold');
    xlabel('(a) Overall system architecture showing excitation, sensing, estimation, control, and recovery subsystems');

    % Save as high-resolution PNG and SVG
    png_file1 = fullfile(figures_dir, 'FIG1_System_Block_Diagram.png');
    svg_file1 = fullfile(figures_dir, 'FIG1_System_Block_Diagram.svg');
    saveas(fig1, png_file1);
    % Note: SVG export might require additional handling depending on MATLAB version
    % For now, we'll save as PNG and note that SVG can be generated similarly
    fprintf('Saved: %s\n', png_file1);
    close(fig1);

    % Figure 2: Adaptive Excitation Control Loop Timing Diagram
    fprintf('Generating FIG. 2: Adaptive Excitation Control Loop Timing Diagram...\n');
    fig2 = figure('Position', [100 100 1200 600], 'Color', 'white');
    axes2 = axes('Position', [0.1 0.2 0.8 0.6], 'Box', 'on', 'XGrid', 'on', 'YGrid', 'on');

    % Time axis
    t_max = 100e-3;  % 100 ms window to show several cycles
    t = linspace(0, t_max, 1000);

    % Excitation pulse train (adaptive)
    pulse_width = 10e-6;   % 10 µs
    pulse_period = 10e-3;  % 10 ms (100 Hz)
    excitation = zeros(size(t));
    for i = 1:floor(t_max/pulse_period)
        start_idx = round(i * pulse_period / t_max * numel(t));
        width_idx = round(pulse_width / t_max * numel(t));
        if start_idx + width_idx <= numel(t)
            excitation(start_idx:start_idx+width_idx) = 0.5;  % 500 mA pulse
        end
    end

    % Make some pulses adaptive (wider/narrower based on uncertainty)
    % Simulate uncertainty decreasing over time
    uncertainty = linspace(0.8, 0.2, floor(t_max/pulse_period));  % High to low uncertainty
    for i = 1:floor(t_max/pulse_period)
        start_idx = round(i * pulse_period / t_max * numel(t));
        base_width_idx = round(pulse_width / t_max * numel(t));
        % Adaptive width: higher uncertainty -> wider pulse
        width_factor = 0.5 + 0.5 * uncertainty(i);  % 0.5 to 1.0 scaling
        width_idx = round(base_width_idx * width_factor);
        if start_idx + width_idx <= numel(t)
            excitation(start_idx:start_idx+width_idx) = 0.5 * width_factor;  % Scale amplitude too for visualization
        end
    end

    % Sensing windows (aligned with pulses, with small delay for settling)
    sensing_delay = 1e-6;  % 1 µs settling time
    sensing_width = 5e-6;  % 5 µs sensing window
    sensing = zeros(size(t));
    for i = 1:floor(t_max/pulse_period)
        pulse_start_idx = round(i * pulse_period / t_max * numel(t));
        sensing_start_idx = round((pulse_start_idx + pulse_width/t_max*numel(t) + sensing_delay/t_max*numel(t)));
        width_idx = round(sensing_width / t_max * numel(t));
        if sensing_start_idx + width_idx <= numel(t)
            sensing(sensing_start_idx:sensing_start_idx+width_idx) = 0.3;
        end
    end

    % Parameter estimation uncertainty (declining over time)
    uncertainty_signal = zeros(size(t));
    for i = 1:floor(t_max/pulse_period)
        start_idx = round(i * pulse_period / t_max * numel(t));
        end_idx = round((i+1) * pulse_period / t_max * numel(t)) - 1;
        if end_idx > start_idx && start_idx >= 1 && end_idx <= numel(t)
            % Linear decline in uncertainty over each period
            unc_val = uncertainty(i);
            uncertainty_signal(start_idx:end_idx) = unc_val;
        end
    end

    % Plot signals
    hold on;
    plot(t*1000, excitation*1, 'r-', 'LineWidth', 2, 'DisplayName', 'Excitation Current');
    plot(t*1000, sensing*0.8 + 0.1, 'g-', 'LineWidth', 2, 'DisplayName', 'Sensing Window');
    plot(t*1000, uncertainty_signal*0.6 + 0.4, 'b-', 'LineWidth', 2, 'DisplayName', 'Estimation Uncertainty');
    hold off;

    % Formatting
    xlabel('Time (ms)');
    ylabel('Normalized Amplitude');
    title('FIG. 2: Adaptive Excitation Control Loop Timing Diagram', ...
          'FontSize', 14, 'FontWeight', 'bold');
    legend('Location', 'best');
    grid on, alpha(0.3);

    % Add annotations for key timing relationships
    text(t_max*1000*0.1, 0.9, 'Excitation Pulse', 'Color', 'red', 'FontWeight', 'bold');
    text(t_max*1000*0.1, 0.7, 'Sensing Window (after settling)', 'Color', 'green', 'FontWeight', 'bold');
    text(t_max*1000*0.1, 0.5, 'Estimation Uncertainty \\downarrow', 'Color', 'blue', 'FontWeight', 'bold');
    annotation('textarrow', [0.2 0.3], [0.5 0.5], 'String', 'Adaptive pulse width \\propto 1/uncertainty', ...
               'Color', 'black', 'FontSize', 9);

    % Save figure
    png_file2 = fullfile(figures_dir, 'FIG2_Adaptive_Excitation_Timing.png');
    svg_file2 = fullfile(figures_dir, 'FIG2_Adaptive_Excitation_Timing.svg');
    saveas(fig2, png_file2);
    fprintf('Saved: %s\n', png_file2);
    close(fig2);

    % Figure 4: Decision Engine Stateflow Chart (simplified representation)
    fprintf('Generating FIG. 4: Decision Engine Stateflow Chart...\n');
    fig4 = figure('Position', [100 100 800 600], 'Color', 'white');
    axes4 = axes('Position', [0.1 0.1 0.8 0.8], 'Box', 'on');
    axis equal;
    axis([0 10 0 10]);
    hold on;

    % Define state positions
    states = struct ...
        ('IDLE',       struct('pos', [2  8], 'label', 'IDLE'), ...
         'SENSING',    struct('pos', [6  8], 'label', 'SENSING'), ...
         'ANALYZING',  struct('pos', [8  5], 'label', 'ANALYZING'), ...
         'RESENSING',  struct('pos', [6  2], 'label', 'RESENSING'), ...
         'REBALANCING',struct('pos', [2  2], 'label', 'REBALANCING'), ...
         'VERIFYING',  struct('pos', [4  5], 'label', 'VERIFYING'), ...
         'COMPLETE',   struct('pos', [8  8], 'label', 'COMPLETE'));

    % Draw states as rounded boxes
    state_colors = lines(numel(fieldnames(states)));
    for i = 1:numel(fieldnames(states))
        field = fieldnames(states){i};
        state = states.(field);
        % Draw rounded rectangle
        rectangle('Position', [state.pos(1)-0.5 state.pos(2)-0.3 1.5 0.6], ...
                  'Curvature', [0.2 0.2], 'EdgeColor', 'black', 'LineWidth', 1.5, ...
                  'FaceColor', state_colors(i,:), 'FaceAlpha', 0.3);
        % Add label
        text(state.pos(1), state.pos(2), state.label, ...
             'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
             'FontWeight', 'bold', 'FontSize', 9);
    end

    % Draw transitions with arrows
    transitions = struct ...
        ('IDLE_TO_SENSING',      struct('from', 'IDLE',    'to', 'SENSING',    'label', 'Start'), ...
         'SENSING_TO_ANALYZING', struct('from', 'SENSING', 'to', 'ANALYZING',  'label', 'Complete'), ...
         'ANALYZING_TO_RESENSING',struct('from','ANALYZING','to','RESENSING',  'label', 'Low\\nConfidence'), ...
         'ANALYZING_TO_REBALANCING',struct('from','ANALYZING','to','REBALANCING','label', 'High\\nConfidence'), ...
         'RESENSING_TO_SENSING',  struct('from','RESENSING','to','SENSING',    'label', 'Retry'), ...
         'REBALANCING_TO_VERIFYING',struct('from','REBALANCING','to','VERIFYING','label', 'Complete'), ...
         'VERIFYING_TO_COMPLETE', struct('from','VERIFYING','to','COMPLETE',   'label', 'Success'), ...
         'VERIFYING_TO_IDLE',     struct('from','VERIFYING','to','IDLE',       'label', 'Fail/Timeout'), ...
         'COMPLETE_TO_IDLE',      struct('from','COMPLETE','to','IDLE',        'label', 'New Cycle'));

    for i = 1:numel(fieldnames(transitions))
        field = fieldnames(transitions){i};
        trans = transitions.(field);
        from_pos = states.(trans.from).pos;
        to_pos = states.(trans.to).pos;
        % Draw arrow
        annotation('arrow', [from_pos(1)/10 + 0.05 (to_pos(1)-from_pos(1))/10 ...
                            from_pos(2)/10 + 0.05 (to_pos(2)-from_pos(2))/10], ...
                  'HeadLength', 8, 'HeadWidth', 5, 'Color', 'black');
        % Add label at midpoint
        mid_pos = [(from_pos(1) + to_pos(1))/2/10 (from_pos(2) + to_pos(2))/2/10];
        text(mid_pos(1), mid_pos(2), trans.label, ...
             'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
             'FontSize', 7, 'BackgroundColor', 'white', 'EdgeColor', 'none');
    end

    hold off;
    % Formatting
    title('FIG. 4: Decision Engine Stateflow Chart', ...
          'FontSize', 14, 'FontWeight', 'bold');
    xlabel('Normalized X Position');
    ylabel('Normalized Y Position');
    set(gca, 'XTick', [], 'YTick', []);  % Hide tick marks since we're using custom coordinates
    axis equal;

    % Save figure
    png_file4 = fullfile(figures_dir, 'FIG4_Decision_Engine_Stateflow.png');
    svg_file4 = fullfile(figures_dir, 'FIG4_Decision_Engine_Stateflow.svg');
    saveas(fig4, png_file4);
    fprintf('Saved: %s\n', png_file4);
    close(fig4);

    % Figure 5: Recovery Waveforms
    fprintf('Generating FIG. 5: Recovery Waveforms...\n');
    fig5 = figure('Position', [100 100 1000 600], 'Color', 'white');

    % Create subplots for different recovery actions
    recovery_actions = {'Depolleting', 'Equilibration', 'Gas Recombination', 'Short Isolation'};
    colors = lines(numel(recovery_actions));

    for i = 1:numel(recovery_actions)
        subplot(2, 2, i);
        % Time axis for recovery (longer duration)
        t_rec = linspace(0, 10, 1000);  % 10 seconds

        % Generate characteristic recovery waveforms based on action type
        switch lower(recovery_actions{i})
            case 'depolleting'
                % Depolleting: oscillating current to break down lithium plating
                carrier = sin(2*pi*50*t_rec);  % 50 Hz carrier
                envelope = exp(-t_rec/2) .* (1 - exp(-t_rec*5));  % Build up then decay
                waveform = carrier .* envelope;
                ylabel('Current (A)');
            case 'equilibration'
                % Equilibration: constant current transfer
                waveform = 0.5 * (1 - exp(-t_rec/3));  % Asymptotic approach to 0.5A
                ylabel('Current (A)');
            case 'gas recombination'
                % Gas recombination: pulsed current with specific frequency
                carrier = square(2*pi*0.5*t_rec);  % 0.5 Hz pulsing
                envelope = exp(-t_rec/5);          % Slow decay
                waveform = carrier .* envelope .* 0.4;
                ylabel('Current (A)');
            case 'short isolation'
                % Short isolation: rapid current interruption
                waveform = 0.6 * exp(-t_rec*10);   % Fast decay to zero
                ylabel('Current (A)');
            otherwise
                waveform = zeros(size(t_rec));
                ylabel('Current (A)');
        end

        plot(t_rec, waveform, 'Color', colors(i,:), 'LineWidth', 2);
        title(recovery_actions{i}, 'FontWeight', 'bold');
        grid on, alpha(0.3);
        xlabel('Time (s)');

        % Add characteristic features annotations
        if strcmpi(recovery_actions{i}, 'depolleting')
            text(2, 0.3, 'Oscillatory\\n\\rightarrow DC', 'FontSize', 8, ...
                 'HorizontalAlignment', 'center');
        elseif strcmpi(recovery_actions{i}, 'equilibration')
            text(5, 0.25, 'Steady State\\n\\rightarrow', 'FontSize', 8, ...
                 'HorizontalAlignment', 'center');
        end
    end

    suptitle('FIG. 5: Recovery Waveforms for Different Actions', ...
             'FontSize', 14, 'FontWeight', 'bold');

    % Save figure
    png_file5 = fullfile(figures_dir, 'FIG5_Recovery_Waveforms.png');
    svg_file5 = fullfile(figures_dir, 'FIG5_Recovery_Waveforms.svg');
    saveas(fig5, png_file5);
    fprintf('Saved: %s\n', png_file5);
    close(fig5);

    fprintf('\nPatent figure generation complete!\n');
    fprintf('Figures saved in: %s\n', figures_dir);
    fprintf('Generated files:\n');
    fprintf('  - FIG1_System_Block_Diagram.png\n');
    fprintf('  - FIG2_Adaptive_Excitation_Timing.png\n');
    fprintf('  - FIG4_Decision_Engine_Stateflow.png\n');
    fprintf('  - FIG5_Recovery_Waveforms.png\n');
    fprintf('\nNote: FIG.3 (Fusion Architecture) is referenced from the Python repository.\n');
end