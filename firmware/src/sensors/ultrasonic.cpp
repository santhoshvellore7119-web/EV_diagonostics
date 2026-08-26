/**
 * @file ultrasonic.cpp
 * @brief Ultrasonic pulse-echo sensing implementation
 */

#include "ultrasonic.h"

// Pin assignments (will be set in init)
static uint8_t triggerPin = 25;
static uint8_t echoPin = 26;

// For timing the echo pulse
static volatile uint32_t echoStartTime = 0;
static volatile uint32_t echoEndTime = 0;
static volatile bool echoReceived = false;

/**
 * @brief ISR for echo pin (rising edge)
 */
void IRAM_ATTR echoRisingISR() {
  echoStartTime = micros();
}

/**
 * @brief ISR for echo pin (falling edge)
 */
void IRAM_ATTR echoFallingISR() {
  echoEndTime = micros();
  echoReceived = true;
}

bool ultrasonic_init(uint8_t trigger_pin, uint8_t echo_pin) {
  triggerPin = trigger_pin;
  echoPin = echo_pin;

  pinMode(triggerPin, OUTPUT);
  pinMode(echoPin, INPUT);
  digitalWrite(triggerPin, LOW);

  // Attach interrupts for echo pin
  attachInterrupt(digitalPinToInterrupt(echoPin), echoRisingISR, RISING);
  attachInterrupt(digitalPinToInterrupt(echoPin), echoFallingISR, FALLING);

  return true;
}

void ultrasonic_sample(UltrasonicData *data) {
  // Trigger ultrasonic pulse
  digitalWrite(triggerPin, HIGH);
  delayMicroseconds(10); // 10 us trigger pulse
  digitalWrite(triggerPin, LOW);

  // Wait for echo (with timeout)
  echoReceived = false;
  uint32_t startWait = micros();
  while (!echoReceived && (micros() - startWait) < 3000) { // 3ms timeout (max range ~50cm in air)
    // Busy wait, but we could yield
  }

  if (echoReceived) {
    data->time_of_flight_us = echoEndTime - echoStartTime;
    // For simplicity, we'll set amplitude to 1.0 (could be measured via ADC)
    data->amplitude = 1.0;
    // Phase shift would require coherent detection, not implemented here
    data->phase_shift = 0.0;
  } else {
    // Timeout
    data->time_of_flight_us = 0;
    data->amplitude = 0;
    data->phase_shift = 0;
  }
  data->timestamp_us = micros();
}