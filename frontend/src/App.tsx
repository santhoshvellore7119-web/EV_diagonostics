import React from 'react';
import { useSelector } from 'react-redux';
import { RootState } from './store';
import LiveView from './components/views/LiveView';
import SimulinkView from './components/views/SimulinkView';
import ThreeDView from './components/views/ThreeDView';
import ControlPanel from './components/panels/ControlPanel';
import SOHChart from './components/charts/SOHChart';
import VoltageChart from './components/charts/VoltageChart';
import TemperatureChart from './components/charts/TemperatureChart';
import DegradationChart from './components/charts/DegradationChart';
import './App.css';

function App() {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const mode = useSelector((state: RootState) => state.mode.current);

  const iBal = frame?.rebalancing_powerStage_actualCurrent || (frame?.rebalancing_active ? 1.5 : 0.0);
  const isLockout = frame?.rebalancing_state?.toLowerCase().includes('lockout') || frame?.rebalancing_state?.toLowerCase().includes('isolated');
  const isBalancing = (iBal > 0.05 || frame?.rebalancing_active) && !isLockout;

  // Real-time loss breakdown estimation when active
  const pTrans = Math.max(0.0, iBal * (frame?.electrical_voltage || 3.60));
  const pCond = Math.max(0.0, (iBal ** 2) * 0.0095);
  const pSw = Math.max(0.0, iBal * 0.012);
  const pCore = isBalancing ? 0.038 : 0.0;
  const pLossTotal = pCond + pSw + pCore;
  const zvsEff = isBalancing ? (frame?.zvs_efficiency_pct || (pTrans > 0 ? ((pTrans / (pTrans + pLossTotal)) * 100.0) : 92.4)) : 0.0;

  return (
    <div className="App">
      <header className="app-header">
        <div>
          <h1>Unified Diagnostic Dashboard</h1>
          <div className="app-subtitle">
            Low-Cost Multi-Modal Diagnostic & Active Cell-Rebalancing System
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            style={{
              padding: '6px 12px',
              background: 'rgba(2, 132, 199, 0.25)',
              border: '1px solid #38bdf8',
              borderRadius: '6px',
              color: '#38bdf8',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
            onClick={async () => {
              try {
                const res = await fetch('http://localhost:8000/api/simulink/open', { method: 'POST' });
                const data = await res.json();
                if (data.launched_locally) {
                  alert('Launching MATLAB Simulink (ev_cell_digital_twin.slx)...');
                } else {
                  navigator.clipboard?.writeText(data.matlab_command || "run('matlab_simulink_demo/launch_simulink.m');");
                  alert('In MATLAB, run:\n' + (data.matlab_command || "run('matlab_simulink_demo/launch_simulink.m');"));
                }
              } catch (e) {
                alert("Run in MATLAB: run('matlab_simulink_demo/launch_simulink.m');");
              }
            }}
          >
            🚀 Simulink (MATLAB)
          </button>

          <button
            style={{
              padding: '6px 12px',
              background: 'rgba(168, 85, 247, 0.25)',
              border: '1px solid #c084fc',
              borderRadius: '6px',
              color: '#c084fc',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
            onClick={async () => {
              try {
                const res = await fetch('http://localhost:8000/api/matlab/ml_demo/open', { method: 'POST' });
                const data = await res.json();
                if (data.launched_locally) {
                  alert('Launching MATLAB Multi-Modal ML Fusion Demonstrator (run_matlab_ml_demo.m)...');
                } else {
                  navigator.clipboard?.writeText(data.matlab_command || "run('run_matlab_ml_demo.m');");
                  alert('In MATLAB, run:\n' + (data.matlab_command || "run('run_matlab_ml_demo.m');"));
                }
              } catch (e) {
                alert("Run in MATLAB Command Window:\nrun('run_matlab_ml_demo.m');");
              }
            }}
          >
            🧠 ML Model (MATLAB)
          </button>

          <button
            style={{
              padding: '6px 12px',
              background: 'rgba(16, 185, 129, 0.25)',
              border: '1px solid #34d399',
              borderRadius: '6px',
              color: '#34d399',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
            onClick={() => window.open('http://localhost:8000/gazebo', '_blank')}
          >
            🌐 Gazebo 3D Studio
          </button>

          <div className="header-status-badge">
            <div className="connection-status">
              <span className="live-dot"></span>
              <span>SYSTEM ACTIVE: 10 Hz</span>
            </div>
          </div>
        </div>
      </header>

      <div className="main-container">
        {/* Control Panel */}
        <aside className="sidebar">
          <ControlPanel />
        </aside>

        {/* Main Content */}
        <main className="main-content">
          {/* Always-visible Panels */}
          <div className="always-visible-panels">
            <div className="ml-fusion-panel">
              <h2>ML Fusion Panel</h2>
              <div className="panel-content">
                <SOHChart />
                <VoltageChart />
                <TemperatureChart />
                <DegradationChart />
              </div>
            </div>

            <div className="rebalancing-panel">
              <h2>Active Rebalancing Panel</h2>
              <div className="panel-content">
                <div className="rebalancing-status">
                  {frame ? (
                    <>
                      <div style={{ marginBottom: '8px' }}>
                        <strong>Supervisor State: </strong>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          background: isLockout ? '#ef4444' : isBalancing ? '#10b981' : '#64748b',
                          color: '#ffffff'
                        }}>
                          {isLockout ? 'CRITICAL LOCKOUT (ISOLATED)' : isBalancing ? 'ACTIVE BALANCING (ZVS)' : 'MONITORING (NOMINAL)'}
                        </span>
                      </div>
                      <p><strong>Selected Action:</strong> {frame.rebalancing_selectedAction?.toUpperCase() || 'NONE'}</p>
                      <p><strong>Decision Rationale:</strong> {frame.rebalancing_actionReason || 'Cell state within normal tolerances'}</p>
                      <p><strong>Target Voltage:</strong> {frame.rebalancing_powerStage_targetVoltage?.toFixed(2)} V</p>
                      <p><strong>Target Shuttling Current:</strong> {frame.rebalancing_powerStage_targetCurrent?.toFixed(2)} A</p>

                      {/* Conditional Efficiency & Power Loss Breakdown (Active Mode Only) */}
                      {isBalancing && (
                        <div style={{
                          marginTop: '12px',
                          padding: '10px 14px',
                          background: 'rgba(16, 185, 129, 0.08)',
                          border: '1px solid rgba(16, 185, 129, 0.3)',
                          borderRadius: '8px'
                        }}>
                          <div style={{ fontWeight: 700, color: '#10b981', marginBottom: '6px', fontSize: '0.85rem' }}>
                            ⚡ ZVS Active Stage Efficiency: {zvsEff.toFixed(1)}%
                          </div>
                          <div style={{ fontSize: '0.78rem', lineHeight: '1.5', color: '#cbd5e1' }}>
                            <div>• Conduction Loss (MOSFET + DCR): <strong>{pCond.toFixed(3)} W</strong></div>
                            <div>• Soft-Switching Loss (ZVS 85% reduced): <strong>{pSw.toFixed(3)} W</strong></div>
                            <div>• Inductor Core Loss (Ferrite SER2918H): <strong>{pCore.toFixed(3)} W</strong></div>
                            <div>• Net Shuttling Power Transferred: <strong>{pTrans.toFixed(2)} W</strong></div>
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <p>Awaiting live telemetry stream...</p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Three Synchronized Views */}
          <div className="views-container">
            <LiveView />
            <SimulinkView />
            <ThreeDView />
          </div>
        </main>
      </div>

      <footer className="app-footer">
        <p>EV Battery Diagnostic System - Research Grade Dashboard</p>
        <p>
          Mode: {mode.toUpperCase()} | Origin: {frame?.data_origin || '3D-SIM'} | Frame: {frame?.frameId ? frame.frameId.substring(0, 8) : 'None'} |
          Timestamp: {frame ? new Date(frame.timestamp * 1000).toLocaleTimeString() : 'None'}
        </p>
      </footer>
    </div>
  );
}

export default App;