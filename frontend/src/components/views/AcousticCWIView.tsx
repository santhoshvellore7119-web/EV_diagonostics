import React, { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';

interface CWIMetrics {
  dv_over_v_percent: number;
  max_correlation: number;
  decorrelation_kd: number;
  elastic_modulus_shift_pct: number;
  nonlinear_beta: number;
  correlation_curve: { eps_percent: number; correlation: number }[];
  coda_window_us: [number, number];
}

interface CWIData {
  time_us: number[];
  ref_amplitude: number[];
  cur_amplitude: number[];
  cwi_metrics: CWIMetrics;
  degradation_mode: string;
}

const AcousticCWIView: React.FC = () => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const [cwiData, setCwiData] = useState<CWIData | null>(null);
  const [showEnvelope, setShowEnvelope] = useState<boolean>(true);

  const fetchCWI = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/research/cwi_spectrogram');
      if (res.ok) {
        const data = await res.json();
        setCwiData(data);
      }
    } catch (e) {
      // Backend maybe offline
    }
  };

  useEffect(() => {
    fetchCWI();
    const interval = setInterval(fetchCWI, 2500);
    return () => clearInterval(interval);
  }, [frame?.degradation_mode]);

  if (!cwiData) {
    return (
      <div style={{ padding: '24px', color: '#94a3b8', textAlign: 'center' }}>
        Loading Ultrasonic Guided Wave & CWI Laboratory...
      </div>
    );
  }

  const { time_us, ref_amplitude, cur_amplitude, cwi_metrics, degradation_mode } = cwiData;

  const svgW = 600;
  const svgH = 260;
  const padL = 45;
  const padR = 20;
  const padT = 20;
  const padB = 35;

  const minT = time_us[0] || 0;
  const maxT = time_us[time_us.length - 1] || 12.8;
  const minA = -1.2;
  const maxA = 1.2;

  const scaleT = (t: number) => padL + ((t - minT) / (maxT - minT)) * (svgW - padL - padR);
  const scaleA = (a: number) => svgH - padB - ((a - minA) / (maxA - minA)) * (svgH - padT - padB);

  // Construct SVG paths
  const refPath = ref_amplitude
    .map((a, i) => `${i === 0 ? 'M' : 'L'} ${scaleT(time_us[i]).toFixed(1)} ${scaleA(a).toFixed(1)}`)
    .join(' ');
  const curPath = cur_amplitude
    .map((a, i) => `${i === 0 ? 'M' : 'L'} ${scaleT(time_us[i]).toFixed(1)} ${scaleA(a).toFixed(1)}`)
    .join(' ');

  // Coda window box
  const [codaStart, codaEnd] = cwi_metrics.coda_window_us;
  const codaBoxX1 = scaleT(codaStart);
  const codaBoxX2 = scaleT(codaEnd);

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
              SECTION 03
            </span>
            <h2 style={{ margin: 0, fontSize: '1.05rem', color: '#f8fafc', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.02em' }}>
              Ultrasonic Guided Wave & Coda Wave Interferometry (CWI)
            </h2>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '3px', fontFamily: 'monospace' }}>
            2.0 MHz PITCH-CATCH A-SCAN • WAVEFORM STRETCHING • RELATIVE VELOCITY SHIFT Δv/v
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <label style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showEnvelope}
              onChange={e => setShowEnvelope(e.target.checked)}
              style={{ accentColor: '#00ff9d' }}
            />
            Show AD8307 Log-Envelope
          </label>
          <span style={{ padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700, background: '#1e293b', color: '#38bdf8' }}>
            MODE: {degradation_mode.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Main Grid: Waveform Display + CWI Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '16px' }}>
        {/* A-Scan Visualizer */}
        <div style={{ background: '#07090e', border: '1px solid #1e293b', borderRadius: '10px', padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#38bdf8' }}>
              Operando RF A-Scan Waveform (Healthy Baseline vs. Live Perturbed)
            </span>
            <div style={{ display: 'flex', gap: '12px', fontSize: '0.72rem' }}>
              <span style={{ color: '#64748b' }}>— Reference</span>
              <span style={{ color: '#00ff9d', fontWeight: 600 }}>— Live Echo</span>
              <span style={{ color: '#a855f7' }}>■ Coda Window</span>
            </div>
          </div>

          <svg width="100%" height={svgH} viewBox={`0 0 ${svgW} ${svgH}`}>
            {/* Coda observation region highlight */}
            <rect
              x={codaBoxX1}
              y={padT}
              width={codaBoxX2 - codaBoxX1}
              height={svgH - padT - padB}
              fill="rgba(168, 85, 247, 0.08)"
              stroke="rgba(168, 85, 247, 0.3)"
              strokeDasharray="4 2"
            />
            <text x={(codaBoxX1 + codaBoxX2) / 2} y={padT + 12} fill="#c084fc" fontSize={9} textAnchor="middle" fontWeight={600}>
              Coda Analysis Window ({codaStart.toFixed(1)} - {codaEnd.toFixed(1)} µs)
            </text>

            {/* Zero line */}
            <line x1={padL} y1={scaleA(0)} x2={svgW - padR} y2={scaleA(0)} stroke="#1e293b" strokeWidth={1} />

            {/* Axes */}
            <line x1={padL} y1={svgH - padB} x2={svgW - padR} y2={svgH - padB} stroke="#334155" strokeWidth={1.5} />
            <line x1={padL} y1={padT} x2={padL} y2={svgH - padB} stroke="#334155" strokeWidth={1.5} />

            {/* Labels */}
            <text x={svgW / 2} y={svgH - 6} fill="#94a3b8" fontSize={10} textAnchor="middle" fontWeight={600}>
              Propagation Time (µs)
            </text>
            <text x={12} y={svgH / 2} fill="#94a3b8" fontSize={10} textAnchor="middle" transform={`rotate(-90,12,${svgH / 2})`} fontWeight={600}>
              Normalized RF Voltage
            </text>

            {/* Reference Waveform */}
            <path d={refPath} fill="none" stroke="#475569" strokeWidth={1.2} strokeDasharray="3 3" />

            {/* Current Waveform */}
            <path d={curPath} fill="none" stroke="#00ff9d" strokeWidth={1.8} />

            {/* Time ticks */}
            {[0, 2, 4, 6, 8, 10, 12].map(tVal => {
              if (tVal > maxT) return null;
              const x = scaleT(tVal);
              return (
                <g key={tVal}>
                  <line x1={x} y1={svgH - padB} x2={x} y2={svgH - padB + 4} stroke="#475569" />
                  <text x={x} y={svgH - padB + 14} fill="#64748b" fontSize={9} textAnchor="middle" fontFamily="monospace">
                    {tVal}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* CWI Metrics Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ background: '#0d111a', border: '1px solid #1e293b', borderRadius: '10px', padding: '14px' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.05em' }}>
              Microstructural CWI Parameters
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.76rem' }}>
              <div style={{ background: '#131826', padding: '8px', borderRadius: '6px' }}>
                <div style={{ color: '#64748b' }}>Velocity Shift (Δv/v)</div>
                <div style={{ color: Math.abs(cwi_metrics.dv_over_v_percent) > 1.0 ? '#ffb700' : '#00ff9d', fontSize: '0.95rem', fontWeight: 700 }}>
                  {cwi_metrics.dv_over_v_percent > 0 ? `+${cwi_metrics.dv_over_v_percent}%` : `${cwi_metrics.dv_over_v_percent}%`}
                </div>
              </div>
              <div style={{ background: '#131826', padding: '8px', borderRadius: '6px' }}>
                <div style={{ color: '#64748b' }}>Waveform Decorrelation</div>
                <div style={{ color: cwi_metrics.decorrelation_kd > 0.1 ? '#ff3366' : '#38bdf8', fontSize: '0.95rem', fontWeight: 700 }}>
                  {cwi_metrics.decorrelation_kd.toFixed(4)}
                </div>
              </div>
              <div style={{ background: '#131826', padding: '8px', borderRadius: '6px' }}>
                <div style={{ color: '#64748b' }}>Elastic Modulus (ΔM/M)</div>
                <div style={{ color: '#cbd5e1', fontSize: '0.95rem', fontWeight: 700 }}>
                  {cwi_metrics.elastic_modulus_shift_pct > 0 ? `+${cwi_metrics.elastic_modulus_shift_pct}%` : `${cwi_metrics.elastic_modulus_shift_pct}%`}
                </div>
              </div>
              <div style={{ background: '#131826', padding: '8px', borderRadius: '6px' }}>
                <div style={{ color: '#64748b' }}>Nonlinear Harmonic β</div>
                <div style={{ color: '#c084fc', fontSize: '0.95rem', fontWeight: 700 }}>
                  {cwi_metrics.nonlinear_beta.toFixed(2)}
                </div>
              </div>
            </div>
          </div>

          <div style={{ background: 'rgba(0, 255, 157, 0.08)', border: '1px solid rgba(0, 255, 157, 0.25)', borderRadius: '10px', padding: '12px', fontSize: '0.74rem', color: '#94a3b8', lineHeight: '1.5' }}>
            🔊 <strong style={{ color: '#00ff9d' }}>Acoustic Coda Principle:</strong> While primary Time-of-Flight only samples a single direct path, multiple scattering in the coda reverberation window travels ~10x the cell thickness, magnifying velocity perturbations from early micro-delamination and solid electrolyte interphase softening.
          </div>
        </div>
      </div>
    </div>
  );
};

export default AcousticCWIView;
