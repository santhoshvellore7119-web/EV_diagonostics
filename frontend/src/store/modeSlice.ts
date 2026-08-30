import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface ModeState {
  current: 'live' | 'simulink' | '3d' | 'gazebo';
}

const initialState: ModeState = {
  current: '3d', // default to 3D simulation
};

export const modeSlice = createSlice({
  name: 'mode',
  initialState,
  reducers: {
    setMode: (state, action: PayloadAction<'live' | 'simulink' | '3d' | 'gazebo'>) => {
      state.current = action.payload;
    },
  },
});

export const { setMode } = modeSlice.actions;

export default modeSlice.reducer;