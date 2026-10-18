"""
common/drive_cycles.py
======================
Standardized Automotive Drive Cycle Profiles for EV Battery Research & Benchmarking.

Implements standard testing profiles according to SAE / EPA / UNECE specifications:
1. WLTP Class 3b (Worldwide Harmonised Light Vehicles Test Procedure):
   - Low, Medium, High, and Extra-High speed phases.
   - Normalized power-to-current mapping for standard 21700 / 18650 cylindrical cells.
2. US06 (Supplemental Federal Test Procedure):
   - High-acceleration, aggressive highway driving with heavy regenerative braking.
3. UDDS (Urban Dynamometer Driving Schedule / EPA FTP-72):
   - City driving profile with frequent stops and starts.
4. Pulse Discharge (HPPC - Hybrid Pulse Power Characterization):
   - Standard 10s discharge pulse, 40s rest, 10s regen pulse at varying SOC levels.

References:
  - UNECE Global Technical Regulation No. 15 (WLTP).
  - EPA 40 CFR Appendix I to Part 86 (Dynamometer Drive Schedules).
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import numpy as np


@dataclass
class DriveCycleProfile:
    """Encapsulates a standard drive cycle time series and cell load current."""
    name: str
    duration_s: float
    dt: float
    time_s: np.ndarray
    speed_kmh: np.ndarray
    current_a: np.ndarray        # Positive = discharge, Negative = regenerative braking
    c_rate: np.ndarray           # Normalized C-rate
    total_ah_discharged: float
    total_ah_regenerated: float
    peak_discharge_current_a: float
    peak_regen_current_a: float


def generate_wltp_class3_profile(
    cell_nominal_ah: float = 5.0,
    dt: float = 1.0,
    scale_factor: float = 1.0,
    seed: int = 42
) -> DriveCycleProfile:
    """
    Generates a normalized 1800-second WLTP Class 3b drive cycle for single-cell evaluation.
    
    Phases:
      - Low (0 - 589 s): Urban driving, max speed 56.5 km/h.
      - Medium (589 - 1022 s): Suburban driving, max speed 76.6 km/h.
      - High (1022 - 1477 s): Rural driving, max speed 97.4 km/h.
      - Extra-High (1477 - 1800 s): Motorway driving, max speed 131.3 km/h.
    """
    duration = 1800.0
    time = np.arange(0.0, duration, dt, dtype=np.float64)
    n_pts = len(time)

    # Analytical piece-wise velocity curve approximating WLTP Class 3b speed profile [km/h]
    speed = np.zeros(n_pts, dtype=np.float64)
    rng = np.random.default_rng(seed)

    for i, t in enumerate(time):
        if t < 589.0:
            # Low Phase: Multiple start-stop micro-trips
            v = 28.0 * (1.0 - np.cos(2.0 * np.pi * t / 118.0)) * (0.6 + 0.4 * np.sin(2.0 * np.pi * t / 295.0))
            speed[i] = max(0.0, min(56.5, v))
        elif t < 1022.0:
            # Medium Phase: Flowing suburban traffic
            t_rel = t - 589.0
            v = 38.0 * (1.0 - np.cos(2.0 * np.pi * t_rel / 216.5)) * (0.8 + 0.2 * np.sin(t_rel / 40.0))
            speed[i] = max(0.0, min(76.6, v))
        elif t < 1477.0:
            # High Phase: Highway cruising with sustained speed
            t_rel = t - 1022.0
            v = 48.0 * (1.0 - np.cos(2.0 * np.pi * t_rel / 455.0)) * (0.9 + 0.1 * np.cos(t_rel / 70.0))
            speed[i] = max(0.0, min(97.4, v))
        else:
            # Extra-High Phase: High-speed motorway segment
            t_rel = t - 1477.0
            v = 65.0 * (1.0 - np.cos(2.0 * np.pi * t_rel / 323.0))
            speed[i] = max(0.0, min(131.3, v))

    # Add realistic micro-accelerations (traffic jitter)
    speed_jitter = gaussian_smooth(rng.normal(0.0, 1.2, n_pts), sigma=3.0)
    speed = np.maximum(0.0, speed + np.where(speed > 5.0, speed_jitter, 0.0))

    # Convert vehicle speed profile to traction power and cell current
    # Traction load: P = m * v * a + 0.5 * rho * Cd * A * v^3 + Crr * m * g * v
    v_mps = speed / 3.6
    accel = np.gradient(v_mps, dt)

    # Normalized specific power per cell [W / cell]
    # Standard EV: ~1500 kg vehicle, 400 V / 100 Ah pack (~96S20P = 1920 cells)
    p_aero = 0.5 * 1.225 * 0.28 * 2.2 * (v_mps ** 3) / 1920.0
    p_roll = 0.012 * 1500.0 * 9.81 * v_mps / 1920.0
    p_inertial = 1500.0 * v_mps * accel / 1920.0
    p_aux = 1.2  # 1.2 W auxiliary load per cell (HVAC, BMS electronics)

    p_cell = (p_aero + p_roll + p_inertial + p_aux) * scale_factor

    # Regenerative braking capture efficiency: 75% for moderate braking, 0% for mechanical cutoff
    current_a = np.zeros(n_pts, dtype=np.float64)
    v_nominal_cell = 3.70  # Nominal cell voltage

    for i in range(n_pts):
        if p_cell[i] >= 0.0:
            # Discharge
            current_a[i] = p_cell[i] / v_nominal_cell
        else:
            # Regenerative braking charge (negative current)
            regen_limit = -1.5 * cell_nominal_ah  # Max 1.5C regen charge
            i_regen = (p_cell[i] * 0.75) / v_nominal_cell
            current_a[i] = max(regen_limit, i_regen)

    c_rate = current_a / cell_nominal_ah

    # Calculate Ah metrics
    dt_hours = dt / 3600.0
    ah_discharged = float(np.sum(current_a[current_a > 0.0]) * dt_hours)
    ah_regenerated = float(np.sum(np.abs(current_a[current_a < 0.0])) * dt_hours)

    return DriveCycleProfile(
        name="WLTP_Class_3b",
        duration_s=duration,
        dt=dt,
        time_s=time,
        speed_kmh=speed,
        current_a=current_a,
        c_rate=c_rate,
        total_ah_discharged=ah_discharged,
        total_ah_regenerated=ah_regenerated,
        peak_discharge_current_a=float(np.max(current_a)),
        peak_regen_current_a=float(np.min(current_a)),
    )


def generate_us06_profile(
    cell_nominal_ah: float = 5.0,
    dt: float = 1.0,
    scale_factor: float = 1.0,
    seed: int = 101
) -> DriveCycleProfile:
    """
    Generates an aggressive 600-second US06 Supplemental Federal Test Procedure profile.
    Characterized by rapid accelerations, high cruising speeds (up to 130 km/h),
    and intense regenerative braking peaks.
    """
    duration = 600.0
    time = np.arange(0.0, duration, dt, dtype=np.float64)
    n_pts = len(time)
    rng = np.random.default_rng(seed)

    # Multi-harmonic synthetic US06 speed envelope
    v_base = 65.0 * (1.0 - np.cos(2.0 * np.pi * time / duration))
    v_accel_spikes = 35.0 * np.sin(4.0 * np.pi * time / duration) * np.sin(10.0 * np.pi * time / duration)
    speed = np.clip(v_base + v_accel_spikes, 0.0, 129.2)

    v_mps = speed / 3.6
    accel = np.gradient(v_mps, dt)

    p_aero = 0.5 * 1.225 * 0.30 * 2.3 * (v_mps ** 3) / 1920.0
    p_roll = 0.015 * 1600.0 * 9.81 * v_mps / 1920.0
    p_inertial = 1600.0 * v_mps * accel / 1920.0
    p_aux = 1.8

    p_cell = (p_aero + p_roll + p_inertial + p_aux) * scale_factor

    current_a = np.zeros(n_pts, dtype=np.float64)
    v_nominal_cell = 3.70

    for i in range(n_pts):
        if p_cell[i] >= 0.0:
            current_a[i] = p_cell[i] / v_nominal_cell
        else:
            i_regen = (p_cell[i] * 0.80) / v_nominal_cell
            current_a[i] = max(-2.5 * cell_nominal_ah, i_regen)

    c_rate = current_a / cell_nominal_ah
    dt_hours = dt / 3600.0
    ah_discharged = float(np.sum(current_a[current_a > 0.0]) * dt_hours)
    ah_regenerated = float(np.sum(np.abs(current_a[current_a < 0.0])) * dt_hours)

    return DriveCycleProfile(
        name="US06_Aggressive_Highway",
        duration_s=duration,
        dt=dt,
        time_s=time,
        speed_kmh=speed,
        current_a=current_a,
        c_rate=c_rate,
        total_ah_discharged=ah_discharged,
        total_ah_regenerated=ah_regenerated,
        peak_discharge_current_a=float(np.max(current_a)),
        peak_regen_current_a=float(np.min(current_a)),
    )


def generate_hppc_pulse_profile(
    cell_nominal_ah: float = 5.0,
    dt: float = 0.1,
    discharge_c_rate: float = 1.0,
    regen_c_rate: float = 0.75,
) -> DriveCycleProfile:
    """
    Generates a standardized Hybrid Pulse Power Characterization (HPPC) profile:
      - 0 to 10s: Constant current discharge pulse (1.0C).
      - 10 to 50s: Open circuit relaxation period (0 A).
      - 50 to 60s: Regenerative charging pulse (-0.75C).
      - 60 to 120s: Extended thermal/polarization relaxation (0 A).
    """
    duration = 120.0
    time = np.arange(0.0, duration, dt, dtype=np.float64)
    n_pts = len(time)
    current_a = np.zeros(n_pts, dtype=np.float64)

    i_dis = discharge_c_rate * cell_nominal_ah
    i_reg = -regen_c_rate * cell_nominal_ah

    for idx, t in enumerate(time):
        if 0.0 <= t < 10.0:
            current_a[idx] = i_dis
        elif 10.0 <= t < 50.0:
            current_a[idx] = 0.0
        elif 50.0 <= t < 60.0:
            current_a[idx] = i_reg
        else:
            current_a[idx] = 0.0

    c_rate = current_a / cell_nominal_ah
    dt_hours = dt / 3600.0
    ah_discharged = float(np.sum(current_a[current_a > 0.0]) * dt_hours)
    ah_regenerated = float(np.sum(np.abs(current_a[current_a < 0.0])) * dt_hours)

    return DriveCycleProfile(
        name="HPPC_Pulse_Characterization",
        duration_s=duration,
        dt=dt,
        time_s=time,
        speed_kmh=np.zeros(n_pts),
        current_a=current_a,
        c_rate=c_rate,
        total_ah_discharged=ah_discharged,
        total_ah_regenerated=ah_regenerated,
        peak_discharge_current_a=float(np.max(current_a)),
        peak_regen_current_a=float(np.min(current_a)),
    )


def generate_udds_profile(
    cell_nominal_ah: float = 5.0,
    dt: float = 1.0,
    scale_factor: float = 1.0,
    seed: int = 2026
) -> DriveCycleProfile:
    """
    Generates a 1369-second EPA Urban Dynamometer Driving Schedule (UDDS / FTP-72) profile.
    Simulates urban city driving with 18 distinct start-stop cycles, moderate accelerations,
    and extensive idle periods (representing traffic signals). Max speed: 91.2 km/h.
    """
    duration = 1369.0
    time = np.arange(0.0, duration, dt, dtype=np.float64)
    n_pts = len(time)
    rng = np.random.default_rng(seed)

    speed = np.zeros(n_pts, dtype=np.float64)
    for idx, t in enumerate(time):
        # Piecewise urban stop-go velocity profile with traffic idling
        cycle_phase = (t % 152.0)
        if cycle_phase < 25.0:
            speed[idx] = 0.0  # Idling at red signal
        elif cycle_phase < 80.0:
            speed[idx] = 45.0 * np.sin(np.pi * (cycle_phase - 25.0) / 55.0)
        elif cycle_phase < 100.0:
            speed[idx] = 0.0  # Brief stop
        else:
            speed[idx] = 68.0 * (1.0 - np.cos(2.0 * np.pi * (cycle_phase - 100.0) / 52.0)) * 0.5

    # Highway burst in second half (EPA hill climbing phase)
    highway_mask = (time >= 505.0) & (time <= 850.0)
    t_hw = time[highway_mask] - 505.0
    speed[highway_mask] = np.maximum(speed[highway_mask], 91.2 * np.sin(np.pi * t_hw / 345.0))

    # Add realistic micro-dynamics
    jitter = gaussian_smooth(rng.normal(0.0, 0.8, n_pts), sigma=2.5)
    speed = np.clip(speed + np.where(speed > 3.0, jitter, 0.0), 0.0, 91.2)

    v_mps = speed / 3.6
    accel = np.gradient(v_mps, dt)

    p_aero = 0.5 * 1.225 * 0.29 * 2.2 * (v_mps ** 3) / 1920.0
    p_roll = 0.012 * 1550.0 * 9.81 * v_mps / 1920.0
    p_inertial = 1550.0 * v_mps * accel / 1920.0
    p_aux = 1.3  # Urban electronics/AC load

    p_cell = (p_aero + p_roll + p_inertial + p_aux) * scale_factor
    current_a = np.zeros(n_pts, dtype=np.float64)
    v_nominal_cell = 3.70

    for i in range(n_pts):
        if p_cell[i] >= 0.0:
            current_a[i] = p_cell[i] / v_nominal_cell
        else:
            i_regen = (p_cell[i] * 0.72) / v_nominal_cell
            current_a[i] = max(-1.8 * cell_nominal_ah, i_regen)

    c_rate = current_a / cell_nominal_ah
    dt_hours = dt / 3600.0
    ah_discharged = float(np.sum(current_a[current_a > 0.0]) * dt_hours)
    ah_regenerated = float(np.sum(np.abs(current_a[current_a < 0.0])) * dt_hours)

    return DriveCycleProfile(
        name="UDDS_Urban_Dynamometer",
        duration_s=duration,
        dt=dt,
        time_s=time,
        speed_kmh=speed,
        current_a=current_a,
        c_rate=c_rate,
        total_ah_discharged=ah_discharged,
        total_ah_regenerated=ah_regenerated,
        peak_discharge_current_a=float(np.max(current_a)),
        peak_regen_current_a=float(np.min(current_a)),
    )


def gaussian_smooth(arr: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    """1D Gaussian convolution smoothing kernel."""
    radius = int(np.ceil(3.0 * sigma))
    x = np.arange(-radius, radius + 1)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= np.sum(kernel)
    return np.convolve(arr, kernel, mode="same")
