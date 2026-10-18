import React, { useState, useEffect } from 'react';

interface SPMeState {
  current_a: number;
  temp_c: number;
  stoichiometry_surface: number;
  stoichiometry_average: number;
  concentration_gradient_mol_m3: number;
  u_eq_anode_v: number;
  eta_charge_transfer_mv: number;
  electrolyte_drop_mv: number;
  plating_overpotential_margin_mv: number;
  plating_active: boolean;
  accumulated_plated_li_mg: number;
  accumulated_dead_li_mg: number;
  estimated_dendrite_thickness_um: number;
  risk_verdict: 'SAFE_INTERCALATION' | 'INCIPIENT_PLATING_RISK' | 'CRITICAL_PLATING_ACTIVE';
  solid_concentration_profile: number[];
  radial_mesh_norm: number[];
}

interface DriveCycleRun {
  runtime_s: number;
  usable_energy_wh: number;
  heat_loss_wh: number;
  stranded_soc_pct: number;
  v_pack_trace: number[];
  v_cell4_trace: number[];
}

interface DriveCycleBenchmark {
  cycle_name: string;
  cycle_duration_s: number;
  peak_discharge_current_a: number;
  energy_gain_pct: number;
  heat_reduction_pct: number;
  passive_shunt: DriveCycleRun;
  active_zvs: DriveCycleRun;
}

const DriveCycleSPMeView: React.FC = () => {
  const [spmState, setSpmState] = useState<SPMeState | null>(null);
  const [inputCurrent, setInputCurrent] = useState<number>(-8.0);
  const [inputTemp, setInputTemp] = useState<number>(0.0);
  const [isAutoSimulating, setIsAutoSimulating] = useState<boolean>(true);

  // Drive Cycle State
  const [selectedCycle, setSelectedCycle] = useState<string>('wltp');
  const [driveCycleData, setDriveCycleData] = useState<DriveCycleBenchmark | null>(null);
  const [isLoadingCycle, setIsLoadingCycle] = useState<boolean>(false);

  // Poll SPMe state
  useEffect(() => {
    let isMounted = true;
    const fetchSPMe = async () => {
      try {
        const url = `/api/research/spm_plating_state?current_a=${inputCurrent}&temp_c=${inputTemp}&dt=0.5`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          if (isMounted) setSpmState(data);
        }
      } catch (err) {
        console.error('Error fetching SPMe state:', err);
      }
    };

    fetchSPMe();
    let interval: NodeJS.Timeout | null = null;
    if (isAutoSimulating) {
      interval = setInterval(fetchSPMe, 1000);
    }
    return () => {
      isMounted = false;
      if (interval) clearInterval(interval);
    };
  }, [inputCurrent, inputTemp, isAutoSimulating]);

  // Fetch Drive Cycle simulation on selection change
  useEffect(() => {
    let isMounted = true;
    const fetchCycle = async () => {
      setIsLoadingCycle(true);
      try {
        const res = await fetch(`/api/research/drive_cycle_benchmark?cycle_name=${selectedCycle}`);
        if (res.ok) {
          const data = await res.json();
          if (isMounted) setDriveCycleData(data);
        }
      } catch (err) {
        console.error('Error fetching drive cycle benchmark:', err);
      } finally {
        if (isMounted) setIsLoadingCycle(false);
      }
    };
    fetchCycle();
    return () => {
      isMounted = false;
    };
  }, [selectedCycle]);

  const handleResetSPMe = async () => {
    try {
      await fetch('/api/research/spm_plating_reset', { method: 'POST' });
      const res = await fetch(`/api/research/spm_plating_state?current_a=${inputCurrent}&temp_c=${inputTemp}&dt=0.5`);
      if (res.ok) {
        const data = await res.json();
        setSpmState(data);
      }
    } catch (err) {
      console.error('Error resetting SPMe:', err);
    }
  };

  const getVerdictBadge = (verdict?: string) => {
    switch (verdict) {
      case 'CRITICAL_PLATING_ACTIVE':
        return { label: 'CRITICAL: PLATING ACTIVE (ETA < 0 mV)', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' };
      case 'INCIPIENT_PLATING_RISK':
        return { label: 'WARNING: INCIPIENT PLATING MARGIN', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' };
      default:
        return { label: 'NOMINAL: THERMODYNAMICALLY SAFE', color: '#10b981', bg: 'rgba(16, 185, 129, 0.15)' };
    }
  };

  const badge = getVerdictBadge(spmState?.risk_verdict);

  return (
    <div style={{ padding: '16px', background: '#07090e', color: '#f8fafc', minHeight: '100%', fontFamily: 'monospace' }}>
      {/* Header bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', paddingBottom: '10px', borderBottom: '1px solid #1e293b' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, letterSpacing: '0.05em', color: '#38bdf8' }}>
            ELECTROCHEMICAL SPMe & AUTOMOTIVE DRIVE CYCLE WORKSTATION
          </h2>
          <div style={{ fontSize: '0.70rem', color: '#94a3b8', marginTop: '2px' }}>
            OPERANDO GRAPHITE SOLID DIFFUSION • ANODE OVERPOTENTIAL (Φs - Φe) • ZVS DRIVE CYCLE BENCHMARKS
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '0.65rem', padding: '4px 8px', borderRadius: '3px', background: badge.bg, color: badge.color, border: `1px solid ${badge.color}`, fontWeight: 700 }}>
            {badge.label}
          </span>
          <button
            onClick={() => setIsAutoSimulating(!isAutoSimulating)}
            style={{
              padding: '4px 8px',
              fontSize: '0.65rem',
              fontWeight: 700,
              background: isAutoSimulating ? '#1e293b' : '#334155',
              color: '#f8fafc',
              border: '1px solid #475569',
              borderRadius: '2px',
              cursor: 'pointer'
            }}
          >
            {isAutoSimulating ? 'PAUSE CLOCK' : 'RESUME CLOCK'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        {/* LEFT COLUMN: SPMe Electrochemical Model */}
        <div style={{ background: '#0b1120', border: '1px solid #1e293b', borderRadius: '4px', padding: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#38bdf8', letterSpacing: '0.04em' }}>
              1. SINGLE PARTICLE SOLID DIFFUSION & PLATING MARGIN
            </span>
            <button
              onClick={handleResetSPMe}
              style={{ fontSize: '0.60rem', padding: '2px 6px', background: '#1e293b', border: '1px solid #475569', color: '#94a3b8', cursor: 'pointer', borderRadius: '2px' }}
            >
              RESET CELL
            </button>
          </div>

          {/* Interactive Sliders */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', background: '#07090e', padding: '10px', borderRadius: '4px', border: '1px solid #1e293b', marginBottom: '12px' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: '#94a3b8' }}>
                <span>CELL CURRENT (I):</span>
                <span style={{ color: inputCurrent < 0 ? '#38bdf8' : '#10b981', fontWeight: 700 }}>{inputCurrent.toFixed(1)} A ({inputCurrent < 0 ? 'CHARGE' : 'DISCHARGE'})</span>
              </div>
              <input
                type="range"
                min="-15"
                max="10"
                step="0.5"
                value={inputCurrent}
                onChange={(e) => setInputCurrent(parseFloat(e.target.value))}
                style={{ width: '100%', marginTop: '4px' }}
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: '#94a3b8' }}>
                <span>CORE/SURFACE TEMP:</span>
                <span style={{ color: inputTemp <= 0 ? '#60a5fa' : '#f59e0b', fontWeight: 700 }}>{inputTemp.toFixed(1)} °C</span>
              </div>
              <input
                type="range"
                min="-10"
                max="45"
                step="1"
                value={inputTemp}
                onChange={(e) => setInputTemp(parseFloat(e.target.value))}
                style={{ width: '100%', marginTop: '4px' }}
              />
            </div>
          </div>

          {/* Overpotential Gauge & Key Telemetry */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '12px' }}>
            <div style={{ background: '#07090e', padding: '8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.60rem', color: '#64748b' }}>PLATING MARGIN (Φs - Φe)</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 800, color: (spmState?.plating_overpotential_margin_mv ?? 0) < 0 ? '#ef4444' : '#10b981', marginTop: '2px' }}>
                {spmState ? `${spmState.plating_overpotential_margin_mv > 0 ? '+' : ''}${spmState.plating_overpotential_margin_mv} mV` : '--'}
              </div>
              <div style={{ fontSize: '0.55rem', color: '#475569' }}>Threshold: 0.0 mV vs Li/Li+</div>
            </div>

            <div style={{ background: '#07090e', padding: '8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.60rem', color: '#64748b' }}>SURFACE STOICHIOMETRY (x_s)</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#f8fafc', marginTop: '2px' }}>
                {spmState ? `${(spmState.stoichiometry_surface * 100).toFixed(1)}%` : '--'}
              </div>
              <div style={{ fontSize: '0.55rem', color: '#475569' }}>Avg: {spmState ? `${(spmState.stoichiometry_average * 100).toFixed(1)}%` : '--'}</div>
            </div>

            <div style={{ background: '#07090e', padding: '8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.60rem', color: '#64748b' }}>PLATED METALLIC Li</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 800, color: (spmState?.accumulated_plated_li_mg ?? 0) > 0 ? '#ef4444' : '#10b981', marginTop: '2px' }}>
                {spmState ? `${spmState.accumulated_plated_li_mg} mg` : '--'}
              </div>
              <div style={{ fontSize: '0.55rem', color: '#475569' }}>Dead Li: {spmState?.accumulated_dead_li_mg ?? 0} mg</div>
            </div>

            <div style={{ background: '#07090e', padding: '8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.60rem', color: '#64748b' }}>DENDRITE THICKNESS</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 800, color: (spmState?.estimated_dendrite_thickness_um ?? 0) > 1.0 ? '#ef4444' : '#f8fafc', marginTop: '2px' }}>
                {spmState ? `${spmState.estimated_dendrite_thickness_um} µm` : '--'}
              </div>
              <div style={{ fontSize: '0.55rem', color: '#475569' }}>Separator Limit: 16.0 µm</div>
            </div>
          </div>

          {/* SVG Radial Solid Concentration Profile Curve */}
          <div style={{ background: '#07090e', border: '1px solid #1e293b', borderRadius: '3px', padding: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: '#94a3b8', marginBottom: '6px' }}>
              <span>GRAPHITE PARTICLE CONCENTRATION PROFILE c_s(r) [mol/m³]</span>
              <span>CORE (r=0) ➔ SURFACE (r=Rp=8µm)</span>
            </div>

            {spmState?.solid_concentration_profile ? (
              <svg viewBox="0 0 400 120" style={{ width: '100%', height: '110px' }}>
                {/* Horizontal grid lines */}
                <line x1="40" y1="20" x2="390" y2="20" stroke="#1e293b" strokeDasharray="3 3" />
                <line x1="40" y1="60" x2="390" y2="60" stroke="#1e293b" strokeDasharray="3 3" />
                <line x1="40" y1="100" x2="390" y2="100" stroke="#1e293b" strokeDasharray="3 3" />

                {/* Y-axis labels */}
                <text x="35" y="23" fill="#64748b" fontSize="8" textAnchor="end">31.5k</text>
                <text x="35" y="63" fill="#64748b" fontSize="8" textAnchor="end">20.0k</text>
                <text x="35" y="103" fill="#64748b" fontSize="8" textAnchor="end">10.0k</text>

                {/* Polyline plotting concentration profile */}
                {(() => {
                  const pts = spmState.solid_concentration_profile;
                  const n = pts.length;
                  const minVal = 8000;
                  const maxVal = 32000;
                  const coords = pts.map((val, idx) => {
                    const x = 40 + (idx / (n - 1)) * 350;
                    const y = 105 - ((val - minVal) / (maxVal - minVal)) * 85;
                    return `${x},${y}`;
                  }).join(' ');

                  return (
                    <>
                      <polyline
                        fill="none"
                        stroke="#38bdf8"
                        strokeWidth="2.2"
                        points={coords}
                      />
                      {/* Highlight surface concentration point */}
                      <circle
                        cx="390"
                        cy={105 - ((pts[n - 1] - minVal) / (maxVal - minVal)) * 85}
                        r="3.5"
                        fill={(spmState.plating_overpotential_margin_mv < 0) ? '#ef4444' : '#10b981'}
                      />
                    </>
                  );
                })()}

                <text x="40" y="116" fill="#64748b" fontSize="7">r/Rp = 0.0 (Core)</text>
                <text x="390" y="116" fill="#64748b" fontSize="7" textAnchor="end">r/Rp = 1.0 (Interfacial Anode Surface)</text>
              </svg>
            ) : (
              <div style={{ height: '110px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: '0.70rem' }}>
                Evaluating SPMe Solid Diffusion...
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Automotive Drive Cycles & Active Balancing */}
        <div style={{ background: '#0b1120', border: '1px solid #1e293b', borderRadius: '4px', padding: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#10b981', letterSpacing: '0.04em' }}>
              2. STANDARDIZED AUTOMOTIVE DRIVE CYCLES & ACTIVE ZVS
            </span>
            <span style={{ fontSize: '0.62rem', color: '#94a3b8' }}>8S1P PACK (CELL #4 SOH=78%)</span>
          </div>

          {/* Drive Cycle Selector Pills */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px', marginBottom: '12px' }}>
            {[
              { id: 'wltp', label: 'WLTP Class 3b', time: '1800s' },
              { id: 'us06', label: 'US06 Highway', time: '600s' },
              { id: 'udds', label: 'UDDS City', time: '1369s' },
              { id: 'hppc', label: 'HPPC Pulse', time: '120s' },
            ].map(c => (
              <button
                key={c.id}
                onClick={() => setSelectedCycle(c.id)}
                style={{
                  padding: '6px 4px',
                  background: selectedCycle === c.id ? '#1e293b' : '#07090e',
                  border: `1px solid ${selectedCycle === c.id ? '#38bdf8' : '#334155'}`,
                  color: selectedCycle === c.id ? '#38bdf8' : '#94a3b8',
                  borderRadius: '3px',
                  cursor: 'pointer',
                  fontSize: '0.65rem',
                  fontWeight: selectedCycle === c.id ? 700 : 500,
                  textAlign: 'center'
                }}
              >
                <div>{c.label}</div>
                <div style={{ fontSize: '0.55rem', opacity: 0.7 }}>{c.time}</div>
              </button>
            ))}
          </div>

          {/* Drive Cycle Empirical Scorecard */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '12px' }}>
            <div style={{ background: '#07090e', padding: '8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.60rem', color: '#64748b' }}>USABLE PACK ENERGY</div>
              <div style={{ fontSize: '0.90rem', fontWeight: 800, color: '#10b981', marginTop: '2px' }}>
                {driveCycleData ? `${driveCycleData.active_zvs.usable_energy_wh} Wh` : '--'}
              </div>
              <div style={{ fontSize: '0.55rem', color: '#38bdf8' }}>
                Gain: {driveCycleData ? `+${driveCycleData.energy_gain_pct}%` : '--'} vs Passive
              </div>
            </div>

            <div style={{ background: '#07090e', padding: '8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.60rem', color: '#64748b' }}>THERMAL JOULE LOSSES</div>
              <div style={{ fontSize: '0.90rem', fontWeight: 800, color: '#f8fafc', marginTop: '2px' }}>
                {driveCycleData ? `${driveCycleData.active_zvs.heat_loss_wh} Wh` : '--'}
              </div>
              <div style={{ fontSize: '0.55rem', color: '#10b981' }}>
                Saved: {driveCycleData ? `-${driveCycleData.heat_reduction_pct}%` : '--'} Heat
              </div>
            </div>

            <div style={{ background: '#07090e', padding: '8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.60rem', color: '#64748b' }}>PACK OPERATION TIME</div>
              <div style={{ fontSize: '0.90rem', fontWeight: 800, color: '#f8fafc', marginTop: '2px' }}>
                {driveCycleData ? `${driveCycleData.active_zvs.runtime_s} s` : '--'}
              </div>
              <div style={{ fontSize: '0.55rem', color: '#94a3b8' }}>
                Passive Cutoff: {driveCycleData ? `${driveCycleData.passive_shunt.runtime_s} s` : '--'}
              </div>
            </div>
          </div>

          {/* SVG Comparative Voltage Traces: Passive Shunt vs Active ZVS */}
          <div style={{ background: '#07090e', border: '1px solid #1e293b', borderRadius: '3px', padding: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: '#94a3b8', marginBottom: '6px' }}>
              <span>WEAK CELL #4 VOLTAGE TRAJECTORY [V]</span>
              <span>
                <span style={{ color: '#ef4444' }}>■ PASSIVE CUTOFF</span>&nbsp;&nbsp;
                <span style={{ color: '#10b981' }}>■ ACTIVE ZVS RECOVERY</span>
              </span>
            </div>

            {driveCycleData ? (
              <svg viewBox="0 0 400 120" style={{ width: '100%', height: '110px' }}>
                {/* 3.00 V Cutoff Boundary */}
                <line x1="30" y1="95" x2="390" y2="95" stroke="#ef4444" strokeWidth="1" strokeDasharray="4 2" />
                <text x="390" y="92" fill="#ef4444" fontSize="7" textAnchor="end">3.00V CUTOFF</text>

                {/* Y-axis labels */}
                <text x="25" y="25" fill="#64748b" fontSize="8" textAnchor="end">3.8V</text>
                <text x="25" y="60" fill="#64748b" fontSize="8" textAnchor="end">3.4V</text>
                <text x="25" y="98" fill="#64748b" fontSize="8" textAnchor="end">3.0V</text>

                {/* Passive Trace (red) */}
                {(() => {
                  const traceP = driveCycleData.passive_shunt.v_cell4_trace;
                  const n = traceP.length;
                  const ptsP = traceP.map((v, i) => {
                    const x = 30 + (i / (n - 1)) * 360;
                    const y = 95 - ((v - 3.0) / 0.8) * 75;
                    return `${x},${Math.max(15, Math.min(105, y))}`;
                  }).join(' ');
                  return <polyline fill="none" stroke="#ef4444" strokeWidth="1.6" strokeDasharray="3 1" points={ptsP} />;
                })()}

                {/* Active Trace (green) */}
                {(() => {
                  const traceA = driveCycleData.active_zvs.v_cell4_trace;
                  const n = traceA.length;
                  const ptsA = traceA.map((v, i) => {
                    const x = 30 + (i / (n - 1)) * 360;
                    const y = 95 - ((v - 3.0) / 0.8) * 75;
                    return `${x},${Math.max(15, Math.min(105, y))}`;
                  }).join(' ');
                  return <polyline fill="none" stroke="#10b981" strokeWidth="2.2" points={ptsA} />;
                })()}

                <text x="30" y="116" fill="#64748b" fontSize="7">0 s</text>
                <text x="390" y="116" fill="#64748b" fontSize="7" textAnchor="end">{driveCycleData.cycle_duration_s} s</text>
              </svg>
            ) : (
              <div style={{ height: '110px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: '0.70rem' }}>
                {isLoadingCycle ? 'Simulating Dynamic Drive Cycle...' : 'Select a drive cycle above'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DriveCycleSPMeView;
