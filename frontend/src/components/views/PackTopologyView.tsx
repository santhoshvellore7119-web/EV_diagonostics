import React, { useState, useEffect } from 'react';

interface PackCellData {
  cell_id: number;
  voltage_v: number;
  soc_pct: number;
  soh_pct: number;
  temperature_c: number;
  r0_mohm: number;
  degradation_mode: string;
  fault_injected: boolean;
  balancing_status: 'idle' | 'donor' | 'recipient' | 'isolated';
  transfer_current_a: number;
}

interface PackData {
  num_cells: number;
  pack_voltage_v: number;
  voltage_delta_mv: number;
  soc_spread_pct: number;
  max_temp_c: number;
  balancing_active: boolean;
  lockout_active: boolean;
  zvs_efficiency_pct: number;
  usable_capacity_gain_pct: number;
  cumulative_energy_shuttled_wh: number;
  weakest_cell_id: number;
  active_transfers: { from_cells: number[]; to_cell: number; current_a: number; efficiency_pct: number }[];
  cells: PackCellData[];
}

const PackTopologyView: React.FC = () => {
  const [packData, setPackData] = useState<PackData | null>(null);

  // Fault injection controls
  const [selectedCellId, setSelectedCellId] = useState<number>(4);
  const [selectedFault, setSelectedFault] = useState<string>('li_plating');
  const [severity, setSeverity] = useState<number>(0.85);
  const [actionStatus, setActionStatus] = useState<string>('');

  const fetchPack = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/research/pack_topology');
      if (res.ok) {
        const data = await res.json();
        setPackData(data);
      }
    } catch (e) {
      // Backend maybe offline
    }
  };

  useEffect(() => {
    fetchPack();
    const interval = setInterval(fetchPack, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleInjectFault = async () => {
    setActionStatus(`Injecting ${selectedFault} on Cell #${selectedCellId}...`);
    try {
      const res = await fetch('http://localhost:8000/api/research/inject_fault', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cell_id: selectedCellId,
          fault_type: selectedFault,
          severity
        })
      });
      if (res.ok) {
        setActionStatus(`Fault injected successfully! Observing autonomous rebalancing.`);
        fetchPack();
      }
    } catch (e) {
      setActionStatus('Failed to inject fault.');
    }
  };

  const handleResetPack = async () => {
    setActionStatus('Resetting all pack cells to nominal baseline...');
    try {
      const res = await fetch('http://localhost:8000/api/research/reset_pack', { method: 'POST' });
      if (res.ok) {
        setActionStatus('Pack reset complete.');
        fetchPack();
      }
    } catch (e) {
      setActionStatus('Failed to reset pack.');
    }
  };

  if (!packData) {
    return (
      <div style={{ padding: '24px', color: '#94a3b8', textAlign: 'center' }}>
        Loading 8S Modular Pack Topology & Active Balancer...
      </div>
    );
  }

  const {
    pack_voltage_v,
    voltage_delta_mv,
    soc_spread_pct,
    max_temp_c,
    balancing_active,
    lockout_active,
    zvs_efficiency_pct,
    usable_capacity_gain_pct,
    cumulative_energy_shuttled_wh,
    weakest_cell_id,
    cells
  } = packData;

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Header bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              background: '#0284c7',
              color: '#ffffff',
              fontSize: '0.68rem',
              fontWeight: 800,
              padding: '2px 6px',
              borderRadius: '2px',
              fontFamily: 'monospace'
            }}>
              SECTION 05
            </span>
            <h2 style={{ margin: 0, fontSize: '1.05rem', color: '#f8fafc', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.02em' }}>
              8S1P Modular Pack Topology & Active ZVS Energy Balancing Matrix
            </h2>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '3px', fontFamily: 'monospace' }}>
            BIDIRECTIONAL QUASI-RESONANT FLYBACK BUS • WEAKEST-FIRST SHUTTLING (η ≥ 92.8%) • AUTONOMOUS INTERLOCKS
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{
            padding: '4px 10px',
            borderRadius: '2px',
            fontSize: '0.70rem',
            fontWeight: 700,
            fontFamily: 'monospace',
            background: lockout_active ? 'rgba(220, 38, 38, 0.2)' : balancing_active ? 'rgba(16, 185, 129, 0.2)' : 'rgba(100, 116, 139, 0.15)',
            border: `1px solid ${lockout_active ? '#dc2626' : balancing_active ? '#10b981' : '#334155'}`,
            color: lockout_active ? '#f87171' : balancing_active ? '#34d399' : '#cbd5e1'
          }}>
            {lockout_active ? 'STRING ISOLATED - LOCKOUT ACTIVE' : balancing_active ? 'ZVS BUS ENGAGED (η ≥ 92.8%)' : 'STRING BALANCED - STANDBY'}
          </span>
        </div>
      </div>

      {/* Metric Counters Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px' }}>
        <div style={{ background: '#0d111a', border: '1px solid #1e293b', borderRadius: '8px', padding: '10px 14px' }}>
          <div style={{ fontSize: '0.70rem', color: '#64748b', textTransform: 'uppercase' }}>Pack String Voltage</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#ffffff' }}>{pack_voltage_v.toFixed(2)} V</div>
        </div>
        <div style={{ background: '#0d111a', border: '1px solid #1e293b', borderRadius: '8px', padding: '10px 14px' }}>
          <div style={{ fontSize: '0.70rem', color: '#64748b', textTransform: 'uppercase' }}>Max Cell Spread (ΔV)</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: voltage_delta_mv > 50 ? '#ffb700' : '#38bdf8' }}>
            {voltage_delta_mv.toFixed(1)} mV
          </div>
        </div>
        <div style={{ background: '#0d111a', border: '1px solid #1e293b', borderRadius: '8px', padding: '10px 14px' }}>
          <div style={{ fontSize: '0.70rem', color: '#64748b', textTransform: 'uppercase' }}>SOC Inbalance (ΔSOC)</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: soc_spread_pct > 8 ? '#ffb700' : '#00ff9d' }}>
            {soc_spread_pct.toFixed(1)}%
          </div>
        </div>
        <div style={{ background: '#0d111a', border: '1px solid #1e293b', borderRadius: '8px', padding: '10px 14px' }}>
          <div style={{ fontSize: '0.70rem', color: '#64748b', textTransform: 'uppercase' }}>ZVS Flyback Efficiency</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#10b981' }}>{zvs_efficiency_pct.toFixed(1)}%</div>
        </div>
        <div style={{ background: '#0d111a', border: '1px solid #1e293b', borderRadius: '8px', padding: '10px 14px' }}>
          <div style={{ fontSize: '0.70rem', color: '#64748b', textTransform: 'uppercase' }}>Usable Pack Gain</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#00f0ff' }}>+{usable_capacity_gain_pct.toFixed(1)}%</div>
        </div>
        <div style={{ background: '#0d111a', border: '1px solid #1e293b', borderRadius: '8px', padding: '10px 14px' }}>
          <div style={{ fontSize: '0.70rem', color: '#64748b', textTransform: 'uppercase' }}>Peak Cell Temp</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: max_temp_c > 45 ? '#ef4444' : '#10b981' }}>{max_temp_c.toFixed(1)} °C</div>
        </div>
        <div style={{ background: '#0d111a', border: '1px solid #1e293b', borderRadius: '8px', padding: '10px 14px' }}>
          <div style={{ fontSize: '0.70rem', color: '#64748b', textTransform: 'uppercase' }}>Shuttled Energy</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#c084fc' }}>{cumulative_energy_shuttled_wh.toFixed(2)} Wh</div>
        </div>
      </div>

      {/* 8-Cell Grid Matrix */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
        gap: '12px'
      }}>
        {cells.map(cell => {
          const isWeakest = cell.cell_id === weakest_cell_id;
          const isRecipient = cell.balancing_status === 'recipient';
          const isDonor = cell.balancing_status === 'donor';

          return (
            <div
              key={cell.cell_id}
              style={{
                background: isRecipient ? 'rgba(16, 185, 129, 0.08)' : isDonor ? 'rgba(2, 132, 199, 0.08)' : '#07090e',
                border: `1.5px solid ${isRecipient ? '#10b981' : isDonor ? '#0284c7' : isWeakest ? '#f59e0b' : '#1e293b'}`,
                borderRadius: '10px',
                padding: '12px',
                position: 'relative',
                transition: 'all 0.2s ease'
              }}
            >
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>
                  Cell #{cell.cell_id}
                </span>
                <span style={{
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  background: isRecipient ? '#059669' : isDonor ? '#0284c7' : '#334155',
                  color: '#ffffff'
                }}>
                  {cell.balancing_status.toUpperCase()}
                </span>
              </div>

              {/* Core Telemetry */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '0.74rem', marginBottom: '8px' }}>
                <div>
                  <span style={{ color: '#64748b' }}>Voltage: </span>
                  <strong style={{ color: '#f8fafc' }}>{cell.voltage_v.toFixed(3)} V</strong>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>Temp: </span>
                  <strong style={{ color: cell.temperature_c > 45 ? '#ef4444' : '#f8fafc' }}>{cell.temperature_c.toFixed(1)} °C</strong>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>SOC: </span>
                  <strong style={{ color: '#38bdf8' }}>{cell.soc_pct.toFixed(1)}%</strong>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>SOH: </span>
                  <strong style={{ color: cell.soh_pct < 80 ? '#f59e0b' : '#34d399' }}>{cell.soh_pct.toFixed(1)}%</strong>
                </div>
              </div>

              {/* Shuttling Current Bar */}
              {Math.abs(cell.transfer_current_a) > 0.05 && (
                <div style={{
                  fontSize: '0.72rem',
                  padding: '4px 8px',
                  background: isRecipient ? 'rgba(16, 185, 129, 0.2)' : 'rgba(2, 132, 199, 0.2)',
                  borderRadius: '4px',
                  color: isRecipient ? '#34d399' : '#38bdf8',
                  fontWeight: 600,
                  display: 'flex',
                  justifyContent: 'space-between'
                }}>
                  <span>{isRecipient ? '📥 Receiving Charge:' : '📤 Supplying Charge:'}</span>
                  <span>{Math.abs(cell.transfer_current_a).toFixed(2)} A</span>
                </div>
              )}

              {/* Degradation Tag */}
              {cell.degradation_mode !== 'healthy' && (
                <div style={{
                  marginTop: '6px',
                  fontSize: '0.68rem',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  color: '#f87171',
                  fontWeight: 600,
                  textAlign: 'center'
                }}>
                  ⚠️ {cell.degradation_mode.replace(/_/g, ' ').toUpperCase()}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Fault Injection & Laboratory Console */}
      <div style={{
        background: '#0d111a',
        border: '1px solid #1e293b',
        borderRadius: '10px',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#ffb700', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          🛠️ Interactive Hardware-in-the-Loop Fault Injection Console
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'center' }}>
          <div>
            <label style={{ fontSize: '0.72rem', color: '#64748b', display: 'block', marginBottom: '4px' }}>Target Cell:</label>
            <select
              value={selectedCellId}
              onChange={e => setSelectedCellId(Number(e.target.value))}
              style={{ background: '#1e293b', color: '#fff', border: '1px solid #334155', borderRadius: '6px', padding: '6px 10px', fontSize: '0.78rem' }}
            >
              {[1, 2, 3, 4, 5, 6, 7, 8].map(id => (
                <option key={id} value={id}>Cell #{id}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ fontSize: '0.72rem', color: '#64748b', display: 'block', marginBottom: '4px' }}>Degradation Mode:</label>
            <select
              value={selectedFault}
              onChange={e => setSelectedFault(e.target.value)}
              style={{ background: '#1e293b', color: '#fff', border: '1px solid #334155', borderRadius: '6px', padding: '6px 10px', fontSize: '0.78rem' }}
            >
              <option value="li_plating">Lithium Plating (Acoustic Velocity Drop + R_ct Jump)</option>
              <option value="internal_short">Internal Short Circuit (Micro-Puncture Emulation + Thermal Rise)</option>
              <option value="gas_generation">Gas Generation / Delamination (Coda Acoustic Dispersion)</option>
              <option value="electrolyte_decomposition">Electrolyte Decomposition (Ohmic R0 Jump)</option>
              <option value="active_material_loss">Loss of Active Material (Capacity Fade)</option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: '0.72rem', color: '#64748b', display: 'block', marginBottom: '4px' }}>Severity: {(severity * 100).toFixed(0)}%</label>
            <input
              type="range"
              min="0.2"
              max="1.0"
              step="0.05"
              value={severity}
              onChange={e => setSeverity(Number(e.target.value))}
              style={{ width: '120px' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '14px' }}>
            <button
              onClick={handleInjectFault}
              style={{
                padding: '8px 16px',
                background: '#ea580c',
                border: 'none',
                borderRadius: '6px',
                color: '#fff',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              ⚡ Inject Fault
            </button>
            <button
              onClick={handleResetPack}
              style={{
                padding: '8px 16px',
                background: '#334155',
                border: 'none',
                borderRadius: '6px',
                color: '#fff',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              ↺ Reset Pack
            </button>
          </div>
        </div>
        {actionStatus && (
          <div style={{ fontSize: '0.74rem', color: '#38bdf8', fontFamily: 'monospace' }}>
            {actionStatus}
          </div>
        )}
      </div>
    </div>
  );
};

export default PackTopologyView;
