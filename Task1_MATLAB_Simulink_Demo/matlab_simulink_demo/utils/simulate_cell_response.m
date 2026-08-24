function response = simulate_cell_response(model, soc, degradation_mode, add_noise)
%SIMULATE_CELL_RESPONSE Simulate battery cell response
%
%   RESPONSE = SIMULATE_CELL_RESPONSE(MODEL, SOC, DEGRADATION_MODE, ADD_NOISE)
%   simulates the electrical, ultrasonic, and thermal response of a battery
%   cell to an excitation pulse.
%
%   Inputs:
%       model - model struct from init_physics_model
%       soc - state of charge (0-1)
%       degradation_mode - string indicating degradation mode
%       add_noise - boolean to add noise (default: true)
%
%   Output:
%       response - struct containing electrical, ultrasonic, and thermal responses

    if nargin < 4, add_noise = true; end
    if nargin < 3, degradation_mode = 'healthy'; end
    if nargin < 2, soc = 0.5; end

    % Update parameters based on degradation mode
    params = model.P;
    params = update_degradation_mode(params, degradation_mode);

    P = params;
    t = model.t;
    excitation_pulse = model.excitation_pulse;
    dt = t(2) - t(1);

    response = struct();

    % Electrical response (ECM voltage)
    ocv = P.OCV_INTERCEPT + P.OCV_SLOPE * soc;
    % Voltage drop across R0 and RC parallel combination
    % V_rc voltage across the RC pair
    v_rc = zeros(size(t));

    % Simple RC circuit simulation for the polarization voltage
    % dv_rc/dt = -v_rc/(R1*C1) + i/C1
    % Discretized: v_rc[k] = v_rc[k-1]*exp(-dt/(R1*C1)) + i[k]*R1*(1-exp(-dt/(R1*C1)))
    rc_time_constant = P.R1 * P.C1;
    alpha = exp(-dt / rc_time_constant);
    beta = P.R1 * (1 - alpha);

    for k = 2:length(t)
        v_rc(k) = v_rc(k-1) * alpha + excitation_pulse(k) * beta;
    end

    voltage = ocv - excitation_pulse * P.R0 - v_rc;
    current = excitation_pulse;
    power = voltage .* current;

    if add_noise
        voltage = voltage + randn(size(voltage)) * P.ELECTRICAL_NOISE_STD_V * (1 + P.noise_level);
    end
    response.electrical = struct('voltage', voltage, 'current', current, 'power', power);

    % Ultrasonic response
    tof_base = 2 * P.ULTRASONIC_PATH_LENGTH_M / P.SOS;
    tof = tof_base / P.sos_factor;  % Adjust for degradation mode

    % Simulate received signal with delay and attenuation
    delay_samples = round(tof * P.DAQ_SAMPLING_RATE_HZ);
    delay_samples = max(0, min(delay_samples, length(excitation_pulse)-1));
    received_signal = zeros(size(excitation_pulse));
    if delay_samples < length(excitation_pulse)
        received_signal(delay_samples+1:end) = excitation_pulse(1:end-delay_samples);
    end
    received_signal = received_signal / P.attenuation_factor;

    if add_noise
        received_signal = received_signal + randn(size(received_signal)) * 0.01 * P.noise_level;
    end

    [~, peak_idx] = max(abs(received_signal));
    amplitude = abs(received_signal(peak_idx));
    phase_shift = P.phase_factor + randn * 0.01 * P.noise_level;

    response.ultrasonic = struct('tof', tof, 'amplitude', amplitude, 'phase_shift', phase_shift);

    % Thermal response
    power_dissipated = excitation_pulse.^2 * P.R0;
    energy_per_sample = power_dissipated * dt;
    temperature_rise = zeros(size(t));
    temp_ambient = P.AMBIENT_TEMPERATURE_K;
    R_th = P.THERMAL_RESISTANCE_K_PER_W * P.R_th_scale;
    C_th = P.THERMAL_CAPACITY_J_PER_K * P.C_th_scale;
    heat_factor = P.heat_factor;

    for i = 2:length(t)
        power_in = energy_per_sample(i-1) * heat_factor;
        if i > 1
            power_out = (temperature_rise(i-1) + temp_ambient - temp_ambient) / R_th;
        else
            power_out = 0;
        end
        dT_dt = (power_in - power_out) / C_th * dt;
        temperature_rise(i) = temperature_rise(i-1) + dT_dt;
    end
    dT_dt_final = (energy_per_sample(end) * heat_factor - ...
                   (temperature_rise(end) + temp_ambient - temp_ambient) / R_th) / C_th;
    if add_noise
        temperature_rise = temperature_rise + randn(size(temperature_rise)) * P.THERMAL_NOISE_STD_K * (1 + P.noise_level);
    end
    response.thermal = struct('temperature_rise', temperature_rise, 'dT_dt', dT_dt_final);
end