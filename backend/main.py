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
from pydantic import BaseModel
import numpy as np

import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
project_root = os.path.dirname(backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

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

# Processors
ml_processor = MLProcessor(sequence_length=256)
rebalancing_processor = RebalancingProcessor()
evidence_generator = EvidenceGenerator(max_buffer_size=10000)

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

# Compatibility patch for Starlette 0.36+ / FastAPI 0.110+ router init
import inspect
import starlette.routing
from fastapi.routing import APIRouter

if 'on_startup' not in inspect.signature(starlette.routing.Router.__init__).parameters:
    _orig_apirouter_init = APIRouter.__init__

    def _patched_apirouter_init(
        self,
        *,
        prefix="",
        tags=None,
        dependencies=None,
        default_response_class=None,
        responses=None,
        callbacks=None,
        routes=None,
        redirect_slashes=True,
        default=None,
        dependency_overrides_provider=None,
        route_class=None,
        on_startup=None,
        on_shutdown=None,
        lifespan=None,
        deprecated=None,
        include_in_schema=True,
        generate_unique_id_function=None,
    ):
        if default_response_class is None:
            from fastapi.responses import JSONResponse
            default_response_class = JSONResponse
        if generate_unique_id_function is None:
            from fastapi.routing import generate_unique_id
            generate_unique_id_function = generate_unique_id

        super(APIRouter, self).__init__(
            routes=routes,
            redirect_slashes=redirect_slashes,
            default=default,
            lifespan=lifespan,
        )

        if prefix:
            assert prefix.startswith("/"), "A path prefix must start with '/'"
            assert not prefix.endswith("/"), "A path prefix must not end with '/'"
        self.prefix = prefix
        self.tags = tags or []
        self.dependencies = list(dependencies or [])
        self.deprecated = deprecated
        self.include_in_schema = include_in_schema
        self.responses = responses or {}
        self.callbacks = callbacks or []
        self.dependency_overrides_provider = dependency_overrides_provider
        from fastapi.routing import APIRoute
        self.route_class = route_class or APIRoute
        self.default_response_class = default_response_class
        self.generate_unique_id_function = generate_unique_id_function

    APIRouter.__init__ = _patched_apirouter_init


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
    rebalancing_selectedAction: str
    rebalancing_actionReason: str
    rebalancing_powerStage_targetCurrent: float
    rebalancing_powerStage_actualCurrent: float
    rebalancing_powerStage_targetVoltage: float
    rebalancing_powerStage_actualVoltage: float
    rebalancing_powerStage_pwmDutyCycle: float
    rebalancing_executionTime: float

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
async def root():
    return {
        "name": "Unified Diagnostic Dashboard API",
        "version": "1.0.0",
        "status": "online",
        "active_mode": active_mode
    }


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
                if msg.get("type") == "set_mode" and msg.get("mode") in ['live', 'simulink', '3d', 'gazebo']:
                    await set_mode(msg["mode"])
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)


# Data pipeline simulation loop (10 Hz)
async def simulate_data():
    """Streaming loop fetching frames from ingestor, passing through ML and Rebalancing."""
    frame_id = 0
    while True:
        try:
            # 1. Fetch raw frame from active ingestor
            frame = None
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

            # 2. Process frame through ML pipeline (SOH estimation + degradation classification)
            enhanced_frame = await ml_processor.process_frame(frame)
            if enhanced_frame is not None:
                frame = enhanced_frame

            # 3. Process frame through Active Rebalancing engine
            rebalancing_info = rebalancing_processor.process_frame(frame)
            if rebalancing_info:
                frame.update(rebalancing_info)

            # 4. Record frame in evidence generator (if active) and buffer
            if evidence_generator.is_recording:
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


def _generate_fallback_frame() -> Dict[str, Any]:
    """Generate a fallback frame when ingestors are not available."""
    base_v = 3.6 + random.uniform(-0.1, 0.1)
    base_i = 1.5 + random.uniform(-0.2, 0.2)
    frame = {
        "timestamp": time.time(),
        "frameId": str(uuid.uuid4()),
        "source": active_mode if active_mode in ['live', 'simulink', '3d', 'gazebo'] else "fallback",
        "cellId": "cell_001",
        "packId": "pack_001",

        # Electrical data (simulated)
        "electrical_voltage": base_v,
        "electrical_current": base_i,
        "electrical_power": base_v * base_i,
        "electrical_resistance": 0.05 + random.uniform(-0.005, 0.005),
        "electrical_uncertainty": 0.01,

        # Ultrasonic data (in microseconds)
        "ultrasonic_timeOfFlight": 8.0 + random.uniform(-0.3, 0.3),
        "ultrasonic_amplitude": 1.0 + random.uniform(-0.1, 0.1),
        "ultrasonic_phaseShift": 0.0 + random.uniform(-0.05, 0.05),
        "ultrasonic_speedOfSound": 2500.0 + random.uniform(-50, 50),
        "ultrasonic_uncertainty": 0.1,

        # Thermal data
        "thermal_temperature": 26.5 + random.uniform(-2, 4),
        "thermal_tempGradient": 0.08 + random.uniform(-0.02, 0.02),
        "thermal_heatFlux": 10.0 + random.uniform(-2, 2),
        "thermal_uncertainty": 0.5,

        # State of Health (initial estimate)
        "stateOfHealth_value": 88.0 + random.uniform(-2, 2),
        "stateOfHealth_confidenceInterval_lower": 85.0,
        "stateOfHealth_confidenceInterval_upper": 91.0,
        "stateOfHealth_method": "fusion",

        # Degradation classification
        "degradation_mode": "healthy",
        "degradation_probability": 0.94,
        "degradation_perClass_healthy": 0.94,
        "degradation_perClass_li_plating": 0.02,
        "degradation_perClass_active_material_loss": 0.01,
        "degradation_perClass_electrolyte_decomposition": 0.01,
        "degradation_perClass_gas_generation": 0.01,
        "degradation_perClass_internal_short": 0.01,
        "degradation_entropy": 0.08,

        # Rebalancing state
        "rebalancing_state": "IDLE",
        "rebalancing_selectedAction": "none",
        "rebalancing_actionReason": "Cell operating within nominal limits",
        "rebalancing_powerStage_targetCurrent": 0.0,
        "rebalancing_powerStage_actualCurrent": 0.0,
        "rebalancing_powerStage_targetVoltage": 0.0,
        "rebalancing_powerStage_actualVoltage": 0.0,
        "rebalancing_powerStage_pwmDutyCycle": 0.0,
        "rebalancing_executionTime": 0.0,

        # Simulation fields
        "simulation_soc": 0.65 + random.uniform(-0.05, 0.05),
        "simulation_excitationAmplitude": 0.5,
        "simulation_noiseLevel": 0.05,
        "simulation_stepCount": 0
    }
    return frame


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)