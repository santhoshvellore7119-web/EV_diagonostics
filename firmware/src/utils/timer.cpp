/**
 * @file timer.cpp
 * @brief Timer utility implementation for excitation pulse generation
 *        Using ESP32 hardware timer.
 */

#include "timer.h"

// Static variables for ISR access
static uint8_t excitation_pin = 27;
static uint32_t pulse_width_us = 10;
static uint32_t period_ms = 100; // Default period for ISR reconfiguration
static hw_timer_t * timer = NULL;
static portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;

/**
 * @brief ISR for timer interrupt
 */
void IRAM_ATTR timer_isr() {
  portENTER_ISR_ISR(&timerMux);
  // Generate excitation pulse
  digitalWrite(excitation_pin, HIGH);
  // Delay for pulse width (blocking but short)
  delayMicroseconds(pulse_width_us);
  digitalWrite(excitation_pin, LOW);
  portEXIT_ISR_ISR(&timerMux);
}

void timer_init_excitation(uint32_t period_ms_arg, uint32_t pulse_width_us_arg, uint8_t excitation_pin_arg) {
  excitation_pin = excitation_pin_arg;
  pulse_width_us = pulse_width_us_arg;
  period_ms = period_ms_arg; // Store for potential reconfiguration

  // Configure excitation pin as output
  pinMode(excitation_pin, OUTPUT);
  digitalWrite(excitation_pin, LOW);

  // Create and configure timer
  timer = timerBegin(0, 80, true); // Timer 0, divider 80 (1 MHz tick), count up
  timerAlarmWrite(timer, period_ms * 1000, true); // period in microseconds, autoreload
  timerAttachInterrupt(timer, &timer_isr, true); // edge interrupt
  timerAlarmEnable(timer); // enable interrupt
}

void timer_update_excitation(uint32_t period_ms_arg, uint32_t pulse_width_us_arg) {
  portENTER_CRITICAL_ISR(&timerMux);

  // Update parameters if non-zero values provided
  if (pulse_width_us_arg > 0) {
    pulse_width_us = pulse_width_us_arg;
  }

  if (period_ms_arg > 0) {
    period_ms = period_ms_arg;
    // Reconfigure timer with new period
    timerAlarmWrite(timer, period_ms * 1000, true);
  }

  portEXIT_CRITICAL_ISR(&timerMux);
}

void trigger_excitation_pulse(void) {
  // For software triggering (if needed)
  digitalWrite(excitation_pin, HIGH);
  delayMicroseconds(pulse_width_us);
  digitalWrite(excitation_pin, LOW);
}