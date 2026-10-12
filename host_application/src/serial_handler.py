"""
Serial communication handler for the EV Battery Diagnostic System.
Manages serial connection to MCU and parses incoming JSON packets.
"""

import serial
import threading
import json
import time
from .logger import get_logger


class SerialReader(threading.Thread):
    """
    Thread to read serial data from the MCU.
    Expects JSON packets as defined in the firmware.
    """

    def __init__(self, port='COM3', baudrate=115200, callback=None):
        super().__init__()
        self.logger = get_logger(__name__)
        self.port = port
        self.baudrate = baudrate
        self.callback = callback
        self.running = False
        self.serial_conn = None
        self.logger.debug(f"SerialReader initialized for port {port} at {baudrate} baud")

    def run(self):
        """Main thread loop for reading serial data."""
        self.logger.info(f"Attempting to connect to {self.port} at {self.baudrate} baud")
        self.running = True
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            self.logger.info(f"Connected to {self.port} at {self.baudrate} baud")
        except serial.SerialException as e:
            self.logger.error(f"Failed to open serial port {self.port}: {e}")
            self.running = False
            return

        buffer = ""
        bytes_read = 0
        packets_processed = 0

        while self.running:
            try:
                if self.serial_conn.in_waiting:
                    data = self.serial_conn.read(self.serial_conn.in_waiting).decode('utf-8', errors='ignore')
                    bytes_read += len(data)
                    buffer += data

                    # Extract complete balanced JSON objects (supporting nested braces)
                    while '{' in buffer:
                        start_idx = buffer.index('{')
                        if start_idx > 0:
                            buffer = buffer[start_idx:]
                        depth = 0
                        in_string = False
                        escape = False
                        end_idx = -1
                        for idx, ch in enumerate(buffer):
                            if escape:
                                escape = False
                                continue
                            if ch == '\\' and in_string:
                                escape = True
                                continue
                            if ch == '"':
                                in_string = not in_string
                                continue
                            if not in_string:
                                if ch == '{':
                                    depth += 1
                                elif ch == '}':
                                    depth -= 1
                                    if depth == 0:
                                        end_idx = idx + 1
                                        break
                        if end_idx == -1:
                            # Wait for more serial bytes to complete the JSON object
                            break
                        json_str = buffer[:end_idx]
                        buffer = buffer[end_idx:].lstrip()
                        try:
                            packet = json.loads(json_str)
                            packets_processed += 1
                            if self.callback:
                                self.callback(packet)
                            if packets_processed % 100 == 0:
                                self.logger.debug(f"Processed {packets_processed} packets, {bytes_read} bytes read")
                        except json.JSONDecodeError as e:
                            self.logger.debug(f"Invalid JSON received: {json_str[:50]}... Error: {e}")
                else:
                    time.sleep(0.001)  # Small delay to prevent CPU hogging
            except Exception as e:
                self.logger.error(f"Serial read error: {e}")
                break

        self.logger.info(f"Serial reader stopping. Total: {bytes_read} bytes read, {packets_processed} packets processed")
        if self.serial_conn:
            self.serial_conn.close()
            self.logger.debug("Serial connection closed")

    def stop(self):
        """Stop the serial reader thread."""
        self.logger.info("Stopping serial reader...")
        self.running = False

    def isRunning(self) -> bool:
        """Compatibility alias for Qt-style thread check."""
        return self.is_alive()

    def wait(self, timeout: float = 2.0):
        """Compatibility alias for Qt-style thread join."""
        if self.is_alive():
            self.join(timeout=timeout)

    def is_connected(self):
        """Check if serial connection is active."""
        return self.serial_conn is not None and self.serial_conn.is_open

    def send_data(self, data):
        """
        Send data to the MCU over serial connection.

        Args:
            data (str or dict): Data to send. If dict, will be JSON-encoded.

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.is_connected():
            self.logger.warning("Cannot send data: not connected to serial port")
            return False

        try:
            if isinstance(data, dict):
                msg = json.dumps(data) + '\n'
            else:
                msg = str(data)
                if not msg.endswith('\n'):
                    msg += '\n'

            self.serial_conn.write(msg.encode('utf-8'))
            self.logger.debug(f"Sent data: {msg.strip()}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send data: {e}")
            return False