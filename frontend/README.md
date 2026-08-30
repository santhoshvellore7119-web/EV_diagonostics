# Unified Diagnostic Dashboard for EV Battery Management System

This is the frontend of the **Unified Diagnostic Dashboard** for the "Low-Cost Multi-Modal Diagnostic and Active Cell-Rebalancing System for Second-Life EV Battery Packs" project.

## Overview

The dashboard provides a single web interface to monitor and interact with five disconnected subsystems:

1. **Live Hardware** - ESP32/FreeRTOS firmware + host application (PyQt5)
2. **Simulink Simulation** - MATLAB/Simulink battery model (exported as FMU via Simulink Coder)
3. **3D Visualization** - Gazebo-based physics simulation with sensor data overlays
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
- **Real-time Data Streaming**: WebSocket connection for sub-second updates
- **Evidence Generation Features** (implemented in backend):
  - Modality ablation studies
  - Baseline comparison (fused model vs electrical-only)
  - Before/after rebalancing trend tracking
  - Session recording and replay capabilities
- **Responsive Design**: Works on different screen sizes

## Technology Stack

- **Frontend**: React 18 with TypeScript, Redux Toolkit for state management
- **Styling**: Custom CSS with responsive layout
- **Communication**: WebSocket for real-time data, REST API for configuration
- **Charting**: Custom SVG-based charts (SOH, Voltage, Temperature, Degradation)
- **Build Tool**: Create React App (CRA)

## Getting Started

### Prerequisites

- Node.js (v16 or higher)
- npm (v8 or higher)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/santhoshvellore7119-web/EV_diagonostics.git
   cd EV_diagonostics/frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

### Running the Application

1. **Start the Backend Server** (required for data):
   ```bash
   cd ../backend
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   The backend will run on `http://localhost:8000`

2. **Start the Frontend**:
   ```bash
   cd ../frontend
   npm start
   ```
   The frontend will run on `http://localhost:3000`

### Available Scripts

In the frontend project directory, you can run:

#### `npm start`
Runs the app in development mode. Open [http://localhost:3000](http://localhost:3000) to view it in the browser. The page will reload when you make edits, and you will see any lint errors in the console.

#### `npm test`
Launches the test runner in interactive watch mode.

#### `npm run build`
Builds the app for production to the `build` folder. It correctly bundles React in production mode and optimizes the build for best performance. The build is minified and includes content hashes.

#### `npm run eject`
**Note: this is a one-way operation.** If you aren't satisfied with the build tool and configuration choices, you can eject at any time. This command will remove the single build dependency from your project.

Instead, it will copy all configuration files and transitive dependencies (webpack, Babel, ESLint, etc.) into your project so you have full control over them. All commands except `eject` will still work, but they will point to the copied scripts.

## Project Structure

```
frontend/
├── public/                 # Static assets
│   ├── index.html          # Main HTML template
│   ├── favicon.ico         # Application icon
│   └── manifest.json       # PWA manifest
├── src/
│   ├── components/         # Reusable components
│   │   ├── charts/         # Data visualization charts
│   │   ├── panels/         # UI panels (ControlPanel, etc.)
│   │   └── views/          # Main views (LiveView, SimulinkView, ThreeDView)
│   ├── services/           # Service workers (WebSocket service)
│   ├── store/              # Redux store slices
│   ├── App.tsx             # Main application component
│   ├── index.tsx           # Entry point
│   └── ...                 # Styles, configuration files
```

## Configuration

The frontend connects to the backend via WebSocket. The WebSocket URL is configured via environment variable:

- `REACT_APP_WS_URL`: WebSocket URL (defaults to `ws://localhost:8000/ws`)

To change the backend URL, create a `.env` file in the frontend directory:
```
REACT_APP_WS_URL=ws://your-backend-domain:8000/ws
```

## Gazebo Integration

This dashboard includes built-in support for Gazebo/ROS 2 integration:

1. The Gazebo mode appears as a button in the control panel alongside Live, Simulink, and 3D options
2. When Gazebo mode is selected, the dashboard expects data from the Gazebo ingestor backend
3. The Gazebo ingestor (`backend/ingest/gazebo.py`) subscribes to ROS 2 topics and converts them to DiagnosticFrame format
4. If ROS 2 is not available, the system gracefully falls back to simulated Gazebo data

For detailed Gazebo setup instructions, see [docs/GAZEBO_INTEGRATION.md](../docs/GAZEBO_INTEGRATION.md).

## Data Format

All components communicate using the **DiagnosticFrame** schema, which includes:

- Timing and identification (timestamp, frameId, source, cellId)
- Electrical data (voltage, current, power, resistance, uncertainty)
- Ultrasonic data (time of flight, amplitude, phase shift, speed of sound)
- Thermal data (temperature, gradient, heat flux)
- State of Health (value, confidence intervals, method)
- Degradation classification (mode, probability, per-class scores)
- Rebalancing state (status, selected action, reason, power stage parameters)
- Simulation fields (SOC, excitation amplitude, noise level, step count)

## Development

### Code Style

- Follows standard React/TypeScript conventions
- Uses ESLint for code linting
- Components are organized by feature/function

### State Management

- Redux Toolkit is used for predictable state management
- Three main slices:
  - `diagnosticFrame`: Stores current frame data
  - `mode`: Tracks active view mode (live/simulink/3d/gazebo)
  - `timeline`: Manages playback controls and frame buffering

### Adding New Features

1. **New Chart**: Add to `src/components/charts/` and import in relevant panels
2. **New View**: Add to `src/components/views/` and include in `App.tsx`
3. **New Panel**: Add to `src/components/panels/` and include in `App.tsx`
4. **New Data Source**: 
   - Add backend ingestor in `backend/ingest/`
   - Update `backend/main.py` to instantiate and manage the ingestor
   - Add mode to `frontend/src/store/modeSlice.ts`
   - Update `frontend/src/components/panels/ControlPanel.tsx` for UI
   - Update `frontend/src/store/diagnosticFrameSlice.ts` for type support

## Deployment

To deploy the frontend:

1. Build for production:
   ```bash
   npm run build
   ```

2. The build output is in the `build/` directory
3. Deploy the contents of `build/` to any static web server (Apache, Nginx, CDN, etc.)

For backend deployment instructions, see the backend README.

## Related Documentation

- [Backend Implementation](../backend/README.md)
- [System Architecture](../docs/ARCHITECTURE.md)
- [Gazebo Integration Guide](../docs/GAZEBO_INTEGRATION.md)
- [Project Status](../PROJECT_STATUS.md)
- [Requirements](../REQUIREMENTS.md)

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## Acknowledgments

- Created as part of the EV battery diagnostic system project
- Built with Create React App
- Inspired by open-source dashboard and visualization projects