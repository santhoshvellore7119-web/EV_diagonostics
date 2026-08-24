/**
 * @file daq.cpp
 * @brief Data Acquisition (DAQ) implementation
 */

#include "daq.h"

static uint32_t packet_counter = 0;

void daq_init(void) {
  packet_counter = 0;
  // Any other initialization if needed
}

void daq_create_packet(const ElectricalData *elec,
                       const UltrasonicData *ultra,
                       const ThermalData *therm,
                       DAQPacket *packet) {
  packet->electrical = *elec;
  packet->ultrasonic = *ultra;
  packet->thermal = *therm;
  packet->packet_id = packet_counter++;
  packet->timestamp_us = elec->timestamp_us; // Use electrical timestamp as reference (they should be close)
}