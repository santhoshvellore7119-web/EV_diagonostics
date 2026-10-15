% =========================================================================
% SIMULATE 8S MODULAR PACK ACTIVE ZVS BALANCING VS PASSIVE IN MATLAB
% =========================================================================
% Comprehensive multi-cell pack digital twin:
% Compares:
% 1. Unbalanced baseline
% 2. Passive bleed resistor balancing (100 mA resistive dissipation)
% 3. Proposed ZVS Quasi-Resonant Flyback Active Balancer (2.0 A shuttling, 92.8% eff)

function results = simulate_8s_active_pack_complete()
    fprintf('===================================================================\n');
    fprintf(' [MATLAB DIGITAL TWIN] 8S Modular Pack Active Balancing Simulation\n');
    fprintf('===================================================================\n');

    num_cells = 8;
    time_s = 0:1:3600; % 1 hour discharge simulation
    N = length(time_s);

    % Cell initial conditions: Cell 4 is aged/weak
    soh_init = [98.5, 97.8, 98.2, 79.5, 99.0, 97.6, 98.4, 98.0];
    soc_init = [72.0, 71.0, 73.0, 56.0, 74.0, 71.5, 72.5, 71.8];
    cap_nominal = 5.0; % Ah

    % Topologies: 1 = Unbalanced, 2 = Passive Bleed, 3 = Active ZVS
    topologies = {'Unbalanced Baseline', 'Passive Bleed (100 mA)', 'Active ZVS Flyback (2.0 A)'};
    results = struct();

    fig = figure('Name', '8S Pack Active Balancing Comparison', 'Position', [80 80 1300 800], 'Visible', 'off');

    colors = lines(num_cells);

    for top_idx = 1:3
        soc = repmat(soc_init, N, 1);
        v_cell = zeros(N, num_cells);
        t_cell = repmat(26.0, N, num_cells);
        pack_active = true(1, N);

        i_load = 3.2; % 3.2 A constant pack discharge
        cutoff_time = N;

        for k = 1:N-1
            dt = 1.0;
            if ~pack_active(k)
                soc(k+1, :) = soc(k, :);
                v_cell(k+1, :) = v_cell(k, :);
                t_cell(k+1, :) = t_cell(k, :);
                continue;
            end

            % Compute cell internal resistance R0 from SOH
            r0 = 0.026 + (100 - soh_init) * 0.00045; % Ohms

            % Determine balancing currents
            i_bal = zeros(1, num_cells);
            p_bal_loss = 0.0;

            if top_idx == 2 % Passive bleed
                v_mean = mean(v_cell(k, :));
                for c = 1:num_cells
                    if v_cell(k, c) > (min(v_cell(k, :)) + 0.05)
                        i_bal(c) = 0.10; % 100 mA resistive bleed
                        p_bal_loss = p_bal_loss + i_bal(c) * v_cell(k, c);
                    end
                end
            elseif top_idx == 3 % Proposed Active ZVS
                [min_soc, weak_c] = min(soc(k, :));
                [max_soc, strong_c] = max(soc(k, :));
                if (max_soc - min_soc) > 2.0
                    i_shuttle = 2.0; % 2.0 A shuttling
                    eta = 0.928;     % 92.8% soft-switching efficiency
                    i_bal(weak_c) = -i_shuttle * eta; % Receiving
                    donors = find(soc(k, :) > (min_soc + 3.0));
                    if ~isempty(donors)
                        i_bal(donors) = i_shuttle / length(donors);
                    end
                end
            end

            % Update SOC and Voltages
            for c = 1:num_cells
                i_cell_net = i_load + i_bal(c);
                dsoc = -(i_cell_net * dt / (3600 * cap_nominal * (soh_init(c)/100))) * 100;
                soc(k+1, c) = max(0, min(100, soc(k, c) + dsoc));

                % OCV-R model
                ocv = 3.45 + 0.70 * (soc(k+1, c) / 100);
                v_cell(k+1, c) = ocv - i_cell_net * r0(c);

                % Thermal update (Joule heat + cooling + balancing dissipation)
                p_joule = (i_cell_net^2) * r0(c);
                if top_idx == 2 && i_bal(c) > 0
                    p_joule = p_joule + i_bal(c) * v_cell(k+1, c); % Bleed resistor heat
                end
                dt_temp = (p_joule * 0.12 - 0.015 * (t_cell(k, c) - 25.0)) * dt;
                t_cell(k+1, c) = t_cell(k, c) + dt_temp;
            end

            % Check pack voltage cutoff (if any cell hits 3.0 V)
            if any(v_cell(k+1, :) < 3.00)
                pack_active(k+1:end) = false;
                cutoff_time = k;
                break;
            end
        end

        usable_time_min = cutoff_time / 60.0;
        usable_energy_wh = sum(mean(v_cell(1:cutoff_time, :), 2) * i_load * (1/3600));

        results.(sprintf('top_%d', top_idx)).name = topologies{top_idx};
        results.(sprintf('top_%d', top_idx)).cutoff_time_min = usable_time_min;
        results.(sprintf('top_%d', top_idx)).usable_energy_wh = usable_energy_wh;
        results.(sprintf('top_%d', top_idx)).max_temp_c = max(max(t_cell));

        % Subplot 1: Cell Voltages
        subplot(2, 2, 1);
        hold on; grid on; box on;
        plot(time_s(1:cutoff_time)/60, v_cell(1:cutoff_time, 4), 'LineWidth', 2.0);
        title('Weakest Cell (Cell #4) Voltage Profile', 'FontSize', 11, 'FontWeight', 'bold');
        xlabel('Time (min)'); ylabel('Cell Voltage (V)');
        yline(3.0, '--r', '3.0V Cutoff');

        % Subplot 2: Cell SOC Spread over Time
        subplot(2, 2, 2);
        hold on; grid on; box on;
        soc_spread = max(soc(1:cutoff_time, :), [], 2) - min(soc(1:cutoff_time, :), [], 2);
        plot(time_s(1:cutoff_time)/60, soc_spread, 'LineWidth', 2.0);
        title('Pack SOC Inbalance (\DeltaSOC = Max - Min)', 'FontSize', 11, 'FontWeight', 'bold');
        xlabel('Time (min)'); ylabel('\DeltaSOC (%)');

        % Subplot 3: Maximum Pack Temperature
        subplot(2, 2, 3);
        hold on; grid on; box on;
        plot(time_s(1:cutoff_time)/60, max(t_cell(1:cutoff_time, :), [], 2), 'LineWidth', 2.0);
        title('Peak Pack Temperature T_{max} (°C)', 'FontSize', 11, 'FontWeight', 'bold');
        xlabel('Time (min)'); ylabel('T_{max} (°C)');
    end

    subplot(2, 2, 1); legend(topologies, 'Location', 'southwest', 'FontSize', 8);
    subplot(2, 2, 2); legend(topologies, 'Location', 'northeast', 'FontSize', 8);
    subplot(2, 2, 3); legend(topologies, 'Location', 'northwest', 'FontSize', 8);

    % Subplot 4: Usable Capacity Gain Comparison
    subplot(2, 2, 4);
    bar_data = [results.top_1.usable_energy_wh, results.top_2.usable_energy_wh, results.top_3.usable_energy_wh];
    b = bar(categorical(topologies), bar_data, 'FaceColor', [0.15 0.55 0.85]);
    grid on; box on;
    title('Usable Energy Delivered Before Cutoff (Wh)', 'FontSize', 11, 'FontWeight', 'bold');
    ylabel('Pack Usable Energy (Wh)');
    for i = 1:3
        text(i, bar_data(i) * 0.5, sprintf('%.1f Wh', bar_data(i)), ...
             'HorizontalAlignment', 'center', 'Color', 'white', 'FontWeight', 'bold');
    end

    gain_pct = ((results.top_3.usable_energy_wh - results.top_1.usable_energy_wh) / results.top_1.usable_energy_wh) * 100;
    fprintf('[RESULT] Proposed ZVS Balancer Usable Energy Gain: +%.2f%%\n', gain_pct);

    % Save figure
    out_dir = fullfile(fileparts(mfilename('fullpath')), 'figures');
    if ~exist(out_dir, 'dir'), mkdir(out_dir); end
    fig_path = fullfile(out_dir, 'FIG7_8S_Pack_Active_Balancing_Comparison.png');
    saveas(fig, fig_path);
    close(fig);

    fprintf('[SUCCESS] 8S Modular Pack Active Balancing simulation completed.\n');
    fprintf('[SAVED] Figure generated: %s\n', fig_path);
end
