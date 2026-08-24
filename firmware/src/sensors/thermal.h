/**
 * @file thermal.h
 * @brief Thermal sensing interface (contact array or IR thermopile)
 */

#ifndef THERMAL_H
#define THERMAL_H

#include <Arduino.h>

/**
 * @brief Structure to hold thermal measurement data
 */
typedef struct {
  float temperature_c;      //!< Temperature in Celsius
  float temp_gradient_c_per_s; //!< Temperature gradient (dT/dt) in Celsius per second
  uint32_t timestamp_us;    //!< Timestamp in microseconds
} ThermalData;

/**
 * @brief Initialize thermal sensor
 * @return true on success, false on failure
 */
bool thermal_init(void);

/**
 * @brief Sample thermal data
 * @param[out] data Pointer to ThermalData structure to fill
 */
void thermal_sample(ThermalData *data);

#endif // THERMAL_H