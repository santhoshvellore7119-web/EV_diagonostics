/**
 * @file serializer.h
 * @brief Utility for serializing DAQ packets to JSON
 */

#ifndef SERIALIZER_H
#define SERIALIZER_H

#include <Arduino.h>
#include "daq/daq.h"

/**
 * @brief Convert DAQ packet to JSON string
 * @param[in] packet Pointer to DAQPacket
 * @param[out] json_buffer Buffer to hold JSON string
 * @param[in] buffer_size Size of json_buffer
 */
void serializer_to_json(const DAQPacket *packet, char *json_buffer, size_t buffer_size);

#endif // SERIALIZER_H