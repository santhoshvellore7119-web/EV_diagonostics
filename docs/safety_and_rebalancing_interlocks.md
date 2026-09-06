# Multi-Layer Safety Architecture & Rebalancing Interlocks

## 1. Safety Engineering Philosophy & Hazards Classification
Active rebalancing and in-situ electro-thermal recovery of lithium-ion cells entails delivering controlled current pulses and energy transfer between cells. In degraded cells (particularly cells exhibiting internal dendritic growth, localized lithium plating, or active material breakdown), unconstrained charging or power injection presents severe safety hazards:
- **Thermal Runaway Risk**: High-rate charging of an internally shorted or plated cell can trigger separator collapse and catastrophic exothermic propagation.
- **Gas Evolution & Case Rupture**: Over-potentials in degraded electrolyte can accelerate gas generation (CO2, H2, hydrocarbons).
- **False-Positive Actuation Hazard**: Acting on low-confidence or high-uncertainty model inferences could execute aggressive deplating pulses on a healthy or critically damaged cell.

To establish absolute fail-safe operation, this system implements a **Four-Tier Defense-in-Depth Safety Architecture**.

`
+========================================================================+
| LAYER 3: CLOUD & FLEET SUPERVISION (1 - 10 Hz Telemetry Sync)          |
| - Fleet-wide outlier anomaly detection                                 |
| - Remote E-Stop override & fleet lockdown commands                     |
+========================================================================+
                                   |
                                   v
+========================================================================+
| LAYER 2: ML DECISION ENGINE & UNCERTAINTY INTERLOCKS (10 Hz Cycle)     |
| - Epistemic uncertainty gate: sigma_SOH <= 3.0%                        |
| - Classification confidence gate: P(mode) >= 0.85                      |
| - Degradation mode lockouts: Immediate isolation on INTERNAL_SHORT     |
| - Thermal gradient interlock: Delta_T <= 3.0 deg C                     |
+========================================================================+
                                   |
                                   v
+========================================================================+
| LAYER 1: FIRMWARE RTOS DETERMINISTIC MONITORING (1 kHz Loop)           |
| - Independent hardware watchdog timer (100 ms timeout)                 |
| - Cell voltage bounds checking: 2.80 V <= V_cell <= 4.25 V             |
| - Delta-V imbalance threshold: |V_cell - V_avg| <= 350 mV              |
| - Current limit clamping: I_balance <= 2.0 A                           |
+========================================================================+
                                   |
                                   v
+========================================================================+
| LAYER 0: ANALOG HARDWARE INTERLOCKS & GALVANIC ISOLATION               |
| - Dual-switch optical disconnect relay (AQY282EH)                      |
| - Hardwired analog window comparator (Over-V / Under-V / Over-T)       |
| - Passive pull-down gate resistors: Default state = HIGH IMPEDANCE (0A)|
| - Resettable PTC / Thermal Fuse on each cell balancing tap             |
+========================================================================+
`

---

## 2. Safety Interlock Thresholds & Gating Matrix

| Parameter / Condition | Safe Operational Bound | Warning Threshold | Emergency Lockout Action |
|---|---|---|---|
| **Cell Terminal Voltage (V_cell)** | 3.00 V - 4.20 V | < 2.90 V or > 4.22 V | Hardware Contactor Open (I = 0 A) if V < 2.80 V or V > 4.25 V |
| **Max Cell Temperature (T_max)** | < 45.0 deg C | 45.0 - 55.0 deg C | Disable Rebalancing (I = 0 A) if T > 55.0 deg C |
| **Inter-Cell Thermal Gradient (Delta T)** | Delta T < 1.5 deg C | 1.5 deg C <= Delta T <= 3.0 deg C | Hard Lockout if Delta T > 3.0 deg C |
| **ML Model SOH Uncertainty (sigma_SOH)** | sigma_SOH < 2.0% | 2.0% <= sigma_SOH <= 3.0% | Inhibit Active Actions if sigma_SOH > 3.0% |
| **Classification Confidence (P_mode)** | P >= 0.85 | 0.65 <= P < 0.85 | Revert to Passive Monitoring if P < 0.85 |
| **Classification Entropy (H(P))** | H(P) < 0.80 nats | 0.80 <= H(P) <= 1.20 | Revert to Passive Monitoring if H(P) > 1.20 |

---

## 3. Degradation Mode Specific Action & Isolation Rules

### 3.1 Mode 0: HEALTHY
- **Action**: NONE / Passive balancing only if |V_cell - V_pack_avg| > 30 mV.
- **Permitted Current**: Normal operating range.

### 3.2 Mode 1: LI_PLATING
- **Action**: PULSE_DEPLATING (Restricted parameter envelope).
- **Safety Interlock**:
  - Pulse duration tau <= 15 ms.
  - Current limited to 1.0 A.
  - Strictly forbidden if Delta T > 2.0 deg C or SOH < 60%.
  - Verification sensing must run after every 100 pulses.

### 3.3 Mode 2: ACTIVE_MATERIAL_LOSS
- **Action**: EQUILIBRATION (Low-rate CCCV relaxation).
- **Safety Interlock**:
  - Current limited to 0.5 A (< 0.15C).
  - Target voltage strictly capped at 3.80 V.

### 3.4 Mode 3: ELECTROLYTE_DECOMPOSITION
- **Action**: EQUILIBRATION with reduced upper voltage cut-off (3.70 V).
- **Safety Interlock**:
  - Fast-charging completely disabled for this cell channel.

### 3.5 Mode 4: GAS_GENERATION
- **Action**: GAS_RECOMBINATION (Low-voltage holding).
- **Safety Interlock**:
  - Temperature monitoring at 50 Hz; if rate-of-rise dT/dt > 0.1 deg C/s, abort immediately.

### 3.6 Mode 5: INTERNAL_SHORT
- **Action**: SAFETY_LOCKOUT_ISOLATED.
- **Safety Interlock**:
  - **HARD EMERGENCY ISOLATION**: Both high-side and low-side power MOSFETs disabled.
  - Optical disconnect relay de-energized.
  - Cell flagged as critical in CAN bus message 0x18FF50DE.
  - Auditory/Visual fault alarm asserted on dashboard and vehicle cluster.
  - Power stage locked out permanently until manual service inspection.

---

## 4. Verification & Validation Protocol
All safety interlocks are validated through deterministic test suites (tests/test_decision_engine.py, tests/test_safety_interlocks.py) verifying:
1. **Zero-Current on Fault**: Verification that rebalancing_powerStage_targetCurrent == 0.0 upon any fault trigger.
2. **Watchdog Dropout Response**: Verification of < 5 ms transition to SAFETY_LOCKOUT_ISOLATED.
3. **Uncertainty Rejection**: Verification that high-uncertainty outputs (sigma > 3.0%) fail-safe to passive IDLE state.
