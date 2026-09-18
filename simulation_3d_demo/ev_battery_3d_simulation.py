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
        """Default system parameters and physical dimensions"""
        return {
            # Cell dimensions (meters) - 18650 / 21700 standard form factors
            'cell_length': 0.065,   # 65 mm height
            'cell_width': 0.018,    # 18 mm diameter (18650 cylinder)
            'cell_radius': 0.009,   # 9 mm radius
            'cell_height': 0.065,   # 65 mm height

            # Jelly-roll layer physical properties
            'anode_thickness_m': 80e-6,      # 80 µm Graphite
            'cathode_thickness_m': 70e-6,    # 70 µm NMC/LFP
            'separator_thickness_m': 20e-6,  # 20 µm Polyolefin
            'cu_foil_thickness_m': 10e-6,    # 10 µm Copper
            'al_foil_thickness_m': 15e-6,    # 15 µm Aluminum

            # Anisotropic thermal conductivity (W / (m*K))
            'k_radial': 0.55,       # Low across polymer/electrolyte layers
            'k_axial': 28.5,        # High along metallic current collectors
            'rho_density': 2450.0,  # kg / m^3
            'cp_specific_heat': 1050.0, # J / (kg*K)

            # Acoustic impedance of layers (MRayl = 1e6 kg/(m^2*s))
            'acoustic_impedances': {
                'copper': 41.8,     # Cu current collector
                'aluminum': 17.3,   # Al current collector
                'electrolyte': 1.6, # Liquid carbonate electrolyte
                'separator': 1.9,   # Polyethylene/Polypropylene
                'graphite': 5.2,    # Anode matrix
                'nmc_cathode': 12.8,# Cathode active material
                'gas_pocket': 0.0004,# High impedance mismatch (gas generation)
                'li_plating': 2.8   # Metallic lithium deposition layer
            },

            # Sensor positions (relative to cell center in meters)
            'electrical_pos': np.array([0, 0, 0.035]),      # Top positive terminal
            'ultrasonic_tx_pos': np.array([-0.009, 0, 0]),  # Left side wall
            'ultrasonic_rx_pos': np.array([0.009, 0, 0]),   # Right side wall
            'thermal_pos': np.array([0, 0, -0.035]),        # Bottom base

            # MCU and converter positions
            'mcu_pos': np.array([0.035, 0, 0.02]),          # Top-right front
            'converter_pos': np.array([-0.035, 0, -0.02]),  # Bottom-left back

            # Excitation pulse parameters
            'pulse_width_s': 10e-6,    # 10 microseconds
            'pulse_amplitude_a': 0.5,  # 500 mA
            'pulse_period_s': 0.1      # 10 Hz
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

    def compute_3d_thermal_field(self, nr=8, ntheta=16, nz=10):
        """
        Compute 3D finite-volume temperature field T(r, theta, z) across the cylindrical cell.
        Solves anisotropic steady-state/quasi-transient heat conduction:
        k_r * (d2T/dr2 + 1/r*dT/dr) + k_z * d2T/dz2 + q''' = rho * Cp * dT/dt
        """
        radius = float(self.params['cell_width']) / 2.0
        height = float(self.params['cell_height'])
        k_r = float(self.params.get('k_radial', 0.55))
        k_z = float(self.params.get('k_axial', 28.5))
        
        r_grid = np.linspace(0.001, radius, nr)
        theta_grid = np.linspace(0, 2 * np.pi, ntheta)
        z_grid = np.linspace(-height / 2.0, height / 2.0, nz)

        # Baseline ambient temperature
        ambient = 25.0 + (10.0 if self.degradation_mode == 'internal_short' else 0.0)
        phys = DEGRADATION_PHYSICS_PARAMS.get(self.degradation_mode, DEGRADATION_PHYSICS_PARAMS['healthy'])
        i_pulse = float(self.params.get('pulse_amplitude_a', 0.5))
        
        # Volumetric Joule heating source term q''' (W/m^3)
        cell_vol = np.pi * (radius ** 2) * height
        q_joule = (i_pulse ** 2) * (phys['r0'] + phys['r1']) / max(1e-8, cell_vol)

        T_3d = np.zeros((nr, ntheta, nz))

        # Core temperature rise from 1D analytical radial profile + axial cooling
        for i, r in enumerate(r_grid):
            for k, z in enumerate(z_grid):
                # Analytical cylindrical profile T(r) = T_surf + (q''' * R^2 / (4 * k_r)) * (1 - (r/R)^2)
                t_radial_rise = (q_joule * (radius ** 2) / (4.0 * max(0.1, k_r))) * (1.0 - (r / radius) ** 2)
                # Axial conduction to tabs at z = +/- height/2
                z_norm = 1.0 - (2.0 * abs(z) / height) ** 2
                t_axial_factor = 0.8 + 0.2 * z_norm
                
                base_t = ambient + (t_radial_rise * t_axial_factor * 0.05)
                T_3d[i, :, k] = base_t

        # Localized hotspot injection for internal short
        if self.degradation_mode == 'internal_short':
            # Defect location at r=0.4*R, theta=pi/4, z=0
            defect_r_idx = int(nr * 0.4)
            defect_th_idx = int(ntheta * 0.125)
            defect_z_idx = int(nz * 0.5)
            
            for i in range(nr):
                for j in range(ntheta):
                    for k in range(nz):
                        dist_sq = ((i - defect_r_idx) / nr) ** 2 + ((j - defect_th_idx) / ntheta) ** 2 + ((k - defect_z_idx) / nz) ** 2
                        hotspot_delta = 18.5 * np.exp(-dist_sq / 0.04)
                        T_3d[i, j, k] += hotspot_delta

        return {
            'r_grid': r_grid,
            'theta_grid': theta_grid,
            'z_grid': z_grid,
            'T_field': T_3d,
            'T_max': float(np.max(T_3d)),
            'T_min': float(np.min(T_3d)),
            'T_surface': T_3d[-1, :, :]
        }

    def compute_acoustic_ray_path(self, num_rays=12):
        """
        Simulate acoustic ray propagation through the multi-layer cylindrical jelly-roll.
        Calculates ToF, interface transmission coefficients, and ray trajectories.
        """
        radius = float(self.params['cell_width']) / 2.0
        tx_pos = self.params['ultrasonic_tx_pos']
        rx_pos = self.params['ultrasonic_rx_pos']
        
        phys = DEGRADATION_PHYSICS_PARAMS.get(self.degradation_mode, DEGRADATION_PHYSICS_PARAMS['healthy'])
        sos = float(phys['sos'])
        base_atten = float(phys['attenuation'])

        rays = []
        # Ray fan across the cell diameter
        z_offsets = np.linspace(-0.015, 0.015, num_rays)
        
        for idx, z_off in enumerate(z_offsets):
            p_start = np.array([tx_pos[0], tx_pos[1], tx_pos[2] + z_off])
            p_end = np.array([rx_pos[0], rx_pos[1], rx_pos[2] + z_off])
            
            # Straight-line ray path with layer transmission loss
            dist = np.linalg.norm(p_end - p_start)
            tof_ray_us = (dist / max(100.0, sos)) * 1e6
            
            # Attenuation calculation based on degradation mode
            if self.degradation_mode == 'gas_generation':
                # Severe acoustic scattering in gas bubbles
                ray_amp = base_atten * np.exp(-0.35 * (idx % 3 + 1))
            elif self.degradation_mode == 'internal_short':
                ray_amp = base_atten * (0.85 if abs(z_off) < 0.005 else 1.0)
            else:
                ray_amp = base_atten * (1.0 - 0.05 * (abs(z_off) / 0.015))

            rays.append({
                'start': p_start.tolist(),
                'end': p_end.tolist(),
                'tof_us': float(tof_ray_us),
                'amplitude': float(ray_amp)
            })

        return rays

    def compute_degradation_spatial_profile(self):
        """
        Generate 3D geometric coordinates for degradation visualization overlays.
        """
        radius = float(self.params['cell_width']) / 2.0
        height = float(self.params['cell_height'])
        
        profile = {
            'mode': self.degradation_mode,
            'features': []
        }

        if self.degradation_mode == 'li_plating':
            # Dendrite layer on outer anode perimeter
            angles = np.linspace(0, 2 * np.pi, 24)
            for ang in angles:
                dendrite_h = np.random.uniform(0.0005, 0.0015)
                profile['features'].append({
                    'type': 'plating_layer',
                    'pos': [float((radius - 0.001) * np.cos(ang)), float((radius - 0.001) * np.sin(ang)), float(np.random.uniform(-height/3, height/3))],
                    'radius': float(dendrite_h),
                    'severity': 0.85
                })
        elif self.degradation_mode == 'gas_generation':
            # Gas bubbles in jellyroll pockets
            for _ in range(16):
                r_pos = np.random.uniform(0.002, radius * 0.8)
                th_pos = np.random.uniform(0, 2 * np.pi)
                z_pos = np.random.uniform(-height * 0.35, height * 0.35)
                profile['features'].append({
                    'type': 'gas_bubble',
                    'pos': [float(r_pos * np.cos(th_pos)), float(r_pos * np.sin(th_pos)), float(z_pos)],
                    'radius': float(np.random.uniform(0.001, 0.0025)),
                    'reverberation_factor': 0.90
                })
        elif self.degradation_mode == 'internal_short':
            # Hotspot core defect
            profile['features'].append({
                'type': 'internal_short_core',
                'pos': [0.003, 0.003, 0.0],
                'radius': 0.0035,
                'temp_peak_c': 55.0
            })

        return profile

    def export_3d_state_dict(self):
        """
        Export complete 3D multi-physics state for JSON serialization and WebGL sync.
        """
        thermal_data = self.compute_3d_thermal_field()
        acoustic_rays = self.compute_acoustic_ray_path()
        degradation_profile = self.compute_degradation_spatial_profile()
        sensor_readings = self.compute_sensor_readings()

        return {
            'timestamp': self._get_timestamp(),
            'step_count': self._step_count,
            'soc': float(self.soc),
            'degradation_mode': self.degradation_mode,
            'dimensions': {
                'height_m': float(self.params['cell_height']),
                'radius_m': float(self.params['cell_width']) / 2.0
            },
            'sensors': {
                'electrical_pos': self.params['electrical_pos'].tolist(),
                'ultrasonic_tx_pos': self.params['ultrasonic_tx_pos'].tolist(),
                'ultrasonic_rx_pos': self.params['ultrasonic_rx_pos'].tolist(),
                'thermal_pos': self.params['thermal_pos'].tolist(),
                'mcu_pos': self.params['mcu_pos'].tolist(),
                'converter_pos': self.params['converter_pos'].tolist()
            },
            'thermal': {
                'T_max': thermal_data['T_max'],
                'T_min': thermal_data['T_min'],
                'surface_temperature_matrix': thermal_data['T_surface'].tolist()
            },
            'acoustic_rays': acoustic_rays,
            'degradation_profile': degradation_profile,
            'readings': sensor_readings
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
        self.ax_3d.set_title('3D Multi-Physics System Configuration', fontsize=10)

        # Draw battery cell with 3D thermal surface heatmap
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
        """Draw the battery cell as a cylinder with 3D thermal heatmap colormap"""
        radius = float(self.params['cell_width']) / 2.0
        height = float(self.params['cell_height'])

        # Create cylinder surface
        u = np.linspace(0, 2 * np.pi, 24)
        v = np.linspace(-height / 2.0, height / 2.0, 16)
        u_grid, v_grid = np.meshgrid(u, v)
        x = radius * np.cos(u_grid)
        y = radius * np.sin(u_grid)
        z = v_grid

        # Calculate surface thermal distribution for coloring
        thermal_data = self.compute_3d_thermal_field(nr=8, ntheta=24, nz=16)
        t_surface = thermal_data['T_surface'].T  # Shape matching meshgrid (16, 24)

        t_min = min(25.0, thermal_data['T_min'])
        t_max = max(35.0, thermal_data['T_max'])
        t_norm = (t_surface - t_min) / max(1e-3, (t_max - t_min))

        cmap = plt.get_cmap('plasma')
        colors = cmap(t_norm)

        # Plot colored surface
        self.ax_3d.plot_surface(x, y, z, facecolors=colors, alpha=0.6, linewidth=0.2, shade=True)

        # Add cell label
        self.ax_3d.text(0, 0, height/2 + 0.008, f"Cell ({self.degradation_mode})",
                       fontsize=8, ha='center', va='bottom', color='black', fontweight='bold')


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