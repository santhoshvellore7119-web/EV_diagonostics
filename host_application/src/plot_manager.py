"""
Plot management module for the EV Battery Diagnostic System host application.
Handles plot initialization, updating, and visualization.
"""

import pyqtgraph as pg
from PyQt5 import QtGui
from .logger import get_logger
import numpy as np


class PlotManager:
    """
    Manages plots for the host application visualization.
    """

    def __init__(self):
        """Initialize the plot manager."""
        self.logger = get_logger(__name__)
        self.logger.debug("PlotManager initialized")

        # Plot widgets and curves
        self.electrical_plot = None
        self.ultrasonic_plot = None
        self.thermal_plot = None

        self.electrical_curve = None
        self.ultrasonic_curve = None
        self.thermal_curve = None

        # Plot configurations
        self.plot_colors = {
            'electrical': ('y', '#FFFF00'),  # Yellow
            'ultrasonic': ('c', '#00FFFF'),  # Cyan
            'thermal': ('m', '#FF00FF')      # Magenta
        }

    def setup_plots(self, electrical_plot, ultrasonic_plot, thermal_plot):
        """
        Setup plot widgets and initialize curves.

        Args:
            electrical_plot: PyQtGraph plot widget for electrical data
            ultrasonic_plot: PyQtGraph plot widget for ultrasonic data
            thermal_plot: PyQtGraph plot widget for thermal data
        """
        self.electrical_plot = electrical_plot
        self.ultrasonic_plot = ultrasonic_plot
        self.thermal_plot = thermal_plot

        # Initialize curves with pens
        self.electrical_curve = self.electrical_plot.plot(
            pen=pg.mkPen(color=self.plot_colors['electrical'][1], width=2)
        )
        self.ultrasonic_curve = self.ultrasonic_plot.plot(
            pen=pg.mkPen(color=self.plot_colors['ultrasonic'][1], width=2)
        )
        self.thermal_curve = self.thermal_plot.plot(
            pen=pg.mkPen(color=self.plot_colors['thermal'][1], width=2)
        )

        self._configure_plot_axes()
        self.logger.info("Plots initialized successfully")

    def _configure_plot_axes(self):
        """Configure axes labels and appearance for all plots."""
        plots_config = [
            (self.electrical_plot, 'Electrical Signal', 'Voltage (V)', 'Time (s)'),
            (self.ultrasonic_plot, 'Ultrasonic Signal', 'Time-of-Flight (µs)', 'Time (s)'),
            (self.thermal_plot, 'Thermal Signal', 'Temperature (°C)', 'Time (s)')
        ]

        for plot, title, left_label, bottom_label in plots_config:
            if plot:
                plot.setTitle(title)
                plot.setLabel('left', left_label)
                plot.setLabel('bottom', bottom_label)
                plot.showGrid(x=True, y=True, alpha=0.3)
                plot.setBackground('#1e1e1e')  # Dark background for better visibility

    def update_plots(self, time_data, electrical_data, ultrasonic_data, thermal_data):
        """
        Update all plots with new data.

        Args:
            time_data (numpy array): Time values for x-axis
            electrical_data (numpy array): Electrical sensor values
            ultrasonic_data (numpy array): Ultrasonic sensor values
            thermal_data (numpy array): Thermal sensor values
        """
        try:
            if len(time_data) == 0:
                return

            # Update electrical plot
            if self.electrical_curve and len(electrical_data) == len(time_data):
                self.electrical_curve.setData(time_data, electrical_data)

            # Update ultrasonic plot
            if self.ultrasonic_curve and len(ultrasonic_data) == len(time_data):
                self.ultrasonic_curve.setData(time_data, ultrasonic_data)

            # Update thermal plot
            if self.thermal_curve and len(thermal_data) == len(time_data):
                self.thermal_curve.setData(time_data, thermal_data)

        except Exception as e:
            self.logger.error(f"Error updating plots: {e}")

    def clear_plots(self):
        """Clear all plot data."""
        try:
            if self.electrical_curve:
                self.electrical_curve.setData([], [])
            if self.ultrasonic_curve:
                self.ultrasonic_curve.setData([], [])
            if self.thermal_curve:
                self.thermal_curve.setData([], [])
            self.logger.debug("Plots cleared")
        except Exception as e:
            self.logger.error(f"Error clearing plots: {e}")

    def set_plot_ranges(self, x_range=None, y_ranges=None):
        """
        Set fixed ranges for plot axes.

        Args:
            x_range (tuple, optional): (min, max) for x-axis
            y_ranges (dict, optional): {'electrical': (min, max), 'ultrasonic': (min, max), 'thermal': (min, max)}
        """
        try:
            if x_range and self.electrical_plot:
                self.electrical_plot.setXRange(*x_range)
                self.ultrasonic_plot.setXRange(*x_range)
                self.thermal_plot.setXRange(*x_range)

            if y_ranges:
                if 'electrical' in y_ranges and self.electrical_plot:
                    self.electrical_plot.setYRange(*y_ranges['electrical'])
                if 'ultrasonic' in y_ranges and self.ultrasonic_plot:
                    self.ultrasonic_plot.setYRange(*y_ranges['ultrasonic'])
                if 'thermal' in y_ranges and self.thermal_plot:
                    self.thermal_plot.setYRange(*y_ranges['thermal'])
        except Exception as e:
            self.logger.error(f"Error setting plot ranges: {e}")

    def enable_auto_range(self, enable=True):
        """
        Enable or disable auto-ranging for plots.

        Args:
            enable (bool): True to enable auto-ranging, False to disable
        """
        try:
            if self.electrical_plot:
                self.electrical_plot.enableAutoRange('xy', enable)
            if self.ultrasonic_plot:
                self.ultrasonic_plot.enableAutoRange('xy', enable)
            if self.thermal_plot:
                self.thermal_plot.enableAutoRange('xy', enable)
        except Exception as e:
            self.logger.error(f"Error setting auto range: {e}")

    def add_legend(self, electrical_name="Electrical", ultrasonic_name="Ultrasonic", thermal_name="Thermal"):
        """
        Add legends to plots.

        Args:
            electrical_name (str): Label for electrical plot legend
            ultrasonic_name (str): Label for ultrasonic plot legend
            thermal_name (str): Label for thermal plot legend
        """
        try:
            # Note: PyQtGraph legend support is limited on PlotWidget
            # For more advanced legends, consider using GraphicsLayoutWidget
            pass
        except Exception as e:
            self.logger.error(f"Error adding legend: {e}")

    def export_plot_data(self, filepath):
        """
        Export current plot data to a CSV file.

        Args:
            filepath (str): Path to save the CSV file

        Returns:
            bool: True if exported successfully, False otherwise
        """
        try:
            import csv
            # This would require access to the current data buffers
            # For now, we'll log that this feature needs implementation
            self.logger.info(f"Plot data export to {filepath} requested (feature pending implementation)")
            return False
        except Exception as e:
            self.logger.error(f"Error exporting plot data: {e}")
            return False