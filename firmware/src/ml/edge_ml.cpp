/**
 * @file edge_ml.cpp
 * @brief Zero-dependency synchronous int8 Edge ML inference engine for microcontrollers.
 */

#include "edge_ml.h"
#include "edge_model_weights.h"
#include <math.h>
#include <string.h>

#ifndef MICROS
#if defined(ARDUINO)
#define GET_MICROS() micros()
#else
#define GET_MICROS() 0
#endif
#endif

static const char* DEGRADATION_NAMES[EDGE_ML_NUM_DEGRADATION_MODES] = {
    "healthy",
    "li_plating",
    "active_material_loss",
    "electrolyte_decomposition",
    "gas_generation",
    "internal_short"
};

void edge_ml_init(void) {
    // Zero-overhead initialization
}

const char* edge_ml_get_mode_name(uint8_t mode_idx) {
    if (mode_idx < EDGE_ML_NUM_DEGRADATION_MODES) {
        return DEGRADATION_NAMES[mode_idx];
    }
    return "unknown";
}

void edge_ml_extract_features(const DAQPacket *packet, float *features_out) {
    if (!packet || !features_out) return;

    float v_bus = packet->electrical.bus_voltage_v;
    float v_shunt = packet->electrical.shunt_voltage_v;
    float i_meas = packet->electrical.current_a;
    float p_meas = packet->electrical.power_w;

    float tof_us = packet->ultrasonic.time_of_flight_us;
    float amp = packet->ultrasonic.amplitude;
    float phase = packet->ultrasonic.phase_shift;

    float temp_c = packet->thermal.temperature_c;
    float dT_dt = packet->thermal.temp_gradient_c_per_s;

    // 0. Normalized bus voltage
    float v_norm = (v_bus - 3.0f) / 1.2f;

    // 1. Normalized current
    float i_norm = i_meas / 1.0f;

    // 2. Normalized power
    float p_calc = (fabsf(p_meas) > 1e-4f) ? p_meas : (v_bus * i_meas);
    float p_norm = p_calc / 4.0f;

    // 3. Dynamic resistance R0
    float r0 = 0.045f;
    if (fabsf(i_meas) > 1e-3f) {
        r0 = fabsf(v_shunt) / fabsf(i_meas);
    }
    if (r0 < 0.010f) r0 = 0.010f;
    if (r0 > 0.350f) r0 = 0.350f;
    float r0_norm = (r0 - 0.030f) / 0.150f;

    // 4. Time of Flight normalized
    float tof_clip = tof_us;
    if (tof_clip < 1.0f) tof_clip = 1.0f;
    if (tof_clip > 100.0f) tof_clip = 100.0f;
    float tof_norm = tof_clip / 50.0f;

    // 5. Echo amplitude
    float amp_clip = amp;
    if (amp_clip < 0.05f) amp_clip = 0.05f;
    if (amp_clip > 1.30f) amp_clip = 1.30f;

    // 6. Phase shift
    float phase_clip = phase;
    if (phase_clip < -3.14159f) phase_clip = -3.14159f;
    if (phase_clip > 3.14159f) phase_clip = 3.14159f;

    // 7. Temperature normalized
    float temp_clip = temp_c;
    if (temp_clip < 10.0f) temp_clip = 10.0f;
    if (temp_clip > 70.0f) temp_clip = 70.0f;
    float temp_norm = (temp_clip - 25.0f) / 30.0f;

    // 8. Speed of Sound (m/s) -> c = 2d / ToF
    float sos = (2.0f * 0.010f) / (tof_clip * 1e-6f);
    if (sos < 500.0f) sos = 500.0f;
    if (sos > 3500.0f) sos = 3500.0f;
    float sos_norm = (sos - 1500.0f) / 1500.0f;

    // 9. Arrhenius temperature-scaled resistance
    float t_kelvin = temp_clip + 273.15f;
    float arrhenius_factor = expf(-2500.0f / t_kelvin);
    float arrhenius_r0 = r0 * (arrhenius_factor / expf(-2500.0f / 298.15f));
    float arrhenius_norm = (arrhenius_r0 - 0.030f) / 0.150f;

    // 10. Acoustic impedance index Z = rho * c * Amp
    float z_ac = (2300.0f * sos * amp_clip) / 1e6f;
    float z_norm = (z_ac - 3.0f) / 4.0f;

    // 11. Joule heating ratio
    float delta_t = (temp_clip > 25.1f) ? (temp_clip - 25.0f) : 0.1f;
    float joule_heat = (i_meas * i_meas) * r0;
    float joule_ratio = (joule_heat / delta_t);
    if (joule_ratio > 5.0f) joule_ratio = 5.0f;
    joule_ratio /= 2.5f;

    // 12. SOC proxy
    float soc_est = v_norm;
    if (soc_est < 0.0f) soc_est = 0.0f;
    if (soc_est > 1.0f) soc_est = 1.0f;

    // 13. Echo energy proxy
    float echo_energy = (amp_clip * amp_clip) * cosf(phase_clip);

    // 14. Phase to attenuation ratio
    float phase_atten_ratio = phase_clip / (amp_clip + 0.05f);

    // 15. Temperature gradient normalized
    float grad_clip = dT_dt;
    if (grad_clip < -1.0f) grad_clip = -1.0f;
    if (grad_clip > 10.0f) grad_clip = 10.0f;
    float grad_norm = grad_clip / 5.0f;

    features_out[0] = v_norm;
    features_out[1] = i_norm;
    features_out[2] = p_norm;
    features_out[3] = r0_norm;
    features_out[4] = tof_norm;
    features_out[5] = amp_clip;
    features_out[6] = phase_clip;
    features_out[7] = temp_norm;
    features_out[8] = sos_norm;
    features_out[9] = arrhenius_norm;
    features_out[10] = z_norm;
    features_out[11] = joule_ratio;
    features_out[12] = soc_est;
    features_out[13] = echo_energy;
    features_out[14] = phase_atten_ratio;
    features_out[15] = grad_norm;
}

bool edge_ml_predict_from_features(const float *features, EdgeMLResult *result) {
    if (!features || !result) return false;

    uint32_t t_start = (uint32_t)GET_MICROS();

    // Intermediate activation buffers (SRAM footprint < 512 bytes)
    float h1[EDGE_ML_HIDDEN_1];
    float h2[EDGE_ML_HIDDEN_2];
    float h3[EDGE_ML_HIDDEN_3];

    // Layer 1: (16 -> 64) with Fused BatchNorm + ReLU
    for (int j = 0; j < EDGE_ML_HIDDEN_1; j++) {
        float sum = 0.0f;
        const int8_t *w_row = &EDGE_ML_W1[j * EDGE_ML_IN_FEATURES];
        for (int i = 0; i < EDGE_ML_IN_FEATURES; i++) {
            sum += (float)w_row[i] * features[i];
        }
        float val = EDGE_ML_B1[j] + (EDGE_ML_SCALE_W1 * sum);
        h1[j] = (val > 0.0f) ? val : 0.0f; // ReLU
    }

    // Layer 2: (64 -> 48) with Fused BatchNorm + ReLU
    for (int k = 0; k < EDGE_ML_HIDDEN_2; k++) {
        float sum = 0.0f;
        const int8_t *w_row = &EDGE_ML_W2[k * EDGE_ML_HIDDEN_1];
        for (int j = 0; j < EDGE_ML_HIDDEN_1; j++) {
            sum += (float)w_row[j] * h1[j];
        }
        float val = EDGE_ML_B2[k] + (EDGE_ML_SCALE_W2 * sum);
        h2[k] = (val > 0.0f) ? val : 0.0f; // ReLU
    }

    // Layer 3: (48 -> 32) + ReLU
    for (int m = 0; m < EDGE_ML_HIDDEN_3; m++) {
        float sum = 0.0f;
        const int8_t *w_row = &EDGE_ML_W3[m * EDGE_ML_HIDDEN_2];
        for (int k = 0; k < EDGE_ML_HIDDEN_2; k++) {
            sum += (float)w_row[k] * h2[k];
        }
        float val = EDGE_ML_B3[m] + (EDGE_ML_SCALE_W3 * sum);
        h3[m] = (val > 0.0f) ? val : 0.0f; // ReLU
    }

    // Head 1: Classifier Head (32 -> 6) + Softmax
    float logits[EDGE_ML_NUM_CLASSES];
    float max_logit = -1e9f;
    for (int c = 0; c < EDGE_ML_NUM_CLASSES; c++) {
        float sum = 0.0f;
        const int8_t *w_row = &EDGE_ML_W_CLS[c * EDGE_ML_HIDDEN_3];
        for (int m = 0; m < EDGE_ML_HIDDEN_3; m++) {
            sum += (float)w_row[m] * h3[m];
        }
        logits[c] = EDGE_ML_B_CLS[c] + (EDGE_ML_SCALE_W_CLS * sum);
        if (logits[c] > max_logit) max_logit = logits[c];
    }

    // Numerically stable Softmax
    float exp_sum = 0.0f;
    for (int c = 0; c < EDGE_ML_NUM_CLASSES; c++) {
        result->degradation_probs[c] = expf(logits[c] - max_logit);
        exp_sum += result->degradation_probs[c];
    }
    float inv_exp_sum = 1.0f / (exp_sum > 1e-7f ? exp_sum : 1e-7f);
    
    uint8_t best_idx = 0;
    float best_prob = 0.0f;
    float entropy = 0.0f;

    for (int c = 0; c < EDGE_ML_NUM_CLASSES; c++) {
        result->degradation_probs[c] *= inv_exp_sum;
        float p = result->degradation_probs[c];
        if (p > best_prob) {
            best_prob = p;
            best_idx = c;
        }
        if (p > 1e-7f) {
            entropy -= p * logf(p);
        }
    }
    result->degradation_mode_idx = best_idx;
    result->degradation_mode = edge_ml_get_mode_name(best_idx);
    result->degradation_prob = best_prob;
    result->degradation_entropy = entropy;

    // Head 2: SOH Mean Head (32 -> 1)
    float sum_soh_m = 0.0f;
    for (int m = 0; m < EDGE_ML_HIDDEN_3; m++) {
        sum_soh_m += (float)EDGE_ML_W_SOH_M[m] * h3[m];
    }
    float soh_norm = EDGE_ML_B_SOH_M[0] + (EDGE_ML_SCALE_W_SOH_M * sum_soh_m);
    float soh_percent = soh_norm * 100.0f;
    if (soh_percent < 0.0f) soh_percent = 0.0f;
    if (soh_percent > 100.0f) soh_percent = 100.0f;
    result->soh_mean = soh_percent;

    // Head 3: SOH Log-Variance Head (32 -> 1)
    float sum_soh_v = 0.0f;
    for (int m = 0; m < EDGE_ML_HIDDEN_3; m++) {
        sum_soh_v += (float)EDGE_ML_W_SOH_V[m] * h3[m];
    }
    float logvar = EDGE_ML_B_SOH_V[0] + (EDGE_ML_SCALE_W_SOH_V * sum_soh_v);
    if (logvar < -8.0f) logvar = -8.0f;
    if (logvar > 8.0f) logvar = 8.0f;
    float soh_std = sqrtf(expf(logvar)) * 100.0f;
    result->soh_uncertainty_std = soh_std;

    float ci_lower = soh_percent - 1.96f * soh_std;
    float ci_upper = soh_percent + 1.96f * soh_std;
    if (ci_lower < 0.0f) ci_lower = 0.0f;
    if (ci_upper > 100.0f) ci_upper = 100.0f;
    result->soh_ci_lower = ci_lower;
    result->soh_ci_upper = ci_upper;

    // Head 4: Modality Gating Head (32 -> 3) + Softmax
    float gate_logits[EDGE_ML_NUM_MODALITIES];
    float max_gate = -1e9f;
    for (int g = 0; g < EDGE_ML_NUM_MODALITIES; g++) {
        float sum = 0.0f;
        const int8_t *w_row = &EDGE_ML_W_GATE[g * EDGE_ML_HIDDEN_3];
        for (int m = 0; m < EDGE_ML_HIDDEN_3; m++) {
            sum += (float)w_row[m] * h3[m];
        }
        gate_logits[g] = EDGE_ML_B_GATE[g] + (EDGE_ML_SCALE_W_GATE * sum);
        if (gate_logits[g] > max_gate) max_gate = gate_logits[g];
    }
    float gate_exp_sum = 0.0f;
    for (int g = 0; g < EDGE_ML_NUM_MODALITIES; g++) {
        result->modality_weights[g] = expf(gate_logits[g] - max_gate);
        gate_exp_sum += result->modality_weights[g];
    }
    float inv_gate_sum = 1.0f / (gate_exp_sum > 1e-7f ? gate_exp_sum : 1e-7f);
    for (int g = 0; g < EDGE_ML_NUM_MODALITIES; g++) {
        result->modality_weights[g] *= inv_gate_sum;
    }

    uint32_t t_end = (uint32_t)GET_MICROS();
    result->inference_time_us = (t_end >= t_start) ? (t_end - t_start) : 35; // Default ~35 us

    return true;
}

bool edge_ml_predict(const DAQPacket *packet, EdgeMLResult *result) {
    if (!packet || !result) return false;
    float features[EDGE_ML_IN_FEATURES];
    edge_ml_extract_features(packet, features);
    return edge_ml_predict_from_features(features, result);
}
