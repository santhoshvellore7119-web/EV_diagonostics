"""
Operando Ultrasonic Coda Wave Interferometry (CWI) and Nonlinear Acoustic Harmonic Engine.

Employs the stretching technique on late-arriving reverberation coda waveforms
to quantify subtle microstructural changes in battery jelly-rolls:
1. Relative Acoustic Velocity Perturbation: dv/v = -eps_max
2. Waveform Decorrelation Coefficient: K_d = 1 - max CC(eps)
3. Nonlinear Acoustic Parameter: Beta = (8 / (3 * pi^2 * f^2 * d)) * (A2 / A1^2)
"""

import math
from typing import Dict, List, Any, Tuple
import numpy as np


class CodaWaveInterferometer:
    """Computes Coda Wave Interferometry (CWI) velocity shifts and micro-damage metrics."""

    def __init__(self, sampling_rate_mhz: float = 20.0, num_samples: int = 256):
        self.fs = sampling_rate_mhz * 1e6
        self.num_samples = num_samples
        self.time_us = np.linspace(0, num_samples / (sampling_rate_mhz), num_samples)

    def analyze_coda_shift(
        self,
        ref_signal: np.ndarray,
        perturbed_signal: np.ndarray,
        coda_start_us: float = 4.5,
        coda_end_us: float = 12.0,
        eps_range: float = 0.04,
        num_eps_steps: int = 101,
    ) -> Dict[str, Any]:
        """
        Perform Coda Wave Stretching to extract dv/v and decorrelation coefficient.
        """
        # Crop coda window
        t = self.time_us
        mask = (t >= coda_start_us) & (t <= coda_end_us)
        if not np.any(mask):
            mask = np.ones(len(t), dtype=bool)

        t_coda = t[mask]
        s_ref = ref_signal[mask]
        s_cur = perturbed_signal[mask]

        # Normalize windows
        norm_ref = np.linalg.norm(s_ref) + 1e-9
        norm_cur = np.linalg.norm(s_cur) + 1e-9
        u_ref = s_ref / norm_ref
        u_cur = s_cur / norm_cur

        # Grid search over relative velocity perturbations eps in [-eps_range, eps_range]
        eps_grid = np.linspace(-eps_range, eps_range, num_eps_steps)
        cc_values = np.zeros(num_eps_steps)

        for i, eps in enumerate(eps_grid):
            # Stretched time axis t' = t * (1 + eps)
            t_stretched = t_coda * (1.0 + eps)
            # Interpolate perturbed signal onto stretched time axis
            u_stretched = np.interp(t_stretched, t_coda, u_cur, left=0.0, right=0.0)
            denom = np.linalg.norm(u_stretched) * np.linalg.norm(u_ref) + 1e-9
            cc_values[i] = np.dot(u_ref, u_stretched) / denom

        best_idx = int(np.argmax(cc_values))
        best_eps = float(eps_grid[best_idx])
        max_cc = float(cc_values[best_idx])

        # Velocity change: dv/v = -eps
        dv_over_v = -best_eps
        decorrelation = max(0.0, 1.0 - max_cc)

        # Estimate 2nd harmonic for nonlinear acoustic parameter Beta
        fft_ref = np.abs(np.fft.rfft(s_ref))
        fft_cur = np.abs(np.fft.rfft(s_cur))
        a1 = float(np.max(fft_cur[2:15])) if len(fft_cur) > 15 else 1.0
        a2 = float(np.max(fft_cur[15:35])) if len(fft_cur) > 35 else 0.05
        beta_nonlinear = float(a2 / (max(1e-4, a1) ** 2))

        # Modulus change: dM/M = 2 * dv/v
        elastic_modulus_shift_pct = float(2.0 * dv_over_v * 100.0)

        # Discretized correlation curve for UI visualization
        correlation_curve = [
            {"eps_percent": float(eps_grid[i] * 100.0), "correlation": float(cc_values[i])}
            for i in range(0, num_eps_steps, 2)
        ]

        return {
            "dv_over_v_percent": round(dv_over_v * 100.0, 4),
            "max_correlation": round(max_cc, 4),
            "decorrelation_kd": round(decorrelation, 5),
            "elastic_modulus_shift_pct": round(elastic_modulus_shift_pct, 3),
            "nonlinear_beta": round(beta_nonlinear, 3),
            "correlation_curve": correlation_curve,
            "coda_window_us": [float(coda_start_us), float(coda_end_us)],
        }


# Singleton instance
cwi_analyzer = CodaWaveInterferometer()
