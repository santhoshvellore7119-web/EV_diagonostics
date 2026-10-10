import React, { useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../../store';
import { setMode } from '../../store/modeSlice';
import {
  setPlaybackSpeed,
  setIsPlaying,
  setCurrentTimeIndex
} from '../../store/timelineSlice';
import {
  setIsPaused,
  setScrubIndex
} from '../../store/diagnosticFrameSlice';

const ControlPanel: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const mode = useSelector((state: RootState) => state.mode.current);
  const { playbackSpeed } = useSelector((state: RootState) => state.timeline);
  const { history, isPaused, scrubIndex } = useSelector((state: RootState) => state.diagnosticFrame);

  // Dynamic Multi-Chemistry Battery Simulation Parameters
  const [chemistry, setChemistry] = useState<string>('nmc_811');
  const [formFactor, setFormFactor] = useState<string>('21700_cylindrical');
  const [degradationMode, setDegradationMode] = useState<string>('healthy');
  const [soc, setSoc] = useState<number>(65);
  const [ambientTemp, setAmbientTemp] = useState<number>(25);
  const [loadCurrentC, setLoadCurrentC] = useState<number>(0.5);
  const [cycleCount, setCycleCount] = useState<number>(50);
  const [isMachineRunning, setIsMachineRunning] = useState<boolean>(false);

  const historyLength = history.length;
  const currentScrub = scrubIndex !== null ? scrubIndex : Math.max(0, historyLength - 1);

  const handleModeChange = (newMode: 'live' | 'simulink' | '3d' | 'gazebo') => {
    dispatch(setMode(newMode));
    fetch(`http://localhost:8000/api/mode/set?mode=${newMode}`, { method: 'POST' }).catch(() => {});
  };

  const handlePlayPause = () => {
    const nextPaused = !isPaused;
    dispatch(setIsPaused(nextPaused));
    dispatch(setIsPlaying(!nextPaused));
    if (!nextPaused) {
      dispatch(setScrubIndex(null));
    }
  };

  const handleSpeedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const speed = parseFloat(e.target.value);
    dispatch(setPlaybackSpeed(speed));
  };

  const handleTimeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const timeIndex = parseInt(e.target.value, 10);
    dispatch(setIsPaused(true));
    dispatch(setIsPlaying(false));
    dispatch(setScrubIndex(timeIndex));
    dispatch(setCurrentTimeIndex(timeIndex));
  };

  // Real-time parameter sync to backend dynamic physics engine
  const updateBatteryPhysics = async (updated: Record<string, any>) => {
    try {
      await fetch('http://localhost:8000/api/battery/parameters/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      });
    } catch (e) {
      // Backend maybe offline
    }
  };

  const handleChemistryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setChemistry(val);
    updateBatteryPhysics({ chemistry: val });
  };

  const handleFormFactorChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setFormFactor(val);
    updateBatteryPhysics({ form_factor: val });
  };

  const handleDegradationChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setDegradationMode(val);
    updateBatteryPhysics({ degradation_mode: val });
  };

  const handleSocChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setSoc(val);
    updateBatteryPhysics({ soc: val / 100.0 });
  };

  const handleTempChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setAmbientTemp(val);
    updateBatteryPhysics({ ambient_temp_c: val });
  };

  const handleLoadChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setLoadCurrentC(val);
    updateBatteryPhysics({ load_current_c: val });
  };

  const handleCyclesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value, 10);
    setCycleCount(val);
    updateBatteryPhysics({ cycle_count: val });
  };

  const handleTriggerMachineCycle = async () => {
    setIsMachineRunning(true);
    try {
      await fetch(`http://localhost:8000/api/machine/cycle/start?degradation_mode=${degradationMode}`, { method: 'POST' });
    } catch (e) {
      // Ignore
    } finally {
      setTimeout(() => setIsMachineRunning(false), 8000);
    }
  };

  return (
    <div className="control-panel">
      {/* 1. View Mode Selection */}
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

      {/* 2. Dynamic Multi-Chemistry Battery Configuration (Simulation Modes) */}
      {mode !== 'live' && (
        <div className="control-section" style={{ borderLeft: '3px solid #38bdf8', paddingLeft: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <h3 style={{ margin: 0, color: '#38bdf8' }}>🔋 Dynamic Battery Physics</h3>
            <span style={{ fontSize: '0.65rem', background: '#0284c7', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontWeight: 700 }}>
              CONTINUOUS ODE
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem' }}>
            {/* Chemistry Dropdown */}
            <div>
              <label style={{ display: 'block', color: '#94a3b8', marginBottom: '2px' }}>Chemistry Profile:</label>
              <select
                value={chemistry}
                onChange={handleChemistryChange}
                style={{
                  width: '100%',
                  background: '#0f172a',
                  color: '#f8fafc',
                  border: '1px solid #334155',
                  borderRadius: '4px',
                  padding: '5px 8px',
                  fontSize: '0.78rem'
                }}
              >
                <option value="nmc_811">NMC 811 (High Energy Density, 3.65V)</option>
                <option value="lfp">LFP - LiFePO4 (Thermal Stability, 3.20V)</option>
                <option value="nca">NCA - LiNiCoAlO2 (High Capacity, 3.60V)</option>
                <option value="lto">LTO - Titanate (Ultra-Fast 20k Cycle, 2.30V)</option>
                <option value="solid_state">Solid-State Ceramic Li-Metal (Next-Gen 3.80V)</option>
              </select>
            </div>

            {/* Form Factor Dropdown */}
            <div>
              <label style={{ display: 'block', color: '#94a3b8', marginBottom: '2px' }}>Form Factor:</label>
              <select
                value={formFactor}
                onChange={handleFormFactorChange}
                style={{
                  width: '100%',
                  background: '#0f172a',
                  color: '#f8fafc',
                  border: '1px solid #334155',
                  borderRadius: '4px',
                  padding: '5px 8px',
                  fontSize: '0.78rem'
                }}
              >
                <option value="18650_cylindrical">18650 Cylindrical (18mm × 65mm)</option>
                <option value="21700_cylindrical">21700 Cylindrical (21mm × 70mm)</option>
                <option value="prismatic_100ah">Prismatic 100Ah Heavy Duty Block</option>
                <option value="pouch_60ah">Pouch 60Ah High-Surface Cell</option>
              </select>
            </div>

            {/* Degradation State Dropdown */}
            <div>
              <label style={{ display: 'block', color: '#94a3b8', marginBottom: '2px' }}>Degradation Mode:</label>
              <select
                value={degradationMode}
                onChange={handleDegradationChange}
                style={{
                  width: '100%',
                  background: '#0f172a',
                  color: '#f8fafc',
                  border: '1px solid #334155',
                  borderRadius: '4px',
                  padding: '5px 8px',
                  fontSize: '0.78rem'
                }}
              >
                <option value="healthy">Healthy Baseline (Nominal SEI)</option>
                <option value="li_plating">Lithium Plating (Acoustic Velocity Drop)</option>
                <option value="active_material_loss">Active Material Loss (Resistance Growth)</option>
                <option value="electrolyte_decomposition">Electrolyte Decomposition (Gas Pockets)</option>
                <option value="gas_generation">Gas Generation (Severe Acoustic Attenuation)</option>
                <option value="internal_short">Internal Micro-Short (Thermal Hotspot)</option>
              </select>
            </div>

            {/* SOC Slider */}
            <div style={{ marginTop: '2px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: '0.75rem' }}>
                <span>State of Charge (SOC):</span>
                <span style={{ color: '#38bdf8', fontWeight: 700 }}>{soc}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="1"
                value={soc}
                onChange={handleSocChange}
                style={{ width: '100%', accentColor: '#38bdf8' }}
              />
            </div>

            {/* Ambient Temperature Slider */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: '0.75rem' }}>
                <span>Operating Temperature:</span>
                <span style={{ color: '#f59e0b', fontWeight: 700 }}>{ambientTemp}°C</span>
              </div>
              <input
                type="range"
                min="-20"
                max="60"
                step="1"
                value={ambientTemp}
                onChange={handleTempChange}
                style={{ width: '100%', accentColor: '#f59e0b' }}
              />
            </div>

            {/* Load Current C-rate Slider */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: '0.75rem' }}>
                <span>C-Rate Load Current:</span>
                <span style={{ color: loadCurrentC < 0 ? '#10b981' : '#a855f7', fontWeight: 700 }}>
                  {loadCurrentC > 0 ? `+${loadCurrentC.toFixed(1)}C (Discharge)` : `${loadCurrentC.toFixed(1)}C (Charge)`}
                </span>
              </div>
              <input
                type="range"
                min="-5.0"
                max="5.0"
                step="0.1"
                value={loadCurrentC}
                onChange={handleLoadChange}
                style={{ width: '100%', accentColor: '#a855f7' }}
              />
            </div>

            {/* Cycle Count Slider */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: '0.75rem' }}>
                <span>Aging History (Cycles):</span>
                <span style={{ color: '#ef4444', fontWeight: 700 }}>{cycleCount} cycles</span>
              </div>
              <input
                type="range"
                min="0"
                max="3000"
                step="10"
                value={cycleCount}
                onChange={handleCyclesChange}
                style={{ width: '100%', accentColor: '#ef4444' }}
              />
            </div>
          </div>
        </div>
      )}

      {/* 3. Automated 6-Stage Robotic Diagnostic Machine */}
      <div className="control-section">
        <h3>🤖 Automated Test Machine</h3>
        <button
          onClick={handleTriggerMachineCycle}
          disabled={isMachineRunning}
          style={{
            width: '100%',
            padding: '8px 12px',
            background: isMachineRunning ? '#475569' : '#8b5cf6',
            color: '#ffffff',
            border: 'none',
            borderRadius: '6px',
            fontWeight: 700,
            fontSize: '0.8rem',
            cursor: isMachineRunning ? 'wait' : 'pointer'
          }}
        >
          {isMachineRunning ? '⚙ Running 6-Stage Diagnostic Cycle...' : '▶ Start Automated Machine Cycle'}
        </button>
      </div>

      {/* 4. Playback & Ring Buffer Controls */}
      <div className="control-section">
        <h3>Playback & Ring Buffer Controls</h3>
        <div className="playback-controls">
          <button
            onClick={handlePlayPause}
            className={`play-pause-button ${isPaused ? 'paused' : 'playing'}`}
            style={{
              padding: '6px 14px',
              fontWeight: 600,
              background: isPaused ? '#f59e0b' : '#10b981',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              width: '100%'
            }}
          >
            {isPaused ? '▶ Resume Live' : '❚❚ Pause Buffer'}
          </button>

          <div className="speed-control" style={{ marginTop: '8px' }}>
            <label>Rate: </label>
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

          <div className="timeline-control" style={{ marginTop: '8px' }}>
            <label>Frame Buffer: </label>
            <input
              type="range"
              min="0"
              max={Math.max(0, historyLength - 1)}
              value={currentScrub}
              onChange={handleTimeChange}
              disabled={historyLength <= 1}
            />
            <span>{currentScrub + (historyLength > 0 ? 1 : 0)} / {Math.max(1, historyLength)}</span>
          </div>
        </div>
      </div>

      {/* 5. Rebalancing Controls */}
      <div className="control-section">
        <h3>Active Power Stage Controls</h3>
        <div className="rebalancing-controls">
          <button
            className="trigger-rebalance"
            onClick={() => {
              fetch('http://localhost:8000/api/rebalance/trigger', { method: 'POST' }).catch(() => {});
            }}
          >
            Trigger Rebalance
          </button>
          <button
            className="reset-system"
            onClick={() => {
              fetch('http://localhost:8000/api/system/reset', { method: 'POST' }).catch(() => {});
            }}
          >
            Reset System
          </button>
        </div>
      </div>

      {/* 6. External Digital Twin & MATLAB Demonstrators */}
      <div className="control-section">
        <h3>🚀 MATLAB & External Twins</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
          <button
            style={{
              padding: '8px 12px',
              background: '#0284c7',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 600,
              fontSize: '0.8rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px'
            }}
            onClick={async () => {
              try {
                const res = await fetch('http://localhost:8000/api/simulink/open', { method: 'POST' });
                const data = await res.json();
                if (data.launched_locally) {
                  alert('Launching MATLAB & Simulink model (ev_cell_digital_twin.slx)...');
                } else {
                  navigator.clipboard?.writeText(data.matlab_command || "run('matlab_simulink_demo/launch_simulink.m');");
                  alert('MATLAB launch command copied to clipboard!\nIn MATLAB Command Window run:\n' + (data.matlab_command || "run('matlab_simulink_demo/launch_simulink.m');"));
                }
              } catch (e) {
                alert("To open in MATLAB, run in MATLAB Command Window:\nrun('matlab_simulink_demo/launch_simulink.m');");
              }
            }}
          >
            🚀 Open Simulink in MATLAB
          </button>

          <button
            style={{
              padding: '8px 12px',
              background: '#7c3aed',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 600,
              fontSize: '0.8rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px'
            }}
            onClick={async () => {
              try {
                const res = await fetch('http://localhost:8000/api/matlab/ml_demo/open', { method: 'POST' });
                const data = await res.json();
                if (data.launched_locally) {
                  alert('Launching MATLAB Multi-Modal ML Fusion Demonstrator...');
                } else {
                  navigator.clipboard?.writeText(data.matlab_command || "run('run_matlab_ml_demo.m');");
                  alert('MATLAB ML Demo command copied to clipboard!\nIn MATLAB Command Window run:\n' + (data.matlab_command || "run('run_matlab_ml_demo.m');"));
                }
              } catch (e) {
                alert("To run in MATLAB, execute in MATLAB Command Window:\nrun('run_matlab_ml_demo.m');");
              }
            }}
          >
            🧠 Run ML Model in MATLAB
          </button>

          <button
            style={{
              padding: '8px 12px',
              background: '#059669',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 600,
              fontSize: '0.8rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px'
            }}
            onClick={() => {
              window.open('http://localhost:8000/gazebo', '_blank');
            }}
          >
            🌐 Open Gazebo 3D World
          </button>
        </div>
      </div>
    </div>
  );
};

export default ControlPanel;