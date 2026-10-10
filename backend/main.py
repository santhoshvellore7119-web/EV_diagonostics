"""
Main FastAPI application for the Unified Diagnostic Dashboard.
Provides REST API endpoints and WebSocket streaming for DiagnosticFrame data.
Integrates Data Ingestors, PyTorch ML Fusion, and Active Rebalancing Engine.
"""

import asyncio
import json
import uuid
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import numpy as np
import subprocess

import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
project_root = os.path.dirname(backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.diagnostic_schema import DiagnosticFrame

# Import ingestors, ML processor, and Rebalancing processor
try:
    from .ingest.threed import ThreedIngestor
    from .ingest.gazebo import GazeboIngestor
    from .ingest.simulink import SimulinkIngestor
    from .ingest.firmware import FirmwareIngestor
    from .ml_processor import MLProcessor
    from .rebalancing import RebalancingProcessor
    from .evidence import EvidenceGenerator
except (ImportError, ValueError):
    from ingest.threed import ThreedIngestor
    from ingest.gazebo import GazeboIngestor
    from ingest.simulink import SimulinkIngestor
    from ingest.firmware import FirmwareIngestor
    from ml_processor import MLProcessor
    from rebalancing import RebalancingProcessor
    from evidence import EvidenceGenerator

try:
    from .battery_physics import DynamicBatteryPhysicsEngine, BATTERY_CHEMISTRIES, FORM_FACTOR_GEOMETRY
except (ImportError, ValueError):
    from battery_physics import DynamicBatteryPhysicsEngine, BATTERY_CHEMISTRIES, FORM_FACTOR_GEOMETRY

try:
    from .machine_cycle import MachineCycleController
    from .ascan_synthesizer import synthesize_rf_ascan_waveform
except (ImportError, ValueError):
    from machine_cycle import MachineCycleController
    from ascan_synthesizer import synthesize_rf_ascan_waveform


class FrameBuffer:
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.buffer: List[Dict[str, Any]] = []

    def add(self, frame: Dict[str, Any]):
        """Add a frame to the buffer, maintaining max size."""
        self.buffer.append(frame)
        if len(self.buffer) > self.max_size:
            self.buffer.pop(0)

    def get_latest(self) -> Optional[Dict[str, Any]]:
        """Get the most recent frame."""
        return self.buffer[-1] if self.buffer else None

    def get_historical(self, start: int = 0, end: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get historical frames by index."""
        if end is None:
            end = len(self.buffer)
        return self.buffer[start:end]


# Global instances
frame_buffer = FrameBuffer(max_size=10000)

# Processors & Machine Workflow Controllers
ml_processor = MLProcessor(sequence_length=256)
rebalancing_processor = RebalancingProcessor()
evidence_generator = EvidenceGenerator(max_buffer_size=10000)
machine_controller = MachineCycleController()

# Ingestor instances
firmware_ingestor = FirmwareIngestor()
simulink_ingestor = SimulinkIngestor(fmu_path="backend/fmu/ev_cell_digital_twin.fmu")
threed_ingestor = ThreedIngestor()
gazebo_ingestor = GazeboIngestor()

# Active ingestor
active_ingestor = threed_ingestor
active_mode = "3d"


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize processors and ingestors
    print("Initializing Unified Diagnostic Dashboard Backend...")
    try:
        await ml_processor.initialize()
    except Exception as e:
        print(f"Warning: ML processor initialization error: {e}")

    try:
        await threed_ingestor.initialize()
    except Exception as e:
        print(f"Warning: 3D ingestor initialization error: {e}")

    try:
        await gazebo_ingestor.initialize()
    except Exception as e:
        print(f"Warning: Gazebo ingestor initialization error: {e}")

    print("Starting diagnostic data streaming task (10 Hz)...")
    simulation_task = asyncio.create_task(simulate_data())
    yield

    # Shutdown: cancel background tasks and cleanup
    simulation_task.cancel()
    try:
        await simulation_task
    except asyncio.CancelledError:
        pass

    if hasattr(threed_ingestor, 'cleanup'):
        await threed_ingestor.cleanup()
    if hasattr(gazebo_ingestor, 'cleanup'):
        await gazebo_ingestor.cleanup()
    if hasattr(firmware_ingestor, 'disconnect'):
        await firmware_ingestor.disconnect()
    if hasattr(simulink_ingestor, 'terminate'):
        await simulink_ingestor.terminate()



app = FastAPI(
    title="Unified Diagnostic Dashboard API",
    version="1.0.0",
    description="Backend API and WebSocket streaming for Multi-Modal EV Battery Diagnostics & Active Rebalancing",
    lifespan=lifespan
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API
class DiagnosticFrameBase(BaseModel):
    timestamp: float
    frameId: str
    source: str  # 'live', 'simulink', '3d', 'gazebo'
    cellId: str
    packId: Optional[str] = None

    # Electrical data
    electrical_voltage: float
    electrical_current: float
    electrical_power: float
    electrical_resistance: float
    electrical_uncertainty: float

    # Ultrasonic data
    ultrasonic_timeOfFlight: float
    ultrasonic_amplitude: float
    ultrasonic_phaseShift: float
    ultrasonic_speedOfSound: float
    ultrasonic_uncertainty: float

    # Thermal data
    thermal_temperature: float
    thermal_tempGradient: float
    thermal_heatFlux: float
    thermal_uncertainty: float

    # State of Health
    stateOfHealth_value: float
    stateOfHealth_confidenceInterval_lower: float
    stateOfHealth_confidenceInterval_upper: float
    stateOfHealth_method: str

    # Degradation classification
    degradation_mode: str
    degradation_probability: float
    degradation_perClass_healthy: float
    degradation_perClass_li_plating: float
    degradation_perClass_active_material_loss: float
    degradation_perClass_electrolyte_decomposition: float
    degradation_perClass_gas_generation: float
    degradation_perClass_internal_short: float
    degradation_entropy: float

    # Rebalancing state
    rebalancing_state: str
    rebalancing_active: Optional[bool] = False
    rebalancing_selectedAction: str
    rebalancing_actionReason: str
    rebalancing_powerStage_targetCurrent: float
    rebalancing_powerStage_actualCurrent: float
    rebalancing_powerStage_targetVoltage: float
    rebalancing_powerStage_actualVoltage: float
    rebalancing_powerStage_pwmDutyCycle: float
    rebalancing_executionTime: float
    zvs_efficiency_pct: Optional[float] = 0.0

    # Data provenance and origin
    data_origin: Optional[str] = 'LIVE'

    # Simulation fields (optional)
    simulation_soc: Optional[float] = None
    simulation_excitationAmplitude: Optional[float] = None
    simulation_noiseLevel: Optional[float] = None
    simulation_stepCount: Optional[int] = None


class DiagnosticFrame(DiagnosticFrameBase):
    pass


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected WebSocket clients."""
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                if connection in self.active_connections:
                    self.active_connections.remove(connection)


manager = ConnectionManager()


# API Endpoints
@app.get("/")
@app.get("/api/status")
async def root():
    return {
        "name": "Unified Diagnostic Dashboard API",
        "version": "1.0.0",
        "status": "online",
        "active_mode": active_mode
    }


@app.get("/gazebo")
async def get_gazebo_viewer():
    """Serve the interactive Gazebo 3D Digital Twin Studio."""
    viewer_path = os.path.join(backend_dir, "static", "gazebo_viewer.html")
    if os.path.exists(viewer_path):
        return FileResponse(viewer_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Gazebo viewer not found")


@app.get("/api/gazebo/open")
@app.post("/api/gazebo/open")
async def open_gazebo():
    """Trigger or redirect to Gazebo 3D World / Digital Twin viewer."""
    return {
        "status": "success",
        "action": "open_viewer",
        "url": "/gazebo",
        "message": "Gazebo 3D Studio opened successfully."
    }


def find_matlab_executable() -> Optional[str]:
    """Finds the local MATLAB executable across PATH, Program Files, and registry."""
    import shutil
    import glob

    # 1. Check system PATH
    which_path = shutil.which("matlab")
    if which_path and os.path.exists(which_path):
        return which_path

    # 2. Check standard Windows Program Files
    candidates = [
        r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe",
        r"C:\Program Files\MATLAB\R2025a\bin\matlab.exe",
        r"C:\Program Files\MATLAB\R2024b\bin\matlab.exe",
        r"C:\Program Files\MATLAB\R2024a\bin\matlab.exe",
        r"C:\Program Files\MATLAB\R2023b\bin\matlab.exe",
        r"C:\Program Files\MATLAB\R2023a\bin\matlab.exe",
        r"C:\Program Files\MATLAB\R2022b\bin\matlab.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    # 3. Dynamic glob search in MATLAB root directory
    matlab_root = r"C:\Program Files\MATLAB"
    if os.path.exists(matlab_root):
        matches = glob.glob(os.path.join(matlab_root, "*", "bin", "matlab.exe"))
        if matches:
            # Pick highest version
            return sorted(matches)[-1]

    return None


@app.get("/api/simulink/open")
@app.post("/api/simulink/open")
async def open_simulink():
    """
    Launch or redirect to MATLAB Simulink model (ev_cell_digital_twin.slx).
    Directly opens the MATLAB desktop software installed on the PC.
    """
    launch_script = os.path.join(project_root, "matlab_simulink_demo", "launch_simulink.m")
    demo_dir = os.path.join(project_root, "matlab_simulink_demo")
    slx_path = os.path.join(demo_dir, "models", "ev_cell_digital_twin.slx")
    matlab_cmd = f"run('{launch_script.replace(os.sep, '/')}');"

    matlab_exe = find_matlab_executable()
    launched = False
    error_msg = None

    if matlab_exe and os.path.exists(matlab_exe):
        try:
            print(f"[MATLAB Launcher] Found MATLAB at: {matlab_exe}. Spawning process...")
            cmd = [
                matlab_exe,
                "-sd", demo_dir,
                "-r", f"run('{launch_script.replace(os.sep, '/')}');"
            ]
            if sys.platform == "win32":
                DETACHED_PROCESS = 0x00000008
                subprocess.Popen(cmd, creationflags=DETACHED_PROCESS, close_fds=True)
            else:
                subprocess.Popen(cmd)
            launched = True
        except Exception as e:
            error_msg = str(e)
            print(f"[MATLAB Launcher] Error spawning MATLAB executable: {e}")
    else:
        # Fallback to general system command
        try:
            subprocess.Popen(["matlab", "-sd", demo_dir, "-r", matlab_cmd], shell=True)
            launched = True
        except Exception as e:
            error_msg = str(e)

    return {
        "status": "success" if launched else "fallback",
        "launched_locally": launched,
        "matlab_executable": matlab_exe,
        "model_name": "ev_cell_digital_twin",
        "model_path": slx_path,
        "launch_script": launch_script,
        "matlab_command": matlab_cmd,
        "instructions": f"In MATLAB Command Window, run:\naddpath(genpath('{demo_dir.replace(os.sep, '/')}'));\nrun('{launch_script.replace(os.sep, '/')}');"
    }


@app.get("/api/matlab/ml_demo/open")
@app.post("/api/matlab/ml_demo/open")
async def open_matlab_ml_demo():
    """Launch the standalone Multi-Modal ML Fusion Demonstrator in MATLAB."""
    launch_script = os.path.join(project_root, "run_matlab_ml_demo.m")
    matlab_cmd = f"run('{launch_script.replace(os.sep, '/')}');"
    matlab_exe = find_matlab_executable()
    launched = False

    if matlab_exe and os.path.exists(matlab_exe):
        try:
            cmd = [
                matlab_exe,
                "-sd", project_root,
                "-r", f"run('{launch_script.replace(os.sep, '/')}');"
            ]
            if sys.platform == "win32":
                DETACHED_PROCESS = 0x00000008
                subprocess.Popen(cmd, creationflags=DETACHED_PROCESS, close_fds=True)
            else:
                subprocess.Popen(cmd)
            launched = True
        except Exception as e:
            print(f"[MATLAB ML Launcher] Error spawning MATLAB: {e}")
    else:
        try:
            subprocess.Popen(["matlab", "-sd", project_root, "-r", matlab_cmd], shell=True)
            launched = True
        except Exception:
            pass

    return {
        "status": "success" if launched else "fallback",
        "launched_locally": launched,
        "script": "run_matlab_ml_demo.m",
        "matlab_command": matlab_cmd,
        "instructions": f"In MATLAB Command Window run:\nrun('{launch_script.replace(os.sep, '/')}');"
    }


@app.get("/api/machine/status")
async def get_machine_status():
    """Get the current state and metrics of the 6-stage automated test machine."""
    return machine_controller.get_status()


@app.post("/api/machine/cycle/start")
async def start_machine_cycle(degradation_mode: Optional[str] = 'healthy'):
    """Initiate the 6-stage automated robotic diagnostic and recovery cycle."""
    if not machine_controller.is_running:
        asyncio.create_task(machine_controller.start_automated_cycle(degradation_mode))
    return {"status": "started", "machine": machine_controller.get_status()}


@app.post("/api/machine/format/set")
async def set_cell_format(format_name: str = Query(..., description="18650_cylindrical, 21700_cylindrical, prismatic_100ah, pouch_60ah")):
    """Set the active cell form factor geometry and clamping parameters."""
    machine_controller.set_cell_format(format_name)
    return {"status": "success", "selected_format": format_name, "info": machine_controller.get_status()}


@app.get("/api/ascan/latest")
async def get_latest_ascan():
    """Get synthesized 10 MHz RF Ultrasonic A-scan oscillogram with defect echo detection."""
    latest = frame_buffer.get_latest()
    tof = latest.get("ultrasonic_timeOfFlight", 8.0) if latest else 8.0
    sos = latest.get("ultrasonic_speedOfSound", 2500.0) if latest else 2500.0
    deg = latest.get("degradation_mode", "healthy") if latest else "healthy"
    att = latest.get("ultrasonic_amplitude", 1.0) if latest else 1.0
    fmt = machine_controller.selected_format
    return synthesize_rf_ascan_waveform(tof_us=tof, sos=sos, degradation_mode=deg, attenuation=att, cell_format=fmt)


@app.get("/api/frames/latest")
async def get_latest_frame():
    """Get the most recent DiagnosticFrame."""
    latest = frame_buffer.get_latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No frames available yet")
    return latest


@app.get("/api/frames/historical")
async def get_historical_frames(start: int = 0, end: Optional[int] = None):
    """Get historical frames by index range."""
    frames = frame_buffer.get_historical(start, end)
    return {"frames": frames, "count": len(frames)}


@app.get("/api/mode/current")
async def get_current_mode():
    """Get the current active data mode."""
    return {"mode": active_mode}


@app.post("/api/mode/set")
async def set_mode(mode: str = Query(..., description="Data source mode: live, simulink, 3d, or gazebo")):
    """Set the active data source mode (live, simulink, 3d, gazebo)."""
    global active_ingestor, active_mode
    valid_modes = ['live', 'simulink', '3d', 'gazebo']
    if mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Must be one of {valid_modes}")

    # Switch to the appropriate ingestor
    if mode == 'live':
        active_ingestor = firmware_ingestor
    elif mode == 'simulink':
        active_ingestor = simulink_ingestor
    elif mode == '3d':
        active_ingestor = threed_ingestor
    elif mode == 'gazebo':
        active_ingestor = gazebo_ingestor

    active_mode = mode
    ml_processor.reset_buffers()
    print(f"Switched active mode to: {mode}")
    return {"message": f"Mode set to {mode}", "mode": mode}


# --- Physical Serial Hardware Ingestion Endpoints ---
@app.get("/api/firmware/ports")
async def list_serial_ports():
    """List physical serial COM ports detected on the host machine."""
    ports = firmware_ingestor.list_available_ports()
    return {"ports": ports, "count": len(ports)}


class FirmwareConnectRequest(BaseModel):
    port: str
    baudrate: Optional[int] = 115200


@app.post("/api/firmware/connect")
async def connect_firmware(req: FirmwareConnectRequest):
    """Connect to a physical hardware serial COM port."""
    success = await firmware_ingestor.connect(port=req.port, baudrate=req.baudrate)
    if success:
        return {"status": "connected", "port": req.port, "baudrate": req.baudrate}
    else:
        raise HTTPException(status_code=400, detail=f"Failed to connect to serial port {req.port}")


@app.post("/api/firmware/disconnect")
async def disconnect_firmware():
    """Disconnect from physical hardware serial port."""
    await firmware_ingestor.disconnect()
    return {"status": "disconnected"}


@app.get("/api/firmware/status")
async def get_firmware_status():
    """Get live hardware connection status and port details."""
    return firmware_ingestor.get_status()


# --- Dynamic Battery Chemistry & Physics Configuration Endpoints ---
@app.get("/api/battery/chemistries")
async def get_battery_chemistries():
    """Get canonical electrochemical profiles for all supported battery chemistries."""
    return {"chemistries": BATTERY_CHEMISTRIES}


@app.get("/api/battery/form_factors")
async def get_battery_form_factors():
    """Get geometric dimensions for all cell form factors."""
    return {"form_factors": FORM_FACTOR_GEOMETRY}


class BatteryParamUpdateRequest(BaseModel):
    chemistry: Optional[str] = None
    form_factor: Optional[str] = None
    soc: Optional[float] = None
    ambient_temp_c: Optional[float] = None
    load_current_c: Optional[float] = None
    cycle_count: Optional[int] = None
    degradation_mode: Optional[str] = None
    noise_level: Optional[float] = None
    excitation_amplitude: Optional[float] = None


@app.post("/api/battery/parameters/set")
async def set_battery_parameters(params: BatteryParamUpdateRequest):
    """Dynamically set physical parameters across all simulation models in real-time."""
    pdict = {k: v for k, v in params.model_dump().items() if v is not None} if hasattr(params, 'model_dump') else {k: v for k, v in params.dict().items() if v is not None}
    
    # Propagate to 3D and Gazebo ingestors
    for ing in [threed_ingestor, gazebo_ingestor]:
        if hasattr(ing, 'set_parameters'):
            await ing.set_parameters(**pdict)
            
    # Propagate format to machine controller if provided
    if params.form_factor:
        machine_controller.set_cell_format(params.form_factor)
        
    return {"status": "updated", "parameters": pdict}


@app.get("/api/battery/state")
async def get_battery_state():
    """Get current physical state from active simulator."""
    if hasattr(active_ingestor, 'engine'):
        return active_ingestor.engine.get_state()
    return {"status": "no_physics_engine_in_mode", "mode": active_mode}


@app.post("/api/simulation/parameters")
async def set_simulation_parameters(
    degradation_mode: Optional[str] = None,
    soc: Optional[float] = None,
    noise_level: Optional[float] = None,
    excitation_amplitude: Optional[float] = None,
    chemistry: Optional[str] = None,
    form_factor: Optional[str] = None,
    ambient_temp_c: Optional[float] = None,
    load_current_c: Optional[float] = None,
    cycle_count: Optional[int] = None
):
    """Dynamically propagate simulation parameters to all ingestors and underlying simulators."""
    valid_degs = ['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition', 'gas_generation', 'internal_short']
    if degradation_mode is not None and degradation_mode not in valid_degs:
        raise HTTPException(status_code=400, detail=f"Invalid degradation_mode. Must be one of {valid_degs}")

    params = {}
    if degradation_mode is not None: params['degradation_mode'] = degradation_mode
    if soc is not None: params['soc'] = soc
    if noise_level is not None: params['noise_level'] = noise_level
    if excitation_amplitude is not None: params['excitation_amplitude'] = excitation_amplitude
    if chemistry is not None: params['chemistry'] = chemistry
    if form_factor is not None: params['form_factor'] = form_factor
    if ambient_temp_c is not None: params['ambient_temp_c'] = ambient_temp_c
    if load_current_c is not None: params['load_current_c'] = load_current_c
    if cycle_count is not None: params['cycle_count'] = cycle_count

    for ing in [threed_ingestor, gazebo_ingestor, simulink_ingestor, firmware_ingestor]:
        if hasattr(ing, 'set_parameters'):
            await ing.set_parameters(**params)
        else:
            if degradation_mode is not None and hasattr(ing, 'degradation_mode'):
                ing.degradation_mode = degradation_mode
            if soc is not None and hasattr(ing, 'soc'):
                ing.soc = soc
            if noise_level is not None and hasattr(ing, 'noise_level'):
                ing.noise_level = noise_level
            if excitation_amplitude is not None and hasattr(ing, 'excitation_amplitude'):
                ing.excitation_amplitude = excitation_amplitude

    if form_factor:
        machine_controller.set_cell_format(form_factor)

    return {
        "status": "updated",
        **params
    }


# WebSocket endpoint for real-time frame streaming
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Send immediate latest frame on connect if available
    latest = frame_buffer.get_latest()
    if latest:
        try:
            await websocket.send_json(latest)
        except Exception:
            pass

    try:
        while True:
            # Keep connection open and receive any client messages/commands
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                mtype = msg.get("type")
                if mtype == "set_mode" and msg.get("mode") in ['live', 'simulink', '3d', 'gazebo']:
                    await set_mode(msg["mode"])
                elif mtype in ["set_parameters", "set_simulation_parameters", "set_degradation_mode"]:
                    deg = msg.get("degradation_mode") or msg.get("mode")
                    soc = msg.get("soc")
                    noise = msg.get("noise_level")
                    exc = msg.get("excitation_amplitude")
                    await set_simulation_parameters(
                        degradation_mode=deg,
                        soc=soc,
                        noise_level=noise,
                        excitation_amplitude=exc
                    )
            except Exception as e:
                print(f"Error handling websocket client message: {e}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)


# Data pipeline streaming loop (10 Hz)
async def simulate_data():
    """Streaming loop fetching frames from ingestor, passing through ML and Rebalancing."""
    frame_id = 0
    while True:
        try:
            frame = None

            # --- STRICT ISOLATION: LIVE HARDWARE vs SIMULATION MODES ---
            if active_mode == 'live':
                if firmware_ingestor.is_connected:
                    raw_hw = await firmware_ingestor.read_frame()
                    if raw_hw is not None:
                        frame = raw_hw
                    else:
                        frame = firmware_ingestor.last_hardware_packet

                if frame is None:
                    # Hardware disconnected: do NOT generate fake simulated readings
                    ports = firmware_ingestor.list_available_ports()
                    frame = {
                        "timestamp": time.time(),
                        "frameId": f"HW-DISCONNECTED-{frame_id:06d}",
                        "source": "live",
                        "data_origin": "LIVE-DISCONNECTED",
                        "hardware_connected": False,
                        "cellId": "physical_serial_port",
                        "packId": "live_hardware_pack",
                        "status_message": "Hardware Disconnected: Connect ESP32 / DAQ on physical COM port to stream live sensor data.",
                        "available_ports": ports,

                        # Electrical data (zeroed when hardware not attached)
                        "electrical_voltage": 0.0,
                        "electrical_current": 0.0,
                        "electrical_power": 0.0,
                        "electrical_resistance": 0.0,
                        "electrical_uncertainty": 0.0,

                        # Ultrasonic data
                        "ultrasonic_timeOfFlight": 0.0,
                        "ultrasonic_amplitude": 0.0,
                        "ultrasonic_phaseShift": 0.0,
                        "ultrasonic_speedOfSound": 0.0,
                        "ultrasonic_uncertainty": 0.0,

                        # Thermal data
                        "thermal_temperature": 0.0,
                        "thermal_tempGradient": 0.0,
                        "thermal_heatFlux": 0.0,
                        "thermal_uncertainty": 0.0,

                        # State of Health
                        "stateOfHealth_value": 0.0,
                        "stateOfHealth_confidenceInterval_lower": 0.0,
                        "stateOfHealth_confidenceInterval_upper": 0.0,
                        "stateOfHealth_method": "hardware_port_disconnected",

                        # Degradation classification
                        "degradation_mode": "disconnected",
                        "degradation_probability": 0.0,
                        "degradation_perClass_healthy": 0.0,
                        "degradation_perClass_li_plating": 0.0,
                        "degradation_perClass_active_material_loss": 0.0,
                        "degradation_perClass_electrolyte_decomposition": 0.0,
                        "degradation_perClass_gas_generation": 0.0,
                        "degradation_perClass_internal_short": 0.0,
                        "degradation_entropy": 0.0,

                        # Rebalancing state
                        "rebalancing_state": "DISCONNECTED",
                        "rebalancing_selectedAction": "none",
                        "rebalancing_actionReason": "No physical COM port connected",
                        "rebalancing_powerStage_targetCurrent": 0.0,
                        "rebalancing_powerStage_actualCurrent": 0.0,
                        "rebalancing_powerStage_targetVoltage": 0.0,
                        "rebalancing_powerStage_actualVoltage": 0.0,
                        "rebalancing_powerStage_pwmDutyCycle": 0.0,
                        "rebalancing_executionTime": 0.0
                    }
            else:
                # Simulation modes (3d, gazebo, simulink)
                if active_ingestor is not None:
                    if hasattr(active_ingestor, 'get_frame'):
                        frame = await active_ingestor.get_frame()
                    elif hasattr(active_ingestor, 'read_frame'):
                        frame = await active_ingestor.read_frame()
                    elif hasattr(active_ingestor, 'step'):
                        frame = await active_ingestor.step()

                if frame is None:
                    frame = _generate_fallback_frame()

            # Ensure correct source label
            frame["source"] = active_mode

            # Only run ML & Rebalancing if hardware is connected or in simulation mode
            if frame.get("data_origin") != "LIVE-DISCONNECTED":
                # 2. Process frame through ML pipeline (SOH estimation + degradation classification)
                enhanced_frame = await ml_processor.process_frame(frame)
                if enhanced_frame is not None:
                    frame = enhanced_frame

                # 3. Process frame through Active Rebalancing engine
                rebalancing_info = rebalancing_processor.process_frame(frame)
                if rebalancing_info:
                    frame.update(rebalancing_info)

            # 3.5 Generate live A-Scan RF waveform & machine status overlay
            tof_val = float(frame.get('ultrasonic_timeOfFlight', 8.0))
            sos_val = float(frame.get('ultrasonic_speedOfSound', 2500.0))
            deg_val = str(frame.get('degradation_mode', 'healthy'))
            att_val = float(frame.get('ultrasonic_amplitude', 1.0))
            fmt_val = str(machine_controller.selected_format)

            frame['ascan_waveform'] = synthesize_rf_ascan_waveform(
                tof_us=tof_val if tof_val > 0 else 8.0,
                sos=sos_val if sos_val > 0 else 2500.0,
                degradation_mode=deg_val if deg_val != 'disconnected' else 'healthy',
                attenuation=att_val if att_val > 0 else 1.0,
                cell_format=fmt_val
            )
            frame['machine_cycle'] = machine_controller.get_status()

            # 4. Record frame in evidence generator (if active) and buffer
            if evidence_generator.is_recording and frame.get("data_origin") != "LIVE-DISCONNECTED":
                evidence_generator.record_frame(frame)

            frame_buffer.add(frame)

            # 5. Broadcast to connected WebSocket clients
            await manager.broadcast(frame)

            frame_id += 1
            await asyncio.sleep(0.1)  # 10 Hz update rate

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in data simulation loop: {e}")
            await asyncio.sleep(1.0)


_fallback_physics_engine = DynamicBatteryPhysicsEngine()

def _generate_fallback_frame() -> Dict[str, Any]:
    """Generate a physical dynamic frame when ingestors are not available."""
    raw_physics = _fallback_physics_engine.step(dt=0.1)
    frame = {
        "timestamp": raw_physics["timestamp"],
        "frameId": f"PHYS-SIM-{int(time.time()*1000)%1000000:06d}",
        "source": active_mode if active_mode in ['live', 'simulink', '3d', 'gazebo'] else "3d",
        "data_origin": "DYNAMIC-BATTERY-PHYSICS",
        "cellId": f"cell_{_fallback_physics_engine.chemistry}_{_fallback_physics_engine.form_factor}",
        "packId": "pack_001",
        "battery_chemistry": raw_physics["chemistry"],
        "battery_chemistry_name": raw_physics["chemistry_name"],
        "battery_form_factor": raw_physics["form_factor"],
        "battery_form_factor_name": raw_physics["form_factor_name"],

        # Electrical data
        "electrical_voltage": raw_physics["electrical_voltage"],
        "electrical_current": raw_physics["electrical_current"],
        "electrical_power": raw_physics["electrical_power"],
        "electrical_resistance": raw_physics["electrical_resistance"],
        "electrical_uncertainty": raw_physics["electrical_uncertainty"],

        # Ultrasonic data
        "ultrasonic_timeOfFlight": raw_physics["ultrasonic_timeOfFlight"],
        "ultrasonic_amplitude": raw_physics["ultrasonic_amplitude"],
        "ultrasonic_phaseShift": raw_physics["ultrasonic_phaseShift"],
        "ultrasonic_speedOfSound": raw_physics["ultrasonic_speedOfSound"],
        "ultrasonic_uncertainty": raw_physics["ultrasonic_uncertainty"],

        # Thermal data
        "thermal_temperature": raw_physics["thermal_temperature"],
        "thermal_tempGradient": raw_physics["thermal_tempGradient"],
        "thermal_heatFlux": raw_physics["thermal_heatFlux"],
        "thermal_uncertainty": raw_physics["thermal_uncertainty"],

        # State of Health
        "stateOfHealth_value": raw_physics["stateOfHealth_physical_ground_truth"],
        "stateOfHealth_confidenceInterval_lower": max(0.0, raw_physics["stateOfHealth_physical_ground_truth"] - 3.0),
        "stateOfHealth_confidenceInterval_upper": min(100.0, raw_physics["stateOfHealth_physical_ground_truth"] + 3.0),
        "stateOfHealth_method": "dynamic_physics_fusion",

        # Degradation classification
        "degradation_mode": raw_physics["degradation_mode"],
        "degradation_probability": 0.95,
        "degradation_perClass_healthy": 0.95 if raw_physics["degradation_mode"] == 'healthy' else 0.01,
        "degradation_perClass_li_plating": 0.95 if raw_physics["degradation_mode"] == 'li_plating' else 0.01,
        "degradation_perClass_active_material_loss": 0.95 if raw_physics["degradation_mode"] == 'active_material_loss' else 0.01,
        "degradation_perClass_electrolyte_decomposition": 0.95 if raw_physics["degradation_mode"] == 'electrolyte_decomposition' else 0.01,
        "degradation_perClass_gas_generation": 0.95 if raw_physics["degradation_mode"] == 'gas_generation' else 0.01,
        "degradation_perClass_internal_short": 0.95 if raw_physics["degradation_mode"] == 'internal_short' else 0.01,
        "degradation_entropy": 0.05,

        # Rebalancing state
        "rebalancing_state": "monitoring",
        "rebalancing_selectedAction": "none",
        "rebalancing_actionReason": "Nominal telemetry",
        "rebalancing_powerStage_targetCurrent": 0.0,
        "rebalancing_powerStage_actualCurrent": 0.0,
        "rebalancing_powerStage_targetVoltage": 0.0,
        "rebalancing_powerStage_actualVoltage": 0.0,
        "rebalancing_powerStage_pwmDutyCycle": 0.0,
        "rebalancing_executionTime": 0.0,

        # Simulation fields
        "simulation_soc": raw_physics["simulation_soc"],
        "simulation_temp_amb": raw_physics["simulation_temp_amb"],
        "simulation_load_c": raw_physics["simulation_load_c"],
        "simulation_cycle_count": raw_physics["simulation_cycle_count"],
        "simulation_noiseLevel": raw_physics["simulation_noiseLevel"],
        "simulation_excitationAmplitude": raw_physics["simulation_excitationAmplitude"],
        "simulation_stepCount": 0
    }
    diag = DiagnosticFrame.from_dict(frame)
    return diag.to_dict()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)