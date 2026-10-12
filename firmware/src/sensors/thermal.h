/**
 * @file thermal.h
 * @brief Differential surface-to-ambient thermal sensing interface (Dual TMP102/TMP117 I2C)
 */

#ifndef THERMAL_H
#define THERMAL_H

#include <Arduino.h>

/**
 * @brief Structure to hold differential thermal measurement data
 */
typedef struct {
  float temperature_c;          //!< Ambient-compensated cell temperature (25.0 + dT_rise) in Celsius
  float surface_temp_c;         //!< Raw cell surface temperature in Celsius (I2C 0x48)
  float ambient_temp_c;         //!< Raw ambient reference temperature in Celsius (I2C 0x49)
  float temp_gradient_c_per_s;  //!< Differential temperature gradient d(dT)/dt in Celsius per second
  uint32_t timestamp_us;        //!< Timestamp in microseconds
} ThermalData;

/**
 * @brief Initialize dual differential thermal sensors (0x48 surface, 0x49 ambient)
 * @return true on success, false on failure
 */
bool thermal_init(void);

/**
 * @brief Sample differential thermal data (eliminating room temperature drift)
 * @param[out] data Pointer to ThermalData structure to fill
 */
void thermal_sample(ThermalData *data);

#endif // THERMAL_H