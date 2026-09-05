"""
EV Battery Multi-Modal Diagnostic System - 3D Visualization Simulation

This script provides an interactive 3D visualization of the EV battery diagnostic system
showing:
- Battery cell with sensor placement (electrical, ultrasonic, thermal)
- Microcontroller Unit (MCU)
- Bidirectional DC-DC converter
- Real-time parameter display based on user inputs
- Scenario testing for different degradation modes

Dependencies: matplotlib, numpy
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.widgets as widgets
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
sim_core_path = os.path.join(project_root, 'ev_cell_multimodal_sim')
if sim_core_path not in sys.path:
    sys.path.insert(0, sim_core_path)

try:
    from core.physics_engine import DEGRADATION_PHYSICS_PARAMS, simulate_cell_from_parameters
except ImportError:
    from ev_cell_multimodal_sim.core.physics_engine import DEGRADATION_PHYSICS_PARAMS, simulate_cell_from_parameters


class EVBattery3DSimulator:
    def __init__(self, headless=False):
        # System parameters
        self.params = self._default_parameters()
        self.headless = headless

        # Current state
        self.soc = 0.5
        self.degradation_mode = 'healthy'
        self.noise_level = 0.1
        self.excitation_amplitude = 0.5

        # Simulation step counter for data sequencing
        self._step_count = 0

        # Initialize simulation GUI if not headless
        if not headless:
            self.fig = plt.figure(figsize=(14, 9))
            self.fig.suptitle('Low-Cost Multi-Modal Diagnostic and Active Cell-Rebalancing System',
                              fontsize=14, fontweight='bold')

            # Create 3D axis
            self.ax_3d = self.fig.add_subplot(121, projection='3d')

            # Create control panel
            self.create_controls()

            # Create status display
            self.create_status_display()

            # Initial render
            self.update_visualization()
        else:
            self.fig = None
            self.ax_3d = None

    def _default_parameters(self):
        """Default system parameters"""
        return {
            # Cell dimensions (meters)
            'cell_length': 0.065,   # 6.5 cm
            'cell_width': 0.02,     # 2 cm radius (cylinder approximation)
            'cell_height': 0.065,   # 6.5 cm

            # Sensor positions (relative to cell center)
            'electrical_pos': np.array([0, 0, 0.035]),      # Top center
            'ultrasonic_tx_pos': np.array([-0.01, 0, 0]),   # Left side
            'ultrasonic_rx_pos': np.array([0.01, 0, 0]),    # Right side
            'thermal_pos': np.array([0, 0, -0.035]),        # Bottom center

            # MCU and converter positions
            'mcu_pos': np.array([0.04, 0, 0.02]),           # Top-right front
            'converter_pos': np.array([-0.04, 0, -0.02]),   # Bottom-left back

            # Excitation pulse parameters
            'pulse_width_s': 10e-6,    # 10 microseconds
            'pulse_amplitude_a': 0.5,  # 500 mA
            'pulse_period_s': 0.1,     # 10 Hz

            # Degradation effects on sensor readings
            'degradation_effects': {
                'healthy': {'electrical': 1.0, 'ultrasonic': 1.0, 'thermal': 1.0},
                'li_plating': {'electrical': 1.02, 'ultrasonic': 0.99, 'thermal': 1.05},
                'active_material_loss': {'electrical': 1.05, 'ultrasonic': 0.97, 'thermal': 1.1},
                'electrolyte_decomposition': {'electrical': 1.03, 'ultrasonic': 0.98, 'thermal': 1.05},
                'gas_generation': {'electrical': 1.08, 'ultrasonic': 0.93, 'thermal': 1.2},
                'internal_short': {'electrical': 1.15, 'ultrasonic': 0.85, 'thermal': 1.8}
            }
        }

    def create_controls(self):
        """Create interactive controls for the simulation"""
        # Adjust subplot to make room for controls
        plt.subplots_adjust(left=0.25, bottom=0.25)

        # State of Charge slider
        ax_soc = plt.axes([0.25, 0.15, 0.4, 0.03])
        self.soc_slider = widgets.Slider(
            ax_soc, 'State of Charge', 0.0, 1.0, valinit=self.soc, valstep=0.01
        )
        self.soc_slider.on_changed(self.update_soc)

        # Degradation mode dropdown
        ax_deg = plt.axes([0.25, 0.10, 0.3, 0.03])
        self.deg_dropdown = widgets.RadioButtons(
            ax_deg,
            ['healthy', 'li_plating', 'active_material_loss',
             'electrolyte_decomposition', 'gas_generation', 'internal_short'],
            active=0
        )
        self.deg_dropdown.on_clicked(self.update_degradation_mode)

        # Noise level slider
        ax_noise = plt.axes([0.25, 0.05, 0.4, 0.03])
        self.noise_slider = widgets.Slider(
            ax_noise, 'Noise Level', 0.0, 1.0, valinit=self.noise_level, valstep=0.01
        )
        self.noise_slider.on_changed(self.update_noise)

        # Excitation amplitude slider
        ax_exc = plt.axes([0.25, 0.00, 0.4, 0.03])
        self.exc_slider = widgets.Slider(
            ax_exc, 'Excitation (A)', 0.1, 1.0, valinit=self.excitation_amplitude, valstep=0.01
        )
        self.exc_slider.on_changed(self.update_excitation)

        # Scenario buttons
        button_width = 0.12
        button_height = 0.04
        button_left = 0.02
        button_top = 0.7

        self.btn_healthy = widgets.Button(
            plt.axes([button_left, button_top, button_width, button_height]),
            'Healthy', color='lightgreen', hovercolor='green'
        )
        self.btn_li_plating = widgets.Button(
            plt.axes([button_left, button_top - 0.06, button_width, button_height]),
            'Li Plating', color='lightblue', hovercolor='blue'
        )
        self.btn_active_loss = widgets.Button(
            plt.axes([button_left, button_top - 0.12, button_width, button_height]),
            'Active Loss', color='lightcoral', hovercolor='red'
        )
        self.btn_electrolyte = widgets.Button(
            plt.axes([button_left, button_top - 0.18, button_width, button_height]),
            'Electrolyte', color='khaki', hovercolor='orange'
        )
        self.btn_gas = widgets.Button(
            plt.axes([button_left, button_top - 0.24, button_width, button_height]),
            'Gas Gen', color='plum', hovercolor='purple'
        )
        self.btn_internal_short = widgets.Button(
            plt.axes([button_left, button_top - 0.30, button_width, button_height]),
            'Internal Short', color='lavender', hovercolor='violet'
        )

        self.btn_healthy.on_clicked(self.scenario_healthy)
        self.btn_li_plating.on_clicked(self.scenario_li_plating)
        self.btn_active_loss.on_clicked(self.scenario_active_material_loss)
        self.btn_electrolyte.on_clicked(self.scenario_electrolyte_decomposition)
        self.btn_gas.on_clicked(self.scenario_gas_generation)
        self.btn_internal_short.on_clicked(self.scenario_internal_short)

    def create_status_display(self):
        """Create status display panel"""
        # Create text boxes for status information
        self.status_text = self.fig.text(0.02, 0.75, '', fontsize=9,
                                         verticalalignment='top',
                                         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        # Parameter display
        self.param_text = self.fig.text(0.02, 0.5, '', fontsize=9,
                                        verticalalignment='top',
                                        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

        # Update status initially
        self.update_status_display()

    def update_soc(self, val):
        """Update state of charge"""
        self.soc = val
        self.update_visualization()

    def update_degradation_mode(self, label):
        """Update degradation mode"""
        self.degradation_mode = label
        self.update_visualization()

    def update_noise(self, val):
        """Update noise level"""
        self.noise_level = val
        self.update_visualization()

    def update_excitation(self, val):
        """Update excitation amplitude"""
        self.excitation_amplitude = val
        self.params['pulse_amplitude_a'] = val
        self.update_visualization()

    def scenario_healthy(self, event):
        """Set scenario to healthy cell"""
        self.soc_slider.set_val(0.5)
        self.deg_dropdown.set_active(0)
        self.noise_slider.set_val(0.1)
        self.exc_slider.set_val(0.5)

    def scenario_li_plating(self, event):
        """Set scenario to lithium plating"""
        self.soc_slider.set_val(0.4)
        self.deg_dropdown.set_active(1)
        self.noise_slider.set_val(0.2)
        self.exc_slider.set_val(0.5)

    def scenario_active_material_loss(self, event):
        """Set scenario to active material loss"""
        self.soc_slider.set_val(0.6)
        self.deg_dropdown.set_active(2)
        self.noise_slider.set_val(0.2)
        self.exc_slider.set_val(0.4)

    def scenario_electrolyte_decomposition(self, event):
        """Set scenario to electrolyte decomposition"""
        self.soc_slider.set_val(0.5)
        self.deg_dropdown.set_active(3)
        self.noise_slider.set_val(0.15)
        self.exc_slider.set_val(0.45)

    def scenario_gas_generation(self, event):
        """Set scenario to gas generation"""
        self.soc_slider.set_val(0.7)
        self.deg_dropdown.set_active(4)
        self.noise_slider.set_val(0.25)
        self.exc_slider.set_val(0.3)

    def scenario_internal_short(self, event):
        """Set scenario to internal short"""
        self.soc_slider.set_val(0.2)
        self.deg_dropdown.set_active(5)
        self.noise_slider.set_val(0.4)
        self.exc_slider.set_val(0.6)

    def compute_sensor_readings(self):
        """Compute simulated sensor readings based on canonical ODE physics model"""
        phys = DEGRADATION_PHYSICS_PARAMS.get(
            self.degradation_mode, DEGRADATION_PHYSICS_PARAMS['healthy']
        )

        noise_factor = float(self.noise_level)

        # Sample physical parameter state around nominal regime
        r0 = float(phys['r0'] * (1.0 + np.random.normal(0, 0.02 * noise_factor)))
        r1 = float(phys['r1'] * (1.0 + np.random.normal(0, 0.02 * noise_factor)))
        c1 = float(phys['c1'] * (1.0 + np.random.normal(0, 0.02 * noise_factor)))
        sos = float(phys['sos'] + np.random.normal(0, 10.0 * noise_factor))
        attenuation = float(np.clip(phys['attenuation'] + np.random.normal(0, 0.015 * noise_factor), 0.15, 1.15))
        phase_shift = float(phys.get('phase_shift', 0.0) + np.random.normal(0, 0.02 * noise_factor))
        r_th = float(phys.get('r_th', 2.0) * (1.0 + np.random.normal(0, 0.02 * noise_factor)))
        c_th = float(phys.get('c_th', 500.0) * (1.0 + np.random.normal(0, 0.02 * noise_factor)))

        # Electrical ECM calculations
        i_pulse = float(self.params.get('pulse_amplitude_a', 0.5))
        ocv = float(3.0 + 1.2 * np.clip(self.soc, 0.0, 1.0))
        voltage = float(ocv - i_pulse * r0 + np.random.normal(0, 0.002 * noise_factor))
        current = float(i_pulse + np.random.normal(0, 0.005 * noise_factor))
        power = float(voltage * current)

        # Ultrasonic calculations (round-trip path length d = 2 * 0.01 m = 0.02 m)
        tof_s = float(2.0 * 0.01 / max(100.0, sos) + np.random.normal(0, 0.05e-6 * noise_factor))
        tof_us = float(tof_s * 1e6)

        # Thermal calculations
        ambient_temp = 25.0 + (10.0 if self.degradation_mode == 'internal_short' else 0.0)
        temp_rise = float((r0 + r1) * (i_pulse ** 2) * r_th * 30.0 + max(0.0, ambient_temp - 25.0) + np.random.normal(0, 0.05 * noise_factor))
        temperature = float(25.0 + temp_rise)
        dT_dt = float((i_pulse ** 2) * (r0 + r1) * 50.0 / (c_th * 1e-2) + np.random.normal(0, 0.01 * noise_factor))

        return {
            'electrical': {
                'voltage': voltage,
                'current': current,
                'power': power,
                'resistance': r0,
                'r0': r0,
                'r1': r1,
                'c1': c1
            },
            'ultrasonic': {
                'tof': tof_s,
                'tof_us': tof_us,
                'amplitude': attenuation,
                'phase_shift': phase_shift,
                'speed_of_sound': sos
            },
            'thermal': {
                'temperature_rise': temp_rise,
                'temperature': temperature,
                'dT_dt': dT_dt
            }
        }

    def update_visualization(self):
        """Update the 3D visualization"""
        if self.headless or self.ax_3d is None:
            return

        # Clear the 3D axis
        self.ax_3d.clear()

        # Set labels and title
        self.ax_3d.set_xlabel('X (m)', fontsize=8)
        self.ax_3d.set_ylabel('Y (m)', fontsize=8)
        self.ax_3d.set_zlabel('Z (m)', fontsize=8)
        self.ax_3d.set_title('3D System Configuration', fontsize=10)

        # Draw battery cell (cylinder approximation)
        self.draw_battery_cell()

        # Draw sensors
        self.draw_sensors()

        # Draw MCU and converter
        self.draw_mcu_and_converter()

        # Draw excitation pulse visualization
        self.draw_excitation_pulse()

        # Set equal aspect ratio and limits
        max_range = self.params['cell_length'] * 0.6
        self.ax_3d.set_xlim([-max_range, max_range])
        self.ax_3d.set_ylim([-max_range, max_range])
        self.ax_3d.set_zlim([-max_range*0.8, max_range*0.8])

        # Update status displays
        self.update_status_display()

        # Redraw
        self.fig.canvas.draw_idle()

    def draw_battery_cell(self):
        """Draw the battery cell as a cylinder"""
        # Parameters
        radius = self.params['cell_width'] / 2
        height = self.params['cell_height']

        # Create cylinder
        u = np.linspace(0, 2 * np.pi, 12)
        v = np.linspace(0, height, 8)
        u, v = np.meshgrid(u, v)
        x = radius * np.cos(u)
        y = radius * np.sin(u)
        z = v - height/2  # Center vertically

        # Plot surface
        self.ax_3d.plot_surface(x, y, z, alpha=0.2, color='lightgray', linewidth=0.5)

        # Add cell label
        self.ax_3d.text(0, 0, height/2 + 0.008, 'Battery Cell',
                       fontsize=8, ha='center', va='bottom', color='darkgray')

    def draw_sensors(self):
        """Draw all sensors on the battery cell"""
        # Electrical sensor (top) - red sphere
        elec_pos = self.params['electrical_pos']
        self.ax_3d.scatter([elec_pos[0]], [elec_pos[1]], [elec_pos[2]],
                          c='red', s=60, marker='o', alpha=0.8)
        self.ax_3d.text(elec_pos[0], elec_pos[1], elec_pos[2] + 0.008,
                       'Elec', fontsize=7, ha='center', va='bottom', color='red')

        # Ultrasonic transmitter (left) - blue square
        ult_tx_pos = self.params['ultrasonic_tx_pos']
        self.ax_3d.scatter([ult_tx_pos[0]], [ult_tx_pos[1]], [ult_tx_pos[2]],
                          c='blue', s=50, marker='s', alpha=0.8)
        self.ax_3d.text(ult_tx_pos[0], ult_tx_pos[1], ult_tx_pos[2] + 0.008,
                       'US Tx', fontsize=7, ha='center', va='bottom', color='blue')

        # Ultrasonic receiver (right) - blue square
        ult_rx_pos = self.params['ultrasonic_rx_pos']
        self.ax_3d.scatter([ult_rx_pos[0]], [ult_rx_pos[1]], [ult_rx_pos[2]],
                          c='blue', s=50, marker='s', alpha=0.8)
        self.ax_3d.text(ult_rx_pos[0], ult_rx_pos[1], ult_rx_pos[2] + 0.008,
                       'US Rx', fontsize=7, ha='center', va='bottom', color='blue')

        # Draw line between ultrasonic transducers to show path
        self.ax_3d.plot([ult_tx_pos[0], ult_rx_pos[0]],
                       [ult_tx_pos[1], ult_rx_pos[1]],
                       [ult_tx_pos[2], ult_rx_pos[2]],
                       'b--', alpha=0.4, linewidth=0.8)

        # Thermal sensor (bottom) - green triangle
        thor_pos = self.params['thermal_pos']
        self.ax_3d.scatter([thor_pos[0]], [thor_pos[1]], [thor_pos[2]],
                          c='green', s=50, marker='^', alpha=0.8)
        self.ax_3d.text(thor_pos[0], thor_pos[1], thor_pos[2] - 0.008,
                       'Thermal', fontsize=7, ha='center', va='top', color='green')

    def draw_mcu_and_converter(self):
        """Draw MCU and bidirectional DC-DC converter"""
        # MCU - purple cube
        mcu_pos = self.params['mcu_pos']
        self.draw_cube(mcu_pos, size=0.006, color='purple', alpha=0.7)
        self.ax_3d.text(mcu_pos[0], mcu_pos[1], mcu_pos[2] + 0.008,
                       'MCU', fontsize=7, ha='center', va='bottom', color='purple')

        # Bidirectional DC-DC converter - orange cylinder (simplified as cube)
        conv_pos = self.params['converter_pos']
        self.draw_cube(conv_pos, size=0.006, color='orange', alpha=0.7)
        self.ax_3d.text(conv_pos[0], conv_pos[1], conv_pos[2] + 0.008,
                       'Conv', fontsize=7, ha='center', va='bottom', color='orange')

        # Draw connection lines (simulated buses)
        # MCU to sensors (I2C/SPI)
        sensor_positions = [
            self.params['electrical_pos'],
            self.params['ultrasonic_tx_pos'],
            self.params['ultrasonic_rx_pos'],
            self.params['thermal_pos']
        ]

        for pos in sensor_positions:
            self.ax_3d.plot([mcu_pos[0], pos[0]],
                           [mcu_pos[1], pos[1]],
                           [mcu_pos[2], pos[2]],
                           'k:', alpha=0.2, linewidth=0.5)

        # MCU to converter (control signals)
        self.ax_3d.plot([mcu_pos[0], conv_pos[0]],
                       [mcu_pos[1], conv_pos[1]],
                       [mcu_pos[2], conv_pos[2]],
                       'k-.', alpha=0.3, linewidth=0.6)

    def draw_cube(self, center, size, color='blue', alpha=0.7):
        """Draw a cube at the specified position"""
        # Create cube vertices
        half_size = size / 2
        offsets = [-half_size, half_size]

        # Generate all 8 corners
        corners = []
        for x in offsets:
            for y in offsets:
                for z in offsets:
                    corners.append([center[0] + x, center[1] + y, center[2] + z])
        corners = np.array(corners)

        # Define the 12 edges of a cube
        edges = [
            [0, 1], [1, 3], [3, 2], [2, 0],  # bottom face
            [4, 5], [5, 7], [7, 6], [6, 4],  # top face
            [0, 4], [1, 5], [2, 6], [3, 7]   # vertical edges
        ]

        # Plot each edge
        for edge in edges:
            start, end = corners[edge[0]], corners[edge[1]]
            self.ax_3d.plot([start[0], end[0]],
                           [start[1], end[1]],
                           [start[2], end[2]],
                           color=color, alpha=alpha, linewidth=1)

    def draw_excitation_pulse(self):
        """Visualize the excitation pulse"""
        # Show excitation pulse as a vertical line with intensity modulation
        pulse_height = 0.015

        # Base position (center of cell)
        base_x, base_y, base_z = 0, 0, 0

        # Draw pulse line
        self.ax_3d.plot([base_x, base_x],
                       [base_y, base_y],
                       [base_z - pulse_height/2, base_z + pulse_height/2],
                       'k-', linewidth=2, alpha=0.6, label='Excitation Pulse')

        # Add pulse label
        self.ax_3d.text(base_x, base_y, base_z + pulse_height/2 + 0.003,
                       'Excitation', fontsize=7, ha='center', va='bottom',
                       color='black', rotation=90)

    def update_status_display(self):
        """Update the status display text"""
        # Compute current sensor readings
        readings = self.compute_sensor_readings()

        # Format status text
        status_lines = [
            f"System State:",
            f"  SOC: {self.soc:.2f}",
            f"  Degradation: {self.degradation_mode.replace('_', ' ').title()}",
            f"  Noise: {self.noise_level:.2f}",
            f"  Excitation: {self.params['pulse_amplitude_a']:.2f} A",
            "",
            f"Sensor Readings:",
            f"  Electrical:",
            f"    V: {readings['electrical']['voltage']:.3f} V",
            f"    I: {readings['electrical']['current']:.3f} A",
            f"    P: {readings['electrical']['power']:.3f} W",
            f"  Ultrasonic:",
            f"    ToF: {readings['ultrasonic']['tof']*1e6:.1f} µs",
            f"    Amp: {readings['ultrasonic']['amplitude']:.3f}",
            f"    Phs: {readings['ultrasonic']['phase_shift']*1000:.1f} mrad",
            f"  Thermal:",
            f"    ΔT: {readings['thermal']['temperature_rise']:.3f} K",
            f"    dT/dt: {readings['thermal']['dT_dt']:.3f} K/s"
        ]

        self.status_text.set_text('\n'.join(status_lines))

        # Format parameter text (what user can control)
        param_lines = [
            f"Controls:",
            f"  • SOC: {self.soc:.2f}",
            f"  • Degradation: {self.degradation_mode.replace('_', ' ').title()}",
            f"  • Noise: {self.noise_level:.2f}",
            f"  • Excitation: {self.params['pulse_amplitude_a']:.2f} A",
            "",
            f"Scenarios:",
            f"  Healthy | Li Plating | Active Loss",
            f"  Electrolyte | Gas Gen | Internal Short"
        ]

        self.param_text.set_text('\n'.join(param_lines))

    # Data interface methods for ingestor
    def get_simulation_state(self):
        """
        Get the current simulation state for data ingestion.
        Returns a dictionary with all parameters needed by the ingestor.
        """
        # Increment step counter
        self._step_count += 1

        return {
            'soc': self.soc,
            'degradation_mode': self.degradation_mode,
            'noise_level': self.noise_level,
            'excitation_amplitude': self.excitation_amplitude,
            'step_count': self._step_count,
            'timestamp': self._get_timestamp() if hasattr(self, '_last_timestamp') else None
        }

    def _get_timestamp(self):
        """Get current timestamp - placeholder for actual timing"""
        import time
        return time.time()

    def get_sensor_readings(self):
        """Get current sensor readings - wrapper for compute_sensor_readings"""
        return self.compute_sensor_readings()

    def run(self):
        """Start the simulation"""
        plt.show()


def main():
    """Main function to run the 3D simulation"""
    print("Starting EV Battery Multi-Modal Diagnostic System - 3D Visualization")
    print("=" * 65)
    print("Features:")
    print("  - Interactive 3D visualization of battery diagnostic system")
    print("  - Real-time sensor reading simulation based on degradation modes")
    print("  - Adjustable parameters: SOC, degradation mode, noise, excitation")
    print("  - Preset scenarios for common battery degradation cases")
    print("  - Visual representation of sensors, MCU, and converter")
    print("")
    print("Close the window to exit the simulation.")
    print("")

    # Create and run simulator
    simulator = EVBattery3DSimulator()
    simulator.run()


if __name__ == "__main__":
    main()