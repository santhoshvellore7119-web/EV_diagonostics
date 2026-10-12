/**
 * @file electrical.h
 * @brief 4-Wire Kelvin electrical sensing & active pulse-step impedance interface for INA226
 */

#ifndef ELECTRICAL_H
#define ELECTRICAL_H

#include <Arduino.h>
#include <Wire.h>

// Gate drive pin for the 1-Ohm Kelvin diagnostic pulse load MOSFET (IRLZ44N / AO3400)
#define PULSE_LOAD_MOSFET_PIN 14

/**
 * @brief Structure to hold electrical measurement data
 */
typedef struct {
  float bus_voltage_v;      //!< Loaded cell terminal voltage in volts
  float shunt_voltage_v;    //!< Dynamic cell voltage step dV_cell = V_rest - V_load (for R0 = dV/dI)
  float current_a;          //!< Excitation / discharge current in amps
  float power_w;            //!< Instantaneous power in watts
  float r0_ohm;             //!< Measured dynamic ohmic + polarization resistance (Ohms)
  uint32_t timestamp_us;    //!< Timestamp in microseconds
} ElectricalData;

/**
 * @brief Initialize electrical sensor (INA226 + Kelvin pulse MOSFET gate)
 * @return true on success, false on failure
 */
bool electrical_init(void);

/**
 * @brief Sample electrical data using 4-wire Kelvin pulse-step impedance measurement
 * @param[out] data Pointer to ElectricalData structure to fill
 */
void electrical_sample(ElectricalData *data);

#endif // ELECTRICAL_H