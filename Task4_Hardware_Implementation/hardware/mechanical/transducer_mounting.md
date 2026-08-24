# EV Battery Diagnostic System - Ultrasonic Transducer Mounting Guide

## Overview
This document describes the recommended methods for mounting ultrasonic transducer pairs to battery cells for reliable time-of-flight (ToF) measurements. Proper mounting is critical for signal coupling efficiency, measurement repeatability, and long-term stability.

## Transducer Specifications
- **Type**: Piezoelectric disc transducers
- **Frequency**: 40 kHz center frequency
- **Diameter**: Typically 10-20mm (application dependent)
- **Radiation Surface**: Active piezoelectric area (typically 80-90% of physical diameter)
- **Recommended Pair**: Matched transmitter/receiver with similar characteristics

## Mounting Methods

### 1. Direct Coupling with Adhesive (Recommended for Permanent Installation)
**Best for**: Long-term monitoring, production fixtures

#### Materials
- **Coupling Agent**: 
  - Medical ultrasound gel (temporary/reusable)
  - Silicone-based adhesive (RTV silicone, permanent)
  - Epoxy with acoustic matching properties (permanent)
  - Grease-free petroleum jelly (temporary)
- **Surface Preparation**: Isopropyl alcohol wipes, lint-free cloths
- **Fixture**: Optional 3D-printed or machined holder for alignment

#### Procedure
1. **Surface Preparation**:
   - Clean battery cell mounting area with isopropyl alcohol
   - Ensure surface is flat, smooth, and free of contaminants
   - For curved surfaces, consider slight surface preparation to improve contact

2. **Adhesive Application** (for permanent):
   - Apply thin, uniform layer of coupling agent to transducer face
   - Avoid air bubbles - use vacuum degassing if possible
   - Spread to slightly larger than transducer diameter

3. **Transducer Placement**:
   - Place transmitter transducer on one side of cell
   - Place receiver transducer on opposite side, axially aligned
   - Apply gentle pressure to ensure complete contact
   - Remove excess adhesive that squeezes out

4. **Curing** (if applicable):
   - Follow manufacturer's instructions for adhesive curing time
   - Typically 24 hours for full strength at room temperature
   - Avoid mechanical stress during curing

5. **Fixturing** (optional but recommended):
   - Use alignment jig to maintain transducer positioning
   - Add damping material to reduce vibration sensitivity
   - Consider thermal insulation if significant temperature gradients expected

#### Advantages
- Excellent acoustic coupling
- Long-term stability
- Repeatable measurements
- Good for automated production

#### Disadvantages
- Semi-permanent (difficult to remove without residue)
- Requires careful application to avoid bubbles
- Curing time required for permanent adhesives

### 2. Spring-Loaded Fixture (Recommended for Prototyping and Testing)
**Best for**: Lab testing, frequent transducer changes, multiple cell types

#### Materials
- **Fixture Base**: Non-conductive material (FR4, acrylic, wood)
- **Spring Mechanisms**: Small compression springs or pogo pins
- **Transducer Holders**: 3D-printed or machined cups with acoustic backing
- **Alignment Features**: Guide pins or baskets
- **Pressure Application**: Adjustable thumbscrews or lever mechanisms

#### Procedure
1. **Fixture Setup**:
   - Mount transducer holders on adjustable platforms
   - Ensure holders allow slight transducer movement for contact
   - Include acoustic backing material (absorbing foam) behind transducers

2. **Cell Placement**:
   - Position battery cell between transducer holders
   - Use guides to maintain consistent positioning

3. **Pressure Application**:
   - Adjust springs or thumbscrews to apply gentle pressure
   - Target: Enough pressure for good contact without damaging cell
   - Typical force: 0.5-5N depending on cell size and transducer diameter

4. **Coupling Agent Application**:
   - Apply coupling gel to transducer faces before each measurement
   - Reapply as needed during extended testing sessions

#### Advantages
- Reusable and adjustable
- No residue on cells
- Quick transducer changes
- Good for testing multiple cell types/form factors

#### Disadvantages
- Slightly lower coupling efficiency than direct adhesive
- Requires gel reapplication
- Potential for movement during testing if not properly designed
- More complex initial setup

### 3. Clamp-Based Fixture (For Cylindrical Cells)
**Best for**: 18650, 21700, 26650 and similar cylindrical cells

#### Materials
- **Clamp Body**: Non-conductive, chemically resistant material
- **V-Blocks or Saddle**: To hold cylindrical cell in place
- **Transducer Mounts**: Adjustable posts with transducer holders
- **Pressure Mechanism**: Springs, screws, or cam systems
- **Coupling Medium**: Gel or temporary adhesive

#### Procedure
1. **Cell Positioning**:
   - Place cell in V-block or saddle fixture
   - Ensure axis is horizontal and level
   - Stabilize to prevent rolling

2. **Transducer Positioning**:
   - Mount transducers on adjustable posts
   - Position for radial measurement (through cell diameter)
   - Or axial measurement (through cell height, requires end access)

3. **Coupling Application**:
   - Apply coupling gel to transducer faces
   - Bring transducers into contact with cell surface
   - Apply gentle clamping pressure

#### Advantages
- Excellent for cylindrical cell standardization
- Good repeatability for same form factor
- Can be automated for production testing

#### Disadvantages
- Form factor specific
- Requires access to appropriate cell surfaces
- More complex mechanical design

## Coupling Media Selection Guide

| Coupling Agent | Best For | Frequency Range | Thickness | Temp Range | Notes |
|----------------|----------|-----------------|-----------|------------|-------|
| **Ultrasound Gel** | Testing, prototyping | 20kHz - 20MHz | 0.1-0.5mm | 0-40°C | Water-based, dries out over time, requires reapplication |
| **Silicone RTV** | Semi-permanent | 20kHz - 5MHz | 0.05-0.2mm | -50 to +200°C | Provides some vibration isolation, long-term stability |
| **Acoustic Epoxy** | Permanent installation | 20kHz - 10MHz | 0.02-0.1mm | -40 to +150°C | Best acoustic transmission, permanent bond |
| **Petroleum Jelly** | Temporary testing | 20kHz - 10MHz | 0.1-0.5mm | -20 to +40°C | Inexpensive, easy to clean, can migrate over time |
| **Glycerol-Water Mix** | Lab testing | 20kHz - 50MHz | 0.05-0.2mm | 0-80°C | Tunable acoustic impedance, evaporates over time |

## Mounting Position Guidelines

### Cell Selection Criteria
1. **Surface Flatness**: <0.1mm variation over transducer diameter
2. **Surface Cleanliness**: Free of oxides, oils, contaminants
3. **Material Homogeneity**: Avoid welds, seams, or thick coating areas
4. **Accessibility**: Both sides accessible for opposing transducers

### Recommended Mounting Locations
- **Cylindrical Cells** (18650 format):
  - **Radial**: Through diameter (requires cell holder to prevent rotation)
  - **Axial**: Through height (requires access to both ends, may require case modification)
  
- **Pouch Cells**:
  - **Through Thickness**: Preferred method (largest surface area)
  - **Along Width**: If thickness access limited
  
- **Prismatic Cells**:
  - **Through Thickness**: Preferred if dimensions allow
  - **Along Largest Face**: Alternative mounting

### Alignment Requirements
- **Axial Alignment**: Transmitters and receivers should be aligned within 5° of perfect opposition
- **Parallelism**: Transducer faces should be parallel to within 2°
- **Centering**: Active elements should be centered over each other
- **Separation Distance**: Determined by cell thickness plus coupling layer (<1mm ideal)

## Acoustic Considerations

### Coupling Layer Thickness
- **Ideal**: As thin as possible while eliminating air gaps
- **Typical Range**: 0.05-0.5mm depending on coupling agent
- **Effect**: Thicker layers reduce high-frequency response and increase phase shift

### Acoustic Impedance Matching
- **Goal**: Minimize reflection at interfaces
- **Typical Values** (in MRayls):
  - Piezoelectric transducer: ~30-35
  - Coupling gel: ~1.5 (similar to water)
  - Battery casing (Al/Steel): ~16-45
  - Battery internals (liquid/electrode): ~1.5-2.5
- **Strategy**: Use coupling agent to bridge large impedance mismatches

### Signal Attenuation Factors
1. **Transmission Loss**: At each interface (approx. -20 to -50 dB per interface)
2. **Absorption Loss**: In coupling medium and battery materials
3. **Scattering Loss**: From material inhomogeneities, bubbles, particles
4. **Diffraction Loss**: From finite transducer size relative to wavelength

### Wavelength Considerations
- **Speed of Sound in Battery Materials**: ~1500-3000 m/s (dependent on composition, temperature, state of charge)
- **Wavelength at 40kHz**: λ = v/f ≈ 38-75mm
- **Beam Width**: Approximately transducer diameter for near-field measurements
- **Near Field Length**: D²/(4λ) ≈ 3-20mm for typical 10-20mm transducers

## Validation and Testing Procedures

### Initial Setup Verification
1. **Continuity Check**: Verify electrical connections to transducers
2. **Capacitance Measurement**: Measure transducer capacitance (should match spec ±20%)
3. **Resonance Check**: Use impedance analyzer to verify fs and fp

### Coupling Quality Tests
1. **Through-Transmission Test**:
   - Measure signal amplitude with known good transducers
   - Compare to free-space measurement (through air)
   - Typical coupling loss: 3-10 dB with good gel
   
2. **Time-of-Flight Consistency**:
   - Measure ToF 100 times with fixed setup
   - Standard deviation should be <0.1% of mean ToF
   - Indicates stable coupling and alignment

3. **Temperature Cycling Test**:
   - Measure ToF at multiple temperatures (0°C, 25°C, 45°C, 60°C)
   - Should show predictable variation with temperature
   - Hysteresis should be minimal upon return to room temperature

### Long-Term Stability Tests
1. **Drift Monitoring**:
   - Measure ToF every hour for 24 hours
   - Drift should be <0.5% total over period
   
2. **Mechanical Shock/Vibration**:
   - Subject to gentle tapping or vibration
   - Monitor for sudden ToF changes indicating detachment
   
3. **Coupling Agent Degradation**:
   - For gels: Monitor for drying or migration
   - For adhesives: Monitor for delamination or cracking

## Safety and Handling Considerations

### Battery Safety
1. **Voltage Isolation**: Ensure transducers are electrically isolated from battery terminals
2. **Current Limiting**: Use series resistors to limit fault currents
3. **Temperature Monitoring**: Do not exceed battery temperature specifications
4. **Mechanical Stress**: Avoid deforming cells during mounting

### Personnel Safety
1. **Ultrasonic Exposure**: 40kHz is generally safe, but avoid prolonged close exposure to high-intensity beams
2. **Chemical Handling**: Use gloves when handling coupling agents, especially solvents for cleaning
3. **Eye Protection**: When using adhesives or epoxies that may splatter
4. **Ventilation**: Use in well-ventilated area when working with curing adhesives

### Equipment Protection
1. **ESD Precautions**: Use anti-static wrist straps when handling transducers and electronics
2. **Moisture Protection**: Seal connections if operating in humid environments
3. **Strain Relief**: Provide strain relief on transducer cables to prevent connection damage
4. **Cable Routing**: Keep away from high-voltage or high-current conductors to avoid interference

## Troubleshooting Guide

### Symptom: Low Signal Amplitude
**Possible Causes**:
- Poor coupling (air bubbles, insufficient pressure)
- Incorrect transducer orientation (not opposed)
- Damaged transducers
- Excessive coupling layer thickness
- Wrong frequency (transducers damaged or wrong spec)

**Solutions**:
- Reapply coupling gel, ensure bubble-free contact
- Verify transducer alignment with visual inspection or laser guide
- Test transducers with known good pair
- Reduce coupling layer thickness
- Verify driving frequency matches transducer resonance

### Symptom: Noisy or Erratic Measurements
**Possible Causes**:
- Loose mechanical coupling
- Electromagnetic interference (EMI)
- Temperature fluctuations
- Battery movement or swelling
- Acoustic reflections from nearby objects

**Solutions**:
- Increase mounting pressure or improve fixturing
- Shield cables, use twisted pairs, increase distance from noise sources
- Allow temperature stabilization, monitor and compensate
- Secure battery in fixture, monitor for physical changes
- Increase distance from reflecting surfaces, use absorbing materials

### Symptom: Systematic Offset in Measurements
**Possible Causes**:
- Temperature-dependent speed of sound changes
- Coupling agent temperature dependence
- Battery swelling or mechanical changes
- Drift in electronic timing circuits

**Solutions**:
- Implement temperature compensation based on measured battery temp
- Characterize coupling agent temp coefficient and compensate
- Monitor battery dimensions and account for swelling
- Calibrate system timing against known reference

## Maintenance Procedures

### Regular Inspection (Weekly for Active Systems)
1. Visual inspection of transducer-cell interface
2. Check for coupling agent degradation (drying, cracking, migration)
3. Verify mechanical fasteners are secure
4. Clean electrical contacts if needed
5. Verify cable integrity and strain relief

### Coupling Agent Renewal
- **Gels**: Reapply before each test session or daily for continuous monitoring
- **Semi-permanent adhesives**: Inspect monthly, reapply as needed
- **Permanent adhesives**: Designed for lifetime of installation, inspect quarterly

### Calibration Schedule
1. **Initial Calibration**: Upon system setup
2. **Periodic Verification**: Monthly for critical applications
3. **After Maintenance**: Whenever transducers are disturbed or coupling renewed
4. **Environmental Changes**: Significant temperature or humidity changes

## Documentation and Traceability

### Mounting Records
For each battery cell tested, record:
1. Date and time of mounting
2. Transducer pair ID/slot number
3. Coupling agent type and batch/lot number
4. Applied pressure or torque values (if measurable)
5. Initial coupling verification measurements
6. Operator ID
7. Any observations or anomalies

### System Validation
Maintain records of:
1. Transducer calibration certificates
2. Coupling agent material safety data sheets (MSDS)
3. Fixture design drawings and specifications
4. Validation test results and procedures
5. Change control documentation for any modifications

## References and Standards
1. **IEC 60512-2**: Electromechanical components for electronic connectors - Basic testing procedures and measuring methods
2. **ASTM E1065**: Standard Guide for Evaluating Characteristics of Coupling Agents
3. **ISO 16750-3**: Road vehicles - Environmental conditions and testing for electrical and electronic equipment - Part 3: Mechanical loads
4. **Manufacturer datasheets**: Specific transducer and coupling agent recommendations
5. **Application notes**: From transducer manufacturers on medical and industrial bonding techniques

## Appendix A: Sample Mounting Fixture Sketch

```
Top View (for rectangular/pouch cells):

    [Transmitter Holder]
          ▼
    ┌─────────────┐
    │  Battery    │ ← Cell positioned here
    │    Cell     │
    └─────────────┘
          ▲
    [Receiver Holder]

Side View (showing coupling layers):

    [Backing Material]
          ▼
    ┌─────────────┐    ← Transducer holder/face
    │  Transmitter│
    │   (TX)      │
    └─────────────┘
          ▼
    ┌─────────────┐    ← Coupling layer (gel/adhesive)
    │  Coupling   │
    │   Agent     │
    └─────────────┘
          ▼
    ┌─────────────┐    ← Battery casing/wall
    │  Battery    │
    │   Wall      │
    └─────────────┘
          ▼
    ┌─────────────┐    ← Battery internal medium
    │  Battery    │
    │  Internal   │
    └─────────────┘
          ▲
    ┌─────────────┐    ← Coupling layer (gel/adhesive)
    │  Coupling   │
    │   Agent     │
    └─────────────┘
          ▼
    ┌─────────────┐    ← Transducer holder/face
    │  Receiver   │
    │   (RX)      │
    └─────────────┘
          ▼
    [Backing Material]
```

## Appendix B: Coupling Agent Application Tips

### For Gels and Liquids:
1. Use syringe or applicator for precise placement
2. Apply to center of transducer face first
3. Gently spread outward to avoid trapping air
4. Use plastic spreader or gloved finger for even distribution
5. Excess should form small bead around edges - indicates complete coverage

### For Adhesives and Epoxys:
1. Mix thoroughly according to manufacturer instructions
2. Apply within pot life limits
3. Use spatula or notch spreader for controlled thickness
4. Consider using spacing beads or shims for uniform gap
5. Apply weight or clamps during curing if recommended
6. Clean excess immediately before curing

### Final Check:
- Hold transducers up to light - should see slight meniscus indicating complete contact
- Gentle twist should feel slightly resistant, not loose or grating
- No visible air bubbles at interface