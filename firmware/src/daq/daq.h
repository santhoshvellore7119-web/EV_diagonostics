/**
 * @file daq.h
 * @brief Data Acquisition (DAQ) interface for fusing sensor data
 */

#ifndef DAQ_H
#define DAQ_H

#include <Arduino.h>
#include "sensors/electrical.h"
#include "sensors/ultrasonic.h"
#include "sensors/thermal.h"

/**
 * @brief Structure to hold the fused DAQ packet
 */
typedef struct {
  ElectricalData electrical;
  UltrasonicData ultrasonic;
  ThermalData thermal;
  uint32_t packet_id;       //!< Packet identifier
  uint64_t timestamp_us;    //!< Timestamp in microseconds (64-bit to avoid rollover issues)
} DAQPacket;

/**
 * @brief Initialize DAQ module
 */
void daq_init(void);

/**
 * @brief Create a DAQ packet from sensor data
 * @param[in] elec  Electrical data
 * @param[in] ultra Ultrasonic data
 * @param[in] therm Thermal data
 * @param[out] packet Pointer to DAQPacket to fill
 */
void daq_create_packet(const ElectricalData *elec,
                       const UltrasonicData *ultra,
                       const ThermalData *therm,
                       DAQPacket *packet);

#endif // DAQ_H