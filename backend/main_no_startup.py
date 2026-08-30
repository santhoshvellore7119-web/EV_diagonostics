"""
Main FastAPI application for the Unified Diagnostic Dashboard.
Provides REST API endpoints and WebSocket streaming for DiagnosticFrame data.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np

# For now, we'll use a simple in-memory buffer. Later we'll replace with a proper buffer.
class FrameBuffer:
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.buffer: List[Dict] = []

    def add(self, frame: Dict):
        """Add a frame to the buffer, maintaining max size."""
        self.buffer.append(frame)
        if len(self.buffer) > self.max_size:
            self.buffer.pop(0)

    def get_latest(self) -> Optional[Dict]:
        """Get the most recent frame."""
        return self.buffer[-1] if self.buffer else None

    def get_historical(self, start: int = 0, end: Optional[int] = None) -> List[Dict]:
        """Get historical frames by index."""
        if end is None:
            end = len(self.buffer)
        return self.buffer[start:end]

# Global instances
frame_buffer = FrameBuffer(max_size=10000)
connected_websockets: List[WebSocket] = []

app = FastAPI(title="Unified Diagnostic Dashboard API", version="0.1.0")

# CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class DiagnosticFrameBase(BaseModel):
    timestamp: float
    frameId: str
    source: str  # 'live', 'simulink', '3d'
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
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected WebSocket clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                # Remove broken connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

# API Endpoints
@app.get("/")
async def root():
    return {"message": "Unified Diagnostic Dashboard API"}

@app.get("/api/frames/latest")
async def get_latest_frame():
    """Get the most recent DiagnosticFrame."""
    latest = frame_buffer.get_latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No frames available")
    return latest

@app.get("/api/frames/historical")
async def get_historical_frames(start: int = 0, end: Optional[int] = None):
    """Get historical frames by index range."""
    frames = frame_buffer.get_historical(start, end)
    return {"frames": frames, "count": len(frames)}

@app.post("/api/mode/set")
async def set_mode(mode: str):
    """Set the active data source mode (live, simulink, 3d)."""
    # In a full implementation, this would switch the active ingestion pipeline
    # For now, we just acknowledge
    if mode not in ['live', 'simulink', '3d']:
        raise HTTPException(status_code=400, detail="Invalid mode")
    return {"message": f"Mode set to {mode}", "mode": mode}

# WebSocket endpoint for real-time frame streaming
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and send periodic updates
            # In a real implementation, we would send new frames as they arrive
            # For now, we'll send the latest frame every second
            await asyncio.sleep(1)
            latest = frame_buffer.get_latest()
            if latest:
                await websocket.send_json(latest)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Helper function to simulate incoming data for testing
async def simulate_data():
    """Simulate incoming DiagnosticFrame data for testing purposes."""
    import random
    import time

    frame_id = 0
    while True:
        # Create a simulated frame
        frame = {
            "timestamp": time.time(),
            "frameId": str(uuid.uuid4()),
            "source": "3d",  # Start with 3D simulation
            "cellId": "cell_001",
            "packId": "pack_001",

            # Electrical data (simulated)
            "electrical_voltage": 3.5 + random.uniform(-0.2, 0.2),
            "electrical_current": 2.0 + random.uniform(-0.5, 0.5),
            "electrical_power": 0.0,  # Will be calculated
            "electrical_resistance": 0.05 + random.uniform(-0.01, 0.01),
            "electrical_uncertainty": 0.01,

            # Ultrasonic data (simulated)
            "ultrasonic_timeOfFlight": 8.0 + random.uniform(-0.5, 0.5),  # microseconds
            "ultrasonic_amplitude": 1.0 + random.uniform(-0.2, 0.2),
            "ultrasonic_phaseShift": 0.0 + random.uniform(-0.1, 0.1),
            "ultrasonic_speedOfSound": 2500.0 + random.uniform(-100, 100),
            "ultrasonic_uncertainty": 0.1,

            # Thermal data (simulated)
            "thermal_temperature": 25.0 + random.uniform(-5, 10),
            "thermal_tempGradient": 0.1 + random.uniform(-0.05, 0.05),
            "thermal_heatFlux": 10.0 + random.uniform(-5, 5),
            "thermal_uncertainty": 0.5,

            # State of Health (simulated)
            "stateOfHealth_value": 85.0 + random.uniform(-10, 10),
            "stateOfHealth_confidenceInterval_lower": 80.0,
            "stateOfHealth_confidenceInterval_upper": 90.0,
            "stateOfHealth_method": "fusion",

            # Degradation classification (simulated)
            "degradation_mode": "healthy",
            "degradation_probability": 0.95,
            "degradation_perClass_healthy": 0.95,
            "degradation_perClass_li_plating": 0.01,
            "degradation_perClass_active_material_loss": 0.01,
            "degradation_perClass_electrolyte_decomposition": 0.01,
            "degradation_perClass_gas_generation": 0.01,
            "degradation_perClass_internal_short": 0.01,
            "degradation_entropy": 0.1,

            # Rebalancing state (simulated)
            "rebalancing_state": "idle",
            "rebalancing_selectedAction": "none",
            "rebalancing_actionReason": "No action required",
            "rebalancing_powerStage_targetCurrent": 0.0,
            "rebalancing_powerStage_actualCurrent": 0.0,
            "rebalancing_powerStage_targetVoltage": 0.0,
            "rebalancing_powerStage_actualVoltage": 0.0,
            "rebalancing_powerStage_pwmDutyCycle": 0.0,
            "rebalancing_executionTime": 0.0,

            # Simulation fields
            "simulation_soc": 0.5 + random.uniform(-0.1, 0.1),
            "simulation_excitationAmplitude": 0.5,
            "simulation_noiseLevel": 0.1,
            "simulation_stepCount": frame_id
        }

        # Calculate power
        frame["electrical_power"] = frame["electrical_voltage"] * frame["electrical_current"]

        # Add to buffer and broadcast
        frame_buffer.add(frame)
        await manager.broadcast(frame)

        frame_id += 1
        await asyncio.sleep(0.1)  # 10 Hz update rate

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)