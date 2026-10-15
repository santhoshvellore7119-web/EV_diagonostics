% =========================================================================
% COMPUTE ULTRASONIC CODA WAVE INTERFEROMETRY (CWI) VELOCITY SHIFT IN MATLAB
% =========================================================================
% Implements the waveform stretching method on reverberation coda:
% dv/v = -eps_max, K_d = 1 - max CC(eps)

function [dv_over_v, decorrelation, max_cc] = compute_cwi_velocity_shift(ref_signal, cur_signal, coda_indices, eps_range)
    if nargin < 3 || isempty(coda_indices)
        coda_indices = round(length(ref_signal)*0.35) : round(length(ref_signal)*0.90);
    end
    if nargin < 4 || isempty(eps_range)
        eps_range = 0.05; % +/- 5% velocity search range
    end

    s_ref = ref_signal(coda_indices);
    s_cur = cur_signal(coda_indices);

    % Normalize
    s_ref = (s_ref - mean(s_ref)) / (norm(s_ref) + 1e-9);
    s_cur = (s_cur - mean(s_cur)) / (norm(s_cur) + 1e-9);

    t_orig = 1:length(s_ref);
    eps_grid = linspace(-eps_range, eps_range, 121);
    cc_vals = zeros(size(eps_grid));

    for i = 1:length(eps_grid)
        eps = eps_grid(i);
        t_stretched = t_orig * (1 + eps);
        s_stretched = interp1(t_orig, s_cur, t_stretched, 'linear', 0);
        denom = norm(s_stretched) * norm(s_ref) + 1e-9;
        cc_vals(i) = dot(s_ref, s_stretched) / denom;
    end

    [max_cc, best_idx] = max(cc_vals);
    best_eps = eps_grid(best_idx);
    dv_over_v = -best_eps;
    decorrelation = max(0, 1 - max_cc);
end
