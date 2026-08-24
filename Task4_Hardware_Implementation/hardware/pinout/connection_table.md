# EV Battery Diagnostic System - Hardware Connection Table

## MCU Pinout (ESP32-WROOM-32 or Compatible)

| Function | MCU Pin | Details | Notes |
|----------|---------|---------|-------|
| **Ultrasonic Excitation** | GPIO27 | Drives MOSFET gate (e.g., 2N7002) to generate ultrasonic pulse (10µs width, 10Hz period) | Connected to MOSFET driver circuit |
| **Ultrasonic Trigger** | GPIO25 | Trigger pulse to ultrasonic transmitter (piezo disc) | 10µs pulse initiates measurement |
| **Ultrasonic Echo** | GPIO26 | Echo input from ultrasonic receiver (piezo disc) | Measures time-of-flight |
| **I²C Bus SDA** | GPIO21 | I²C data line for sensors | Default I²C pins, can be remapped |
| **I²C Bus SCL** | GPIO22 | I²C clock line for sensors | Default I²C pins, can be remapped |
| **UART0 TX** | GPIO1 | Transmit to host PC | Connected to USB-to-UART bridge |
| **UART0 RX** | GPIO3 | Receive from host PC | Connected to USB-to-UART bridge |
| **Power Stage Voltage Sense** | ADC1_CH0 (GPIO36) | Voltage divider output from power stage | Requires external voltage divider |
| **Power Stage Current Sense** | ADC1_CH1 (GPIO37) | ACS712 current sensor output | Requires scaling/filtering |
| **Optional LCD SDA** | GPIO18 | I2C data for LCD display | Shared I2C bus possible |
| **Optional LCD SCL** | GPIO19 | I2C clock for LCD display | Shared I2C bus possible |
| **Optional LCD Reset** | GPIO23 | Reset signal for LCD display | Active low reset |
| **Optional LCD Backlight** | GPIO25 (via PWM) | Backlight brightness control | PWM capable pin |

## Sensor Connections

### INA226 Electrical Sensor
- **VCC**: 3.3V
- **GND**: Ground
- **SDA**: Connected to MCU GPIO21 (I²C SDA)
- **SCL**: Connected to MCU GPIO22 (I²C SCL)
- **ALERT**: Not connected (optional interrupt)
- **ADDRESS**: GND (sets address to 0x40)

### TMP102 Temperature Sensor
- **VCC**: 3.3V
- **GND**: Ground
- **SDA**: Connected to MCU GPIO21 (I²C SDA)
- **SCL**: Connected to MCU GPIO22 (I²C SCL)
- **ADDRESS**: GND (sets address to 0x48)

### Ultrasonic Transducer Pair
- **Transmitter (TX)**:
  - One side: Connected to MOSFET drain (via series resistor)
  - Other side: Ground
- **Receiver (RX)**:
  - One side: Connected to MCU GPIO26 (with bias circuit)
  - Other side: Ground
- **Excitation Circuit**:
  - MOSFET (e.g., 2N7002): Gate to GPIO27, Drain to TX+, Source to Ground
  - Flyback diode: Across transducer terminals
  - Series resistor: 22-100Ω between MOSFET and transducer

### Power Stage Monitoring
- **Voltage Sensing**:
  - Voltage divider: Two resistors across power stage output
  - Center tap: To ADC1_CH0 (GPIO36)
  - Ends: To power stage +V and Ground
- **Current Sensing**:
  - ACS712: In series with power stage output
  - OUTPUT: To ADC1_CH1 (GPIO37) via optional RC filter
  - VCC: 3.3V
  - GND: Ground

## Communication Interfaces

### Host PC Connection
- **USB-to-UART Bridge** (e.g., CP2102, CH340):
  - USB: To host PC
  - TX: To MCU GPIO3 (RX)
  - RX: To MCU GPIO1 (TX)
  - VCC: 3.3V
  - GND: Ground
  - DTR/RTS: Optional for auto-reset

### Optional Peripherals
- **I2C LCD Display** (16x2 or 20x4):
  - VCC: 3.3V or 5V (depending on display)
  - GND: Ground
  - SDA: To MCU GPIO18 (shared I2C)
  - SCL: To MCU GPIO19 (shared I2C)

## Power Connections

| Rail | Source | Details |
|------|--------|---------|
| **3.3V** | On-board regulator or USB | Powers MCU, sensors, logic |
| **5V** | USB or external supply | May be needed for some sensors or LCD backlight |
| **Power Stage** | Battery pack or external supply | High voltage/current DC-DC input/output |

## Implementation Notes

1. **I2C Bus**: Can run at 400kHz fast mode for efficient sensor polling
2. **ADC Configuration**: ESP32 ADC2 cannot be used when Wi-Fi is active, so ADC1 channels (GPIO36-39) are recommended
3. **Interrupts**: GPIO26 (ultrasonic echo) can use interrupts for precise timing measurement
4. **PWM Capability**: GPIO25 and GPIO27 are PWM capable for variable control if needed
5. **Pull-up Resistors**: I2C bus requires 4.7kΩ pull-up resistors to 3.3V
6. **ESD Protection**: Consider TVS diodes on exposed connectors (USB, sensor interfaces)
7. **Filtering**: Analog signals may benefit from RC filtering before ADC inputs