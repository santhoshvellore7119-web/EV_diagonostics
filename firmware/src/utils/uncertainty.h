/**
 * @file uncertainty.h
 * @brief Uncertainty estimation for adaptive excitation control
 */

#ifndef UNCERTAINTY_H
#define UNCERTAINTY_H

#include <Arduino.h>
#include "daq.h"

/**
 * @brief Initialize uncertainty estimation module
 * @param sample_size Number of recent samples to consider for uncertainty calculation
 */
void uncertainty_init(uint8_t sample_size = 10);

/**
 * @brief Update uncertainty estimation with new DAQ packet
 * @param packet Pointer to DAQPacket containing fused sensor data
 * @return Uncertainty score (0.0 to 1.0, where 0=certain, 1=uncertain)
 */
float uncertainty_update(const DAQPacket *packet);

/**
 * @brief Get current uncertainty estimate
 * @return Current uncertainty score (0.0 to 1.0)
 */
float uncertainty_get(void);

/**
 * @brief Reset uncertainty estimation history
 */
void uncertainty_reset(void);

#endif // UNCERTAINTY_H