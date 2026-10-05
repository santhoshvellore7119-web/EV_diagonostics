/**
 * @file freertos_multi_task_supervisor.h
 * @brief FreeRTOS Real-Time Supervisor for Multi-Modal EV Battery Diagnostics
 *        and Bidirectional Active Cell Rebalancing.
 *
 * Target: ESP32-S3 (Xtensa Dual-Core 240MHz) / FreeRTOS v10.4+
 * Features:
 *  - Core 0: High-Speed DAQ (100 Hz Ultrasonic ToF / INA226 ADC) & Safety Supervisor (1 kHz)
 *  - Core 1: Synchronous ZVS Active Balancing Control (100 kHz PWM) & Edge ML Inference
 */

#ifndef FREERTOS_MULTI_TASK_SUPERVISOR_H
#define FREERTOS_MULTI_TASK_SUPERVISOR_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

#define NUM_SERIES_CELLS            4
#define BALANCING_PWM_FREQ_HZ       100000UL   /* 100 kHz switching frequency */
#define DEAD_TIME_NS                25         /* ZVS zero-voltage switching dead time */
#define MAX_BALANCING_CURRENT_A     2.50f      /* Maximum continuous shuttling current */
#define CELL_VOLTAGE_MAX_LIMIT_V    4.25f      /* Overvoltage threshold */
#define CELL_VOLTAGE_MIN_LIMIT_V    2.70f      /* Undervoltage threshold */
#define CELL_TEMP_MAX_LIMIT_C       55.0f      /* Thermal runaway safety cutoff */
#define TOF_ANOMALY_DELTA_PS        25000.0f   /* 25 ns sudden shift indicates plating/gas */

/**
 * @brief Degradation mode enumeration matching Python and MATLAB pipelines.
 */
typedef enum {
    DEG_MODE_HEALTHY                  = 0,
    DEG_MODE_SEI_GROWTH               = 1,
    DEG_MODE_LITHIUM_PLATING          = 2,
    DEG_MODE_ELECTROLYTE_DECOMPOSITION= 3,
    DEG_MODE_ACTIVE_MATERIAL_LOSS     = 4,
    DEG_MODE_THERMAL_RUNAWAY_RISK     = 5
} DegradationMode_t;

/**
 * @brief Active rebalancing bridge mode.
 */
typedef enum {
    BALANCER_IDLE                     = 0,
    BALANCER_DISCHARGE_DONOR          = 1,
    BALANCER_CHARGE_RECIPIENT         = 2,
    BALANCER_EMERGENCY_SHUTDOWN       = 3
} BalancerState_t;

/**
 * @brief Multi-modal cell physical telemetry state structure.
 */
typedef struct {
    uint8_t cell_id;
    float voltage_v;
    float current_a;
    float temperature_c;
    float ultrasonic_tof_s;
    float ultrasonic_amplitude_v;
    float internal_resistance_mOhm;
    float state_of_charge;
    float state_of_health;
    DegradationMode_t detected_fault;
    BalancerState_t balancer_state;
    float balancing_current_target_a;
    uint32_t timestamp_ms;
} CellTelemetry_t;

/**
 * @brief System-wide supervisor state context.
 */
typedef struct {
    CellTelemetry_t cells[NUM_SERIES_CELLS];
    float pack_voltage_v;
    float pack_current_a;
    float max_cell_temp_c;
    float max_soc_divergence;
    uint8_t donor_cell_idx;
    uint8_t recipient_cell_idx;
    bool emergency_tripped;
    uint32_t safety_trip_flags;
    uint32_t cycle_count;
} BmsSupervisorContext_t;

/* System lifecycle and supervisor API */
void bms_supervisor_init(BmsSupervisorContext_t *ctx);
bool bms_supervisor_check_safety_limits(BmsSupervisorContext_t *ctx);
void bms_supervisor_update_cell_telemetry(BmsSupervisorContext_t *ctx, uint8_t cell_idx,
                                         float v, float i, float temp, float tof, float amp);
void bms_supervisor_compute_zvs_rebalancing_targets(BmsSupervisorContext_t *ctx);
void bms_supervisor_apply_pwm_deadtime(uint16_t pwm_period_ticks, uint16_t *dt_high_ticks, uint16_t *dt_low_ticks);

/* FreeRTOS Task function prototypes */
void Task_FastDAQ(void *pvParameters);
void Task_ZVSControl(void *pvParameters);
void Task_SafetySupervisor(void *pvParameters);
void Task_TelemetryStream(void *pvParameters);

#ifdef __cplusplus
}
#endif

#endif /* FREERTOS_MULTI_TASK_SUPERVISOR_H */
