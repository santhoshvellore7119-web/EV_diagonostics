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

  return (
    <div className="App">
      <header className="app-header">
        <div>
          <h1>Unified Diagnostic Dashboard</h1>
          <div className="app-subtitle">
            Low-Cost Multi-Modal Diagnostic & Active Cell-Rebalancing System
          </div>
        </div>
        <div className="header-status-badge">
          <div className="connection-status">
            <span className="live-dot"></span>
            <span>SYSTEM ACTIVE: 10 Hz</span>
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
                {/* Rebalancing details will be shown in the views */}
                <div className="rebalancing-status">
                  {frame && (
                    <>
                      <p><strong>State:</strong> {frame.rebalancing_state}</p>
                      <p><strong>Selected Action:</strong> {frame.rebalancing_selectedAction}</p>
                      <p><strong>Reason:</strong> {frame.rebalancing_actionReason}</p>
                      <p><strong>Target Voltage:</strong> {frame.rebalancing_powerStage_targetVoltage?.toFixed(2)} V</p>
                      <p><strong>Target Current:</strong> {frame.rebalancing_powerStage_targetCurrent?.toFixed(2)} A</p>
                    </>
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
          Mode: {mode.toUpperCase()} | Frame: {frame?.frameId || 'None'} |
          Timestamp: {frame ? new Date(frame.timestamp * 1000).toLocaleString() : 'None'}
        </p>
      </footer>
    </div>
  );
}

export default App;