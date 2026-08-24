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

                    # Look for complete JSON objects (simplistic)
                    while buffer.startswith('{') and '}' in buffer:
                        end = buffer.index('}') + 1
                        json_str = buffer[:end]
                        buffer = buffer[end:]
                        try:
                            packet = json.loads(json_str)
                            packets_processed += 1
                            if self.callback:
                                self.callback(packet)
                            # Log every 100 packets to avoid spam
                            if packets_processed % 100 == 0:
                                self.logger.debug(f"Processed {packets_processed} packets, {bytes_read} bytes read")
                        except json.JSONDecodeError as e:
                            self.logger.debug(f"Invalid JSON received: {json_str[:50]}... Error: {e}")
                            pass  # Invalid JSON, ignore
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