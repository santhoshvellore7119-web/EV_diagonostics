import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface TimelineState {
  currentTimeIndex: number; // index in the frame buffer
  playbackSpeed: number; // 1.0 = normal speed
  isPlaying: boolean;
  frameBufferLength: number;
}

const initialState: TimelineState = {
  currentTimeIndex: 0,
  playbackSpeed: 1.0,
  isPlaying: false,
  frameBufferLength: 0,
};

export const timelineSlice = createSlice({
  name: 'timeline',
  initialState,
  reducers: {
    setCurrentTimeIndex: (state, action: PayloadAction<number>) => {
      state.currentTimeIndex = action.payload;
    },
    setPlaybackSpeed: (state, action: PayloadAction<number>) => {
      state.playbackSpeed = action.payload;
    },
    setIsPlaying: (state, action: PayloadAction<boolean>) => {
      state.isPlaying = action.payload;
    },
    setFrameBufferLength: (state, action: PayloadAction<number>) => {
      state.frameBufferLength = action.payload;
    },
  },
});

export const { setCurrentTimeIndex, setPlaybackSpeed, setIsPlaying, setFrameBufferLength } = timelineSlice.actions;

export default timelineSlice.reducer;