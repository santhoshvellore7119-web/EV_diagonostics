/**
 * @file usb.h
 * @brief USB communication interface (USB CDC)
 */

#ifndef USB_H
#define USB_H

#include <Arduino.h>
#include <stdint.h>

/**
 * @brief Initialize USB CDC communication
 * @note This function assumes the board is configured for USB CDC (e.g., ESP32 with USB native)
 */
void usb_init(void);

/**
 * @brief Send binary data over USB CDC
 * @param data Pointer to data to send
 * @param length Length of data in bytes
 */
void usb_send_binary(const void *data, size_t length);

/**
 * @brief Send string over USB CDC (null-terminated)
 * @param str Null-terminated string to send
 */
void usb_send_string(const char *str);

#endif // USB_H