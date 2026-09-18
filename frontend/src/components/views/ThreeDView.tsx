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

type RenderMode = 'realistic' | 'thermal' | 'acoustic' | 'xray' | 'cutaway';
type SceneMode = 'single_cell' | 'pack_module';
type ColormapType = 'thermal' | 'turbo' | 'inferno' | 'viridis';

const ThreeDView: React.FC = () => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const mode = useSelector((state: RootState) => state.mode.current);
  
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const oscCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Camera & Interaction State
  const [pitch, setPitch] = useState<number>(0.35);
  const [yaw, setYaw] = useState<number>(0.78);
  const [zoom, setZoom] = useState<number>(1.0);
  const [autoRotate, setAutoRotate] = useState<boolean>(true);
  const [renderMode, setRenderMode] = useState<RenderMode>('realistic');
  const [sceneMode, setSceneMode] = useState<SceneMode>('single_cell');
  const [colormap, setColormap] = useState<ColormapType>('thermal');
  const [showWireframe, setShowWireframe] = useState<boolean>(false);
  const [showOscilloscope, setShowOscilloscope] = useState<boolean>(true);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Animation pulse phase & particle state
  const wavePhaseRef = useRef<number>(0);
  const particlePhaseRef = useRef<number>(0);

  // 3D Projection Matrix math
  const project = useCallback((p: Point3D, width: number, height: number, panX: number = 0, panY: number = 0): Point2D => {
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
    const fov = 420 * zoom;
    const cameraDist = 320;
    const depth = z2 + cameraDist;
    const scale = depth > 10 ? fov / depth : 1;

    return {
      x: width / 2 + panX + x2 * scale,
      y: height / 2 + panY - y2 * scale,
      depth: z2
    };
  }, [pitch, yaw, zoom]);

  // Colormap generator (Thermal, Turbo, Inferno, Viridis)
  const getColor = useCallback((tempC: number, alpha: number = 1.0): string => {
    const tNorm = Math.max(0, Math.min(1, (tempC - 20.0) / 35.0));
    let r = 0, g = 0, b = 0;

    if (colormap === 'turbo') {
      r = Math.floor(Math.sin(tNorm * Math.PI * 1.5) * 127 + 128);
      g = Math.floor(Math.sin(tNorm * Math.PI) * 255);
      b = Math.floor(Math.cos(tNorm * Math.PI * 1.5) * 127 + 128);
    } else if (colormap === 'inferno') {
      r = Math.floor(Math.min(255, tNorm * 300));
      g = Math.floor(Math.max(0, (tNorm - 0.3) * 350));
      b = Math.floor(Math.max(0, 180 - tNorm * 180));
    } else if (colormap === 'viridis') {
      r = Math.floor(68 + tNorm * 185);
      g = Math.floor(1 + tNorm * 230);
      b = Math.floor(84 + (1 - tNorm) * 120);
    } else {
      // Thermal Cool-Warm
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
    }
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }, [colormap]);

  // Render Oscilloscope waveform on secondary canvas
  const renderOscilloscope = useCallback(() => {
    const canvas = oscCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Dark grid background
    ctx.fillStyle = 'rgba(10, 15, 26, 0.92)';
    ctx.fillRect(0, 0, w, h);

    // Reticle Grid
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.15)';
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 20) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 15) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    const tof = frame?.ultrasonic_timeOfFlight || 8.0;
    const atten = frame?.ultrasonic_amplitude || 1.0;
    const degMode = frame?.degradation_mode || 'healthy';

    // Baseline excitation pulse & Echo pulse simulation
    ctx.strokeStyle = degMode === 'gas_generation' ? '#ff00ff' : '#00ffff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    const cy = h / 2;
    const numPoints = w;
    for (let x = 0; x < numPoints; x++) {
      const t_us = (x / w) * 16.0; // 0 to 16 us window
      
      // Tx Excitation Spike at t = 0.5 us
      let yVal = 0;
      if (t_us >= 0.2 && t_us <= 1.2) {
        yVal += Math.sin((t_us - 0.2) * Math.PI * 8) * Math.exp(-(t_us - 0.2) * 4) * 35;
      }

      // Rx Echo Pulse centered at ToF
      const dt = t_us - tof;
      if (Math.abs(dt) < 2.5) {
        const phase = degMode === 'li_plating' ? Math.PI : 0;
        const envelope = Math.exp(-dt * dt * 2.0);
        yVal += Math.sin(dt * Math.PI * 6 + phase) * envelope * 28 * atten;
      }

      // Add slight noise floor
      yVal += (Math.random() - 0.5) * 1.5;

      const py = cy - yVal;
      if (x === 0) ctx.moveTo(x, py);
      else ctx.lineTo(x, py);
    }
    ctx.stroke();

    // ToF Indicator Marker Line
    const markerX = (tof / 16.0) * w;
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(markerX, 0);
    ctx.lineTo(markerX, h);
    ctx.stroke();
    ctx.setLineDash([]);

    // Text labels
    ctx.fillStyle = '#38bdf8';
    ctx.font = '9px monospace';
    ctx.fillText(`ToF: ${tof.toFixed(2)} µs`, markerX + 4, 12);
    ctx.fillText(`Amp: ${(atten * 100).toFixed(0)}%`, 6, h - 6);
  }, [frame]);

  // Main Canvas Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let localYaw = yaw;

    const render = () => {
      if (autoRotate && !isDragging) {
        localYaw += 0.005;
        setYaw(localYaw);
      }
      wavePhaseRef.current = (wavePhaseRef.current + 0.05) % (Math.PI * 2);
      particlePhaseRef.current = (particlePhaseRef.current + 0.03) % 1.0;

      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      // Deep space workstation gradient
      const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
      bgGrad.addColorStop(0, '#070b12');
      bgGrad.addColorStop(0.5, '#0d1527');
      bgGrad.addColorStop(1, '#131f38');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // High-precision Grid Floor
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.12)';
      ctx.lineWidth = 1;
      const gridSize = 180;
      const gridSteps = 9;
      for (let i = -gridSteps; i <= gridSteps; i++) {
        const p1 = project({ x: (i * gridSize) / gridSteps, y: -90, z: -gridSize }, width, height);
        const p2 = project({ x: (i * gridSize) / gridSteps, y: -90, z: gridSize }, width, height);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();

        const p3 = project({ x: -gridSize, y: -90, z: (i * gridSize) / gridSteps }, width, height);
        const p4 = project({ x: gridSize, y: -90, z: (i * gridSize) / gridSteps }, width, height);
        ctx.beginPath();
        ctx.moveTo(p3.x, p3.y);
        ctx.lineTo(p4.x, p4.y);
        ctx.stroke();
      }

      const degMode = frame?.degradation_mode || 'healthy';
      const cellTemp = frame?.thermal_temperature || 25.0;

      // Single Cell or 4S Pack Module Rendering
      const cellOffsets = sceneMode === 'single_cell' 
        ? [{ x: 0, z: 0, id: 'CELL-01', temp: cellTemp, soc: frame?.simulation_soc || 0.5 }]
        : [
            { x: -90, z: -20, id: 'CELL-1', temp: cellTemp + 1.2, soc: 0.85 },
            { x: -30, z: 0,   id: 'CELL-2', temp: cellTemp, soc: 0.65 },
            { x: 30,  z: 0,   id: 'CELL-3', temp: cellTemp - 0.8, soc: 0.42 },
            { x: 90,  z: -20, id: 'CELL-4', temp: cellTemp + 3.5, soc: 0.28 }
          ];

      const cellRadius = sceneMode === 'single_cell' ? 44 : 24;
      const cellHeight = sceneMode === 'single_cell' ? 140 : 80;
      const numSegments = sceneMode === 'single_cell' ? 32 : 18;
      const numRings = sceneMode === 'single_cell' ? 12 : 6;

      // Draw Cells
      cellOffsets.forEach((cOffset, cellIdx) => {
        // Render Cylinder Mesh
        for (let r = 0; r < numRings - 1; r++) {
          const yTop = -cellHeight / 2 + (r * cellHeight) / (numRings - 1);
          const yBot = -cellHeight / 2 + ((r + 1) * cellHeight) / (numRings - 1);

          for (let s = 0; s < numSegments; s++) {
            // Cutaway Mode: peel back quadrant 0..8
            if (renderMode === 'cutaway' && s < numSegments / 3 && sceneMode === 'single_cell') {
              continue; // Expose interior jellyroll
            }

            const a1 = (s * Math.PI * 2) / numSegments;
            const a2 = ((s + 1) * Math.PI * 2) / numSegments;

            let quadTemp = cOffset.temp;
            if (degMode === 'internal_short' && cellIdx === 0) {
              const isHotspot = Math.abs(s - numSegments / 4) < 4 && Math.abs(r - numRings / 2) < 3;
              quadTemp = isHotspot ? cellTemp + 22.0 : cellTemp + 4.0;
            } else if (degMode === 'li_plating') {
              quadTemp = cOffset.temp + Math.sin(a1 * 2) * 1.8;
            }

            const p1 = project({ x: cOffset.x + cellRadius * Math.cos(a1), y: yTop, z: cOffset.z + cellRadius * Math.sin(a1) }, width, height);
            const p2 = project({ x: cOffset.x + cellRadius * Math.cos(a2), y: yTop, z: cOffset.z + cellRadius * Math.sin(a2) }, width, height);
            const p3 = project({ x: cOffset.x + cellRadius * Math.cos(a2), y: yBot, z: cOffset.z + cellRadius * Math.sin(a2) }, width, height);
            const p4 = project({ x: cOffset.x + cellRadius * Math.cos(a1), y: yBot, z: cOffset.z + cellRadius * Math.sin(a1) }, width, height);

            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.lineTo(p3.x, p3.y);
            ctx.lineTo(p4.x, p4.y);
            ctx.closePath();

            if (renderMode === 'thermal') {
              ctx.fillStyle = getColor(quadTemp, 0.85);
              ctx.fill();
            } else if (renderMode === 'xray') {
              ctx.fillStyle = 'rgba(14, 165, 233, 0.15)';
              ctx.fill();
            } else if (renderMode === 'cutaway') {
              const shade = Math.floor(140 + 70 * Math.cos(a1 - yaw));
              ctx.fillStyle = `rgba(${shade - 15}, ${shade}, ${shade + 25}, 0.88)`;
              ctx.fill();
            } else {
              // Realistic Metallic Shader with Specular Shading
              const lightNorm = Math.cos(a1 - yaw);
              const specular = Math.pow(Math.max(0, lightNorm), 4) * 60;
              const shade = Math.min(255, Math.floor(120 + 80 * Math.max(0, lightNorm) + specular));
              ctx.fillStyle = `rgba(${shade - 20}, ${shade}, ${shade + 30}, 0.92)`;
              ctx.fill();
            }

            if (showWireframe || renderMode === 'xray') {
              ctx.strokeStyle = 'rgba(255, 255, 255, 0.18)';
              ctx.lineWidth = 0.8;
              ctx.stroke();
            }
          }
        }

        // Cutaway Interior Jellyroll layers (Anode, Separator, Cathode, Central Pin)
        if (renderMode === 'cutaway' && sceneMode === 'single_cell') {
          // Central Steel Mandrel Pin
          const pinRad = 8;
          for (let s = 0; s < 12; s++) {
            const a1 = (s * Math.PI * 2) / 12;
            const a2 = ((s + 1) * Math.PI * 2) / 12;
            const pt1 = project({ x: pinRad * Math.cos(a1), y: cellHeight / 2, z: pinRad * Math.sin(a1) }, width, height);
            const pt2 = project({ x: pinRad * Math.cos(a2), y: cellHeight / 2, z: pinRad * Math.sin(a2) }, width, height);
            const pt3 = project({ x: pinRad * Math.cos(a2), y: -cellHeight / 2, z: pinRad * Math.sin(a2) }, width, height);
            const pt4 = project({ x: pinRad * Math.cos(a1), y: -cellHeight / 2, z: pinRad * Math.sin(a1) }, width, height);
            ctx.beginPath();
            ctx.moveTo(pt1.x, pt1.y);
            ctx.lineTo(pt2.x, pt2.y);
            ctx.lineTo(pt3.x, pt3.y);
            ctx.lineTo(pt4.x, pt4.y);
            ctx.closePath();
            ctx.fillStyle = '#64748b';
            ctx.fill();
          }

          // Spiral Jellyroll Layers (Copper Anode Foil + NMC Cathode)
          const numSpirals = 24;
          for (let sp = 0; sp < numSpirals; sp++) {
            const rSpiral = pinRad + (sp * (cellRadius - pinRad)) / numSpirals;
            const ang = sp * 0.4 + wavePhaseRef.current * 0.2;
            const pLayer = project({ x: rSpiral * Math.cos(ang), y: 0, z: rSpiral * Math.sin(ang) }, width, height);
            ctx.beginPath();
            ctx.arc(pLayer.x, pLayer.y, 2.5, 0, Math.PI * 2);
            ctx.fillStyle = sp % 2 === 0 ? '#b45309' : '#0284c7'; // Copper vs Aluminum/NMC
            ctx.fill();
          }
        }

        // Positive Terminal Brass Cap
        const capRadius = cellRadius * 0.45;
        const capTop = cellHeight / 2 + (sceneMode === 'single_cell' ? 12 : 6);
        ctx.beginPath();
        for (let s = 0; s <= numSegments; s++) {
          const a = (s * Math.PI * 2) / numSegments;
          const pt = project({ x: cOffset.x + capRadius * Math.cos(a), y: capTop, z: cOffset.z + capRadius * Math.sin(a) }, width, height);
          if (s === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        }
        ctx.fillStyle = '#fbbf24';
        ctx.fill();
        ctx.strokeStyle = '#d97706';
        ctx.stroke();

        // Cell Label Tag
        const tagPos = project({ x: cOffset.x, y: -cellHeight / 2 - 16, z: cOffset.z }, width, height);
        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px monospace';
        ctx.fillText(`${cOffset.id} (${(cOffset.soc * 100).toFixed(0)}%)`, tagPos.x - 22, tagPos.y);
      });

      // Nickel Busbars in Pack Mode
      if (sceneMode === 'pack_module') {
        ctx.strokeStyle = '#94a3b8';
        ctx.lineWidth = 4;
        ctx.beginPath();
        const pBus1 = project({ x: cellOffsets[0].x, y: cellHeight / 2 + 6, z: cellOffsets[0].z }, width, height);
        const pBus2 = project({ x: cellOffsets[1].x, y: cellHeight / 2 + 6, z: cellOffsets[1].z }, width, height);
        const pBus3 = project({ x: cellOffsets[2].x, y: cellHeight / 2 + 6, z: cellOffsets[2].z }, width, height);
        const pBus4 = project({ x: cellOffsets[3].x, y: cellHeight / 2 + 6, z: cellOffsets[3].z }, width, height);
        ctx.moveTo(pBus1.x, pBus1.y);
        ctx.lineTo(pBus2.x, pBus2.y);
        ctx.lineTo(pBus3.x, pBus3.y);
        ctx.lineTo(pBus4.x, pBus4.y);
        ctx.stroke();

        // Active Rebalancer Energy Shuttle Bezier Arcs (High SOC to Low SOC)
        const pHigh = project({ x: cellOffsets[0].x, y: cellHeight / 2 + 15, z: cellOffsets[0].z }, width, height);
        const pLow = project({ x: cellOffsets[3].x, y: cellHeight / 2 + 15, z: cellOffsets[3].z }, width, height);
        const pMid = project({ x: 0, y: cellHeight / 2 + 65, z: 0 }, width, height);

        ctx.strokeStyle = 'rgba(16, 185, 129, 0.75)';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(pHigh.x, pHigh.y);
        ctx.quadraticCurveTo(pMid.x, pMid.y, pLow.x, pLow.y);
        ctx.stroke();

        // Animated Charge Energy Packet
        const tP = particlePhaseRef.current;
        const qx = (1 - tP) * (1 - tP) * pHigh.x + 2 * (1 - tP) * tP * pMid.x + tP * tP * pLow.x;
        const qy = (1 - tP) * (1 - tP) * pHigh.y + 2 * (1 - tP) * tP * pMid.y + tP * tP * pLow.y;

        ctx.beginPath();
        ctx.arc(qx, qy, 6, 0, Math.PI * 2);
        ctx.fillStyle = '#10b981';
        ctx.shadowColor = '#34d399';
        ctx.shadowBlur = 12;
        ctx.fill();
        ctx.shadowBlur = 0; // reset
      }

      // Single Cell Transducers & Acoustic Beam Rays
      if (sceneMode === 'single_cell') {
        const txPos = { x: -cellRadius - 10, y: 0, z: 0 };
        const rxPos = { x: cellRadius + 10, y: 0, z: 0 };
        const pTx = project(txPos, width, height);
        const pRx = project(rxPos, width, height);

        // Transducer Blocks
        ctx.fillStyle = '#0ea5e9';
        ctx.fillRect(pTx.x - 8, pTx.y - 8, 16, 16);
        ctx.fillStyle = '#ffffff';
        ctx.font = '10px monospace';
        ctx.fillText('Tx', pTx.x - 6, pTx.y - 12);

        ctx.fillStyle = '#10b981';
        ctx.fillRect(pRx.x - 8, pRx.y - 8, 16, 16);
        ctx.fillStyle = '#ffffff';
        ctx.fillText('Rx', pRx.x - 6, pRx.y - 12);

        // Acoustic Wavefront Propagation Rays
        const numRays = 7;
        const waveAtten = frame?.ultrasonic_amplitude || 1.0;

        for (let i = 0; i < numRays; i++) {
          const yOff = ((i - (numRays - 1) / 2) * cellHeight * 0.38) / numRays;
          const rStart = project({ x: -cellRadius, y: yOff, z: 0 }, width, height);
          const rEnd = project({ x: cellRadius, y: yOff, z: 0 }, width, height);

          // Animated acoustic pulse
          const wavePulseX = -cellRadius + ((wavePhaseRef.current * 28) % (cellRadius * 2));
          const pPulse = project({ x: wavePulseX, y: yOff, z: 0 }, width, height);

          ctx.beginPath();
          ctx.moveTo(rStart.x, rStart.y);
          ctx.lineTo(rEnd.x, rEnd.y);
          ctx.strokeStyle = degMode === 'gas_generation' 
            ? 'rgba(236, 72, 153, 0.4)' 
            : `rgba(14, 165, 233, ${0.25 * waveAtten})`;
          ctx.lineWidth = 2;
          ctx.stroke();

          ctx.beginPath();
          ctx.arc(pPulse.x, pPulse.y, 4, 0, Math.PI * 2);
          ctx.fillStyle = degMode === 'gas_generation' ? '#ec4899' : '#38bdf8';
          ctx.fill();
        }

        // Degradation Anomaly Overlays
        if (degMode === 'li_plating') {
          for (let i = 0; i < 20; i++) {
            const ang = (i * Math.PI * 2) / 20;
            const dPos = project({
              x: (cellRadius - 2) * Math.cos(ang),
              y: (Math.sin(i * 1.7) * cellHeight) / 3,
              z: (cellRadius - 2) * Math.sin(ang)
            }, width, height);
            ctx.beginPath();
            ctx.arc(dPos.x, dPos.y, 3, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(45, 212, 191, 0.85)';
            ctx.fill();
          }
        } else if (degMode === 'gas_generation') {
          for (let i = 0; i < 14; i++) {
            const bPos = project({
              x: Math.sin(i * 2.3) * cellRadius * 0.65,
              y: Math.cos(i * 1.7) * cellHeight * 0.35,
              z: Math.sin(i * 0.9) * cellRadius * 0.65
            }, width, height);
            ctx.beginPath();
            ctx.arc(bPos.x, bPos.y, 5 + (i % 4), 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(236, 72, 153, 0.65)';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        } else if (degMode === 'internal_short') {
          const defectPos = project({ x: 4, y: 0, z: 4 }, width, height);
          const radPulse = 14 + Math.sin(wavePhaseRef.current * 4) * 4;
          ctx.beginPath();
          ctx.arc(defectPos.x, defectPos.y, radPulse, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(239, 68, 68, 0.75)';
          ctx.fill();
          ctx.strokeStyle = '#fbbf24';
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      }

      renderOscilloscope();
      animationFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [project, pitch, yaw, zoom, autoRotate, renderMode, sceneMode, colormap, showWireframe, frame, isDragging, renderOscilloscope, getColor]);

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

  // Camera Presets
  const setCameraPreset = (preset: 'iso' | 'top' | 'cutaway' | 'pack') => {
    if (preset === 'iso') {
      setPitch(0.35); setYaw(0.78); setZoom(1.0);
    } else if (preset === 'top') {
      setPitch(1.50); setYaw(0.0); setZoom(1.1);
    } else if (preset === 'cutaway') {
      setPitch(0.20); setYaw(0.45); setZoom(1.2); setRenderMode('cutaway');
    } else if (preset === 'pack') {
      setPitch(0.40); setYaw(0.60); setZoom(0.85); setSceneMode('pack_module');
    }
  };

  if (mode !== '3d' && mode !== 'gazebo') {
    return null;
  }

  return (
    <div className="view-container three-d-view" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* View Header */}
      <div className="view-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px', background: '#0f172a', borderBottom: '1px solid #1e293b' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>🔋</span> {mode === 'gazebo' ? 'Gazebo Coupled Multi-Physics Environment' : '3D Multi-Physics & Active Rebalancing Visualizer'}
        </h2>
        <div className="view-status" style={{ display: 'flex', gap: '16px', alignItems: 'center', fontSize: '0.85rem' }}>
          <span style={{ color: '#10b981', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', background: '#10b981', borderRadius: '50%', display: 'inline-block' }} />
            {mode.toUpperCase()} STREAMING
          </span>
          <span style={{ color: '#94a3b8' }}>Frame: {frame?.frameId?.slice(0, 8) || '00000000'}</span>
          <span style={{ color: '#94a3b8' }}>
            {frame?.timestamp ? new Date(frame.timestamp * 1000).toLocaleTimeString() : '--:--:--'}
          </span>
        </div>
      </div>

      {/* 3D View Controls Toolbar */}
      <div style={{ display: 'flex', gap: '8px', padding: '10px 20px', background: '#1e293b', borderBottom: '1px solid #334155', alignItems: 'center', flexWrap: 'wrap' }}>
        {/* Scene Mode Selector */}
        <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>Scene:</span>
        <button
          onClick={() => setSceneMode('single_cell')}
          style={{
            padding: '4px 10px',
            fontSize: '0.78rem',
            borderRadius: '4px',
            border: sceneMode === 'single_cell' ? '1px solid #38bdf8' : '1px solid #475569',
            background: sceneMode === 'single_cell' ? '#0284c7' : '#334155',
            color: '#ffffff',
            cursor: 'pointer'
          }}
        >
          Single Cell
        </button>
        <button
          onClick={() => setSceneMode('pack_module')}
          style={{
            padding: '4px 10px',
            fontSize: '0.78rem',
            borderRadius: '4px',
            border: sceneMode === 'pack_module' ? '1px solid #38bdf8' : '1px solid #475569',
            background: sceneMode === 'pack_module' ? '#0284c7' : '#334155',
            color: '#ffffff',
            cursor: 'pointer'
          }}
        >
          4S Pack Module
        </button>

        <div style={{ width: '1px', height: '18px', background: '#475569', margin: '0 4px' }} />

        {/* Render Shading Mode */}
        <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>Shader:</span>
        {(['realistic', 'cutaway', 'thermal', 'acoustic', 'xray'] as RenderMode[]).map(m => (
          <button
            key={m}
            onClick={() => setRenderMode(m)}
            style={{
              padding: '4px 10px',
              fontSize: '0.78rem',
              borderRadius: '4px',
              border: renderMode === m ? '1px solid #38bdf8' : '1px solid #475569',
              background: renderMode === m ? '#0369a1' : '#334155',
              color: '#ffffff',
              cursor: 'pointer',
              textTransform: 'capitalize'
            }}
          >
            {m}
          </button>
        ))}

        <div style={{ width: '1px', height: '18px', background: '#475569', margin: '0 4px' }} />

        {/* Colormap Selector */}
        {renderMode === 'thermal' && (
          <>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>Colormap:</span>
            {(['thermal', 'turbo', 'inferno', 'viridis'] as ColormapType[]).map(c => (
              <button
                key={c}
                onClick={() => setColormap(c)}
                style={{
                  padding: '4px 8px',
                  fontSize: '0.75rem',
                  borderRadius: '4px',
                  border: colormap === c ? '1px solid #f59e0b' : '1px solid #475569',
                  background: colormap === c ? '#d97706' : '#334155',
                  color: '#ffffff',
                  cursor: 'pointer',
                  textTransform: 'capitalize'
                }}
              >
                {c}
              </button>
            ))}
            <div style={{ width: '1px', height: '18px', background: '#475569', margin: '0 4px' }} />
          </>
        )}

        {/* Camera Presets */}
        <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>Camera:</span>
        <button
          onClick={() => setCameraPreset('iso')}
          style={{ padding: '4px 8px', fontSize: '0.75rem', borderRadius: '4px', border: '1px solid #475569', background: '#334155', color: '#f8fafc', cursor: 'pointer' }}
        >
          Iso 3D
        </button>
        <button
          onClick={() => setCameraPreset('top')}
          style={{ padding: '4px 8px', fontSize: '0.75rem', borderRadius: '4px', border: '1px solid #475569', background: '#334155', color: '#f8fafc', cursor: 'pointer' }}
        >
          Top Ortho
        </button>
        <button
          onClick={() => setCameraPreset('cutaway')}
          style={{ padding: '4px 8px', fontSize: '0.75rem', borderRadius: '4px', border: '1px solid #475569', background: '#334155', color: '#f8fafc', cursor: 'pointer' }}
        >
          Cutaway
        </button>

        <div style={{ width: '1px', height: '18px', background: '#475569', margin: '0 4px' }} />

        {/* Toggles */}
        <button
          onClick={() => setAutoRotate(!autoRotate)}
          style={{
            padding: '4px 10px',
            fontSize: '0.78rem',
            borderRadius: '4px',
            border: '1px solid #475569',
            background: autoRotate ? '#059669' : '#334155',
            color: '#ffffff',
            cursor: 'pointer'
          }}
        >
          {autoRotate ? '⏸ Orbit' : '▶ Orbit'}
        </button>

        <button
          onClick={() => setShowWireframe(!showWireframe)}
          style={{
            padding: '4px 10px',
            fontSize: '0.78rem',
            borderRadius: '4px',
            border: '1px solid #475569',
            background: showWireframe ? '#7c3aed' : '#334155',
            color: '#ffffff',
            cursor: 'pointer'
          }}
        >
          Wireframe
        </button>

        <button
          onClick={() => setShowOscilloscope(!showOscilloscope)}
          style={{
            padding: '4px 10px',
            fontSize: '0.78rem',
            borderRadius: '4px',
            border: '1px solid #475569',
            background: showOscilloscope ? '#0284c7' : '#334155',
            color: '#ffffff',
            cursor: 'pointer'
          }}
        >
          Scope
        </button>
      </div>

      {/* 3D Canvas Container */}
      <div style={{ position: 'relative', flex: 1, minHeight: '500px', overflow: 'hidden' }}>
        <canvas
          ref={canvasRef}
          width={920}
          height={540}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
          style={{ width: '100%', height: '100%', cursor: isDragging ? 'grabbing' : 'grab' }}
        />

        {/* Floating Telemetry HUD (Glassmorphic Top-Left) */}
        <div style={{
          position: 'absolute',
          top: '16px',
          left: '16px',
          background: 'rgba(15, 23, 42, 0.88)',
          backdropFilter: 'blur(10px)',
          border: '1px solid #334155',
          borderRadius: '10px',
          padding: '12px 18px',
          color: '#f8fafc',
          fontSize: '0.82rem',
          lineHeight: '1.6',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
          pointerEvents: 'none'
        }}>
          <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.85rem' }}>
            Multi-Modal Telemetry
          </div>
          <div><strong>Degradation State:</strong> <span style={{ color: '#fbbf24', fontWeight: 600 }}>{frame?.degradation_mode?.replace(/_/g, ' ') || 'healthy'}</span></div>
          <div><strong>State of Health:</strong> {frame?.stateOfHealth_value?.toFixed(1) || '98.5'}%</div>
          <div><strong>Terminal Voltage:</strong> {frame?.electrical_voltage?.toFixed(3) || '3.700'} V</div>
          <div><strong>Surface Temp:</strong> {frame?.thermal_temperature?.toFixed(1) || '25.0'} °C</div>
          <div><strong>Acoustic ToF:</strong> {frame?.ultrasonic_timeOfFlight?.toFixed(2) || '8.00'} µs</div>
          <div><strong>Sound Velocity:</strong> {frame?.ultrasonic_speedOfSound?.toFixed(0) || '2500'} m/s</div>
          <div><strong>Rebalancer:</strong> <span style={{ color: (frame?.rebalancing_state?.toLowerCase().includes('lockout') || frame?.rebalancing_state?.toLowerCase().includes('isolated')) ? '#ef4444' : '#10b981', fontWeight: 600 }}>{frame?.rebalancing_state || 'IDLE'}</span></div>
          <div><strong>Efficiency:</strong> <span style={{ color: '#34d399', fontWeight: 600 }}>92.4% (ZVS Stage)</span></div>
        </div>

        {/* Embedded Ultrasonic RF Oscilloscope (Bottom-Left) */}
        {showOscilloscope && (
          <div style={{
            position: 'absolute',
            bottom: '16px',
            left: '16px',
            background: 'rgba(15, 23, 42, 0.92)',
            backdropFilter: 'blur(8px)',
            border: '1px solid #334155',
            borderRadius: '8px',
            padding: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
          }}>
            <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#38bdf8', marginBottom: '4px', letterSpacing: '0.05em' }}>
              ULTRASONIC RF PULSE-ECHO (10 MHz)
            </div>
            <canvas ref={oscCanvasRef} width={260} height={100} style={{ display: 'block', borderRadius: '4px' }} />
          </div>
        )}

        {/* Interactive Guide / Legend (Bottom-Right) */}
        <div style={{
          position: 'absolute',
          bottom: '16px',
          right: '16px',
          background: 'rgba(15, 23, 42, 0.88)',
          backdropFilter: 'blur(10px)',
          border: '1px solid #334155',
          borderRadius: '8px',
          padding: '10px 14px',
          color: '#94a3b8',
          fontSize: '0.76rem',
          lineHeight: '1.4'
        }}>
          <div>🖱 <strong>Left Drag:</strong> 3D Orbit Camera</div>
          <div>⚙ <strong>Scroll:</strong> Zoom Perspective</div>
          <div>✨ <strong>Green Arcs:</strong> Active Rebalance Shuttling</div>
        </div>
      </div>
    </div>
  );
};

export default ThreeDView;