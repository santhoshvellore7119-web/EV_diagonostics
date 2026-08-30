# Gazebo Integration for EV Battery Diagnostic Dashboard

This document explains how to integrate Gazebo (via ROS 2) with the Unified Diagnostic Dashboard for enhanced battery simulation and testing capabilities.

## Overview

The Gazebo integration replaces the standard Python/matplotlib-based 3D simulation with a high-fidelity physics-based simulation using Gazebo (or Ignition Gazebo) through ROS 2. This provides more realistic battery behavior modeling, including complex electro-thermal-mechanical interactions.

## Prerequisites

Before integrating Gazebo, ensure you have:

1. **Ubuntu 20.04 or 22.04** (recommended for ROS 2 compatibility)
2. **ROS 2 Foxy Fitzroy** (for Ubuntu 20.04) or **ROS 2 Humble Hawksbill** (for Ubuntu 22.04)
3. **Gazebo 11** (comes with ROS 2 Foxy) or **Ignition Gazebo** (comes with ROS 2 Humble)
4. **Git** for cloning additional repositories
5. **Basic familiarity with ROS 2 concepts** (nodes, topics, messages)

## Installation Steps

### 1. Install ROS 2

Follow the official ROS 2 installation guide for your Ubuntu version:

**For Ubuntu 22.04 (ROS 2 Humble):**
```bash
# Set locale
locale  # check for UTF-8
sudo apt update && sudo apt install locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# Add the ROS 2 apt repository
sudo apt install software-properties-common
sudo add-apt-repository universe

sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install ros-humble-desktop

# Source ROS 2 setup
source /opt/ros/humble/setup.bash

# Install development tools
sudo apt install ros-humble-ros-base
sudo apt install ros-humble-rviz2
```

**For Ubuntu 20.04 (ROS 2 Foxy):**
Replace `humble` with `foxy` in the above commands.

### 2. Install Gazebo/Ignition Dependencies

Gazebo is typically included with ROS 2 desktop installations, but you may need additional packages:

```bash
# For ROS 2 Humble (Ignition Gazebo)
sudo apt install ros-humble-ignition-gazebo

# For ROS 2 Foxy (Gazebo 11)
sudo apt install ros-foxy-gazebo-ros-pkgs
```

### 3. Verify Installation

Test that ROS 2 and Gazebo are working:

```bash
# Source ROS 2
source /opt/ros/humble/setup.bash  # or foxy

# Run a simple test
ros2 run demo_nodes_cpp talker

# In another terminal:
ros2 run demo_nodes_cpp listener

# Test Gazebo (should open a window)
gazebo  # or ign gazebo for Ignition
```

## Setting Up the Battery Simulation Model

To use Gazebo for battery simulation, you need a Gazebo model that represents an EV battery cell and publishes the necessary sensor data.

### Option 1: Use an Existing Battery Model

Check if there are existing EV battery models in Gazebo model databases:
- [Gazebo Models Fuel](https://fuel.gazebosim.org/)
- [ROS 2 Gazebo Repositories](https://github.com/ros2/gazebo_ros_pkgs)

### Option 2: Create a Custom Battery Model

If no suitable model exists, you'll need to create one. This involves:

1. **SDF (Simulation Description Format)** file defining the battery geometry
2. **Plugins** to simulate battery electrochemistry and publish sensor data
3. **ROS 2 integrators** to convert Gazebo data to ROS topics

A simplified approach is to create a model that:
- Represents the battery cell geometry
- Uses Gazebo's built-in sensors or custom plugins to publish:
  - Voltage (`/battery/voltage` - std_msgs/Float64)
  - Current (`/battery/current` - std_msgs/Float64)
  - Temperature (`/battery/temperature` - sensor_msgs/Temperature)
  - Time of Flight (`/ultrasonic/time_of_flight` - std_msgs/Float64)
  - And other required topics

### Example Topic Mapping

The Gazebo ingestor in this project expects the following ROS 2 topics:

| Topic | Message Type | Description |
|-------|--------------|-------------|
| `/battery/voltage` | std_msgs/Float64 | Battery voltage in volts |
| `/battery/current` | std_msgs/Float64 | Battery current in amperes |
| `/battery/temperature` | sensor_msgs/Temperature | Battery temperature in Celsius |
| `/ultrasonic/time_of_flight` | std_msgs/Float64 | Ultrasonic time of flight in seconds |
| `/ultrasonic/amplitude` | std_msgs/Float64 | Ultrasonic signal amplitude |
| `/ultrasonic/phase_shift` | std_msgs/Float64 | Ultrasonic phase shift in radians |
| `/thermal/heat_flux` | std_msgs/Float64 | Heat flux in W/m² |
| `/battery/soc` | std_msgs/Float64 | State of charge (0.0-1.0) |
| `/battery/degradation_mode` | std_msgs/Float64 | Degradation mode encoded as float |

## Configuration

### 1. Backend Configuration

The Gazebo ingestor (`backend/ingest/gazebo.py`) is already configured to:
- Connect to ROS 2
- Subscribe to the expected topics
- Convert ROS messages to DiagnosticFrame format
- Fall back to simulation if ROS 2 is not available

No additional backend configuration is needed unless you change topic names.

### 2. Frontend Configuration

The frontend has been updated to:
- Accept 'gazebo' as a valid mode in the control panel
- Display appropriate labels and information for Gazebo mode
- Reuse the 3D visualization capabilities for Gazebo data

No additional frontend configuration is needed.

### 3. Environment Variables

Ensure the backend can connect to your Gazebo/ROS 2 simulation:
- The ingestor automatically attempts to initialize ROS 2
- If running on the same machine, no configuration is needed
- If running on different machines, configure ROS_DOMAIN_ID and ROS_LOCALHOST_ONLY appropriately

## Running the Integrated System

### Step 1: Start ROS 2 (if not already sourced)
```bash
source /opt/ros/humble/setup.bash  # Adjust for your ROS 2 version
```

### Step 2: Launch Your Gazebo Battery Simulation
```bash
# Launch your custom battery simulation
ros2 launch your_battery_pkg battery_simulation.launch.py

# Or run Gazebo directly with your model
gazebo --verbose path/to/your/battery_model.sdf
```

### Step 3: Start the Diagnostic Dashboard Backend
```bash
cd /path/to/EV_diagonostics/backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Step 4: Start the Diagnostic Dashboard Frontend
```bash
cd /path/to/EV_diagonostics/frontend
npm start
```

### Step 5: Switch to Gazebo Mode
1. Open the dashboard in your browser (http://localhost:3000)
2. Click the "Gazebo" button in the control panel
3. The system should now display data from your Gazebo simulation

## Troubleshooting

### Common Issues

1. **ROS 2 not found**
   - Ensure ROS 2 is properly sourced: `source /opt/ros/<distro>/setup.bash`
   - Check that ROS 2 packages are installed: `ros2 --version`

2. **Topics not being published**
   - Verify your Gazebo model is publishing to the expected topics
   - Use `ros2 topic list` to see available topics
   - Use `ros2 topic echo /topic_name` to check data flow

3. **Backend falling back to simulation**
   - Check console output for ROS 2 initialization errors
   - Ensure the Gazebo ingestor can import rclpy: `python3 -c "import rclpy"`
   - Verify firewall settings allow localhost communication

4. **No data in dashboard**
   - Check that the backend is receiving data: look for "Gazebo frame" logs
   - Verify WebSocket connection in browser developer tools
   - Check that mode was successfully switched to 'gazebo'

### Validation

To validate your Gazebo integration is working correctly:

1. Check that the backend console shows: "Gazebo/ROS 2 ingestor initialized"
2. Verify that you see log messages like: "Gazebo frame X: Voltage=3.7V, Degradation=healthy"
3. Confirm the frontend shows "Gazebo" as the active mode in the footer
4. Watch for changing values in the 3D view as your Gazebo simulation runs

## Customization

### Adjusting Topic Names

If your Gazebo simulation uses different topic names, modify:
- `backend/ingest/gazebo.py`: Update the topic names in the subscriber creation
- The callback functions remain the same, just change the topic strings

### Adding Additional Sensors

To add more sensor data to the DiagnosticFrame:
1. Add new subscribers in `gazebo.py` `__init__` method
2. Add callback methods to store the data
3. Update `_convert_to_diagnostic_frame()` to include the new fields
4. Update the DiagnosticFrame TypeScript interface in frontend if needed
5. Update any views or panels that should display the new data

## Performance Considerations

Gazebo simulations can be computationally intensive. For optimal performance:

1. **Use appropriate simulation speed**: Adjust `real_time_update_rate` in your SDF
2. **Simplify collision geometry**: Use simple shapes for physics calculations
3. **Limit visual complexity**: Use lower detail models for physics-based rendering
4. **Consider headless mode**: For testing without GUI: `gazebo -s`
5. **Monitor resources**: Use `htop` or similar to check CPU/Memory usage

## References

- ROS 2 Documentation: https://docs.ros.org/en/humble/
- Gazebo Documentation: https://gazebosim.org/api/guide/
- Ignition Gazebo Documentation: https://gazebosim.org/api/ign/
- ROS 2 Gazebo Integration: https://github.com/ros2/gazebo_ros_pkgs
- Battery Modeling in Gazebo: Search for electrochemical models in Gazebo Fuel

## Notes for Development

1. During development, you can use the built-in simulation mode of the Gazebo ingestor by ensuring ROS 2 is not available or not sourced.
2. The ingestor gracefully degrades to simulation mode, allowing development and testing without a full Gazebo setup.
3. When deploying to a system with Gazebo/ROS 2, simply source the ROS 2 environment before starting the backend.