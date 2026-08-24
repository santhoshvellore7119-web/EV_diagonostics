# Dependencies

## Firmware (MCU)
- Arduino IDE (or PlatformIO) with ESP32/STM32 support
- Required libraries (install via Library Manager):
  - Wire.h (I2C) - built-in
  - SPI.h - built-in
  - No external libraries required for the core sensors (INA226, TMP102, piezoelectric) - we use direct register access

## Machine Learning Pipeline (Python)
- Python 3.8+
- torch>=2.0.0
- numpy>=1.24.0
- scikit-learn>=1.3.0
- matplotlib>=3.7.0

Install via:
```bash
pip install torch torchvision numpy scikit-learn matplotlib
```

## Host Application (Python)
- Python 3.8+
- pyqt5>=5.15.0
- pyqtgraph>=0.13.0
- pyserial>=3.5
- numpy>=1.24.0

Install via:
```bash
pip install pyqt5 pyqtgraph pyserial numpy
```

## Verification and Decision Engine (Python)
- Python 3.8+
- numpy>=1.24.0

(These are already included in the ML pipeline requirements.)

## Optional for Development
- Jupyter notebook for data exploration
- pandas for data handling
- seaborn for advanced plotting

Install via:
```bash
pip install jupyter pandas seaborn
```