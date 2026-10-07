import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';
import * as THREE from 'three';

type RenderMode = 'realistic' | 'thermal' | 'acoustic' | 'xray' | 'cutaway';
type CellFormat = '18650_cylindrical' | '21700_cylindrical' | 'prismatic_100ah' | 'pouch_60ah';

interface ComponentInfo {
  id: string;
  name: string;
  icon: string;
  role: string;
  principle: string;
  specs: string;
  liveReading: string;
}

const COMPONENT_DETAILS: Record<string, ComponentInfo> = {
  clamping_actuator: {
    id: 'clamping_actuator',
    name: 'Robotic Pneumatic Clamping Gantry',
    icon: '🦾',
    role: 'Precision Mechanical Fixturing & Normal Force Regulation',
    principle: 'Dual linear ball-screw actuators apply a calibrated normal force (120 N to 450 N) ensuring zero acoustic air gaps and constant contact resistance under thermal expansion.',
    specs: 'Stroke: 150 mm | Force Range: 50–600 N | Repeatability: ±5 µm | Force Sensor: Piezo-resistive load cell',
    liveReading: 'Clamping Force: 120.0 N | Gantry Status: LOCKED & STABLE'
  },
  kelvin_probes: {
    id: 'kelvin_probes',
    name: '4-Wire Kelvin Gold-Plated Current Probes',
    icon: '⚡',
    role: 'True DC Resistance & Electrochemical Impedance Acquisition',
    principle: 'Separates current injection (Force lines) from voltage measurement (Sense lines) to eliminate lead and contact resistance, resolving sub-milliohm DC internal resistance (R0).',
    specs: 'Plating: Hard Gold over Nickel | Contact R: < 0.5 mΩ | Current Rating: 30 A continuous / 100 A pulse | Spring Force: 3.5 N/pin',
    liveReading: 'Sense Voltage: 3.650 V | Loop Current: 1.50 A | Contact Resistance: 0.22 mΩ'
  },
  ultrasonic_horns: {
    id: 'ultrasonic_horns',
    name: 'Dual 10 MHz PZT Ultrasonic Horns (Tx & Rx)',
    icon: '🔊',
    role: 'Multi-Layer Structural & State-of-Charge Acoustic Pulse-Echo',
    principle: 'Transmits 10 MHz longitudinal acoustic waves through the battery core. Time-of-Flight (ToF) tracks modulus/SoC changes, while defect reflections detect lithium dendrites and gas delamination.',
    specs: 'Frequency: 10.0 MHz | Transducer: Lead Zirconate Titanate (PZT-5A) | Wedge: Rexolite delay line | ToF Precision: 55 ps (TDC7200)',
    liveReading: 'Time-of-Flight: 8.01 µs | Velocity: 2498 m/s | Coupling SNR: 32.4 dB'
  },
  liquid_coldplate: {
    id: 'liquid_coldplate',
    name: 'Microchannel Liquid Cold-Plate & Peltier Sink',
    icon: '❄',
    role: 'Active Isothermal Heat Sink & Thermal Wave Telemetry',
    principle: 'Copper-aluminum microchannels circulate dielectric coolant with an embedded Peltier heat pump to maintain isothermal boundary conditions (25.0 ± 0.2 °C) during high-rate testing.',
    specs: 'Thermal Conductivity: 390 W/(m·K) | Heat Flux: Up to 45 W/cm² | Coolant: 50/50 Water-Glycol | Flow Rate: 1.8 L/min',
    liveReading: 'Base Temp: 24.8 °C | Coolant Flow: 1.8 L/min | Heat Flux: 3.2 W'
  },
  zvs_rebalancer: {
    id: 'zvs_rebalancer',
    name: 'Zero-Voltage-Switching (ZVS) Active Rebalancer',
    icon: '🔄',
    role: 'Non-Dissipative Bidirectional Resonant Charge Shuttling',
    principle: 'Utilizes a GaN-based resonant quasi-ZVS converter to shuttle charge from high-SoC cells to weaker cells with zero switching loss, achieving ≥92.4% efficiency without resistive bleed heat.',
    specs: 'Topology: Resonant Switched Capacitor | Switching Freq: 250 kHz | Peak Current: 3.0 A | Efficiency: ≥92.4% | Control: CAN / PWM',
    liveReading: 'Stage: ACTIVE RESONANT | Transfer Current: 2.0 A | Efficiency: 92.4% | Energy Saved: 89.2%'
  },
  cell_core: {
    id: 'cell_core',
    name: 'Battery Core & Multi-Layer Microstructure',
    icon: '🔋',
    role: 'Electrochemical Energy Storage Unit Under Test',
    principle: 'Cathode (NMC622/811), polyolefin microporous separator, and graphite anode. Acoustic and electrical impedance variations reveal degradation modes (Li plating, gas voids, loss of active material).',
    specs: 'Nominal Voltage: 3.65 V | Chemistry: LiNiMnCoO2 (NMC) / Graphite | Acoustic Z: 1.85 MRayl (separator)',
    liveReading: 'SoC: 50.0% | SoH: 91.2% | Deg Mode: HEALTHY | Layer Status: INTACT'
  }
};

const ThreeDView: React.FC = () => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const frameRef = useRef(frame);
  useEffect(() => {
    frameRef.current = frame;
  }, [frame]);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const oscCanvasRef = useRef<HTMLCanvasElement | null>(null);

  // Three.js instances
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const animFrameIdRef = useRef<number | null>(null);

  // Dynamic 3D Objects
  const cellGroupRef = useRef<THREE.Group | null>(null);
  const gantryPistonRef = useRef<THREE.Group | null>(null);
  const waveMeshRef = useRef<THREE.Mesh | null>(null);
  const arcLinesRef = useRef<THREE.Line | null>(null);
  const coolantParticlesRef = useRef<THREE.Points | null>(null);

  // Camera Spherical Orbit State
  const sphericalRef = useRef<{ radius: number; phi: number; theta: number }>({
    radius: 42,
    phi: Math.PI / 3,
    theta: 0.8
  });
  const targetRef = useRef<THREE.Vector3>(new THREE.Vector3(0, 6, 0));
  const isDraggingRef = useRef<boolean>(false);
  const prevMouseRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // UI & Controller State
  const [selectedFormat, setSelectedFormat] = useState<CellFormat>('18650_cylindrical');
  const selectedFormatRef = useRef(selectedFormat);
  useEffect(() => {
    selectedFormatRef.current = selectedFormat;
  }, [selectedFormat]);

  const [renderMode, setRenderMode] = useState<RenderMode>('realistic');
  const [showWireframe, setShowWireframe] = useState<boolean>(false);
  const [showOscilloscope, setShowOscilloscope] = useState<boolean>(true);
  const [activeComponent, setActiveComponent] = useState<ComponentInfo | null>(COMPONENT_DETAILS.clamping_actuator);
  const [cycleStage, setCycleStage] = useState<string>('IDLE');
  const [cycleProgress, setCycleProgress] = useState<number>(0);
  const [isCycleRunning, setIsCycleRunning] = useState<boolean>(false);
  
  const [autoRotate, setAutoRotate] = useState<boolean>(true);
  const autoRotateRef = useRef(autoRotate);
  useEffect(() => {
    autoRotateRef.current = autoRotate;
  }, [autoRotate]);

  const updateCameraPosition = useCallback(() => {
    if (!cameraRef.current) return;
    const s = sphericalRef.current;
    cameraRef.current.position.set(
      targetRef.current.x + s.radius * Math.sin(s.phi) * Math.sin(s.theta),
      targetRef.current.y + s.radius * Math.cos(s.phi),
      targetRef.current.z + s.radius * Math.sin(s.phi) * Math.cos(s.theta)
    );
    cameraRef.current.lookAt(targetRef.current);
  }, []);

  // 1. Initialize High-End 3D WebGL Scene ONCE on mount
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 920;
    const height = container.clientHeight || 560;

    // Create Scene, Camera, Renderer
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x070a13);
    scene.fog = new THREE.FogExp2(0x070a13, 0.008);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    cameraRef.current = camera;
    updateCameraPosition();

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    } catch (err) {
      console.warn('WebGL context creation failed (likely headless test runner).', err);
      return;
    }

    renderer.setClearColor(0x070a13, 1.0);
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.innerHTML = '';
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // --- Mouse Orbit Interaction Handlers ---
    const domEl = renderer.domElement;
    const onMouseDown = (e: MouseEvent) => {
      isDraggingRef.current = true;
      prevMouseRef.current = { x: e.clientX, y: e.clientY };
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const dx = e.clientX - prevMouseRef.current.x;
      const dy = e.clientY - prevMouseRef.current.y;
      prevMouseRef.current = { x: e.clientX, y: e.clientY };

      sphericalRef.current.theta -= dx * 0.008;
      sphericalRef.current.phi = Math.max(0.1, Math.min(Math.PI / 2 + 0.08, sphericalRef.current.phi - dy * 0.008));
      updateCameraPosition();
    };

    const onMouseUp = () => {
      isDraggingRef.current = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      sphericalRef.current.radius = Math.max(10, Math.min(80, sphericalRef.current.radius + e.deltaY * 0.04));
      updateCameraPosition();
    };

    domEl.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    domEl.addEventListener('wheel', onWheel, { passive: false });

    // --- Lighting Rig ---
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.65);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0x38bdf8, 1.2);
    dirLight1.position.set(20, 40, 20);
    dirLight1.castShadow = true;
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x10b981, 0.6);
    dirLight2.position.set(-20, 20, -20);
    scene.add(dirLight2);

    const pointLight = new THREE.PointLight(0x0284c7, 1.5, 30);
    pointLight.position.set(0, 12, 10);
    scene.add(pointLight);

    // --- Base Optical Granite Bench & Grid ---
    const benchGeo = new THREE.BoxGeometry(32, 2, 24);
    const benchMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      roughness: 0.3,
      metalness: 0.8
    });
    const bench = new THREE.Mesh(benchGeo, benchMat);
    bench.position.set(0, -1, 0);
    bench.receiveShadow = true;
    scene.add(bench);

    const grid = new THREE.GridHelper(30, 30, 0x0284c7, 0x1e293b);
    grid.position.set(0, 0.02, 0);
    scene.add(grid);

    // --- Machine Structural Frame & Vertical Linear Columns ---
    const colGeo = new THREE.CylinderGeometry(0.4, 0.4, 26, 16);
    const colMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.9, roughness: 0.2 });

    const col1 = new THREE.Mesh(colGeo, colMat);
    col1.position.set(-9, 13, -7);
    scene.add(col1);

    const col2 = new THREE.Mesh(colGeo, colMat);
    col2.position.set(9, 13, -7);
    scene.add(col2);

    // Top Cross-Beam Gantry
    const beamGeo = new THREE.BoxGeometry(20, 1.8, 4);
    const beamMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.7, roughness: 0.4 });
    const beam = new THREE.Mesh(beamGeo, beamMat);
    beam.position.set(0, 26, -7);
    scene.add(beam);

    // Safety Stack Light Tower
    const towerGeo = new THREE.CylinderGeometry(0.35, 0.35, 3.5, 16);
    const towerMat = new THREE.MeshStandardMaterial({
      color: 0x10b981,
      emissive: 0x10b981,
      emissiveIntensity: 0.8
    });
    const tower = new THREE.Mesh(towerGeo, towerMat);
    tower.position.set(8.5, 29, -7);
    scene.add(tower);

    // --- Motorized Vertical Clamping Gantry (Piston) ---
    const gantryGroup = new THREE.Group();
    gantryGroup.position.set(0, 14, 0);

    const pistonCylinder = new THREE.Mesh(
      new THREE.CylinderGeometry(0.8, 0.8, 6, 24),
      new THREE.MeshStandardMaterial({ color: 0x64748b, metalness: 0.85, roughness: 0.2 })
    );
    pistonCylinder.position.set(0, 3, 0);
    gantryGroup.add(pistonCylinder);

    // Upper Kelvin Contact Head (Gold Plated)
    const probeHead = new THREE.Mesh(
      new THREE.CylinderGeometry(1.4, 1.6, 1.2, 24),
      new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.95, roughness: 0.1 })
    );
    probeHead.position.set(0, 0, 0);
    gantryGroup.add(probeHead);

    // Pogo-Pin Contacts
    for (let i = -1; i <= 1; i += 2) {
      const pin = new THREE.Mesh(
        new THREE.CylinderGeometry(0.12, 0.12, 0.8, 12),
        new THREE.MeshStandardMaterial({ color: 0xffd700, metalness: 1.0, roughness: 0.1 })
      );
      pin.position.set(i * 0.45, -0.7, 0);
      gantryGroup.add(pin);
    }

    scene.add(gantryGroup);
    gantryPistonRef.current = gantryGroup;

    // --- Lower Base Fixture & Microchannel Cold Plate ---
    const coldPlateGeo = new THREE.BoxGeometry(10, 1.2, 10);
    const coldPlateMat = new THREE.MeshStandardMaterial({
      color: 0x0284c7,
      metalness: 0.6,
      roughness: 0.3
    });
    const coldPlate = new THREE.Mesh(coldPlateGeo, coldPlateMat);
    coldPlate.position.set(0, 0.6, 0);
    scene.add(coldPlate);

    // Lower Negative Kelvin Contact
    const negContact = new THREE.Mesh(
      new THREE.CylinderGeometry(1.6, 1.8, 0.6, 24),
      new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.9, roughness: 0.15 })
    );
    negContact.position.set(0, 1.3, 0);
    scene.add(negContact);

    // --- Coolant Tubes with Flow Particles ---
    const particleCount = 40;
    const particleGeo = new THREE.BufferGeometry();
    const particlePos = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i++) {
      particlePos[i * 3] = (Math.random() - 0.5) * 8;
      particlePos[i * 3 + 1] = 0.6;
      particlePos[i * 3 + 2] = (Math.random() - 0.5) * 8;
    }
    particleGeo.setAttribute('position', new THREE.BufferAttribute(particlePos, 3));
    const particleMat = new THREE.PointsMaterial({
      color: 0x38bdf8,
      size: 0.3,
      transparent: true,
      opacity: 0.85
    });
    const coolantPoints = new THREE.Points(particleGeo, particleMat);
    scene.add(coolantPoints);
    coolantParticlesRef.current = coolantPoints;

    // --- Dual Lateral Ultrasonic Acoustic Transducer Horns ---
    const txGroup = new THREE.Group();
    txGroup.position.set(-5.5, 6, 0);
    const hornGeo = new THREE.ConeGeometry(0.9, 2.5, 16);
    hornGeo.rotateZ(Math.PI / 2);
    const hornMat = new THREE.MeshStandardMaterial({ color: 0x06b6d4, metalness: 0.8, roughness: 0.25 });
    const txHorn = new THREE.Mesh(hornGeo, hornMat);
    txGroup.add(txHorn);
    scene.add(txGroup);

    const rxGroup = new THREE.Group();
    rxGroup.position.set(5.5, 6, 0);
    const rxHornGeo = new THREE.ConeGeometry(0.9, 2.5, 16);
    rxHornGeo.rotateZ(-Math.PI / 2);
    const rxHorn = new THREE.Mesh(rxHornGeo, hornMat);
    rxGroup.add(rxHorn);
    scene.add(rxGroup);

    // Concentric Ultrasonic Wavefront Mesh (Volumetric Acoustic Ring)
    const waveGeo = new THREE.TorusGeometry(2.2, 0.12, 16, 64);
    waveGeo.rotateY(Math.PI / 2);
    const waveMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.7,
      wireframe: true
    });
    const waveMesh = new THREE.Mesh(waveGeo, waveMat);
    waveMesh.position.set(0, 6, 0);
    scene.add(waveMesh);
    waveMeshRef.current = waveMesh;

    // --- ZVS Active Rebalancer Inverter PCB Board ---
    const pcbGroup = new THREE.Group();
    pcbGroup.position.set(-11, 4, 3);
    const pcbBase = new THREE.Mesh(
      new THREE.BoxGeometry(4.5, 6, 0.4),
      new THREE.MeshStandardMaterial({ color: 0x064e3b, metalness: 0.3, roughness: 0.7 })
    );
    pcbGroup.add(pcbBase);

    // Planar Inductors
    const indGeo = new THREE.CylinderGeometry(0.7, 0.7, 0.8, 16);
    const indMat = new THREE.MeshStandardMaterial({ color: 0xb45309, metalness: 0.7, roughness: 0.3 });
    const ind1 = new THREE.Mesh(indGeo, indMat);
    ind1.position.set(-1, 1.2, 0.5);
    pcbGroup.add(ind1);
    const ind2 = new THREE.Mesh(indGeo, indMat);
    ind2.position.set(1, 1.2, 0.5);
    pcbGroup.add(ind2);

    scene.add(pcbGroup);

    // Active Rebalancing Energy Laser Arcs (Line geometry)
    const arcMat = new THREE.LineBasicMaterial({ color: 0x10b981, linewidth: 2, transparent: true, opacity: 0.9 });
    const arcGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-11, 4, 3),
      new THREE.Vector3(0, 7, 0)
    ]);
    const arcLine = new THREE.Line(arcGeo, arcMat);
    scene.add(arcLine);
    arcLinesRef.current = arcLine;

    // --- Battery Cell Model Holder Group ---
    const cellGroup = new THREE.Group();
    scene.add(cellGroup);
    cellGroupRef.current = cellGroup;

    // Animation Loop
    let clock = new THREE.Clock();
    const animate = () => {
      animFrameIdRef.current = requestAnimationFrame(animate);
      try {
        const delta = Math.min(clock.getDelta(), 0.1);
        const elapsed = clock.getElapsedTime();

        if (autoRotateRef.current && !isDraggingRef.current) {
          sphericalRef.current.theta += 0.005;
          updateCameraPosition();
        }

        // 1. Acoustic Wave Pulsing
        if (waveMeshRef.current) {
          const waveScale = (elapsed * 2.5) % 3.0;
          waveMeshRef.current.scale.set(1 + waveScale * 0.4, 1 + waveScale * 0.4, 1 + waveScale * 0.4);
          (waveMeshRef.current.material as THREE.MeshBasicMaterial).opacity = Math.max(0.1, 1.0 - waveScale / 3.0);
        }

        // 2. Coolant Particle Flow
        if (coolantParticlesRef.current) {
          const positions = coolantParticlesRef.current.geometry.attributes.position.array as Float32Array;
          for (let i = 0; i < particleCount; i++) {
            positions[i * 3 + 2] += delta * 4.0;
            if (positions[i * 3 + 2] > 4.5) positions[i * 3 + 2] = -4.5;
          }
          coolantParticlesRef.current.geometry.attributes.position.needsUpdate = true;
        }

        // 3. Dynamic Rebalancing Shuttling Arc
        if (arcLinesRef.current) {
          const currentFrame = frameRef.current;
          const isRebalancing = currentFrame?.rebalancing_active || (currentFrame?.rebalancing_powerStage_actualCurrent && currentFrame.rebalancing_powerStage_actualCurrent > 0);
          arcLinesRef.current.visible = !!isRebalancing;
          if (isRebalancing) {
            (arcLinesRef.current.material as THREE.LineBasicMaterial).opacity = 0.5 + 0.5 * Math.sin(elapsed * 15.0);
          }
        }

        // 4. Clamping Piston Dynamic Stroke
        if (gantryPistonRef.current) {
          const fmt = selectedFormatRef.current;
          const targetY = fmt === '18650_cylindrical' ? 10.5
                        : fmt === '21700_cylindrical' ? 11.5
                        : fmt === 'prismatic_100ah' ? 13.0
                        : 9.5;
          gantryPistonRef.current.position.y = THREE.MathUtils.lerp(gantryPistonRef.current.position.y, targetY, 0.1);
        }

        if (rendererRef.current && sceneRef.current && cameraRef.current) {
          rendererRef.current.render(sceneRef.current, cameraRef.current);
        }
      } catch (err) {
        console.warn('Animation loop caught:', err);
      }
    };

    animate();

    // Handle Window Resize
    const handleResize = () => {
      if (!containerRef.current || !rendererRef.current || !cameraRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      cameraRef.current.aspect = w / h;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(w, h);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      domEl.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      domEl.removeEventListener('wheel', onWheel);
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
      if (rendererRef.current && rendererRef.current.domElement) {
        rendererRef.current.domElement.remove();
        rendererRef.current.dispose();
      }
    };
  }, [updateCameraPosition]);

  // 2. Build Cell Geometry ONLY whenever Format, RenderMode, or Wireframe changes
  useEffect(() => {
    const cellGroup = cellGroupRef.current;
    if (!cellGroup) return;

    // Clear old cell meshes
    while (cellGroup.children.length > 0) {
      cellGroup.remove(cellGroup.children[0]);
    }

    const cellTemp = frameRef.current?.thermal_temperature || 25.0;

    // Base Color calculation
    let baseColor = 0x38bdf8;
    if (renderMode === 'thermal') {
      const tNorm = Math.max(0, Math.min(1, (cellTemp - 20) / 30));
      baseColor = tNorm > 0.6 ? 0xef4444 : tNorm > 0.3 ? 0xf59e0b : 0x10b981;
    } else if (renderMode === 'xray') {
      baseColor = 0x818cf8;
    }

    const isTransparent = renderMode === 'xray' || renderMode === 'cutaway';
    const cellMat = new THREE.MeshStandardMaterial({
      color: baseColor,
      metalness: renderMode === 'realistic' ? 0.8 : 0.2,
      roughness: 0.3,
      transparent: isTransparent,
      opacity: renderMode === 'xray' ? 0.45 : renderMode === 'cutaway' ? 0.85 : 1.0,
      wireframe: showWireframe
    });

    if (selectedFormat === '18650_cylindrical' || selectedFormat === '21700_cylindrical') {
      const radius = selectedFormat === '18650_cylindrical' ? 1.8 : 2.2;
      const height = selectedFormat === '18650_cylindrical' ? 8.5 : 9.8;

      const cylinder = new THREE.Mesh(
        new THREE.CylinderGeometry(radius, radius, height, 32, 1, renderMode === 'cutaway', 0, renderMode === 'cutaway' ? Math.PI * 1.4 : Math.PI * 2),
        cellMat
      );
      cylinder.position.set(0, height / 2 + 1.5, 0);
      cylinder.castShadow = true;
      cellGroup.add(cylinder);

      // Terminal Cap (Gold/Steel)
      const cap = new THREE.Mesh(
        new THREE.CylinderGeometry(radius * 0.5, radius * 0.5, 0.4, 24),
        new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.9, roughness: 0.1 })
      );
      cap.position.set(0, height + 1.7, 0);
      cellGroup.add(cap);

      // Internal Spiral Jelly-Roll Microstructure (Visible in Cutaway/X-Ray)
      if (renderMode === 'cutaway' || renderMode === 'xray') {
        for (let j = 1; j <= 5; j++) {
          const jrRadius = (radius * j) / 6.0;
          const jrMesh = new THREE.Mesh(
            new THREE.CylinderGeometry(jrRadius, jrRadius, height * 0.9, 24, 1, true),
            new THREE.MeshBasicMaterial({
              color: j % 2 === 0 ? 0x10b981 : 0xf59e0b,
              wireframe: true,
              transparent: true,
              opacity: 0.7
            })
          );
          jrMesh.position.set(0, height / 2 + 1.5, 0);
          cellGroup.add(jrMesh);
        }
      }
    } else if (selectedFormat === 'prismatic_100ah') {
      const width = 7.5;
      const height = 10.5;
      const depth = 3.8;

      const prism = new THREE.Mesh(
        new THREE.BoxGeometry(width, height, depth),
        cellMat
      );
      prism.position.set(0, height / 2 + 1.5, 0);
      prism.castShadow = true;
      cellGroup.add(prism);

      // Prismatic Dual Terminals & Burst Safety Vent
      const termPos = new THREE.Mesh(
        new THREE.CylinderGeometry(0.6, 0.6, 0.8, 16),
        new THREE.MeshStandardMaterial({ color: 0xef4444, metalness: 0.9 })
      );
      termPos.position.set(-2.2, height + 1.8, 0);
      cellGroup.add(termPos);

      const termNeg = new THREE.Mesh(
        new THREE.CylinderGeometry(0.6, 0.6, 0.8, 16),
        new THREE.MeshStandardMaterial({ color: 0x0284c7, metalness: 0.9 })
      );
      termNeg.position.set(2.2, height + 1.8, 0);
      cellGroup.add(termNeg);

      const vent = new THREE.Mesh(
        new THREE.CylinderGeometry(0.4, 0.4, 0.1, 16),
        new THREE.MeshStandardMaterial({ color: 0x64748b })
      );
      vent.position.set(0, height + 1.55, 0);
      cellGroup.add(vent);

      // Internal Stacked Electrode Sheets
      if (renderMode === 'cutaway' || renderMode === 'xray') {
        for (let l = 0; l < 8; l++) {
          const layerMesh = new THREE.Mesh(
            new THREE.BoxGeometry(width * 0.85, 0.1, depth * 0.85),
            new THREE.MeshBasicMaterial({ color: l % 2 === 0 ? 0x34d399 : 0xf59e0b, opacity: 0.8, transparent: true })
          );
          layerMesh.position.set(0, 2.5 + l * 1.1, 0);
          cellGroup.add(layerMesh);
        }
      }
    } else {
      // Pouch Cell Format
      const width = 6.0;
      const height = 7.5;
      const depth = 1.2;

      const pouch = new THREE.Mesh(
        new THREE.BoxGeometry(width, height, depth),
        cellMat
      );
      pouch.position.set(0, height / 2 + 1.5, 0);
      cellGroup.add(pouch);

      // Foil Tabs
      const tabPos = new THREE.Mesh(
        new THREE.BoxGeometry(1.2, 1.2, 0.05),
        new THREE.MeshStandardMaterial({ color: 0xef4444, metalness: 0.9 })
      );
      tabPos.position.set(-1.6, height + 2.0, 0);
      cellGroup.add(tabPos);

      const tabNeg = new THREE.Mesh(
        new THREE.BoxGeometry(1.2, 1.2, 0.05),
        new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.9 })
      );
      tabNeg.position.set(1.6, height + 2.0, 0);
      cellGroup.add(tabNeg);
    }
  }, [selectedFormat, renderMode, showWireframe]);

  // 3. Render 10 MHz RF Ultrasonic Oscilloscope on 2D Overlay Canvas
  const renderOscilloscope = useCallback(() => {
    const canvas = oscCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    // Clear background
    ctx.fillStyle = '#020617';
    ctx.fillRect(0, 0, w, h);

    // Draw Oscilloscope Grid
    ctx.strokeStyle = '#0f172a';
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 25) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 20) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Zero-crossing line
    ctx.strokeStyle = '#334155';
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();

    // Synthesize/Render A-Scan Trace based on current telemetry
    const currentFrame = frameRef.current;
    const tof = currentFrame?.ultrasonic_timeOfFlight || 8.0;
    const atten = currentFrame?.ultrasonic_amplitude !== undefined ? currentFrame.ultrasonic_amplitude : 0.85;
    const degMode = currentFrame?.degradation_mode || 'healthy';

    ctx.lineWidth = 1.5;
    ctx.strokeStyle = degMode === 'gas_generation' ? '#ff00ff' : degMode === 'li_plating' ? '#f59e0b' : '#38bdf8';
    ctx.beginPath();

    const cy = h / 2;
    for (let x = 0; x < w; x++) {
      const t_us = (x / w) * 16.0; // 0 to 16 µs time window
      let yVal = 0;

      // Front-wall transmission echo
      if (t_us >= 0.5 && t_us <= 2.5) {
        const env = Math.exp(-Math.pow((t_us - 1.5) / 0.4, 2));
        yVal += Math.sin((t_us - 1.5) * 20.0) * env * (h * 0.38);
      }

      // Defect internal scattering echoes
      if (degMode === 'gas_generation' && t_us >= 3.5 && t_us <= 5.5) {
        const envDef = Math.exp(-Math.pow((t_us - 4.5) / 0.5, 2)) * 0.7;
        yVal += Math.sin((t_us - 4.5) * 25.0) * envDef * (h * 0.28);
      } else if (degMode === 'li_plating' && t_us >= 2.8 && t_us <= 4.2) {
        const envPlat = Math.exp(-Math.pow((t_us - 3.5) / 0.3, 2)) * 0.5;
        yVal += Math.sin((t_us - 3.5) * 30.0) * envPlat * (h * 0.22);
      }

      // Back-wall structural reflection echo
      if (t_us >= tof - 1.0 && t_us <= tof + 1.0) {
        const phase = degMode === 'li_plating' ? Math.PI : 0;
        const envBack = Math.exp(-Math.pow((t_us - tof) / 0.45, 2)) * atten;
        yVal += Math.sin((t_us - tof) * 20.0 + phase) * envBack * (h * 0.35);
      }

      yVal += (Math.random() - 0.5) * 1.5;
      const py = cy - yVal;
      if (x === 0) ctx.moveTo(x, py);
      else ctx.lineTo(x, py);
    }
    ctx.stroke();

    // ToF Marker Cursor
    const markerX = (tof / 16.0) * w;
    ctx.strokeStyle = '#eab308';
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(markerX, 0);
    ctx.lineTo(markerX, h);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = '#38bdf8';
    ctx.font = '10px monospace';
    ctx.fillText(`ToF: ${tof.toFixed(2)} µs`, markerX + 4, 14);
    ctx.fillText(`Amp: ${(atten * 100).toFixed(0)}%`, 8, h - 8);
  }, []);

  useEffect(() => {
    renderOscilloscope();
  }, [renderOscilloscope, frame]);

  // Automated 6-Stage Testing Cycle Handler
  const handleStartCycle = async () => {
    setIsCycleRunning(true);
    const stages = [
      'CLAMPING_ENGAGED',
      'ACOUSTIC_COUPLING_CHECK',
      'TRI_MODAL_PULSE_SCAN',
      'AI_FUSION_INFERENCE',
      'ACTIVE_REBALANCING_EXECUTION',
      'HEALTH_CERTIFICATION'
    ];

    for (let i = 0; i < stages.length; i++) {
      setCycleStage(stages[i]);
      for (let p = 0; p <= 100; p += 25) {
        setCycleProgress(p);
        await new Promise((r) => setTimeout(r, 200));
      }
    }
    setIsCycleRunning(false);
  };

  // Switch Camera View Presets
  const setCameraPreset = (preset: 'overview' | 'gantry' | 'horns' | 'rebalancer') => {
    if (preset === 'overview') {
      sphericalRef.current = { radius: 42, phi: Math.PI / 3, theta: 0.8 };
      targetRef.current.set(0, 6, 0);
    } else if (preset === 'gantry') {
      sphericalRef.current = { radius: 22, phi: Math.PI / 4, theta: 0.4 };
      targetRef.current.set(0, 11, 0);
    } else if (preset === 'horns') {
      sphericalRef.current = { radius: 18, phi: Math.PI / 2.3, theta: 0.0 };
      targetRef.current.set(0, 6, 0);
    } else if (preset === 'rebalancer') {
      sphericalRef.current = { radius: 20, phi: Math.PI / 2.8, theta: -1.2 };
      targetRef.current.set(-11, 4, 3);
    }
    updateCameraPosition();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#070a13', color: '#e2e8f0' }}>
      {/* Top Industrial Machine Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '10px 14px',
        background: '#0f172a',
        borderBottom: '1px solid #1e293b',
        flexWrap: 'wrap'
      }}>
        {/* Format Selector Pills */}
        <div style={{ display: 'flex', gap: '4px', background: '#020617', padding: '3px', borderRadius: '6px' }}>
          {(['18650_cylindrical', '21700_cylindrical', 'prismatic_100ah', 'pouch_60ah'] as CellFormat[]).map((fmt) => (
            <button
              key={fmt}
              onClick={() => setSelectedFormat(fmt)}
              style={{
                padding: '4px 8px',
                fontSize: '0.74rem',
                borderRadius: '4px',
                border: 'none',
                background: selectedFormat === fmt ? '#0284c7' : 'transparent',
                color: selectedFormat === fmt ? '#ffffff' : '#94a3b8',
                fontWeight: selectedFormat === fmt ? 700 : 500,
                cursor: 'pointer'
              }}
            >
              {fmt === '18650_cylindrical' ? '18650 4S'
                : fmt === '21700_cylindrical' ? '21700 Pack'
                : fmt === 'prismatic_100ah' ? 'Prismatic 100Ah'
                : 'Pouch 60Ah'}
            </button>
          ))}
        </div>

        {/* Render View Modes */}
        <div style={{ display: 'flex', gap: '4px', background: '#020617', padding: '3px', borderRadius: '6px' }}>
          {(['realistic', 'thermal', 'xray', 'cutaway'] as RenderMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setRenderMode(m)}
              style={{
                padding: '4px 8px',
                fontSize: '0.74rem',
                borderRadius: '4px',
                border: 'none',
                textTransform: 'capitalize',
                background: renderMode === m ? '#0284c7' : 'transparent',
                color: renderMode === m ? '#ffffff' : '#94a3b8',
                fontWeight: renderMode === m ? 700 : 500,
                cursor: 'pointer'
              }}
            >
              {m}
            </button>
          ))}
        </div>

        {/* Camera Preset Quick Buttons */}
        <div style={{ display: 'flex', gap: '4px' }}>
          <button onClick={() => setCameraPreset('overview')} style={{ padding: '4px 8px', fontSize: '0.74rem', background: '#1e293b', color: '#f8fafc', border: '1px solid #334155', borderRadius: '4px', cursor: 'pointer' }}>👁 Overview</button>
          <button onClick={() => setCameraPreset('gantry')} style={{ padding: '4px 8px', fontSize: '0.74rem', background: '#1e293b', color: '#f8fafc', border: '1px solid #334155', borderRadius: '4px', cursor: 'pointer' }}>🦾 Clamp</button>
          <button onClick={() => setCameraPreset('horns')} style={{ padding: '4px 8px', fontSize: '0.74rem', background: '#1e293b', color: '#f8fafc', border: '1px solid #334155', borderRadius: '4px', cursor: 'pointer' }}>🔊 Horns</button>
          <button onClick={() => setCameraPreset('rebalancer')} style={{ padding: '4px 8px', fontSize: '0.74rem', background: '#1e293b', color: '#f8fafc', border: '1px solid #334155', borderRadius: '4px', cursor: 'pointer' }}>🔄 Rebalancer</button>
        </div>

        <button
          onClick={() => setAutoRotate(!autoRotate)}
          style={{
            padding: '4px 10px',
            fontSize: '0.75rem',
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
            fontSize: '0.75rem',
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
            fontSize: '0.75rem',
            borderRadius: '4px',
            border: '1px solid #475569',
            background: showOscilloscope ? '#0284c7' : '#334155',
            color: '#ffffff',
            cursor: 'pointer'
          }}
        >
          {showOscilloscope ? '📊 Hide Scope' : '📊 Show Scope'}
        </button>

        {/* Automated Machine Test Cycle Execution Button */}
        <button
          onClick={handleStartCycle}
          disabled={isCycleRunning}
          style={{
            padding: '4px 12px',
            fontSize: '0.76rem',
            fontWeight: 700,
            borderRadius: '6px',
            border: '1px solid #38bdf8',
            background: isCycleRunning ? '#0284c7' : '#0369a1',
            color: '#ffffff',
            cursor: isCycleRunning ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          {isCycleRunning ? `⏳ Running ${cycleStage.replace(/_/g, ' ')} (${cycleProgress}%)` : '▶ Run 6-Stage Cycle'}
        </button>

        <button
          onClick={() => window.open('http://localhost:8000/gazebo', '_blank')}
          style={{
            marginLeft: 'auto',
            padding: '4px 12px',
            fontSize: '0.78rem',
            fontWeight: 700,
            borderRadius: '6px',
            border: '1px solid #10b981',
            background: '#059669',
            color: '#ffffff',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          🌐 Open Gazebo Studio
        </button>
      </div>

      {/* Main 3D Canvas & Interactive HUD Overlay */}
      <div style={{ position: 'relative', flex: 1, minHeight: '520px', overflow: 'hidden' }}>
        <div ref={containerRef} style={{ width: '100%', height: '100%', cursor: 'grab' }} />

        {/* Floating Machine Diagnostics HUD (Top-Left) */}
        <div style={{
          position: 'absolute',
          top: '16px',
          left: '16px',
          background: 'rgba(15, 23, 42, 0.90)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(56, 189, 248, 0.4)',
          borderRadius: '12px',
          padding: '14px 18px',
          color: '#f8fafc',
          fontSize: '0.82rem',
          lineHeight: '1.6',
          boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
          pointerEvents: 'auto',
          maxWidth: '320px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.85rem' }}>
              Machine Test Station
            </span>
            <span style={{
              background: frame?.data_origin === 'FMU' ? '#2563eb' : '#0284c7',
              color: '#ffffff',
              padding: '2px 8px',
              borderRadius: '9999px',
              fontSize: '0.70rem',
              fontWeight: 700
            }}>
              {frame?.data_origin || '3D-SIM'}
            </span>
          </div>
          <div><strong>Test Stage:</strong> <span style={{ color: '#fbbf24', fontWeight: 700 }}>{cycleStage}</span></div>
          <div><strong>Degradation State:</strong> <span style={{ color: '#38bdf8', fontWeight: 600 }}>{frame?.degradation_mode?.replace(/_/g, ' ') || 'healthy'}</span></div>
          <div><strong>State of Health:</strong> {frame?.stateOfHealth_value !== undefined ? `${frame.stateOfHealth_value.toFixed(1)}%` : '—'}</div>
          <div><strong>Terminal Voltage:</strong> {frame?.electrical_voltage !== undefined ? `${frame.electrical_voltage.toFixed(3)} V` : '—'}</div>
          <div><strong>Surface Temp:</strong> {frame?.thermal_temperature !== undefined ? `${frame.thermal_temperature.toFixed(1)} °C` : '—'}</div>
          <div><strong>Acoustic ToF:</strong> {frame?.ultrasonic_timeOfFlight !== undefined ? `${frame.ultrasonic_timeOfFlight.toFixed(2)} µs` : '—'}</div>
          <div><strong>Rebalancer:</strong> <span style={{ color: (frame?.rebalancing_state?.toLowerCase().includes('lockout')) ? '#ef4444' : '#10b981', fontWeight: 600 }}>{frame?.rebalancing_state || 'IDLE'}</span></div>
          <div><strong>ZVS Efficiency:</strong> <span style={{ color: '#34d399', fontWeight: 700 }}>{frame?.zvs_efficiency_pct && frame.zvs_efficiency_pct > 0 ? `${frame.zvs_efficiency_pct.toFixed(1)}% (ZVS Stage)` : '—'}</span></div>
        </div>

        {/* Interactive Component Inspector Drawer (Top-Right) */}
        <div style={{
          position: 'absolute',
          top: '16px',
          right: '16px',
          background: 'rgba(15, 23, 42, 0.92)',
          backdropFilter: 'blur(14px)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: '12px',
          padding: '14px',
          maxWidth: '340px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
          fontSize: '0.80rem'
        }}>
          <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '8px', fontSize: '0.85rem' }}>
            ⚙ Interactive Component Inspector
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '10px' }}>
            {Object.values(COMPONENT_DETAILS).map((comp) => (
              <button
                key={comp.id}
                onClick={() => setActiveComponent(comp)}
                style={{
                  padding: '6px',
                  borderRadius: '6px',
                  border: '1px solid',
                  borderColor: activeComponent?.id === comp.id ? '#38bdf8' : '#334155',
                  background: activeComponent?.id === comp.id ? 'rgba(56, 189, 248, 0.2)' : '#1e293b',
                  color: '#f8fafc',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  textAlign: 'left',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <span>{comp.icon}</span>
                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{comp.name.split(' ')[0]}</span>
              </button>
            ))}
          </div>

          {activeComponent && (
            <div style={{ borderTop: '1px solid #334155', paddingTop: '8px', color: '#cbd5e1', lineHeight: '1.4' }}>
              <div style={{ fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
                {activeComponent.icon} {activeComponent.name}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#38bdf8', marginBottom: '4px' }}>
                <strong>Role:</strong> {activeComponent.role}
              </div>
              <div style={{ fontSize: '0.73rem', marginBottom: '6px' }}>
                {activeComponent.principle}
              </div>
              <div style={{ fontSize: '0.70rem', color: '#94a3b8', background: '#0f172a', padding: '6px', borderRadius: '4px', marginBottom: '6px' }}>
                <strong>Specs:</strong> {activeComponent.specs}
              </div>
              <div style={{ fontSize: '0.72rem', color: '#34d399', fontWeight: 600 }}>
                {activeComponent.liveReading}
              </div>
            </div>
          )}
        </div>

        {/* Embedded Ultrasonic RF Oscilloscope (Bottom-Left) */}
        {showOscilloscope && (
          <div style={{
            position: 'absolute',
            bottom: '16px',
            left: '16px',
            background: 'rgba(15, 23, 42, 0.94)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            borderRadius: '10px',
            padding: '10px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.6)'
          }}>
            <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#38bdf8', marginBottom: '6px', letterSpacing: '0.05em' }}>
              ULTRASONIC RF PULSE-ECHO (10 MHz OSCILLOGRAM)
            </div>
            <canvas ref={oscCanvasRef} width={280} height={110} style={{ display: 'block', borderRadius: '6px' }} />
          </div>
        )}

        {/* Navigation & Interaction Legend (Bottom-Right) */}
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
          <div>✨ <strong>Green Arcs:</strong> ZVS Active Energy Shuttling</div>
        </div>
      </div>
    </div>
  );
};

export default ThreeDView;