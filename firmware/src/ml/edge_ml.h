/**
 * @file edge_ml.h
 * @brief High-performance synchronous Edge ML diagnostic engine for MCU firmware.
 * @note Zero external dependencies. Designed for real-time synchronous execution in DAQ loop.
 */

#ifndef EDGE_ML_H
#define EDGE_ML_H

#include <stdint.h>
#include <stdbool.h>
#include "daq/daq.h"

#ifdef __cplusplus
extern "C" {
#endif

#define EDGE_ML_NUM_DEGRADATION_MODES 6

/**
 * @brief Result structure for on-device Edge ML inference
 */
typedef struct {
    float degradation_probs[EDGE_ML_NUM_DEGRADATION_MODES];
    uint8_t degradation_mode_idx;
    const char *degradation_mode;
    float degradation_prob;
    float degradation_entropy;
    
    float soh_mean;
    float soh_uncertainty_std;
    float soh_ci_lower;
    float soh_ci_upper;
    
    float modality_weights[3]; // 0: Electrical, 1: Ultrasonic, 2: Thermal
    uint32_t inference_time_us;
} EdgeMLResult;

/**
 * @brief Initialize Edge ML inference engine
 */
void edge_ml_init(void);

/**
 * @brief Extract 16 physical features from DAQPacket
 * @param[in] packet Input sensor DAQ packet
 * @param[out] features_out Array of at least 16 float elements
 */
void edge_ml_extract_features(const DAQPacket *packet, float *features_out);

/**
 * @brief Execute end-to-end inference directly on DAQPacket
 * @param[in] packet Input sensor DAQ packet
 * @param[out] result Output prediction and uncertainty estimates
 * @return true if inference succeeded, false otherwise
 */
bool edge_ml_predict(const DAQPacket *packet, EdgeMLResult *result);

/**
 * @brief Execute inference on pre-extracted 16-D feature vector
 * @param[in] features Input 16-D float array
 * @param[out] result Output prediction and uncertainty estimates
 * @return true if inference succeeded, false otherwise
 */
bool edge_ml_predict_from_features(const float *features, EdgeMLResult *result);

/**
 * @brief Get degradation mode name string from class index
 */
const char* edge_ml_get_mode_name(uint8_t mode_idx);

#ifdef __cplusplus
}
#endif

#endif // EDGE_ML_H
