# Task 2: Python Multi-Modal Simulation - Uncertainty-Aware Fusion

## Overview
This folder contains the enhanced Python multi-modal simulation system featuring uncertainty-aware fusion networks, RESENSING state decision engine, and comprehensive diagnostic capabilities for EV battery health monitoring.

## Files Included

### Core Models
- `models/fusion_net.py` - Uncertainty-aware multi-branch fusion network with precision-weighted attention
- `models/train.py` - Uncertainty-aware loss functions, training scripts, and ablation studies
- `models/evaluate.py` - Model evaluation and testing utilities

### Control Systems
- `control/decision_engine.py` - Decision engine with RESENSING state and confidence thresholding
- `control/rebalancing_sim.py` - confidence logging, fault injection simulation, and rebalancing algorithms

### Core Simulation
- `core/physics_engine.py` - Enhanced multi-physics simulation with to_csv export for MATLAB cross-validation
- `core/virtual_daq.py` - Configurable sensor noise and fault injection for realistic testing
- `core/cell_database.py` - Synthetic battery data generation for various degradation modes

### Dashboard & Visualization
- `dashboard/pages/live_diagnostic.py` - Enhanced Streamlit multi-page application for live diagnostics
- `dashboard/pages/scenario_lab.py` - Interactive scenario testing environment for degradation modes
- `dashboard/app.py` - Main dashboard application entry point

### Testing & Validation
- `tests/test_integration.py` - Integration tests for system components
- `tests/test_simulation.py` - Unit tests for simulation accuracy
- `run_full_pipeline.py` - Complete end-to-end simulation pipeline

### Configuration
- `config/params.py` - System parameters and configuration settings

## Key Innovations Implemented
✅ **Uncertainty-Aware Multi-Branch Fusion Network**
- Heteroscedastic uncertainty estimation for each sensor modality
- Precision-weighted attention mechanism for adaptive sensor fusion
- Confidence quantification in fusion outputs

✅ **RESENSING State Decision Engine**
- Low-confidence state triggering maximum re-sense cycles
- Confidence thresholding for reliable degradation mode classification
- Prevention of infinite loops through cycle limits

✅ **Enhanced Simulation Capabilities**
- Configurable sensor noise and fault injection
- To_csv export for MATLAB/Simulink cross-validation
- Scenario-based testing for all degradation modes

✅ **Interactive Diagnostic Dashboard**
- Live multi-sensor data visualization
- Interactive scenario lab for testing recovery actions
- Real-time ML prediction display with confidence indicators

## Verification
All files have been verified for:
- Python syntax correctness (no import or runtime errors)
- Successful instantiation of all core components
- Proper tensor shapes and data flow in fusion network
- Correct decision engine mapping (e.g., Li Plating → PULSE_DEPLATING)
- Functional dashboard applications

This implementation provides a robust, uncertainty-aware diagnostic system that maintains performance even under noisy or faulty sensor conditions, with intelligent fallback mechanisms for low-confidence scenarios.
