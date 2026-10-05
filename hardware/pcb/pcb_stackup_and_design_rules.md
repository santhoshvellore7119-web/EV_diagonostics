# Multi-Modal EV Battery Diagnostic & Active Rebalancer
## 4-Layer PCB Stackup and High-Frequency Hardware Design Rules

### 1. Board Specifications & Substrate Stackup

This design uses a standard 4-layer FR-4 board with **ENIG (Electroless Nickel Immersion Gold)** surface finish, optimized for low-noise high-frequency ultrasonic analog front-end (AFE) signals and 100 kHz synchronous bidirectional active cell-rebalancing power stages.

| Layer | Layer Name | Copper Thickness | Dielectric Thickness | Material / Description |
|---|---|---|---|---|
| **L1 (Top)** | Component / RF Microstrip & Power Signals | $1.0\text{ oz } (35\,\mu\text{m})$ | $0.20\,\text{mm}$ (7.87 mil) | Prepreg (FR-4, $\epsilon_r = 4.4$, $\tan\delta = 0.02$) |
| **L2 (Inner 1)**| Solid Analog & Digital Ground Plane (GND) | $1.0\text{ oz } (35\,\mu\text{m})$ | $1.00\,\text{mm}$ (39.37 mil) | Core (FR-4, $\epsilon_r = 4.5$) |
| **L3 (Inner 2)**| Power Rails ($+5\text{V}$, $+3.3\text{V}$, $+12\text{V}_\text{PULSE}$) | $1.0\text{ oz } (35\,\mu\text{m})$ | $0.20\,\text{mm}$ (7.87 mil) | Prepreg (FR-4, $\epsilon_r = 4.4$) |
| **L4 (Bottom)** | High-Current Balancing Loops & Low-Speed Signals | $1.0\text{ oz } (35\,\mu\text{m})$ | — | Solder Mask + ENIG |

- **Total Finished Thickness**: $1.60\,\text{mm} \pm 10\%$
- **Minimum Trace / Clearance**: $0.15\,\text{mm} / 0.15\,\text{mm}$ (6 mil / 6 mil)
- **Minimum Via Drill / Annular Ring**: $0.30\,\text{mm} \text{ drill} / 0.15\,\text{mm} \text{ ring}$ ($0.60\,\text{mm}$ pad)
- **High-Current Via Sizing**: $0.50\,\text{mm} \text{ drill} / 1.00\,\text{mm} \text{ pad}$ with thermal relief matrix

---

### 2. High-Frequency Ultrasonic Transmission Line Design ($50\,\Omega$ Microstrip)

The $5\text{--}10\,\text{MHz}$ ultrasonic transducer echoes exhibit nanosecond rise-times and millivolt-level signal amplitudes, requiring controlled characteristic impedance ($Z_0 = 50\,\Omega \pm 5\%$) between the piezo transducer SMA connector, the TX high-voltage pulse clamp, and the **AD8065** low-noise operational amplifier.

#### Microstrip Calculation Formula:
$$Z_0 = \frac{87}{\sqrt{\epsilon_r + 1.41}} \ln\left( \frac{5.98 \cdot h}{0.8 \cdot w + t} \right)$$

For $h = 0.20\,\text{mm}$, $t = 0.035\,\text{mm}$, and $\epsilon_r = 4.4$:
- **Calculated Trace Width ($w$)**: $0.36\,\text{mm}$ (14.2 mil) $\rightarrow Z_0 = 50.2\,\Omega$
- **Ground Return Reference**: Continuous, uninterrupted solid copper ground on **Layer 2** directly beneath all ultrasonic analog traces. No split planes or routed traces beneath the AFE signal path.
- **Guard Ring & Coplanar Shielding**: Analog AFE inputs (AD8065 pin 3 and TLV3501 pin 2) are surrounded by a top-layer grounded copper pour with ground stitching vias placed every $3.0\,\text{mm}$ ($\le \lambda/20$ at 100 MHz).

---

### 3. Star-Point Kelvin Grounding & Noise Partitioning

To prevent $100\,\text{kHz} / 2.5\,\text{A}$ active rebalancing switching harmonics and body-diode reverse recovery spikes from polluting picosecond-level ultrasonic ToF measurements:

1. **Physical Domain Split**:
   - **Zone A (Quiet Analog - AFE & TDC7200)**: Houses TDC7200, AD8065, TLV3501, and low-drift 16 MHz reference oscillator.
   - **Zone B (Digital & MCU)**: Houses ESP32-S3 microcontroller, USB/UART isolators, SPI/I2C buses, and status LEDs.
   - **Zone C (Power Switching & Active Rebalancer)**: Houses FDMS86180 MOSFETs, TPS28225 gate drivers, SER2918H inductor, INA226 current shunt, and optical solid-state relays.
2. **Kelvin Ground Tie Point**:
   - Analog Ground (`AGND`) and Power Ground (`PGND`) are strictly isolated on Layer 1 and Layer 4.
   - They converge at a single star point on Layer 2 immediately adjacent to the bulk input decoupling capacitor matrix via a zero-ohm resistor footprint ($R_\text{STAR} = 0\,\Omega$, 0805) or net-tie copper bridge.
3. **Current Shunt Sensing Routing**:
   - INA226 differential sensing lines (`IN+`, `IN-`) from the $10\,\text{m}\Omega$ shunt resistor ($R_\text{SENSE}$) are routed as a closely spaced differential pair ($0.20\,\text{mm}$ width, $0.15\,\text{mm}$ gap) directly to the inner Kelvin pads of the 4-terminal shunt resistor package.

---

### 4. Thermal Management & High-Current Active Balancing Rules

The bidirectional synchronous buck-boost stage transfers up to $2.5\,\text{A}$ RMS continuous current between series cells.

1. **MOSFET Thermal Dissipation (FDMS86180, Power56 Package)**:
   - The exposed drain pad ($Q_1, Q_2$) is connected to an array of $3 \times 3$ thermal vias ($0.3\,\text{mm}$ drill, $0.15\,\text{mm}$ wall copper plating) directly sinking heat into Layer 4 copper flood.
   - Copper flood area $\ge 250\,\text{mm}^2$ per power FET ensures maximum junction temperature $T_j < 65^\circ\text{C}$ under worst-case continuous 2.5 A shuttling.
2. **Inductor Placement (Coilcraft SER2918H-103KL)**:
   - Shielded ferrite construction minimizes magnetic stray flux coupling into adjacent ADC or SPI traces.
   - Power switching node (SW) copper area is kept strictly minimal in area ($\le 15\,\text{mm}^2$) to reduce capacitive $dV/dt$ electric field emissions.
3. **Gate Driver Loop Inductance (TPS28225 / TC4420)**:
   - High-side bootstrap loop ($C_\text{BOOT} \rightarrow \text{BOOT} \rightarrow \text{HDRV} \rightarrow Q_1\text{-Gate} \rightarrow \text{SW}$) and low-side loop ($V_\text{DD} \rightarrow \text{LDRV} \rightarrow Q_2\text{-Gate} \rightarrow \text{PGND}$) are routed on Layer 1 with loop area $< 25\,\text{mm}^2$ to prevent gate ringing and parasitic turn-on.

---

### 5. Bill of Materials (BOM) Alignment Summary

| Subsystem Component | Reference Designator | Package / Footprint | Function in Schematic & PCB |
|---|---|---|---|
| **Microcontroller** | `U1` (ESP32-S3-WROOM-1) | Module SMD | FreeRTOS dual-core supervisor, ZVS PWM generator, edge inference |
| **Time-to-Digital Converter** | `U2` (TDC7200PWR) | TSSOP-14 | $55\,\text{ps}$ ultrasonic ToF stop-time counter |
| **High-Speed Comparator** | `U3` (TLV3501AIDBVR) | SOT-23-6 | $4.5\,\text{ns}$ ultrasonic zero-crossing detector |
| **Low-Noise Op-Amp** | `U4` (AD8065ARTZ) | SOT-23-5 | $145\,\text{MHz}$ FET-input ultrasonic echo preamplifier |
| **High-Side Current/Power** | `U5` (INA226AIDGSR) | VSSOP-10 | $16\text{-bit}$ $I/V/P$ monitor with alert interrupt |
| **Synchronous MOSFETs** | `Q1, Q2` (FDMS86180) | Power56 (8-PQFN) | $3.2\,\text{m}\Omega$ $R_\text{DS(on)}$ ZVS bidirectional switches |
| **MOSFET Gate Driver** | `U6` (TPS28225DRBR) | SON-8 ($3\times3\text{mm}$) | High-speed synchronous half-bridge driver |
| **Power Inductor** | `L1` (SER2918H-103KL) | SMD $28\times28\text{mm}$ | $10\,\mu\text{H}$, $3.1\,\text{m}\Omega$ DCR, $25\,\text{A}$ saturation |
| **Cell Multiplexer Relay** | `K1` (G3VM-61A1) | DIP-4 / SMD | Optical solid-state relay for 4S cell channel selection |

**Total PCB System BOM Cost**: **$38.75 USD** (manufacturable in 100-unit pilot runs).
