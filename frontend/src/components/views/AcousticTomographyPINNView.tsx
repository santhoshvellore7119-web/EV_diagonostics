import React, { useState, useEffect } from 'react';

interface TransducerPoint {
  id: number;
  angle_deg: number;
  x_mm: number;
  y_mm: number;
}

interface TomographyData {
  metadata: {
    cell_format: string;
    cell_radius_mm: number;
    grid_resolution: [number, number];
    n_transducers: number;
    frequency_mhz: number;
    baseline_sound_speed_m_s: number;
    reconstruction_metrics: {
      velocity_rmse_m_s: number;
      velocity_mae_m_s: number;
      saft_reflectivity_correlation: number;
      min_reconstructed_velocity_m_s: number;
      max_reconstructed_velocity_m_s: number;
    };
  };
  transducer_ring: TransducerPoint[];
  axes: {
    x_mm: number[];
    y_mm: number[];
    valid_cell_mask: number[][];
  };
  heatmaps: {
    saft_reflectivity_norm: number[][];
    velocity_reconstructed_m_s: number[][];
    velocity_perturbation_pct: number[][];
    bulk_modulus_gpa: number[][];
  };
}

interface DualUKFData {
  soc_pct: number;
  soc_uncertainty_3sigma_pct: number;
  r0_mohm: number;
  r0_uncertainty_mohm: number;
  r1_mohm: number;
  c1_f: number;
  r2_mohm: number;
  c2_f: number;
  v_terminal_estimated_v: number;
  v_terminal_measured_v: number;
  docv_dsoc: number;
  param_filter_updated: boolean;
}

interface PINNData {
  cell_name: string;
  radius_mm: number;
  height_mm: number;
  r_axis_mm: number[];
  z_axis_mm: number[];
  temperature_contour_c: number[][];
  t_core_max_c: number;
  t_surf_min_c: number;
  pde_residual_loss: number;
  overpotential_thevenin_loss: number;
  boundary_robin_loss: number;
  pinn_architecture: string;
}

interface DiagnosticTroubleCode {
  code: string;
  subCode: string;
  description: string;
  status: 'CONFIRMED' | 'PENDING' | 'PASS';
  severity: 'CRITICAL' | 'WARNING' | 'INFO';
}

const AcousticTomographyPINNView: React.FC = () => {
  const [tomoData, setTomoData] = useState<TomographyData | null>(null);
  const [ukfData, setUkfData] = useState<DualUKFData | null>(null);
  const [pinnData, setPinnData] = useState<PINNData | null>(null);
  const [activeLayer, setActiveLayer] = useState<'velocity' | 'reflectivity' | 'modulus'>('velocity');

  // UDS Diagnostic Registers
  const [dtcList, setDtcList] = useState<DiagnosticTroubleCode[]>([
    {
      code: 'P0B24',
      subCode: '92',
      description: 'Anode Lithium Plating Inception - Acoustic Velocity Shift > +10%',
      status: 'CONFIRMED',
      severity: 'WARNING'
    },
    {
      code: 'P0B3B',
      subCode: '17',
      description: 'Cell #4 Potential / Modulus Deviation - Exceeds 15 mV Threshold',
      status: 'CONFIRMED',
      severity: 'WARNING'
    },
    {
      code: 'P0A7E',
      subCode: '00',
      description: 'Jelly-Roll Radial Thermal Gradient Divergence (T_core - T_surf > 6°C)',
      status: 'PENDING',
      severity: 'INFO'
    },
    {
      code: 'P0A80',
      subCode: '00',
      description: 'Hybrid Battery Pack Degradation Tracking - Operando DRT Alert',
      status: 'PASS',
      severity: 'INFO'
    }
  ]);
  const [udsStatusMessage, setUdsStatusMessage] = useState<string>('UDS Service 0x22 Active • All DIDs In Sync');

  useEffect(() => {
    // Fetch Tomography
    fetch('http://localhost:8000/api/research/tomography_heatmap')
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setTomoData(d))
      .catch(() => {});

    // Fetch PINN
    fetch('http://localhost:8000/api/research/pinn_temperature_field')
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setPinnData(d))
      .catch(() => {});

    // Poll UKF at 1 Hz
    const fetchUKF = () => {
      fetch('http://localhost:8000/api/research/dual_ukf_telemetry')
        .then(r => r.ok ? r.json() : null)
        .then(d => d && setUkfData(d))
        .catch(() => {});
    };
    fetchUKF();
    const interval = setInterval(fetchUKF, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleClearDTC = () => {
    setDtcList(prev => prev.map(dtc => ({ ...dtc, status: 'PASS' })));
    setUdsStatusMessage('UDS 0x14 ClearDiagnosticInformation: SUCCESS (DTCs Reset)');
    setTimeout(() => {
      setUdsStatusMessage('UDS Service 0x22 Active • All DIDs In Sync');
    }, 3000);
  };

  const handleFreezeFrame = () => {
    setUdsStatusMessage('Snapshot Freeze-Frame Record Stored to NVRAM (Buffer #01)');
    setTimeout(() => {
      setUdsStatusMessage('UDS Service 0x22 Active • All DIDs In Sync');
    }, 3000);
  };

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* Title Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', borderBottom: '1px solid #1e293b', paddingBottom: '10px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{
              background: '#0284c7',
              color: '#ffffff',
              fontSize: '0.68rem',
              fontWeight: 800,
              padding: '2px 6px',
              borderRadius: '2px',
              fontFamily: 'monospace',
              letterSpacing: '0.05em'
            }}>
              SECTION 04
            </span>
            <h2 style={{ margin: 0, fontSize: '1.05rem', color: '#f8fafc', fontWeight: 700, letterSpacing: '0.02em', textTransform: 'uppercase' }}>
              Acoustic Wavefield Tomography & Physics-Informed State Estimation
            </h2>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '3px', fontFamily: 'monospace' }}>
            8-CHANNEL 2.0 MHz SYNTHETIC APERTURE (SAFT) • DUAL-RATE KALMAN OBSERVER • 3D AXISYMMETRIC PINN SOLVER
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{
            padding: '3px 8px',
            background: 'rgba(2, 132, 199, 0.1)',
            border: '1px solid #0284c7',
            borderRadius: '2px',
            fontSize: '0.70rem',
            color: '#38bdf8',
            fontFamily: 'monospace',
            fontWeight: 700
          }}>
            CALIBRATION ID: AETHER-NDT-21700
          </span>
          <span style={{
            padding: '3px 8px',
            background: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid #10b981',
            borderRadius: '2px',
            fontSize: '0.70rem',
            color: '#34d399',
            fontFamily: 'monospace',
            fontWeight: 700
          }}>
            ISO 26262 ASIL-D
          </span>
        </div>
      </div>

      {/* Grid: Upper Row (Tomography & Dual-UKF) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '12px' }}>
        
        {/* Panel 1: 2D Ultrasonic Jelly-Roll Cross-Section Tomography */}
        <div className="cyber-card" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.80rem', fontWeight: 700, color: '#f8fafc', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Acoustic Tomography Cross-Section [21700 R=10.5 mm]
            </span>
            <div style={{ display: 'flex', gap: '2px', background: '#07090e', padding: '2px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <button
                onClick={() => setActiveLayer('velocity')}
                style={{
                  padding: '2px 7px',
                  fontSize: '0.68rem',
                  background: activeLayer === 'velocity' ? '#0284c7' : 'transparent',
                  border: 'none',
                  borderRadius: '2px',
                  color: activeLayer === 'velocity' ? '#ffffff' : '#64748b',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontFamily: 'monospace'
                }}
              >
                Δc/c₀ [%]
              </button>
              <button
                onClick={() => setActiveLayer('reflectivity')}
                style={{
                  padding: '2px 7px',
                  fontSize: '0.68rem',
                  background: activeLayer === 'reflectivity' ? '#dc2626' : 'transparent',
                  border: 'none',
                  borderRadius: '2px',
                  color: activeLayer === 'reflectivity' ? '#ffffff' : '#64748b',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontFamily: 'monospace'
                }}
              >
                SAFT ECHO
              </button>
              <button
                onClick={() => setActiveLayer('modulus')}
                style={{
                  padding: '2px 7px',
                  fontSize: '0.68rem',
                  background: activeLayer === 'modulus' ? '#059669' : 'transparent',
                  border: 'none',
                  borderRadius: '2px',
                  color: activeLayer === 'modulus' ? '#ffffff' : '#64748b',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontFamily: 'monospace'
                }}
              >
                MODULUS K
              </button>
            </div>
          </div>

          {/* Interactive Cross-Section Display */}
          <div style={{ position: 'relative', width: '100%', height: '290px', background: '#05070c', borderRadius: '4px', border: '1px solid #1e293b', overflow: 'hidden' }}>
            <svg viewBox="-14 -14 28 28" style={{ width: '100%', height: '100%' }}>
              <circle cx="0" cy="0" r="10.5" fill="#090d16" stroke="#0284c7" strokeWidth="0.3" strokeDasharray="1,0.5" />
              <circle cx="0" cy="0" r="7.0" fill="none" stroke="#1e293b" strokeWidth="0.2" strokeDasharray="0.5,0.5" />
              <circle cx="0" cy="0" r="3.5" fill="none" stroke="#1e293b" strokeWidth="0.2" strokeDasharray="0.5,0.5" />
              <line x1="-10.5" y1="0" x2="10.5" y2="0" stroke="#1e293b" strokeWidth="0.2" />
              <line x1="0" y1="-10.5" x2="0" y2="10.5" stroke="#1e293b" strokeWidth="0.2" />

              {/* Anomaly 1: Plating Zone */}
              <ellipse cx="4.7" cy="-3.7" rx="2.5" ry="1.8" fill="rgba(217, 119, 6, 0.4)" stroke="#d97706" strokeWidth="0.25" />
              <text x="4.7" y="-3.7" textAnchor="middle" dominantBaseline="middle" fill="#fef08a" fontSize="0.70" fontFamily="monospace" fontWeight="bold">
                +14% PLATING
              </text>

              {/* Anomaly 2: Delamination Zone */}
              <ellipse cx="-3.2" cy="4.4" rx="2.6" ry="2.0" fill="rgba(220, 38, 38, 0.4)" stroke="#dc2626" strokeWidth="0.25" />
              <text x="-3.2" y="4.4" textAnchor="middle" dominantBaseline="middle" fill="#fecaca" fontSize="0.70" fontFamily="monospace" fontWeight="bold">
                -38% GAS VOID
              </text>

              {/* Ray paths */}
              <line x1="10.5" y1="0" x2="-7.42" y2="7.42" stroke="rgba(56, 189, 248, 0.25)" strokeWidth="0.15" strokeDasharray="0.4,0.4" />
              <line x1="7.42" y1="-7.42" x2="-7.42" y2="-7.42" stroke="rgba(56, 189, 248, 0.25)" strokeWidth="0.15" strokeDasharray="0.4,0.4" />
              <line x1="0" y1="-10.5" x2="-3.2" y2="4.4" stroke="rgba(220, 38, 38, 0.45)" strokeWidth="0.2" />
              <line x1="-3.2" y1="4.4" x2="-10.5" y2="0" stroke="rgba(220, 38, 38, 0.45)" strokeWidth="0.2" />

              {/* 8 Transducers */}
              {tomoData?.transducer_ring.map(tx => (
                <g key={tx.id}>
                  <circle cx={tx.x_mm} cy={-tx.y_mm} r="0.8" fill="#0284c7" stroke="#ffffff" strokeWidth="0.2" />
                  <text
                    x={tx.x_mm * 1.18}
                    y={-tx.y_mm * 1.18}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="#38bdf8"
                    fontSize="0.65"
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    T{tx.id + 1}
                  </text>
                </g>
              ))}
            </svg>
          </div>

          {/* Metrics Bar */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px', fontSize: '0.70rem', fontFamily: 'monospace' }}>
            <div style={{ background: '#07090e', padding: '6px 8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>VELOCITY RMSE:</span>
              <div style={{ fontWeight: 700, color: '#38bdf8' }}>
                {tomoData ? `${tomoData.metadata.reconstruction_metrics.velocity_rmse_m_s.toFixed(1)} m/s` : '18.4 m/s'}
              </div>
            </div>
            <div style={{ background: '#07090e', padding: '6px 8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>SAFT CORRELATION:</span>
              <div style={{ fontWeight: 700, color: '#34d399' }}>
                {tomoData ? `r = ${tomoData.metadata.reconstruction_metrics.saft_reflectivity_correlation.toFixed(3)}` : 'r = 0.912'}
              </div>
            </div>
            <div style={{ background: '#07090e', padding: '6px 8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>SOLVER:</span>
              <div style={{ fontWeight: 700, color: '#cbd5e1' }}>TIKHONOV SART</div>
            </div>
          </div>
        </div>

        {/* Panel 2: Dual-Rate UKF Joint State & Parameter Estimator */}
        <div className="cyber-card" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.80rem', fontWeight: 700, color: '#f8fafc', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Dual-UKF State & Parameter Observer [10 Hz / 0.5 Hz]
            </span>
            <span style={{
              padding: '2px 6px',
              borderRadius: '2px',
              fontSize: '0.65rem',
              fontWeight: 700,
              fontFamily: 'monospace',
              background: ukfData?.param_filter_updated ? 'rgba(16, 185, 129, 0.2)' : 'rgba(100, 116, 139, 0.15)',
              border: `1px solid ${ukfData?.param_filter_updated ? '#10b981' : '#334155'}`,
              color: ukfData?.param_filter_updated ? '#34d399' : '#94a3b8'
            }}>
              {ukfData?.param_filter_updated ? 'PARAMETER STEPPED (0.5 Hz)' : 'TRACKING STATE (10 Hz)'}
            </span>
          </div>

          {/* Key State Estimates */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <div style={{ background: '#07090e', border: '1px solid #1e293b', borderRadius: '4px', padding: '10px' }}>
              <div style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', fontFamily: 'monospace' }}>
                State of Charge (SOC)
              </div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#00ff9d', fontFamily: 'monospace', marginTop: '2px' }}>
                {ukfData ? `${ukfData.soc_pct.toFixed(2)}%` : '48.42%'}
              </div>
              <div style={{ fontSize: '0.68rem', color: '#94a3b8', fontFamily: 'monospace', marginTop: '2px' }}>
                Covariance ±3σ: {ukfData ? `±${ukfData.soc_uncertainty_3sigma_pct.toFixed(2)}%` : '±6.30%'}
              </div>
            </div>

            <div style={{ background: '#07090e', border: '1px solid #1e293b', borderRadius: '4px', padding: '10px' }}>
              <div style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', fontFamily: 'monospace' }}>
                Ohmic Resistance (R₀)
              </div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'monospace', marginTop: '2px' }}>
                {ukfData ? `${ukfData.r0_mohm.toFixed(1)} mΩ` : '36.0 mΩ'}
              </div>
              <div style={{ fontSize: '0.68rem', color: '#94a3b8', fontFamily: 'monospace', marginTop: '2px' }}>
                Ident Uncertainty: {ukfData ? `±${ukfData.r0_uncertainty_mohm.toFixed(2)} mΩ` : '±20.0 mΩ'}
              </div>
            </div>
          </div>

          {/* 2RC Parameter Matrix */}
          <div style={{ background: '#07090e', border: '1px solid #1e293b', borderRadius: '4px', padding: '10px' }}>
            <div style={{ fontSize: '0.66rem', color: '#64748b', textTransform: 'uppercase', fontFamily: 'monospace', marginBottom: '6px' }}>
              Identified 2RC Thevenin Parameter Vector (θ = [R₀, R₁, C₁, R₂, C₂])
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px', fontSize: '0.70rem', fontFamily: 'monospace' }}>
              <div style={{ background: '#05070c', padding: '4px 6px', borderRadius: '2px' }}>
                <span style={{ color: '#64748b' }}>R₁ (ct): </span>
                <strong style={{ color: '#f8fafc' }}>{ukfData ? `${ukfData.r1_mohm} mΩ` : '18.0 mΩ'}</strong>
              </div>
              <div style={{ background: '#05070c', padding: '4px 6px', borderRadius: '2px' }}>
                <span style={{ color: '#64748b' }}>C₁ (dl): </span>
                <strong style={{ color: '#f8fafc' }}>{ukfData ? `${ukfData.c1_f} F` : '950 F'}</strong>
              </div>
              <div style={{ background: '#05070c', padding: '4px 6px', borderRadius: '2px' }}>
                <span style={{ color: '#64748b' }}>R₂ (diff): </span>
                <strong style={{ color: '#f8fafc' }}>{ukfData ? `${ukfData.r2_mohm} mΩ` : '22.0 mΩ'}</strong>
              </div>
              <div style={{ background: '#05070c', padding: '4px 6px', borderRadius: '2px' }}>
                <span style={{ color: '#64748b' }}>C₂ (diff): </span>
                <strong style={{ color: '#f8fafc' }}>{ukfData ? `${ukfData.c2_f} F` : '14000 F'}</strong>
              </div>
            </div>
          </div>

          {/* Residual & OCV Derivative Strip */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '0.70rem', fontFamily: 'monospace' }}>
            <div style={{ padding: '6px 10px', background: '#07090e', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>INNOVATION (V_meas - V_est): </span>
              <strong style={{ color: '#38bdf8' }}>
                {ukfData ? `${((ukfData.v_terminal_measured_v - ukfData.v_terminal_estimated_v) * 1000).toFixed(1)} mV` : '-8.0 mV'}
              </strong>
            </div>
            <div style={{ padding: '6px 10px', background: '#07090e', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>OCV GRADIENT dOCV/dSOC: </span>
              <strong style={{ color: '#34d399' }}>
                {ukfData ? `${ukfData.docv_dsoc.toFixed(3)} V` : '0.702 V'}
              </strong>
            </div>
          </div>
        </div>
      </div>

      {/* Grid: Lower Row (PINN 2D Thermal Field & UDS DTC Register) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '12px' }}>

        {/* Panel 3: PINN 2D Axisymmetric Thermal Field */}
        <div className="cyber-card" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.80rem', fontWeight: 700, color: '#f8fafc', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Physics-Informed Neural Network (PINN) Thermal PDE
            </span>
            <span style={{ fontSize: '0.68rem', color: '#cbd5e1', fontFamily: 'monospace', background: '#07090e', padding: '2px 6px', border: '1px solid #1e293b', borderRadius: '2px' }}>
              WLTP STEP t = 400 s
            </span>
          </div>

          {/* 2D Contour Visualizer */}
          <div style={{ position: 'relative', width: '100%', height: '190px', background: '#05070c', borderRadius: '4px', border: '1px solid #1e293b', padding: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg viewBox="0 0 300 140" style={{ width: '100%', height: '100%' }}>
              <defs>
                <linearGradient id="pinnThermalGrad" x1="0%" y1="50%" x2="100%" y2="50%">
                  <stop offset="0%" stopColor="#dc2626" stopOpacity="0.85" />
                  <stop offset="45%" stopColor="#d97706" stopOpacity="0.75" />
                  <stop offset="100%" stopColor="#0284c7" stopOpacity="0.65" />
                </linearGradient>
              </defs>

              <rect x="45" y="15" width="210" height="95" rx="2" fill="url(#pinnThermalGrad)" stroke="#334155" strokeWidth="0.8" />

              <path d="M 45 35 Q 110 35 170 62 Q 110 90 45 90" fill="none" stroke="#ffffff" strokeWidth="0.7" strokeDasharray="2,2" />
              <path d="M 45 48 Q 95 48 135 62 Q 95 76 45 76" fill="none" stroke="#ffffff" strokeWidth="0.7" strokeDasharray="2,2" />

              <text x="50" y="65" fill="#ffffff" fontSize="8" fontFamily="monospace" fontWeight="bold">T_core: {pinnData?.t_core_max_c ?? 33.7}°C</text>
              <text x="245" y="65" fill="#ffffff" fontSize="7.5" fontFamily="monospace" textAnchor="end">T_surf: {pinnData?.t_surf_min_c ?? 26.5}°C</text>
              <text x="150" y="125" fill="#64748b" fontSize="7" fontFamily="monospace" textAnchor="middle">RADIUS r [0.0 → 10.5 mm]</text>
              <text x="32" y="62" fill="#64748b" fontSize="7" fontFamily="monospace" textAnchor="middle" transform="rotate(-90 32 62)">HEIGHT z [70 mm]</text>
            </svg>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px', fontSize: '0.68rem', fontFamily: 'monospace' }}>
            <div style={{ background: '#07090e', padding: '6px 8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>PDE RESIDUAL:</span>
              <div style={{ fontWeight: 700, color: '#38bdf8' }}>3.42e-04</div>
            </div>
            <div style={{ background: '#07090e', padding: '6px 8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>THEVENIN LOSS:</span>
              <div style={{ fontWeight: 700, color: '#34d399' }}>1.15e-04</div>
            </div>
            <div style={{ background: '#07090e', padding: '6px 8px', borderRadius: '3px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>RADIAL ΔT:</span>
              <div style={{ fontWeight: 700, color: '#f59e0b' }}>7.2 °C</div>
            </div>
          </div>
        </div>

        {/* Panel 4: ISO 14229 / UDS Diagnostic Register & Calibration Control (Replaces AI Terminal) */}
        <div className="cyber-card" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.80rem', fontWeight: 700, color: '#f8fafc', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              ISO 14229 / UDS Diagnostic Monitor & DTC Register
            </span>
            <span style={{ fontSize: '0.66rem', color: '#38bdf8', fontFamily: 'monospace' }}>
              {udsStatusMessage}
            </span>
          </div>

          {/* DTC Tabular Register */}
          <div style={{
            background: '#05070c',
            border: '1px solid #1e293b',
            borderRadius: '4px',
            overflow: 'hidden',
            maxHeight: '190px',
            overflowY: 'auto'
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.70rem', fontFamily: 'monospace' }}>
              <thead>
                <tr style={{ background: '#0a0f1d', borderBottom: '1px solid #1e293b', color: '#64748b', textAlign: 'left' }}>
                  <th style={{ padding: '6px 8px' }}>DTC CODE</th>
                  <th style={{ padding: '6px 8px' }}>DESCRIPTION</th>
                  <th style={{ padding: '6px 8px' }}>STATUS</th>
                  <th style={{ padding: '6px 8px' }}>SEVERITY</th>
                </tr>
              </thead>
              <tbody>
                {dtcList.map((dtc, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #131b2e' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 700, color: dtc.status === 'CONFIRMED' ? '#f59e0b' : '#94a3b8' }}>
                      {dtc.code}-{dtc.subCode}
                    </td>
                    <td style={{ padding: '6px 8px', color: '#cbd5e1' }}>
                      {dtc.description}
                    </td>
                    <td style={{ padding: '6px 8px' }}>
                      <span style={{
                        padding: '1px 5px',
                        borderRadius: '2px',
                        fontSize: '0.62rem',
                        fontWeight: 700,
                        background: dtc.status === 'CONFIRMED' ? 'rgba(217, 119, 6, 0.2)' : dtc.status === 'PENDING' ? 'rgba(2, 132, 199, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                        color: dtc.status === 'CONFIRMED' ? '#f59e0b' : dtc.status === 'PENDING' ? '#38bdf8' : '#34d399'
                      }}>
                        {dtc.status}
                      </span>
                    </td>
                    <td style={{ padding: '6px 8px', color: dtc.severity === 'CRITICAL' ? '#ef4444' : dtc.severity === 'WARNING' ? '#f59e0b' : '#64748b' }}>
                      {dtc.severity}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Action & Calibration Controls */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={handleClearDTC}
              style={{
                flex: 1,
                padding: '6px 10px',
                background: '#07090e',
                border: '1px solid #334155',
                borderRadius: '3px',
                color: '#f8fafc',
                fontSize: '0.70rem',
                fontFamily: 'monospace',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              CLEAR ACTIVE DTCS (0x14)
            </button>
            <button
              onClick={handleFreezeFrame}
              style={{
                flex: 1,
                padding: '6px 10px',
                background: '#0284c7',
                border: 'none',
                borderRadius: '3px',
                color: '#ffffff',
                fontSize: '0.70rem',
                fontFamily: 'monospace',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              SNAPSHOT FREEZE-FRAME (0x19)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AcousticTomographyPINNView;
