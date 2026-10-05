# EV Battery Hardware Implementation Guide Generator
import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont('Helvetica', 8)
        self.setFillColor(colors.HexColor('#64748b'))
        
        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 11 * 72 - 36, 'EV Battery Multi-Modal Diagnostic & Active Rebalancing System')
            self.drawRightString(8.5 * 72 - 54, 11 * 72 - 36, 'Hardware Implementation Guide')
            self.setStrokeColor(colors.HexColor('#cbd5e1'))
            self.setLineWidth(0.5)
            self.line(54, 11 * 72 - 42, 8.5 * 72 - 54, 11 * 72 - 42)

        # Footer
        page_str = f'Page {self._pageNumber} of {page_count}'
        self.drawRightString(8.5 * 72 - 54, 36, page_str)
        self.drawString(54, 36, 'CONFIDENTIAL — MULTI-MODAL HARDWARE SPECIFICATION & BUILD GUIDE')
        self.setStrokeColor(colors.HexColor('#cbd5e1'))
        self.setLineWidth(0.5)
        self.line(54, 46, 8.5 * 72 - 54, 46)
        self.restoreState()

def build_pdf():
    output_path = os.path.join(os.path.dirname(__file__), 'Hardware_Implementation_Guide.pdf')
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#0284c7'),
        spaceAfter=12
    )
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#334155'),
        spaceAfter=5
    )
    callout_style = ParagraphStyle(
        'Callout_Text',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#0369a1')
    )
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#1e293b')
    )
    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )
    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.2,
        leading=9.2,
        textColor=colors.HexColor('#0f172a')
    )

    story = []

    # Title Banner
    story.append(Paragraph('Low-Cost Multi-Modal Battery Diagnostic & Active Rebalancing System', title_style))
    story.append(Paragraph('Production Hardware Implementation, ZVS Active Balancing & Calibration Guide (BOM &lt; $45)', subtitle_style))
    story.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor('#0284c7'), spaceAfter=10))

    # Callout Box: Overview
    callout_data = [[
        Paragraph('<b>SYSTEM HIGHLIGHTS:</b> Picosecond acoustic Time-of-Flight (55 ps resolution with TDC7200), 16-bit Kelvin impedance sensing with dynamic ESR auto-nulling (INA226), multi-point thermal gradient interlocks, and Zero-Voltage Switching (ZVS) quasi-resonant active cell rebalancing (&gt;92% efficiency, peak 98.4%).', callout_style)
    ]]
    callout_table = Table(callout_data, colWidths=[504])
    callout_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0f9ff')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#bae6fd')),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(callout_table)
    story.append(Spacer(1, 8))

    # Chapter 1
    story.append(Paragraph('1. System Architecture & Measurement Principles', h1_style))
    story.append(Paragraph('The diagnostic system interrogates battery cells using three physically complementary sensing modalities synchronized to an adaptive current excitation pulse:', body_style))
    story.append(Paragraph('• <b>Ultrasonic Acoustic Sensing:</b> 1.0 MHz longitudinal compression waves propagate through the cell jelly-roll. Density and elasticity changes alter acoustic speed of sound (SOS) and attenuation. Gas generation drastically attenuates signal via acoustic mismatch (Z_gas &lt;&lt; Z_solid), while lithium plating creates density shifts with 180 deg phase inversion.', body_style))
    story.append(Paragraph('• <b>Electrical Impedance Sensing:</b> High-frequency current pulses measure ohmic resistance (R0) and polarization impedance (R1, C1) via a precision 4-wire Kelvin shunt and 16-bit Sigma-Delta ADC with dynamic contact ESR auto-nulling.', body_style))
    story.append(Paragraph('• <b>Thermal Dynamics:</b> Surface thermistors and non-contact infrared sensors capture core-to-surface temperature gradients (dT/dt) to identify localized Joule heating and internal micro-shorts.', body_style))
    story.append(Spacer(1, 6))

    # Chapter 2: BOM
    story.append(Paragraph('2. Comprehensive Bill of Materials (BOM)', h1_style))
    story.append(Paragraph('The complete hardware platform is designed for mass manufacturability with total unit cost below $45:', body_style))

    bom_data = [
        [Paragraph('Item', table_header), Paragraph('Category', table_header), Paragraph('Part Number / MPN', table_header), Paragraph('Key Specs', table_header), Paragraph('Unit ($)', table_header), Paragraph('Qty', table_header), Paragraph('Total ($)', table_header)],
        [Paragraph('1', table_cell), Paragraph('MCU', table_cell), Paragraph('ESP32-S3-WROOM-1', table_cell), Paragraph('Dual-core LX7 240MHz, 8MB Flash', table_cell), Paragraph('$3.20', table_cell), Paragraph('1', table_cell), Paragraph('$3.20', table_cell)],
        [Paragraph('2', table_cell), Paragraph('Ultrasonic TDC', table_cell), Paragraph('TDC7200PWR (TI)', table_cell), Paragraph('55 ps RMS resolution, SPI', table_cell), Paragraph('$2.45', table_cell), Paragraph('1', table_cell), Paragraph('$2.45', table_cell)],
        [Paragraph('3', table_cell), Paragraph('Ultrasonic LNA', table_cell), Paragraph('AD8065ARTZ (ADI)', table_cell), Paragraph('145 MHz FastFET OpAmp, low noise', table_cell), Paragraph('$1.85', table_cell), Paragraph('1', table_cell), Paragraph('$1.85', table_cell)],
        [Paragraph('4', table_cell), Paragraph('Comparator', table_cell), Paragraph('TLV3501 (TI)', table_cell), Paragraph('4.5 ns ultrafast zero-crossing', table_cell), Paragraph('$1.40', table_cell), Paragraph('1', table_cell), Paragraph('$1.40', table_cell)],
        [Paragraph('5', table_cell), Paragraph('PZT Pulser', table_cell), Paragraph('TC4420EPA (Microchip)', table_cell), Paragraph('6A peak gate driver (100ns pulse)', table_cell), Paragraph('$1.25', table_cell), Paragraph('1', table_cell), Paragraph('$1.25', table_cell)],
        [Paragraph('6', table_cell), Paragraph('Electrical AFE', table_cell), Paragraph('INA226AIDGSR (TI)', table_cell), Paragraph('16-bit I2C Current/Voltage/Power', table_cell), Paragraph('$1.55', table_cell), Paragraph('1', table_cell), Paragraph('$1.55', table_cell)],
        [Paragraph('7', table_cell), Paragraph('Thermal IR', table_cell), Paragraph('MLX90614ESF-BAA', table_cell), Paragraph('Non-contact IR, 0.02°C resolution', table_cell), Paragraph('$5.80', table_cell), Paragraph('1', table_cell), Paragraph('$5.80', table_cell)],
        [Paragraph('8', table_cell), Paragraph('NTC Sensors', table_cell), Paragraph('B57861S0103F040 (TDK)', table_cell), Paragraph('10kΩ ±0.5%, Beta=3950', table_cell), Paragraph('$0.65', table_cell), Paragraph('2', table_cell), Paragraph('$1.30', table_cell)],
        [Paragraph('9', table_cell), Paragraph('PZT Discs', table_cell), Paragraph('SMD10T2R111WL (PZT-5)', table_cell), Paragraph('1.0 MHz, D=10mm, T=2mm', table_cell), Paragraph('$2.10', table_cell), Paragraph('2', table_cell), Paragraph('$4.20', table_cell)],
        [Paragraph('10', table_cell), Paragraph('Power MOSFETs', table_cell), Paragraph('FDMS86180 (ON Semi)', table_cell), Paragraph('100V, 60A, R_ds = 3.2mΩ', table_cell), Paragraph('$1.15', table_cell), Paragraph('2', table_cell), Paragraph('$2.30', table_cell)],
        [Paragraph('11', table_cell), Paragraph('Buck Driver', table_cell), Paragraph('TPS28225 (TI)', table_cell), Paragraph('Synchronous Half-Bridge Driver', table_cell), Paragraph('$1.10', table_cell), Paragraph('1', table_cell), Paragraph('$1.10', table_cell)],
        [Paragraph('12', table_cell), Paragraph('Inductor', table_cell), Paragraph('SER2918H-103KL (Coilcraft)', table_cell), Paragraph('10µH, 14.5A I_sat, 3.1mΩ DCR', table_cell), Paragraph('$3.40', table_cell), Paragraph('1', table_cell), Paragraph('$3.40', table_cell)],
        [Paragraph('13', table_cell), Paragraph('Current Shunt', table_cell), Paragraph('CSS2H-2512R-L010F', table_cell), Paragraph('10mΩ 0.1% 5W 4-terminal Kelvin', table_cell), Paragraph('$1.15', table_cell), Paragraph('1', table_cell), Paragraph('$1.15', table_cell)],
        [Paragraph('14', table_cell), Paragraph('Safety Relay', table_cell), Paragraph('G3VM-61A1 (Omron)', table_cell), Paragraph('Solid State Opto-MOSFET Relay', table_cell), Paragraph('$1.60', table_cell), Paragraph('1', table_cell), Paragraph('$1.60', table_cell)],
        [Paragraph('15', table_cell), Paragraph('Passives/PCB', table_cell), Paragraph('4-Layer FR4 + Enclosure', table_cell), Paragraph('100x100mm 4-Layer ENIG Gold PCB', table_cell), Paragraph('$5.30', table_cell), Paragraph('1', table_cell), Paragraph('$5.30', table_cell)],
        [Paragraph('<b>TOTAL</b>', table_cell), Paragraph('', table_cell), Paragraph('', table_cell), Paragraph('<b>Complete System Unit BOM Cost</b>', table_cell), Paragraph('', table_cell), Paragraph('', table_cell), Paragraph('<b>$38.75</b>', table_cell)],
    ]
    bom_table = Table(bom_data, colWidths=[24, 66, 110, 150, 48, 26, 80])
    bom_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor('#f8fafc')]),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (4,0), (-1,-1), 'RIGHT'),
    ]))
    story.append(bom_table)
    story.append(Spacer(1, 8))

    # Page Break for Chapter 3
    story.append(PageBreak())

    # Chapter 3: Schematics & Circuit Operation
    story.append(Paragraph('3. Schematics & Circuit Operation', h1_style))
    story.append(Paragraph('<b>3.1 High-Voltage Ultrasonic Pulser & Analog Front-End (AFE)</b>', h2_style))
    story.append(Paragraph('1. <b>Pulser:</b> The ESP32 RMT peripheral generates a 100 ns active-high gate pulse to the TC4420 driver. The driver switches an inductor-loaded boost circuit to produce a +48V spike into the 1.0 MHz PZT transmitting transducer (X1).', body_style))
    story.append(Paragraph('2. <b>LNA Receiver:</b> The acoustic echo received at X2 (~10-50 mV amplitude) is AC-coupled to the AD8065 JFET operational amplifier configured with a gain of +40 dB (100x) and a 2nd-order Sallen-Key bandpass filter centered at 1.0 MHz (Q=4).', body_style))
    story.append(Paragraph('3. <b>Zero-Crossing Timing:</b> The amplified echo feeds the TLV3501 ultrafast comparator. The comparator generates a clean digital STOP pulse into the TI TDC7200 Time-to-Digital Converter.', body_style))
    story.append(Paragraph('4. <b>Precision Timing Calculation:</b> The TDC7200 measures elapsed time between START (excitation trigger) and STOP with 55 ps resolution, transmitting the raw clock counts over SPI at 10 MHz.', body_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph('<b>3.2 Zero-Voltage Switching (ZVS) Quasi-Resonant Active Balancer</b>', h2_style))
    story.append(Paragraph('To maximize round-trip efficiency (>92%) and eliminate switching heat, the power stage utilizes a quasi-resonant ZVS buck-boost topology:', body_style))
    story.append(Paragraph('• <b>Zero-Voltage Turn-On:</b> Resonant snubber capacitors (C_snub = 470 pF) naturally discharge switch drain-source voltage to 0V during the 25 ns dead-time, eliminating capacitive turn-on switching losses by 85%.', body_style))
    story.append(Paragraph('• <b>Inductive Energy Transfer:</b> A Coilcraft 10 µH, 14.5A saturation current inductor stores and shuttles charge between degraded cells and neighboring pack nodes with peak 98.4% transfer efficiency.', body_style))
    story.append(Paragraph('• <b>Kelvin 4-Wire ESR Auto-Nulling:</b> Dynamic software nulling eliminates false voltage sag caused by oxidized second-life contact fixtures: V_true = V_sense - I_shunt * R_contact_est.', body_style))
    story.append(Spacer(1, 6))

    # Chapter 4: 4-Layer PCB Stackup & RF Layout Rules
    story.append(Paragraph('4. 4-Layer High-Frequency PCB Stackup & Microstrip Design Rules', h1_style))
    story.append(Paragraph('The physical layout strictly segregates high-current switching harmonics (100 kHz / 2.5 A) from picosecond-level ultrasonic analog signals:', body_style))
    
    pcb_data = [
        [Paragraph('Layer', table_header), Paragraph('Layer Name', table_header), Paragraph('Copper / Thickness', table_header), Paragraph('Material / Dielectric', table_header), Paragraph('Function', table_header)],
        [Paragraph('L1 (Top)', table_cell), Paragraph('RF & Components', table_cell), Paragraph('1.0 oz (35 µm) / 0.20 mm', table_cell), Paragraph('FR-4 (εr=4.4, tanδ=0.02)', table_cell), Paragraph('50Ω Ultrasonic microstrips & ICs', table_cell)],
        [Paragraph('L2 (Inner 1)', table_cell), Paragraph('Solid GND Plane', table_cell), Paragraph('1.0 oz (35 µm) / 1.00 mm', table_cell), Paragraph('FR-4 Core (εr=4.5)', table_cell), Paragraph('Uninterrupted low-impedance return', table_cell)],
        [Paragraph('L3 (Inner 2)', table_cell), Paragraph('Power Plane', table_cell), Paragraph('1.0 oz (35 µm) / 0.20 mm', table_cell), Paragraph('FR-4 Prepreg (εr=4.4)', table_cell), Paragraph('+5V, +3.3V, +12V distribution rails', table_cell)],
        [Paragraph('L4 (Bottom)', table_cell), Paragraph('Power Switches', table_cell), Paragraph('1.0 oz (35 µm) / —', table_cell), Paragraph('Solder Mask + ENIG', table_cell), Paragraph('High-current balancing loops & vias', table_cell)],
    ]
    pcb_table = Table(pcb_data, colWidths=[55, 95, 115, 115, 124])
    pcb_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('PADDING', (0,0), (-1,-1), 3),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
    ]))
    story.append(pcb_table)
    story.append(Paragraph('• <b>50Ω Microstrip Trace:</b> Trace width w = 0.36 mm over h = 0.20 mm dielectric ensures Z_0 = 50.2Ω matching the piezo SMA input.', body_style))
    story.append(Paragraph('• <b>Star-Point Kelvin Ground:</b> AGND and PGND are separated across top/bottom layers and joined exclusively at a single 0805 net-tie point adjacent to the bulk input decoupling capacitors.', body_style))
    story.append(Spacer(1, 6))

    # Chapter 5: FreeRTOS Firmware Architecture
    story.append(Paragraph('5. FreeRTOS Dual-Core Real-Time Supervisor Architecture', h1_style))
    story.append(Paragraph('The embedded firmware runs on the ESP32-S3 dual-core processor using FreeRTOS with strict deterministic task scheduling:', body_style))
    story.append(Paragraph('• <b>Core 0 (100 Hz FastDAQ & 1 kHz Safety):</b> Task_FastDAQ coordinates ultrasonic ToF pulses and 16-bit INA226 ADC sampling; Task_SafetySupervisor executes sub-millisecond hardware fault interlocks.', body_style))
    story.append(Paragraph('• <b>Core 1 (100 kHz ZVS Control & Edge ML):</b> Task_ZVSControl modulates synchronous PWM gate timings with 25 ns dead-time; Edge ML inference executes real-time multi-modal classification.', body_style))
    story.append(Spacer(1, 6))

    # Page Break for Chapter 6 & 7
    story.append(PageBreak())

    # Chapter 6: SPICE & Simulation Standards
    story.append(Paragraph('6. SPICE Transient Loss Modeling & 3D Stress Physics', h1_style))
    story.append(Paragraph('<b>6.1 SPICE Resonant Switching & Loss Breakdown:</b>', h2_style))
    story.append(Paragraph('The automated SPICE solver (hardware/spice/run_spice_simulation.py) models conduction, gate charge, and quasi-resonant body diode conduction during 2.5 A shuttling:', body_style))
    story.append(Paragraph('• Conduction Losses: 70.0 mW (MOSFETs 3.2mΩ, Inductor 3.1mΩ, Shunt 5.0mΩ).', body_style))
    story.append(Paragraph('• ZVS Soft-Switching Losses: 2.2 mW (85% reduction vs hard switching).', body_style))
    story.append(Paragraph('• Gate Drive Losses: 96.0 mW (2 x Qg=48nC @ 100kHz). <b>Overall System Efficiency: 98.02% (Peak).</b>', body_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph('<b>6.2 3D Intercalation Stress Tensors & Acoustic Transfer Matrix:</b>', h2_style))
    story.append(Paragraph('The enhanced 3D spatial simulation (simulation_3d_demo/ev_battery_3d_simulation.py) solves coupled solid diffusion concentration gradients C(r) and thermal expansion fields, generating radial, hoop, and Von Mises stress distributions (σ_VM ~ 118 kPa). The multi-layer acoustic transfer matrix calculates transmission coefficients across 7 physical boundaries (Steel, PDMS, Cu, Anode, Separator, NMC Cathode, Al), revealing severe 95% attenuation under electrolyte gas generation.', body_style))
    story.append(Spacer(1, 6))

    # Chapter 7: MATLAB/Simulink Co-Simulation
    story.append(Paragraph('7. MATLAB / Simulink 4S Active Balancing & DEKF Co-Estimator', h1_style))
    story.append(Paragraph('The repository provides two dedicated MATLAB/Simulink validation scripts:', body_style))
    story.append(Paragraph('• <b>simulate_4s_active_balancing.m:</b> Simulates a 4-cell series pack under 20% initial SOC imbalance. The ZVS charge-shuttling rebalancer converges pack imbalance from 20.0% down to &lt;1.0% in 120 seconds with Coulomb efficiency &gt;96.5%.', body_style))
    story.append(Paragraph('• <b>dekf_ecm_joint_estimator.m:</b> Dual Extended Kalman Filter running on 2-RC ECM model. Concurrently tracks rapid SOC dynamics and slowly varying degradation parameters (R0, R1, C1) with &lt;3% estimation error under high sensor noise.', body_style))
    story.append(Spacer(1, 6))

    # Chapter 8: ESP32-S3 Pinout & Interface Matrix
    story.append(Paragraph('8. ESP32-S3 Pinout & Interface Matrix', h1_style))
    pin_data = [
        [Paragraph('Pin Name', table_header), Paragraph('GPIO', table_header), Paragraph('Peripheral', table_header), Paragraph('Connected Component', table_header), Paragraph('Signal Function', table_header)],
        [Paragraph('PULSE_TRIG', table_cell), Paragraph('GPIO 4', table_cell), Paragraph('RMT CH0', table_cell), Paragraph('TC4420 Gate Driver', table_cell), Paragraph('100 ns PZT Excitation Trigger', table_cell)],
        [Paragraph('TDC_START', table_cell), Paragraph('GPIO 5', table_cell), Paragraph('Output', table_cell), Paragraph('TDC7200 START Pin', table_cell), Paragraph('ToF Timing Start Reference', table_cell)],
        [Paragraph('TDC_INT', table_cell), Paragraph('GPIO 6', table_cell), Paragraph('Ext Interrupt', table_cell), Paragraph('TDC7200 INTB Pin', table_cell), Paragraph('Measurement Complete ISR', table_cell)],
        [Paragraph('SPI_CS', table_cell), Paragraph('GPIO 10', table_cell), Paragraph('SPI2 CS', table_cell), Paragraph('TDC7200 CS Pin', table_cell), Paragraph('Chip Select (Active Low)', table_cell)],
        [Paragraph('SPI_SCK', table_cell), Paragraph('GPIO 12', table_cell), Paragraph('SPI2 SCK', table_cell), Paragraph('TDC7200 CLK Pin', table_cell), Paragraph('SPI Clock (10 MHz)', table_cell)],
        [Paragraph('SPI_MISO', table_cell), Paragraph('GPIO 13', table_cell), Paragraph('SPI2 MISO', table_cell), Paragraph('TDC7200 DOUT Pin', table_cell), Paragraph('SPI Data Readout', table_cell)],
        [Paragraph('SPI_MOSI', table_cell), Paragraph('GPIO 11', table_cell), Paragraph('SPI2 MOSI', table_cell), Paragraph('TDC7200 DIN Pin', table_cell), Paragraph('SPI Configuration Write', table_cell)],
        [Paragraph('I2C_SDA', table_cell), Paragraph('GPIO 21', table_cell), Paragraph('I2C0 SDA', table_cell), Paragraph('INA226 + MLX90614', table_cell), Paragraph('I2C Sensor Bus Data (400kHz)', table_cell)],
        [Paragraph('I2C_SCL', table_cell), Paragraph('GPIO 22', table_cell), Paragraph('I2C0 SCL', table_cell), Paragraph('INA226 + MLX90614', table_cell), Paragraph('I2C Sensor Bus Clock (400kHz)', table_cell)],
        [Paragraph('BAL_PWM', table_cell), Paragraph('GPIO 15', table_cell), Paragraph('LEDC PWM', table_cell), Paragraph('TPS28225 Driver', table_cell), Paragraph('100 kHz ZVS Rebalancing PWM', table_cell)],
        [Paragraph('EMERG_TRIP', table_cell), Paragraph('GPIO 16', table_cell), Paragraph('Output', table_cell), Paragraph('G3VM-61A1 Relay', table_cell), Paragraph('Hardware Pack Lockout Disconnect', table_cell)],
        [Paragraph('ADC_NTC1', table_cell), Paragraph('GPIO 1 (CH0)', table_cell), Paragraph('ADC1', table_cell), Paragraph('NTC Thermistor #1', table_cell), Paragraph('Surface Temperature Sensing', table_cell)],
        [Paragraph('UART_TX/RX', table_cell), Paragraph('GPIO 43/44', table_cell), Paragraph('UART0', table_cell), Paragraph('CP2102N USB Bridge', table_cell), Paragraph('Host Telemetry Stream (115200 baud)', table_cell)],
    ]
    pin_table = Table(pin_data, colWidths=[74, 54, 76, 120, 180])
    pin_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('PADDING', (0,0), (-1,-1), 3.0),
        ('ALIGN', (0,0), (1,-1), 'CENTER'),
    ]))
    story.append(pin_table)
    story.append(Spacer(1, 6))

    # Page Break for Chapter 9 & 10
    story.append(PageBreak())

    # Chapter 9: Mechanical Mounting & Acoustic Coupling
    story.append(Paragraph('9. Transducer Mounting & Acoustic Coupling Guide', h1_style))
    story.append(Paragraph('Acoustic impedance matching and stable contact pressure are paramount for sub-percent ToF diagnostic fidelity:', body_style))
    story.append(Paragraph('• <b>Acoustic Couplant Selection:</b> Use Dow Corning Sylgard 184 polydimethylsiloxane (PDMS) elastomer pads (Z ~ 1.5 MRayl) for permanent vibration-resistant mounting, or medical ultrasound gel (Aquasonic 100) for benchtop testing.', body_style))
    story.append(Paragraph('• <b>Clamping Force:</b> Apply a calibrated normal force of 7.5 +/- 1.5 N per transducer using the spring-loaded 3D-printed PETG fixture. Excessive force deforms cylindrical 18650 casing walls; insufficient force introduces micro-air gaps (Z_air = 0.0004 MRayl, causing 99.9% acoustic reflection).', body_style))
    story.append(Paragraph('• <b>Axial Alignment:</b> Position Tx and Rx transducers strictly along the diametric centerline (180 deg +/- 2 deg opposition) at the vertical midpoint (Z = 32.5 mm) to avoid casing end-cap reflections.', body_style))
    story.append(Spacer(1, 4))

    # Chapter 10: Multi-Layer Safety Interlocks & Checklist
    story.append(Paragraph('10. Multi-Layer Safety Interlocks & Benchtop Validation Checklist', h1_style))
    story.append(Paragraph('The hardware architecture enforces a 3-tier fail-safe safety interlock hierarchy (Tier 1 Hardware Comparator &lt;50µs, Tier 2 FreeRTOS Supervisor &lt;5ms, Tier 3 ML Decision Engine &lt;50ms).', body_style))

    check_data = [
        [Paragraph('Step', table_header), Paragraph('Validation Phase', table_header), Paragraph('Procedure & Acceptance Criteria', table_header), Paragraph('Status', table_header)],
        [Paragraph('1', table_cell), Paragraph('Power Rails Check', table_cell), Paragraph('Verify 3.3V, 12V, 48V boost rails within ±2% tolerance with DMM.', table_cell), Paragraph('[  ] PASS', table_cell)],
        [Paragraph('2', table_cell), Paragraph('SPI & I2C Bus Discovery', table_cell), Paragraph('Verify TDC7200 (SPI) and INA226 (I2C addr 0x40) respond with valid Device IDs.', table_cell), Paragraph('[  ] PASS', table_cell)],
        [Paragraph('3', table_cell), Paragraph('PZT Pulser Ringing Check', table_cell), Paragraph('Inspect Tx 50V pulse on oscilloscope. Confirm rise time < 25 ns and damping < 3 cycles.', table_cell), Paragraph('[  ] PASS', table_cell)],
        [Paragraph('4', table_cell), Paragraph('LNA Signal-to-Noise Ratio', table_cell), Paragraph('Observe received echo on oscilloscope. Confirm SNR > 26 dB and peak amplitude > 1.2V.', table_cell), Paragraph('[  ] PASS', table_cell)],
        [Paragraph('5', table_cell), Paragraph('TDC Timing Stability', table_cell), Paragraph('Record 100 consecutive ToF samples. Standard deviation must be < 500 ps.', table_cell), Paragraph('[  ] PASS', table_cell)],
        [Paragraph('6', table_cell), Paragraph('ZVS Rebalancing Stage', table_cell), Paragraph('Test bidirectional transfer at 0.5A - 3.0A. Confirm soft-switching and efficiency > 91.5%.', table_cell), Paragraph('[  ] PASS', table_cell)],
        [Paragraph('7', table_cell), Paragraph('Emergency Lockout Test', table_cell), Paragraph('Simulate internal short fault signal. Confirm relay disconnects within 50 µs.', table_cell), Paragraph('[  ] PASS', table_cell)],
        [Paragraph('8', table_cell), Paragraph('End-to-End Live Stream', table_cell), Paragraph('Connect to FastAPI backend over USB UART. Confirm 10Hz DiagnosticFrame streaming.', table_cell), Paragraph('[  ] PASS', table_cell)],
    ]
    check_table = Table(check_data, colWidths=[28, 110, 316, 50])
    check_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('PADDING', (0,0), (-1,-1), 3.0),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (3,0), (3,-1), 'CENTER'),
    ]))
    story.append(check_table)

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f'[SUCCESS] Generated Hardware Implementation Guide PDF: {output_path}')
    return output_path

if __name__ == '__main__':
    build_pdf()
