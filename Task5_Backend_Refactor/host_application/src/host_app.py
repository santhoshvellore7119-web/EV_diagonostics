"""
Host Application for EV Battery Diagnostic System
Provides interactive GUI for visualizing sensor data, ML predictions,
and controlling recovery actions.

Refactored to use modular components:
- logger.py: Centralized logging
- serial_handler.py: Serial communication
- data_manager.py: Data buffering and replay
- plot_manager.py: Plot management
- ml_handler.py: ML result processing
"""

import sys
import time
import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg

# Import our modular components
from .logger import get_logger
from .serial_handler import SerialReader
from .data_manager import DataManager
from .plot_manager import PlotManager
from .ml_handler import MLHandler


class HostApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        self.logger.info("Initializing Host Application")

        # Initialize managers
        self.logger.debug("Initializing managers")
        self.data_manager = DataManager(max_buffer_size=1000, record_dir='recordings')
        self.plot_manager = PlotManager()
        self.ml_handler = MLHandler()

        # State variables
        self.sensing_active = False
        self.recovery_active = False
        self.last_ui_update = time.time()
        self.ui_update_interval = 0.1  # Update UI max 10 times per second

        # Serial reader
        self.serial_reader = None

        # Setup UI and connections
        self.init_ui()
        self.init_plots()
        self.init_connections()

        self.logger.info("Host Application initialized successfully")

    def init_ui(self):
        """Initialize the user interface."""
        self.logger.debug("Initializing UI")
        self.setWindowTitle("EV Battery Diagnostic & Recovery System")
        self.setGeometry(100, 100, 1200, 800)

        # Central widget
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QHBoxLayout(central_widget)

        # Left panel: controls and status
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setFixedWidth(300)

        # Status group
        status_group = QtWidgets.QGroupBox("System Status")
        status_layout = QtWidgets.QFormLayout()
        self.state_label = QtWidgets.QLabel("Idle")
        self.mode_label = QtWidgets.QLabel("Unknown")
        self.soh_label = QtWidgets.QLabel("0%")
        self.deg_label = QtWidgets.QLabel("Unknown")
        self.conf_label = QtWidgets.QLabel("Low")
        status_layout.addRow("State:", self.state_label)
        status_layout.addRow("Degradation Mode:", self.deg_label)
        status_layout.addRow("Probability:", self.mode_label)
        status_layout.addRow("Confidence:", self.conf_label)
        status_layout.addRow("SOH Estimate:", self.soh_label)
        status_group.setLayout(status_layout)
        left_panel.addWidget(status_group)

        # Control group
        control_group = QtWidgets.QGroupBox("Controls")
        control_layout = QtWidgets.QVBoxLayout()
        self.start_btn = QtWidgets.QPushButton("Start Sensing")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.recovery_btn = QtWidgets.QPushButton("Start Recovery")
        self.recovery_btn.setEnabled(False)
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.recovery_btn)
        control_group.setLayout(control_layout)
        left_panel.addWidget(control_group)

        # Recording controls
        record_group = QtWidgets.QGroupBox("Recording")
        record_layout = QtWidgets.VBoxLayout()
        self.record_btn = QtWidgets.QPushButton("Start Recording")
        self.record_btn.setCheckable(True)
        self.playback_btn = QtWidgets.QPushButton("Playback")
        self.playback_btn.setEnabled(False)
        record_layout.addWidget(self.record_btn)
        record_layout.addWidget(self.playback_btn)
        record_group.setLayout(record_layout)
        left_panel.addWidget(record_group)

        # Serial settings
        serial_group = QtWidgets.QGroupBox("Serial Communication")
        serial_layout = QtWidgets.QFormLayout()
        self.port_input = QtWidgets.QLineEdit("COM3")
        self.baud_input = QtWidgets.QLineEdit("115200")
        self.connect_btn = QtWidgets.QPushButton("Connect")
        serial_layout.addRow("Port:", self.port_input)
        serial_layout.addRow("Baudrate:", self.baud_input)
        serial_layout.addRow(self.connect_btn)
        serial_group.setLayout(serial_layout)
        left_panel.addWidget(serial_group)

        left_panel.addStretch()
        layout.addLayout(left_panel)

        # Right panel: plots
        right_panel = QtWidgets.QVBoxLayout()
        self.plot_tabs = QtWidgets.QTabWidget()
        self.electrical_plot = pg.PlotWidget(title="Electrical Signal (Voltage)")
        self.ultrasonic_plot = pg.PlotWidget(title="Ultrasonic Signal (Time-of-Flight)")
        self.thermal_plot = pg.PlotWidget(title="Thermal Signal (Temperature)")

        self.plot_tabs.addTab(self.electrical_plot, "Electrical")
        self.plot_tabs.addTab(self.ultrasonic_plot, "Ultrasonic")
        self.plot_tabs.addTab(self.thermal_plot, "Thermal")
        right_panel.addWidget(self.plot_tabs)
        layout.addLayout(right_panel)

        self.logger.debug("UI initialization complete")

    def init_plots(self):
        """Initialize plot configurations."""
        self.logger.debug("Initializing plots")
        self.plot_manager.setup_plots(
            self.electrical_plot,
            self.ultrasonic_plot,
            self.thermal_plot
        )
        self.logger.debug("Plot initialization complete")

    def init_connections(self):
        """Initialize signal-slot connections."""
        self.logger.debug("Initializing connections")
        self.start_btn.clicked.connect(self.start_sensing)
        self.stop_btn.clicked.connect(self.stop_sensing)
        self.recovery_btn.clicked.connect(self.toggle_recovery)
        self.connect_btn.clicked.connect(self.toggle_serial)
        self.record_btn.toggled.connect(self.toggle_recording)
        self.playback_btn.clicked.connect(self.toggle_playback)
        self.logger.debug("Connections initialized")

    def toggle_serial(self):
        """Toggle serial connection."""
        if self.serial_reader and self.serial_reader.isRunning():
            self.logger.info("Disconnecting from serial port")
            self.serial_reader.stop()
            self.serial_reader.wait()
            self.connect_btn.setText("Connect")
            self.state_label.setText("Disconnected")
            self.serial_reader = None
        else:
            port = self.port_input.text()
            try:
                baud = int(self.baud_input.text())
                self.logger.info(f"Connecting to {port} at {baud} baud")
                self.serial_reader = SerialReader(
                    port=port,
                    baudrate=baud,
                    callback=self.handle_serial_data
                )
                self.serial_reader.start()
                self.connect_btn.setText("Disconnect")
                self.state_label.setText("Connected")
            except ValueError:
                self.logger.error(f"Invalid baud rate: {self.baud_input.text()}")
                QtWidgets.QMessageBox.warning(self, "Error", "Please enter a valid baud rate")
            except Exception as e:
                self.logger.error(f"Failed to connect to serial port: {e}")
                QtWidgets.QMessageBox.critical(self, "Connection Error", f"Failed to connect: {e}")

    def start_sensing(self):
        """Start sensing process."""
        if not self.serial_reader or not self.serial_reader.isRunning():
            self.logger.warning("Attempted to start sensing without serial connection")
            QtWidgets.QMessageBox.warning(self, "Warning", "Please connect to serial port first.")
            return

        self.logger.info("Starting sensing")
        self.sensing_active = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.recovery_btn.setEnabled(True)
        self.state_label.setText("Sensing Active")

        # Clear previous data when starting new sensing session
        self.data_manager.clear_buffers()
        self.ml_handler.reset()
        self.update_status_display()

    def stop_sensing(self):
        """Stop sensing process."""
        self.logger.info("Stopping sensing")
        self.sensing_active = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.recovery_btn.setEnabled(False)
        self.state_label.setText("Sensing Stopped")
        self.update_status_display()

    def toggle_recovery(self):
        """Toggle recovery process."""
        if not self.recovery_active:
            self.logger.info("Starting recovery")
            self.recovery_active = True
            self.recovery_btn.setText("Stop Recovery")
            self.state_label.setText("Recovery Active")
            # Send recovery start command to MCU (would be implemented in serial_handler)
        else:
            self.logger.info("Stopping recovery")
            self.recovery_active = False
            self.recovery_btn.setText("Start Recovery")
            self.state_label.setText("Recovery Stopped")
            # Send recovery stop command
        self.update_status_display()

    def toggle_recording(self, checked):
        """Toggle recording on/off."""
        if checked:
            self.logger.info("Starting recording")
            filepath = self.data_manager.start_recording()
            if filepath:
                self.record_btn.setText("Stop Recording")
                self.playback_btn.setEnabled(False)  # Disable playback during recording
                self.state_label.setText(f"Recording: {filepath.split('/')[-1]}")
            else:
                self.record_btn.setChecked(False)
                self.logger.error("Failed to start recording")
        else:
            self.logger.info("Stopping recording")
            filepath = self.data_manager.stop_recording()
            if filepath:
                self.record_btn.setText("Start Recording")
                self.playback_btn.setEnabled(True)  # Re-enable playback
                self.state_label.setText("Recording Stopped")
                # Show recording info in status bar or popup
                info = self.data_manager.get_recording_info(filepath)
                if info:
                    self.logger.info(f"Recording saved: {info['sample_count']} samples, {info['size_bytes']} bytes")
            else:
                self.logger.error("Failed to stop recording properly")

    def toggle_playback(self):
        """Toggle playback mode."""
        if self.data_manager.is_playing:
            self.logger.info("Stopping playback")
            if self.data_manager.stop_playback():
                self.playback_btn.setText("Playback")
                self.state_label.setText("Playback Stopped")
        else:
            # Show file dialog to select recording
            from PyQt5.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Select Recording File",
                self.data_manager.record_dir,
                "JSONL Files (*.jsonl)"
            )
            if filename:
                self.logger.info(f"Loading recording: {filename}")
                if self.data_manager.load_recording(filename):
                    if self.data_manager.start_playback():
                        self.playback_btn.setText("Stop Playback")
                        self.state_label.setText("Playback Active")
                    else:
                        self.logger.error("Failed to start playback")
                else:
                    self.logger.error("Failed to load recording")
            else:
                self.logger.info("Playback cancelled by user")

    def update_status_display(self):
        """Update the status display with current ML results."""
        ml_results = self.ml_handler.get_ml_results()
        display_text = self.ml_handler.get_display_text()

        # Update labels
        self.deg_label.setText(display_text['mode_text'])
        self.mode_label.setText(display_text['probability_text'])
        self.soh_label.setText(display_text['soh_text'])
        self.conf_label.setText(display_text['confidence_text'])

        # Update colors based on status
        colors = self.ml_handler.get_status_color()
        # This would require implementing color setting in Qt labels
        # For now, we'll log the colors
        self.logger.debug(f"Status colors - Mode: {colors['mode_color']}, "
                         f"Prob: {colors['probability_color']}, SOH: {colors['soh_color']}")

    def handle_serial_data(self, packet):
        """
        Callback for incoming serial data.
        Processes packets and updates data buffers and ML results.
        """
        try:
            # Extract timestamp (use packet timestamp if available, otherwise current time)
            timestamp = packet.get('timestamp_us', time.time() * 1e6) / 1e6  # Convert to seconds if needed
            if isinstance(timestamp, (int, float)) and timestamp > 1e9:  # Likely microseconds
                timestamp = timestamp / 1e6

            # Extract sensor data
            electrical_packet = packet.get('electrical', {})
            ultrasonic_packet = packet.get('ultrasonic', {})
            thermal_packet = packet.get('thermal', {})

            # Process electrical data (use bus voltage for plotting)
            electrical_value = electrical_packet.get('bus_voltage_v', 0.0)

            # Process ultrasonic data (use time-of-flight for plotting)
            ultrasonic_value = ultrasonic_packet.get('time_of_fight_us', 0.0)

            # Process thermal data (use temperature for plotting)
            thermal_value = thermal_packet.get('temperature_c', 0.0)

            # Add sample to data manager
            self.data_manager.add_sample(timestamp, electrical_value, ultrasonic_value, thermal_value)

            # Update ML results if present in packet
            if 'degradation_mode' in packet or 'degradation_prob' in packet:
                mode_name = packet.get('degradation_mode')
                mode_index = packet.get('degradation_mode_index')
                probability = packet.get('degradation_prob', 0.0)
                soh = packet.get('soh', 0.0)

                self.ml_handler.update_ml_results(
                    mode_index=mode_index,
                    mode_name=mode_name,
                    probability=probability,
                    soh=soh
                )
                # Update UI display periodically to avoid excessive updates
                current_time = time.time()
                if current_time - self.last_ui_update > self.ui_update_interval:
                    self.update_status_display()
                    self.last_ui_update = current_time

            # Update plots periodically (limit to reduce CPU usage)
            current_time = time.time()
            if current_time - self.last_ui_update > self.ui_update_interval:
                time_data, electrical_data, ultrasonic_data, thermal_data = self.data_manager.get_buffers()
                self.plot_manager.update_plots(time_data, electrical_data, ultrasonic_data, thermal_data)
                self.last_ui_update = current_time

        except Exception as e:
            self.logger.error(f"Error processing serial data: {e}", exc_info=True)

    def closeEvent(self, event):
        """Handle application close event."""
        self.logger.info("Application closing")

        # Stop any active processes
        if self.sensing_active:
            self.stop_sensing()
        if self.recovery_active:
            self.toggle_recovery()
        if self.data_manager.is_recording:
            self.data_manager.stop_recording()
        if self.data_manager.is_playing:
            self.data_manager.stop_playback()

        # Stop serial reader
        if self.serial_reader and self.serial_reader.isRunning():
            self.logger.info("Stopping serial reader")
            self.serial_reader.stop()
            self.serial_reader.wait()

        self.logger.info("Application shutting down")
        event.accept()