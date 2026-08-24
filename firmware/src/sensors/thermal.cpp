/**
 * @file thermal.cpp
 * @brief Thermal sensing implementation (I2C TMP102 example)
 */

#include "thermal.h"
#include <Wire.h>

// TMP102 I2C address (ADDR pin to GND)
#define TMP102_ADDRESS 0x48
#define TMP102_REG_TEMP 0x00

bool thermal_init(void) {
  Wire.beginTransmission(TMP102_ADDRESS);
  Wire.write(TMP102_REG_TEMP); // Point to temperature register (though we just need to wake it up)
  Wire.endTransmission();
  return true;
}

void thermal_sample(ThermalData *data) {
  // Read temperature from TMP102
  Wire.beginTransmission(TMP102_ADDRESS);
  Wire.write(TMP102_REG_TEMP);
  Wire.endTransmission();
  Wire.requestFrom(TMP102_ADDRESS, 2);
  if (Wire.available() >= 2) {
    uint8_t msb = Wire.read();
    uint8_t lsb = Wire.read();
    int16_t temp_raw = (msb << 4) | (lsb >> 4); // 12-bit value
    // Handle negative temperatures
    if (temp_raw > 0x7FF) {
      temp_raw -= 0x1000; // 2's complement
    }
    data->temperature_c = temp_raw * 0.0625; // TMP102 resolution 0.0625°C per LSB
  } else {
    data->temperature_c = 25.0; // Default if read fails
  }

  // For gradient, we need to store previous temperature and time.
  // We'll use static variables for simplicity (not thread-safe but okay for single task)
  static float last_temp = 0.0;
  static uint32_t last_time = 0;
  uint32_t now = micros();
  if (last_time == 0) {
    // First reading
    data->temp_gradient_c_per_s = 0.0;
  } else {
    float dt = (now - last_time) / 1000000.0; // seconds
    if (dt > 0) {
      data->temp_gradient_c_per_s = (data->temperature_c - last_temp) / dt;
    } else {
      data->temp_gradient_c_per_s = 0.0;
    }
  }
  last_temp = data->temperature_c;
  last_time = now;

  data->timestamp_us = now;
}