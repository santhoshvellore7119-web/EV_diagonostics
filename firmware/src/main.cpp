/**
 * @file main.cpp
 * @brief Main firmware for Low-Cost Multi-Modal Diagnostic and Active Cell-Rebalancing System
 *
 * This firmware implements:
 * 1. Precision timer-triggered excitation pulse generation with adaptive control
 * 2. High-speed ADC/ultrasonic pulse-echo trigger-and-capture
 * 3. Continuous I2C/SPI polling for electrical and thermal telemetry
 * 4. Binary serialization/JSON packet streaming over UART/USB
 * 5. Uncertainty-based adaptive excitation pulse control
 *
 * Target MCU: ESP32 with FreeRTOS
 */

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include "sensors/electrical.h"
#include "sensors/ultrasonic.h"
#include "sensors/thermal.h"
#include "daq/daq.h"
#include "communication/uart.h"
#include "communication/usb.h"
#include "utils/timer.h"
#include "utils/serializer.h"
#include "utils/uncertainty.h"

// Task handles
TaskHandle_t electricalTaskHandle = NULL;
TaskHandle_t ultrasonicTaskHandle = NULL;
TaskHandle_t thermalTaskHandle = NULL;
TaskHandle_t daqTaskHandle = NULL;
TaskHandle_t communicationTaskHandle = NULL;
TaskHandle_t adaptiveControlTaskHandle = NULL;  // New task for adaptive control

// Queues for inter-task communication
QueueHandle_t electricalDataQueue;
QueueHandle_t ultrasonicDataQueue;
QueueHandle_t thermalDataQueue;
QueueHandle_t daqOutputQueue;
QueueHandle_t uncertaintyQueue;  // Queue for uncertainty values

// Global configuration
const uint32_t SAMPLE_RATE_HZ = 100000; // 100 kHz sampling
uint32_t EXCITATION_PULSE_WIDTH_US = 10; // 10 us pulse (will be adapted)
uint32_t EXCITATION_PERIOD_MS = 100; // 10 Hz excitation (will be adapted)
const uint8_t EXCITATION_PIN = 27; // GPIO pin for excitation pulse

// Adaptive control parameters
const float UNCERTAINTY_THRESHOLD_LOW = 0.3;    // Below this, decrease pulse width/period
const float UNCERTAINTY_THRESHOLD_HIGH = 0.7;   // Above this, increase pulse width/period
const uint32_t MIN_PULSE_WIDTH_US = 5;          // Minimum pulse width
const uint32_t MAX_PULSE_WIDTH_US = 50;         // Maximum pulse width
const uint32_t MIN_PERIOD_MS = 50;              // Minimum period (20 Hz max)
const uint32_t MAX_PERIOD_MS = 500;             // Maximum period (2 Hz min)
const uint32_t ADAPTIVE_CONTROL_INTERVAL_MS = 500; // How often to adjust parameters

// For tracking excitation control state
static uint32_t last_adjustment_time = 0;

/**
 * @brief Task for adaptive excitation control
 * Adjusts excitation parameters based on uncertainty estimation
 */
void adaptiveControlTask(void *parameter) {
  TickType_t lastWakeTime = xTaskGetTickCount();
  const TickType_t interval = pdMS_TO_TICKS(ADAPTIVE_CONTROL_INTERVAL_MS);

  for (;;) {
    // Wait for the interval or until notified
    vTaskDelayUntil(&lastWakeTime, interval);

    // Skip if not enough time has passed (protection against early wakeups)
    if ((xTaskGetTickCount() - lastWakeTime) < (interval / 2)) {
      continue;
    }

    // Get current uncertainty estimate
    float uncertainty = uncertainty_get();

    // Adapt excitation parameters based on uncertainty
    uint32_t new_pulse_width_us = EXCITATION_PULSE_WIDTH_US;
    uint32_t new_period_ms = EXCITATION_PERIOD_MS;

    if (uncertainty < UNCERTAINTY_THRESHOLD_LOW) {
      // Low uncertainty - we can use shorter pulses and less frequent excitation
      // to reduce wear on battery while still getting good data
      new_pulse_width_us = (uint32_t)(EXCITATION_PULSE_WIDTH_US * 0.8);  // Decrease by 20%
      new_period_ms = (uint32_t)(EXCITATION_PERIOD_MS * 1.2);           // Increase period by 20%
    } else if (uncertainty > UNCERTAINTY_THRESHOLD_HIGH) {
      // High uncertainty - we need more/better data, so increase pulse width
      #ifdef DEBUG
      // Serial.print("High uncertainty: "); Serial.println(uncertainty, 3);
      #endif
      new_pulse_width_us = (uint32_t)(EXCITATION_PULSE_WIDTH_US * 1.2);  // Increase by 20%
      new_period_ms = (uint32_t)(EXCITATION_PERIOD_MS * 0.8);           // Decrease period by 20%
    }

    // Apply bounds
    new_pulse_width_us = constrain(new_pulse_width_us, MIN_PULSE_WIDTH_US, MAX_PULSE_WIDTH_US);
    new_period_ms = constrain(new_period_ms, MIN_PERIOD_MS, MAX_PERIOD_MS);

    // Only update if changed significantly (to reduce timer reconfiguration overhead)
    if (abs((int)new_pulse_width_us - (int)EXCITATION_PULSE_WIDTH_US) >= 2 ||
        abs((int)new_period_ms - (int)EXCITATION_PERIOD_MS) >= 10) {

      #ifdef DEBUG
      // Serial.print("Adapting excitation: ");
      // Serial.print("PW: "); Serial.print(EXCITATION_PULSE_WIDTH_US); Serial.print("->"); Serial.print(new_pulse_width_us);
      // Serial.print(" us, Period: "); Serial.print(EXCITATION_PERIOD_MS); Serial.print("->"); Serial.print(new_period_ms);
      // Serial.print(" ms, Uncertainty: "); Serial.println(uncertainty, 3);
      #endif

      // Update global variables
      EXCITATION_PULSE_WIDTH_US = new_pulse_width_us;
      EXCITATION_PERIOD_MS = new_period_ms;

      // Update timer configuration
      timer_update_excitation(EXCITATION_PERIOD_MS, EXCITATION_PULSE_WIDTH_US);

      last_adjustment_time = xTaskGetTickCount();
    }
  }
}

/**
 * @brief Task for electrical sensing (current/voltage via INA226)
 */
void electricalTask(void *parameter) {
  ElectricalData data;
  TickType_t lastWakeTime = xTaskGetTickCount();

  for (;;) {
    // Wait for excitation pulse trigger (from timer interrupt or task notification)
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

    // Sample electrical data
    electrical_sample(&data);

    // Send to queue
    xQueueOverwrite(electricalDataQueue, &data);

    // Delay until next cycle (if needed)
    vTaskDelayUntil(&lastWakeTime, pdMS_TO_TICKS(10));
  }
}

/**
 * @brief Task for ultrasonic pulse-echo sensing
 */
void ultrasonicTask(void *parameter) {
  UltrasonicData data;
  TickType_t lastWakeTime = xTaskGetTickCount();

  for (;;) {
    // Wait for excitation pulse trigger
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

    // Trigger ultrasonic pulse and capture echo
    ultrasonic_sample(&data);

    // Send to queue
    xQueueOverwrite(ultrasonicDataQueue, &data);

    vTaskDelayUntil(&lastWakeTime, pdMS_TO_TICKS(10));
  }
}

/**
 * @brief Task for thermal sensing (contact array or IR thermopile)
 */
void thermalTask(void *parameter) {
  ThermalData data;
  TickType_t lastWakeTime = xTaskGetTickCount();

  for (;;) {
    // Wait for excitation pulse trigger
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

    // Sample thermal data
    thermal_sample(&data);

    // Send to queue
    xQueueOverwrite(thermalDataQueue, &data);

    vTaskDelayUntil(&lastWakeTime, pdMS_TO_TICKS(10));
  }
}

/**
 * @brief DAQ task to fuse sensor data and create packets
 * Also calculates uncertainty for adaptive control
 */
void daqTask(void *parameter) {
  ElectricalData elecData;
  UltrasonicData ultraData;
  ThermalData thermData;
  DAQPacket packet;
  TickType_t lastWakeTime = xTaskGetTickCount();

  for (;;) {
    // Wait for all sensor data (with timeout)
    if (xQueueReceive(electricalDataQueue, &elecData, pdMS_TO_TICKS(5)) == pdPASS &&
        xQueueReceive(ultrasonicDataQueue, &ultraData, pdMS_TO_TICKS(5)) == pdPASS &&
        xQueueReceive(thermalDataQueue, &thermData, pdMS_TO_TICKS(5)) == pdPASS) {

      // Fuse data into packet
      daq_create_packet(&elecData, &ultraData, &thermData, &packet);

      // Send to communication queue
      xQueueOverwrite(daqOutputQueue, &packet);

      #ifdef DEBUG
      // Uncertainty calculation for debugging (could be enabled via compile flag)
      // float uncertainty = uncertainty_get();
      // Serial.print("DAQ Packet - Uncertainty: "); Serial.println(uncertainty, 3);
      #endif
    }

    vTaskDelayUntil(&lastWakeTime, pdMS_TO_TICKS(10));
  }
}

/**
 * @brief Communication task to stream data over UART/USB
 */
void communicationTask(void *parameter) {
  DAQPacket packet;
  TickType_t lastWakeTime = xTaskGetTickCount();

  for (;;) {
    // Wait for DAQ packet
    if (xQueueReceive(daqOutputQueue, &packet, pdMS_TO_TICKS(10)) == pdPASS) {
      // Stream as binary
      uart_send_binary(&packet, sizeof(DAQPacket));
      usb_send_binary(&packet, sizeof(DAQPacket));

      // Also send as JSON for debugging (optional)
      char jsonBuffer[256];
      serializer_to_json(&packet, jsonBuffer, sizeof(jsonBuffer));
      uart_send_string(jsonBuffer);
      usb_send_string(jsonBuffer);
    }

    vTaskDelayUntil(&lastWakeTime, pdMS_TO_TICKS(20));
  }
}

/**
 * @brief Timer interrupt service routine for excitation pulse generation
 *
 * This ISR triggers the excitation pulse and notifies the sensing tasks.
 */
void IRAM_ATTR timer_isr() {
  // Trigger excitation pulse (hardware trigger)
  trigger_excitation_pulse();

  // Notify all sensing tasks to sample
  BaseType_t higherPriorityTaskWoken = pdFALSE;
  vTaskNotifyGiveFromISR(electricalTaskHandle, &higherPriorityTaskWoken);
  vTaskNotifyGiveFromISR(ultrasonicTaskHandle, &higherPriorityTaskWoken);
  vTaskNotifyGiveFromISR(thermalTaskHandle, &higherPriorityTaskWoken);
  portYIELD_FROM_ISR(higherPriorityTaskWoken);
}

void setup() {
  // Initialize serial for debugging
  Serial.begin(115200);
  while (!Serial) { ; } // Wait for serial port to connect (for USB CDC)

  // Initialize I2C and SPI
  Wire.begin();
  SPI.begin();

  // Initialize sensors
  electrical_init();
  ultrasonic_init(25, 26); // trigger pin 25, echo pin 26
  thermal_init();

  // Initialize DAQ
  daq_init();

  // Initialize communication
  uart_init(115200);
  usb_init();

  // Initialize uncertainty estimation
  uncertainty_init(10);  // Use last 10 samples for uncertainty calculation

  // Create queues
  electricalDataQueue = xQueueCreate(10, sizeof(ElectricalData));
  ultrasonicDataQueue = xQueueCreate(10, sizeof(UltrasonicData));
  thermalDataQueue = xQueueCreate(10, sizeof(ThermalData));
  daqOutputQueue = xQueueCreate(10, sizeof(DAQPacket));

  // Create tasks
  xTaskCreatePinnedToCore(electricalTask, "ElectricalTask", 4096, NULL, 2, &electricalTaskHandle, 0);
  xTaskCreatePinnedToCore(ultrasonicTask, "UltrasonicTask", 4096, NULL, 2, &ultrasonicTaskHandle, 0);
  xTaskCreatePinnedToCore(thermalTask, "ThermalTask", 4096, NULL, 2, &thermalTaskHandle, 0);
  xTaskCreatePinnedToCore(daqTask, "DAQTask", 4096, NULL, 3, &daqTaskHandle, 0);
  xTaskCreatePinnedToCore(communicationTask, "CommunicationTask", 4096, NULL, 1, &communicationTaskHandle, 1);
  xTaskCreatePinnedToCore(adaptiveControlTask, "AdaptiveCtrlTask", 2048, NULL, 2, &adaptiveControlTaskHandle, 0);

  // Start timer for excitation pulse generation
  timer_init_excitation(EXCITATION_PERIOD_MS, EXCITATION_PULSE_WIDTH_US, EXCITATION_PIN);
}

void loop() {
  // Main loop does nothing; all work is done in tasks
  vTaskDelay(portMAX_DELAY);
}