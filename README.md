# Unified Diagnostic Dashboard for EV Battery Management System

This repository contains the complete implementation of a **Unified Diagnostic Dashboard** for the "Low-Cost Multi-Modal Diagnostic and Active Cell-Rebalancing System for Second-Life EV Battery Packs" project.

## Overview

The system integrates five disconnected subsystems into a single web-based dashboard, enabling seamless switching between:

1. **Live Hardware** - Real-time data from ESP32/FreeRTOS firmware + host application (PyQt5)
2. **Simulink Simulation** - MATLAB/Simulink battery model exported as FMU via Simulink Coder
3. **3D Visualization** - Gazebo-based physics simulation with sensor data overlays (newly added)
4. **ML Pipeline** - PyTorch multi-branch fusion model for State of Health and degradation prediction
5. **Active Rebalancing** - Decision engine + PID controller for cell balancing

### Key Features

- **Three Synchronized Views**: Live data, Simulink simulation, and Gazebo 3D visualization
- **Always-Visible Panels**:
  - ML Fusion Panel: Shows State of Health, voltage, temperature, and degradation charts with uncertainty quantification
  - Rebalancing Panel: Displays current rebalancing status and parameters
- **Interactive Control Panel**:
  - Mode switching (Live/Simulink/3D/Gazebo)
  - Playback controls (Play/Pause, Speed control, Timeline scrubber)
  - Rebalancing controls (Trigger manual rebalancing, Reset system)
- **Real-time Data Streaming**: WebSocket connection for sub-second updates (10Hz)
- **Evidence Generation Features** (implemented in backend):
  - Modality ablation studies
  - Baseline comparison (fused model vs electrical-only)
  - Before/after rebalancing trend tracking
  - Session recording and replay capabilities
- **Responsive Design**: Works on different screen sizes
- **Shared DiagnosticFrame Schema**: Single source of truth across all modalities

## Technology Stack

### Backend
- **Language**: Python 3.12
- **Framework**: FastAPI with Uvicorn server
- **Communication**: WebSocket for real-time data, REST API for configuration
- **Data Handling**: Pydantic models for validation, in-memory frame buffering
- **Modules**:
  - Firmware ingestor (serial/ESP32 interface)
  - Simulink FMU ingestor
  - 3D simulation ingestor (using existing Python/OpenGL simulation)
  - Gazebo/ROS 2 ingestor (newly added)
  - ML processor (PyTorch multi-branch fusion)
  - Evidence generation module
  - Active rebalancing interface

### Frontend
- **Framework**: React 18 with TypeScript
- **State Management**: Redux Toolkit
- **Styling**: Custom CSS with responsive layout
- **Communication**: WebSocket service for real-time data
- **Charting**: Custom SVG-based charts (SOH, Voltage, Temperature, Degradation)
- **Views**: Three synchronized views (Live, Simulink, 3D/Gazebo)
- **Build Tool**: Create React App (CRA)

## Getting Started

### Prerequisites

- **Backend**: Python 3.12+, pip
- **Frontend**: Node.js (v16+), npm (v8+)
- **Optional for Gazebo**: Ubuntu 20.04/22.04 with ROS 2 (Foxy/Humble) and Gazebo/Ignition

### Backend Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/santhoshvellore7119-web/EV_diagonostics.git
   cd EV_diagonostics/backend
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   The backend API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd ../frontend
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```
   The frontend will be available at `http://localhost:3000`

### Using Gazebo Mode (Optional)

To use actual Gazebo simulation instead of the built-in fallback:

1. Install ROS 2 and Gazebo/Ignition on Ubuntu:
   - Follow instructions in [docs/GAZEBO_INTEGRATION.md](docs/GAZEBO_INTEGRATION.md)
2. Create or obtain an EV battery model that publishes to the expected ROS topics:
   - `/battery/voltage` (std_msgs/Float64)
   - `/battery/current` (std_msgs/Float64)
   - `/battery/temperature` (sensor_msgs/Temperature)
   - `/ultrasonic/time_of_flight` (std_msgs/Float64)
   - `/ultrasonic/amplitude` (std_msgs/Float64)
   - `/ultrasonic/phase_shift` (std_msgs/Float64)
   - `/thermal/heat_flux` (std_msgs/Float64)
   - `/battery/soc` (std_msgs/Float64)
   - `/battery/degradation_mode` (std_msgs/Float64)
3. Source the ROS 2 environment before starting the backend:
   ```bash
   source /opt/ros/<distro>/setup.bash
   ```
4. Launch your Gazebo battery simulation
5. Start the backend and frontend as usual
6. Select "Gazebo" mode in the control panel

If ROS 2 is not available, the system automatically falls back to simulated Gazebo data, ensuring the dashboard remains functional.

## Project Structure

```
EV_diagonostics/
├── backend/                  # Python/FastAPI backend
│   ├── main.py               # Application entry point
│   ├── ingest/               # Data ingestor modules
│   │   ├── firmware.py       # ESP32/FreeRTOS hardware interface
│   │   ├── simulink.py       # Simulink FMU interface
│   │   ├── threed.py         # 3D simulation interface
│   │   └── gazebo.py         # Gazebo/ROS 2 interface (new)
│   ├── evidence.py           # Evidence generation features
│   ├── ml_processor.py       # ML pipeline interface
│   ├── rebalancing.py        # Active rebalancing interface
│   ├── requirements.txt      # Python dependencies
│   └── ...                   # Supporting modules
├── frontend/                 # React/TypeScript frontend
│   ├── src/
│   │   ├── components/       # Reusable components (charts, panels, views)
│   │   ├── services/         # WebSocket service
│   │   ├── store/            # Redux store (diagnosticFrame, mode, timeline)
│   │   ├── App.tsx           # Main application component
│   │   └── ...               # Styles, configuration files
│   ├── public/               # Static assets
│   └── package.json          # npm dependencies
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md       # System architecture and design decisions
│   ├── GAZEBO_INTEGRATION.md # Guide for installing/configuring Gazebo/ROS 2
│   └── ...                   # Additional documentation
├── docs/                     # Original subsystem directories (unchanged)
│   ├── firmware/             # MCU firmware (ESP32/FreeRTOS)
│   ├── ml_pipeline/          # PyTorch-based machine learning pipeline
│   ├── active_rebalancing/   # Recovery algorithms
│   ├── hardware/             # Hardware documentation
│   ├── host_application/     # Host PC application (PyQt5)
│   ├── matlab_simulink_demo/ # MATLAB/Simulink digital twin
│   ├── simulation_3d_demo/   # 3D EV battery simulation (Python/OpenGL)
│   └── tests/                # Test scripts and utilities
├── PROJECT_STATUS.md         # Tracking of completed work and next steps
├── REQUIREMENTS.md           # High-level dependencies
├── LICENSE                   # MIT license
└── .gitignore                # Git ignore rules
```

## Data Format

All components communicate using the **DiagnosticFrame** schema, a shared JSON object that includes:

- **Timing and identification**: `timestamp`, `frameId`, `source` (live/simulink/3d/gazebo), `cellId`, `packId`
- **Electrical data**: `electrical_voltage`, `electrical_current`, `electrical_power`, `electrical_resistance`, `electrical_uncertainty`
- **Ultrasonic data**: `ultrasonic_timeOfFlight`, `ultrasonic_amplitude`, `ultrasonic_phaseShift`, `ultrasonic_speedOfSound`, `ultrasonic_uncertainty`
- **Thermal data**: `thermal_temperature`, `thermal_tempGradient`, `thermal_heatFlux`, `thermal_uncertainty`
- **State of Health**: `stateOfHealth_value`, `stateOfHealth_confidenceInterval_lower`, `stateOfHealth_confidenceInterval_upper`, `stateOfHealth_method`
- **Degradation classification**: `degradation_mode`, `degradation_probability`, per-class probabilities, `degradation_entropy`
- **Rebalancing state**: `rebalancing_state`, `rebalancing_selectedAction`, `rebalancing_actionReason`, power stage parameters (target/actual voltage/current, PWM duty cycle, execution time)
- **Simulation fields** (optional): `simulation_soc`, `simulation_excitationAmplitude`, `simulation_noiseLevel`, `simulation_stepCount`

## Evidende Generation Features

The backend includes modules for generating evidence suitable for publication and patent applications:

- **Modality Ablation Studies**: Compare system performance with different sensor modalities enabled/disabled
- **Baseline Comparison**: Evaluate fused model performance against electrical-only baseline
- **Before/After Rebalancing Trends**: Track changes in battery characteristics before and after rebalancing actions
- **Session Recording and Replay**: Save diagnostic sessions for later analysis and demonstration
- **Chart Export**: Generate PNG/SVG exports of all charts and views

These features are accessible via the backend API and can be extended as needed.

## Development Guidelines

### Backend
- Add new ingestors in `backend/ingest/` following the existing pattern (inherit base interface)
- Update `backend/main.py` to instantiate and manage new ingestors
- Add new modes to the `/api/mode/set` endpoint validation
- Ensure all modules return data conforming to the DiagnosticFrame schema

### Frontend
- Add new chart types to `src/components/charts/`
- Add new views to `src/components/views/` and include in `App.tsx`
- Update `src/components/panels/ControlPanel.tsx` for new mode buttons
- Extend Redux store slices:
  - `modeSlice.ts` for new mode types
  - `diagnosticFrameSlice.ts` for new fields (if needed)
- Use TypeScript interfaces for type safety

## Deployment

### Backend
- For production, consider using a process manager like `systemd`, `supervisor`, or Docker
- The server binds to `0.0.0.0:8000` by default; adjust host/port as needed
- Enable logging and monitoring as required for your deployment environment

### Frontend
1. Build for production:
   ```bash
   cd frontend
   npm run build
   ```
2. The build output is in the `build/` directory
3. Deploy the contents of `build/` to any static web server (Apache, Nginx, CDN, cloud storage, etc.)
4. Ensure the frontend can reach the backend WebSocket endpoint (adjust `REACT_APP_WS_URL` in `.env` if needed)

### Docker (Optional)
Dockerfiles can be added for both backend and frontend for containerized deployment.

## Related Documentation

- [Backend Documentation](../backend/README.md) - Detailed backend API and modules
- [System Architecture](../docs/ARCHITECTURE.md) - Complete system design with data flow diagrams
- [Gazebo Integration Guide](../docs/GAZEBO_INTEGRATION.md) - Step-by-step instructions for Gazebo/ROS 2 setup
- [Project Status](../PROJECT_STATUS.md) - Progress tracking and upcoming tasks
- [Requirements](../REQUIREMENTS.md) - High-level functional and non-functional requirements

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Developed as part of the EV battery diagnostic system project
- Built with FastAPI, React, TypeScript, and Redux Toolkit
- Inspired by open-source dashboard and visualization projects
- Thanks to contributors and open-source communities