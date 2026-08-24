function [params, mode_info] = degradation_mode_library(mode_input, soh_estimate, temperature)
%DEGRADATION_MODE_LIBRARY Get parameters for different degradation modes with mixed-mode support
%
%   [PARAMS, MODE_INFO] = DEGRADATION_MODE_LIBRARY(MODE_INPUT, SOH_ESTIMATE, TEMPERATURE)
%   returns a struct with parameter adjustments for the specified degradation
%   mode(s) and diagnostic information.
%
%   Enhanced version that supports:
%   - Mixed degradation modes (e.g., 0.3*li_plating + 0.7*active_material_loss)
%   - Continuous degradation progression modeling
%   - Uncertainty quantification
%   - SOH-dependent parameter scaling
%   - Temperature-dependent parameter adjustments
%
%   INPUTS:
%     MODE_INPUT - Degradation mode specification. Can be:
%                  * String: 'healthy', 'li_plating', etc. (backward compatible)
%                  * Struct: with fields .mode (string) and .weight (scalar) for single mode
%                  * Cell array of structs: [{.mode, .weight}, ...] for mixed modes
%                  * Vector: numeric codes [1,2,3...] mapping to mode list
%                  * Empty or omitted: defaults to healthy
%     SOH_ESTIMATE - Estimated State of Health (0-100%). If provided, parameters
%                    are adjusted based on degradation severity.
%     TEMPERATURE - Battery temperature in Kelvin. If provided, parameters are
%                   adjusted based on temperature effects on electrochemical
%                   properties.
%
%   OUTPUTS:
%     PARAMS - Struct with scaled parameters:
%              R0_scale, R1_scale, C1_scale, sos_factor, attenuation_factor,
%              phase_factor, R_th_scale, C_th_scale, heat_factor
%     MODE_INFO - Diagnostic information struct containing:
%                 detected_modes: cell array of mode names
%                 mode_weights: corresponding weights (sum to 1)
%                 primary_mode: most likely mode
%                 mode_entropy: measure of mixedness (0=pure, log(N)=maximum mixed)
%                 soh_adjustment: whether SOH-based adjustment was applied
%                 temperature_adjustment: whether temperature-based adjustment was applied
%                 degradation_progression: estimated progression stage (0-1)
%
%   EXAMPLES:
%     % Backward compatible usage
%     [params, info] = degradation_mode_library('li_plating');
%
%     % Mixed mode usage
%     modes = {struct('mode','li_plating','weight',0.4), ...
%              struct('mode','active_material_loss','weight',0.6)};
%     [params, info] = degradation_mode_library(modes, 75.0);
%
%     % With temperature adjustment
%     [params, info] = degradation_mode_library('li_plating', 65.0, 310.15);  % 37°C
%
%   See also load_parameters, estimate_ecm_params_rls

    % Default SOH estimate if not provided
    if nargin < 2 || isempty(soh_estimate)
        soh_estimate = 100.0;  % Assume healthy if SOH unknown
    end

    % Default temperature if not provided (ambient temperature from load_parameters)
    if nargin < 3 || isempty(temperature)
        temp_params = load_parameters();
        temperature = temp_params.AMBIENT_TEMPERATURE_K;  % Default to ambient
    end

    % Define base mode parameters (same as original library)
    base_modes = containers.Map;
    % Format: mode_name -> struct with scaling factors

    % Healthy baseline
    base_modes('healthy') = struct( ...
        'R0_scale', 1.0, 'R1_scale', 1.0, 'C1_scale', 1.0, ...
        'sos_factor', 1.0, 'attenuation_factor', 1.0, 'phase_factor', 0.0, ...
        'R_th_scale', 1.0, 'C_th_scale', 1.0, 'heat_factor', 1.0);

    % Lithium plating (recoverable)
    base_modes('li_plating') = struct( ...
        'R0_scale', 1.2, 'R1_scale', 1.1, 'C1_scale', 0.95, ...
        'sos_factor', 0.995, 'attenuation_factor', 1.05, 'phase_factor', -0.01, ...
        'R_th_scale', 1.05, 'C_th_scale', 0.99, 'heat_factor', 1.05);

    % Severe lithium plating (less recoverable)
    base_modes('severe_li_plating') = struct( ...
        'R0_scale', 1.5, 'R1_scale', 1.3, 'C1_scale', 0.8, ...
        'sos_factor', 0.98, 'attenuation_factor', 1.2, 'phase_factor', -0.02, ...
        'R_th_scale', 1.1, 'C_th_scale', 0.95, 'heat_factor', 1.1);

    % Active material loss
    base_modes('active_material_loss') = struct( ...
        'R0_scale', 1.1, 'R1_scale', 1.2, 'C1_scale', 0.8, ...
        'sos_factor', 0.98, 'attenuation_factor', 1.2, 'phase_factor', -0.02, ...
        'R_th_scale', 1.1, 'C_th_scale', 0.95, 'heat_factor', 1.1);

    % Electrolyte decomposition
    base_modes('electrolyte_decomposition') = struct( ...
        'R0_scale', 1.15, 'R1_scale', 1.15, 'C1_scale', 0.85, ...
        'sos_factor', 0.985, 'attenuation_factor', 1.15, 'phase_factor', -0.015, ...
        'R_th_scale', 1.08, 'C_th_scale', 0.97, 'heat_factor', 1.08);

    % Gas generation
    base_modes('gas_generation') = struct( ...
        'R0_scale', 1.3, 'R1_scale', 1.0, 'C1_scale', 0.9, ...
        'sos_factor', 0.97, 'attenuation_factor', 1.5, 'phase_factor', -0.03, ...
        'R_th_scale', 1.3, 'C_th_scale', 0.9, 'heat_factor', 1.2);

    % Internal short
    base_modes('internal_short') = struct( ...
        'R0_scale', 0.8, 'R1_scale', 0.9, 'C1_scale', 0.95, ...
        'sos_factor', 0.99, 'attenuation_factor', 2.0, 'phase_factor', 0.02, ...
        'R_th_scale', 0.8, 'C_th_scale', 1.02, 'heat_factor', 2.0);

    % Define mode list for consistent ordering
    mode_list = {'healthy', 'li_plating', 'severe_li_plating', 'active_material_loss', ...
                 'electrolyte_decomposition', 'gas_generation', 'internal_short'};

    % Parse input mode specification
    [mode_names, mode_weights] = parse_mode_input(mode_input, mode_list);

    % Normalize weights to sum to 1
    if ~isempty(mode_weights)
        mode_weights = mode_weights / sum(mode_weights);
    else
        % Default to healthy if no modes specified
        mode_names = {'healthy'};
        mode_weights = [1.0];
    end

    % Calculate mixed-mode parameters (weighted average)
    params = struct();
    % Initialize all fields to 0 explicitly
    params.R0_scale = 0;
    params.R1_scale = 0;
    params.C1_scale = 0;
    params.sos_factor = 0;
    params.attenuation_factor = 0;
    params.phase_factor = 0;
    params.R_th_scale = 0;
    params.C_th_scale = 0;
    params.heat_factor = 0;

    % Accumulate weighted values
    for i = 1:numel(mode_names)
        if isKey(base_modes, mode_names{i})
            mode_data = base_modes(mode_names{i});
            params.R0_scale = params.R0_scale + mode_weights(i) * mode_data.R0_scale;
            params.R1_scale = params.R1_scale + mode_weights(i) * mode_data.R1_scale;
            params.C1_scale = params.C1_scale + mode_weights(i) * mode_data.C1_scale;
            params.sos_factor = params.sos_factor + mode_weights(i) * mode_data.sos_factor;
            params.attenuation_factor = params.attenuation_factor + mode_weights(i) * mode_data.attenuation_factor;
            params.phase_factor = params.phase_factor + mode_weights(i) * mode_data.phase_factor;
            params.R_th_scale = params.R_th_scale + mode_weights(i) * mode_data.R_th_scale;
            params.C_th_scale = params.C_th_scale + mode_weights(i) * mode_data.C_th_scale;
            params.heat_factor = params.heat_factor + mode_weights(i) * mode_data.heat_factor;
        else
            warning('Unknown degradation mode: %s. Using healthy baseline.', mode_names{i});
            healthy_data = base_modes('healthy');
            params.R0_scale = params.R0_scale + mode_weights(i) * healthy_data.R0_scale;
            params.R1_scale = params.R1_scale + mode_weights(i) * healthy_data.R1_scale;
            params.C1_scale = params.C1_scale + mode_weights(i) * healthy_data.C1_scale;
            params.sos_factor = params.sos_factor + mode_weights(i) * healthy_data.sos_factor;
            params.attenuation_factor = params.attenuation_factor + mode_weights(i) * healthy_data.attenuation_factor;
            params.phase_factor = params.phase_factor + mode_weights(i) * healthy_data.phase_factor;
            params.R_th_scale = params.R_th_scale + mode_weights(i) * healthy_data.R_th_scale;
            params.C_th_scale = params.C_th_scale + mode_weights(i) * healthy_data.C_th_scale;
            params.heat_factor = params.heat_factor + mode_weights(i) * healthy_data.heat_factor;
        end
    end

    % Apply SOH-based adjustments for degradation progression
    [params_adj, soh_info] = apply_soh_adjustments(params, mode_names, mode_weights, soh_estimate);
    params = params_adj;

    % Apply temperature-based adjustments
    [params_temp, temp_info] = apply_temperature_adjustments(params, mode_names, mode_weights, temperature);
    params = params_temp;

    % Calculate diagnostic information
    mode_info = struct();
    mode_info.detected_modes = mode_names;
    mode_info.mode_weights = mode_weights;
    [~, idx] = max(mode_weights);
    mode_info.primary_mode = mode_names{idx};
    mode_info.mode_entropy = -sum(mode_weights .* log2(mode_weights + eps));
    mode_info.soh_adjustment = soh_info.applied;
    mode_info.temperature_adjustment = temp_info.applied;
    mode_info.degradation_progression = soh_info.progression_stage;
end

function [mode_names, mode_weights] = parse_mode_input(mode_input, mode_list)
    % Parse various mode input formats into cell array of names and vector of weights

    if nargin < 2
        mode_list = {'healthy', 'li_plating', 'severe_li_plating', 'active_material_loss', ...
                     'electrolyte_decomposition', 'gas_generation', 'internal_short'};
    end

    mode_names = {};
    mode_weights = [];

    if isempty(mode_input)
        % Empty input defaults to healthy
        mode_names = {'healthy'};
        mode_weights = [1.0];
        return;
    end

    if ischar(mode_input) || isstring(mode_input)
        % String input - single mode
        mode_str = lower(char(mode_input));
        mode_names = {mode_str};
        mode_weights = [1.0];
    elseif isstruct(mode_input)
        % Struct input - single mode with weight
        if isfield(mode_input, 'mode') && isfield(mode_input, 'weight')
            mode_names = {lower(char(mode_input.mode))};
            mode_weights = [double(mode_input.weight)];
        else
            error('Invalid struct format. Must contain .mode and .weight fields.');
        end
    elseif iscell(mode_input)
        % Cell array input - could be strings or structs
        if all(cellfun(@(x) ischar(x) || isstring(x), mode_input))
            % Cell array of strings
            mode_names = lower(cellfun(@char, mode_input, 'UniformOutput', false));
            mode_weights = ones(size(mode_names));
        elseif all(cellfun(@isstruct, mode_input))
            % Cell array of structs
            mode_names = {};
            mode_weights = [];
            for i = 1:numel(mode_input)
                % Use {} to access cell contents, not ()
                if isfield(mode_input{i}, 'mode') && isfield(mode_input{i}, 'weight')
                    mode_names{end+1} = lower(char(mode_input{i}.mode));
                    mode_weights(end+1) = double(mode_input{i}.weight);
                else
                    error('Invalid struct at index %d. Must contain .mode and .weight fields.', i);
                end
            end
        else
            error('Cell array must contain either all strings or all structs.');
        end
    elseif isnumeric(mode_input)
        % Numeric input - map to mode list indices
        mode_input = round(mode_input);  % Ensure integers
        valid_idx = mode_input >= 1 & mode_input <= numel(mode_list);
        if ~all(valid_idx)
            error('Numeric mode values must be between 1 and %d.', numel(mode_list));
        end
        mode_names = mode_list(mode_input);
        mode_weights = ones(size(mode_input));
    else
        error('Unsupported mode_input type. Use string, struct, cell array, or numeric vector.');
    end
end

function [params_adj, soh_info] = apply_soh_adjustments(params, mode_names, mode_weights, soh_estimate)
    % Apply SOH-based adjustments to model degradation progression

    soh_info.applied = false;
    soh_info.progression_stage = 0;

    % Only apply SOH adjustments if SOH is below nominal (indicating degradation)
    if soh_estimate >= 98.0
        % Nearly healthy - minimal adjustment needed
        params_adj = params;
        return;
    end

    % Calculate degradation severity (0 = healthy, 1 = fully degraded)
    degradation_severity = max(0, min(1, (100.0 - soh_estimate) / 50.0));
    % Scale so that 50% SOH = severity 1.0, 100% SOH = severity 0

    % Apply SOH adjustments
    params_adj = params;  % Start with a copy

    if degradation_severity > 0
        % Calculate degradation contribution (excluding healthy mode)
        healthy_idx = strcmp(mode_names, 'healthy');
        if any(healthy_idx)
            healthy_weight = mode_weights(healthy_idx);
            degradation_weight = 1.0 - healthy_weight;
        else
            degradation_weight = 1.0;  % No healthy component
        end

        if degradation_weight > 0
            % Define SOH adjustment factors for each parameter type
            % These represent how parameters continue to degrade with progressing SOH
            R0_factor = 1.0 + 0.5 * degradation_severity;      % Resistance increases with degradation
            R1_factor = 1.0 + 0.3 * degradation_severity;      % Polarization resistance
            C1_factor = 1.0 - 0.4 * degradation_severity;      % Capacitance decreases
            sos_factor = 1.0 - 0.02 * degradation_severity;    % Speed of sound decreases slightly
            attenuation_factor = 1.0 + 0.8 * degradation_severity; % Attenuation increases significantly
            phase_factor = -0.03 * degradation_severity;       % Phase shift increases in magnitude
            R_th_factor = 1.0 + 0.4 * degradation_severity;    % Thermal resistance increases
            C_th_factor = 1.0 - 0.3 * degradation_severity;    % Thermal capacitance decreases
            heat_factor = 1.0 + 1.0 * degradation_severity;    % Heat generation increases significantly

            % Blend between base params and SOH-adjusted params based on degradation contribution
            params_adj.R0_scale = (1 - degradation_weight) * params.R0_scale + degradation_weight * (params.R0_scale * R0_factor);
            params_adj.R1_scale = (1 - degradation_weight) * params.R1_scale + degradation_weight * (params.R1_scale * R1_factor);
            params_adj.C1_scale = (1 - degradation_weight) * params.C1_scale + degradation_weight * (params.C1_scale * C1_factor);
            params_adj.sos_factor = (1 - degradation_weight) * params.sos_factor + degradation_weight * (params.sos_factor * sos_factor);
            params_adj.attenuation_factor = (1 - degradation_weight) * params.attenuation_factor + degradation_weight * (params.attenuation_factor * attenuation_factor);
            params_adj.phase_factor = (1 - degradation_weight) * params.phase_factor + degradation_weight * (params.phase_factor * phase_factor);
            params_adj.R_th_scale = (1 - degradation_weight) * params.R_th_scale + degradation_weight * (params.R_th_scale * R_th_factor);
            params_adj.C_th_scale = (1 - degradation_weight) * params.C_th_scale + degradation_weight * (params.C_th_scale * C_th_factor);
            params_adj.heat_factor = (1 - degradation_weight) * params.heat_factor + degradation_weight * (params.heat_factor * heat_factor);
        end
        % If degradation_weight = 0 (pure healthy), no SOH adjustment needed (params_adj already equals params)
    end

    soh_info.applied = true;
    soh_info.progression_stage = degradation_severity;
end

function [params_adj, temp_info] = apply_temperature_adjustments(params, mode_names, mode_weights, temperature)
    % Apply temperature-based adjustments to model parameters

    temp_info.applied = false;
    temp_info.progression_stage = 0;

    % Load nominal parameters to get reference temperature
    nominal_params = load_parameters();
    T_nominal = nominal_params.AMBIENT_TEMPERATURE_K;  % Nominal temperature (25°C = 298.15K)

    % Calculate temperature difference from nominal
    delta_T = temperature - T_nominal;

    % Only apply temperature adjustments if significantly different from nominal
    if abs(delta_T) < 1.0  % Less than 1K difference - negligible
        params_adj = params;
        return;
    end

    % Calculate normalized temperature effect
    % Using a linear approximation for modest temperature ranges
    % For larger ranges, more complex models would be needed
    temp_effect = delta_T / T_nominal;  % Normalized temperature difference

    % Apply temperature adjustments
    params_adj = params;  % Start with a copy

    if abs(temp_effect) > 0
        % Define temperature adjustment factors for each parameter type
        % Based on typical battery temperature coefficients

        % Resistance typically increases with temperature (positive tempco)
        % But for battery ECM, the relationship is complex
        R0_temp = 1.0 + 0.003 * temp_effect;      % ~0.3%/°C for resistance
        R1_temp = 1.0 + 0.002 * temp_effect;      % ~0.2%/°C for polarization resistance
        C1_temp = 1.0 - 0.01 * temp_effect;       % ~-1%/°C for capacitance (decreases with temp)
        sos_temp = 1.0 + 0.001 * temp_effect;     % Speed of sound increases slightly with temp
        attenuation_temp = 1.0 - 0.005 * temp_effect; % Attenuation decreases with temp
        phase_temp = 0.0;  % Phase shift less temperature dependent
        R_th_temp = 1.0 - 0.002 * temp_effect;    % Thermal resistance decreases slightly with temp
        C_th_temp = 1.0 + 0.001 * temp_effect;    % Thermal capacitance increases slightly with temp
        heat_temp = 1.0 + 0.005 * temp_effect;    % Heat generation increases with temp

        % Apply temperature adjustments (multiplicative with existing params)
        params_adj.R0_scale = params.R0_scale * R0_temp;
        params_adj.R1_scale = params.R1_scale * R1_temp;
        params_adj.C1_scale = params.C1_scale * C1_temp;
        params_adj.sos_factor = params.sos_factor * sos_temp;
        params_adj.attenuation_factor = params.attenuation_factor * attenuation_temp;
        params_adj.phase_factor = params.phase_factor + phase_temp;  % Additive for phase
        params_adj.R_th_scale = params.R_th_scale * R_th_temp;
        params_adj.C_th_scale = params.C_th_scale * C_th_temp;
        params_adj.heat_factor = params.heat_factor * heat_temp;
    end

    temp_info.applied = true;
    temp_info.progression_stage = abs(temp_effect);  % Normalized temperature deviation
end