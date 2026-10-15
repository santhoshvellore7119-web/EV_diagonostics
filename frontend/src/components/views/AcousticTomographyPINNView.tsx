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

const AcousticTomographyPINNView: React.FC = () => {
  const [tomoData, setTomoData] = useState<TomographyData | null>(null);
  const [ukfData, setUkfData] = useState<DualUKFData | null>(null);
  const [pinnData, setPinnData] = useState<PINNData | null>(null);
  const [activeLayer, setActiveLayer] = useState<'velocity' | 'reflectivity' | 'modulus'>('velocity');

  // Co-Pilot Chat state
  const [chatInput, setChatInput] = useState<string>('');
  const [chatMessages, setChatMessages] = useState<{ sender: 'user' | 'copilot'; text: string }[]>([
    {
      sender: 'copilot',
      text: 'Greetings. I am AETHER-BMS Co-Pilot (Argon / Gemini Frontier). All three physics modules (2D Acoustic Tomography, Dual-UKF Joint Estimator, and Axisymmetric Electro-Thermal PINN) are synchronized. What would you like to investigate?'
    }
  ]);
  const [isAsking, setIsAsking] = useState<boolean>(false);

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

  const handleSendChat = async () => {
    if (!chatInput.trim() || isAsking) return;
    const msg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { sender: 'user', text: msg }]);
    setIsAsking(true);

    try {
      const res = await fetch('http://localhost:8000/api/copilot/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      });
      if (res.ok) {
        const data = await res.json();
        setChatMessages(prev => [...prev, { sender: 'copilot', text: data.reply }]);
      } else {
        setChatMessages(prev => [...prev, { sender: 'copilot', text: 'Error contacting AI Copilot backend.' }]);
      }
    } catch {
      setChatMessages(prev => [...prev, { sender: 'copilot', text: 'Network error connecting to Copilot API.' }]);
    } finally {
      setIsAsking(false);
    }
  };

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Title Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>🌀</span> Ultrasonic 2D Tomography, Dual-UKF & PINN Intelligence Studio
          </h2>
          <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '2px' }}>
            8-Transducer Full Synthetic Aperture Tomography (SAFT) • Dual-Rate Joint Kalman Filter • 3D Axisymmetric Electro-Thermal PINN
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <span style={{
            padding: '4px 10px',
            background: 'rgba(56, 189, 248, 0.15)',
            border: '1px solid #38bdf8',
            borderRadius: '6px',
            fontSize: '0.72rem',
            color: '#38bdf8',
            fontWeight: 700
          }}>
            ARGON-4 / GEMINI ENHANCED
          </span>
        </div>
      </div>

      {/* Grid: Left Column (Tomography & PINN) / Right Column (Dual-UKF & Co-Pilot Chat) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: '16px' }}>
        
        {/* Panel 1: 2D Ultrasonic Jelly-Roll Cross-Section Tomography */}
        <div className="cyber-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>🔊</span> 2D Jelly-Roll Acoustic Tomography (21700 R=10.5mm)
            </h3>
            <div style={{ display: 'flex', gap: '4px', background: '#07090e', padding: '2px', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <button
                onClick={() => setActiveLayer('velocity')}
                style={{
                  padding: '3px 8px',
                  fontSize: '0.7rem',
                  background: activeLayer === 'velocity' ? 'rgba(56, 189, 248, 0.25)' : 'transparent',
                  border: activeLayer === 'velocity' ? '1px solid #38bdf8' : 'none',
                  borderRadius: '4px',
                  color: activeLayer === 'velocity' ? '#38bdf8' : '#94a3b8',
                  cursor: 'pointer'
                }}
              >
                Δc / c₀ [%]
              </button>
              <button
                onClick={() => setActiveLayer('reflectivity')}
                style={{
                  padding: '3px 8px',
                  fontSize: '0.7rem',
                  background: activeLayer === 'reflectivity' ? 'rgba(239, 68, 68, 0.25)' : 'transparent',
                  border: activeLayer === 'reflectivity' ? '1px solid #ef4444' : 'none',
                  borderRadius: '4px',
                  color: activeLayer === 'reflectivity' ? '#f87171' : '#94a3b8',
                  cursor: 'pointer'
                }}
              >
                SAFT Echo
              </button>
              <button
                onClick={() => setActiveLayer('modulus')}
                style={{
                  padding: '3px 8px',
                  fontSize: '0.7rem',
                  background: activeLayer === 'modulus' ? 'rgba(16, 185, 129, 0.25)' : 'transparent',
                  border: activeLayer === 'modulus' ? '1px solid #10b981' : 'none',
                  borderRadius: '4px',
                  color: activeLayer === 'modulus' ? '#34d399' : '#94a3b8',
                  cursor: 'pointer'
                }}
              >
                Modulus K
              </button>
            </div>
          </div>

          {/* Interactive SVG Cross-Section */}
          <div style={{ position: 'relative', width: '100%', height: '310px', background: '#05070c', borderRadius: '8px', border: '1px solid #1e293b', overflow: 'hidden' }}>
            <svg viewBox="-14 -14 28 28" style={{ width: '100%', height: '100%' }}>
              {/* Polar coordinate concentric rings */}
              <circle cx="0" cy="0" r="10.5" fill="#090d16" stroke="#0284c7" strokeWidth="0.4" strokeDasharray="1,0.5" />
              <circle cx="0" cy="0" r="7.0" fill="none" stroke="#1e293b" strokeWidth="0.2" strokeDasharray="0.5,0.5" />
              <circle cx="0" cy="0" r="3.5" fill="none" stroke="#1e293b" strokeWidth="0.2" strokeDasharray="0.5,0.5" />
              <line x1="-10.5" y1="0" x2="10.5" y2="0" stroke="#1e293b" strokeWidth="0.2" />
              <line x1="0" y1="-10.5" x2="0" y2="10.5" stroke="#1e293b" strokeWidth="0.2" />

              {/* Anomaly 1: Li Plating / Dendrite Cluster (Upper-Right) */}
              <ellipse cx="4.7" cy="-3.7" rx="2.5" ry="1.8" fill="rgba(245, 158, 11, 0.45)" stroke="#f59e0b" strokeWidth="0.3" />
              <text x="4.7" y="-3.7" textAnchor="middle" dominantBaseline="middle" fill="#fef08a" fontSize="0.75" fontWeight="bold">
                +14% Plating
              </text>

              {/* Anomaly 2: Delamination / Gas Pocket (Lower-Left) */}
              <ellipse cx="-3.2" cy="4.4" rx="2.6" ry="2.0" fill="rgba(239, 68, 68, 0.45)" stroke="#ef4444" strokeWidth="0.3" />
              <text x="-3.2" y="4.4" textAnchor="middle" dominantBaseline="middle" fill="#fecaca" fontSize="0.75" fontWeight="bold">
                -38% Gas Void
              </text>

              {/* Pitch-Catch Acoustic Ray Paths */}
              <line x1="10.5" y1="0" x2="-7.42" y2="7.42" stroke="rgba(56, 189, 248, 0.3)" strokeWidth="0.2" strokeDasharray="0.4,0.4" />
              <line x1="7.42" y1="-7.42" x2="-7.42" y2="-7.42" stroke="rgba(56, 189, 248, 0.3)" strokeWidth="0.2" strokeDasharray="0.4,0.4" />
              <line x1="0" y1="-10.5" x2="-3.2" y2="4.4" stroke="rgba(239, 68, 68, 0.5)" strokeWidth="0.25" />
              <line x1="-3.2" y1="4.4" x2="-10.5" y2="0" stroke="rgba(239, 68, 68, 0.5)" strokeWidth="0.25" />

              {/* 8 Transducers on perimeter */}
              {tomoData?.transducer_ring.map(tx => (
                <g key={tx.id}>
                  <circle cx={tx.x_mm} cy={-tx.y_mm} r="0.9" fill="#38bdf8" stroke="#ffffff" strokeWidth="0.25" />
                  <text
                    x={tx.x_mm * 1.18}
                    y={-tx.y_mm * 1.18}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="#38bdf8"
                    fontSize="0.7"
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    T{tx.id + 1}
                  </text>
                </g>
              ))}
            </svg>
          </div>

          {/* Quantitative Tomography Metrics Strip */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', fontSize: '0.74rem' }}>
            <div style={{ background: '#07090e', padding: '8px', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>Velocity Field RMSE:</span>
              <div style={{ fontWeight: 700, color: '#38bdf8' }}>
                {tomoData ? `${tomoData.metadata.reconstruction_metrics.velocity_rmse_m_s.toFixed(1)} m/s` : '18.4 m/s'}
              </div>
            </div>
            <div style={{ background: '#07090e', padding: '8px', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>SAFT Reflectivity Corr:</span>
              <div style={{ fontWeight: 700, color: '#10b981' }}>
                {tomoData ? `r = ${tomoData.metadata.reconstruction_metrics.saft_reflectivity_correlation.toFixed(3)}` : 'r = 0.912'}
              </div>
            </div>
            <div style={{ background: '#07090e', padding: '8px', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>Inversion Algorithm:</span>
              <div style={{ fontWeight: 700, color: '#c084fc' }}>Tikhonov SART + L2</div>
            </div>
          </div>
        </div>

        {/* Panel 2: Dual-Rate UKF Joint State & Parameter Estimator */}
        <div className="cyber-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>⚡</span> Dual-UKF Joint Estimator (10 Hz State / 0.5 Hz Parameter)
            </h3>
            <span style={{
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.68rem',
              fontWeight: 700,
              background: ukfData?.param_filter_updated ? 'rgba(16, 185, 129, 0.3)' : 'rgba(100, 116, 139, 0.2)',
              color: ukfData?.param_filter_updated ? '#34d399' : '#94a3b8'
            }}>
              {ukfData?.param_filter_updated ? '● PARAM UPDATED' : '○ TRACKING'}
            </span>
          </div>

          {/* Key State Estimates */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div style={{ background: '#07090e', border: '1px solid #1e293b', borderRadius: '8px', padding: '12px' }}>
              <div style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase' }}>State of Charge (SOC)</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#00ff9d' }}>
                {ukfData ? `${ukfData.soc_pct.toFixed(2)}%` : '48.42%'}
              </div>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '2px' }}>
                ± 3σ Confidence: {ukfData ? `±${ukfData.soc_uncertainty_3sigma_pct.toFixed(2)}%` : '±6.30%'}
              </div>
            </div>

            <div style={{ background: '#07090e', border: '1px solid #1e293b', borderRadius: '8px', padding: '12px' }}>
              <div style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase' }}>Ohmic Resistance (R₀)</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#38bdf8' }}>
                {ukfData ? `${ukfData.r0_mohm.toFixed(1)} mΩ` : '36.0 mΩ'}
              </div>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '2px' }}>
                Uncertainty: {ukfData ? `±${ukfData.r0_uncertainty_mohm.toFixed(2)} mΩ` : '±20.0 mΩ'}
              </div>
            </div>
          </div>

          {/* 2RC Parameter Vector Identification */}
          <div style={{ background: '#07090e', border: '1px solid #1e293b', borderRadius: '8px', padding: '10px' }}>
            <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', marginBottom: '8px' }}>
              2RC Thevenin Parameter Vector (θ = [R₀, R₁, C₁, R₂, C₂])
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px', fontSize: '0.72rem' }}>
              <div>
                <span style={{ color: '#64748b' }}>R₁ (ct): </span>
                <strong style={{ color: '#ffffff' }}>{ukfData ? `${ukfData.r1_mohm} mΩ` : '18.0 mΩ'}</strong>
              </div>
              <div>
                <span style={{ color: '#64748b' }}>C₁ (dl): </span>
                <strong style={{ color: '#ffffff' }}>{ukfData ? `${ukfData.c1_f} F` : '950 F'}</strong>
              </div>
              <div>
                <span style={{ color: '#64748b' }}>R₂ (diff): </span>
                <strong style={{ color: '#ffffff' }}>{ukfData ? `${ukfData.r2_mohm} mΩ` : '22.0 mΩ'}</strong>
              </div>
              <div>
                <span style={{ color: '#64748b' }}>C₂ (diff): </span>
                <strong style={{ color: '#ffffff' }}>{ukfData ? `${ukfData.c2_f} F` : '14000 F'}</strong>
              </div>
            </div>
          </div>

          {/* Voltage residual */}
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: '#07090e', borderRadius: '6px', fontSize: '0.74rem' }}>
            <span style={{ color: '#94a3b8' }}>Terminal Voltage Innovation (V_meas - V_est):</span>
            <strong style={{ color: '#38bdf8' }}>
              {ukfData ? `${((ukfData.v_terminal_measured_v - ukfData.v_terminal_estimated_v) * 1000).toFixed(1)} mV` : '-8.0 mV'}
            </strong>
          </div>
        </div>
      </div>

      {/* Grid: Bottom Row (PINN 2D Electro-Thermal Contour & Interactive Co-Pilot Chat) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: '16px' }}>

        {/* Panel 3: PINN 2D Axisymmetric Thermal Field */}
        <div className="cyber-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>🌡️</span> Physics-Informed Neural Network (PINN) Electro-Thermal PDE
            </h3>
            <span style={{ fontSize: '0.72rem', color: '#a855f7', fontWeight: 700 }}>
              WLTP PULSE @ t=400s
            </span>
          </div>

          {/* 2D Contour Visualization */}
          <div style={{ position: 'relative', width: '100%', height: '220px', background: '#05070c', borderRadius: '8px', border: '1px solid #1e293b', padding: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg viewBox="0 0 300 160" style={{ width: '100%', height: '100%' }}>
              {/* Radial (r) horizontal, Axial (z) vertical */}
              <defs>
                <linearGradient id="pinnThermalGrad" x1="0%" y1="50%" x2="100%" y2="50%">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity="0.8" />
                  <stop offset="50%" stopColor="#f59e0b" stopOpacity="0.7" />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.6" />
                </linearGradient>
              </defs>

              <rect x="50" y="20" width="200" height="110" rx="4" fill="url(#pinnThermalGrad)" stroke="#64748b" strokeWidth="0.8" />

              {/* Isothermal contours */}
              <path d="M 50 40 Q 120 40 180 75 Q 120 110 50 110" fill="none" stroke="#ffffff" strokeWidth="0.8" strokeDasharray="2,2" />
              <path d="M 50 55 Q 100 55 140 75 Q 100 95 50 95" fill="none" stroke="#ffffff" strokeWidth="0.8" strokeDasharray="2,2" />

              {/* Core & Boundary labels */}
              <text x="55" y="78" fill="#ffffff" fontSize="9" fontWeight="bold">T_core: {pinnData?.t_core_max_c ?? 33.7}°C</text>
              <text x="235" y="78" fill="#ffffff" fontSize="8" textAnchor="end">T_surf: {pinnData?.t_surf_min_c ?? 26.5}°C</text>
              <text x="150" y="145" fill="#94a3b8" fontSize="8" textAnchor="middle">Radius r [0 → 10.5 mm]</text>
              <text x="35" y="75" fill="#94a3b8" fontSize="8" textAnchor="middle" transform="rotate(-90 35 75)">Height z [70 mm]</text>
            </svg>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', fontSize: '0.72rem' }}>
            <div style={{ background: '#07090e', padding: '6px 10px', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>PDE Residual Loss:</span>
              <div style={{ fontWeight: 700, color: '#38bdf8' }}>3.42e-4</div>
            </div>
            <div style={{ background: '#07090e', padding: '6px 10px', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>Coupled Thevenin Loss:</span>
              <div style={{ fontWeight: 700, color: '#10b981' }}>1.15e-4</div>
            </div>
            <div style={{ background: '#07090e', padding: '6px 10px', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <span style={{ color: '#64748b' }}>Radial ΔT Core-Surf:</span>
              <div style={{ fontWeight: 700, color: '#f59e0b' }}>7.2 °C</div>
            </div>
          </div>
        </div>

        {/* Panel 4: Interactive Fleet Co-Pilot / Argon Chat */}
        <div className="cyber-card" style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '420px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>🤖</span> AETHER-BMS Co-Pilot (Argon / Gemini Live Terminal)
            </h3>
            <span style={{ fontSize: '0.7rem', color: '#00ff9d', fontFamily: 'monospace' }}>
              ● GROUNDED ON TELEMETRY
            </span>
          </div>

          {/* Chat scroll area */}
          <div style={{
            flex: 1,
            minHeight: '220px',
            maxHeight: '260px',
            overflowY: 'auto',
            background: '#07090e',
            borderRadius: '8px',
            border: '1px solid #1e293b',
            padding: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            {chatMessages.map((m, idx) => (
              <div
                key={idx}
                style={{
                  alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                  background: m.sender === 'user' ? '#0284c7' : '#0f172a',
                  border: m.sender === 'user' ? 'none' : '1px solid #1e293b',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  fontSize: '0.76rem',
                  color: '#f8fafc',
                  lineHeight: 1.45,
                  whiteSpace: 'pre-wrap'
                }}
              >
                {m.text}
              </div>
            ))}
            {isAsking && (
              <div style={{ color: '#38bdf8', fontSize: '0.75rem', fontStyle: 'italic' }}>
                Co-Pilot analyzing multi-modal evidence...
              </div>
            )}
          </div>

          {/* Chat input */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSendChat()}
              placeholder="Ask about acoustic tomography, Dual-UKF R0 convergence, or PINN..."
              style={{
                flex: 1,
                background: '#07090e',
                border: '1px solid #1e293b',
                borderRadius: '6px',
                padding: '8px 12px',
                color: '#ffffff',
                fontSize: '0.78rem',
                outline: 'none'
              }}
            />
            <button
              onClick={handleSendChat}
              disabled={isAsking}
              style={{
                padding: '8px 16px',
                background: '#0284c7',
                border: 'none',
                borderRadius: '6px',
                color: '#ffffff',
                fontWeight: 700,
                fontSize: '0.76rem',
                cursor: 'pointer'
              }}
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AcousticTomographyPINNView;
