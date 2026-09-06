function params = update_degradation_mode(params, mode)
%UPDATE_DEGRADATION_MODE Update parameters based on degradation mode
%   PARAMS = UPDATE_DEGRADATION_MODE(PARAMS, MODE) updates the PARAMS struct
%   with scaling factors for the specified degradation mode.
%
%   Supported modes: 'healthy', 'li_plating', 'severe_li_plating',
%   'active_material_loss', 'gas_generation', 'internal_short'

    % Get degradation mode scaling factors
    mode_params = degradation_mode_library(mode);

    % Update scale factors
    params.R0_scale = mode_params.R0_scale;
    params.R1_scale = mode_params.R1_scale;
    params.C1_scale = mode_params.C1_scale;
    params.sos_factor = mode_params.sos_factor;
    params.attenuation_factor = mode_params.attenuation_factor;
    params.phase_factor = mode_params.phase_factor;
    params.R_th_scale = mode_params.R_th_scale;
    params.C_th_scale = mode_params.C_th_scale;
    params.heat_factor = mode_params.heat_factor;

    % Recalculate effective parameters
    params.R0 = params.R0_NOMINAL * params.R0_scale;
    params.R1 = params.R1_NOMINAL * params.R1_scale;
    params.C1 = params.C1_NOMINAL * params.C1_scale;

    % Update current degradation mode for reference
    params.current_degradation = mode;
end
