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

  // Reset buffers
  sample_count = 0;
  electrical_uncertainty_sum = 0.0f;
  ultrasonic_uncertainty_sum = 0.0f;
  thermal_uncertainty_sum = 0.0f;
  buffer_index = 0;

  // Clear buffers
  for (int i = 0; i < 50; i++) {
    recent_voltage_values[i] = 0.0f;
    recent_tof_values[i] = 0.0f;
    recent_temp_values[i] = 0.0f;
  }
}

/**
 * @brief Calculate uncertainty based on variance of recent measurements
 * @param values Array of recent values
 * @param count Number of valid values in array
 * @param mean_value Mean of the values (for normalization)
 * @return Uncertainty score (0.0 to 1.0)
 */
static float calculate_uncertainty(float* values, uint8_t count, float mean_value) {
  if (count < 2) {
    return 0.5f;  // High uncertainty when insufficient data
  }

  // Calculate variance
  float variance = 0.0f;
  for (uint8_t i = 0; i < count; i++) {
    float diff = values[i] - mean_value;
    variance += diff * diff;
  }
  variance /= count;

  // Normalize uncertainty (0-1 range)
  // Using a sigmoid-like function: uncertainty = 1 / (1 + exp(-k*variance))
  // where k controls sensitivity
  const float k = 10.0f;  // Sensitivity factor
  float uncertainty = 1.0f / (1.0f + exp(-k * variance));

  return uncertainty;
}

/**
 * @brief Update uncertainty estimation with new DAQ packet
 * @param packet Pointer to DAQPacket containing fused sensor data
 * @return Uncertainty score (0.0 to 1.0, where 0=certain, 1=uncertain)
 */
float uncertainty_update(const DAQPacket *packet) {
  if (packet == NULL) {
    return 0.5f;  // Default uncertainty for invalid packet
  }

  // Extract key features for uncertainty calculation
  float voltage = packet->electrical.bus_voltage_v;
  float tof = packet->ultrasonic.tof;
  float temp_rise = 0.0f;

  // Calculate average temperature rise from thermal data
  // For simplicity, we'll use the first few samples or a subset
  // In a real implementation, you'd compute the actual rise
  temp_rise = packet->thermal.temperature_rise;  // Simplified - use first sample

  // Add to circular buffers
  recent_voltage_values[buffer_index] = voltage;
  recent_tof_values[buffer_index] = tof;
  recent_temp_values[buffer_index] = temp_rise;

  buffer_index = (buffer_index + 1) % 50;
  if (sample_count < sample_size) {
    sample_count++;
  }

  // Calculate effective count for statistics
  uint8_t effective_count = (sample_count < sample_size) ? sample_count : sample_size;

  // Calculate means for recent values
  float voltage_mean = 0.0f;
  float tof_mean = 0.0f;
  float temp_mean = 0.0f;

  uint8_t start_index = (buffer_index >= sample_count) ? 0 : (buffer_index + 50 - sample_count) % 50;

  for (uint8_t i = 0; i < effective_count; i++) {
    uint8_t idx = (start_index + i) % 50;
    voltage_mean += recent_voltage_values[idx];
    tof_mean += recent_tof_values[idx];
    temp_mean += recent_temp_values[idx];
  }

  voltage_mean /= effective_count;
  tof_mean /= effective_count;
  temp_mean /= effective_count;

  // Calculate individual uncertainties
  float voltage_uncertainty = calculate_uncertainty(recent_voltage_values, effective_count, voltage_mean);
  float tof_uncertainty = calculate_uncertainty(recent_tof_values, effective_count, tof_mean);
  float temp_uncertainty = calculate_uncertainty(recent_temp_values, effective_count, temp_mean);

  #ifdef DEBUG
  // For debugging - you could enable this with a compile flag
  // Serial.print("Uncertainties - V: "); Serial.print(voltage_uncertainty, 3);
  // Serial.print(", ToF: "); Serial.print(tof_uncertainty, 3);
  // Serial.print(", T: "); Serial.println(temp_uncertainty, 3);
  #endif

  #else
  (void)voltage_uncertainty;  // Suppress unused variable warning in release
  (void)tof_uncertainty;
  (void)temp_uncertainty;
  #endif

  #ifdef DEBUG
  // For debugging - you could enable this with a compile flag
  // Serial.print("Uncertainties - V: "); Serial.print(voltage_uncertainty, 3);
  // Serial.print(", ToF: "); Serial.print(tof_uncertainty, 3);
  // Serial.print(", T: "); Serial.println(temp_uncertainty, 3);
  #endif

  // Combined uncertainty (weighted average)
  // Weights can be adjusted based on modality importance for degradation detection
  const float voltage_weight = 0.4;
  const float tof_weight = 0.35;
  const float temp_weight = 0.25;

  float combined_uncertainty =
    voltage_uncertainty * voltage_weight +
    tof_uncertainty * tof_weight +
    temp_uncertainty * temp_weight;

  return combined_uncertainty;
}

/**
 * @brief Get current uncertainty estimate
 * @return Current uncertainty score (0.0 to 1.0)
 */
float uncertainty_get(void) {
  // For simplicity, we'll return a default value if not enough samples
  // In a more sophisticated implementation, this would return the last calculated uncertainty
  if (sample_count < 2) {
    return 0.5f;  // High uncertainty until we have enough data
  }

  // This would ideally return the last calculated uncertainty from uncertainty_update
  // For this implementation, we'll recalculate based on current buffers
  // In practice, you'd store the last calculated value

  // Re-use the calculation logic from uncertainty_update but without updating buffers
  if (sample_count < 2) {
    return 0.5f;
  }

  uint8_t effective_count = (sample_count < sample_size) ? sample_count : sample_size;

  float voltage_mean = 0.0f;
  float tof_mean = 0.0f;
  float temp_mean = 0.0f;

  uint8_t start_index = (buffer_index >= sample_count) ? 0 : (buffer_index + 50 - sample_count) % 50;

  for (uint8_t i = 0; i < effective_count; i++) {
    uint8_t idx = (start_index + i) % 50;
    voltage_mean += recent_voltage_values[idx];
    tof_mean += recent_tof_values[idx];
    temp_mean += recent_temp_values[idx];
  }

  voltage_mean /= effective_count;
  tof_mean /= effective_count;
  temp_mean /= effective_count;

  float voltage_uncertainty = calculate_uncertainty(recent_voltage_values, effective_count, voltage_mean);
  float tof_uncertainty = calculate_uncertainty(recent_tof_values, effective_count, tof_mean);
  float temp_uncertainty = calculate_uncertainty(recent_temp_values, effective_count, temp_mean);

  // Combined uncertainty (weighted average)
  const float voltage_weight = 0.4;
  const float tof_weight = 0.35;
  const float temp_weight = 0.25;

  float combined_uncertainty =
    voltage_uncertainty * voltage_weight +
    tof_uncertainty * tof_weight +
    temp_uncertainty * temp_weight;

  return combined_uncertainty;
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

  // Clear buffers
  for (int i = 0; i < 50; i++) {
    recent_voltage_values[i] = 0.0f;
    recent_tof_values[i] = 0.0f;
    recent_temp_values[i] = 0.0f;
  }
}