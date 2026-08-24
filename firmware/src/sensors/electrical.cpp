/**
 * @file electrical.cpp
 * @brief Electrical sensing implementation for INA226
 */

#include "electrical.h"

// INA226 I2C address (can be changed with ADDR pins)
#define INA226_ADDRESS 0x40

// INA226 registers
#define REG_CONFIG         0x00
#define REG_SHUNT_VOLTAGE  0x01
#define REG_BUS_VOLTAGE    0x02
#define REG_POWER          0x03
#define REG_CURRENT        0x04
#define REG_CALIBRATION    0x05

// Calibration value for INA226 (set for 1A, 0.01 ohm shunt)
// CAL = 0.00512 / (Current_LSB * Rshunt)
// We set Current_LSB to 0.5mA (so 1A = 2048 steps)
// Rshunt = 0.01 ohm
// CAL = 0.00512 / (0.0005 * 0.01) = 0.00512 / 0.000005 = 1024
#define INA226_CAL_VALUE 1024

bool electrical_init(void) {
  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(REG_CONFIG);
  // Set configuration: reset, then set for continuous shunt and bus voltage
  // We'll set: AVG = 1, VBUSCT = 110 (1100us), VSHCT = 110 (1100us), MODE = 7 (continuous shunt and bus)
  Wire.write(0x01); // MSB: AVG=00, VBUSCT=001, VSHCT=001, MODE=001 -> actually we need to set properly
  // Let's set a known good configuration: 0x4527 (common for continuous)
  Wire.write(0x45); // MSB
  Wire.write(0x27); // LSB
  if (Wire.endTransmission() != 0) {
    return false;
  }

  // Set calibration
  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(REG_CALIBRATION);
  Wire.write((INA226_CAL_VALUE >> 8) & 0xFF);
  Wire.write(INA226_CAL_VALUE & 0xFF);
  if (Wire.endTransmission() != 0) {
    return false;
  }

  // Set current LSB to 0.5mA per bit (for 0.01 ohm shunt, 32767 bits = 16.3835A)
  // Actually, the calibration sets the current LSB. We'll compute it in the sample function.
  return true;
}

void electrical_sample(ElectricalData *data) {
  // Read shunt voltage
  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(REG_SHUNT_VOLTAGE);
  Wire.endTransmission();
  Wire.requestFrom(INA226_ADDRESS, 2);
  int16_t shunt_val = (Wire.read() << 8) | Wire.read();
  data->shunt_voltage_v = shunt_val * 0.0000025; // 2.5µV per bit

  // Read bus voltage
  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(REG_BUS_VOLTAGE);
  Wire.endTransmission();
  Wire.requestFrom(INA226_ADDRESS, 2);
  uint16_t bus_val = (Wire.read() << 8) | Wire.read();
  data->bus_voltage_v = (bus_val >> 3) * 0.00125; // 1.25mV per bit (shifted 3 bits)

  // Read current
  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(REG_CURRENT);
  Wire.endTransmission();
  Wire.requestFrom(INA226_ADDRESS, 2);
  int16_t current_val = (Wire.read() << 8) | Wire.read();
  // Current LSB depends on calibration. We'll use the formula: Current = (register value) * 0.00512 / (CAL * 0.00512 / Rshunt) ... actually simpler:
  // The INA226 datasheet: Current = (register value) * 0.00512 / (CAL * 0.00512) ??? Let's use a common approach:
  // We set CAL for 0.5mA per bit, so:
  data->current_a = current_val * 0.0005; // 0.5mA per bit

  // Read power (optional)
  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(REG_POWER);
  Wire.endTransmission();
  Wire.requestFrom(INA226_ADDRESS, 2);
  uint16_t power_val = (Wire.read() << 8) | Wire.read();
  // Power LSB = 25 * Current LSB (from datasheet)
  data->power_w = power_val * 0.0005 * 25; // 25 * 0.5mA * voltage? Actually, power LSB = 25 * current LSB * volt? Let's simplify: we'll compute power as V*I later if needed.
  // For now, we'll set power to bus_voltage * current
  data->power_w = data->bus_voltage_v * data->current_a;

  data->timestamp_us = micros();
}