import React, { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';

interface NyquistPoint {
  freq_hz: number;
  z_re_mohm: number;
  neg_z_im_mohm: number;
  magnitude_mohm: number;
  phase_deg: number;
}

interface DRTPoint {
  tau_s: number;
  gamma_ohm: number;
  gamma_norm: number;
  log_tau: number;
}

interface EISData {
  nyquist: NyquistPoint[];
  drt: DRTPoint[];
  parameters: {
    r0_ohm: number;
    r_sei_ohm: number;
    r_ct_ohm: number;
    sigma_w: number;
    l_inductance_h: number;
    tau_sei_s: number;
    tau_ct_s: number;
  };
  peaks: {
    sei_peak_freq_hz: number;
    ct_peak_freq_hz: number;
    max_neg_zim_mohm: number;
  };
}

const EISNyquistView: React.FC = () => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const [eisData, setEisData] = useState<EISData | null>(null);
  const [hoveredPoint, setHoveredPoint] = useState<NyquistPoint | null>(null);
  const [activeTab, setActiveTab] = useState<'nyquist' | 'bode' | 'drt'>('nyquist');

  const fetchEIS = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/research/eis_nyquist');
      if (res.ok) {
        const data = await res.json();
        setEisData(data);
      }
    } catch (e) {
      // Backend maybe offline
    }
  };

  useEffect(() => {
    fetchEIS();
    const interval = setInterval(fetchEIS, 2000);
    return () => clearInterval(interval);
  }, [frame?.degradation_mode]);

  if (!eisData) {
    return (
      <div style={{ padding: '24px', color: '#94a3b8', textAlign: 'center' }}>
        Loading Operando EIS & DRT Spectrometer...
      </div>
    );
  }

  const { nyquist, drt, parameters, peaks } = eisData;

  // Compute SVG viewBox scales for Nyquist Plot
  const zReVals = nyquist.map(p => p.z_re_mohm);
  const negZImVals = nyquist.map(p => p.neg_z_im_mohm);
  const minX = Math.max(0, Math.min(...zReVals) - 5);
  const maxX = Math.max(...zReVals) + 10;
  const minY = Math.min(0, Math.min(...negZImVals) - 2);
  const maxY = Math.max(...negZImVals) + 8;

  const svgW = 560;
  const svgH = 320;
  const padL = 50;
  const padR = 25;
  const padT = 25;
  const padB = 40;

  const scaleX = (val: number) => padL + ((val - minX) / (maxX - minX)) * (svgW - padL - padR);
  const scaleY = (val: number) => svgH - padB - ((val - minY) / (maxY - minY)) * (svgH - padT - padB);

  // Nyquist line path
  const nyquistPath = nyquist
    .map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${scaleX(p.z_re_mohm).toFixed(1)} ${scaleY(p.neg_z_im_mohm).toFixed(1)}`)
    .join(' ');

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
              SECTION 02
            </span>
            <h2 style={{ margin: 0, fontSize: '1.05rem', color: '#f8fafc', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.02em' }}>
              Operando Electrochemical Impedance & DRT Spectrometer
            </h2>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '3px', fontFamily: 'monospace' }}>
            MULTI-ELEMENT RANDLES DECONVOLUTION • FREQ SWEEP: 0.01 Hz TO 50.0 kHz
          </div>
        </div>

        {/* View mode toggle */}
        <div style={{ display: 'flex', gap: '6px', background: '#0d111a', padding: '4px', borderRadius: '8px', border: '1px solid #1e293b' }}>
          <button
            onClick={() => setActiveTab('nyquist')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'nyquist' ? '#0284c7' : 'transparent',
              color: activeTab === 'nyquist' ? '#ffffff' : '#94a3b8',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Nyquist (Z' vs -Z'')
          </button>
          <button
            onClick={() => setActiveTab('bode')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'bode' ? '#0284c7' : 'transparent',
              color: activeTab === 'bode' ? '#ffffff' : '#94a3b8',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Bode (|Z| & Phase)
          </button>
          <button
            onClick={() => setActiveTab('drt')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'drt' ? '#0284c7' : 'transparent',
              color: activeTab === 'drt' ? '#ffffff' : '#94a3b8',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            DRT Spectrum γ(ln τ)
          </button>
        </div>
      </div>

      {/* Main Grid: Visualizer + Parameters */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(400px, 1fr) 320px', gap: '16px' }}>
        {/* Visualizer Card */}
        <div style={{ background: '#07090e', border: '1px solid #1e293b', borderRadius: '10px', padding: '16px' }}>
          {activeTab === 'nyquist' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#38bdf8' }}>
                  Nyquist Impedance Complex Plane
                </span>
                {hoveredPoint && (
                  <span style={{ fontSize: '0.72rem', color: '#00ff9d', fontFamily: 'monospace' }}>
                    f: {hoveredPoint.freq_hz < 10 ? hoveredPoint.freq_hz.toFixed(2) : Math.round(hoveredPoint.freq_hz)} Hz | Z': {hoveredPoint.z_re_mohm.toFixed(1)} mΩ | -Z'': {hoveredPoint.neg_z_im_mohm.toFixed(1)} mΩ
                  </span>
                )}
              </div>

              <svg width="100%" height={svgH} viewBox={`0 0 ${svgW} ${svgH}`} style={{ overflow: 'visible' }}>
                {/* Grid lines */}
                {[0, 0.25, 0.5, 0.75, 1.0].map(ratio => {
                  const y = scaleY(minY + ratio * (maxY - minY));
                  const x = scaleX(minX + ratio * (maxX - minX));
                  return (
                    <g key={ratio}>
                      <line x1={padL} y1={y} x2={svgW - padR} y2={y} stroke="#131d2e" strokeWidth={1} />
                      <line x1={x} y1={padT} x2={x} y2={svgH - padB} stroke="#131d2e" strokeWidth={1} />
                      <text x={padL - 6} y={y + 3} fill="#64748b" fontSize={9} textAnchor="end" fontFamily="monospace">
                        {(minY + ratio * (maxY - minY)).toFixed(0)}
                      </text>
                      <text x={x} y={svgH - padB + 14} fill="#64748b" fontSize={9} textAnchor="middle" fontFamily="monospace">
                        {(minX + ratio * (maxX - minX)).toFixed(0)}
                      </text>
                    </g>
                  );
                })}

                {/* Axes */}
                <line x1={padL} y1={svgH - padB} x2={svgW - padR} y2={svgH - padB} stroke="#334155" strokeWidth={1.5} />
                <line x1={padL} y1={padT} x2={padL} y2={svgH - padB} stroke="#334155" strokeWidth={1.5} />

                {/* Axis Labels */}
                <text x={svgW / 2} y={svgH - 6} fill="#94a3b8" fontSize={10} textAnchor="middle" fontWeight={600}>
                  Real Impedance Z' (mΩ)
                </text>
                <text x={14} y={svgH / 2} fill="#94a3b8" fontSize={10} textAnchor="middle" transform={`rotate(-90,14,${svgH / 2})`} fontWeight={600}>
                  -Imaginary Impedance -Z'' (mΩ)
                </text>

                {/* Impedance Path */}
                <path d={nyquistPath} fill="none" stroke="#00f0ff" strokeWidth={2.2} strokeLinecap="round" />

                {/* Points */}
                {nyquist.map((p, idx) => (
                  <circle
                    key={idx}
                    cx={scaleX(p.z_re_mohm)}
                    cy={scaleY(p.neg_z_im_mohm)}
                    r={hoveredPoint === p ? 5 : 2.5}
                    fill={idx < 5 ? '#ff3366' : idx > 45 ? '#ffb700' : '#00f0ff'}
                    stroke="#ffffff"
                    strokeWidth={hoveredPoint === p ? 1.5 : 0}
                    style={{ cursor: 'pointer', transition: 'r 0.15s ease' }}
                    onMouseEnter={() => setHoveredPoint(p)}
                    onMouseLeave={() => setHoveredPoint(null)}
                  />
                ))}

                {/* Characteristic Labels */}
                <text x={scaleX(parameters.r0_ohm * 1000)} y={scaleY(0) - 10} fill="#00ff9d" fontSize={9} fontWeight={700} textAnchor="middle">
                  R₀ ({((parameters.r0_ohm) * 1000).toFixed(1)} mΩ)
                </text>
              </svg>
            </div>
          )}

          {activeTab === 'drt' && (
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#a855f7', marginBottom: '8px' }}>
                Distribution of Relaxation Times γ(ln τ) [Tikhonov Ridge Inversion]
              </div>
              <svg width="100%" height={svgH} viewBox={`0 0 ${svgW} ${svgH}`}>
                {/* Baseline */}
                <line x1={padL} y1={svgH - padB} x2={svgW - padR} y2={svgH - padB} stroke="#334155" strokeWidth={1} />
                <line x1={padL} y1={padT} x2={padL} y2={svgH - padB} stroke="#334155" strokeWidth={1} />

                {/* DRT Curve */}
                {(() => {
                  const maxGamma = Math.max(...drt.map(d => d.gamma_ohm), 1e-4);
                  const minLogTau = Math.min(...drt.map(d => d.log_tau));
                  const maxLogTau = Math.max(...drt.map(d => d.log_tau));
                  const dScaleX = (logT: number) => padL + ((logT - minLogTau) / (maxLogTau - minLogTau)) * (svgW - padL - padR);
                  const dScaleY = (g: number) => svgH - padB - (g / maxGamma) * (svgH - padT - padB);

                  const pathD = drt.map((d, i) => `${i === 0 ? 'M' : 'L'} ${dScaleX(d.log_tau).toFixed(1)} ${dScaleY(d.gamma_ohm).toFixed(1)}`).join(' ');
                  const areaD = `${pathD} L ${svgW - padR} ${svgH - padB} L ${padL} ${svgH - padB} Z`;

                  return (
                    <g>
                      <path d={areaD} fill="rgba(168, 85, 247, 0.15)" />
                      <path d={pathD} fill="none" stroke="#c084fc" strokeWidth={2.2} />

                      {/* Relaxation regime zones */}
                      <text x={dScaleX(-4.0)} y={padT + 15} fill="#38bdf8" fontSize={9} textAnchor="middle" fontWeight={600}>
                        SEI Passivation (10⁻⁴ s)
                      </text>
                      <text x={dScaleX(-1.5)} y={padT + 15} fill="#f59e0b" fontSize={9} textAnchor="middle" fontWeight={600}>
                        Charge Transfer R_ct (10⁻² s)
                      </text>
                      <text x={dScaleX(0.5)} y={padT + 15} fill="#10b981" fontSize={9} textAnchor="middle" fontWeight={600}>
                        Solid Diffusion (10⁰ s)
                      </text>
                    </g>
                  );
                })()}
              </svg>
            </div>
          )}

          {activeTab === 'bode' && (
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#38bdf8', marginBottom: '8px' }}>
                Bode Magnitude & Phase Response
              </div>
              <svg width="100%" height={svgH} viewBox={`0 0 ${svgW} ${svgH}`}>
                {/* Magnitude curve */}
                {(() => {
                  const minMag = Math.min(...nyquist.map(n => n.magnitude_mohm));
                  const maxMag = Math.max(...nyquist.map(n => n.magnitude_mohm));
                  const bScaleX = (idx: number) => padL + (idx / (nyquist.length - 1)) * (svgW - padL - padR);
                  const bScaleY = (m: number) => svgH - padB - ((m - minMag) / (maxMag - minMag)) * (svgH - padT - padB);

                  const magPath = nyquist.map((n, i) => `${i === 0 ? 'M' : 'L'} ${bScaleX(i).toFixed(1)} ${bScaleY(n.magnitude_mohm).toFixed(1)}`).join(' ');
                  return <path d={magPath} fill="none" stroke="#38bdf8" strokeWidth={2} />;
                })()}
              </svg>
            </div>
          )}
        </div>

        {/* Electro-chemical Parameter Summary Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ background: '#0d111a', border: '1px solid #1e293b', borderRadius: '10px', padding: '14px' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.05em' }}>
              Deconvolved Circuit Parameters
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.76rem' }}>
              <div style={{ background: '#131826', padding: '8px', borderRadius: '6px' }}>
                <div style={{ color: '#64748b' }}>R₀ (Bulk)</div>
                <div style={{ color: '#00f0ff', fontSize: '0.95rem', fontWeight: 700 }}>
                  {(parameters.r0_ohm * 1000).toFixed(1)} mΩ
                </div>
              </div>
              <div style={{ background: '#131826', padding: '8px', borderRadius: '6px' }}>
                <div style={{ color: '#64748b' }}>R_SEI (Passivation)</div>
                <div style={{ color: '#38bdf8', fontSize: '0.95rem', fontWeight: 700 }}>
                  {(parameters.r_sei_ohm * 1000).toFixed(1)} mΩ
                </div>
              </div>
              <div style={{ background: '#131826', padding: '8px', borderRadius: '6px' }}>
                <div style={{ color: '#64748b' }}>R_ct (Charge Transfer)</div>
                <div style={{ color: '#f59e0b', fontSize: '0.95rem', fontWeight: 700 }}>
                  {(parameters.r_ct_ohm * 1000).toFixed(1)} mΩ
                </div>
              </div>
              <div style={{ background: '#131826', padding: '8px', borderRadius: '6px' }}>
                <div style={{ color: '#64748b' }}>Warburg Coefficient</div>
                <div style={{ color: '#10b981', fontSize: '0.95rem', fontWeight: 700 }}>
                  {(parameters.sigma_w * 1000).toFixed(1)} mΩ
                </div>
              </div>
            </div>
          </div>

          <div style={{ background: '#0d111a', border: '1px solid #1e293b', borderRadius: '10px', padding: '14px' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.05em' }}>
              Characteristic Relaxation Frequencies
            </div>
            <div style={{ fontSize: '0.76rem', color: '#cbd5e1', lineHeight: '1.6' }}>
              <div>• <strong>f_SEI Peak:</strong> {Math.round(peaks.sei_peak_freq_hz)} Hz</div>
              <div>• <strong>f_ct Peak:</strong> {Math.round(peaks.ct_peak_freq_hz)} Hz</div>
              <div>• <strong>Max Reactance (-Z''):</strong> {peaks.max_neg_zim_mohm.toFixed(1)} mΩ</div>
            </div>
          </div>

          <div style={{ background: 'rgba(2, 132, 199, 0.08)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: '10px', padding: '12px', fontSize: '0.74rem', color: '#94a3b8', lineHeight: '1.5' }}>
            💡 <strong style={{ color: '#38bdf8' }}>Physical Insight:</strong> Lithium plating exhibits elevated charge-transfer resistance (R_ct) with depressed phase angle due to dendritic surface roughness, whereas electrolyte decomposition shifts the high-frequency R₀ intercept.
          </div>
        </div>
      </div>
    </div>
  );
};

export default EISNyquistView;
