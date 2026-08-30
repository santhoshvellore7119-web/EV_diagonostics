"""
Firmware ingestion module for live data from ESP32 via host application.

This module connects to the host application's data manager (via serial or socket)
and converts incoming data packets to DiagnosticFrame objects.
"""

import asyncio
import json
import uuid
import random
from datetime import datetime
from typing import Optional, Dict, Any
try:
    import serial  # pySerial for serial communication
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    serial = None
    SERIAL_AVAILABLE = False

# For now, we'll simulate if serial is not available or not configured.
# In a real implementation, we would read from the host application's data manager
# which could be via a TCP socket or a file.

class FirmwareIngestor:
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.is_connected = False
        self.frame_id_counter = 0

    async def connect(self):
        """Connect to the serial port."""
        if not SERIAL_AVAILABLE:
            print("pySerial not installed. Using simulated firmware data.")
            self.is_connected = False
            return

        if self.port is None:
            # Auto-detect ESP32 port
            ports = serial.tools.list_ports.comports()
            for p in ports:
                if 'ESP32' in p.description or 'USB Serial' in p.description:
                    self.port = p.device
                    break

        if self.port:
            try:
                self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
                self.is_connected = True
                print(f"Connected to firmware on {self.port}")
            except Exception as e:
                print(f"Failed to connect to serial port {self.port}: {e}")
                self.is_connected = False
        else:
            print("No serial port specified and none auto-detected. Using simulation.")
            self.is_connected = False

    async def disconnect(self):
        """Disconnect from the serial port."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.is_connected = False

    async def read_frame(self) -> Optional[Dict[str, Any]]:
        """
        Read a frame from the firmware (or simulate).
        Returns a DiagnosticFrame-compatible dictionary or None if no data.
        """
        if not self.is_connected:
            # Simulate data for testing
            return self._simulate_frame()

        if self.serial_conn and self.serial_conn.in_waiting > 0:
            try:
                line = self.serial_conn.readline().decode('utf-8').strip()
                if line:
                    # Assuming the host application sends JSON lines via serial
                    data = json.loads(line)
                    return self._convert_to_diagnostic_frame(data)
            except Exception as e:
                print(f"Error reading from serial: {e}")
                return None
        return None

    def _convert_to_diagnostic_frame(self, raw_data: Dict) -> Dict[str, Any]:
        """
        Convert raw firmware/host data to DiagnosticFrame format.
        This mapping depends on the actual data format from the host application.
        """
        # Example mapping - adjust based on actual data
        frame = {
            "timestamp": raw_data.get("timestamp", datetime.now().timestamp()),
            "frameId": str(uuid.uuid4()),
            "source": "live",
            "cellId": raw_data.get("cellId", "cell_001"),
            "packId": raw_data.get("packId", "pack_001"),

            # Electrical data
            "electrical_voltage": raw_data.get("bus_voltage_v", 0.0),
            "electrical_current": raw_data.get("current_a", 0.0),
            "electrical_power": raw_data.get("power_w", 0.0),
            "electrical_resistance": raw_data.get("resistance", 0.05),
            "electrical_uncertainty": raw_data.get("voltage_uncertainty", 0.01),

            # Ultrasonic data
            "ultrasonic_timeOfFlight": raw_data.get("time_of_flight_us", 8.0),  # microseconds
            "ultrasonic_amplitude": raw_data.get("amplitude", 1.0),
            "ultrasonic_phaseShift": raw_data.get("phase_shift", 0.0),
            "ultrasonic_speedOfSound": raw_data.get("speed_of_sound", 2500.0),
            "ultrasonic_uncertainty": raw_data.get("tof_uncertainty", 0.1),

            # Thermal data
            "thermal_temperature": raw_data.get("temperature_c", 25.0),
            "thermal_tempGradient": raw_data.get("temp_gradient_c_per_s", 0.1),
            "thermal_heatFlux": raw_data.get("heat_flux", 10.0),
            "thermal_uncertainty": raw_data.get("temp_uncertainty", 0.5),

            # State of Health (to be filled by ML pipeline later)
            "stateOfHealth_value": 0.0,
            "stateOfHealth_confidenceInterval_lower": 0.0,
            "stateOfHealth_confidenceInterval_upper": 0.0,
            "stateOfHealth_method": "pending",

            # Degradation classification (to be filled by ML pipeline later)
            "degradation_mode": "unknown",
            "degradation_probability": 0.0,
            "degradation_perClass_healthy": 0.0,
            "degradation_perClass_li_plating": 0.0,
            "degradation_perClass_active_material_loss": 0.0,
            "degradation_perClass_electrolyte_decomposition": 0.0,
            "degradation_perClass_gas_generation": 0.0,
            "degradation_perClass_internal_short": 0.0,
            "degradation_entropy": 0.0,

            # Rebalancing state (to be filled by rebalancing engine later)
            "rebalancing_state": "idle",
            "rebalancing_selectedAction": "none",
            "rebalancing_actionReason": "Pending ML results",
            "rebalancing_powerStage_targetCurrent": 0.0,
            "rebalancing_powerStage_actualCurrent": 0.0,
            "rebalancing_powerStage_targetVoltage": 0.0,
            "rebalancing_powerStage_actualVoltage": 0.0,
            "rebalancing_powerStage_pwmDutyCycle": 0.0,
            "rebalancing_executionTime": 0.0,

            # Simulation fields (not applicable for live)
            "simulation_soc": None,
            "simulation_excitationAmplitude": None,
            "simulation_noiseLevel": None,
            "simulation_stepCount": None
        }

        # Calculate power if not provided
        if frame["electrical_power"] == 0.0:
            frame["electrical_power"] = frame["electrical_voltage"] * frame["electrical_current"]

        return frame

    def _simulate_frame(self) -> Dict[str, Any]:
        """Simulate a frame for testing when no firmware is connected."""
        self.frame_id_counter += 1
        # Simulate realistic values
        base_voltage = 3.5 + random.uniform(-0.2, 0.2)
        base_current = 2.0 + random.uniform(-0.5, 0.5)
        base_power = base_voltage * base_current
        base_resistance = 0.05 + random.uniform(-0.01, 0.01)

        return {
            "timestamp": datetime.now().timestamp(),
            "frameId": str(uuid.uuid4()),
            "source": "live",
            "cellId": "cell_001",
            "packId": "pack_001",

            # Electrical data
            "electrical_voltage": base_voltage + random.uniform(-0.02, 0.02),
            "electrical_current": base_current + random.uniform(-0.02, 0.02),
            "electrical_power": base_power + random.uniform(-0.1, 0.1),
            "electrical_resistance": base_resistance,
            "electrical_uncertainty": 0.01,

            # Ultrasonic data
            "ultrasonic_timeOfFlight": 8.0 + random.uniform(-0.5, 0.5),
            "ultrasonic_amplitude": 1.0 + random.uniform(-0.2, 0.2),
            "ultrasonic_phaseShift": 0.0 + random.uniform(-0.1, 0.1),
            "ultrasonic_speedOfSound": 2500.0 + random.uniform(-100, 100),
            "ultrasonic_uncertainty": 0.1,

            # Thermal data
            "thermal_temperature": 25.0 + random.uniform(-5, 10),
            "thermal_tempGradient": 0.1 + random.uniform(-0.05, 0.05),
            "thermal_heatFlux": 10.0 + random.uniform(-5, 5),
            "thermal_uncertainty": 0.5,

            # State of Health (placeholder - will be updated by ML)
            "stateOfHealth_value": 85.0 + random.uniform(-10, 10),
            "stateOfHealth_confidenceInterval_lower": 80.0,
            "stateOfHealth_confidenceInterval_upper": 90.0,
            "stateOfHealth_method": "fusion",

            # Degradation classification (placeholder)
            "degradation_mode": "healthy",
            "degradation_probability": 0.95,
            "degradation_perClass_healthy": 0.95,
            "degradation_perClass_li_plating": 0.01,
            "degradation_perClass_active_material_loss": 0.01,
            "degradation_perClass_electrolyte_decomposition": 0.01,
            "degradation_perClass_gas_generation": 0.01,
            "degradation_perClass_internal_short": 0.01,
            "degradation_entropy": 0.1,

            # Rebalancing state (placeholder)
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
            "simulation_soc": None,
            "simulation_excitationAmplitude": None,
            "simulation_noiseLevel": None,
            "simulation_stepCount": None
        }


# For testing standalone
async def test_ingestor():
    ingestor = FirmwareIngestor()
    await ingestor.connect()
    try:
        while True:
            frame = await ingestor.read_frame()
            if frame:
                print(f"Received frame: {frame['frameId'][:8]}...")
                # In a real system, we would send this to the backend stream
                # For now, just print a summary
                print(f"  Voltage: {frame['electrical_voltage']:.2f}V")
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        await ingestor.disconnect()


if __name__ == "__main__":
    asyncio.run(test_ingestor())