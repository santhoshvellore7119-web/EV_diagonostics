# Unified Diagnostic Dashboard Architecture

## Overview
This document describes the architecture for a unified web dashboard that integrates five disconnected subsystems into a single coherent system for EV battery diagnostics and active cell-rebalancing. The dashboard provides live hardware diagnostics, Simulink-driven simulation, and 3D cell visualization modes, all sharing a common data model and synchronized UI.

## Core Design Principles
1. **Single Source of Truth**: All modes read from and write to a shared DiagnosticFrame data model
2. **Mode Synchronization**: UI state (timeline, controls) is shared across all three views
3. **Evidence-First**: Built-in features for generating publication/patent-ready evidence
4. **Graceful Degradation**: System works fully in simulated mode without hardware or MATLAB
5. **Research-Grade**: Output suitable for academic publication and patent submission

## DiagnosticFrame Schema
The shared data model that flows between all system components:

```javascript
interface DiagnosticFrame {
  // Timing and identification
  timestamp: number;              // Unix timestamp in milliseconds
  frameId: string;                // Unique identifier for this frame
  source: 'live' | 'simulink' | '3d'; // Data source
  
  // Cell/Pack identification
  cellId: string;                 // Identifier for the cell/battery under test
  packId?: string;                // Optional pack identifier for multi-cell systems
  
  // Multi-modal sensor data (raw and processed)
  electrical: {
    voltage: number;              // Bus voltage (V)
    current: number;              // Current (A)
    power: number;                // Power (W)
    resistance: number;           // Calculated internal resistance (Ω)
    uncertainty: number;          // Measurement uncertainty (±)
  };
  
  ultrasonic: {
    timeOfFlight: number;         // Time of flight (µs)
    amplitude: number;            // Echo amplitude (normalized)
    phaseShift: number;           // Phase shift (radians)
    speedOfSound: number;         // Derived speed of sound (m/s)
    uncertainty: number;          // Measurement uncertainty
  };
  
  thermal: {
    temperature: number;          // Temperature (°C)
    tempGradient: number;         // Temperature gradient (°C/s)
    heatFlux: number;             // Estimated heat flux (W/m²)
    uncertainty: number;          // Measurement uncertainty
  };
  
  // Battery state estimates (from ML pipeline)
  stateOfHealth: {
    value: number;                // SOH percentage (0-100)
    confidenceInterval: [number, number]; // 95% CI [lower, upper]
    method: 'fusion' | 'electrical-only'; // Estimation method
  };
  
  degradation: {
    mode: 'healthy' | 'li_plating' | 'active_material_loss' | 
          'electrolyte_decomposition' | 'gas_generation' | 'internal_short';
    probability: number;          // Classification probability (0-1)
    perClassProbabilities: {      // Calibrated confidence for each class
      healthy: number;
      li_plating: number;
      active_material_loss: number;
      electrolyte_decomposition: number;
      gas_generation: number;
      internal_short: number;
    };
    entropy: number;              // Classification entropy (uncertainty measure)
  };
  
  // Active rebalancing state
  rebalancing: {
    state: 'idle' | 'deciding' | 'executing' | 'verifying' | 'complete';
    selectedAction: 'none' | 'pulse_deplating' | 'equilibration' | 
                   'gas_recombination' | 'short_isolation' | 'balancing';
    actionReason: string;         // Explanation of why this action was selected
    powerStage: {
      targetCurrent: number;      // PID target current (A)
      actualCurrent: number;      // Measured current (A)
      targetVoltage: number;      // PID target voltage (V)
      actualVoltage: number;      // Measured voltage (V)
      pwmDutyCycle: number;       // Current PWM duty cycle (0-1)
    };
    executionTime: number;        // Seconds elapsed in current action
  };
  
  // Simulation-specific fields (when source is 'simulink' or '3d')
  simulation: {
    soc: number;                  // State of charge (0-1)
    excitationAmplitude: number;  // Excitation pulse amplitude (A)
    noiseLevel: number;           // Added noise level for realism
    stepCount: number;            // Simulation step counter
  };
}
```

## Module Boundaries and Data Flow

### 1. Data Ingestion Layer
**Responsibility**: Convert subsystem outputs to DiagnosticFrame format and publish to shared stream

#### Firmware Ingestion (Live Mode)
- **Input**: Serial data from ESP32 firmware (JSON format via serializer.h)
- **Processing**: 
  - Parse incoming JSON packets from host_application/src/data_manager.py
  - Calculate derived values (resistance, power, etc.)
  - Add metadata (timestamp, frameId, source='live')
  - Validate data quality and apply uncertainty estimates
- **Output**: DiagnosticFrame objects published to shared WebSocket stream
- **Files to modify/create**:
  - `backend/ingest/firmware.py`: New module for live data ingestion
  - Modify `host_application/src/data_manager.py` to optionally publish to WebSocket

#### Simulink Bridge (Simulation Mode)
- **Input**: FMU (Functional Mock-up Unit) exported from Simulink model
- **Processing**:
  - Use FMI library for Python to step through simulation
  - Map Simulink outputs to DiagnosticFrame fields
  - Add source='simulink' metadata
  - Generate varying SOC/excitation scenarios based on user input
- **Output**: DiagnosticFrame objects published to shared WebSocket stream
- **Files to modify/create**:
  - `backend/ingest/simulink.py`: New module using fmi-python library
  - Export FMU from Simulink model using Simulink Coder

#### 3D Simulation (Visualization Mode)
- **Input**: Internal simulation state from ev_battery_3d_simulation.py
- **Processing**:
  - Extract sensor readings from 3D simulation compute_sensor_readings()
  - Map to DiagnosticFrame format
  - Add source='3d' metadata
  - Synchronize with user-controlled parameters (SOC, degradation mode, etc.)
- **Output**: DiagnosticFrame objects published to shared WebSocket stream
- **Files to modify/create**:
  - `backend/ingest/threed.py`: New module bridging 3D simulation to data stream
  - Modify `simulation_3d_demo/ev_battery_3d_simulation.py` to expose data interface

### 2. Shared Data Backend (FastAPI + WebSocket)
**Responsibility**: Manage the shared DiagnosticFrame stream, handle mode switching, persist recordings

#### Components:
- **Frame Buffer**: Circular buffer of recent DiagnosticFrame objects (configurable size)
- **Mode Manager**: Tracks current active mode and handles transitions
- **Recording Service**: Logs all incoming frames to disk for replay
- **WebSocket Hub**: Broadcasts frames to all connected frontend clients
- **REST API**: Provides endpoints for configuration, evidence features, and historical data

#### Key Endpoints:
- `GET /api/frames/latest`: Get most recent DiagnosticFrame
- `GET /api/frames/historical?start=&end=`: Get frames in time range
- `POST /api/mode/set`: Switch between live/simulink/3d modes
- `POST /api/recording/start`: Begin session recording
- `POST /api/recording/stop`: End session recording
- `POST /api/evidence/ablation/run`: Run modality ablation on current session
- `GET /api/evidence/baseline`: Get baseline comparison data
- `WebSocket /ws`: Real-time stream of DiagnosticFrame objects

#### Files to create:
- `backend/main.py`: FastAPI application entry point
- `backend/stream.py`: WebSocket connection management
- `backend/recording.py`: Session recording and replay functionality
- `backend/mode_manager.py`: Active mode tracking and switching
- `backend/evidence.py`: Evidence-generation feature implementations

### 3. ML Pipeline Integration
**Responsibility**: Process DiagnosticFrame objects to produce state estimates

#### Processing Flow:
1. Subscribe to shared DiagnosticFrame WebSocket stream
2. For each incoming frame:
   - Extract electrical, ultrasonic, thermal tensors (window of N frames)
   - Run through MultiBranchFusionNet model
   - Produce SOH regression estimate with uncertainty band
   - Produce degradation classification with per-class probabilities
   - Calculate entropy/uncertainty metrics
3. Publish enhanced DiagnosticFrame back to stream with ML results
4. Optional: Run ablation studies by masking modalities

#### Files to modify/create:
- `backend/ml_processor.py`: New module that wraps the PyTorch model
- Modify `ml_pipeline/models/multibranch_fusion_net.py` to output uncertainty estimates
- Add methods for modality masking (set modality tensors to zero)
- Update model to return confidence intervals for SOH estimate

### 4. Active Rebalancing Integration
**Responsibility**: Consume ML-enhanced frames to make recovery decisions

#### Processing Flow:
1. Subscribe to ML-enhanced DiagnosticFrame WebSocket stream
2. For each incoming frame:
   - Feed SOH, degradation mode, probabilities to decision engine state machine
   - Execute state machine step to determine if recovery action needed
   - If executing, send commands to hardware (live mode) or simulate effect (simulation modes)
   - Track action effectiveness over time
3. Publish updated DiagnosticFrame with rebalancing state back to stream
4. Log before/after SOH for each completed recovery cycle

#### Files to modify/create:
- `backend/rebalancing.py`: New module wrapping decision_engine logic
- Modify `active_rebalancing/decision_engine/state_machine.py` to:
  - Accept DiagnosticFrame as input format
  - Output rebalancing commands in standardized format
  - Expose effectiveness tracking for before/after logging
- Add persistence layer for recovery history

### 5. Frontend Application (React + Three.js)
**Responsibility**: Unified UI with three synchronized views and evidence panels

#### Architecture:
- **Single Page Application** with React Router
- **Shared State**: Redux or Context API for:
  - Current DiagnosticFrame
  - Active mode (live/simulink/3d)
  - Timeline position and playback controls
  - Session recording status
  - Evidence view configurations
- **Three synchronized views**:
  1. **Live Diagnostics View**: Real-time charts of sensor data and ML outputs
  2. **Simulink View**: Same as live but labeled as simulation source
  3. **3D View**: Three.js rendering of battery cell with sensor visualization
- **Always-visible panels**:
  - ML Fusion Panel: Shows per-modality contributions, degradation probabilities with confidence, SOH with uncertainty band
  - Rebalancing Panel: Shows current state, selected action with reasoning, power stage telemetry
- **Evidence-generation views** (accessible via tabs or modal):
  - Modality Ablation View: Compare SOH/error with each modality masked
  - Baseline Comparison: Fused model vs electrical-only baseline
  - Before/After Rebalancing Trend: Historical effectiveness of recovery actions
  - Session Replay: Controls to playback recorded sessions

#### Key Technical Details:
- Use WebSocket connection to backend for real-time updates
- Implement charting library (Recharts or Chart.js) with synchronized zoom/pan
- Three.js view shares same timeline controls as 2D views
- Export functionality: PNG/SVG generation for all views using html2canvas or similar
- Responsive design for presentation/demo use

#### Files to create:
- `frontend/src/App.js`: Main application component
- `frontend/src/components/`: React components for views and panels
- `frontend/src/services/`: WebSocket and API service modules
- `frontend/src/store/`: State management (Redux or Context)
- `frontend/src/utils/`: Charting, export, and visualization utilities

## Chosen Simulink Integration Approach: Exported FMU via Simulink Coder

### Why This Choice?
1. **License-Free Deployment**: FMUs can be run without MATLAB license using FMI-compatible libraries
2. **Performance**: Compiled simulation runs faster than interpreted MATLAB Engine
3. **Portability**: Single binary file that works on Windows/Linux/macOS
4. **Accuracy**: Bit-exact reproduction of Simulink model behavior
5. **Requirement Compliance**: Satisfies "Must run without requiring MATLAB installed"

### Implementation Plan:
1. Export the Simulink model (`ev_cell_digital_twin.slx`) as an FMU using Simulink Coder
   - Use "Model Export" -> "Functional Mock-up Unit (FMU)"
   - Select "CS" (Co-Simulation) implementation for greatest compatibility
   - Include necessary solver settings for real-time capability
2. Use `fmi-python` library in backend to load and step through the FMU
3. Map FMU output variables to DiagnosticFrame fields:
   - Electrical: voltage, current, power
   - Ultrasonic: timeOfFlight, amplitude, phaseShift  
   - Thermal: temperature, tempGradient
   - Internal states: SOC, internal variables for enhanced realism
4. Provide user interface to adjust simulation parameters (SOC, excitation amplitude, noise level)
5. Optionally implement stretch goal: precomputed library for instant replay of common scenarios

### Alternatives Considered and Rejected:
- **MATLAB Engine API for Python**: Rejected because requires MATLAB installation, violating core requirement
- **Precomputed simulation only**: Rejected because lacks flexibility for arbitrary scenarios and user interaction
- **Pure Python reimplementation**: Rejected because introduces potential inaccuracies and duplicates effort

## Data Flow Summary

```
+----------------+     +----------------------     +---------------------+
|                |     |                      |     |                     |
|  Firmware      |---> | Data Ingestion Layer |---> | Shared Data Backend |<---------------------+
|  (ESP32)       |     | (firmware.py)        |     | (FastAPI + WS)      |                     |
|                |     |                      |     |                     |                     |
+----------------+     +----------------------     +---------------------+                     |
                                                                     ^                     |
                                                                     |                     |
+----------------+     +----------------------     +---------------------+                     |
|                |     |                      |     |                     |                     |
|  Simulink      |---> | Data Ingestion Layer |---> | Shared Data Backend |                     |
|  (FMU)         |     | (simulink.py)        |     |                     |                     |
|                |     |                      |     |                     |                     |
+----------------+     +----------------------     +---------------------+                     |
                                                                     ^                     |
                                                                     |                     |
+----------------+     +----------------------     +---------------------+                     |
|                |     |                      |     |                     |                     |
|  3D Sim        |---> | Data Ingestion Layer |---> | Shared Data Backend |                     |
|                |     | (threed.py)          |     |                     |                     |
|                |     |                      |     |                     |                     |
+----------------+     +----------------------     +---------------------+                     |
                                                                     ^                     |
                                                                     |                     |
+----------------+     +----------------------     +---------------------+     +------------------+
|                |     |                      |     |                     |     |                  |
|  ML Processor  |<----| Shared Data Backend  |---->| Rebalancing Engine  |<----| Hardware Cmds    |
|                |     | (ml_processor.py)    |     | (rebalancing.py)    |     | (to ESP32)       |
|                |     |                      |     |                     |     |                  |
+----------------+     +----------------------     +---------------------+     +------------------+
                             ^                          ^                          ^
                             |                          |                          |
                             |                          |                          |
                     +----------------+     +------------------+     +------------------+
                     |                |     |                  |     |                  |
                     | Frontend App   |<----| Evidence Features|     | Session Recording|
                     | (React+3JS)    |     | (ablation, etc.) |     | (recording.py)   |
                     |                |     |                  |     |                  |
                     +----------------+     +------------------+     +------------------+
```

## Evidence-Generation Features Implementation

### 1. Modality Ablation View
- **Implementation**: In `backend/evidence.py`, create ablation study functions
- **Method**: For a given session recording, replay frames through ML processor with:
  - Electrical only: zero ultrasonic/thermal tensors
  - Ultrasonic only: zero electrical/thermal tensors  
  - Thermal only: zero electrical/ultrasonic tensors
  - Pairwise combinations: zero one modality
- **Output**: For each configuration, compute:
  - SOH estimation error vs ground truth (when available)
  - Classification accuracy
  - Uncertainty metrics
- **Frontend**: Display comparison charts and export as PNG/SVG

### 2. Baseline Comparison
- **Implementation**: Modified ML processor to also run electrical-only baseline
- **Method**: 
  - Run standard multi-branch fusion on all modalities
  - Run ablation study with only electrical modality active
  - Output both streams for side-by-side comparison
- **Frontend**: Dual-chart showing fused SOH estimate vs baseline with uncertainty bands
- **Export**: Combined chart suitable for publication

### 3. Before/After Rebalancing Log
- **Implementation**: In `rebalancing.py`, persist recovery cycle data
- **Data stored per cycle**:
  - Timestamp
  - Cell ID
  - SOH before action (mean of N frames pre-action)
  - SOH after action (mean of N frames post-action)
  - Selected action type and parameters
  - Action execution time
  - Success metric (SOH improvement > threshold)
- **Frontend**: 
  - Table view of individual cycles
  - Trend chart showing cumulative SOH improvement over time
  - Histogram of effectiveness by action type
- **Export**: CSV data + trend chart as PNG/SVG

### 4. Session Recording and Replay
- **Implementation**: In `backend/recording.py`
- **Recording**:
  - Write incoming DiagnosticFrame objects to JSONL file (one per line)
  - Include metadata: start time, mode, configuration
  - Optional: compress for long sessions
- **Replay**:
  - Load JSONL file and emit frames at original timestamps
  - Support variable playback speed (0.1x - 10x)
  - Synchronize with frontend timeline scrubber
  - Work identically to live mode for ML/rebalancing panels
- **Frontend**: 
  - Recording controls (start/stop)
  - Session library with timestamps/durations
  - Playback controls with speed adjustment
  - Visual indicator when in replay mode

## Non-Functional Requirements Address

### Zero Hardware/Zero MATLAB Mode
- **Default state**: System starts in 3D simulation mode with no connections
- **Fallback logic**: 
  - If no serial data detected after timeout, auto-switch to simulation
  - If FMU fails to load, fall back to precomputed 3D simulation data
  - User can manually select mode at any time
- **User notification**: Clear UI indication of current data source

### Publication-Ready UI
- **Consistent styling**: Shared color scheme, typography, and component design
- **Real units**: All charts show proper units (V, A, W, °C, %, etc.)
- **Axis labels**: Fully labeled with descriptive titles
- **Legend and tooltips**: Interactive explanations of all displayed values
- **Export functionality**: One-click PNG/SVG export for all views and evidence charts
- **Dark/Light mode**: Support for different presentation environments

### Extensibility
- **Modular ingestion**: New data sources can be added by implementing new ingest modules
- **Plugin architecture**: Evidence features implemented as registrable plugins
- **Configuration**: YAML/JSON files for tuning thresholds, buffer sizes, etc.
- **Testing**: Mock data generators for unit testing each layer in isolation

## Subsystem Modifications Required

### Firmware/Host Application
1. `host_application/src/data_manager.py`: 
   - Add WebSocket client to publish live data to backend
   - Maintain backward compatibility with existing local recording
2. Optional: Modify firmware serializer to include additional metadata if needed

### ML Pipeline
1. `ml_pipeline/models/multibranch_fusion_net.py`:
   - Modify forward pass to return uncertainty estimates for SOH
   - Add method for modality masking (zero out specific modality branches)
   - Ensure model outputs calibrated probabilities

### Active Rebalancing
1. `active_rebalancing/decision_engine/state_machine.py`:
   - Refactor to accept DiagnosticFrame as input format
   - Standardize output command format for backend consumption
   - Add persistence hooks for recovery effectiveness tracking
   - Decouple from direct hardware control (backend will handle that)

### 3D Simulation
1. `simulation_3d_demo/ev_battery_3d_simulation.py`:
   - Extract sensor computation into callable function
   - Expose parameters for external control (SOC, degradation mode, etc.)
   - Maintain existing interactive mode for standalone use

## Development Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Create shared DiagnosticFrame TypeScript interface
- [ ] Set up FastAPI backend with WebSocket endpoints
- [ ] Implement basic frame ingestion from 3D simulation
- [ ] Create frontend shell with three synchronized views
- [ ] Define communication protocols between layers

### Phase 2: Core Integration (Weeks 3-4)
- [ ] Implement firmware data ingestion pipeline
- [ ] Integrate ML pipeline with uncertainty outputs
- [ ] Connect active rebalancing decision engine
- [ ] Implement basic recording/replay functionality
- [ ] Create initial ML fusion and rebalancing panels

### Phase 3: Simulation Modes (Weeks 5-6)
- [ ] Export Simulink model as FMU
- [ ] Implement FMU ingestion backend
- [ ] Complete 3D simulation integration
- [ ] Implement mode switching functionality
- [ ] Add synchronized timeline controls

### Phase 4: Evidence Features (Weeks 7-8)
- [ ] Implement modality ablation studies
- [ ] Add baseline comparison functionality
- [ ] Create before/after rebalancing logging
- [ ] Build evidence generation UI views
- [ ] Add PNG/SVG export capabilities

### Phase 5: Polish and Validation (Weeks 9-10)
- [ ] Performance optimization and load testing
- [ ] User acceptance testing with sample datasets
- [ ] Documentation and deployment instructions
- [ ] Video demonstration recording
- [ ] Final review against IDP requirements

## Risks and Mitigations

### Risk: FMU Export Complexity
- **Mitigation**: Start with simple exported model, iterate to include all necessary outputs
- **Backup**: Use precomputed 3D simulation data as fallback during development

### Risk: WebSocket Bandwidth with High-Frequency Data
- **Mitigation**: 
  - Implement frame decimation option (e.g., send every Nth frame)
  - Use binary protocol (MessagePack) instead of JSON
  - Allow client-side subspecifications (e.g., only send updates when values change significantly)

### Risk: ML Model Latency Affecting Real-Time Feel
- **Mitigation**:
  - Run ML processing on separate thread/process
  - Implement prediction caching for identical inputs
  - Show processing latency indicator in UI
  - Allow configuration of ML update rate vs sensor sample rate

### Risk: Synchronization Complexity Between Three Views
- **Mitigation**:
  - Single source of truth in backend stream
  - Frontend derives all views from same DiagnosticFrame
  - Use immutable data patterns to prevent accidental drift
  - Comprehensive integration testing of mode transitions

## Success Criteria

By end of November deadline, the system will:
1. Run fully functional in zero-hardware, zero-MATLAB mode
2. Provide three visually synchronized views (live, simulink, 3d) with shared controls
3. Display ML fusion outputs with uncertainty/confidence values
4. Show active rebalancing state with explainable action selection
5. Include all four evidence-generation features
6. Export charts and data in publication-ready formats (PNG/SVG/CSV)
7. Provide clear documentation for hardware/MATLAB enablement when available
8. Meet interdisciplinary design project requirements for publication/patent submission