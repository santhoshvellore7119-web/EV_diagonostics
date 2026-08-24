/**
 * @file uart.cpp
 * @brief UART communication implementation
 */

#include "uart.h"

void uart_init(uint32_t baud_rate) {
  Serial.begin(baud_rate);
  // Wait for serial to be ready (optional)
  while (!Serial) { ; }
}

void uart_send_binary(const void *data, size_t length) {
  Serial.write((const uint8_t *)data, length);
}

void uart_send_string(const char *str) {
  Serial.print(str);
}