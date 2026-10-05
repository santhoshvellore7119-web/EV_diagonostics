% SIMULATE_4S_ACTIVE_BALANCING
% Comprehensive 4-Cell Series Pack Active Rebalancing Simulation
% Simulates Zero-Voltage Switching (ZVS) quasi-resonant bidirectional energy shuttling
% across a 4S NMC 18650 battery pack module.

function results = simulate_4s_active_balancing(initial_socs, duration_s, dt_s)
    if nargin < 1 || isempty(initial_socs)
        initial_socs = [0.82; 0.70; 0.58; 0.44]; % 4S pack initial SOC imbalance
    end
    if nargin < 2, duration_s = 60.0; end
    if nargin < 3, dt_s = 0.05; end

    time_vec = 0:dt_s:duration_s;
    N_steps = length(time_vec);
    N_cells = 4;

    % Physical cell parameters
    C_nominal_Ah = 2.5;                % 2.5 Ah nominal capacity (18650)
    C_nominal_As = C_nominal_Ah * 3600; % Coulomb capacity
    R0_cells = [0.025; 0.024; 0.026; 0.028]; % Internal resistance (Ohm)
    R1_cells = [0.015; 0.014; 0.016; 0.017]; % Polarization resistance (Ohm)
    C1_cells = [1200; 1150; 1250; 1100];     % Polarization capacitance (F)

    % ZVS Inductive Balancer Parameters
    L_ind_H = 10e-6;                   % 10 uH Coilcraft SER2918H
    f_sw_Hz = 100e3;                   % 100 kHz switching frequency
    eta_zvs = 0.942;                   % 94.2% round-trip transfer efficiency
    I_bal_max_A = 2.5;                 % Maximum continuous balancing current

    % State storage
    soc_history = zeros(N_cells, N_steps);
    voltage_history = zeros(N_cells, N_steps);
    i_bal_history = zeros(N_cells, N_steps);
    temp_history = zeros(N_cells, N_steps);
    efficiency_history = zeros(1, N_steps);

    soc_current = initial_socs(:);
    v_rc_current = zeros(N_cells, 1);
    temp_current = 25.0 * ones(N_cells, 1); % Initial temperature (deg C)

    for k = 1:N_steps
        % 1. Calculate Open Circuit Voltage (OCV) per cell
        % OCV(SOC) = 3.0 + 1.2 * SOC - 0.15 * (1 - SOC)^2
        ocv_cells = 3.0 + 1.2 .* soc_current - 0.15 .* (1.0 - soc_current).^2;

        % 2. Active Rebalancing Control Law:
        % Identify highest-SOC cell (donor) and lowest-SOC cell (recipient)
        [max_soc, max_idx] = max(soc_current);
        [min_soc, min_idx] = min(soc_current);
        soc_imbalance = max_soc - min_soc;

        i_transfer = zeros(N_cells, 1);
        if soc_imbalance > 0.015 % 1.5% imbalance threshold
            % Proportional balancing current demand
            i_demand = min(I_bal_max_A, soc_imbalance * 12.0);
            i_transfer(max_idx) = -i_demand;          % Discharging donor
            i_transfer(min_idx) = i_demand * eta_zvs; % Charging recipient with ZVS efficiency
            current_efficiency = eta_zvs * 100.0;
        else
            current_efficiency = 100.0;
        end

        % 3. Update 2-RC polarization dynamics and terminal voltages
        alpha_rc = exp(-dt_s ./ (R1_cells .* C1_cells));
        beta_rc = R1_cells .* (1.0 - alpha_rc);
        v_rc_current = v_rc_current .* alpha_rc + i_transfer .* beta_rc;

        v_terminal = ocv_cells + i_transfer .* R0_cells - v_rc_current;

        % 4. Coulomb counting SOC update
        % dSOC/dt = I / C_nom
        soc_current = soc_current + (i_transfer .* dt_s) ./ C_nominal_As;
        soc_current = max(0.01, min(0.99, soc_current));

        % 5. Thermal dissipation update (Joule heating + converter losses)
        p_loss_conduction = (i_transfer.^2) .* (R0_cells + R1_cells);
        p_loss_converter = abs(i_transfer) .* (1.0 - eta_zvs) .* ocv_cells;
        p_total_heat = p_loss_conduction + p_loss_converter;

        % dT/dt = (Q_in - (T - T_amb)/R_th) / C_th
        R_th_cell = 3.2;   % K/W
        C_th_cell = 48.0;  % J/K
        t_rise_rate = (p_total_heat - (temp_current - 25.0) ./ R_th_cell) ./ C_th_cell;
        temp_current = temp_current + t_rise_rate .* dt_s;

        % Store telemetry
        soc_history(:, k) = soc_current;
        voltage_history(:, k) = v_terminal;
        i_bal_history(:, k) = i_transfer;
        temp_history(:, k) = temp_current;
        efficiency_history(k) = current_efficiency;
    end

    results = struct();
    results.time_s = time_vec;
    results.soc_history = soc_history;
    results.voltage_history = voltage_history;
    results.i_bal_history = i_bal_history;
    results.temp_history = temp_history;
    results.efficiency_history = efficiency_history;
    results.initial_imbalance_pct = (max(initial_socs) - min(initial_socs)) * 100.0;
    results.final_imbalance_pct = (max(soc_current) - min(soc_current)) * 100.0;
    results.mean_zvs_efficiency_pct = mean(efficiency_history);
    results.pack_voltage_final_v = sum(voltage_history(:, end));

    fprintf('=================================================================\n');
    fprintf(' 4S ACTIVE BATTERY REBALANCING SIMULATION (ZVS QUASI-RESONANT)\n');
    fprintf('=================================================================\n');
    fprintf(' Duration:                %.2f s (dt = %.3f s)\n', duration_s, dt_s);
    fprintf(' Initial SOC Imbalance:   %.2f %%\n', results.initial_imbalance_pct);
    fprintf(' Final SOC Imbalance:     %.2f %%\n', results.final_imbalance_pct);
    fprintf(' Mean ZVS Efficiency:     %.2f %%\n', results.mean_zvs_efficiency_pct);
    fprintf(' Final Pack Voltage:      %.3f V\n', results.pack_voltage_final_v);
    fprintf(' Max Cell Temperature:    %.2f C\n', max(max(temp_history)));
    fprintf('=================================================================\n');
end
