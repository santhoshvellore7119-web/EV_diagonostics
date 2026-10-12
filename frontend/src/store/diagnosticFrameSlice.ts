import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface DiagnosticFrame {
  // Timing and identification
  timestamp: number;
  frameId: string;
  source: 'live' | 'simulink' | '3d' | 'gazebo';
  data_origin?: string;
  cellId: string;
  packId?: string;

  // Electrical data
  electrical_voltage: number;
  electrical_current: number;
  electrical_power: number;
  electrical_resistance: number;
  electrical_uncertainty: number;

  // Ultrasonic data
  ultrasonic_timeOfFlight: number;
  ultrasonic_amplitude: number;
  ultrasonic_phaseShift: number;
  ultrasonic_speedOfSound: number;
  ultrasonic_uncertainty: number;

  // Thermal data
  thermal_temperature: number;
  thermal_tempGradient: number;
  thermal_heatFlux: number;
  thermal_uncertainty: number;

  // State of Health
  stateOfHealth_value: number;
  stateOfHealth_confidenceInterval_lower: number;
  stateOfHealth_confidenceInterval_upper: number;
  stateOfHealth_method: string;

  // Degradation classification
  degradation_mode: string;
  degradation_probability: number;
  degradation_perClass_healthy: number;
  degradation_perClass_li_plating: number;
  degradation_perClass_active_material_loss: number;
  degradation_perClass_electrolyte_decomposition: number;
  degradation_perClass_gas_generation: number;
  degradation_perClass_internal_short: number;
  degradation_entropy: number;

  // Rebalancing state & Power stage
  rebalancing_state: string;
  rebalancing_active?: boolean;
  rebalancing_selectedAction: string;
  rebalancing_actionReason: string;
  rebalancing_powerStage_targetCurrent: number;
  rebalancing_powerStage_actualCurrent: number;
  rebalancing_powerStage_targetVoltage: number;
  rebalancing_powerStage_actualVoltage: number;
  rebalancing_powerStage_pwmDutyCycle: number;
  rebalancing_executionTime: number;
  zvs_efficiency_pct?: number;

  // Simulation fields (optional)
  simulation_soc?: number;
  simulation_temp_amb?: number;
  simulation_load_c?: number;
  simulation_cycle_count?: number;
  simulation_excitationAmplitude?: number;
  simulation_noiseLevel?: number;
  simulation_stepCount?: number;

  // Battery chemistry & geometry
  battery_chemistry?: string;
  battery_chemistry_name?: string;
  battery_form_factor?: string;
  battery_form_factor_name?: string;

  // Online 2-RC ECM & EIS Nyquist Observer
  ecm_r0_est?: number;
  ecm_r1_est?: number;
  ecm_c1_est?: number;
  ecm_r2_est?: number;
  ecm_c2_est?: number;
  ecm_v_rc1?: number;
  ecm_v_rc2?: number;
  ecm_ocv_est?: number;
  eis_spectrum?: Array<{
    freq_hz: number;
    z_real_ohm: number;
    z_imag_ohm: number;
  }>;

  // PINN & RUL & Cross-Modal Attention
  pinn_physics_residual?: number;
  rul_remaining_cycles?: number;
  rul_knee_point_cycles?: number;
  modality_attention_electrical?: number;
  modality_attention_ultrasonic?: number;
  modality_attention_thermal?: number;

  // Ultrasonic A-Scan Analytic Envelope
  ascan_waveform?: {
    time_us: number[];
    rf_signal_mv: number[];
    analytic_envelope_mv: number[];
    instantaneous_phase_rad?: number[];
  };

  // Automated Machine Cycle & 4S1P Pack Topology
  machine_cycle?: {
    running: boolean;
    stage: string;
    progress: number;
  };
  pack_cells?: Array<{
    id: number;
    soc: number;
    v: number;
    temp: number;
    r0_mohm?: number;
  }>;
}

export interface DiagnosticFrameState {
  frame: DiagnosticFrame | null;
  history: DiagnosticFrame[];
  maxHistorySize: number;
  isPaused: boolean;
  scrubIndex: number | null;
  loading: boolean;
  error: string | null;
}

const initialState: DiagnosticFrameState = {
  frame: null,
  history: [],
  maxHistorySize: 300,
  isPaused: false,
  scrubIndex: null,
  loading: false,
  error: null,
};

export const diagnosticFrameSlice = createSlice({
  name: 'diagnosticFrame',
  initialState,
  reducers: {
    setFrame: (state, action: PayloadAction<DiagnosticFrame>) => {
      // Append to ring buffer
      state.history.push(action.payload);
      if (state.history.length > state.maxHistorySize) {
        state.history.shift();
      }
      // If not paused or scrubbing, update active frame
      if (!state.isPaused && state.scrubIndex === null) {
        state.frame = action.payload;
      }
    },
    setScrubIndex: (state, action: PayloadAction<number | null>) => {
      state.scrubIndex = action.payload;
      if (action.payload !== null && action.payload >= 0 && action.payload < state.history.length) {
        state.frame = state.history[action.payload];
      } else if (action.payload === null && state.history.length > 0) {
        state.frame = state.history[state.history.length - 1];
      }
    },
    setIsPaused: (state, action: PayloadAction<boolean>) => {
      state.isPaused = action.payload;
      if (!action.payload && state.history.length > 0) {
        state.scrubIndex = null;
        state.frame = state.history[state.history.length - 1];
      }
    },
    clearHistory: (state) => {
      state.history = [];
      state.scrubIndex = null;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
});

export const { setFrame, setScrubIndex, setIsPaused, clearHistory, setLoading, setError } = diagnosticFrameSlice.actions;

export default diagnosticFrameSlice.reducer;