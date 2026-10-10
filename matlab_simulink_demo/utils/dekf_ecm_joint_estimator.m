% DEKF_ECM_JOINT_ESTIMATOR
% Dual Extended Kalman Filter (DEKF) for Joint State-of-Charge (SOC)
% and 2-RC Equivalent Circuit Model (ECM) Parameter Estimation [R0, R1, C1].
%
% Implements coupled state filter and parameter filter with covariance bounding.

function [soc_est, theta_est, P_state, P_param] = dekf_ecm_joint_estimator(v_meas, i_meas, dt, state_prev, theta_prev, P_state_prev, P_param_prev)
    if nargin < 3, dt = 0.01; end
    if nargin < 4 || isempty(state_prev)
        state_prev = [0.80; 0.0]; % [SOC; V_rc]
    end
    if nargin < 5 || isempty(theta_prev)
        theta_prev = [0.025; 0.015; 1200.0]; % [R0_ohm; R1_ohm; C1_farad]
    end
    if nargin < 6 || isempty(P_state_prev)
        P_state_prev = diag([1e-4, 1e-4]);
    end
    if nargin < 7 || isempty(P_param_prev)
        P_param_prev = diag([1e-5, 1e-5, 1e2]);
    end

    % Nominal capacity
    C_nominal_As = 2.5 * 3600.0; % 2.5 Ah in Coulombs

    % Unpack parameters
    R0 = max(0.005, theta_prev(1));
    R1 = max(0.002, theta_prev(2));
    C1 = max(100.0, theta_prev(3));
    tau_rc = R1 * C1;

    % Noise covariance matrices
    Q_state = diag([1e-6, 1e-5]);    % State process noise
    R_meas_v = 1e-4;                 % Voltage measurement noise
    Q_param = diag([1e-7, 1e-7, 1e-1]); % Parameter drift noise

    % -------------------------------------------------------------
    % 1. State Filter Time Update (Prediction)
    % -------------------------------------------------------------
    soc_pred = state_prev(1) - (i_meas * dt) / C_nominal_As;
    soc_pred = max(0.01, min(0.99, soc_pred));

    alpha_rc = exp(-dt / tau_rc);
    beta_rc = R1 * (1.0 - alpha_rc);
    v_rc_pred = state_prev(2) * alpha_rc + i_meas * beta_rc;

    x_pred = [soc_pred; v_rc_pred];

    % State Transition Jacobian F_x
    F_x = [1.0, 0.0; 0.0, alpha_rc];
    P_state_pred = F_x * P_state_prev * F_x' + Q_state;

    % -------------------------------------------------------------
    % 2. State Filter Measurement Update (Correction)
    % -------------------------------------------------------------
    % OCV model: OCV(SOC) = 3.0 + 1.2 * SOC
    ocv_pred = 3.0 + 1.2 * soc_pred;
    v_est_state = ocv_pred - i_meas * R0 - v_rc_pred;

    % Measurement Jacobian H_x = [d(V_est)/d(SOC), d(V_est)/d(V_rc)]
    H_x = [1.2, -1.0];
    K_state = (P_state_pred * H_x') / (H_x * P_state_pred * H_x' + R_meas_v);

    x_corr = x_pred + K_state * (v_meas - v_est_state);
    P_state = (eye(2) - K_state * H_x) * P_state_pred;

    soc_est = max(0.01, min(0.99, x_corr(1)));
    v_rc_est = x_corr(2);

    % -------------------------------------------------------------
    % 3. Parameter Filter Time Update
    % -------------------------------------------------------------
    theta_pred = theta_prev;
    P_param_pred = P_param_prev + Q_param;

    % -------------------------------------------------------------
    % 4. Parameter Filter Measurement Update
    % -------------------------------------------------------------
    v_est_param = (3.0 + 1.2 * soc_est) - i_meas * theta_pred(1) - v_rc_est;

    % Measurement Jacobian with respect to parameters H_theta = [dV/dR0, dV/dR1, dV/dC1]
    % dV/dR0 = -i_meas
    % dV/dR1 ≈ -i_meas * (1 - alpha_rc)
    % dV/dC1 ≈ -v_rc_est * (dt / (R1 * C1^2))
    H_theta = [-i_meas, -i_meas * (1.0 - alpha_rc), -v_rc_est * (dt / (R1 * C1^2 + 1e-6))];

    K_param = (P_param_pred * H_theta') / (H_theta * P_param_pred * H_theta' + R_meas_v);
    theta_corr = theta_pred + K_param * (v_meas - v_est_param);
    P_param = (eye(3) - K_param * H_theta) * P_param_pred;

    % Physical bounds enforcement
    theta_est = [
        max(0.005, min(0.200, theta_corr(1))); % R0: 5mOhm to 200mOhm
        max(0.002, min(0.150, theta_corr(2))); % R1: 2mOhm to 150mOhm
        max(100.0, min(5000.0, theta_corr(3)))  % C1: 100F to 5000F
    ];
end
