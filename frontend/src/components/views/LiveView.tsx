import React, { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';

interface SerialPortInfo {
  port: string;
  description: string;
  hwid?: string;
}

const LiveView: React.FC = () => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const mode = useSelector((state: RootState) => state.mode.current);

  const [availablePorts, setAvailablePorts] = useState<SerialPortInfo[]>([]);
  const [selectedPort, setSelectedPort] = useState<string>('');
  const [baudrate, setBaudrate] = useState<number>(115200);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [connecting, setConnecting] = useState<boolean>(false);
  const [statusMsg, setStatusMsg] = useState<string>('');

  const fetchPortsAndStatus = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/firmware/status');
      if (res.ok) {
        const data = await res.json();
        setIsConnected(data.is_connected);
        if (data.port) setSelectedPort(data.port);
        if (data.baudrate) setBaudrate(data.baudrate);
        if (data.available_ports && data.available_ports.length > 0) {
          setAvailablePorts(data.available_ports);
          if (!selectedPort) setSelectedPort(data.available_ports[0].port);
        }
      }
    } catch (e) {
      // Backend maybe offline
    }
  };

  useEffect(() => {
    if (mode === 'live') {
      fetchPortsAndStatus();
      const interval = setInterval(fetchPortsAndStatus, 3000);
      return () => clearInterval(interval);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const handleScanPorts = async () => {
    try {
      setStatusMsg('Scanning physical COM / Serial ports...');
      const res = await fetch('http://localhost:8000/api/firmware/ports');
      const data = await res.json();
      setAvailablePorts(data.ports || []);
      if (data.ports && data.ports.length > 0) {
        setSelectedPort(data.ports[0].port);
        setStatusMsg(`Found ${data.ports.length} physical serial port(s).`);
      } else {
        setStatusMsg('No active serial hardware ports detected on host system.');
      }
    } catch (e) {
      setStatusMsg('Failed to scan COM ports: Backend connection error.');
    }
  };

  const handleConnect = async () => {
    if (!selectedPort) {
      setStatusMsg('Please select or specify a COM / Serial port.');
      return;
    }
    setConnecting(true);
    setStatusMsg(`Connecting to ${selectedPort} at ${baudrate} baud...`);
    try {
      const res = await fetch('http://localhost:8000/api/firmware/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ port: selectedPort, baudrate })
      });
      if (res.ok) {
        setIsConnected(true);
        setStatusMsg(`Connected successfully to ${selectedPort}!`);
      } else {
        const err = await res.json();
        setIsConnected(false);
        setStatusMsg(`Connection failed: ${err.detail || 'Port open error'}`);
      }
    } catch (e) {
      setIsConnected(false);
      setStatusMsg('Connection request failed: Backend unreachable.');
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await fetch('http://localhost:8000/api/firmware/disconnect', { method: 'POST' });
      setIsConnected(false);
      setStatusMsg('Serial port disconnected.');
    } catch (e) {
      setStatusMsg('Disconnect failed.');
    }
  };

  // Only render when in live mode
  if (mode !== 'live') {
    return null;
  }

  const isHardwareConnected = isConnected && frame && frame.data_origin === 'LIVE-HARDWARE';

  return (
    <div className="view-container live-view">
      <div className="view-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <h2>Physical Hardware Live Ingestion</h2>
          {isHardwareConnected ? (
            <span style={{ background: '#059669', color: '#fff', padding: '3px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 700 }}>
              ● LIVE HARDWARE LINK ACTIVE ({selectedPort} @ {baudrate})
            </span>
          ) : (
            <span style={{ background: '#dc2626', color: '#fff', padding: '3px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 700 }}>
              ⚠ HARDWARE DISCONNECTED
            </span>
          )}
        </div>
        {frame && (
          <div className="view-status">
            <span className="frame-id">Frame: {frame.frameId}</span>
            <span className="timestamp">
              {new Date(frame.timestamp * 1000).toLocaleTimeString()}
            </span>
          </div>
        )}
      </div>

      {/* Hardware Connection Control Bar */}
      <div style={{
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: '8px',
        padding: '12px 16px',
        marginBottom: '16px',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>COM Port:</span>
          {availablePorts.length > 0 ? (
            <select
              value={selectedPort}
              onChange={(e) => setSelectedPort(e.target.value)}
              disabled={isConnected}
              style={{
                background: '#0f172a',
                color: '#e2e8f0',
                border: '1px solid #475569',
                borderRadius: '4px',
                padding: '6px 10px',
                fontSize: '0.85rem'
              }}
            >
              {availablePorts.map((p) => (
                <option key={p.port} value={p.port}>
                  {p.port} ({p.description})
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              placeholder="e.g. COM3 or /dev/ttyUSB0"
              value={selectedPort}
              onChange={(e) => setSelectedPort(e.target.value)}
              disabled={isConnected}
              style={{
                background: '#0f172a',
                color: '#e2e8f0',
                border: '1px solid #475569',
                borderRadius: '4px',
                padding: '6px 10px',
                fontSize: '0.85rem',
                width: '180px'
              }}
            />
          )}

          <button
            onClick={handleScanPorts}
            disabled={isConnected}
            style={{
              background: '#334155',
              color: '#f8fafc',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 12px',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: isConnected ? 'not-allowed' : 'pointer'
            }}
          >
            🔍 Scan Ports
          </button>

          <span style={{ color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600, marginLeft: '8px' }}>Baud Rate:</span>
          <select
            value={baudrate}
            onChange={(e) => setBaudrate(parseInt(e.target.value, 10))}
            disabled={isConnected}
            style={{
              background: '#0f172a',
              color: '#e2e8f0',
              border: '1px solid #475569',
              borderRadius: '4px',
              padding: '6px 10px',
              fontSize: '0.85rem'
            }}
          >
            <option value={9600}>9600</option>
            <option value={57600}>57600</option>
            <option value={115200}>115200 (Default)</option>
            <option value={230400}>230400</option>
            <option value={921600}>921600 (High Speed)</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {!isConnected ? (
            <button
              onClick={handleConnect}
              disabled={connecting}
              style={{
                background: '#0284c7',
                color: '#ffffff',
                border: 'none',
                borderRadius: '6px',
                padding: '8px 16px',
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: connecting ? 'wait' : 'pointer'
              }}
            >
              {connecting ? 'Connecting...' : '🔌 Connect Hardware'}
            </button>
          ) : (
            <button
              onClick={handleDisconnect}
              style={{
                background: '#dc2626',
                color: '#ffffff',
                border: 'none',
                borderRadius: '6px',
                padding: '8px 16px',
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: 'pointer'
              }}
            >
              Disconnect
            </button>
          )}
        </div>
      </div>

      {statusMsg && (
        <div style={{
          background: isConnected ? 'rgba(5, 150, 105, 0.15)' : 'rgba(220, 38, 38, 0.15)',
          border: `1px solid ${isConnected ? '#059669' : '#dc2626'}`,
          color: isConnected ? '#34d399' : '#f87171',
          padding: '8px 14px',
          borderRadius: '6px',
          marginBottom: '16px',
          fontSize: '0.85rem'
        }}>
          {statusMsg}
        </div>
      )}

      {/* Disconnected Guidance State */}
      {!isHardwareConnected && (
        <div style={{
          background: '#0f172a',
          border: '1px solid #1e293b',
          borderRadius: '12px',
          padding: '32px 24px',
          textAlign: 'center',
          color: '#94a3b8',
          marginTop: '12px'
        }}>
          <div style={{ fontSize: '3rem', marginBottom: '12px' }}>🔌</div>
          <h3 style={{ color: '#f1f5f9', marginBottom: '8px' }}>Physical Hardware Disconnected</h3>
          <p style={{ maxWidth: '650px', margin: '0 auto 16px auto', lineHeight: '1.6', fontSize: '0.9rem' }}>
            Live Data mode strictly streams telemetry directly from physical microcontroller boards (e.g. <strong>ESP32, STM32, Texas Instruments TDC7200, or USB DAQ</strong>).
            To preserve laboratory data integrity, <strong>no simulated or fake values are rendered in Live mode</strong>.
          </p>
          <div style={{
            display: 'inline-block',
            textAlign: 'left',
            background: '#1e293b',
            borderRadius: '8px',
            padding: '16px 20px',
            fontSize: '0.85rem',
            color: '#cbd5e1'
          }}>
            <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '6px' }}>📌 Next Steps:</div>
            <div>1. Connect your ESP32 or serial DAQ to a physical USB COM port.</div>
            <div>2. Click <strong>"Scan Ports"</strong> above and select the detected COM device.</div>
            <div>3. Click <strong>"Connect Hardware"</strong> to initiate high-speed serial streaming.</div>
            <div style={{ marginTop: '8px', color: '#94a3b8' }}>
              💡 <em>To experiment with multi-chemistry battery physics without hardware, switch to <strong>3D Simulation</strong>, <strong>Gazebo</strong>, or <strong>Simulink</strong> in the Control Panel.</em>
            </div>
          </div>
        </div>
      )}

      {/* Active Connected Telemetry Grid */}
      {isHardwareConnected && frame && (
        <div className="view-content">
          <div className="data-section electrical">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>Electrical (ADC Sensors)</h3>
              <span style={{ fontSize: '0.7rem', color: '#38bdf8', fontWeight: 600 }}>LIVE HARDWARE</span>
            </div>
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
                <label>Internal Resistance (R₀):</label>
                <span>{frame.electrical_resistance?.toFixed(4)} Ω</span>
              </div>
            </div>
          </div>

          <div className="data-section ultrasonic">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>Ultrasonic (TDC7200 Acoustic)</h3>
              <span style={{ fontSize: '0.7rem', color: '#38bdf8', fontWeight: 600 }}>LIVE HARDWARE</span>
            </div>
            <div className="data-grid">
              <div className="data-item">
                <label>Time of Flight:</label>
                <span>{frame.ultrasonic_timeOfFlight?.toFixed(2)} μs</span>
              </div>
              <div className="data-item">
                <label>Echo Amplitude:</label>
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>Thermal (RTD / Heat Flux)</h3>
              <span style={{ fontSize: '0.7rem', color: '#38bdf8', fontWeight: 600 }}>LIVE HARDWARE</span>
            </div>
            <div className="data-grid">
              <div className="data-item">
                <label>Surface Temperature:</label>
                <span>{frame.thermal_temperature?.toFixed(2)}°C</span>
              </div>
              <div className="data-item">
                <label>Temperature Gradient:</label>
                <span>{frame.thermal_tempGradient?.toFixed(4)}°C/s</span>
              </div>
              <div className="data-item">
                <label>Heat Flux:</label>
                <span>{frame.thermal_heatFlux?.toFixed(2)} W/m²</span>
              </div>
            </div>
          </div>

          <div className="data-section ml-results">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>ML Multi-Modal Fusion (PyTorch)</h3>
              <span style={{ fontSize: '0.7rem', color: '#a855f7', fontWeight: 600 }}>FUSED INFERENCE</span>
            </div>
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
                <label>Mode Confidence:</label>
                <span>{(frame.degradation_probability * 100).toFixed(1)}%</span>
              </div>
              <div className="data-item">
                <label>Fault Risk:</label>
                <span style={{ color: frame.degradation_mode === 'healthy' ? '#10b981' : '#ef4444' }}>
                  {frame.degradation_mode === 'healthy' 
                    ? `${Math.max(0, 100 - frame.degradation_probability * 100).toFixed(1)}%` 
                    : `${(frame.degradation_probability * 100).toFixed(1)}%`}
                </span>
              </div>
              <div className="data-item">
                <label>Shannon Entropy:</label>
                <span>{frame.degradation_entropy?.toFixed(3)}</span>
              </div>
            </div>
          </div>

          <div className="data-section rebalancing">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>Active Power Stage Rebalancing</h3>
              <span style={{ fontSize: '0.7rem', color: '#f59e0b', fontWeight: 600 }}>ZVS CONVERTER</span>
            </div>
            <div className="data-grid">
              <div className="data-item">
                <label>Controller State:</label>
                <span>{frame.rebalancing_state?.replace(/_/g, ' ').toUpperCase()}</span>
              </div>
              <div className="data-item">
                <label>Selected Action:</label>
                <span>{frame.rebalancing_selectedAction?.replace(/_/g, ' ').toUpperCase()}</span>
              </div>
              <div className="data-item">
                <label>Action Rationale:</label>
                <span>{frame.rebalancing_actionReason}</span>
              </div>
              <div className="data-item">
                <label>Injected Current:</label>
                <span>{frame.rebalancing_powerStage_targetCurrent?.toFixed(2)} A</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LiveView;