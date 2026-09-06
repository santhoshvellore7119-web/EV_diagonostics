import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../../store';
import {
  setMode
} from '../../store/modeSlice';
import {
  setCurrentTimeIndex,
  setPlaybackSpeed,
  setIsPlaying
} from '../../store/timelineSlice';

const ControlPanel: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const mode = useSelector((state: RootState) => state.mode.current);
  const { isPlaying, playbackSpeed, currentTimeIndex, frameBufferLength } = useSelector(
    (state: RootState) => state.timeline
  );

  const handleModeChange = (newMode: 'live' | 'simulink' | '3d' | 'gazebo') => {
    dispatch(setMode(newMode));
    fetch(`http://localhost:8000/api/mode/set?mode=${newMode}`, { method: 'POST' }).catch(() => {
      // Keep running smoothly even if backend is starting up
    });
  };

  const handlePlayPause = () => {
    dispatch(setIsPlaying(!isPlaying));
  };

  const handleSpeedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const speed = parseFloat(e.target.value);
    dispatch(setPlaybackSpeed(speed));
  };

  const handleTimeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const timeIndex = parseInt(e.target.value, 10);
    dispatch(setCurrentTimeIndex(timeIndex));
  };

  return (
    <div className="control-panel">
      <div className="control-section">
        <h3>View Mode</h3>
        <div className="mode-group">
          <button
            className={`${mode === 'live' ? 'active' : ''}`}
            onClick={() => handleModeChange('live')}
          >
            Live Data
          </button>
          <button
            className={`${mode === 'simulink' ? 'active' : ''}`}
            onClick={() => handleModeChange('simulink')}
          >
            Simulink
          </button>
          <button
            className={`${mode === '3d' ? 'active' : ''}`}
            onClick={() => handleModeChange('3d')}
          >
            3D Simulation
          </button>
          <button
            className={`${mode === 'gazebo' ? 'active' : ''}`}
            onClick={() => handleModeChange('gazebo')}
          >
            Gazebo
          </button>
        </div>
      </div>

      <div className="control-section">
        <h3>Playback Controls</h3>
        <div className="playback-controls">
          <button
            onClick={handlePlayPause}
            className="play-pause-button"
          >
            {isPlaying ? '❚❚ Pause' : '▶ Play'}
          </button>

          <div className="speed-control">
            <label>Speed: </label>
            <input
              type="range"
              min="0.1"
              max="3.0"
              step="0.1"
              value={playbackSpeed}
              onChange={handleSpeedChange}
            />
            <span>{playbackSpeed.toFixed(1)}x</span>
          </div>

          <div className="timeline-control">
            <label>Time: </label>
            <input
              type="range"
              min="0"
              max={Math.max(0, frameBufferLength - 1)}
              value={currentTimeIndex}
              onChange={handleTimeChange}
            />
            <span>{currentTimeIndex} / {frameBufferLength}</span>
          </div>
        </div>
      </div>

      <div className="control-section">
        <h3>Rebalancing Controls</h3>
        <div className="rebalancing-controls">
          <button
            className="trigger-rebalance"
            onClick={() => {
              // In a real implementation, this would trigger a manual rebalancing cycle
              console.log('Manual rebalancing triggered');
              alert('Manual rebalancing triggered - would initiate recovery cycle');
            }}
          >
            Trigger Rebalancing
          </button>
          <button
            className="reset-system"
            onClick={() => {
              console.log('System reset requested');
              alert('System reset - would clear all states and restart');
            }}
          >
            Reset System
          </button>
        </div>
      </div>
    </div>
  );
};

export default ControlPanel;