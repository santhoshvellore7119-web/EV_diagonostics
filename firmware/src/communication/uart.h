/**
 * @file uart.h
 * @brief UART communication interface
 */

#ifndef UART_H
#define UART_H

#include <Arduino.h>
#include <stdint.h>

/**
 * @brief Initialize UART (serial) communication
 * @param baud_rate Baud rate for UART (default 115200)
 */
void uart_init(uint32_t baud_rate = 115200);

/**
 * @brief Send binary data over UART
 * @param data Pointer to data to send
 * @param length Length of data in bytes
 */
void uart_send_binary(const void *data, size_t length);

/**
 * @brief Send string over UART (null-terminated)
 * @param str Null-terminated string to send
 */
void uart_send_string(const char *str);

#endif // UART_H