#!/usr/bin/env python3
"""
Unit tests for Gazebo multi-physics simulation model, sensor plugins, ROS 2 topics,
and MATLAB 3D spatial co-simulation bridge.
"""

import os
import sys
import xml.etree.ElementTree as ET
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from gazebo.gazebo_battery_bridge import GazeboBatteryBridge
from matlab_simulink_demo.utils.export_3d_mesh_to_matlab import export_3d_physics_to_matlab


def test_gazebo_sdf_model_structure():
    """
    Verify Gazebo SDF model format:
    - Chassis and 4-cell series links
    - Optical thermal camera & Ultrasonic PZT array sensors
    - Battery thermal & ZVS rebalancing plugins
    """
    sdf_path = os.path.join(project_root, 'gazebo', 'models', 'ev_battery_pack', 'model.sdf')
    assert os.path.exists(sdf_path), "Gazebo model.sdf missing"

    tree = ET.parse(sdf_path)
    root = tree.getroot()
    model = root.find('model')
    assert model is not None, "Root element must contain <model>"
    assert model.attrib.get('name') == 'ev_battery_pack'

    # Verify 4-cell links
    links = [link.attrib.get('name') for link in model.findall('link')]
    assert 'chassis' in links
    assert 'cell_1' in links
    assert 'cell_2' in links
    assert 'cell_3' in links
    assert 'cell_4' in links
    assert 'rebalancer_power_stage' in links

    # Verify sensors
    sensors = [s.attrib.get('name') for s in model.findall('sensor')]
    assert 'pack_thermal_imager' in sensors
    assert 'pzt_ultrasonic_array' in sensors

    # Verify plugins
    plugin_files = [p.attrib.get('filename') for p in model.findall('plugin')]
    assert 'libgazebo_battery_thermal_plugin.so' in plugin_files
    assert 'libgazebo_zvs_rebalancing_plugin.so' in plugin_files


def test_gazebo_battery_bridge_multiphysics():
    """
    Verify Gazebo multi-physics bridge:
    - 3D stress tensors (Von Mises)
    - 7-layer acoustic power throughput
    - 4S active rebalancing current shuttling
    - ROS 2 topic formatting and MATLAB export formatting
    """
    bridge = GazeboBatteryBridge(pack_id="TEST-PACK-4S", update_rate_hz=10.0)
    packet = bridge.step_physics(dt=0.1)

    assert packet["source"] == "gazebo_sim"
    assert "electrical" in packet
    assert "thermal" in packet
    assert "mechanical" in packet
    assert "rebalancing" in packet
    assert "cells" in packet
    assert len(packet["cells"]) == 4

    # Verify mechanical 3D stress & acoustic throughput
    assert "sigma_von_mises_kpa" in packet["mechanical"]
    assert packet["mechanical"]["sigma_von_mises_kpa"] > 50.0
    assert "acoustic_power_throughput_pct" in packet["mechanical"]

    # Verify ROS 2 topic translation
    ros2_topics = bridge.to_ros2_topics(packet)
    assert "/ev_battery/telemetry" in ros2_topics
    assert "/ev_battery/spatial_3d_stress" in ros2_topics
    assert "/ev_battery/acoustic_echo" in ros2_topics
    assert "/ev_battery/zvs_rebalancing" in ros2_topics

    # Verify MATLAB telemetry formatting
    matlab_data = bridge.export_matlab_telemetry(packet)
    assert "V_pack" in matlab_data
    assert "Stress_VM_kPa" in matlab_data
    assert "P_acoustic_pct" in matlab_data
    assert len(matlab_data["Cell_SOCs"]) == 4


def test_matlab_3d_simulation_script_and_export():
    """
    Verify MATLAB 3D visualization script and Python 3D mesh export bridge.
    """
    matlab_script = os.path.join(project_root, 'matlab_simulink_demo', 'scripts', 'visualize_3d_battery_stress_thermal.m')
    assert os.path.exists(matlab_script), "MATLAB 3D visualizer script missing"

    with open(matlab_script, 'r', encoding='utf-8') as f:
        m_content = f.read()

    assert "visualize_3d_battery_stress_thermal" in m_content
    assert "sigma_von_mises_kpa" in m_content or "sigma_vm" in m_content
    assert "acoustic_boundaries" in m_content

    # Run Python-to-MATLAB 3D mesh exporter
    exported = export_3d_physics_to_matlab()
    assert os.path.exists(exported["json_file"])
    assert "thermal_3d" in exported
    assert "stress_tensors" in exported
    assert "acoustic_transfer" in exported
    assert "pack_4s_module" in exported


def test_gazebo_cpp_plugin_source_integrity():
    """
    Verify native C++ Gazebo ModelPlugin source and build files.
    """
    plugin_cpp = os.path.join(project_root, 'gazebo', 'plugins', 'gazebo_battery_thermal_plugin.cpp')
    cmakelists = os.path.join(project_root, 'gazebo', 'plugins', 'CMakeLists.txt')

    assert os.path.exists(plugin_cpp), "Gazebo plugin C++ source missing"
    assert os.path.exists(cmakelists), "Gazebo CMakeLists.txt missing"

    with open(plugin_cpp, 'r', encoding='utf-8') as f:
        cpp_content = f.read()

    assert "BatteryThermalModelPlugin" in cpp_content
    assert "GZ_REGISTER_MODEL_PLUGIN" in cpp_content
