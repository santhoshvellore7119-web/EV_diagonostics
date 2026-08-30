import { configureStore } from '@reduxjs/toolkit';
import diagnosticFrameReducer from './diagnosticFrameSlice';
import modeReducer from './modeSlice';
import timelineReducer from './timelineSlice';

export const store = configureStore({
  reducer: {
    diagnosticFrame: diagnosticFrameReducer,
    mode: modeReducer,
    timeline: timelineReducer,
  },
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;