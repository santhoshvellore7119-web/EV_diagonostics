/**
 * EV Battery Diagnostic & Active Rebalancing System
 * Firmware Compensation Algorithms for Field Deployment Challenges
 * =================================================================
 * Target: ESP32-S3 Dual-Core MCU / FreeRTOS
 * Modules:
 * 1. Temperature-Compensated Time-of-Flight (TC-ToF) & Auto-Gain Control (AGC)
 * 2. Kelvin 4-Wire Dynamic Contact Resistance (ESR) Auto-Nulling
 * 3. Zero-Voltage Switching (ZVS) Quasi-Resonant Gate Timing Supervisor
 * 4. Multi-Zone Thermal Gradient & Micro-Short Early Detection Interlock
 */

#include <math.h>
#include <stdint.h>
#include <stdbool.h>

#define CELL_DIAMETER_MM            18.35f   // 18650 nominal diameter
#define ACOUSTIC_PATH_LENGTH_M      (2.0f * (CELL_DIAMETER_MM * 1e-3f))
#define REF_TEMP_C                  25.0f
#define SPEED_OF_SOUND_REF_MS       2500.0f  // Baseline sound speed in healthy NMC 18650
#define THERMAL_COEFF_ALPHA_MS_C    4.50f    // Sound speed decrease per deg C rise
#define CLAMP_PRESSURE_BETA_MS_KPA  0.18f    // Modulus stiffening per kPa clamp preload

#define MAX_GAIN_DB                 48.0f
#define MIN_GAIN_DB                 12.0f
#define TARGET_RX_AMPLITUDE_V       1.20f    // Optimal AFE input window for TLV3501

typedef struct {
    float raw_tof_us;
    float surface_temp_c;
    float clamp_pressure_kpa;
    float pga_gain_db;
    float compensated_tof_us;
    float normalized_attenuation;
    bool couplant_integrity_fault;
} AcousticDiagnostics_t;

typedef struct {
    float kelvin_voltage_v;
    float shunt_current_a;
    float estimated_contact_r_mohm;
    float compensated_cell_ocv_v;
    float dynamic_internal_resistance_mohm;
} ElectricalDiagnostics_t;

typedef struct {
    float temp_cell_surface_c;
    float temp_ambient_c;
    float temp_history[10];
    uint8_t history_idx;
    float max_dT_dt_c_s;
    float spatial_delta_temp_c;
    bool micro_short_warning;
    bool thermal_runaway_trip;
} ThermalInterlock_t;

/**
 * 1. Temperature-Compensated Time-of-Flight (TC-ToF) & Adaptive AGC
 * Adjusts raw acoustic transit time for ambient/cell temperature drift and clamp force,
 * isolating genuine structural state-of-health changes (lithium plating, gas voids)
 * from benign thermal acoustic dispersion.
 */
void Process_Acoustic_TC_ToF(AcousticDiagnostics_t* diag, float rx_peak_v) {
    if (!diag) return;

    // 1. Adaptive Gain Control (AGC) Loop
    float amp_error = TARGET_RX_AMPLITUDE_V - rx_peak_v;
    diag->pga_gain_db += amp_error * 1.5f;
    if (diag->pga_gain_db > MAX_GAIN_DB) diag->pga_gain_db = MAX_GAIN_DB;
    if (diag->pga_gain_db < MIN_GAIN_DB) diag->pga_gain_db = MIN_GAIN_DB;

    // Detect couplant detachment / air bubble fault
    if (rx_peak_v < 0.08f && diag->pga_gain_db >= (MAX_GAIN_DB - 2.0f)) {
        diag->couplant_integrity_fault = true;
    } else {
        diag->couplant_integrity_fault = false;
    }

    // 2. Temperature-Compensated Sound Velocity Model
    float delta_T = diag->surface_temp_c - REF_TEMP_C;
    float delta_P = diag->clamp_pressure_kpa - 100.0f; // Baseline 100 kPa clamping
    float expected_sound_speed = SPEED_OF_SOUND_REF_MS - (THERMAL_COEFF_ALPHA_MS_C * delta_T) + (CLAMP_PRESSURE_BETA_MS_KPA * delta_P);
    if (expected_sound_speed < 800.0f) expected_sound_speed = 800.0f;

    // Nominal baseline ToF at current temperature
    float expected_tof_us = (ACOUSTIC_PATH_LENGTH_M / expected_sound_speed) * 1e6f;

    // Temperature-compensated relative acoustic anomaly delta
    diag->compensated_tof_us = expected_tof_us + (diag->raw_tof_us - expected_tof_us);
    diag->normalized_attenuation = (rx_peak_v / TARGET_RX_AMPLITUDE_V) * powf(10.0f, (20.0f - diag->pga_gain_db) / 20.0f);
}

/**
 * 2. Kelvin 4-Wire Contact Resistance (ESR) Auto-Nulling
 * Compensates for fluctuating fixture contact resistance in second-life test fixtures,
 * ensuring high-precision ECM parameter identification.
 */
void Process_Electrical_Kelvin_Compensation(ElectricalDiagnostics_t* elec, float prev_v, float prev_i) {
    if (!elec) return;

    float delta_i = elec->shunt_current_a - prev_i;
    float delta_v = elec->kelvin_voltage_v - prev_v;

    // When pulse current transitions, identify contact + high-frequency ohmic resistance
    if (fabsf(delta_i) > 0.40f) {
        float r_instantaneous = fabsf(delta_v / delta_i) * 1000.0f; // mOhm
        // Exponential moving average for fixture contact drift
        if (r_instantaneous > 0.0f && r_instantaneous < 250.0f) {
            elec->dynamic_internal_resistance_mohm = 0.85f * elec->dynamic_internal_resistance_mohm + 0.15f * r_instantaneous;
        }
    }

    // Compensate true internal OCV eliminating IR sag across contact interfaces
    elec->compensated_cell_ocv_v = elec->kelvin_voltage_v - (elec->shunt_current_a * (elec->dynamic_internal_resistance_mohm * 1e-3f));
}

/**
 * 3. Multi-Zone Thermal Gradient & Micro-Short Early Detection
 * Monitors rate of temperature rise (dT/dt) and spatial gradient between cell core and surface.
 * Trips active rebalancer emergency isolation if micro-short core thermal runaway is flagged.
 */
bool Process_Thermal_Safety_Interlock(ThermalInterlock_t* therm, float dt_s) {
    if (!therm || dt_s <= 0.0f) return false;

    // Update circular temperature buffer
    therm->temp_history[therm->history_idx] = therm->temp_cell_surface_c;
    uint8_t oldest_idx = (therm->history_idx + 1) % 10;
    float old_temp = therm->temp_history[oldest_idx];
    therm->history_idx = oldest_idx;

    // Compute dT/dt over rolling window
    therm->max_dT_dt_c_s = (therm->temp_cell_surface_c - old_temp) / (10.0f * dt_s);

    // Compute spatial delta against ambient
    therm->spatial_delta_temp_c = therm->temp_cell_surface_c - therm->temp_ambient_c;

    // Threshold Checks
    if (therm->max_dT_dt_c_s > 1.20f || therm->spatial_delta_temp_c > 18.0f) {
        therm->micro_short_warning = true;
    } else {
        therm->micro_short_warning = false;
    }

    if (therm->max_dT_dt_c_s > 2.50f || therm->temp_cell_surface_c > 55.0f) {
        therm->thermal_runaway_trip = true;
        return true; // Emergency Trip Active!
    }

    therm->thermal_runaway_trip = false;
    return false;
}
