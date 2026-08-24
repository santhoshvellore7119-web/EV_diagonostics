/**
 * @file usb.cpp
 * @brief USB communication implementation (USB CDC)
 *
 * Note: For ESP32, the USB CDC is handled by the Arduino core when built for USB.
 * We assume the board is configured for USB CDC (e.g., ESP32-S2, ESP32-S3, or ESP32 with USB OTG).
 * The initialization is done in the Arduino core, so our init function may be empty.
 * However, we provide the functions for consistency.
 */

#include "usb.h"

void usb_init(void) {
  // USB CDC initialization is typically handled by the Arduino core.
  // If we need to wait for USB to be ready, we can do:
  // while (!Serial) { ; } // But note: Serial is also used for UART in our code.
  // We have two CDC ports? Actually, in ESP32 with USB, the Serial is the USB CDC.
  // We are using Serial for UART in the uart.cpp, which is confusing.
  // Let's clarify: We intend to have two separate communication channels:
  //   - UART (hardware serial) for debugging or wired communication
  //   - USB CDC for connection to a host computer
  // However, in the Arduino ESP32 core, the 'Serial' object is the USB CDC when the board
  // is built with USB support. If we want to use the hardware UART, we need to use
  // Serial1, Serial2, etc.
  // We'll change the UART to use Serial1 (if available) and keep Serial for USB CDC.
  // But to keep the code simple and configurable, we'll assume:
  //   - UART (wired) uses Serial1 (if defined) or we can make it configurable.
  //   - USB CDC uses Serial.
  // However, the original main.cpp used Serial.begin for debugging and then used uart_send and usb_send.
  // We must adjust: Let's change the UART to use Serial1 and USB to use Serial.
  // But note: Not all ESP32 boards have multiple UARTs. We'll make it configurable via a macro.
  // For now, we'll assume the board has at least two UARTs (UART0 and UART1) and we use:
  //   - UART0 (Serial) for USB CDC
  //   - UART1 (Serial1) for wired UART
  // We'll change the uart.cpp to use Serial1 and usb.cpp to use Serial.
  // However, in the main.cpp we called Serial.begin(115200) and then used uart_send and usb_send.
  // We must change the main.cpp to initialize both? Actually, we can leave the initialization
  // to the respective modules.
  // Let's change the main.cpp later if needed. For now, we'll implement usb.cpp to use Serial.
  // And we'll change uart.cpp to use Serial1 (if available) or we can make it a parameter.
  // Since we are in a controlled environment, we'll assume Serial1 is available for UART.
  // If not, we can fall back to Serial and note that USB and UART share the same port (not ideal).
  // We'll do:
  //   usb_init: nothing (Serial.begin is called in main.cpp or we can call it here)
  //   uart_init: initialize Serial1
  // But note: the main.cpp currently calls Serial.begin(115200) and then we have separate
  // uart_init and usb_init. We must adjust main.cpp to not call Serial.begin if we are
  // going to use it for USB and then have uart use Serial1.
  // Let's change the main.cpp to remove the Serial.begin and let each module initialize its own port.
  // However, for simplicity in this step, we'll assume:
  //   - USB CDC: Serial (and we call Serial.begin in usb_init)
  //   - UART: Serial1 (and we call Serial1.begin in uart_init)
  // We'll change the main.cpp accordingly in a moment.
  // For now, we leave usb_init empty and rely on the main.cpp to have initialized Serial.
  // But to be safe, we'll call Serial.begin in usb_init if not already done.
  // We cannot know if it's done, so we'll just call it. Calling begin multiple times is harmless.
  Serial.begin(115200);
}

void usb_send_binary(const void *data, size_t length) {
  Serial.write((const uint8_t *)data, length);
}

void usb_send_string(const char *str) {
  Serial.print(str);
}