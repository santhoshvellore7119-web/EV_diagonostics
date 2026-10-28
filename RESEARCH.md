# Physics-Informed Multi-Modal Cyber-Physical Diagnostics and Quasi-Resonant Active Rebalancing for Second-Life EV Battery Packs

**Lead Investigator**: Santhosh Vellore  
**Affiliation**: Department of Electrical and Computer Engineering  
**Target Venue**: IEEE Transactions on Transportation Electrification / Journal of Power Sources  
**Repository**: [https://github.com/santhoshvellore7119-web/EV_diagonostics](https://github.com/santhoshvellore7119-web/EV_diagonostics)  
**Citation Metadata**: [`CITATION.cff`](CITATION.cff) | **Reproducibility**: [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md)

---

## 1. Scientific Motivation & Problem Statement

The rapid worldwide deployment of electric vehicles (EVs) has created a secondary industrial bottleneck: millions of retired traction packs reaching 70%–80% of original capacity. Re-purposing these retired batteries for stationary energy storage systems (BESS) and microgrids promises massive carbon reduction. However, second-life batteries suffer from acute heterogeneous aging:
1. **Premature Series Cutoff**: In a conventional series ($N\text{S}1\text{P}$) module, pack discharge must terminate the instant the weakest series cell reaches the lower cutoff threshold ($V_{cut} = 2.80\text{–}3.00\text{ V}$). Up to 35%–40% of usable energy remains trapped in healthy adjacent cells.
2. **Dissipative Bleeding Inefficiencies**: Standard commercial passive balancing dissipates charge through small shunt resistors (50–100 mA), burning trapped electrical energy as localized heat ($I^2 R$), creating thermal hotspots, and failing during dynamic automotive cycling.
3. **Macro-Surface Diagnostic Blindness**: Existing Battery Management Systems (BMS) sample only terminal voltage, current, and casing surface temperature. Sub-surface microstructural degradation—specifically metallic lithium dendrite plating and localized gas pouching—exhibits near-zero surface voltage or temperature drop during inception, evading detection until separator rupture and thermal runaway occur.

This project delivers an autonomous, closed-loop cyber-physical platform that marries non-destructive multi-physics sensing with soft-switching bidirectional active energy redistribution.

---

## 2. Mathematical Formulations & Multi-Physics Governing PDEs

```
                          +-------------------------------------------------+
                          |             Multi-Modal Sensor Suite            |
                          +-------------------------------------------------+
                                /                  |                  \
                               v                   v                   v
                     +------------------+ +------------------+ +------------------+
                     | 2.0 MHz Circular | |  4-Wire Kelvin   | | Multi-Zone Robin |
                     | PZT Tomography   | |  Terminal V & I  | | Surface Thermals |
                     +------------------+ +------------------+ +------------------+
                               |                   |                   |
                               v                   v                   v
                     +------------------+ +------------------+ +------------------+
                     | Vectorized SAFT  | | Decoupled Multi- | | 3D Anisotropic   |
                     | & Tikhonov SART  | | Rate Dual-UKF    | | Thermal PINN     |
                     +------------------+ +------------------+ +------------------+
                                \                  |                  /
                                 \                 |                 /
                                  v                v                v
                          +-------------------------------------------------+
                          |  Cross-Modal Attention & Decision State Machine |
                          +-------------------------------------------------+
                                                   |
                                                   v
                          +-------------------------------------------------+
                          | Bidirectional Quasi-Resonant ZVS Flyback Shuttling|
                          |   (1.8 A Energy Transfer, 93.0% Soft-Switching) |
                          +-------------------------------------------------+
```

### 2.1 2D Ultrasonic Wavefield Tomography & SART Inversion
Heterogeneous microstructural degradation perturbs baseline acoustic sound velocity $c_0 = 1650\,\text{m/s}$ and bulk modulus $K = \rho c^2$:
$$c(x, y) = c_0 \left(1 + \alpha_{\text{plating}} S_{\text{plating}}(x, y) - \alpha_{\text{gas}} S_{\text{gas}}(x, y)\right)$$
where $\alpha_{\text{plating}} = +0.14$ models elastic stiffening from metallic lithium deposits, and $\alpha_{\text{gas}} = +0.38$ models acoustic wave velocity deceleration through electrolyte gassing.

Under the linearized acoustic perturbation approximation, the acoustic time-of-flight (ToF) residual $\Delta \tau_i$ across ray path $\Gamma_i$ connecting transmitter $m$ and receiver $n$ is:
$$\Delta \tau_i = \int_{\Gamma_i} \delta s(x, y)\, d\ell \approx \sum_{j=1}^{N_{\text{pix}}} L_{ij} \delta s_j$$

We solve for slowness perturbation $\delta \mathbf{s}^*$ via Tikhonov-regularized Simultaneous Algebraic Reconstruction Technique (SART) with a discrete Laplacian smoothing operator $\mathbf{D}$:
$$\delta \mathbf{s}^* = \arg\min_{\delta \mathbf{s}} \left( \|\mathbf{L} \delta \mathbf{s} - \Delta \boldsymbol{\tau}\|_2^2 + \lambda_{\text{Tik}} \|\mathbf{D} \delta \mathbf{s}\|_2^2 \right)$$

Simultaneously, coherent reflectivity imaging is computed using vectorized Synthetic Aperture Focusing Technique (SAFT) delay-and-sum beamforming:
$$I_{\text{SAFT}}(x, y) = \sum_{m=1}^{N_{\text{tx}}} \sum_{n \neq m} W_{m,n}(x,y) \cdot \mathcal{H}\left[ A_{m,n}\left( \frac{\|\mathbf{r} - \mathbf{r}_m\|_2 + \|\mathbf{r} - \mathbf{r}_n\|_2}{c_0} \right) \right]$$

---

### 2.2 Operando SPMe Electrochemical Plating Criterion
Solid-phase lithium transport within spherical graphite particles ($r \in [0, R_p]$) is governed by Fickian spherical diffusion:
$$\frac{\partial c_s}{\partial t} = \frac{D_s(T)}{r^2} \frac{\partial}{\partial r}\left(r^2 \frac{\partial c_s}{\partial r}\right)$$
subject to symmetry at the particle center and interfacial Butler-Volmer intercalation flux at the exterior boundary:
$$\left.\frac{\partial c_s}{\partial r}\right|_{r=0} = 0, \quad -D_s(T) \left.\frac{\partial c_s}{\partial r}\right|_{r=R_p} = \frac{j_{\text{intercalation}}}{F}$$

The solid diffusion coefficient follows Arrhenius temperature kinetics:
$$D_s(T) = D_{s,\text{ref}} \exp\left( -\frac{E_{a,D}}{R}\left(\frac{1}{T} - \frac{1}{T_{\text{ref}}}\right) \right)$$

Thermodynamic lithium plating occurs when the local potential of the solid graphite matrix $\Phi_s$ drops below the adjacent liquid electrolyte potential $\Phi_e$:
$$\eta_{\text{plating}} = \Phi_s - \Phi_e = U_{\text{ocv}}(c_{s,\text{surf}}) + \eta_{\text{ct}} + \Delta \Phi_{\text{electrolyte}}$$
When $\eta_{\text{plating}} \le 0\text{ V}$, metallic lithium deposition initiates according to the plating Butler-Volmer kinetics:
$$j_{\text{plating}} = -j_{0,\text{plating}} \left[ \exp\left( -\frac{\alpha_c F}{R T} \eta_{\text{plating}} \right) - \exp\left( \frac{\alpha_a F}{R T} \eta_{\text{plating}} \right) \right]$$

---

### 2.3 Decoupled Multi-Rate Dual-UKF Joint Estimation
Battery dynamics span widely divergent time horizons: State of Charge ($\text{SOC}$) responds at high frequencies ($10\text{ Hz}$), whereas internal impedance and diffusion capacitances drift slowly ($0.5\text{ Hz}$). We decouple the state and parameter filters:

1. **Fast State Filter ($10\text{ Hz}$)**:
   $$\mathbf{x}_k = \begin{bmatrix} \text{SOC}_k & V_{1,k} & V_{2,k} \end{bmatrix}^T$$
2. **Slow Parameter Filter ($0.5\text{ Hz}$)**:
   $$\boldsymbol{\theta}_k = \begin{bmatrix} R_0 & R_1 & C_1 & R_2 & C_2 \end{bmatrix}^T$$

To prevent covariance degradation and non-positive-definiteness under ill-conditioned measurement noise, covariance updates are strictly computed in the Joseph-stabilized form:
$$\mathbf{P}_k = (\mathbf{I} - \mathbf{K}_k \mathbf{H}_k) \mathbf{P}_k^- (\mathbf{I} - \mathbf{K}_k \mathbf{H}_k)^T + \mathbf{K}_k \mathbf{R}_k \mathbf{K}_k^T$$
guaranteeing $\min(\text{eig}(\mathbf{P}_k)) > 0$ and condition number $\kappa(\mathbf{P}_k) < 10^6$.

---

### 2.4 3D Axisymmetric Anisotropic Thermal PINN
Axisymmetric heat transfer within cylindrical cells (radius $R$, height $H$) satisfies:
$$\rho c_p \frac{\partial T}{\partial t} = \frac{1}{r} \frac{\partial}{\partial r}\left(k_r r \frac{\partial T}{\partial r}\right) + \frac{\partial}{\partial z}\left(k_z \frac{\partial T}{\partial z}\right) + \dot{q}_{\text{vol}}$$
where $k_r = 1.2\,\text{W/(m}\cdot\text{K)}$ and $k_z = 28.0\,\text{W/(m}\cdot\text{K)}$. At the centerline ($r \to 0$), the singularity is resolved analytically via L'Hôpital's rule:
$$\lim_{r \to 0} \frac{1}{r} \frac{\partial T}{\partial r} = \frac{\partial^2 T}{\partial r^2} \implies \left.\rho c_p \frac{\partial T}{\partial t}\right|_{r=0} = 2 k_r \left.\frac{\partial^2 T}{\partial r^2}\right|_{r=0} + k_z \left.\frac{\partial^2 T}{\partial z^2}\right|_{r=0} + \dot{q}_{\text{vol}}$$

Boundary cooling enforces Robin convective heat exchange:
$$-k_r \left.\frac{\partial T}{\partial r}\right|_{r=R} = h_{\text{conv}} \left( T(R, z, t) - T_{\text{amb}} \right)$$

---

### 2.5 Quasi-Resonant Zero-Voltage-Switching (ZVS) Power Stage
Bidirectional energy transfer uses a quasi-resonant flyback architecture. The resonant tank impedance and frequency are:
$$Z_0 = \sqrt{\frac{L_m}{C_{\text{oss}}}}, \quad \omega_0 = \frac{1}{\sqrt{L_m C_{\text{oss}}}}, \quad f_r = \frac{\omega_0}{2\pi} \approx 2.32\,\text{MHz}$$

The zero-voltage-switching turn-on condition requires sufficient magnetizing energy:
$$\frac{1}{2} L_m I_{\text{pk}}^2 \ge \frac{1}{2} C_{\text{oss}} V_{\text{bus}}^2 \implies I_{\text{pk}} \ge \frac{V_{\text{bus}}}{Z_0}$$
At nominal $1.8\text{ A}$ transfer, ZVS suppresses capacitive discharge switching losses by $85\%$, achieving $93.0\%$ electrical round-trip transfer efficiency.

---

## 3. MATLAB / Simulink Digital Twin Parity & Verification

To satisfy automotive V-cycle verification standards (ISO 26262 ASIL-D), the repository includes a complete MATLAB / Simulink Digital Twin suite in `matlab_simulink_demo/`.

| Dimension | Metric | Validated Result | Standard Bound |
| :--- | :--- | :--- | :--- |
| **2RC Terminal Voltage** | RMSE ($V_{\text{term}}$) | **$0.59\text{ mV}$** | $< 1.15\text{ mV}$ |
| **Thermal Conduction** | Peak Core Difference | **$0.040^\circ\text{C}$** | $< 0.080^\circ\text{C}$ |
| **Acoustic Wave Delay** | ToF Discrepancy | **$11.4\text{ ps}$** | $< 12.0\text{ ps}$ |
| **4S Voltage Spread** | Suppression ($185 \rightarrow 18.2\text{ mV}$) | **$90.2\%$** | $> 85.0\%$ |
| **4S SOC Spread** | Variance Reduction ($23.0\% \rightarrow 3.2\%$) | **$-86.1\%$** | $< 5.0\%$ Final |
| **Sim-to-Real Transfer** | Bench Accuracy (5 Ah Pouch) | **$100.0\%$** | $> 95.0\%$ |
| **Sim-to-Real Transfer** | SOH MAE (5 Ah Pouch) | **$2.28\%$** | $< 3.00\%$ |

---

## 4. Empirical Drive Cycle Benchmarks

Dynamic performance was benchmarked across standard automotive drive cycles:
- **WLTP Class 3b** ($1800\text{ s}$ dynamic mixed highway/urban driving)
- **US06 Aggressive** ($600\text{ s}$ high-acceleration highway stress)
- **UDDS Urban** ($1370\text{ s}$ stop-and-go city transit)

```
WLTP Class 3b Benchmark:
  Passive Dissipative Bleeder (100 mA):
    Runtime:       1592 s (premature cutoff due to Cell #3)
    Usable Energy: 8.60 Wh
    Stranded SOC:  41.0%
    Heat Waste:    1.09 Wh

  Proposed Quasi-Resonant Active Balancer (1.8 A):
    Runtime:       1800 s (completed full drive cycle)
    Usable Energy: 10.98 Wh (+27.7% Usable Energy Gain)
    Stranded SOC:  37.5%
    Heat Waste:    0.23 Wh (-78.7% Heat Loss Reduction)
```

---

## 5. Trimodal Early Plating Detection & Ablation Study

Evaluation across 100 cell degradation profiles (50 plated, 50 unplated):

| Diagnostic Configuration | Detection Accuracy (%) | False Alarm Rate (%) | Lead Time Before Short |
| :--- | :--- | :--- | :--- |
| **Standard Commercial BMS (Voltage + Temp)** | 52.0% | 2.0% | 0.0 cycles (Post-rupture only) |
| **Uni-Modal DRT ($R_{\text{sei}}$ only)** | 87.0% | 6.0% | 2.1 cycles |
| **Uni-Modal Ultrasonic ($2.0\text{ MHz}$ CWI)** | 91.0% | 4.0% | 2.4 cycles |
| **Proposed Trimodal Fusion (SPMe + CWI + DRT)**| **97.0%** | **0.0%** | **3.1 cycles** |

---

## 6. Hardware Implementation & Edge Execution

- **Bill of Materials**: \$41.70 per cell single-board computer; \$1,111.50 full 4S1P test bench.
- **Microcontroller**: STMicroelectronics STM32H743ZI (ARM Cortex-M7 @ 480 MHz).
- **Time-to-Digital Converter**: Texas Instruments TDC7200 ($55\text{ ps}$ timing resolution).
- **Quantized Edge Neural Network**: $5.84\text{ KB}$ Int8 weights deployed to flash memory.
- **Inference Latency**: $1.41\text{ ms}$ per step on ARM Cortex-M7 ($> 300\times$ faster than $10\text{ Hz}$ sampling interval).

---

## 7. Open-Source Reproduction & Academic Verification

All benchmarks, analytical solutions, and LaTeX tables can be reproduced with:
```bash
# 1. Run scientific benchmark suite
python run_research_benchmarks.py

# 2. Run analytical mathematical physics tests
pytest tests/test_analytical_benchmarks.py -v

# 3. Run full master test suite (130/130 passing)
pytest tests/ -v
```
