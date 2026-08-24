function model = init_physics_model()
%INIT_PHYSICS_MODEL Initialize the multi-physics battery cell model
%
%   MODEL = INIT_PHYSICS_MODEL() returns a struct containing the
%   initialized physics model for simulating electrical, ultrasonic,
%   and thermal responses.

    model = struct();

    % Store parameters
    model.P = load_parameters();

    % Precompute some values for efficiency
    model.t = (0:1/model.P.DAQ_SAMPLING_RATE_HZ:model.P.EXCITATION_PERIOD_S)';
    model.t = model.t(1:end-1); % Remove last element to match SAMPLES_PER_CYCLE exactly
    assert(numel(model.t) == model.P.SAMPLES_PER_CYCLE, 'Time vector mismatch');

    % Precompute excitation pulse
    model.excitation_pulse = zeros(size(model.t));
    pulse_width_samples = round(model.P.EXCITATION_PULSE_WIDTH_S * model.P.DAQ_SAMPLING_RATE_HZ);
    model.excitation_pulse(1:pulse_width_samples) = model.P.EXCITATION_PULSE_AMPLITUDE_A;

end
