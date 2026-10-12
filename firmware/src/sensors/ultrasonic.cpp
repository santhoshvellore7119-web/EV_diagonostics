/**
 * @file ultrasonic.cpp
 * @brief 1-2 MHz Ultrasonic pitch-catch sensing implementation via TI TDC7200 (55ps SPI ToF),
 *        AD8307 Logarithmic Envelope Detector (ADC), and TLV3501 Comparator.
 */

#include "ultrasonic.h"
#include <math.h>

// TI TDC7200 SPI Register Map
#define TDC7200_REG_CONFIG1       0x00
#define TDC7200_REG_CONFIG2       0x01
#define TDC7200_REG_INT_STATUS    0x02
#define TDC7200_REG_TIME1         0x10
#define TDC7200_REG_CLOCK_COUNT1  0x11
#define TDC7200_REG_CALIBRATION1  0x1B
#define TDC7200_REG_CALIBRATION2  0x1C

// TDC7200 External Reference Clock (8.0 MHz -> 125.0 ns period, 10 calibration periods)
#define TDC7200_REF_CLOCK_HZ      8000000.0f
#define TDC7200_CAL2_PERIODS      10.0f

static uint8_t triggerPin = 25;
static uint8_t echoPin = 26;
static bool tdc7200_present = false;

static volatile uint32_t pulseStartTimeUs = 0;
static volatile uint32_t echoArrivalTimeUs = 0;
static volatile bool echoReceived = false;
static volatile uint8_t firstArrivalPolarity = 1;

static void tdc7200_write_reg8(uint8_t reg, uint8_t val) {
  digitalWrite(TDC7200_CS_PIN, LOW);
  SPI.transfer((reg & 0x1F) | 0x40); // Write bit = 0x40
  SPI.transfer(val);
  digitalWrite(TDC7200_CS_PIN, HIGH);
}

static uint8_t tdc7200_read_reg8(uint8_t reg) {
  digitalWrite(TDC7200_CS_PIN, LOW);
  SPI.transfer(reg & 0x1F);
  uint8_t val = SPI.transfer(0x00);
  digitalWrite(TDC7200_CS_PIN, HIGH);
  return val;
}

static uint32_t tdc7200_read_reg24(uint8_t reg) {
  digitalWrite(TDC7200_CS_PIN, LOW);
  SPI.transfer(reg & 0x1F);
  uint32_t b2 = SPI.transfer(0x00);
  uint32_t b1 = SPI.transfer(0x00);
  uint32_t b0 = SPI.transfer(0x00);
  digitalWrite(TDC7200_CS_PIN, HIGH);
  return ((b2 << 16) | (b1 << 8) | b0) & 0x007FFFFF;
}

/**
 * @brief ISR for first-arrival STOP edge from TLV3501 high-speed comparator
 */
void IRAM_ATTR echoArrivalISR() {
  if (!echoReceived) {
    echoArrivalTimeUs = micros();
    firstArrivalPolarity = (uint8_t)digitalRead(TLV3501_PHASE_PIN);
    echoReceived = true;
  }
}

bool ultrasonic_init(uint8_t trigger_pin, uint8_t echo_pin) {
  triggerPin = trigger_pin;
  echoPin = echo_pin;

  pinMode(triggerPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(TLV3501_PHASE_PIN, INPUT);
  pinMode(AD8307_ENV_ADC_PIN, INPUT);
  digitalWrite(triggerPin, LOW);

  // Initialize TDC7200 SPI interface
  pinMode(TDC7200_CS_PIN, OUTPUT);
  pinMode(TDC7200_ENABLE_PIN, OUTPUT);
  pinMode(TDC7200_INT_PIN, INPUT_PULLUP);
  digitalWrite(TDC7200_CS_PIN, HIGH);
  digitalWrite(TDC7200_ENABLE_PIN, HIGH);
  delay(2);

  SPI.begin();
  // Configure TDC7200 Mode 2 (250 ns to 8 ms range, 10 clock calibration periods)
  tdc7200_write_reg8(TDC7200_REG_CONFIG2, 0x40);
  uint8_t readback = tdc7200_read_reg8(TDC7200_REG_CONFIG2);
  tdc7200_present = (readback == 0x40);

  // Attach rising-edge interrupt for comparator fallback timing & phase polarity capture
  attachInterrupt(digitalPinToInterrupt(echoPin), echoArrivalISR, RISING);

  return true;
}

void ultrasonic_sample(UltrasonicData *data) {
  if (!data) return;

  // Arm TDC7200 for new measurement cycle (START_MEAS = bit 0, Measurement Mode 2 = bit 1)
  if (tdc7200_present) {
    tdc7200_write_reg8(TDC7200_REG_INT_STATUS, 0x1F); // Clear status flags
    tdc7200_write_reg8(TDC7200_REG_CONFIG1, 0x03);    // Mode 2 + Start Measurement
  }

  echoReceived = false;
  pulseStartTimeUs = micros();

  // Generate 2.0 MHz excitation burst (4 cycles @ 500 ns period = 2 us burst via TC4420 gate driver)
  digitalWrite(triggerPin, HIGH);
  delayMicroseconds(2);
  digitalWrite(triggerPin, LOW);

  // Sample AD8307 logarithmic envelope output across arrival window (samples 0..15)
  // and late reverberation coda window (samples 16..31)
  uint16_t env_samples[32];
  uint16_t peak_adc = 0;
  uint8_t peak_idx = 0;
  for (uint8_t i = 0; i < 32; i++) {
    env_samples[i] = analogRead(AD8307_ENV_ADC_PIN);
    if (env_samples[i] > peak_adc && i < 18) {
      peak_adc = env_samples[i];
      peak_idx = i;
    }
    delayMicroseconds(1);
  }

  // Compute Time-of-Flight (us) from TDC7200 55ps registers if present
  float tof_us = 0.0f;
  if (tdc7200_present && digitalRead(TDC7200_INT_PIN) == LOW) {
    uint32_t time1 = tdc7200_read_reg24(TDC7200_REG_TIME1);
    uint32_t clk_cnt1 = tdc7200_read_reg24(TDC7200_REG_CLOCK_COUNT1);
    uint32_t cal1 = tdc7200_read_reg24(TDC7200_REG_CALIBRATION1);
    uint32_t cal2 = tdc7200_read_reg24(TDC7200_REG_CALIBRATION2);

    float cal_diff = (float)(cal2 > cal1 ? (cal2 - cal1) : 1);
    float cal_Count = cal_diff / (TDC7200_CAL2_PERIODS - 1.0f);
    float norm_lsb_us = (1.0e6f / TDC7200_REF_CLOCK_HZ) / (cal_Count > 1.0f ? cal_Count : 1.0f);
    tof_us = ((float)time1 * norm_lsb_us) + ((float)clk_cnt1 * (1.0e6f / TDC7200_REF_CLOCK_HZ));
  } else if (echoReceived && echoArrivalTimeUs >= pulseStartTimeUs) {
    // Hardware comparator edge timing (ToF = Arrival - Trigger Start, NOT pulse width)
    tof_us = (float)(echoArrivalTimeUs - pulseStartTimeUs);
  } else if (peak_adc > 180) {
    // Envelope peak arrival index fallback (1.25 us per sample step)
    tof_us = 3.2f + (float)peak_idx * 1.25f;
  } else {
    tof_us = 8.0f; // Nominal fallback for 10mm pouch cell at 2500 m/s round-trip
  }

  // Convert AD8307 log-amp ADC reading (12-bit 0..4095, 25 mV/dB slope) to normalized linear amplitude
  float v_env = ((float)peak_adc / 4095.0f) * 3.3f;
  // Calibrated mapping: 2.1V -> 1.00 healthy reference amplitude
  float amp_norm = (v_env > 0.25f) ? ((v_env - 0.25f) / 1.85f) : 0.85f;
  if (amp_norm < 0.05f) amp_norm = 0.05f;
  if (amp_norm > 1.30f) amp_norm = 1.30f;

  // Compute late reverberation coda energy ratio (gas generation multi-path scattering indicator)
  float main_energy = 1e-4f;
  float coda_energy = 0.0f;
  for (uint8_t i = 2; i < 16; i++) {
    float s = (float)env_samples[i] / 4095.0f;
    main_energy += s * s;
  }
  for (uint8_t i = 16; i < 32; i++) {
    float s = (float)env_samples[i] / 4095.0f;
    coda_energy += s * s;
  }
  float reverb_ratio = coda_energy / main_energy;

  // Phase shift from TLV3501 first-arrival polarity & acoustic impedance inversion
  // Metallic Li-plating or gas layer interface causes half-wave phase inversion
  float phase_rad = (firstArrivalPolarity == 0) ? -0.785398f : 0.0f;
  if (reverb_ratio > 0.38f) {
    phase_rad = 1.570796f; // Strong multi-path phase dispersion under gassing
  }

  data->time_of_flight_us = tof_us;
  data->amplitude = amp_norm;
  data->phase_shift = phase_rad;
  data->reverb_energy_ratio = reverb_ratio;
  data->timestamp_us = micros();
}