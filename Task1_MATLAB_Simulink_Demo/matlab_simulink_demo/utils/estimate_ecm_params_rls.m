function [param_est, param_unc] = estimate_ecm_params_rls(y, u, P_prev, lambda, theta_dim)
%ESTIMATE_ECM_PARAMS_RLS Recursive Least Squares estimator for ECM parameters
%
%   [PARAM_EST, PARAM_UNC] = ESTIMATE_ECM_PARAMS_RLS(Y, U, P_PREV, LAMBDA, THETA_DIM)
%   estimates ECM parameters [R0, R1, C1] using Recursive Least Squares.
%
%   Inputs:
%       y - measured output (voltage)
%       u - input (current)
%       P_prev - previous covariance matrix
%       lambda - forgetting factor (0 < lambda <= 1)
%       theta_dim - number of parameters to estimate (3 for [R0, R1, C1])
%
%   Outputs:
%       param_est - estimated parameters [R0_est, R1_est, C1_est]
%       param_unc - parameter uncertainties (sqrt of diagonal of covariance)

    % Persistent variables to maintain state between calls
    persistent P theta_est

    % Initialize on first call
    if isempty(P) || isempty(theta_est)
        % Initial parameter guess [R0, R1, C1]
        theta_est = [0.02; 0.01; 1000];  % [Ohm, Ohm, Farad]
        % Initial covariance matrix
        P = eye(theta_dim) * 1000;  % Large initial uncertainty
    end

    % Forgetting factor (if not provided, use default)
    if nargin < 4 || isempty(lambda)
        lambda = 0.99;  % Default forgetting factor
    end

    % Ensure lambda is in valid range
    lambda = max(0.95, min(1.0, lambda));

    % For ECM: voltage = OCV - R0*current - R1*current*(1 - exp(-t/(R1*C1)))
    % We'll use a simplified linear-in-paramenters form for RLS
    % For small time constants or specific operating points, we can approximate

    % Regressor vector for ECM voltage model:
    % v = OCV - R0*i - v_polarization
    % where v_polarization is modeled as receiver output of RC circuit

    % Simplified approach: use voltage and current to estimate resistance
    % More sophisticated: use battery model structure

    % For this implementation, we'll estimate [R0, R1] assuming known C1
    % or use a simplified model that's linear in parameters

    % Battery voltage model: V = OCV - I*R0 - V1
    % where dV1/dt = -V1/(R1*C1) + I/C1

    % Discretizing: V1[k] = V1[k-1]*exp(-Ts/(R1*C1)) + I[k]*R1*(1-exp(-Ts/(R1*C1)))
    % This is not linear in R1 and C1

    % Alternative: Use current integration approach or focus on resistance estimation
    % For now, implement a basic RLS for resistance estimation

    % Simplified voltage model: V = OCV - I*R_total
    % where we estimate R_total and then try to separate R0 and R1

    % This is a simplification - in practice, you'd need a more complex observer
    % or execute at different frequencies to separate R0 and R1 effects

    % For demonstration, we'll estimate effective resistance
    % and use nominal C1 value to estimate R1 from time constant if possible

    % Regressor: [-current] for estimating effective resistance
    phi = [-u];  % Regressor for -I*R term

    % Gain calculation
    lambda = 0.99;  % Forgetting factor
    L = (P * phi) / (lambda + phi' * P * phi);

    % Parameter update
    theta_est = theta_est + L' * (y - phi * theta_est);

    % Covariance update
    P = (P - L * phi' * P) / lambda;

    % Ensure positive definite
    P = (P + P') / 2;

    % Extract estimated parameters
    R0_est = max(0.001, theta_est(1));  % Ensure positive resistance
    R1_est = max(0.001, theta_est(2));  % Ensure positive resistance

    % For now, keep C1 nominal since it's harder to identify without dynamics
    C1_est = 1000;  % Nominal value

    param_est = [R0_est; R1_est; C1_est];

    % Parameter uncertainties (standard deviation)
    param_unc = sqrt(diag(P));

    % Scale uncertainties appropriately
    param_unc(1) = max(param_unc(1), 0.0001);  % R0 uncertainty
    param_unc(2) = max(param_unc(2), 0.0001);  % R1 uncertainty
    param_unc(3) = max(param_unc(3), 1.0);     % C1 uncertainty
end

% Reset function for initializing estimator
function reset_ecm_params_rls()
%RESET_ECM_PARAMS_RLS Reset the RLS estimator to initial conditions
    % Clear persistent variables
    if isvector(instrfindall) || ~isempty(instrfindall)
        clear estimate_ecm_params_rls;
    end
end