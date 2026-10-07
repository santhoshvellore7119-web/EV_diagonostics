import React from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';

const SimulinkView: React.FC = () => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const mode = useSelector((state: RootState) => state.mode.current);

  // Only render when in simulink mode
  if (mode !== 'simulink') {
    return null;
  }

  if (!frame) {
    return (
      <div className="view-container simulink-view">
        <div className="view-placeholder">
          <h2>Simulink Simulation</h2>
          <p>Waiting for Simulink FMU data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="view-container simulink-view">
      <div className="view-header">
        <h2>Simulink Simulation</h2>
        <div className="view-status">
          <span className="status-indicator simulink">● Simulink</span>
          <span className="frame-id">Frame: {frame.frameId}</span>
          <span className="timestamp">
            {new Date(frame.timestamp * 1000).toLocaleTimeString()}
          </span>
        </div>
      </div>

      <div style={{
        margin: '12px 0 16px 0',
        padding: '12px 16px',
        background: 'rgba(2, 132, 199, 0.12)',
        border: '1px solid rgba(56, 189, 248, 0.4)',
        borderRadius: '8px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '10px'
      }}>
        <div>
          <div style={{ fontWeight: 700, color: '#38bdf8', fontSize: '0.9rem' }}>
            ⚡ Direct Simulink & MATLAB Digital Twin Link
          </div>
          <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '2px' }}>
            Model: <code>ev_cell_digital_twin.slx</code> (2-RC ECM + Acoustic Wave + Lumped Thermal)
          </div>
        </div>
        <button
          style={{
            padding: '8px 16px',
            background: '#0284c7',
            color: '#ffffff',
            border: 'none',
            borderRadius: '6px',
            fontWeight: 700,
            fontSize: '0.82rem',
            cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(2, 132, 199, 0.4)'
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
          🚀 Open in MATLAB / Simulink
        </button>
      </div>

      <div className="view-content">
        <div className="data-section electrical">
          <h3>Electrical</h3>
          <div className="data-grid">
            <div className="data-item">
              <label>Voltage:</label>
              <span>{frame.electrical_voltage?.toFixed(3)} V</span>
            </div>
            <div className="data-item">
              <label>Current:</label>
              <span>{frame.electrical_current?.toFixed(3)} A</span>
            </div>
            <div className="data-item">
              <label>Power:</label>
              <span>{frame.electrical_power?.toFixed(2)} W</span>
            </div>
            <div className="data-item">
              <label>Resistance:</label>
              <span>{frame.electrical_resistance?.toFixed(4)} Ω</span>
            </div>
          </div>
        </div>

        <div className="data-section ultrasonic">
          <h3>Ultrasonic</h3>
          <div className="data-grid">
            <div className="data-item">
              <label>Time of Flight:</label>
              <span>{frame.ultrasonic_timeOfFlight?.toFixed(2)} μs</span>
            </div>
            <div className="data-item">
              <label>Amplitude:</label>
              <span>{frame.ultrasonic_amplitude?.toFixed(3)} V</span>
            </div>
            <div className="data-item">
              <label>Phase Shift:</label>
              <span>{frame.ultrasonic_phaseShift?.toFixed(3)}°</span>
            </div>
            <div className="data-item">
              <label>Speed of Sound:</label>
              <span>{frame.ultrasonic_speedOfSound?.toFixed(0)} m/s</span>
            </div>
          </div>
        </div>

        <div className="data-section thermal">
          <h3>Thermal</h3>
          <div className="data-grid">
            <div className="data-item">
              <label>Temperature:</label>
              <span>{frame.thermal_temperature?.toFixed(2)}°C</span>
            </div>
            <div className="data-item">
              <label>Temperature Gradient:</label>
              <span>{frame.thermal_tempGradient?.toFixed(4)}°C/mm</span>
            </div>
            <div className="data-item">
              <label>Heat Flux:</label>
              <span>{frame.thermal_heatFlux?.toFixed(2)} W/m²</span>
            </div>
          </div>
        </div>

        <div className="data-section ml-results">
          <h3>Machine Learning Results</h3>
          <div className="data-grid">
            <div className="data-item">
              <label>State of Health:</label>
              <span className="soh-value">
                {frame.stateOfHealth_value?.toFixed(1)}%
              </span>
              <span className="soh-confidence">
                [{frame.stateOfHealth_confidenceInterval_lower?.toFixed(1)}-
                {frame.stateOfHealth_confidenceInterval_upper?.toFixed(1)}%]
              </span>
            </div>
            <div className="data-item">
              <label>Degradation Mode:</label>
              <span className="degradation-mode">
                {frame.degradation_mode?.replace(/_/g, ' ').toUpperCase()}
              </span>
            </div>
            <div className="data-item">
              <label>Probability:</label>
              <span>{(frame.degradation_probability * 100).toFixed(1)}%</span>
            </div>
            <div className="data-item">
              <label>Entropy:</label>
              <span>{frame.degradation_entropy?.toFixed(3)}</span>
            </div>
          </div>
        </div>

        <div className="data-section rebalancing">
          <h3>Rebalancing Status</h3>
          <div className="data-grid">
            <div className="data-item">
              <label>State:</label>
              <span>{frame.rebalancing_state?.replace(/_/g, ' ').toUpperCase()}</span>
            </div>
            <div className="data-item">
              <label>Action:</label>
              <span>{frame.rebalancing_selectedAction?.replace(/_/g, ' ').toUpperCase()}</span>
            </div>
            <div className="data-item">
              <label>Reason:</label>
              <span>{frame.rebalancing_actionReason}</span>
            </div>
            <div className="data-item">
              <label>Target Voltage:</label>
              <span>{frame.rebalancing_powerStage_targetVoltage?.toFixed(2)} V</span>
            </div>
            <div className="data-item">
              <label>Target Current:</label>
              <span>{frame.rebalancing_powerStage_targetCurrent?.toFixed(2)} A</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SimulinkView;