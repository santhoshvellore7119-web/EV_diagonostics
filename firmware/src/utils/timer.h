/**
 * @file timer.h
 * @brief Timer utility for generating excitation pulses with adaptive control
 */

#ifndef TIMER_H
#define TIMER_H

#include <Arduino.h>

/**
 * @brief Initialize timer for periodic excitation pulse generation
 * @param period_ms Period between pulses in milliseconds
 * @param pulse_width_us Pulse width in microseconds
 * @param excitation_pin GPIO pin used for excitation pulse (default: 27)
 */
void timer_init_excitation(uint32_t period_ms, uint32_t pulse_width_us, uint8_t excitation_pin = 27);

/**
 * @brief Update excitation pulse parameters at runtime
 * @param period_ms New period between pulses in milliseconds (0 to keep unchanged)
 * @param pulse_width_us New pulse width in microseconds (0 to keep unchanged)
 * @note Only non-zero values are updated
 */
void timer_update_excitation(uint32_t period_ms, uint32_t pulse_width_us);

/**
 * @brief Trigger an excitation pulse (to be called from ISR or task)
 * @note This function should trigger the hardware to generate a pulse.
 *       Implementation depends on the hardware (e.g., using a GPIO or DAC).
 */
void trigger_excitation_pulse(void);

#endif // TIMER_H