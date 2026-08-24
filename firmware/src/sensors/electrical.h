/**
 * @file electrical.h
 * @brief Electrical sensing interface for INA226 or similar shunt-based current/voltage sensor
 */

#ifndef ELECTRICAL_H
#define ELECTRICAL_H

#include <Arduino.h>
#include <Wire.h>

/**
 * @brief Structure to hold electrical measurement data
 */
typedef struct {
  float bus_voltage_v;      //!< Bus voltage in volts
  float shunt_voltage_v;    //!< Shunt voltage in volts
  float current_a;          //!< Current in amps
  float power_w;            //!< Power in watts
  uint32_t timestamp_us;    //!< Timestamp in microseconds
} ElectricalData;

/**
 * @brief Initialize electrical sensor (INA226)
 * @return true on success, false on failure
 */
bool electrical_init(void);

/**
 * @brief Sample electrical data
 * @param[out] data Pointer to ElectricalData structure to fill
 */
void electrical_sample(ElectricalData *data);

#endif // ELECTRICAL_H