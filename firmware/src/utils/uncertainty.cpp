/**
 * @file uncertainty.cpp
 * @brief Uncertainty estimation implementation for adaptive excitation control
 */

#include "uncertainty.h"
#include <math.h>

// Static variables for uncertainty estimation
static uint8_t sample_size = 10;
static uint8_t sample_count = 0;
static float electrical_uncertainty_sum = 0.0f;
static float ultrasonic_uncertainty_sum = 0.0f;
static float thermal_uncertainty_sum = 0.0f;
static float recent_voltage_values[50] = {0};  // Circular buffer for voltage
static float recent_tof_values[50] = {0};      // Circular buffer for ToF
static float recent_temp_values[50] = {0};     // Circular buffer for temperature
static uint8_t buffer_index = 0;
static float last_combined_uncertainty = 0.5f;

/**
 * @brief Initialize uncertainty estimation module
 * @param sample_size_arg Number of recent samples to consider for uncertainty calculation
 */
void uncertainty_init(uint8_t sample_size_arg) {
  if (sample_size_arg > 0 && sample_size_arg <= 50) {
    sample_size = sample_size_arg;
  } else {
    sample_size = 10;  // Default
  }

  uncertainty_reset();
}

/**
 * @brief Calculate uncertainty based on variance of recent measurements in circular buffer
 * @param values Circular buffer array of recent values (length 50)
 * @param start_idx Starting index in circular buffer
 * @param count Number of valid values in window
 * @param mean_value Mean of the values
 * @return Uncertainty score (0.0 to 1.0)
 */
static float calculate_uncertainty(const float* values, uint8_t start_idx, uint8_t count, float mean_value) {
  if (count < 2) {
    return 0.5f;  // High uncertainty when insufficient data
  }

  float variance = 0.0f;
  for (uint8_t i = 0; i < count; i++) {
    uint8_t idx = (start_idx + i) % 50;
    float diff = values[idx] - mean_value;
    variance += diff * diff;
  }
  variance /= (float)count;

  // Normalize variance into [0, 1] uncertainty score
  const float k = 10.0f;
  float uncertainty = 2.0f / (1.0f + expf(-k * variance)) - 1.0f;
  if (uncertainty < 0.0f) uncertainty = 0.0f;
  if (uncertainty > 1.0f) uncertainty = 1.0f;

  return uncertainty;
}

/**
 * @brief Update uncertainty estimation with new DAQ packet
 * @param packet Pointer to DAQPacket containing fused sensor data
 * @return Uncertainty score (0.0 to 1.0, where 0=certain, 1=uncertain)
 */
float uncertainty_update(const DAQPacket *packet) {
  if (packet == NULL) {
    return 0.5f;
  }

  // Extract key features from canonical DAQPacket struct fields
  float voltage = packet->electrical.bus_voltage_v;
  float tof = packet->ultrasonic.time_of_flight_us;
  float temp_rise = packet->thermal.temperature_c - 25.0f;

  // Add to circular buffers
  recent_voltage_values[buffer_index] = voltage;
  recent_tof_values[buffer_index] = tof;
  recent_temp_values[buffer_index] = temp_rise;

  buffer_index = (buffer_index + 1) % 50;
  if (sample_count < sample_size) {
    sample_count++;
  }

  uint8_t effective_count = (sample_count < sample_size) ? sample_count : sample_size;
  if (effective_count < 2) {
    last_combined_uncertainty = 0.5f;
    return last_combined_uncertainty;
  }

  float voltage_mean = 0.0f;
  float tof_mean = 0.0f;
  float temp_mean = 0.0f;

  uint8_t start_index = (buffer_index + 50 - effective_count) % 50;

  for (uint8_t i = 0; i < effective_count; i++) {
    uint8_t idx = (start_index + i) % 50;
    voltage_mean += recent_voltage_values[idx];
    tof_mean += recent_tof_values[idx];
    temp_mean += recent_temp_values[idx];
  }

  voltage_mean /= (float)effective_count;
  tof_mean /= (float)effective_count;
  temp_mean /= (float)effective_count;

  float voltage_uncertainty = calculate_uncertainty(recent_voltage_values, start_index, effective_count, voltage_mean);
  float tof_uncertainty = calculate_uncertainty(recent_tof_values, start_index, effective_count, tof_mean);
  float temp_uncertainty = calculate_uncertainty(recent_temp_values, start_index, effective_count, temp_mean);

  const float voltage_weight = 0.40f;
  const float tof_weight = 0.35f;
  const float temp_weight = 0.25f;

  last_combined_uncertainty =
    voltage_uncertainty * voltage_weight +
    tof_uncertainty * tof_weight +
    temp_uncertainty * temp_weight;

  return last_combined_uncertainty;
}

/**
 * @brief Get current uncertainty estimate
 * @return Current uncertainty score (0.0 to 1.0)
 */
float uncertainty_get(void) {
  if (sample_count < 2) {
    return 0.5f;
  }
  return last_combined_uncertainty;
}

/**
 * @brief Reset uncertainty estimation history
 */
void uncertainty_reset(void) {
  sample_count = 0;
  electrical_uncertainty_sum = 0.0f;
  ultrasonic_uncertainty_sum = 0.0f;
  thermal_uncertainty_sum = 0.0f;
  buffer_index = 0;
  last_combined_uncertainty = 0.5f;

  for (int i = 0; i < 50; i++) {
    recent_voltage_values[i] = 0.0f;
    recent_tof_values[i] = 0.0f;
    recent_temp_values[i] = 0.0f;
  }
}