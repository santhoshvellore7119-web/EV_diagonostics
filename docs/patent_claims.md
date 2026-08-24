# Patent Claims for Low-Cost Multi-Modal Diagnostic and Active Cell-Rebalancing System

## Field of the Invention
The present invention relates to battery diagnostics, specifically to a low-cost multi-modal sensing system for assessing the state of health and degradation modes of electric vehicle (EV) battery packs, and to an active recovery system that applies targeted electrical waveforms to restore capacity.

## Background
Second-life EV battery packs retain significant capacity but exhibit variability in degradation states. Existing diagnostic equipment (electrochemical impedance spectrometers, ultrasonic analyzers) is costly (>$10k per channel), limiting widespread adoption. There is a need for a low-cost, integrated system that can simultaneously assess multiple degradation modes and apply recovery actions.

## Summary of the Invention
The invention provides a system and method for:
1. Synchronized multi-modal excitation and sensing (electrical, ultrasonic, thermal).
2. Real-time data acquisition and feature extraction.
3. Machine learning-based degradation mode classification and state-of-health estimation.
4. Closed-loop control of a bidirectional DC-DC converter to apply recovery waveforms.
5. Verification of recovery effectiveness.

## Claims

### Claim 1 (System Claim - Independent)
A low-cost multi-modal diagnostic and active cell-rebalancing system for an electric vehicle battery pack, comprising:
- an electrical sensing subsystem configured to measure bus voltage, shunt voltage, current, and power in response to an excitation pulse;
- an ultrasonic sensing subsystem comprising a pair of piezoelectric transducers configured to transmit and receive an ultrasonic pulse-echo signal, measuring time-of-flight, amplitude, and phase shift;
- a thermal sensing subsystem configured to measure transient temperature response and temperature gradient during excitation;
- a microcontroller unit (MCU) comprising:
  - a hardware timer configured to generate a periodic excitation pulse;
  - means for triggering the electrical, ultrasonic, and thermal sensing subsystems synchronously with the excitation pulse;
  - means for sampling outputs from each sensing subsystem at a high sampling rate;
  - means for fusing the sampled data into a synchronized data packet;
  - means for executing a machine learning algorithm that classifies degradation mode and estimates state-of-health from the fused data;
  - means for determining a recovery action based on the classified degradation mode and estimated state-of-health;
  - means for controlling a bidirectional DC-DC converter to apply a recovery waveform to the battery pack;
- a bidirectional DC-DC converter coupled to the battery pack and configured to discharge or charge the battery pack under control of the MCU;
- wherein the electrical sensing subsystem comprises a shunt-based current sensor (e.g., INA226) interfaced with the MCU via an inter-integrated circuit (I2C) bus;
- wherein the ultrasonic sensing subsystem comprises a transmitter and receiver piezoelectric transducer connected to general-purpose input/output (GPIO) pins of the MCU;
- wherein the thermal sensing subsystem comprises a digital temperature sensor (e.g., TMP102) interfaced with the MCU via I2C;
- wherein the MCU is further configured to stream the synchronized data packet to a host computer via a universal asynchronous receiver-transmitter (UART) or universal serial bus (USB) communication channel;
- wherein the system is configured to operate at a total bill-of-materials cost of less than fifty United States dollars (USD 50) per sensing channel.

### Claim 2 (Method Claim - Independent)
A method for diagnosing and actively recovering capacity in an electric vehicle battery pack, comprising:
- generating an excitation pulse using a hardware timer of a microcontroller unit (MCU);
- synchronously triggering an electrical sensing subsystem, an ultrasonic sensing subsystem, and a thermal sensing subsystem to sense a response to the excitation pulse;
- sampling outputs from the electrical sensing subsystem at a first sampling rate to obtain electrical signals;
- sampling outputs from the ultrasonic sensing subsystem at a second sampling rate to obtain an ultrasonic pulse-echo waveform;
- sampling outputs from the thermal sensing subsystem at a third sampling rate to obtain a transient thermal response;
- fusing the sampled electrical signals, ultrasonic pulse-echo waveform, and transient thermal response into a synchronized data packet;
- executing a machine learning algorithm on the synchronized data packet to classify degradation mode among a plurality of degradation modes and to estimate a state-of-health value;
- determining a recovery action based on the classified degradation mode and the estimated state-of-health value;
- controlling a bidirectional DC-DC converter to apply a recovery waveform to the battery pack according to the determined recovery action;
- wherein the excitation pulse, the electrical sensing, the ultrasonic sensing, and the thermal sensing are all triggered within a microsecond window to ensure temporal alignment;
- wherein the machine learning algorithm comprises a multi-branch fusion network with separate encoders for each modality and a fusion layer;
- wherein the recovery action is selected from the group consisting of: pulse deplating for lithium plating, equilibration for active material loss or electrolyte decomposition, gas recombination for gas generation, and short isolation for internal short;
- wherein the method further comprises verifying the effectiveness of the recovery action by repeating the sensing steps and comparing pre- and post-recovery state-of-health estimates or capacity measurements.

### Claim 3 (Dependent)
The system of Claim 1, wherein the hardware timer is configured to generate the excitation pulse with a pulse width of between 1 microsecond and 100 microseconds.

### Claim 4 (Dependent)
The system of Claim 1, wherein the excitation pulse has a repetition frequency of between 1 Hz and 1 kHz.

### Claim 5 (Dependent)
The system of Claim 1, wherein the electrical sensing subsystem samples the bus voltage and shunt voltage using an analog-to-digital converter (ADC) integrated within the MCU at a sampling rate of at least 100 kHz.

### Claim 6 (Dependent)
The system of Claim 1, wherein the ultrasonic sensing subsystem measures time-of-flight by detecting the leading edge of the received ultrasonic echo using a GPIO pin interrupt of the MCU.

### Claim 7 (Dependent)
The system of Claim 1, wherein the thermal sensing subsystem samples temperature at a sampling rate of at least 1 kHz to capture transient dynamics during excitation.

### Claim 8 (Dependent)
The system of Claim 1, wherein the machine learning algorithm is a neural network comprising:
- a first one-dimensional convolutional neural network (1D-CNN) branch processing the electrical signals;
- a second 1D-CNN branch processing the ultrasonic pulse-echo waveform;
- a third 1D-CNN branch processing the transient thermal response;
- a fusion layer that concatenates outputs from the three branches;
- a fully connected network following the fusion layer;
- a classification head outputting degradation mode probabilities; and
- a regression head outputting state-of-health estimate.

### Claim 9 (Dependent)
The system of Claim 1, wherein the bidirectional DC-DC converter operates in buck mode to discharge the battery pack and in boost mode to charge the battery pack, and wherein the MCU controls the converter via a proportional-integral-derivative (PID) algorithm regulating output voltage or current.

### Claim 10 (Dependent)
The system of Claim 1, further comprising a host computer configured to:
- receive the synchronized data packet via the UART or USB communication channel;
- execute the machine learning algorithm (optionally);
- display real-time sensor data and machine learning outputs in a graphical user interface;
- send commands to the MCU to initiate or halt sensing and recovery actions.

### Claim 11 (Dependent)
The method of Claim 2, wherein the excitation pulse is a current pulse of amplitude between 10 mA and 500 mA.

### Claim 12 (Dependent)
The method of Claim 2, wherein the classifying degradation mode comprises identifying at least one of: healthy, lithium plating, active material loss, electrolyte decomposition, gas generation, and internal short.

### Claim 13 (Dependent)
The method of Claim 2, wherein the determining a recovery action comprises:
- if the classified degradation mode is lithium plating and the estimated state-of-health is above a first threshold, applying a pulse deplating waveform;
- if the classified degradation mode is active material loss or electrolyte decomposition and the estimated state-of-health is above a second threshold, applying an equilibration waveform;
- if the classified degradation mode is gas generation and the estimated state-of-health is above a third threshold, applying a gas recombination waveform;
- if the classified degradation mode is internal short and the estimated state-of-health is above a fourth threshold, applying a short isolation waveform;
- otherwise, applying no recovery action.

### Claim 14 (Dependent)
The system of Claim 1, wherein the MCU is selected from the group consisting of: ESP32 series, STM32F4 series, and STM32H7 series.

### Claim 15 (Dependent)
The system of Claim 1, wherein the piezoelectric transducers operate at a resonant frequency of between 20 kHz and 200 kHz.

## Description of Drawings (Optional)
- FIG. 1: Block diagram of the system.
- FIG. 2: Timing diagram showing synchronized excitation and sensing.
- FIG. 3: Diagram of the multi-branch fusion network architecture.
- FIG. 4: Flowchart of the decision engine for recovery actions.
- FIG. 5: Example recovery waveforms (pulse deplating, equilibration, etc.).

## Abstract
A low-cost multi-modal diagnostic and active cell-rebalancing system for second-life EV battery packs is presented. The system synchronously excites and senses electrical, ultrasonic, and thermal responses to a single pulse, fuses the data via a multi-branch neural network to classify degradation mode and estimate state-of-health, and controls a bidirectional DC-DC converter to apply targeted recovery waveforms. The system achieves a bill-of-materials cost under $50 per channel, enabling widespread deployment for battery grading and recovery.