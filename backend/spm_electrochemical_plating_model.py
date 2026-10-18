"""
backend/spm_electrochemical_plating_model.py
============================================
Physics-Based Single Particle Model with Electrolyte Dynamics (SPMe)
and Operando Anode Lithium Plating Overpotential Criterion.

Theoretical Framework:
1. Solid-Phase Fickian Diffusion in Spherical Graphite Particles:
   dr/dt (c_s) = (D_s / r^2) * d/dr [ r^2 * d(c_s)/dr ]
   BC 1 (Core Symmetry): d(c_s)/dr |_{r=0} = 0
   BC 2 (Interfacial Flux): -D_s * d(c_s)/dr |_{r=R_p} = j_intercalation / F

2. Butler-Volmer Charge-Transfer Intercalation Kinetics:
   j_intercalation = 2 * j_0 * sinh( (alpha * F / (R * T)) * eta_intercalation )
   where j_0 = k_0 * (c_e)^alpha * (c_s,max - c_s,surf)^alpha * (c_s,surf)^(1-alpha)

3. Electrolyte Phase Potential Drop across Porous Separator and Anode:
   Delta_Phi_e = I * ( L_anode / (2 * kappa_eff_anode) + L_separator / kappa_eff_separator )

4. Thermodynamic Lithium Plating Overpotential Margin:
   eta_plating(t) = Phi_s,anode(t) - Phi_e,anode(t) - U_plating
   where U_plating = 0.0 V vs Li/Li+.
   - If eta_plating >= 0 mV: Plating is thermodynamically prohibited (Safe).
   - If eta_plating < 0 mV: Metallic lithium dendrite deposition actively occurs.

5. Metallic Lithium Deposition and Reversible Stripping Rate:
   j_plating = -j_0,plating * exp( -alpha_c * F / (R * T) * eta_plating )  [when eta_plating < 0]
   dm_Li/dt = (M_Li / F) * |j_plating| * Area_anode
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional, List
import numpy as np


@dataclass
class SPMeCellParameters:
    """Electrochemical and geometric parameters for a 21700 NMC811/Graphite cell."""
    name: str = "21700_NMC811_5.0Ah"
    nominal_capacity_ah: float = 5.0
    cell_radius_m: float = 0.0105             # 10.5 mm
    cell_height_m: float = 0.0700             # 70.0 mm
    
    # Negative Electrode (Graphite Anode)
    r_p_anode: float = 8.0e-6                 # Particle radius [m] (8 um)
    l_anode: float = 85.0e-6                  # Electrode thickness [m] (85 um)
    eps_s_anode: float = 0.65                 # Active material volume fraction
    eps_e_anode: float = 0.28                 # Electrolyte porosity
    c_s_max_anode: float = 31500.0            # Max solid lithium concentration [mol/m^3]
    d_s_ref_anode: float = 3.9e-14            # Reference solid diffusion coefficient [m^2/s]
    e_act_ds: float = 35000.0                 # Activation energy for solid diffusion [J/mol]
    k_0_anode: float = 1.76e-11               # Reaction rate constant [mol/(m^2 s (mol/m^3)^1.5)]
    
    # Separator & Electrolyte
    l_separator: float = 16.0e-6              # Separator thickness [m] (16 um)
    eps_e_separator: float = 0.45             # Separator porosity
    c_e_nominal: float = 1000.0               # Bulk electrolyte salt concentration [mol/m^3] (1.0 M LiPF6)
    t_plus: float = 0.38                      # Lithium transference number
    bruggeman_exp: float = 1.5                # Bruggeman tortuosity exponent
    kappa_bulk: float = 1.15                  # Bulk electrolyte conductivity at 298K [S/m]
    
    # Physical Constants
    f_const: float = 96485.332                # Faraday constant [C/mol]
    r_gas: float = 8.31446                    # Universal gas constant [J/(mol K)]
    t_ref: float = 298.15                     # Reference temperature [K] (25 deg C)
    m_li: float = 6.941e-3                    # Molar mass of lithium [kg/mol]
    rho_li: float = 534.0                     # Density of metallic lithium [kg/m^3]
    
    # Plating Parameters
    j_0_plating: float = 0.015                # Exchange current density for Li plating [A/m^2]
    alpha_c_plating: float = 0.50             # Cathodic transfer coefficient for Li plating
    alpha_a_plating: float = 0.50             # Anodic transfer coefficient for Li stripping

    @property
    def a_s_anode(self) -> float:
        """Specific interfacial surface area per unit electrode volume [m^-1]."""
        return 3.0 * self.eps_s_anode / self.r_p_anode

    @property
    def total_electrode_area(self) -> float:
        """Total jelly-roll unwound surface area [m^2] (~0.095 m^2 for 21700 cell)."""
        return 0.095

    @property
    def kappa_eff_anode(self) -> float:
        """Effective electrolyte conductivity in anode porous matrix [S/m]."""
        return self.kappa_bulk * (self.eps_e_anode ** self.bruggeman_exp)

    @property
    def kappa_eff_separator(self) -> float:
        """Effective electrolyte conductivity in separator matrix [S/m]."""
        return self.kappa_bulk * (self.eps_e_separator ** self.bruggeman_exp)


class SPMeElectrochemicalSolver:
    """
    Finite-Volume Discretized Single Particle Model with Electrolyte Overpotentials (SPMe)
    and Thermodynamic Lithium Plating Criterion.
    """

    def __init__(self, params: Optional[SPMeCellParameters] = None, n_radial_shells: int = 20):
        self.p = params or SPMeCellParameters()
        self.nr = n_radial_shells

        # Radial discretization for spherical particle: r in [0, R_p]
        self.r_edges = np.linspace(0.0, self.p.r_p_anode, self.nr + 1, dtype=np.float64)
        self.r_centers = 0.5 * (self.r_edges[:-1] + self.r_edges[1:])
        self.dr = float(self.r_edges[1] - self.r_edges[0])

        # Cell volumes for spherical shells: V_i = (4/3)*pi*(r_{i+1}^3 - r_i^3)
        self.shell_volumes = (4.0 / 3.0) * np.pi * (self.r_edges[1:] ** 3 - self.r_edges[:-1] ** 3)
        self.interface_areas = 4.0 * np.pi * (self.r_edges[1:-1] ** 2)

        # State Variables
        # Initial equilibrium solid concentration profile: 80% SOC graphite stoichiometry (~0.68)
        self.c_s = np.full(self.nr, 0.68 * self.p.c_s_max_anode, dtype=np.float64)
        self.accumulated_plated_li_mg = 0.0      # Total metallic lithium plated [mg]
        self.accumulated_dead_li_mg = 0.0        # Irreversible "dead" lithium [mg]
        self.plating_active = False

    @staticmethod
    def u_anode_graphite(stoich: np.ndarray | float) -> np.ndarray | float:
        """
        Analytical equilibrium Open-Circuit Potential of Graphite Anode U_n(x) [V vs Li/Li+]
        as a function of lithium stoichiometry x = c_s,surf / c_s,max.
        Reference: Safari & Delacourt (J. Electrochem. Soc. 2011).
        """
        x = np.clip(stoich, 0.001, 0.999)
        u_eq = (
            0.7222
            + 0.1387 * np.sqrt(x)
            - 0.0290 * x
            - 0.0172 / x
            + 0.0190 / np.sqrt(x)
            + 0.2808 * np.exp(0.90 - 15.0 * x)
            - 0.7984 * (1.0 + np.tanh((x - 0.156) / 0.0361))
            - 0.3800 * (1.0 + np.tanh((x - 0.530) / 0.0340))
            - 0.0716 * (1.0 + np.tanh((x - 0.750) / 0.0440))
        )
        return np.maximum(0.005, u_eq)

    def calculate_diffusion_coeff(self, temp_k: float) -> float:
        """Evaluates Arrhenius temperature-dependent solid diffusion coefficient D_s(T)."""
        temp_k = max(240.0, min(350.0, temp_k))
        arrh = np.exp(-(self.p.e_act_ds / self.p.r_gas) * (1.0 / temp_k - 1.0 / self.p.t_ref))
        return float(self.p.d_s_ref_anode * arrh)

    def step(
        self,
        current_a: float,
        temp_c: float = 25.0,
        dt: float = 0.1
    ) -> Dict[str, Any]:
        """
        Advances the electrochemical state by dt seconds under current_a [A]
        (current_a > 0 = discharge, current_a < 0 = charging).
        """
        temp_k = temp_c + 273.15
        d_s = self.calculate_diffusion_coeff(temp_k)

        # 1. Total interfacial pore-wall flux density j_tot [A / m^2 of particle surface]
        total_particle_area = self.p.a_s_anode * (self.p.l_anode * self.p.total_electrode_area)
        # For anode: discharge (current_a > 0) de-intercalates lithium (j_flux < 0)
        # Charging (current_a < 0) intercalates lithium into graphite (j_flux > 0)
        j_applied = (-current_a) / max(total_particle_area, 1e-6)

        # 2. Update Spherical Solid Diffusion via Finite-Volume Conservation
        # Internal flux between shells (+r direction): F_{i+1/2} = -D_s * (c_{i+1} - c_i) / dr * Area
        internal_grad = (self.c_s[1:] - self.c_s[:-1]) / self.dr
        f_int = -d_s * internal_grad * self.interface_areas  # [mol/s]

        # Rate of mole accumulation in each spherical shell dn_i/dt:
        # shell 0 (core): receives 0 from center, loses f_int[0] to shell 1
        # shell i (middle): receives f_int[i-1], loses f_int[i]
        # shell nr-1 (surface): receives f_int[-1] from interior, plus flux entering from surface
        outer_area = 4.0 * np.pi * (self.p.r_p_anode ** 2)
        flux_entering_surface = (j_applied / self.p.f_const) * outer_area  # [mol/s]

        dn_dt = np.zeros(self.nr, dtype=np.float64)
        dn_dt[0] = -f_int[0]
        if self.nr > 2:
            dn_dt[1:-1] = f_int[:-1] - f_int[1:]
        dn_dt[-1] = f_int[-1] + flux_entering_surface

        # Update shell concentrations: dc_i/dt = dn_i/dt / V_i
        dc_s_dt = dn_dt / self.shell_volumes
        self.c_s = np.clip(self.c_s + dc_s_dt * dt, 10.0, self.p.c_s_max_anode * 0.995)

        c_s_surf = float(self.c_s[-1])
        c_s_avg = float(np.sum(self.c_s * self.shell_volumes) / np.sum(self.shell_volumes))
        stoich_surf = c_s_surf / self.p.c_s_max_anode
        stoich_avg = c_s_avg / self.p.c_s_max_anode

        # 3. Intercalation Equilibrium Potential and Overpotentials
        u_eq_anode = float(self.u_anode_graphite(stoich_surf))

        # Butler-Volmer exchange current density j_0 [A/m^2]
        term1 = (self.p.c_e_nominal) ** 0.5
        term2 = max(1e-3, self.p.c_s_max_anode - c_s_surf) ** 0.5
        term3 = max(1e-3, c_s_surf) ** 0.5
        j_0 = self.p.f_const * self.p.k_0_anode * term1 * term2 * term3
        j_0 = max(1e-4, j_0)

        # Invert Butler-Volmer to find charge-transfer overpotential eta_ct:
        # j = 2 * j_0 * sinh(0.5 * F * eta_ct / (R * T))
        arg = np.clip(j_applied / (2.0 * j_0), -100.0, 100.0)
        eta_ct = float((2.0 * self.p.r_gas * temp_k / self.p.f_const) * np.arcsinh(arg))

        # Electrolyte ohmic potential drop across porous separator and anode:
        # Delta_Phi_e = I * [ L_anode / (2 * kappa_eff_anode) + L_separator / kappa_eff_sep ] / Area
        r_electrolyte = (
            (self.p.l_anode / (2.0 * self.p.kappa_eff_anode) + self.p.l_separator / self.p.kappa_eff_separator)
            / self.p.total_electrode_area
        )
        delta_phi_e = float(current_a * r_electrolyte)

        # Solid phase potential at anode surface:
        # Phi_s,anode = U_anode(stoich_surf) + eta_ct + Delta_Phi_e
        phi_s_anode = u_eq_anode + eta_ct + delta_phi_e

        # 4. Thermodynamic Lithium Plating Overpotential Margin:
        # Plating potential = Phi_s - Phi_e - U_plating (where U_plating = 0 V vs Li/Li+)
        # Relative to Li reference: eta_plating = Phi_s_anode - Delta_Phi_e
        eta_plating = u_eq_anode + eta_ct
        plating_margin_mv = float(eta_plating * 1000.0)

        # 5. Metallic Lithium Deposition / Stripping Kinetics:
        j_plating = 0.0
        delta_plated_mg = 0.0

        if plating_margin_mv < 0.0 and current_a < 0.0:
            # Active Fast-Charging Metallic Plating Condition!
            self.plating_active = True
            # Butler-Volmer / Tafel side reaction current density
            eta_plat_volts = eta_plating
            exp_term = np.exp(-self.p.alpha_c_plating * self.p.f_const * eta_plat_volts / (self.p.r_gas * temp_k))
            j_plating = float(self.p.j_0_plating * exp_term)  # [A/m^2]
            
            # Rate of mass accumulation: dm/dt = (M_Li / F) * j_plating * Area [kg/s]
            dm_dt = (self.p.m_li / self.p.f_const) * j_plating * self.p.total_electrode_area
            delta_plated_mg = dm_dt * dt * 1e6
            self.accumulated_plated_li_mg += delta_plated_mg
        elif current_a >= 0.0 and self.accumulated_plated_li_mg > 0.0:
            # Chemical/Electrochemical Stripping during Rest or Discharge
            self.plating_active = False
            # Reversible dissolution rate
            strip_rate_mg_s = 0.005 * (temp_k / 298.15)
            stripped_mg = min(self.accumulated_plated_li_mg, strip_rate_mg_s * dt)
            self.accumulated_plated_li_mg -= stripped_mg
            # 12% converts into irreversible "dead" isolated lithium
            self.accumulated_dead_li_mg += stripped_mg * 0.12
        else:
            self.plating_active = False

        # Equivalent dendrite thickness estimate [microns]
        # Thickness = mass / (density * Area)
        dendrite_thickness_um = float(
            (self.accumulated_plated_li_mg * 1e-6)
            / (self.p.rho_li * self.p.total_electrode_area)
            * 1e6
        )

        return {
            "current_a": float(current_a),
            "temp_c": float(temp_c),
            "stoichiometry_surface": round(stoich_surf, 4),
            "stoichiometry_average": round(stoich_avg, 4),
            "concentration_gradient_mol_m3": round(float(c_s_surf - self.c_s[0]), 1),
            "u_eq_anode_v": round(u_eq_anode, 4),
            "eta_charge_transfer_mv": round(eta_ct * 1000.0, 2),
            "electrolyte_drop_mv": round(delta_phi_e * 1000.0, 2),
            "plating_overpotential_margin_mv": round(plating_margin_mv, 2),
            "plating_active": self.plating_active,
            "accumulated_plated_li_mg": round(self.accumulated_plated_li_mg, 4),
            "accumulated_dead_li_mg": round(self.accumulated_dead_li_mg, 4),
            "estimated_dendrite_thickness_um": round(dendrite_thickness_um, 3),
            "risk_verdict": (
                "CRITICAL_PLATING_ACTIVE" if plating_margin_mv < -15.0
                else "INCIPIENT_PLATING_RISK" if plating_margin_mv < 5.0
                else "SAFE_INTERCALATION"
            )
        }

    def reset(self, initial_soc: float = 0.80) -> None:
        """Resets the internal solid concentration profile and plating counters."""
        init_stoich = np.clip(initial_soc * 0.85, 0.05, 0.85)
        self.c_s = np.full(self.nr, init_stoich * self.p.c_s_max_anode, dtype=np.float64)
        self.accumulated_plated_li_mg = 0.0
        self.accumulated_dead_li_mg = 0.0
        self.plating_active = False


# Global singleton instance for live real-time simulation
spme_solver_singleton = SPMeElectrochemicalSolver()
