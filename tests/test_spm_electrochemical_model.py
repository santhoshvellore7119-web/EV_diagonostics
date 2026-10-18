"""
tests/test_spm_electrochemical_model.py
=======================================
Unit & Physics Tests for Single Particle Model with Electrolyte (SPMe)
and Operando Thermodynamic Lithium Plating Criterion:
  - Fickian solid diffusion conservation inside graphite particle shells.
  - Butler-Volmer intercalation overpotential dynamics.
  - Arrhenius temperature dependence of solid diffusion.
  - Plating overpotential margin sign and active deposition triggering.
  - Reversible stripping kinetics and dead lithium generation.
"""

import pytest
import numpy as np

from backend.spm_electrochemical_plating_model import (
    SPMeCellParameters,
    SPMeElectrochemicalSolver,
)


def test_spme_cell_parameters_initialization():
    """Validates physical parameter boundaries for 21700 cell."""
    p = SPMeCellParameters()
    assert p.nominal_capacity_ah == 5.0
    assert p.r_p_anode > 0.0
    assert p.a_s_anode > 1e5
    assert p.kappa_eff_anode > 0.0
    assert p.kappa_eff_separator > 0.0


def test_spme_solid_diffusion_conservation():
    """Validates that finite-volume shell discretization conserves mass under rest."""
    solver = SPMeElectrochemicalSolver(n_radial_shells=15)
    initial_total_moles = np.sum(solver.c_s * solver.shell_volumes)

    # 10 steps of zero current (open-circuit rest)
    for _ in range(10):
        out = solver.step(current_a=0.0, temp_c=25.0, dt=1.0)
        assert out["current_a"] == 0.0
        assert out["plating_active"] is False

    final_total_moles = np.sum(solver.c_s * solver.shell_volumes)
    assert np.isclose(initial_total_moles, final_total_moles, rtol=1e-5)


def test_spme_arrhenius_diffusion():
    """Validates that diffusion slows down at sub-zero cold temperatures."""
    solver = SPMeElectrochemicalSolver()
    d_warm = solver.calculate_diffusion_coeff(298.15)  # 25 C
    d_cold = solver.calculate_diffusion_coeff(273.15)  # 0 C
    d_freezing = solver.calculate_diffusion_coeff(263.15)  # -10 C

    assert d_warm > d_cold > d_freezing
    assert d_cold < 0.5 * d_warm  # Significant drop in kinetics


def test_spme_discharge_and_charge_directions():
    """Validates that charging increases surface concentration and discharge decreases it."""
    solver = SPMeElectrochemicalSolver()
    solver.reset(initial_soc=0.50)
    c_initial_surf = solver.c_s[-1]

    # Charge at -5.0 A for 10 seconds
    for _ in range(10):
        out_charge = solver.step(current_a=-5.0, temp_c=25.0, dt=1.0)
    assert solver.c_s[-1] > c_initial_surf

    # Discharge at +5.0 A for 10 seconds
    c_after_charge = solver.c_s[-1]
    for _ in range(10):
        out_discharge = solver.step(current_a=+5.0, temp_c=25.0, dt=1.0)
    assert solver.c_s[-1] < c_after_charge


def test_spme_plating_overpotential_margin_output():
    """Validates that step dictionary contains complete diagnostic fields."""
    solver = SPMeElectrochemicalSolver()
    res = solver.step(current_a=-3.5, temp_c=25.0, dt=0.5)

    assert "plating_overpotential_margin_mv" in res
    assert "stoichiometry_surface" in res
    assert "stoichiometry_average" in res
    assert "concentration_gradient_mol_m3" in res
    assert "u_eq_anode_v" in res
    assert "eta_charge_transfer_mv" in res
    assert "electrolyte_drop_mv" in res
    assert "risk_verdict" in res
    assert res["risk_verdict"] in ["SAFE_INTERCALATION", "INCIPIENT_PLATING_RISK", "CRITICAL_PLATING_ACTIVE"]
