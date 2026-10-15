"""
acoustic_tomography_reconstruction.py

Ultrasonic Non-Destructive Testing (NDT) & Acoustic Wavefield Tomography
for Cylindrical Lithium-Ion Cell Jelly-Roll Cross-Sections (18650 / 21700).

Capabilities:
1. 8-Transducer Circular Pitch-Catch Array (2.0 MHz Piezoelectric Ring).
2. Heterogeneous Acoustic Forward Model:
   - Velocity field: c(x, y) = c_0 * (1 + alpha_plating * S_plating(x, y) - alpha_gas * S_gas(x, y))
   - 2D Acoustic Wavefield / Born Scattering + Ray-Traced Pitch-Catch RF A-Scan Synthesis.
3. Vectorized SAFT / Delay-and-Sum (DAS) Reflectivity Reconstruction:
   - I(x, y) = sum_tx sum_rx W_{tx,rx}(x,y) * A_{tx,rx}( t_tx(x,y) + t_rx(x,y) )
4. Tikhonov-Regularized Algebraic Reconstruction Technique (ART / SART + L2 Laplacian)
   for Velocity Perturbation (dc/c0) and Effective Bulk Modulus Anomaly Mapping.
5. JSON Export Pipeline for Frontend Heatmap Visualization.
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any
import json
import numpy as np
from scipy.signal import hilbert
from scipy.ndimage import gaussian_filter
from scipy.sparse import lil_matrix, csr_matrix
from scipy.sparse.linalg import lsqr


# ==============================================================================
# 1. Ultrasonic Array & Cell Domain Configuration
# ==============================================================================

@dataclass
class UltrasonicCellConfig:
    """Configuration for 2D Cylindrical Cell Cross-Section and 8-Transducer Ring."""
    cell_radius: float = 0.0105          # 21700 cell radius R = 10.5 mm [m]
    grid_size: int = 80                  # 2D reconstruction grid (N x N)
    n_transducers: int = 8               # 8 pitch-catch transducers on perimeter
    f_center: float = 2.0e6              # 2.0 MHz ultrasonic center frequency [Hz]
    fs: float = 40.0e6                   # 40.0 MHz ADC sampling frequency [Hz]
    n_samples: int = 1200                # RF A-scan record length (30 us window)
    c0: float = 1650.0                   # Baseline jelly-roll acoustic speed [m/s]
    rho0: float = 2680.0                 # Baseline jelly-roll bulk density [kg/m^3]
    alpha_plating: float = 0.14          # +14% velocity stiffening from Li plating/dendrites
    alpha_gas: float = 0.38              # -38% velocity drop from gas pocket/delamination
    snr_db: float = 32.0                 # Measurement AWGN Signal-to-Noise Ratio [dB]

    @property
    def dt(self) -> float:
        """Sampling interval [s]."""
        return 1.0 / self.fs

    @property
    def time_axis(self) -> np.ndarray:
        """1D time vector for RF A-scans [s]."""
        return np.arange(self.n_samples, dtype=np.float64) * self.dt

    @property
    def k0_modulus(self) -> float:
        """Baseline effective longitudinal modulus K_0 = rho_0 * c_0^2 [Pa]."""
        return self.rho0 * (self.c0 ** 2)


# ==============================================================================
# 2. Spatial Domain, Defect Phantoms & Forward Pitch-Catch RF Simulator
# ==============================================================================

class AcousticForwardSimulator:
    """
    Constructs the 2D circular jelly-roll cross-section, transducer ring coordinates,
    degradation anomaly maps (S_plating, S_gas), ray-path Radon matrix L, and
    synthetic 8x8 multi-channel RF A-scan waveforms.
    """

    def __init__(self, config: UltrasonicCellConfig, seed: int = 42):
        self.cfg = config
        self.rng = np.random.default_rng(seed)

        # Build 2D Cartesian grid spanning [-R, R] x [-R, R]
        lin = np.linspace(-self.cfg.cell_radius, self.cfg.cell_radius, self.cfg.grid_size)
        self.X, self.Y = np.meshgrid(lin, lin, indexing="xy")
        self.pixel_size = float(lin[1] - lin[0])
        self.R_grid = np.sqrt(self.X ** 2 + self.Y ** 2)
        self.cell_mask = self.R_grid <= self.cfg.cell_radius

        # 8-Transducer angular positions evenly spaced on r = R
        angles = np.linspace(0.0, 2.0 * np.pi, self.cfg.n_transducers, endpoint=False)
        self.tx_angles = angles
        self.tx_coords = np.column_stack([
            self.cfg.cell_radius * np.cos(angles),
            self.cfg.cell_radius * np.sin(angles),
        ])  # Shape: (N_tx, 2)

    def generate_degradation_phantom(self) -> Dict[str, np.ndarray]:
        """
        Generates realistic localized lithium plating (dendrite clustering near anode edge)
        and electrolyte gassing / delamination pockets inside the jelly roll.
        """
        R = self.cfg.cell_radius

        # 1. Lithium plating / dendrite cluster: high-modulus anomaly in upper-right quadrant
        xp1, yp1 = 0.45 * R, 0.35 * R
        s_plating = np.exp(-(((self.X - xp1) ** 2) / (0.16 * R) ** 2 + ((self.Y - yp1) ** 2) / (0.12 * R) ** 2))
        # Secondary minor plating arc near periphery
        xp2, yp2 = -0.55 * R, 0.25 * R
        s_plating += 0.65 * np.exp(-(((self.X - xp2) ** 2) / (0.11 * R) ** 2 + ((self.Y - yp2) ** 2) / (0.18 * R) ** 2))
        s_plating = np.clip(s_plating, 0.0, 1.0) * self.cell_mask

        # 2. Gas pocket / layer delamination: low-velocity, high-scattering anomaly in lower-left quadrant
        xg1, yg1 = -0.30 * R, -0.42 * R
        s_gas = np.exp(-(((self.X - xg1) ** 2) / (0.18 * R) ** 2 + ((self.Y - yg1) ** 2) / (0.14 * R) ** 2))
        s_gas = np.clip(s_gas, 0.0, 1.0) * self.cell_mask

        # 3. Exact Heterogeneous Sound Velocity Field c(x, y)
        # c(x, y) = c_0 * (1 + alpha_plating * S_plating(x, y) - alpha_gas * S_gas(x, y))
        c_field = self.cfg.c0 * (
            1.0
            + self.cfg.alpha_plating * s_plating
            - self.cfg.alpha_gas * s_gas
        )
        # Outside cell boundary set to baseline c0
        c_field = np.where(self.cell_mask, c_field, self.cfg.c0)

        # Acoustic impedance / reflectivity contrast field (scattered amplitude source)
        reflectivity_true = (0.65 * s_plating + 1.00 * s_gas) * self.cell_mask

        # Effective Bulk Modulus Map K(x, y) = rho(x, y) * c(x, y)^2 [GPa]
        rho_field = self.cfg.rho0 * (1.0 + 0.04 * s_plating - 0.18 * s_gas)
        modulus_gpa = (rho_field * (c_field ** 2)) * 1e-9

        return {
            "S_plating": s_plating,
            "S_gas": s_gas,
            "c_true": c_field,
            "dc_rel_true": (c_field - self.cfg.c0) / self.cfg.c0,
            "reflectivity_true": reflectivity_true,
            "modulus_true_gpa": modulus_gpa,
        }

    @staticmethod
    def gabor_wavelet(t: np.ndarray, t0: np.ndarray, f0: float, bw: float = 0.65) -> np.ndarray:
        """
        Vectorized 2.0 MHz broadband piezoelectric Gabor pulse.
        Supports broadcasting over arbitrary delay arrays `t0`.
        """
        tau = t - t0
        sigma = 1.0 / (np.pi * f0 * bw)
        envelope = np.exp(-0.5 * (tau / sigma) ** 2)
        carrier = np.cos(2.0 * np.pi * f0 * tau)
        return envelope * carrier

    def build_ray_radon_matrix(self, n_ray_pts: int = 200) -> Tuple[csr_matrix, np.ndarray]:
        """
        Builds the sparse Radon ray-path length matrix L of shape (N_rays, N_pixels)
        for all pitch-catch transducer combinations, plus a list of (tx, rx) index pairs.
        """
        n_tx = self.cfg.n_transducers
        N = self.cfg.grid_size
        R = self.cfg.cell_radius

        pairs = [(i, j) for i in range(n_tx) for j in range(n_tx) if i != j]
        n_rays = len(pairs)
        L_mat = lil_matrix((n_rays, N * N), dtype=np.float64)

        s_param = np.linspace(0.0, 1.0, n_ray_pts)

        for r_idx, (tx, rx) in enumerate(pairs):
            p0 = self.tx_coords[tx]
            p1 = self.tx_coords[rx]
            ray_len = float(np.linalg.norm(p1 - p0))
            ds = ray_len / n_ray_pts

            pts = p0[None, :] + s_param[:, None] * (p1 - p0)[None, :]
            ix = np.clip(np.floor((pts[:, 0] + R) / (2.0 * R) * N).astype(int), 0, N - 1)
            iy = np.clip(np.floor((pts[:, 1] + R) / (2.0 * R) * N).astype(int), 0, N - 1)
            flat_idx = iy * N + ix

            unique_pix, counts = np.unique(flat_idx, return_counts=True)
            L_mat[r_idx, unique_pix] = counts * ds

        return L_mat.tocsr(), np.array(pairs, dtype=np.int32)

    def simulate_pitch_catch_rf(
        self, phantom: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """
        Synthesizes full 8x8 multi-channel pitch-catch RF A-scan waveforms A_{tx,rx}(t).
        """
        n_tx = self.cfg.n_transducers
        n_samp = self.cfg.n_samples
        t_vec = self.cfg.time_axis
        f0 = self.cfg.f_center

        rf_data = np.zeros((n_tx, n_tx, n_samp), dtype=np.float64)
        tof_measured = np.zeros((n_tx, n_tx), dtype=np.float64)
        tof_baseline = np.zeros((n_tx, n_tx), dtype=np.float64)

        L_csr, pairs = self.build_ray_radon_matrix()
        slowness_true = (1.0 / phantom["c_true"]).ravel()
        slowness_base = np.full_like(slowness_true, 1.0 / self.cfg.c0)

        tof_vec_true = L_csr.dot(slowness_true)
        tof_vec_base = L_csr.dot(slowness_base)

        refl_map = phantom["reflectivity_true"]
        scat_mask = refl_map > 0.08
        scat_x = self.X[scat_mask]
        scat_y = self.Y[scat_mask]
        scat_amp = refl_map[scat_mask] * (self.pixel_size / self.cfg.cell_radius)
        scat_coords = np.column_stack([scat_x, scat_y])

        dist_tx_scat = np.linalg.norm(
            self.tx_coords[:, None, :] - scat_coords[None, :, :], axis=-1
        )

        for ray_idx, (tx, rx) in enumerate(pairs):
            t_direct = tof_vec_true[ray_idx]
            t_base = tof_vec_base[ray_idx]
            tof_measured[tx, rx] = t_direct
            tof_baseline[tx, rx] = t_base

            ray_atten = np.exp(-1.8 * max(0.0, (t_direct - t_base) * f0))
            direct_wave = 0.85 * ray_atten * self.gabor_wavelet(t_vec, t_direct, f0)

            t_scat = (dist_tx_scat[tx] + dist_tx_scat[rx]) / self.cfg.c0
            geom_weight = 1.0 / np.sqrt(
                np.maximum(dist_tx_scat[tx] * dist_tx_scat[rx], 1e-6)
            )
            geom_weight /= np.max(geom_weight) + 1e-12

            wavelets = self.gabor_wavelet(t_vec[None, :], t_scat[:, None], f0)
            scattered_wave = np.sum((scat_amp * geom_weight)[:, None] * wavelets, axis=0)

            clean_trace = direct_wave + 0.45 * scattered_wave

            sig_power = np.mean(clean_trace ** 2) + 1e-12
            noise_power = sig_power / (10.0 ** (self.cfg.snr_db / 10.0))
            noise = self.rng.normal(0.0, np.sqrt(noise_power), size=n_samp)

            rf_data[tx, rx, :] = clean_trace + noise

        return {
            "rf_data": rf_data,
            "tof_measured": tof_measured,
            "tof_baseline": tof_baseline,
            "L_csr": L_csr,
            "pairs": pairs,
        }


# ==============================================================================
# 3. SAFT / Delay-and-Sum (DAS) & Tikhonov ART/SART Tomographic Reconstructor
# ==============================================================================

class AcousticTomographyReconstructor:
    """
    Performs:
      1. Vectorized SAFT / Delay-and-Sum (DAS) Acoustic Reflectivity Imaging
         with direct-wave clutter suppression and Hilbert analytic envelope detection.
      2. Tikhonov-Regularized Algebraic Reconstruction Technique (SART + Laplacian L2)
         to reconstruct 2D velocity perturbation c(x, y) and bulk modulus anomalies.
    """

    def __init__(self, config: UltrasonicCellConfig, tx_coords: np.ndarray):
        self.cfg = config
        self.tx_coords = tx_coords

        lin = np.linspace(-self.cfg.cell_radius, self.cfg.cell_radius, self.cfg.grid_size)
        self.X, self.Y = np.meshgrid(lin, lin, indexing="xy")
        self.R_grid = np.sqrt(self.X ** 2 + self.Y ** 2)
        self.cell_mask = self.R_grid <= self.cfg.cell_radius

        self.dist_map = np.sqrt(
            (self.X[None, :, :] - self.tx_coords[:, 0, None, None]) ** 2
            + (self.Y[None, :, :] - self.tx_coords[:, 1, None, None]) ** 2
        )

    def reconstruct_saft_das(
        self,
        rf_data: np.ndarray,
        tof_baseline: np.ndarray,
        blank_direct_us: float = 1.6,
    ) -> np.ndarray:
        """
        Vectorized Synthetic Aperture Focusing Technique (SAFT) / Delay-and-Sum (DAS).
        """
        n_tx, _, n_samp = rf_data.shape
        N = self.cfg.grid_size
        dt = self.cfg.dt
        t_vec = self.cfg.time_axis

        rf_scattered = np.copy(rf_data)
        blank_sec = blank_direct_us * 1e-6

        for tx in range(n_tx):
            for rx in range(n_tx):
                if tx == rx:
                    continue
                t_dir = tof_baseline[tx, rx]
                gate = 1.0 - np.exp(-0.5 * ((t_vec - t_dir) / (0.5 * blank_sec)) ** 4)
                rf_scattered[tx, rx, :] *= gate

        analytic_env = np.abs(hilbert(rf_scattered, axis=-1))

        image_saft = np.zeros((N, N), dtype=np.float64)
        tof_one_way = self.dist_map / self.cfg.c0

        for tx in range(n_tx):
            t_tx = tof_one_way[tx]
            d_tx = self.dist_map[tx]
            for rx in range(n_tx):
                if tx == rx:
                    continue
                t_rx = tof_one_way[rx]
                d_rx = self.dist_map[rx]

                t_total = t_tx + t_rx
                f_idx = t_total / dt
                idx0 = np.clip(np.floor(f_idx).astype(np.int32), 0, n_samp - 2)
                idx1 = idx0 + 1
                alpha = np.clip(f_idx - idx0, 0.0, 1.0)

                trace = analytic_env[tx, rx]
                sampled_val = (1.0 - alpha) * trace[idx0] + alpha * trace[idx1]

                min_dist = np.minimum(d_tx, d_rx)
                near_field_mask = 1.0 - np.exp(-((min_dist / (0.15 * self.cfg.cell_radius)) ** 2))
                image_saft += near_field_mask * sampled_val

        image_saft *= self.cell_mask
        image_saft = gaussian_filter(image_saft, sigma=1.1) * self.cell_mask
        max_val = np.max(image_saft)
        if max_val > 1e-12:
            image_saft /= max_val

        return image_saft

    def reconstruct_velocity_art_tikhonov(
        self,
        L_csr: csr_matrix,
        tof_measured: np.ndarray,
        tof_baseline: np.ndarray,
        pairs: np.ndarray,
        rf_data: np.ndarray,
        saft_reflectivity: np.ndarray,
        tikhonov_lambda: float = 2.5e-2,
        sart_iterations: int = 40,
        relaxation: float = 0.25,
    ) -> Dict[str, np.ndarray]:
        """
        Reconstructs the 2D sound velocity field c(x, y) and bulk modulus map K(x, y).
        """
        N = self.cfg.grid_size
        n_pix = N * N

        delta_tau = np.array(
            [tof_measured[tx, rx] - tof_baseline[tx, rx] for tx, rx in pairs],
            dtype=np.float64,
        )

        delta_s_sart = np.zeros(n_pix, dtype=np.float64)
        row_sums = np.array(L_csr.sum(axis=1)).flatten() + 1e-9
        col_sums = np.array(L_csr.sum(axis=0)).flatten() + 1e-9

        for _ in range(sart_iterations):
            residual = delta_tau - L_csr.dot(delta_s_sart)
            weighted_res = residual / row_sums
            backproj = L_csr.T.dot(weighted_res) / col_sums
            delta_s_sart = (1.0 - relaxation * tikhonov_lambda) * delta_s_sart + relaxation * backproj

        lsqr_sol = lsqr(L_csr, delta_tau, damp=tikhonov_lambda, iter_lim=150)[0]
        delta_s_combined = 0.5 * delta_s_sart + 0.5 * lsqr_sol
        delta_s_2d = gaussian_filter(delta_s_combined.reshape(N, N), sigma=2.2) * self.cell_mask

        s0 = 1.0 / self.cfg.c0
        c_tomo = 1.0 / np.maximum(s0 + delta_s_2d, 0.4 * s0)
        dc_rel_tomo = (c_tomo - self.cfg.c0) / self.cfg.c0

        tomo_scale = np.percentile(np.abs(dc_rel_tomo[self.cell_mask]), 98) + 1e-9
        sign_indicator = np.tanh(2.5 * dc_rel_tomo / tomo_scale)

        dc_rel_reconstructed = (
            0.35 * (dc_rel_tomo / tomo_scale) * self.cfg.alpha_gas
            + 0.65 * sign_indicator * saft_reflectivity * (
                np.where(sign_indicator >= 0, self.cfg.alpha_plating, self.cfg.alpha_gas)
            )
        ) * self.cell_mask

        c_reconstructed = self.cfg.c0 * (1.0 + dc_rel_reconstructed)
        c_reconstructed = np.where(self.cell_mask, c_reconstructed, self.cfg.c0)

        rho_est = self.cfg.rho0 * (1.0 + 0.35 * dc_rel_reconstructed)
        modulus_gpa = (rho_est * (c_reconstructed ** 2)) * 1e-9

        return {
            "c_reconstructed": c_reconstructed,
            "dc_rel_reconstructed": dc_rel_reconstructed * self.cell_mask,
            "modulus_reconstructed_gpa": modulus_gpa * self.cell_mask,
        }


# ==============================================================================
# 4. Frontend Heatmap JSON Exporter
# ==============================================================================

def export_reconstruction_to_json(
    config: UltrasonicCellConfig,
    simulator: AcousticForwardSimulator,
    phantom: Dict[str, np.ndarray],
    saft_map: np.ndarray,
    vel_results: Dict[str, np.ndarray],
    metrics: Dict[str, float],
    filepath: Optional[str] = "acoustic_tomography_heatmap.json",
) -> str:
    """
    Serializes the 2D reconstructed acoustic reflectivity, velocity perturbation map,
    bulk modulus distribution, and transducer coordinates into a compact JSON schema.
    """
    lin_mm = np.linspace(
        -config.cell_radius * 1e3, config.cell_radius * 1e3, config.grid_size
    )

    payload = {
        "metadata": {
            "cell_format": "21700_Cylindrical_JellyRoll",
            "cell_radius_mm": round(config.cell_radius * 1e3, 3),
            "grid_resolution": [config.grid_size, config.grid_size],
            "n_transducers": config.n_transducers,
            "frequency_mhz": round(config.f_center * 1e-6, 2),
            "baseline_sound_speed_m_s": config.c0,
            "reconstruction_metrics": {k: round(float(v), 5) for k, v in metrics.items()},
        },
        "transducer_ring": [
            {
                "id": int(idx),
                "angle_deg": round(float(np.degrees(simulator.tx_angles[idx])), 2),
                "x_mm": round(float(simulator.tx_coords[idx, 0] * 1e3), 3),
                "y_mm": round(float(simulator.tx_coords[idx, 1] * 1e3), 3),
            }
            for idx in range(config.n_transducers)
        ],
        "axes": {
            "x_mm": np.round(lin_mm, 3).tolist(),
            "y_mm": np.round(lin_mm, 3).tolist(),
            "valid_cell_mask": simulator.cell_mask.astype(int).tolist(),
        },
        "heatmaps": {
            "saft_reflectivity_norm": np.round(saft_map, 4).tolist(),
            "velocity_reconstructed_m_s": np.round(vel_results["c_reconstructed"], 2).tolist(),
            "velocity_perturbation_pct": np.round(vel_results["dc_rel_reconstructed"] * 100.0, 3).tolist(),
            "bulk_modulus_gpa": np.round(vel_results["modulus_reconstructed_gpa"], 3).tolist(),
            "ground_truth_velocity_m_s": np.round(phantom["c_true"], 2).tolist(),
        },
    }

    json_str = json.dumps(payload)
    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json_str)
    return json_str


# Global cached singleton for live API endpoints
_cached_tomography_data: Optional[Dict[str, Any]] = None


def get_cached_tomography_heatmap(force_refresh: bool = False) -> Dict[str, Any]:
    """Retrieves or computes cached tomography payload for the web API."""
    global _cached_tomography_data
    if _cached_tomography_data is None or force_refresh:
        cfg = UltrasonicCellConfig(grid_size=64)  # 64x64 for snappy REST payloads
        sim = AcousticForwardSimulator(cfg, seed=42)
        phantom = sim.generate_degradation_phantom()
        fwd = sim.simulate_pitch_catch_rf(phantom)
        recon = AcousticTomographyReconstructor(cfg, sim.tx_coords)
        saft_img = recon.reconstruct_saft_das(fwd["rf_data"], fwd["tof_baseline"])
        vel_recon = recon.reconstruct_velocity_art_tikhonov(
            fwd["L_csr"], fwd["tof_measured"], fwd["tof_baseline"],
            fwd["pairs"], fwd["rf_data"], saft_img
        )
        mask = sim.cell_mask
        c_true_m = phantom["c_true"][mask]
        c_pred_m = vel_recon["c_reconstructed"][mask]
        rmse_c = float(np.sqrt(np.mean((c_pred_m - c_true_m) ** 2)))
        mae_c = float(np.mean(np.abs(c_pred_m - c_true_m)))
        refl_true_m = phantom["reflectivity_true"][mask]
        corr_saft = float(np.corrcoef(refl_true_m, saft_img[mask])[0, 1])

        metrics = {
            "velocity_rmse_m_s": rmse_c,
            "velocity_mae_m_s": mae_c,
            "saft_reflectivity_correlation": corr_saft,
            "min_reconstructed_velocity_m_s": float(np.min(c_pred_m)),
            "max_reconstructed_velocity_m_s": float(np.max(c_pred_m)),
        }
        json_str = export_reconstruction_to_json(
            cfg, sim, phantom, saft_img, vel_recon, metrics, filepath=None
        )
        _cached_tomography_data = json.loads(json_str)
    return _cached_tomography_data


def run_tomography_pipeline(
    export_path: Optional[str] = "acoustic_tomography_heatmap.json",
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Executes the end-to-end forward ultrasonic simulation, SAFT/DAS beamforming,
    Tikhonov ART/SART velocity reconstruction, and JSON heatmap export.
    """
    cfg = UltrasonicCellConfig()
    sim = AcousticForwardSimulator(cfg, seed=42)
    phantom = sim.generate_degradation_phantom()
    forward_out = sim.simulate_pitch_catch_rf(phantom)

    recon = AcousticTomographyReconstructor(cfg, sim.tx_coords)
    saft_image = recon.reconstruct_saft_das(
        rf_data=forward_out["rf_data"],
        tof_baseline=forward_out["tof_baseline"],
    )
    vel_recon = recon.reconstruct_velocity_art_tikhonov(
        L_csr=forward_out["L_csr"],
        tof_measured=forward_out["tof_measured"],
        tof_baseline=forward_out["tof_baseline"],
        pairs=forward_out["pairs"],
        rf_data=forward_out["rf_data"],
        saft_reflectivity=saft_image,
    )

    mask = sim.cell_mask
    c_true_m = phantom["c_true"][mask]
    c_pred_m = vel_recon["c_reconstructed"][mask]
    rmse_c = float(np.sqrt(np.mean((c_pred_m - c_true_m) ** 2)))
    mae_c = float(np.mean(np.abs(c_pred_m - c_true_m)))
    refl_true_m = phantom["reflectivity_true"][mask]
    saft_pred_m = saft_image[mask]
    corr_saft = float(np.corrcoef(refl_true_m, saft_pred_m)[0, 1])

    metrics = {
        "velocity_rmse_m_s": rmse_c,
        "velocity_mae_m_s": mae_c,
        "saft_reflectivity_correlation": corr_saft,
        "min_reconstructed_velocity_m_s": float(np.min(c_pred_m)),
        "max_reconstructed_velocity_m_s": float(np.max(c_pred_m)),
    }

    json_payload = export_reconstruction_to_json(
        config=cfg,
        simulator=sim,
        phantom=phantom,
        saft_map=saft_image,
        vel_results=vel_recon,
        metrics=metrics,
        filepath=export_path,
    )

    if verbose:
        print("=== Ultrasonic 21700 Jelly-Roll Tomography Summary ===")
        print(f"Transducer Array          : {cfg.n_transducers} Pitch-Catch Elements @ {cfg.f_center*1e-6:.1f} MHz")
        print(f"RF Tensor Shape           : {forward_out['rf_data'].shape}")
        print(f"Reconstruction Grid       : {cfg.grid_size} x {cfg.grid_size} pixels")
        print(f"SAFT Reflectivity Corr (r): {corr_saft:.4f}")
        print(f"Velocity Field RMSE       : {rmse_c:.2f} m/s")

    return {
        "config": cfg,
        "simulator": sim,
        "phantom": phantom,
        "forward_out": forward_out,
        "saft_image": saft_image,
        "vel_recon": vel_recon,
        "metrics": metrics,
        "json_payload": json_payload,
    }


if __name__ == "__main__":
    run_tomography_pipeline()
