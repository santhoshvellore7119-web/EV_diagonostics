/**
 * @file ultrasonic.h
 * @brief Ultrasonic pulse-echo sensing interface
 */

#ifndef ULTRASONIC_H
#define ULTRASONIC_H

#include <Arduino.h>

/**
 * @brief Structure to hold ultrasonic measurement data
 */
typedef struct {
  float time_of_flight_us;   //!< Time of flight in microseconds
  float amplitude;          //!< Echo amplitude (relative)
  float phase_shift;        //!< Phase shift (if using coherent detection)
  uint32_t timestamp_us;    //!< Timestamp in microseconds
} UltrasonicData;

/**
 * @brief Initialize ultrasonic sensor (trigger and echo pins)
 * @param trigger_pin GPIO pin for trigger pulse
 * @param echo_pin GPIO pin for echo input
 * @return true on success, false on failure
 */
bool ultrasonic_init(uint8_t trigger_pin, uint8_t echo_pin);

/**
 * @brief Trigger ultrasonic pulse and capture echo
 * @param[out] data Pointer to UltrasonicData structure to fill
 */
void ultrasonic_sample(UltrasonicData *data);

#endif // ULTRASONIC_H