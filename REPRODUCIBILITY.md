# Scientific Reproducibility Guide

This repository conforms to the highest standards of scientific reproducibility, open-source verification, and transparent peer review for electric vehicle battery diagnostics and active cell rebalancing research.

---

## 1. Environment & Prerequisites

### Recommended Platforms
- **OS**: Ubuntu 22.04 LTS / 24.04 LTS, Windows 10/11 (64-bit), or macOS (Sonoma/Sequoia).
- **Python**: Python 3.12 (also tested on 3.10 and 3.11).
- **Node.js**: Node.js 18+ LTS or 20+ LTS (for React telemetry frontend).
- **Optional Tools**: MATLAB R2023b / R2024b (for Simulink FMU co-simulation).

### One-Step Installation
Clone the repository and install all scientific dependencies:
```bash
git clone https://github.com/santhoshvellore7119-web/EV_diagonostics.git
cd EV_diagonostics

# Create and activate a clean virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Upgrade pip and install all scientific packages
pip install --upgrade pip
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

---

## 2. One-Command Master Reproducibility

To automatically run the entire empirical research benchmark suite, evaluate all 6 multi-physics benchmarks, generate the machine-readable summary (`results/research_benchmark_summary.json`), and export publication LaTeX tables:

```bash
python run_research_benchmarks.py
```

### Expected Output Summary
```
==========================================================================================
 MASTER RESEARCH BENCHMARK REPRODUCIBILITY SUITE
 Physics-Informed Multi-Modal EV Battery Diagnostics & Active Rebalancing
==========================================================================================
 Benchmark 1: Dynamic WLTP Drive Cycle State Estimation (Dual-UKF vs Baselines)
 Benchmark 2: 2D Acoustic Wavefield Tomography & Anomaly Localization (SAFT + SART)
 Benchmark 3: 3D Axisymmetric Anisotropic Thermal PINN vs Analytical Bounds
 Benchmark 4: Active ZVS Balancing Across Standardized Automotive Drive Cycles
 Benchmark 5: Silent Lithium Plating Operando Multi-Modal Ablation
 Benchmark 6: MATLAB / Simulink Co-Simulation Parity & Bench Transfer
==========================================================================================
[SUCCESS]: All 6 Master Research Benchmarks completed.
Results archived to: results/research_benchmark_summary.json
Publication LaTeX tables exported to: results/latex/
```

---

## 3. Publication Vector Figures Reproduction

To re-generate all 5 high-resolution vector figures (300 DPI PNG and publication-grade PDF) formatted according to IEEE Transactions / Elsevier standards:

```bash
python scripts/generate_publication_figures.py
```

Generated figure outputs are stored in `paper/figures/`:
- `fig1_spme_solid_diffusion_and_plating.pdf / .png`
- `fig2_acoustic_tomography_reconstruction.pdf / .png`
- `fig3_pinn_thermal_anisotropic_field.pdf / .png`
- `fig4_drive_cycle_active_balancing_wltp.pdf / .png`
- `fig5_silent_plating_early_detection_roc.pdf / .png`

---

## 4. Analytical Mathematical Physics Verification Suite

To verify all numerical implementations against closed-form analytical equations (Fourier radial heat conduction, Fickian spherical diffusion, LC tank ZVS orbit, Dual-UKF covariance positive-definiteness, and acoustic modulus sensitivity):

```bash
pytest tests/test_analytical_benchmarks.py -v
```

All 5 analytical checks are guaranteed to pass with relative errors strictly below theoretical physical tolerances ($< 1.0\%$).

---

## 5. Master Automated Test Suite (130/130 Tests Passing)

To execute the entire end-to-end verification suite across all 20 subsystems:

```bash
pytest tests/ -v
```

Subsystems verified:
1. `test_3d_spatial_physics.py`: Finite volume thermal spatial conduction & 3D ray tracing.
2. `test_advanced_machine_simulation.py`: A-scan acoustic waveform synthesis & defect signatures.
3. `test_analytical_benchmarks.py`: Exact closed-form mathematical solutions vs numerical grids.
4. `test_argon4_novelty_suite.py`: Acoustic tomography, Dual-UKF, PINN loss, and Copilot endpoints.
5. `test_cross_source_consistency.py`: Schema validation & physical telemetry invariants.
6. `test_decision_engine.py`: Finite state machine, PID recovery, and safety contactors.
7. `test_edge_ml_model.py`: 5.84 KB Int8 quantized student model & latency bounds.
8. `test_edge_ml_parity.py`: Teacher-student cross-modal knowledge distillation.
9. `test_edge_ml_pipeline.py`: 360-frame edge pipeline validation.
10. `test_evidence.py`: Structured forensic evidence logging & JSON serialization.
11. `test_fastapi.py`: REST API endpoints, WebSocket streaming, and Gazebo viewer.
12. `test_firmware_static.py`: Embedded C++ FreeRTOS firmware header and implementation audit.
13. `test_gazebo_integration.py`: ROS 2 multi-physics Gazebo world & acoustic array SDF models.
14. `test_hardware_signal_chain.py`: KiCad netlist, 55 ps TDC7200 timing, and RF microstrip rules.
15. `test_ingest.py`: Universal ingestor abstraction across 3D, Gazebo, Simulink, and Firmware.
16. `test_live_pipeline_accuracy.py`: Full multi-modal diagnostic sweep across all degradation modes.
17. `test_matlab_parity.py`: Python vs MATLAB degradation library & edge weights parity.
18. `test_matlab_simulink_comprehensive.py`: S-Function co-sim, active balancing & RLS convergence.
19. `test_ml_model.py`: MultiBranchFusionNet architectures (concat, add, attention).
20. `test_novelty_upgrades.py`: Online RLS observer, dynamic EIS Nyquist, and Hilbert envelope.
21. `test_physics_no_label_leakage.py`: Zero label leakage validation across ambient/SOC sweeps.
22. `test_rebalancing.py`: Dynamic ZVS active energy shuttling & safety lockout.
23. `test_research_benchmarks.py`: Standard drive cycles (WLTP, US06, HPPC) and benchmarks.
24. `test_spm_electrochemical_model.py`: SPMe solid diffusion & Butler-Volmer plating criterion.
25. `test_system_efficiency.py`: Soft-switching ZVS efficiency, energy savings, and timing budget.

---

## 6. Table & Figure Cross-Reference Mapping

| Table / Figure in Paper / Report | Generated By | Output File Reference |
| :--- | :--- | :--- |
| **Table 1** (System Specifications) | `run_research_benchmarks.py` | [`results/latex/table1_specifications.tex`](results/latex/table1_specifications.tex) |
| **Table 2** (Dual-UKF vs EKF Accuracy) | `run_research_benchmarks.py` | [`results/latex/table2_state_estimation.tex`](results/latex/table2_state_estimation.tex) |
| **Table 3** (Automotive Drive Cycles) | `run_research_benchmarks.py` | [`results/latex/table3_drive_cycles.tex`](results/latex/table3_drive_cycles.tex) |
| **Table 4** (Trimodal Ablation Study) | `run_research_benchmarks.py` | [`results/latex/table4_trimodal_ablation.tex`](results/latex/table4_trimodal_ablation.tex) |
| **Table 5** (MATLAB Parity & Transfer) | `run_research_benchmarks.py` | [`results/latex/table5_matlab_parity.tex`](results/latex/table5_matlab_parity.tex) |
| **Figure 1** (SPMe Diffusion & Plating) | `scripts/generate_publication_figures.py` | [`paper/figures/fig1_spme_solid_diffusion_and_plating.pdf`](paper/figures/fig1_spme_solid_diffusion_and_plating.pdf) |
| **Figure 2** (2D Acoustic Tomography) | `scripts/generate_publication_figures.py` | [`paper/figures/fig2_acoustic_tomography_reconstruction.pdf`](paper/figures/fig2_acoustic_tomography_reconstruction.pdf) |
| **Figure 3** (3D Anisotropic Thermal PINN)| `scripts/generate_publication_figures.py` | [`paper/figures/fig3_pinn_thermal_anisotropic_field.pdf`](paper/figures/fig3_pinn_thermal_anisotropic_field.pdf) |
| **Figure 4** (WLTP Active Balancing) | `scripts/generate_publication_figures.py` | [`paper/figures/fig4_drive_cycle_active_balancing_wltp.pdf`](paper/figures/fig4_drive_cycle_active_balancing_wltp.pdf) |
| **Figure 5** (Early Plating Detection ROC)| `scripts/generate_publication_figures.py` | [`paper/figures/fig5_silent_plating_early_detection_roc.pdf`](paper/figures/fig5_silent_plating_early_detection_roc.pdf) |
| **Figures 6–7** (MATLAB Demonstration) | `matlab_simulink_demo/scripts/` | [`matlab_simulink_demo/battery_system_demo.png`](matlab_simulink_demo/battery_system_demo.png) |
| **Figures 8–15** (Live UI Features) | `scripts/capture_all_ui_features.py` | [`docs/ui_screenshots/`](docs/ui_screenshots/) |

---

## 7. Citation

If you use this benchmark harness, software architecture, or physics models in academic work, please cite:

```bibtex
@article{vellore2026multimodal,
  author    = {Vellore, Santhosh},
  title     = {Multi-Modal Physics-Informed Ultrasonic Tomography and Quasi-Resonant Active Balancing for Second-Life EV Battery Packs},
  journal   = {IEEE Transactions on Transportation Electrification},
  year      = {2026},
  volume    = {XX},
  number    = {X},
  pages     = {1--14},
  note      = {Code: https://github.com/santhoshvellore7119-web/EV_diagonostics}
}
```
