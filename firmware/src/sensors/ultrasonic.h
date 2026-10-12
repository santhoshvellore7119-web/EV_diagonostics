/**
 * @file ultrasonic.h
 * @brief 1-2 MHz Ultrasonic pitch-catch sensing interface via TI TDC7200 (55ps SPI ToF),
 *        AD8307 Logarithmic Envelope Detector (ADC), and TLV3501 Zero-Crossing Comparator.
 */

#ifndef ULTRASONIC_H
#define ULTRASONIC_H

#include <Arduino.h>
#include <SPI.h>

// Default Hardware Pin Assignments (ESP32 / STM32 compatible)
#define TDC7200_CS_PIN        5   //!< SPI Chip Select for TDC7200 Time-to-Digital Converter
#define TDC7200_ENABLE_PIN    17  //!< Enable pin for TDC7200
#define TDC7200_INT_PIN       16  //!< Interrupt pin (active low) from TDC7200
#define AD8307_ENV_ADC_PIN    39  //!< ADC1_CH3 input connected to AD8307 log-amp envelope output
#define TLV3501_PHASE_PIN     34  //!< Digital input from TLV3501 comparator for first-arrival phase polarity

/**
 * @brief Structure to hold ultrasonic measurement data
 */
typedef struct {
  float time_of_flight_us;   //!< Time of flight in microseconds (from TDC7200 55ps TDC or edge timer)
  float amplitude;           //!< Peak echo envelope amplitude (normalized [0.05, 1.30] from AD8307)
  float phase_shift;         //!< First-arrival phase shift in radians ([-pi, pi] from TLV3501 polarity & zero-crossing)
  float reverb_energy_ratio; //!< Late-window reverberation coda energy ratio (gas generation indicator)
  uint32_t timestamp_us;     //!< Timestamp in microseconds
} UltrasonicData;

/**
 * @brief Initialize ultrasonic AFE (TDC7200 SPI + AD8307 ADC + trigger/echo fallback pins)
 * @param trigger_pin GPIO pin for TC4420 piezo excitation burst trigger
 * @param echo_pin GPIO pin for TLV3501 comparator STOP edge input
 * @return true on success, false on failure
 */
bool ultrasonic_init(uint8_t trigger_pin, uint8_t echo_pin);

/**
 * @brief Trigger 2 MHz ultrasonic burst, read TDC7200 ToF + AD8307 envelope + phase polarity
 * @param[out] data Pointer to UltrasonicData structure to fill
 */
void ultrasonic_sample(UltrasonicData *data);

#endif // ULTRASONIC_H