# Gazebo Multi-Physics Simulation Package

This package provides a simulation environment for the EV Battery Diagnostic System using Gazebo (Gz Sim) and ROS 2.

## Features
- **SDF Battery Module Model**: Multi-cell high-voltage lithium-ion pack with realistic mass, inertia, and visual contact pads.
- **Thermal & Environmental World**: `ev_battery_thermal_world.sdf` physics world with directional sunlight and thermal sensor plugins.
- **Coupled Multi-Physics Bridge**: Real-time simulation of coupled thermal, mechanical stress, ultrasonic acoustic propagation, and electrical charging/discharging.
- **Telemetry Streaming**: 10 Hz telemetry for integration with the FastAPI backend or independent ROS 2 nodes.

## Directory Structure
```
gazebo/
├── models/
│   └── ev_battery_pack/
│       ├── model.config
│       └── model.sdf
├── worlds/
│   └── ev_battery_thermal_world.sdf
├── gazebo_battery_bridge.py
├── run_gazebo_sim.py
└── README.md
```

## Running the Simulation

### 1. Standalone Sensor Bridge (Continuous)
```bash
python gazebo/run_gazebo_sim.py
```

### 2. Standalone with Raw JSON Output
```bash
python gazebo/run_gazebo_sim.py --json-out
```

### 3. Launch Native Gazebo GUI (Requires Gazebo / Gz Sim)
```bash
python gazebo/run_gazebo_sim.py --mode native
```
