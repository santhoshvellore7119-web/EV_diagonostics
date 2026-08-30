import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface DiagnosticFrame {
  // Timing and identification
  timestamp: number;
  frameId: string;
  source: 'live' | 'simulink' | '3d' | 'gazebo';
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

  // Rebalancing state
  rebalancing_state: string;
  rebalancing_selectedAction: string;
  rebalancing_actionReason: string;
  rebalancing_powerStage_targetCurrent: number;
  rebalancing_powerStage_actualCurrent: number;
  rebalancing_powerStage_targetVoltage: number;
  rebalancing_powerStage_actualVoltage: number;
  rebalancing_powerStage_pwmDutyCycle: number;
  rebalancing_executionTime: number;

  // Simulation fields (optional)
  simulation_soc?: number;
  simulation_excitationAmplitude?: number;
  simulation_noiseLevel?: number;
  simulation_stepCount?: number;
}

interface DiagnosticFrameState {
  frame: DiagnosticFrame | null;
  loading: boolean;
  error: string | null;
}

const initialState: DiagnosticFrameState = {
  frame: null,
  loading: false,
  error: null
};

export const diagnosticFrameSlice = createSlice({
  name: 'diagnosticFrame',
  initialState,
  reducers: {
    setFrame: (state, action: PayloadAction<DiagnosticFrame>) => {
      state.frame = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
});

export const { setFrame, setLoading, setError } = diagnosticFrameSlice.actions;

export default diagnosticFrameSlice.reducer;