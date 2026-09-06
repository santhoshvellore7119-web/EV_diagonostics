/**
 * @file serializer.cpp
 * @brief Utility for serializing DAQ packets to JSON
 */

#include "serializer.h"
#include <stdio.h>

void serializer_to_json(const DAQPacket *packet, char *json_buffer, size_t buffer_size) {
  if (packet == nullptr || json_buffer == nullptr || buffer_size == 0) {
    return;
  }

  int len = snprintf(json_buffer, buffer_size,
    "{{"
    "\"packet_id\":%u,"
    "\"timestamp_us\":%llu,"
    "\"electrical\":{"
      "\"bus_voltage_v\":%.3f,"
      "\"shunt_voltage_v\":%.6f,"
      "\"current_a\":%.3f,"
      "\"power_w\":%.3f,"
      "\"timestamp_us\":%u"
    "},"
    "\"ultrasonic\":{"
      "\"time_of_flight_us\":%.3f,"
      "\"amplitude\":%.3f,"
      "\"phase_shift\":%.3f,"
      "\"timestamp_us\":%u"
    "},"
    "\"thermal\":{"
      "\"temperature_c\":%.2f,"
      "\"temp_gradient_c_per_s\":%.3f,"
      "\"timestamp_us\":%u"
    "}"
    "}}",
    packet->packet_id,
    packet->timestamp_us,
    packet->electrical.bus_voltage_v,
    packet->electrical.shunt_voltage_v,
    packet->electrical.current_a,
    packet->electrical.power_w,
    packet->electrical.timestamp_us,
    packet->ultrasonic.time_of_flight_us,
    packet->ultrasonic.amplitude,
    packet->ultrasonic.phase_shift,
    packet->ultrasonic.timestamp_us,
    packet->thermal.temperature_c,
    packet->thermal.temp_gradient_c_per_s,
    packet->thermal.timestamp_us
  );

  // Ensure null termination (snprintf does this if buffer_size > 0)
  // If the string was truncated, we could add an ellipsis, but we'll leave as is.
}