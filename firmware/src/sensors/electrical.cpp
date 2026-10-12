/**
 * @file electrical.cpp
 * @brief 4-Wire Kelvin electrical sensing & pulse-step impedance implementation for INA226
 */

#include "electrical.h"
#include <math.h>

// INA226 I2C address
#define INA226_ADDRESS     0x40

// INA226 registers
#define REG_CONFIG         0x00
#define REG_SHUNT_VOLTAGE  0x01
#define REG_BUS_VOLTAGE    0x02
#define REG_POWER          0x03
#define REG_CURRENT        0x04
#define REG_CALIBRATION    0x05

// Calibration value for INA226 (Current_LSB = 0.5mA, R_shunt = 0.010 Ohm -> CAL = 1024)
#define INA226_CAL_VALUE   1024

static float last_resting_voltage_v = 3.85f;

static float ina226_read_bus_voltage_v(void) {
  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(REG_BUS_VOLTAGE);
  Wire.endTransmission();
  Wire.requestFrom(INA226_ADDRESS, 2);
  uint16_t bus_val = (Wire.read() << 8) | Wire.read();
  return (float)(bus_val >> 3) * 0.00125f; // 1.25 mV per bit
}

static float ina226_read_current_a(void) {
  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(REG_CURRENT);
  Wire.endTransmission();
  Wire.requestFrom(INA226_ADDRESS, 2);
  int16_t current_val = (Wire.read() << 8) | Wire.read();
  return (float)current_val * 0.0005f; // 0.5 mA per bit
}

bool electrical_init(void) {
  pinMode(PULSE_LOAD_MOSFET_PIN, OUTPUT);
  digitalWrite(PULSE_LOAD_MOSFET_PIN, LOW);

  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(REG_CONFIG);
  // Averaging = 4 samples, 140us conversion time, continuous shunt & bus (0x4327)
  Wire.write(0x43);
  Wire.write(0x27);
  if (Wire.endTransmission() != 0) {
    return false;
  }

  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(REG_CALIBRATION);
  Wire.write((INA226_CAL_VALUE >> 8) & 0xFF);
  Wire.write(INA226_CAL_VALUE & 0xFF);
  if (Wire.endTransmission() != 0) {
    return false;
  }

  last_resting_voltage_v = ina226_read_bus_voltage_v();
  return true;
}

void electrical_sample(ElectricalData *data) {
  if (!data) return;

  // 1. Sample pre-pulse resting voltage & current
  float v_pre = ina226_read_bus_voltage_v();
  float i_pre = ina226_read_current_a();
  if (fabsf(i_pre) < 0.08f && v_pre > 2.5f) {
    last_resting_voltage_v = 0.8f * last_resting_voltage_v + 0.2f * v_pre;
  }

  // 2. Apply brief Kelvin diagnostic excitation pulse if external load current is near zero
  bool pulsed_internally = false;
  if (fabsf(i_pre) < 0.10f) {
    digitalWrite(PULSE_LOAD_MOSFET_PIN, HIGH);
    delayMicroseconds(1500); // Allow 1.5 ms for INA226 ADC conversion under pulse load
    pulsed_internally = true;
  }

  // 3. Read loaded bus voltage and current under excitation
  float v_load = ina226_read_bus_voltage_v();
  float i_load = ina226_read_current_a();

  if (pulsed_internally) {
    digitalWrite(PULSE_LOAD_MOSFET_PIN, LOW);
  }

  // 4. Compute true cell internal voltage step dV_cell = V_rest - V_load
  // Note: INA226 REG_SHUNT_VOLTAGE only measures I * R_shunt (10 mOhm).
  // Storing dV_cell in shunt_voltage_v ensures edge_ml_extract_features computes
  // the cell's internal impedance R_cell = dV_cell / dI_cell, matching Python training!
  float delta_i = fabsf(i_load - i_pre);
  float delta_v = fabsf(last_resting_voltage_v - v_load);
  float r0_est = 0.045f;
  if (delta_i > 0.05f && delta_v > 0.001f) {
    r0_est = delta_v / delta_i;
  } else if (fabsf(i_load) > 0.05f && delta_v > 0.001f) {
    r0_est = delta_v / fabsf(i_load);
  }
  if (r0_est < 0.015f) r0_est = 0.015f;
  if (r0_est > 0.350f) r0_est = 0.350f;

  float i_eff = (fabsf(i_load) > 0.05f) ? fabsf(i_load) : 0.50f;
  data->bus_voltage_v = v_load;
  data->current_a = i_eff;
  data->shunt_voltage_v = i_eff * r0_est; // True internal cell voltage drop I * R_cell
  data->r0_ohm = r0_est;
  data->power_w = data->bus_voltage_v * data->current_a;
  data->timestamp_us = micros();
}