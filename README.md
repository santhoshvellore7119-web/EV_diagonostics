# Low-Cost Multi-Modal Diagnostic and Active Cell-Rebalancing System for Second-Life EV Battery Packs

## Overview
This project implements a low-cost, multi-modal sensing system for diagnosing degradation in second-life electric vehicle (EV) battery packs and applying active recovery actions to restore capacity. The system combines electrical, ultrasonic, and thermal sensing synchronized to a single excitation pulse, fuses the data via a multi-branch neural network, and triggers targeted recovery waveforms via a bidirectional DC-DC converter.

## Features
- **Multi-Modal Sensing Front-End**:
  - Electrical: Dynamic resistance and polarization parameters via shunt-based measurement (INA226).
  - Ultrasonic: Time-of-Flight, amplitude, and phase shift using low-cost piezoelectric transducers.
  - Thermal: Contact array or IR thermopile for transient temperature response.
- **Deterministic Time-Synchronized DAQ**: Hardware-triggered excitation with simultaneous sampling.
- **Multi-Branch Fusion ML Architecture**: 1D-CNN encoders for each modality, fused for degradation mode classification and SOH regression.
- **Closed-Loop Active Rebalancing**: Decision engine triggers recovery actions (pulse deplating, equilibration, etc.) based on ML outputs.
- **Low-Cost Design**: Target BOM <$50 per channel vs. lab-grade equipment (>$10k).

## Project Structure
```
EV_Battery_Diagnostic_System/
├── firmware/                 # MCU firmware (ESP32/FreeRTOS)
│   ├── src/
│   │   ├── main.cpp          # Main firmware logic
│   │   ├── sensors/          # Sensor drivers (electrical, ultrasonic, thermal)
│   │   ├── daq/              # Data acquisition and fusion
│   │   ├── communication/    # UART and USB CDC
│   │   ├── utils/            # Timer, serializer, GPIO
│   │   └── ...
│   └── ...
├── ml_pipeline/              # PyTorch-based machine learning pipeline
│   ├── data/                 # Dataset and synthetic data generation
│   ├── models/               # Multi-branch fusion network
│   └── training/             # Training script with ablation studies
├── active_rebalancing/       # Recovery algorithms
│   ├── decision_engine/      # State machine for recovery decisions
│   ├── power_stage/          # PID controller for bidirectional DC-DC
│   └── verification/         # Scripts to verify recovery effectiveness
├── hardware/                 # Hardware documentation
│   ├── schematics/           # Block diagram
│   └── bom/                  # Bill of materials targeting <$50/channel
├── host_application/         # Host PC application for visualization and control
│   └── src/
│       └── host_app.py       # PyQt5 GUI for real-time monitoring
├── README.md                 # This file
└── REQUIREMENTS.md           # Dependencies (see below)
```

## Getting Started

### Firmware
1. Install ESP32 Arduino core or STM32CubeIDE.
2. Copy the `firmware/src` directory to your IDE.
3. Build and flash to your target MCU.

### Machine Learning Pipeline
1. Install dependencies: `pip install torch torchvision numpy scikit-learn matplotlib`
2. Run training: `cd ml_pipeline/training && python train.py`
3. The script will generate synthetic data, train the model, and save results.

### Host Application
1. Install dependencies: `pip install pyqt5 pyqtgraph pyserial numpy`
2. Run: `cd host_application/src && python host_app.py`
3. Connect to the MCU via serial port (default COM3, 115200 baud).

## Patent Claims
See the `docs/` directory for patent-ready claims (to be added).

## Citation
If you use this work, please cite:
```
@article{yourname2026evbattery,
  title={Low-Cost Multi-Modal Diagnostic and Active Cell-Rebalancing System for Second-Life EV Battery Packs},
  author={Your Name},
  journal={IEEE Transactions on Industrial Electronics},
  year={2026}
}
```

## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments
- Thanks to the open-source community for FreeRTOS, PyTorch, and PyQt5.