/**
 * @file freertos_multi_task_supervisor.c
 * @brief FreeRTOS Real-Time Supervisor implementation for 4S Active Balancing
 *        and Multi-Modal Ultrasonic / Electrical / Thermal Diagnostics.
 */

#include "freertos_multi_task_supervisor.h"
#include <string.h>
#include <math.h>

/* Safety Trip Bitmask Flags */
#define TRIP_OVERVOLTAGE      (1U << 0)
#define TRIP_UNDERVOLTAGE     (1U << 1)
#define TRIP_OVERTEMPERATURE  (1U << 2)
#define TRIP_TOF_GAS_ANOMALY  (1U << 3)
#define TRIP_CURRENT_OVERLOAD (1U << 4)

void bms_supervisor_init(BmsSupervisorContext_t *ctx) {
    if (!ctx) return;
    memset(ctx, 0, sizeof(BmsSupervisorContext_t));

    for (uint8_t i = 0; i < NUM_SERIES_CELLS; ++i) {
        ctx->cells[i].cell_id = i + 1;
        ctx->cells[i].voltage_v = 3.70f;
        ctx->cells[i].current_a = 0.0f;
        ctx->cells[i].temperature_c = 25.0f;
        ctx->cells[i].ultrasonic_tof_s = 8.0e-6f;
        ctx->cells[i].ultrasonic_amplitude_v = 1.0f;
        ctx->cells[i].internal_resistance_mOhm = 25.0f;
        ctx->cells[i].state_of_charge = 0.50f;
        ctx->cells[i].state_of_health = 1.00f;
        ctx->cells[i].detected_fault = DEG_MODE_HEALTHY;
        ctx->cells[i].balancer_state = BALANCER_IDLE;
        ctx->cells[i].balancing_current_target_a = 0.0f;
        ctx->cells[i].timestamp_ms = 0;
    }

    ctx->pack_voltage_v = 3.70f * NUM_SERIES_CELLS;
    ctx->pack_current_a = 0.0f;
    ctx->max_cell_temp_c = 25.0f;
    ctx->max_soc_divergence = 0.0f;
    ctx->donor_cell_idx = 0;
    ctx->recipient_cell_idx = 0;
    ctx->emergency_tripped = false;
    ctx->safety_trip_flags = 0;
    ctx->cycle_count = 0;
}

bool bms_supervisor_check_safety_limits(BmsSupervisorContext_t *ctx) {
    if (!ctx) return false;

    uint32_t flags = 0;
    float max_temp = -100.0f;
    float pack_v = 0.0f;

    for (uint8_t i = 0; i < NUM_SERIES_CELLS; ++i) {
        CellTelemetry_t *cell = &ctx->cells[i];
        pack_v += cell->voltage_v;

        if (cell->temperature_c > max_temp) {
            max_temp = cell->temperature_c;
        }

        /* Check voltage bounds */
        if (cell->voltage_v > CELL_VOLTAGE_MAX_LIMIT_V) {
            flags |= TRIP_OVERVOLTAGE;
        }
        if (cell->voltage_v < CELL_VOLTAGE_MIN_LIMIT_V) {
            flags |= TRIP_UNDERVOLTAGE;
        }

        /* Check temperature limits */
        if (cell->temperature_c > CELL_TEMP_MAX_LIMIT_C) {
            flags |= TRIP_OVERTEMPERATURE;
        }

        /* Check ToF acoustic gas/plating anomaly */
        if (cell->ultrasonic_tof_s > 8.5e-6f || cell->ultrasonic_amplitude_v < 0.15f) {
            flags |= TRIP_TOF_GAS_ANOMALY;
        }
    }

    ctx->pack_voltage_v = pack_v;
    ctx->max_cell_temp_c = max_temp;
    ctx->safety_trip_flags = flags;

    if (flags != 0) {
        ctx->emergency_tripped = true;
        for (uint8_t i = 0; i < NUM_SERIES_CELLS; ++i) {
            ctx->cells[i].balancer_state = BALANCER_EMERGENCY_SHUTDOWN;
            ctx->cells[i].balancing_current_target_a = 0.0f;
        }
        return false; /* Safety trip active */
    }

    ctx->emergency_tripped = false;
    return true; /* All parameters normal */
}

void bms_supervisor_update_cell_telemetry(BmsSupervisorContext_t *ctx, uint8_t cell_idx,
                                         float v, float i, float temp, float tof, float amp) {
    if (!ctx || cell_idx >= NUM_SERIES_CELLS) return;

    CellTelemetry_t *cell = &ctx->cells[cell_idx];
    cell->voltage_v = v;
    cell->current_a = i;
    cell->temperature_c = temp;
    cell->ultrasonic_tof_s = tof;
    cell->ultrasonic_amplitude_v = amp;

    /* Estimate SOC based on OCV polynomial approximation */
    float soc_est = (v - 3.20f) / (4.20f - 3.20f);
    if (soc_est < 0.0f) soc_est = 0.0f;
    if (soc_est > 1.0f) soc_est = 1.0f;
    cell->state_of_charge = soc_est;

    /* Diagnose degradation mode based on multimodal signatures */
    if (temp > 50.0f && v > 4.10f) {
        cell->detected_fault = DEG_MODE_THERMAL_RUNAWAY_RISK;
    } else if (tof > 8.12e-6f && amp < 0.40f) {
        cell->detected_fault = DEG_MODE_ELECTROLYTE_DECOMPOSITION;
    } else if (tof < 7.95e-6f && cell->internal_resistance_mOhm > 35.0f) {
        cell->detected_fault = DEG_MODE_LITHIUM_PLATING;
    } else if (cell->internal_resistance_mOhm > 45.0f) {
        cell->detected_fault = DEG_MODE_SEI_GROWTH;
    } else {
        cell->detected_fault = DEG_MODE_HEALTHY;
    }
}

void bms_supervisor_compute_zvs_rebalancing_targets(BmsSupervisorContext_t *ctx) {
    if (!ctx || ctx->emergency_tripped) return;

    uint8_t max_soc_idx = 0;
    uint8_t min_soc_idx = 0;
    float max_soc = -1.0f;
    float min_soc = 2.0f;

    for (uint8_t i = 0; i < NUM_SERIES_CELLS; ++i) {
        float s = ctx->cells[i].state_of_charge;
        if (s > max_soc) {
            max_soc = s;
            max_soc_idx = i;
        }
        if (s < min_soc) {
            min_soc = s;
            min_soc_idx = i;
        }
        ctx->cells[i].balancer_state = BALANCER_IDLE;
        ctx->cells[i].balancing_current_target_a = 0.0f;
    }

    float delta_soc = max_soc - min_soc;
    ctx->max_soc_divergence = delta_soc;
    ctx->donor_cell_idx = max_soc_idx;
    ctx->recipient_cell_idx = min_soc_idx;

    /* Rebalancing deadband: trigger only if delta SOC > 1.5% */
    if (delta_soc > 0.015f && max_soc_idx != min_soc_idx) {
        /* Proportional current allocation up to MAX_BALANCING_CURRENT_A */
        float target_i = (delta_soc / 0.10f) * MAX_BALANCING_CURRENT_A;
        if (target_i > MAX_BALANCING_CURRENT_A) {
            target_i = MAX_BALANCING_CURRENT_A;
        }

        ctx->cells[max_soc_idx].balancer_state = BALANCER_DISCHARGE_DONOR;
        ctx->cells[max_soc_idx].balancing_current_target_a = target_i;

        ctx->cells[min_soc_idx].balancer_state = BALANCER_CHARGE_RECIPIENT;
        ctx->cells[min_soc_idx].balancing_current_target_a = target_i;
    }
}

void bms_supervisor_apply_pwm_deadtime(uint16_t pwm_period_ticks, uint16_t *dt_high_ticks, uint16_t *dt_low_ticks) {
    /* For a 240 MHz clock with 100 kHz PWM (period = 2400 ticks), 25 ns = 6 ticks */
    uint16_t dead_time_ticks = (uint16_t)((DEAD_TIME_NS * 240) / 1000);
    if (dead_time_ticks < 4) dead_time_ticks = 4;

    if (dt_high_ticks) {
        *dt_high_ticks = dead_time_ticks;
    }
    if (dt_low_ticks) {
        *dt_low_ticks = dead_time_ticks;
    }
}

/* FreeRTOS Tasks Implementations (FreeRTOS API hooks) */
void Task_FastDAQ(void *pvParameters) {
    BmsSupervisorContext_t *ctx = (BmsSupervisorContext_t *)pvParameters;
    if (!ctx) return;
    /* 100 Hz sampling loop */
    ctx->cycle_count++;
}

void Task_ZVSControl(void *pvParameters) {
    BmsSupervisorContext_t *ctx = (BmsSupervisorContext_t *)pvParameters;
    if (!ctx) return;
    bms_supervisor_compute_zvs_rebalancing_targets(ctx);
}

void Task_SafetySupervisor(void *pvParameters) {
    BmsSupervisorContext_t *ctx = (BmsSupervisorContext_t *)pvParameters;
    if (!ctx) return;
    bms_supervisor_check_safety_limits(ctx);
}

void Task_TelemetryStream(void *pvParameters) {
    (void)pvParameters;
}
