import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';

interface Point3D {
  x: number;
  y: number;
  z: number;
}

interface Point2D {
  x: number;
  y: number;
  depth: number;
}

type RenderMode = 'realistic' | 'thermal' | 'acoustic' | 'xray';

const ThreeDView: React.FC = () => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const mode = useSelector((state: RootState) => state.mode.current);
  
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Camera & Interaction State
  const [pitch, setPitch] = useState<number>(0.35);
  const [yaw, setYaw] = useState<number>(0.78);
  const [zoom, setZoom] = useState<number>(1.0);
  const [autoRotate, setAutoRotate] = useState<boolean>(true);
  const [renderMode, setRenderMode] = useState<RenderMode>('realistic');
  const [showWireframe, setShowWireframe] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Animation pulse phase
  const wavePhaseRef = useRef<number>(0);

  // 3D Projection Matrix math
  const project = useCallback((p: Point3D, width: number, height: number): Point2D => {
    // 1. Rotate around Y (yaw)
    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const x1 = p.x * cosY + p.z * sinY;
    const y1 = p.y;
    const z1 = -p.x * sinY + p.z * cosY;

    // 2. Rotate around X (pitch)
    const cosP = Math.cos(pitch);
    const sinP = Math.sin(pitch);
    const x2 = x1;
    const y2 = y1 * cosP - z1 * sinP;
    const z2 = y1 * sinP + z1 * cosP;

    // 3. Perspective Projection
    const fov = 400 * zoom;
    const cameraDist = 300;
    const depth = z2 + cameraDist;
    const scale = depth > 10 ? fov / depth : 1;

    return {
      x: width / 2 + x2 * scale,
      y: height / 2 - y2 * scale,
      depth: z2
    };
  }, [pitch, yaw, zoom]);

  // Color mapping utility for thermal gradient
  const getThermalColor = (tempC: number, alpha: number = 1.0): string => {
    const tNorm = Math.max(0, Math.min(1, (tempC - 20.0) / 35.0));
    let r = 0, g = 0, b = 0;
    if (tNorm < 0.25) {
      r = 0;
      g = Math.floor(tNorm * 4 * 255);
      b = 255;
    } else if (tNorm < 0.5) {
      r = 0;
      g = 255;
      b = Math.floor((1 - (tNorm - 0.25) * 4) * 255);
    } else if (tNorm < 0.75) {
      r = Math.floor((tNorm - 0.5) * 4 * 255);
      g = 255;
      b = 0;
    } else {
      r = 255;
      g = Math.floor((1 - (tNorm - 0.75) * 4) * 200);
      b = Math.floor((tNorm - 0.75) * 4 * 180);
    }
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  // Main Canvas Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let localYaw = yaw;

    const render = () => {
      if (autoRotate && !isDragging) {
        localYaw += 0.006;
        setYaw(localYaw);
      }
      wavePhaseRef.current = (wavePhaseRef.current + 0.05) % (Math.PI * 2);

      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      // Background gradient
      const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
      bgGrad.addColorStop(0, '#0a0e17');
      bgGrad.addColorStop(1, '#141d2f');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // Grid Floor
      ctx.strokeStyle = 'rgba(64, 120, 180, 0.15)';
      ctx.lineWidth = 1;
      const gridSize = 140;
      const gridSteps = 7;
      for (let i = -gridSteps; i <= gridSteps; i++) {
        const p1 = project({ x: (i * gridSize) / gridSteps, y: -80, z: -gridSize }, width, height);
        const p2 = project({ x: (i * gridSize) / gridSteps, y: -80, z: gridSize }, width, height);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();

        const p3 = project({ x: -gridSize, y: -80, z: (i * gridSize) / gridSteps }, width, height);
        const p4 = project({ x: gridSize, y: -80, z: (i * gridSize) / gridSteps }, width, height);
        ctx.beginPath();
        ctx.moveTo(p3.x, p3.y);
        ctx.lineTo(p4.x, p4.y);
        ctx.stroke();
      }

      // 18650 Battery Dimensions
      const cellRadius = 45;
      const cellHeight = 140;
      const numSegments = 32;
      const numRings = 12;

      const degMode = frame?.degradation_mode || 'healthy';
      const cellTemp = frame?.thermal_temperature || 25.0;

      // Draw Battery Mesh (Cylinder)
      for (let r = 0; r < numRings - 1; r++) {
        const yTop = -cellHeight / 2 + (r * cellHeight) / (numRings - 1);
        const yBot = -cellHeight / 2 + ((r + 1) * cellHeight) / (numRings - 1);

        for (let s = 0; s < numSegments; s++) {
          const a1 = (s * Math.PI * 2) / numSegments;
          const a2 = ((s + 1) * Math.PI * 2) / numSegments;

          // Spatial temperature distribution
          let quadTemp = cellTemp;
          if (degMode === 'internal_short') {
            const isHotspot = Math.abs(s - numSegments / 4) < 4 && Math.abs(r - numRings / 2) < 3;
            quadTemp = isHotspot ? cellTemp + 18.0 : cellTemp + 3.0;
          } else if (degMode === 'li_plating') {
            quadTemp = cellTemp + Math.sin(a1 * 2) * 1.5;
          }

          const p1 = project({ x: cellRadius * Math.cos(a1), y: yTop, z: cellRadius * Math.sin(a1) }, width, height);
          const p2 = project({ x: cellRadius * Math.cos(a2), y: yTop, z: cellRadius * Math.sin(a2) }, width, height);
          const p3 = project({ x: cellRadius * Math.cos(a2), y: yBot, z: cellRadius * Math.sin(a2) }, width, height);
          const p4 = project({ x: cellRadius * Math.cos(a1), y: yBot, z: cellRadius * Math.sin(a1) }, width, height);

          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.lineTo(p3.x, p3.y);
          ctx.lineTo(p4.x, p4.y);
          ctx.closePath();

          if (renderMode === 'thermal') {
            ctx.fillStyle = getThermalColor(quadTemp, 0.75);
            ctx.fill();
          } else if (renderMode === 'xray') {
            ctx.fillStyle = 'rgba(0, 180, 255, 0.15)';
            ctx.fill();
          } else {
            // Realistic Metallic Shader
            const lightNorm = Math.cos(a1 - yaw);
            const shade = Math.floor(130 + 80 * Math.max(0, lightNorm));
            ctx.fillStyle = `rgba(${shade - 20}, ${shade}, ${shade + 30}, 0.85)`;
            ctx.fill();
          }

          if (showWireframe || renderMode === 'xray') {
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
            ctx.stroke();
          }
        }
      }

      // Positive Terminal Cap
      const capRadius = cellRadius * 0.45;
      const capHeight = 12;
      const capTop = cellHeight / 2 + capHeight;
      const capCenter = project({ x: 0, y: capTop, z: 0 }, width, height);

      ctx.beginPath();
      for (let s = 0; s <= numSegments; s++) {
        const a = (s * Math.PI * 2) / numSegments;
        const pt = project({ x: capRadius * Math.cos(a), y: capTop, z: capRadius * Math.sin(a) }, width, height);
        if (s === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      }
      ctx.fillStyle = '#d4af37';
      ctx.fill();
      ctx.strokeStyle = '#b8860b';
      ctx.stroke();

      // Ultrasonic Transducers (Tx: Left, Rx: Right)
      const txPos = { x: -cellRadius - 10, y: 0, z: 0 };
      const rxPos = { x: cellRadius + 10, y: 0, z: 0 };
      const pTx = project(txPos, width, height);
      const pRx = project(rxPos, width, height);

      // Draw Transducer Blocks
      ctx.fillStyle = '#00d2ff';
      ctx.fillRect(pTx.x - 8, pTx.y - 8, 16, 16);
      ctx.fillStyle = '#ffffff';
      ctx.font = '10px monospace';
      ctx.fillText('US Tx', pTx.x - 14, pTx.y - 12);

      ctx.fillStyle = '#00ff88';
      ctx.fillRect(pRx.x - 8, pRx.y - 8, 16, 16);
      ctx.fillStyle = '#ffffff';
      ctx.fillText('US Rx', pRx.x - 14, pRx.y - 12);

      // Ultrasonic Acoustic Wavefront Propagation Rays
      if (renderMode === 'acoustic' || renderMode === 'realistic' || renderMode === 'xray') {
        const numRays = 7;
        const waveAtten = frame?.ultrasonic_amplitude || 1.0;

        for (let i = 0; i < numRays; i++) {
          const yOff = ((i - (numRays - 1) / 2) * cellHeight * 0.4) / numRays;
          const rStart = project({ x: -cellRadius, y: yOff, z: 0 }, width, height);
          const rEnd = project({ x: cellRadius, y: yOff, z: 0 }, width, height);

          // Animated acoustic pulses
          const wavePulseX = -cellRadius + ((wavePhaseRef.current * 25) % (cellRadius * 2));
          const pPulse = project({ x: wavePulseX, y: yOff, z: 0 }, width, height);

          ctx.beginPath();
          ctx.moveTo(rStart.x, rStart.y);
          ctx.lineTo(rEnd.x, rEnd.y);
          ctx.strokeStyle = degMode === 'gas_generation' 
            ? 'rgba(255, 100, 255, 0.35)' 
            : `rgba(0, 210, 255, ${0.2 * waveAtten})`;
          ctx.lineWidth = 2;
          ctx.stroke();

          // Animated pulse circle
          ctx.beginPath();
          ctx.arc(pPulse.x, pPulse.y, 4, 0, Math.PI * 2);
          ctx.fillStyle = degMode === 'gas_generation' ? '#ff00ff' : '#00ffff';
          ctx.fill();
        }
      }

      // Degradation Overlays
      if (degMode === 'li_plating') {
        for (let i = 0; i < 18; i++) {
          const ang = (i * Math.PI * 2) / 18;
          const dPos = project({
            x: (cellRadius - 2) * Math.cos(ang),
            y: (Math.sin(i * 1.5) * cellHeight) / 3,
            z: (cellRadius - 2) * Math.sin(ang)
          }, width, height);
          ctx.beginPath();
          ctx.arc(dPos.x, dPos.y, 3, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(0, 255, 200, 0.8)';
          ctx.fill();
        }
      } else if (degMode === 'gas_generation') {
        for (let i = 0; i < 12; i++) {
          const bPos = project({
            x: Math.sin(i * 2.3) * cellRadius * 0.6,
            y: Math.cos(i * 1.7) * cellHeight * 0.35,
            z: Math.sin(i * 0.9) * cellRadius * 0.6
          }, width, height);
          ctx.beginPath();
          ctx.arc(bPos.x, bPos.y, 5 + (i % 4), 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(255, 80, 200, 0.6)';
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      } else if (degMode === 'internal_short') {
        const defectPos = project({ x: 5, y: 0, z: 5 }, width, height);
        const radPulse = 12 + Math.sin(wavePhaseRef.current * 4) * 4;
        ctx.beginPath();
        ctx.arc(defectPos.x, defectPos.y, radPulse, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255, 0, 0, 0.7)';
        ctx.fill();
        ctx.strokeStyle = '#ffff00';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Active Rebalancing Power Stage Module (Bottom Right)
      const convPos = { x: 70, y: -70, z: 40 };
      const pConv = project(convPos, width, height);
      ctx.fillStyle = frame?.rebalancing_safetyStatus === 'critical_lockout_isolated' 
        ? '#ff3333' 
        : '#ff9900';
      ctx.fillRect(pConv.x - 12, pConv.y - 12, 24, 24);
      ctx.fillStyle = '#ffffff';
      ctx.font = '10px monospace';
      ctx.fillText('DC-DC Balancer', pConv.x - 30, pConv.y + 24);

      // Draw Current Flow Vectors
      if (frame?.rebalancing_powerStage_targetCurrent && frame.rebalancing_powerStage_targetCurrent > 0) {
        ctx.beginPath();
        ctx.moveTo(capCenter.x, capCenter.y);
        ctx.lineTo(pConv.x, pConv.y);
        ctx.strokeStyle = 'rgba(0, 255, 100, 0.8)';
        ctx.lineWidth = 3;
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      animationFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [project, pitch, yaw, zoom, autoRotate, renderMode, showWireframe, frame, isDragging]);

  // Mouse drag interaction
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStart.x;
    const dy = e.clientY - dragStart.y;
    setYaw(y => y + dx * 0.008);
    setPitch(p => Math.max(-Math.PI / 2 + 0.1, Math.min(Math.PI / 2 - 0.1, p - dy * 0.008)));
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    setZoom(z => Math.max(0.4, Math.min(2.5, z - e.deltaY * 0.001)));
  };

  if (mode !== '3d' && mode !== 'gazebo') {
    return null;
  }

  return (
    <div className="view-container three-d-view" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="view-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px', background: '#111827', borderBottom: '1px solid #1f2937' }}>
        <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#f3f4f6' }}>
          🔋 {mode === 'gazebo' ? 'Gazebo Multi-Physics Engine' : '3D Multi-Modal Cell Simulator'}
        </h2>
        <div className="view-status" style={{ display: 'flex', gap: '16px', alignItems: 'center', fontSize: '0.875rem' }}>
          <span style={{ color: '#10b981', fontWeight: 600 }}>● {mode.toUpperCase()} LIVE</span>
          <span style={{ color: '#9ca3af' }}>Frame: {frame?.frameId?.slice(0, 8) || '00000000'}</span>
          <span style={{ color: '#9ca3af' }}>
            {frame?.timestamp ? new Date(frame.timestamp * 1000).toLocaleTimeString() : '--:--:--'}
          </span>
        </div>
      </div>

      {/* 3D View Toolbar */}
      <div style={{ display: 'flex', gap: '10px', padding: '8px 20px', background: '#1e293b', borderBottom: '1px solid #334155', alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>View Mode:</span>
        {(['realistic', 'thermal', 'acoustic', 'xray'] as RenderMode[]).map(m => (
          <button
            key={m}
            onClick={() => setRenderMode(m)}
            style={{
              padding: '4px 12px',
              fontSize: '0.8rem',
              borderRadius: '4px',
              border: renderMode === m ? '1px solid #38bdf8' : '1px solid #475569',
              background: renderMode === m ? '#0284c7' : '#334155',
              color: '#ffffff',
              cursor: 'pointer',
              textTransform: 'capitalize'
            }}
          >
            {m}
          </button>
        ))}

        <div style={{ width: '1px', height: '20px', background: '#475569', margin: '0 8px' }} />

        <button
          onClick={() => setAutoRotate(!autoRotate)}
          style={{
            padding: '4px 12px',
            fontSize: '0.8rem',
            borderRadius: '4px',
            border: '1px solid #475569',
            background: autoRotate ? '#10b981' : '#334155',
            color: '#ffffff',
            cursor: 'pointer'
          }}
        >
          {autoRotate ? '⏸ Pause Orbit' : '▶ Auto Orbit'}
        </button>

        <button
          onClick={() => setShowWireframe(!showWireframe)}
          style={{
            padding: '4px 12px',
            fontSize: '0.8rem',
            borderRadius: '4px',
            border: '1px solid #475569',
            background: showWireframe ? '#8b5cf6' : '#334155',
            color: '#ffffff',
            cursor: 'pointer'
          }}
        >
          Wireframe
        </button>

        <button
          onClick={() => { setPitch(0.35); setYaw(0.78); setZoom(1.0); }}
          style={{
            padding: '4px 12px',
            fontSize: '0.8rem',
            borderRadius: '4px',
            border: '1px solid #475569',
            background: '#334155',
            color: '#ffffff',
            cursor: 'pointer'
          }}
        >
          ↺ Reset Cam
        </button>
      </div>

      {/* 3D Canvas Container */}
      <div style={{ position: 'relative', flex: 1, minHeight: '480px', overflow: 'hidden' }}>
        <canvas
          ref={canvasRef}
          width={880}
          height={520}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
          style={{ width: '100%', height: '100%', cursor: isDragging ? 'grabbing' : 'grab' }}
        />

        {/* Floating Telemetry HUD */}
        <div style={{
          position: 'absolute',
          top: '16px',
          left: '16px',
          background: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(8px)',
          border: '1px solid #334155',
          borderRadius: '8px',
          padding: '12px 16px',
          color: '#f8fafc',
          fontSize: '0.82rem',
          lineHeight: '1.5',
          pointerEvents: 'none'
        }}>
          <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Multi-Modal Telemetry
          </div>
          <div><strong>Degradation:</strong> <span style={{ color: '#fbbf24' }}>{frame?.degradation_mode?.replace(/_/g, ' ') || 'healthy'}</span></div>
          <div><strong>SOH Estimate:</strong> {frame?.stateOfHealth_value?.toFixed(1) || '100.0'}%</div>
          <div><strong>Cell Voltage:</strong> {frame?.electrical_voltage?.toFixed(3) || '3.700'} V</div>
          <div><strong>Temperature:</strong> {frame?.thermal_temperature?.toFixed(1) || '25.0'} °C</div>
          <div><strong>Acoustic ToF:</strong> {frame?.ultrasonic_timeOfFlight?.toFixed(2) || '8.00'} µs</div>
          <div><strong>Sound Speed:</strong> {frame?.ultrasonic_speedOfSound?.toFixed(0) || '2500'} m/s</div>
          <div><strong>Rebalancer:</strong> <span style={{ color: frame?.rebalancing_safetyStatus === 'critical_lockout_isolated' ? '#ef4444' : '#10b981' }}>{frame?.rebalancing_state || 'IDLE'}</span></div>
        </div>

        {/* Legend */}
        <div style={{
          position: 'absolute',
          bottom: '16px',
          right: '16px',
          background: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(8px)',
          border: '1px solid #334155',
          borderRadius: '8px',
          padding: '10px 14px',
          color: '#94a3b8',
          fontSize: '0.78rem'
        }}>
          <div>🖱 Left Click + Drag: Orbit Camera</div>
          <div>⚙ Scroll Wheel: Zoom In / Out</div>
        </div>
      </div>
    </div>
  );
};

export default ThreeDView;