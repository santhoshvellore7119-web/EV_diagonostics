"""
dual_ukf_joint_estimator.py

Production-Grade Dual-Unscented Kalman Filter (Dual-UKF) for Joint State and
Parameter Estimation of an EV Lithium-Ion Cell under a Dynamic US06 Drive Cycle.

Architecture:
1. Fast State UKF (10.0 Hz, dt = 0.1 s):
   - Estimates dynamic state vector x_k = [SOC, V_rc1, V_rc2]^T
2. Slow Parameter UKF (0.5 Hz, dt_theta = 2.0 s, every 20 state steps):
   - Estimates time-varying 2RC parameter vector theta_k = [R0, R1, C1, R2, C2]^T
3. Nonlinear Measurement Model:
   - V_terminal = OCV(SOC) - I_k * R0 - V_rc1 - V_rc2
   - 6th-order polynomial OCV(SOC) and exact analytical dOCV/dSOC
4. Numerical Robustness:
   - Van der Merwe scaled sigma points (alpha = 1e-3, beta = 2.0, kappa = 0.0)
   - Jitter-stabilized Cholesky square-root decomposition + Joseph-form covariance update
"""

from dataclasses import dataclass
from typing import Tuple, Dict, Optional, List, Any
import json
import numpy as np
from scipy.linalg import cholesky, LinAlgError


# ==============================================================================
# 1. 6th-Order OCV Polynomial & Derivative Functions
# ==============================================================================

class OCVPolynomialModel:
    """
    6th-Order Polynomial Open-Circuit Voltage (OCV) Model for an NMC/Graphite EV Cell:
      OCV(s) = c6*s^6 + c5*s^5 + c4*s^4 + c3*s^3 + c2*s^2 + c1*s + c0
    """
    COEFFS = np.array([
        -4.8512,   # s^6
        15.9240,   # s^5
        -20.1850,  # s^4
        12.4210,   # s^3
        -3.5820,   # s^2
        0.9985,    # s^1
        3.4250,    # s^0
    ], dtype=np.float64)

    D_COEFFS = np.polyder(COEFFS)

    @classmethod
    def ocv(cls, soc: np.ndarray | float) -> np.ndarray | float:
        """Evaluates 6th-order polynomial OCV(SOC) [V] with safe domain clamping."""
        s = np.clip(soc, 0.001, 0.999)
        return np.polyval(cls.COEFFS, s)

    @classmethod
    def docv_dsoc(cls, soc: np.ndarray | float) -> np.ndarray | float:
        """Evaluates exact analytical derivative dOCV/dSOC [V / unit SOC]."""
        s = np.clip(soc, 0.001, 0.999)
        return np.polyval(cls.D_COEFFS, s)


# ==============================================================================
# 2. Van der Merwe Scaled Sigma Point Generator & Matrix PSD Safeguards
# ==============================================================================

@dataclass
class MerweSigmaWeights:
    """Van der Merwe scaled sigma point parameters and weight vectors."""
    n_dim: int
    alpha: float = 1e-3
    beta: float = 2.0
    kappa: float = 0.0

    def __post_init__(self) -> None:
        L = float(self.n_dim)
        self.lam = (self.alpha ** 2) * (L + self.kappa) - L
        self.gamma = np.sqrt(L + self.lam)

        n_sigma = 2 * self.n_dim + 1
        self.wm = np.full(n_sigma, 1.0 / (2.0 * (L + self.lam)), dtype=np.float64)
        self.wc = np.copy(self.wm)

        self.wm[0] = self.lam / (L + self.lam)
        self.wc[0] = (self.lam / (L + self.lam)) + (1.0 - self.alpha ** 2 + self.beta)


def ensure_spd_and_cholesky(P: np.ndarray, min_eig: float = 1e-12) -> Tuple[np.ndarray, np.ndarray]:
    """
    Guarantees symmetry and positive semi-definiteness of covariance matrix P.
    """
    P_sym = 0.5 * (P + P.T)
    n = P_sym.shape[0]
    eye = np.eye(n, dtype=np.float64)

    for jitter in (0.0, 1e-12, 1e-10, 1e-8):
        try:
            S = cholesky(P_sym + jitter * eye, lower=True)
            return P_sym + jitter * eye, S
        except LinAlgError:
            continue

    eigvals, eigvecs = np.linalg.eigh(P_sym)
    eigvals_clamped = np.maximum(eigvals, min_eig)
    P_spd = eigvecs @ np.diag(eigvals_clamped) @ eigvecs.T
    P_spd = 0.5 * (P_spd + P_spd.T)
    S = cholesky(P_spd, lower=True)
    return P_spd, S


def generate_sigma_points(x: np.ndarray, P: np.ndarray, weights: MerweSigmaWeights) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates 2L + 1 Van der Merwe scaled sigma points around mean `x`.
    """
    P_spd, S = ensure_spd_and_cholesky(P)
    scaled_S = weights.gamma * S

    L = weights.n_dim
    sigma_pts = np.zeros((2 * L + 1, L), dtype=np.float64)
    sigma_pts[0] = x
    for i in range(L):
        col = scaled_S[:, i]
        sigma_pts[i + 1] = x + col
        sigma_pts[L + i + 1] = x - col

    return sigma_pts, P_spd


def joseph_covariance_update(
    P_prior: np.ndarray,
    P_xy: np.ndarray,
    P_yy: np.ndarray,
    K: np.ndarray,
    min_eig: float = 1e-12,
) -> np.ndarray:
    """
    Computes the numerically stable Joseph-form Unscented Kalman covariance update.
    """
    P_post = P_prior - (P_xy @ K.T) - (K @ P_xy.T) + (K @ P_yy @ K.T)
    P_post_spd, _ = ensure_spd_and_cholesky(P_post, min_eig=min_eig)
    return P_post_spd


# ==============================================================================
# 3. Dual-UKF Joint State (10 Hz) & Parameter (0.5 Hz) Estimator
# ==============================================================================

class DualUKFJointEstimator:
    """
    Dual-Unscented Kalman Filter running on two concurrent time scales:
      - Fast State Filter (10 Hz, dt_x = 0.1 s): x_k = [SOC, V_rc1, V_rc2]^T
      - Slow Parameter Filter (0.5 Hz, dt_theta = 2.0 s, ratio M = 20): theta_k = [R0, R1, C1, R2, C2]^T
    """

    def __init__(
        self,
        q_nom_ah: float = 5.0,
        dt_state: float = 0.1,
        dt_param: float = 2.0,
        x0: Optional[np.ndarray] = None,
        theta0: Optional[np.ndarray] = None,
    ):
        self.q_nom_coulombs = q_nom_ah * 3600.0
        self.dt_x = dt_state
        self.dt_theta = dt_param
        self.param_stride = int(round(dt_param / dt_state))

        self.x = (
            np.array([0.72, 0.0, 0.0], dtype=np.float64)
            if x0 is None
            else np.array(x0, dtype=np.float64)
        )
        self.theta = (
            np.array([0.036, 0.018, 950.0, 0.022, 14000.0], dtype=np.float64)
            if theta0 is None
            else np.array(theta0, dtype=np.float64)
        )

        self.theta_min = np.array([0.005, 0.002, 200.0, 0.003, 2000.0], dtype=np.float64)
        self.theta_max = np.array([0.120, 0.080, 5000.0, 0.100, 60000.0], dtype=np.float64)

        self.P_x = np.diag([1.5e-2, 1.0e-4, 1.0e-4]).astype(np.float64)
        self.P_theta = np.diag([4.0e-4, 4.0e-5, 4.0e4, 4.0e-5, 2.0e6]).astype(np.float64)

        self.Q_x = np.diag([1.0e-7, 2.5e-6, 1.0e-6]).astype(np.float64)
        self.R_x = np.array([[2.5e-5]], dtype=np.float64)

        self.Q_theta = np.diag([1.0e-8, 5.0e-8, 2.0e0, 5.0e-8, 5.0e1]).astype(np.float64)
        self.r_theta_scalar = 2.5e-5

        self.weights_x = MerweSigmaWeights(n_dim=3, alpha=1e-3, beta=2.0, kappa=0.0)
        self.weights_theta = MerweSigmaWeights(n_dim=5, alpha=1e-3, beta=2.0, kappa=0.0)

        self.step_counter = 0
        self.window_buffer: List[Tuple[np.ndarray, float, float]] = []

    @staticmethod
    def _propagate_state_single(
        x_vec: np.ndarray, i_prev: float, theta_vec: np.ndarray, dt: float, q_coul: float
    ) -> np.ndarray:
        soc, v1, v2 = x_vec[0], x_vec[1], x_vec[2]
        _, r1, c1, r2, c2 = theta_vec

        tau1 = max(r1 * c1, 1e-3)
        tau2 = max(r2 * c2, 1e-3)
        e1 = np.exp(-dt / tau1)
        e2 = np.exp(-dt / tau2)

        soc_next = np.clip(soc - (i_prev * dt) / q_coul, 0.001, 0.999)
        v1_next = e1 * v1 + r1 * (1.0 - e1) * i_prev
        v2_next = e2 * v2 + r2 * (1.0 - e2) * i_prev
        return np.array([soc_next, v1_next, v2_next], dtype=np.float64)

    @staticmethod
    def _measurement_voltage(x_vec: np.ndarray, i_now: float, theta_vec: np.ndarray) -> float:
        soc, v1, v2 = x_vec[0], x_vec[1], x_vec[2]
        r0 = theta_vec[0]
        v_ocv = float(OCVPolynomialModel.ocv(soc))
        return v_ocv - i_now * r0 - v1 - v2

    def update_state_ukf(self, i_prev: float, i_now: float, v_meas: float) -> Tuple[np.ndarray, float]:
        wx = self.weights_x
        sigma_x, self.P_x = generate_sigma_points(self.x, self.P_x, wx)

        sigma_x_pred = np.array([
            self._propagate_state_single(pt, i_prev, self.theta, self.dt_x, self.q_nom_coulombs)
            for pt in sigma_x
        ])
        x_prior = np.sum(wx.wm[:, None] * sigma_x_pred, axis=0)
        x_prior[0] = np.clip(x_prior[0], 0.001, 0.999)

        dx = sigma_x_pred - x_prior[None, :]
        P_x_prior = (dx.T * wx.wc) @ dx + self.Q_x
        P_x_prior, _ = ensure_spd_and_cholesky(P_x_prior)

        sigma_x_meas, P_x_prior = generate_sigma_points(x_prior, P_x_prior, wx)
        sigma_y = np.array([
            [self._measurement_voltage(pt, i_now, self.theta)] for pt in sigma_x_meas
        ])
        y_prior = np.sum(wx.wm[:, None] * sigma_y, axis=0)

        dy = sigma_y - y_prior[None, :]
        dx_meas = sigma_x_meas - x_prior[None, :]

        P_yy = (dy.T * wx.wc) @ dy + self.R_x
        P_xy = (dx_meas.T * wx.wc) @ dy

        K_x = P_xy / P_yy[0, 0]
        innovation = v_meas - y_prior[0]
        self.x = x_prior + (K_x[:, 0] * innovation)
        self.x[0] = np.clip(self.x[0], 0.001, 0.999)

        self.P_x = joseph_covariance_update(P_x_prior, P_xy, P_yy, K_x, min_eig=1e-12)
        v_est = self._measurement_voltage(self.x, i_now, self.theta)
        return self.x.copy(), v_est

    def update_parameter_ukf(self) -> np.ndarray:
        if len(self.window_buffer) == 0:
            return self.theta.copy()

        wt = self.weights_theta
        theta_prior = self.theta.copy()
        P_theta_prior = self.P_theta + self.Q_theta
        sigma_theta, P_theta_prior = generate_sigma_points(theta_prior, P_theta_prior, wt)
        sigma_theta = np.clip(sigma_theta, self.theta_min[None, :], self.theta_max[None, :])

        n_win = len(self.window_buffer)
        n_sig = sigma_theta.shape[0]
        Y_sigma = np.zeros((n_sig, n_win), dtype=np.float64)

        x_init, _, _ = self.window_buffer[0]
        for s_idx in range(n_sig):
            th_s = sigma_theta[s_idx]
            v1_sim = x_init[1]
            v2_sim = x_init[2]
            tau1 = max(th_s[1] * th_s[2], 1e-3)
            tau2 = max(th_s[3] * th_s[4], 1e-3)
            e1 = np.exp(-self.dt_x / tau1)
            e2 = np.exp(-self.dt_x / tau2)

            for m_idx, (x_m, i_m, _) in enumerate(self.window_buffer):
                if m_idx > 0:
                    i_prev_m = self.window_buffer[m_idx - 1][1]
                    v1_sim = e1 * v1_sim + th_s[1] * (1.0 - e1) * i_prev_m
                    v2_sim = e2 * v2_sim + th_s[3] * (1.0 - e2) * i_prev_m
                v_ocv_m = float(OCVPolynomialModel.ocv(x_m[0]))
                Y_sigma[s_idx, m_idx] = v_ocv_m - i_m * th_s[0] - v1_sim - v2_sim

        y_prior = np.sum(wt.wm[:, None] * Y_sigma, axis=0)
        dy = Y_sigma - y_prior[None, :]
        dtheta = sigma_theta - theta_prior[None, :]

        R_win = np.eye(n_win, dtype=np.float64) * self.r_theta_scalar
        P_yy = (dy.T * wt.wc) @ dy + R_win
        P_yy, _ = ensure_spd_and_cholesky(P_yy, min_eig=1e-10)
        P_theta_y = (dtheta.T * wt.wc) @ dy

        K_theta = np.linalg.solve(P_yy.T, P_theta_y.T).T

        y_meas_vec = np.array([item[2] for item in self.window_buffer], dtype=np.float64)
        innovation_vec = y_meas_vec - y_prior

        self.theta = np.clip(
            theta_prior + K_theta @ innovation_vec,
            self.theta_min,
            self.theta_max,
        )
        self.P_theta = joseph_covariance_update(
            P_theta_prior, P_theta_y, P_yy, K_theta, min_eig=1e-12
        )
        return self.theta.copy()

    def step(self, i_prev: float, i_now: float, v_meas: float) -> Dict[str, Any]:
        """
        Executes a unified step:
          - Runs 10 Hz State UKF.
          - Every 20 steps, triggers 0.5 Hz Parameter UKF.
        """
        self.step_counter += 1
        x_est, v_est = self.update_state_ukf(i_prev, i_now, v_meas)
        self.window_buffer.append((x_est.copy(), float(i_now), float(v_meas)))

        param_updated = False
        if self.step_counter % self.param_stride == 0:
            self.update_parameter_ukf()
            self.window_buffer.clear()
            param_updated = True

        soc_std = float(np.sqrt(max(1e-10, self.P_x[0, 0])))
        r0_std = float(np.sqrt(max(1e-10, self.P_theta[0, 0])))

        return {
            "x_est": x_est,
            "soc_est": float(x_est[0]),
            "soc_uncertainty_3sigma": round(float(3.0 * soc_std * 100.0), 3),
            "v_rc1": float(x_est[1]),
            "v_rc2": float(x_est[2]),
            "theta_est": self.theta.copy(),
            "r0_mohm": round(float(self.theta[0] * 1000.0), 2),
            "r1_mohm": round(float(self.theta[1] * 1000.0), 2),
            "c1_f": round(float(self.theta[2]), 1),
            "r2_mohm": round(float(self.theta[3] * 1000.0), 2),
            "c2_f": round(float(self.theta[4]), 1),
            "r0_uncertainty_mohm": round(float(r0_std * 1000.0), 3),
            "v_est": float(v_est),
            "docv_dsoc": float(OCVPolynomialModel.docv_dsoc(x_est[0])),
            "param_updated": param_updated,
        }


# Global singleton for real-time live telemetry tracking
dual_ukf_singleton = DualUKFJointEstimator()


# ==============================================================================
# 4. Dynamic 300-Second US06 Drive Cycle Simulator & Validation Benchmark
# ==============================================================================

def generate_us06_drive_cycle(
    duration_sec: float = 300.0,
    dt: float = 0.1,
    q_nom_ah: float = 5.0,
    seed: int = 42,
) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    t = np.arange(0.0, duration_sec + dt, dt, dtype=np.float64)
    n_steps = len(t)

    highway_cruise = 6.5 * np.sin(2.0 * np.pi * t / 95.0) ** 2
    hard_accel_pulses = (
        11.0 * np.sin(2.0 * np.pi * t / 18.0) * np.exp(-((t - 85.0) / 55.0) ** 2)
        + 13.5 * np.cos(2.0 * np.pi * t / 14.0) * np.exp(-((t - 215.0) / 65.0) ** 2)
    )
    high_freq_transients = (
        4.8 * np.sin(2.0 * np.pi * t / 5.5)
        + 3.4 * np.cos(2.0 * np.pi * t / 2.3)
        - 5.0 * (np.sin(2.0 * np.pi * t / 28.0) > 0.72).astype(np.float64)
    )
    i_true = highway_cruise + hard_accel_pulses + high_freq_transients

    r0_true = 0.0220 + 0.0015 * (1.0 - np.exp(-t / 180.0))
    r1_true = np.full(n_steps, 0.0140, dtype=np.float64)
    c1_true = np.full(n_steps, 1150.0, dtype=np.float64)
    r2_true = np.full(n_steps, 0.0180, dtype=np.float64)
    c2_true = np.full(n_steps, 16500.0, dtype=np.float64)

    soc_true = np.zeros(n_steps, dtype=np.float64)
    v_rc1_true = np.zeros(n_steps, dtype=np.float64)
    v_rc2_true = np.zeros(n_steps, dtype=np.float64)
    v_term_true = np.zeros(n_steps, dtype=np.float64)

    soc_curr = 0.850
    v1_curr = 0.0
    v2_curr = 0.0
    q_coul = q_nom_ah * 3600.0

    for k in range(n_steps):
        soc_true[k] = soc_curr
        v_rc1_true[k] = v1_curr
        v_rc2_true[k] = v2_curr
        v_ocv = float(OCVPolynomialModel.ocv(soc_curr))
        v_term_true[k] = v_ocv - i_true[k] * r0_true[k] - v1_curr - v2_curr

        e1 = np.exp(-dt / (r1_true[k] * c1_true[k]))
        e2 = np.exp(-dt / (r2_true[k] * c2_true[k]))
        v1_curr = e1 * v1_curr + r1_true[k] * (1.0 - e1) * i_true[k]
        v2_curr = e2 * v2_curr + r2_true[k] * (1.0 - e2) * i_true[k]
        soc_curr = np.clip(soc_curr - (i_true[k] * dt) / q_coul, 0.01, 0.99)

    i_meas = i_true + rng.normal(0.0, 0.040, size=n_steps)
    v_meas = v_term_true + rng.normal(0.0, 0.0035, size=n_steps)

    return {
        "time": t,
        "I_true": i_true,
        "I_meas": i_meas,
        "V_true": v_term_true,
        "V_meas": v_meas,
        "SOC_true": soc_true,
        "V_rc1_true": v_rc1_true,
        "V_rc2_true": v_rc2_true,
        "R0_true": r0_true,
        "R1_true": r1_true,
        "C1_true": c1_true,
        "R2_true": r2_true,
        "C2_true": c2_true,
    }


def run_us06_validation_benchmark(verbose: bool = True) -> Dict[str, Any]:
    """
    Runs the 300-second US06 validation test with initial SOC error and R0 offset,
    verifying rapid convergence to < 1.0% error.
    """
    sim_data = generate_us06_drive_cycle(duration_sec=300.0, dt=0.1, seed=42)
    t = sim_data["time"]
    n_steps = len(t)

    estimator = DualUKFJointEstimator(
        q_nom_ah=5.0,
        dt_state=0.1,
        dt_param=2.0,
        x0=np.array([0.720, 0.0, 0.0]),
        theta0=np.array([0.0340, 0.0180, 950.0, 0.0220, 14000.0]),
    )

    soc_est_hist = np.zeros(n_steps, dtype=np.float64)
    r0_est_hist = np.zeros(n_steps, dtype=np.float64)
    v_est_hist = np.zeros(n_steps, dtype=np.float64)

    for k in range(n_steps):
        i_prev = sim_data["I_meas"][k - 1] if k > 0 else sim_data["I_meas"][0]
        i_now = sim_data["I_meas"][k]
        v_now = sim_data["V_meas"][k]

        out = estimator.step(i_prev=i_prev, i_now=i_now, v_meas=v_now)
        soc_est_hist[k] = out["soc_est"]
        r0_est_hist[k] = out["theta_est"][0]
        v_est_hist[k] = out["v_est"]

    conv_mask = t >= 60.0
    soc_abs_err_pct = np.abs(soc_est_hist - sim_data["SOC_true"]) * 100.0
    r0_rel_err_pct = np.abs(r0_est_hist - sim_data["R0_true"]) / sim_data["R0_true"] * 100.0

    mean_soc_err_conv = float(np.mean(soc_abs_err_pct[conv_mask]))
    final_soc_err_pct = float(soc_abs_err_pct[-1])
    mean_r0_err_conv = float(np.mean(r0_rel_err_pct[conv_mask]))
    final_r0_err_pct = float(r0_rel_err_pct[-1])

    if verbose:
        print("=== Dual-UKF Joint State & Parameter Estimation (300s US06 Profile) ===")
        print(f"State Filter Rate (Fast)        : 10.0 Hz (dt = 0.1 s, N = {n_steps} steps)")
        print(f"Parameter Filter Rate (Slow)    : 0.50 Hz (dt = 2.0 s, {n_steps // 20} updates)")
        print(f"Converged SOC MAE (t >= 60s)    : {mean_soc_err_conv:.4f}% (Final @ 300s: {final_soc_err_pct:.4f}%)")
        print(f"Converged R0  MRE (t >= 60s)    : {mean_r0_err_conv:.4f}% (Final @ 300s: {final_r0_err_pct:.4f}%)")

        assert mean_soc_err_conv < 1.0 and final_soc_err_pct < 1.0, "SOC error exceeded 1.0% threshold!"
        assert mean_r0_err_conv < 1.0 and final_r0_err_pct < 1.0, "R0 error exceeded 1.0% threshold!"
        print("VALIDATION PASSED: Both SOC and R0 estimation errors converged to < 1.0%.")

    return {
        "time": t,
        "SOC_true": sim_data["SOC_true"],
        "SOC_est": soc_est_hist,
        "SOC_err_pct": soc_abs_err_pct,
        "R0_true": sim_data["R0_true"],
        "R0_est": r0_est_hist,
        "R0_err_pct": r0_rel_err_pct,
        "mean_soc_err_conv_pct": mean_soc_err_conv,
        "mean_r0_err_conv_pct": mean_r0_err_conv,
    }


if __name__ == "__main__":
    run_us06_validation_benchmark(verbose=True)
