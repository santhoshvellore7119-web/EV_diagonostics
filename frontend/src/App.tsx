import React, { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import { RootState } from './store';
import LiveView from './components/views/LiveView';
import SimulinkView from './components/views/SimulinkView';
import ThreeDView from './components/views/ThreeDView';
import EISNyquistView from './components/views/EISNyquistView';
import AcousticCWIView from './components/views/AcousticCWIView';
import PackTopologyView from './components/views/PackTopologyView';
import ResearchDossierModal from './components/views/ResearchDossierModal';
import AcousticTomographyPINNView from './components/views/AcousticTomographyPINNView';
import DriveCycleSPMeView from './components/views/DriveCycleSPMeView';
import ControlPanel from './components/panels/ControlPanel';
import SOHChart from './components/charts/SOHChart';
import VoltageChart from './components/charts/VoltageChart';
import TemperatureChart from './components/charts/TemperatureChart';
import DegradationChart from './components/charts/DegradationChart';
import './App.css';

type ActiveTab = 'cockpit' | 'eis_nyquist' | 'acoustic_cwi' | 'tomography_pinn' | 'spme_drive_cycles' | 'pack_matrix' | 'three_d' | 'simulink';

function App() {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const mode = useSelector((state: RootState) => state.mode.current);
  const [activeTab, setActiveTab] = useState<ActiveTab>(() => {
    const hash = window.location.hash.replace('#', '') as ActiveTab;
    const validTabs: ActiveTab[] = ['cockpit', 'eis_nyquist', 'acoustic_cwi', 'tomography_pinn', 'spme_drive_cycles', 'pack_matrix', 'three_d', 'simulink'];
    return validTabs.includes(hash) ? hash : 'cockpit';
  });

  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace('#', '') as ActiveTab;
      const validTabs: ActiveTab[] = ['cockpit', 'eis_nyquist', 'acoustic_cwi', 'tomography_pinn', 'spme_drive_cycles', 'pack_matrix', 'three_d', 'simulink'];
      if (validTabs.includes(hash)) setActiveTab(hash);
    };
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '4px',
            background: '#0284c7',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '1px solid #38bdf8'
          }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 900, color: '#ffffff', fontFamily: 'monospace' }}>AE</span>
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, letterSpacing: '0.04em', color: '#ffffff', textTransform: 'uppercase' }}>
              AETHER-BMS <span style={{ color: '#38bdf8', fontWeight: 600, fontSize: '0.78rem' }}>| OEM DIAGNOSTIC & CALIBRATION WORKSTATION</span>
            </h1>
            <div className="app-subtitle" style={{ fontSize: '0.68rem', color: '#64748b', fontFamily: 'monospace', letterSpacing: '0.02em' }}>
              ASIL-D COMPLIANT • OPERANDO EIS/DRT • ULTRASONIC NDT • ZVS QUASI-RESONANT BALANCING
            </div>
          </div>
        </div>

        {/* Global Action & Nav Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {/* Tab Selection Switcher */}
          <div style={{
            display: 'flex',
            gap: '2px',
            background: '#07090e',
            padding: '3px',
            borderRadius: '4px',
            border: '1px solid #1e293b'
          }}>
            <button
              onClick={() => setActiveTab('cockpit')}
              className={`nav-pill ${activeTab === 'cockpit' ? 'active' : ''}`}
            >
              OVERVIEW
            </button>
            <button
              onClick={() => setActiveTab('eis_nyquist')}
              className={`nav-pill ${activeTab === 'eis_nyquist' ? 'active' : ''}`}
            >
              EIS & DRT
            </button>
            <button
              onClick={() => setActiveTab('acoustic_cwi')}
              className={`nav-pill ${activeTab === 'acoustic_cwi' ? 'active' : ''}`}
            >
              ACOUSTIC CWI
            </button>
            <button
              onClick={() => setActiveTab('tomography_pinn')}
              className={`nav-pill ${activeTab === 'tomography_pinn' ? 'active' : ''}`}
            >
              TOMOGRAPHY & PINN
            </button>
            <button
              onClick={() => setActiveTab('spme_drive_cycles')}
              className={`nav-pill ${activeTab === 'spme_drive_cycles' ? 'active' : ''}`}
            >
              SPMe & DRIVE CYCLES
            </button>
            <button
              onClick={() => setActiveTab('pack_matrix')}
              className={`nav-pill ${activeTab === 'pack_matrix' ? 'active' : ''}`}
            >
              8S PACK MATRIX
            </button>
            <button
              onClick={() => setActiveTab('three_d')}
              className={`nav-pill ${activeTab === 'three_d' ? 'active' : ''}`}
            >
              3D SIMULATION
            </button>
            <button
              onClick={() => setActiveTab('simulink')}
              className={`nav-pill ${activeTab === 'simulink' ? 'active' : ''}`}
            >
              SIMULINK
            </button>
          </div>

          {/* Research Report Button */}
          <button
            onClick={() => setIsDossierOpen(true)}
            style={{
              padding: '6px 10px',
              background: '#07090e',
              border: '1px solid #334155',
              borderRadius: '3px',
              color: '#f8fafc',
              fontSize: '0.70rem',
              fontWeight: 700,
              fontFamily: 'monospace',
              letterSpacing: '0.04em',
              cursor: 'pointer'
            }}
          >
            TECHNICAL DOSSIER
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
                            <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '4px', fontSize: '0.74rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                              [OBSERVER] OPERANDO 2-RC THEVENIN & CROSS-MODAL ATTENTION
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
                              <div style={{ fontWeight: 700, color: '#10b981', marginBottom: '4px', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                [POWER STAGE] ZVS FLYBACK EFFICIENCY: {zvsEff.toFixed(1)}%
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
          {activeTab === 'tomography_pinn' && <AcousticTomographyPINNView />}
          {activeTab === 'spme_drive_cycles' && <DriveCycleSPMeView />}
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