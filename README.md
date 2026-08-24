
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
│   ├── bom/                  # Bill of materials targeting <$50/channel
│   ├── pinout/               # Connection tables and pin assignments
│   ├── mechanical/           # Transducer mounting guides
│   └── timing/               # Timing diagrams and synchronization notes
├── host_application/         # Host PC application for visualization and control
│   ├── src/                  # Application source code
│   │   ├── __init__.py       # Package initializer
│   │   ├── host_app.py       # Main application window
│   │   ├── main.py           # Application entry point
│   │   ├── logger.py         # Centralized logging configuration
│   │   ├── serial_handler.py # Serial communication management
│   │   ├── data_manager.py   # Data buffering, storage, and replay
│   │   ├── plot_manager.py   # Plot management and visualization
│   │   ├── ml_handler.py     # ML result processing and display
│   │   └── ui/               # User interface components
│   ├── test_logs/            # Test logs from development
│   └── logs/                 # Runtime logs (generated during execution)
├── matlab_simulink_demo/     # MATLAB/Simulink digital twin
│   ├── battery_system_demo.m # Main demonstration script
│   ├── load_parameters.m     # System parameter loader
│   ├── degradation_mode_library.m # Centralized degradation parameters
│   ├── simulate_cell_response.m # Enhanced multi-physics simulation
│   ├── estimate_ecm_params_rls.m # RLS estimator implementation
│   ├── stateflow/            # Stateflow charts
│   │   └── excitation_supervisor.sfx # Adaptive control statechart
│   ├── scripts/              # Utility scripts
│   │   ├── run_all_scenarios.m # Batch comparison adaptive vs fixed excitation
│   │   ├── generate_patent_figures.m # Patent application figures
│   │   ├── generate_idp_report_plots.m # IDP report visualizations
│   │   └── compare_with_python_digital_twin.m # MATLAB/Python cross-validation
│   ├── models/               # Simulink model placeholders
│   ├── validation/           # Validation scripts
│   └── utils/                # Utility functions
├── simulation_3d_demo/       # 3D EV battery simulation
│   ├── ev_battery_3d_simulation.py # Main simulation class
│   ├── test_basic_functionality.py # Structure and syntax tests
│   ├── test_simulation.py    # Import and functionality tests
│   ├── verify_simulation.py  # Verification of simulation components
│   └── __pycache__/          # Python cache (generated)
├── docs/                     # Documentation
│   └── (to be added)         # Patent-ready claims, etc.
├── tests/                    # Test scripts and debug utilities
│   ├── test_decision_engine.py
│   ├── test_ml_model.py
│   ├── verify_system.py
│   ├── final_verification.py
│   └── scratch/              # Temporary debug scripts (moved from root)
├── README.md                 # This file
├── REQUIREMENTS.md           # Dependencies (see below)
├── LICENSE                   # MIT license
└── .gitignore                # Git ignore rules
```

