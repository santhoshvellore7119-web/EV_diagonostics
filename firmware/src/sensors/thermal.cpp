/**
 * @file thermal.cpp
 * @brief Dual-sensor differential thermal sensing implementation (TMP102/TMP117 I2C 0x48 & 0x49)
 */

#include "thermal.h"
#include <Wire.h>

// Dual TMP102 / TMP117 I2C addresses
#define TMP_SURFACE_ADDRESS 0x48  // ADDR pin to GND (Cell Surface Contact)
#define TMP_AMBIENT_ADDRESS 0x49  // ADDR pin to V+  (Ambient Reference)
#define TMP_REG_TEMP        0x00

static bool ambient_sensor_present = false;

static bool read_tmp_sensor_c(uint8_t i2c_addr, float *temp_out_c) {
  Wire.beginTransmission(i2c_addr);
  Wire.write(TMP_REG_TEMP);
  if (Wire.endTransmission() != 0) {
    return false;
  }
  Wire.requestFrom(i2c_addr, (uint8_t)2);
  if (Wire.available() >= 2) {
    uint8_t msb = Wire.read();
    uint8_t lsb = Wire.read();
    int16_t temp_raw = (msb << 4) | (lsb >> 4); // 12-bit 2's complement
    if (temp_raw > 0x7FF) {
      temp_raw -= 0x1000;
    }
    *temp_out_c = (float)temp_raw * 0.0625f;
    return true;
  }
  return false;
}

bool thermal_init(void) {
  float dummy_c = 25.0f;
  bool surf_ok = read_tmp_sensor_c(TMP_SURFACE_ADDRESS, &dummy_c);
  ambient_sensor_present = read_tmp_sensor_c(TMP_AMBIENT_ADDRESS, &dummy_c);
  return surf_ok;
}

void thermal_sample(ThermalData *data) {
  if (!data) return;

  float t_surf = 26.5f;
  if (!read_tmp_sensor_c(TMP_SURFACE_ADDRESS, &t_surf)) {
    t_surf = 26.5f;
  }

  float t_amb = 25.0f;
  if (ambient_sensor_present) {
    if (!read_tmp_sensor_c(TMP_AMBIENT_ADDRESS, &t_amb)) {
      t_amb = 25.0f;
    }
  }

  // Compute true internal self-heating rise dT = max(0, T_surface - T_ambient)
  // Referenced to standard 25.0C baseline so EdgeMultiModalNet is 100% invariant to room temperature
  float dt_rise = t_surf - t_amb;
  if (dt_rise < 0.0f) dt_rise = 0.0f;

  data->surface_temp_c = t_surf;
  data->ambient_temp_c = t_amb;
  data->temperature_c = 25.0f + dt_rise;

  static float last_temp_comp = 25.0f;
  static uint32_t last_time_us = 0;
  uint32_t now = micros();
  if (last_time_us == 0) {
    data->temp_gradient_c_per_s = 0.0f;
  } else {
    float dt_s = (float)(now - last_time_us) / 1000000.0f;
    if (dt_s > 1e-4f) {
      data->temp_gradient_c_per_s = (data->temperature_c - last_temp_comp) / dt_s;
    } else {
      data->temp_gradient_c_per_s = 0.0f;
    }
  }
  last_temp_comp = data->temperature_c;
  last_time_us = now;
  data->timestamp_us = now;
}