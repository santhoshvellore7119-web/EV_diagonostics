# EV Battery Diagnostic System - Hardware Connection Table

## MCU Pinout (ESP32-S3 / STM32F407 Compatible)

| Function | MCU Pin | Details | Notes |
|----------|---------|---------|-------|
| **Ultrasonic Burst Trigger** | GPIO25 | Drives `TC4420` 6A gate driver to excite 2.0 MHz PZT TX disc (`START` to `TDC7200`) | 2 µs burst (4 cycles @ 2.0 MHz) |
| **Ultrasonic Comparator STOP** | GPIO26 | `TLV3501` comparator rising-edge output (`STOP` to `TDC7200` + MCU ISR) | First-arrival hardware trigger |
| **TDC7200 SPI CS** | GPIO5 | Chip Select for `TDC7200` 55ps Time-to-Digital Converter | Active LOW |
| **TDC7200 Enable** | GPIO17 | Enable pin for `TDC7200` | Active HIGH |
| **TDC7200 INTB** | GPIO16 | Measurement-complete interrupt from `TDC7200` | Active LOW, internal pull-up |
| **SPI Bus (SCK/MISO/MOSI)** | GPIO18 / 19 / 23 | Hardware SPI bus for `TDC7200` 24-bit ToF register readout | 10 MHz SPI clock |
| **AD8307 Envelope ADC** | ADC1_CH3 (GPIO39) | Analog envelope output (`25 mV/dB`) from `AD8307` logarithmic amplifier | Captures peak amplitude & gassing coda |
| **TLV3501 Phase Polarity** | GPIO34 | Digital polarity sample of first arrival wave | Detects Li-plating phase inversion |
| **Kelvin Pulse Load Gate** | GPIO14 | Drives `IRLZ44N` MOSFET switching $1\,\Omega$, $25\text{ W}$ diagnostic load | Measures $\Delta V_{\text{cell}} = V_{\text{rest}} - V_{\text{load}}$ |
| **I²C Bus SDA** | GPIO21 | I²C data line for `INA226` (`0x40`) and dual `TMP102/TMP117` (`0x48`, `0x49`) | 400 kHz Fast Mode |
| **I²C Bus SCL** | GPIO22 | I²C clock line for `INA226` and dual `TMP102/TMP117` | 4.7 kΩ pull-ups to 3.3V |
| **UART0 TX** | GPIO1 | Transmit diagnostic & Edge ML packets to host PC | `115200 bps` via `CP2102N` |
| **UART0 RX** | GPIO3 | Receive commands from host PC | Connected to USB-to-UART bridge |
| **Power Stage Voltage Sense** | ADC1_CH0 (GPIO36) | Voltage divider output from ZVS active balancer bus | Requires precision divider |
| **Power Stage Current Sense** | ADC1_CH1 (GPIO37) | Balancer inductor current sense output | RC anti-aliasing filter |

## Sensor Connections

### INA226 4-Wire Kelvin Electrical Sensor & Pulse Load
- **VCC / GND**: 3.3V / Ground
- **SDA / SCL**: Connected to MCU GPIO21 / GPIO22 (`ADDRESS` = GND $\rightarrow$ `0x40`)
- **IN+ / IN-**: 4-wire Kelvin sense leads across `CSS2H-2512R-L010F` ($10\text{ m}\Omega$, $0.1\%$) shunt resistor
- **VBUS**: Connected directly to Cell Positive Sense terminal (4-wire Kelvin sense)
- **Diagnostic Pulse Load**: `IRLZ44N` gate driven by `GPIO14` switching a $1\,\Omega$, $25\text{ W}$ power resistor across the cell to measure true internal voltage sag $\Delta V_{\text{cell}} = V_{\text{rest}} - V_{\text{load}}$

### Dual Differential TMP102 / TMP117 Temperature Sensors
- **Sensor 1 (Cell Surface Contact — `0x48`)**:
  - `ADD0` tied to `GND`, Kapton-taped with thermal paste to the pouch cell center/tab
- **Sensor 2 (Ambient Reference — `0x49`)**:
  - `ADD0` tied to `3.3V`, mounted 30 mm away on thermally isolated PCB standoff
- **Differential Compensation**: Firmware computes $\Delta T = \max(0, T_{\text{surface}} - T_{\text{ambient}})$ and references to $25.0^\circ\text{C}$

### 2.0 MHz Ultrasonic Pitch-Catch AFE (`TDC7200` + `AD8065` + `AD8307` + `TLV3501`)
- **Transmitter (TX — 2.0 MHz PZT-5A Disc)**:
  - Driven by `TC4420` 6A MOSFET driver + `FDMS86180` switches from `GPIO25` (also routed to `TDC7200 START`)
- **Receiver (RX — 2.0 MHz PZT-5A Disc)**:
  - Amplified by `AD8065` Low-Noise JFET Op-Amp ($+34\text{ dB}$ bandpass stage)
  - Branch A (Timing & Phase): `TLV3501` 4.5 ns comparator $\rightarrow$ `TDC7200 STOP` + `GPIO26` / `GPIO34`
  - Branch B (Envelope & Reverberation Coda): `AD8307` 92 dB Logarithmic Envelope Detector $\rightarrow$ `ADC1_CH3 (GPIO39)`

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