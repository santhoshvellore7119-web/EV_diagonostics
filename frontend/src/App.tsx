import React, { useState } from 'react';
import { useSelector } from 'react-redux';
import { RootState } from './store';
import LiveView from './components/views/LiveView';
import SimulinkView from './components/views/SimulinkView';
import ThreeDView from './components/views/ThreeDView';
import EISNyquistView from './components/views/EISNyquistView';
import AcousticCWIView from './components/views/AcousticCWIView';
import PackTopologyView from './components/views/PackTopologyView';
import ResearchDossierModal from './components/views/ResearchDossierModal';
import ControlPanel from './components/panels/ControlPanel';
import SOHChart from './components/charts/SOHChart';
import VoltageChart from './components/charts/VoltageChart';
import TemperatureChart from './components/charts/TemperatureChart';
import DegradationChart from './components/charts/DegradationChart';
import './App.css';

type ActiveTab = 'cockpit' | 'eis_nyquist' | 'acoustic_cwi' | 'pack_matrix' | 'three_d' | 'simulink';

function App() {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const mode = useSelector((state: RootState) => state.mode.current);
  const [activeTab, setActiveTab] = useState<ActiveTab>('cockpit');
  const [isDossierOpen, setIsDossierOpen] = useState<boolean>(false);

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
      {/* Top Application Bar */}
      <header className="app-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #0284c7 0%, #00f0ff 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px rgba(0, 240, 255, 0.4)'
          }}>
            <span style={{ fontSize: '1.2rem' }}>⚡</span>
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#ffffff' }}>
              AETHER-BMS <span style={{ color: '#00f0ff', fontWeight: 400, fontSize: '0.82rem' }}>| Research & Operando Diagnostics</span>
            </h1>
            <div className="app-subtitle" style={{ fontSize: '0.73rem', color: '#94a3b8' }}>
              Multi-Modal Acoustic-Electro-Thermal Waveform Fusion & Active ZVS Flyback Rebalancing
            </div>
          </div>
        </div>

        {/* Global Action & Nav Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {/* Tab Selection Switcher */}
          <div style={{
            display: 'flex',
            gap: '4px',
            background: '#07090e',
            padding: '4px',
            borderRadius: '8px',
            border: '1px solid #1e293b'
          }}>
            <button
              onClick={() => setActiveTab('cockpit')}
              className={`nav-pill ${activeTab === 'cockpit' ? 'active' : ''}`}
            >
              🛰️ Cockpit
            </button>
            <button
              onClick={() => setActiveTab('eis_nyquist')}
              className={`nav-pill ${activeTab === 'eis_nyquist' ? 'active' : ''}`}
            >
              🔬 EIS & DRT
            </button>
            <button
              onClick={() => setActiveTab('acoustic_cwi')}
              className={`nav-pill ${activeTab === 'acoustic_cwi' ? 'active' : ''}`}
            >
              🔊 Acoustic CWI
            </button>
            <button
              onClick={() => setActiveTab('pack_matrix')}
              className={`nav-pill ${activeTab === 'pack_matrix' ? 'active' : ''}`}
            >
              🔋 8S Pack Matrix
            </button>
            <button
              onClick={() => setActiveTab('three_d')}
              className={`nav-pill ${activeTab === 'three_d' ? 'active' : ''}`}
            >
              🎮 3D Digital Twin
            </button>
            <button
              onClick={() => setActiveTab('simulink')}
              className={`nav-pill ${activeTab === 'simulink' ? 'active' : ''}`}
            >
              🚀 Simulink
            </button>
          </div>

          {/* Research Report Button */}
          <button
            onClick={() => setIsDossierOpen(true)}
            style={{
              padding: '6px 12px',
              background: 'linear-gradient(135deg, rgba(168, 85, 247, 0.25) 0%, rgba(2, 132, 199, 0.25) 100%)',
              border: '1px solid #a855f7',
              borderRadius: '6px',
              color: '#c084fc',
              fontSize: '0.76rem',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            📄 Scientific Dossier
          </button>

          {/* System status badge */}
          <div className="header-status-badge">
            <div className="connection-status">
              <span className="live-dot"></span>
              <span>10 Hz TELEMETRY</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="main-container">
        {/* Left Telemetry Control Panel */}
        <aside className="sidebar">
          <ControlPanel />
        </aside>

        {/* Center / Right Content Panel */}
        <main className="main-content">
          {activeTab === 'cockpit' && (
            <>
              {/* Always-visible ML & Rebalancing Panels */}
              <div className="always-visible-panels">
                <div className="ml-fusion-panel">
                  <h2>ML Multi-Branch Fusion Panel</h2>
                  <div className="panel-content">
                    <SOHChart />
                    <VoltageChart />
                    <TemperatureChart />
                    <DegradationChart />
                  </div>
                </div>

                <div className="rebalancing-panel">
                  <h2>Active ZVS Rebalancing Stage</h2>
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
                          <p><strong>Target Shuttling Current:</strong> {frame.rebalancing_powerStage_targetCurrent?.toFixed(2)} A</p>

                          {/* Online 2-RC RLS & Attention Strip */}
                          <div style={{
                            marginTop: '10px',
                            padding: '10px 12px',
                            background: 'rgba(2, 132, 199, 0.08)',
                            border: '1px solid rgba(56, 189, 248, 0.25)',
                            borderRadius: '8px',
                            fontSize: '0.76rem',
                            lineHeight: '1.55',
                            color: '#cbd5e1'
                          }}>
                            <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '4px', fontSize: '0.80rem' }}>
                              🧮 Operando 2-RC RLS Observer & Degradation Physics
                            </div>
                            <div>
                              • <strong>Impedance:</strong>{' '}
                              R₀={((frame.ecm_r0_est ?? frame.electrical_resistance ?? 0.028) * 1000).toFixed(1)} mΩ |{' '}
                              R₁={((frame.ecm_r1_est ?? 0.015) * 1000).toFixed(1)} mΩ |{' '}
                              R₂={((frame.ecm_r2_est ?? 0.012) * 1000).toFixed(1)} mΩ
                            </div>
                            <div>
                              • <strong>Cross-Modal Attention:</strong>{' '}
                              Elec {((frame.modality_attention_electrical ?? 0.45) * 100).toFixed(0)}% |{' '}
                              US {((frame.modality_attention_ultrasonic ?? 0.39) * 100).toFixed(0)}% |{' '}
                              Therm {((frame.modality_attention_thermal ?? 0.16) * 100).toFixed(0)}%
                            </div>
                          </div>

                          {/* Soft-Switching Efficiency Metric */}
                          {isBalancing && (
                            <div style={{
                              marginTop: '12px',
                              padding: '10px 14px',
                              background: 'rgba(16, 185, 129, 0.08)',
                              border: '1px solid rgba(16, 185, 129, 0.3)',
                              borderRadius: '8px'
                            }}>
                              <div style={{ fontWeight: 700, color: '#10b981', marginBottom: '4px', fontSize: '0.85rem' }}>
                                ⚡ ZVS Flyback Efficiency: {zvsEff.toFixed(1)}%
                              </div>
                              <div style={{ fontSize: '0.78rem', color: '#cbd5e1' }}>
                                Shuttled Power: <strong>{pTrans.toFixed(2)} W</strong> | Losses (Cond+Sw+Core): <strong>{pLossTotal.toFixed(3)} W</strong>
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

              {/* Three Synchronized Telemetry Views */}
              <div className="views-container">
                <LiveView />
                <SimulinkView />
                <ThreeDView />
              </div>
            </>
          )}

          {activeTab === 'eis_nyquist' && <EISNyquistView />}
          {activeTab === 'acoustic_cwi' && <AcousticCWIView />}
          {activeTab === 'pack_matrix' && <PackTopologyView />}
          {activeTab === 'three_d' && <ThreeDView />}
          {activeTab === 'simulink' && <SimulinkView />}
        </main>
      </div>

      {/* Research Dossier Modal */}
      <ResearchDossierModal
        isOpen={isDossierOpen}
        onClose={() => setIsDossierOpen(false)}
      />

      {/* Footer */}
      <footer className="app-footer">
        <p>AETHER-BMS Unified Multi-Modal Research Platform • Deep Operando Diagnostics & Soft-Switching Active Balancer</p>
        <p>
          Mode: {mode.toUpperCase()} | Origin: {frame?.data_origin || '3D-SIM'} | Frame: {frame?.frameId ? frame.frameId.substring(0, 8) : 'None'} |
          Timestamp: {frame ? new Date(frame.timestamp * 1000).toLocaleTimeString() : 'None'}
        </p>
      </footer>
    </div>
  );
}

export default App;