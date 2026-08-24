# EV Battery Diagnostic System - Timing Diagram

## System Timing Overview
All timing is derived from a central hardware timer operating at 10Hz (100ms period). The excitation pulse serves as the synchronization point for all sensor measurements and processing.

## Fundamental Timing Parameters
- **Excitation Period**: 100 ms (10 Hz frequency)
- **Excitation Pulse Width**: 10 µs (ultrasonic trigger and MOSFET drive)
- **DAQ Sampling Rate**: 200 kHz (5 µs per sample)
- **Samples per Cycle**: 20,000 samples (100 ms @ 200 kHz)

## Detailed Timing Sequence (per 100ms cycle)

### Time Reference: T0 = Start of Excitation Pulse

| Time Offset | Duration | Event | Description |
|-------------|----------|-------|-------------|
| **T0** | 10 µs | **Excitation Pulse Start** | - GPIO27 HIGH (MOSFET gate drive)<br>- GPIO25 HIGH (Ultrasonic trigger)<br>- Begins ultrasonic transmission |
| **T0 + 10µs** | - | **Excitation Pulse End** | - GPIO27 LOW<br>- GPIO25 LOW<br>- Ultrasonic transmission complete |
| **T0 + 10µs** | 0-100µs | **Sensor Settling Time** | - Allow transducer ringing to decay<br>- Wait for stable measurements |
| **T0 + 100µs** | ~100µs | **Electrical Sensor Sample** | - I2C transaction with INA226<br>- Read: Bus voltage, shunt voltage, current, power<br>- Typical duration: 80-120µs @ 400kHz I2C |
| **T0 + 200µs** | ~100µs | **Thermal Sensor Sample** | - I2C transaction with TMP102<br>- Read: Temperature and (if configured) temp gradient<br>- Typical duration: 80-120µs @ 400kHz I2C |
| **T0 + 10µs** | ~3ms max | **Ultrasonic Measurement Window** | - GPIO26 input monitored for echo<br>- Timeout set based on max expected range<br>- For 50cm range in medium (SoS~1500m/s): ~667µs round trip<br>- For 1m range: ~1.33ms round trip<br>- Actual measurement: Time between trigger pulse and echo reception |
| **T0 + 1ms** | Variable | **Data Processing** | - Firmware processes sensor readings<br>- Calculates derived values<br>- Prepares data packet for transmission |
| **T0 + 5ms** | Variable | **Host Communication** | - Transmit JSON packet via UART<br>- Typical packet: ~100-200 bytes<br>- @ 115200 baud: ~8-15ms transmission time |
| **T0 + 15ms** | ~85ms | **Idle / Low Power** | - MCU can enter low-power mode<br>- Prepare for next cycle<br>- Background tasks (if any) |

## Recovery Action Timing (When Activated)

### After Detection Phase (Typically T0 + 20ms)
When the decision engine determines a recovery action is needed:

| Action Type | Timing Characteristics | Details |
|-------------|------------------------|---------|
| **Pulse Deplating** | Periodic pulses | - Discharge pulses: 2-5A, 10-100ms width<br>- Pulse interval: 100ms-5s configurable<br>- Duration: Seconds to minutes |
| **Equilibration** | Constant current | - Charge/discharge: 0.1-2A typical<br>- Duration: Minutes to hours<br>- PID regulation to target voltage/current |
| **Gas Recombination** | Constant voltage | - Voltage hold: 3.8-4.0V typical<br>- Duration: tens of minutes to hours<br>- Current taper as cell charges |
| **Short Isolation** | Open circuit | - Duration: Seconds to minutes<br>- Monitor voltage recovery |
| **Balancing** | PID control | - Continuous adjustment<br>- Duration: Until balance achieved<br>- Typically minutes |

## Synchronization Notes
1. **Common Time Base**: All timing derived from single hardware timer
2. **Deterministic Latency**: Fixed delays between trigger and sampling
3. **Buffering**: Sensor readings buffered until processing time
4. **Communication Asynchronicity**: Host comms may extend beyond cycle but doesn't affect sensing timing
5. **Recovery Actions**: Operate on longer timescales (seconds to hours) independent of 10Hz sensing cycle

## Timing Diagram Visual Description

If creating a visual timing diagram, show:

### Top Row: Control Signals
- **Excitation Pulse (GPIO27)**: 10µs high every 100ms
- **Ultrasonic Trigger (GPIO25)**: 10µs high every 100ms (aligned with excitation)
- **Ultrasonic Echo Window (GPIO26)**: Variable width pulse starting 10µs after trigger

### Middle Row: Sensor Activities
- **I2C Electrical**: ~100µs burst starting ~100µs after T0
- **I2C Thermal**: ~100µs burst starting ~200µs after T0
- **Ultrasonic Measurement**: Variable period starting ~10µs after T0

### Bottom Row: System Activities
- **Data Processing**: Block starting ~1ms after T0
- **Host Comm**: Block starting ~5ms after T0
- **Idle/Low Power**: Remainder of cycle

## Jitter and Variability Considerations
- **Fixed Jitter**: <1µs from timer precision
- **Variable Jitter**: 
  - I2C bus arbitration (if multiple masters)
  - Ultrasonic echo timing (depends on medium properties)
  - Host UART transmission (depends on baud rate and packet size)
- **Worst Case Latency**: Still well within 100ms cycle (<10ms typical processing + comms)

## Applications of This Timing
1. **Oscilloscope Triggering**: Use excitation pulse as trigger to capture all sensor activities
2. **Logic Analyzer Setup**: Configure to capture 100ms window showing all relevant signals
3. **Firmware Validation**: Ensure ISR and task timing meets constraints
4. **System Optimization**: Identify opportunities to reduce processing time or increase sampling rate