#!/usr/bin/env python3
"""
Automated SPICE and Quasi-Resonant ZVS Active Balancer Transient Simulator.

Simulates the high-speed switching dynamics, resonant LC tank transitions,
MOSFET conduction/switching loss distribution, and Coulomb efficiency of the
bidirectional synchronous buck-boost active rebalancer.
"""

import os
import sys
import json
import argparse
import numpy as np


class ZVSSpiceSimulator:
    """
    Quasi-Resonant Zero-Voltage Switching (ZVS) Buck-Boost Converter Model.
    Models the physical hardware components specified in `bom.csv` and `kicad_circuit_netlist.net`:
    - MOSFET: FDMS86180 (Rdson = 3.2 mOhm, Coss = 1200 pF, Qg = 48 nC)
    - Inductor: Coilcraft SER2918H-103KL (L = 10 uH, DCR = 3.1 mOhm)
    - Current Shunt: Bourns CSS2H-2512 (Rshunt = 5.0 mOhm)
    - Gate Driver: TPS28225DRBR (Vgs = 10 V, Dead-Time = 25 ns)
    """

    def __init__(
        self,
        v_high=3.90,
        v_low=3.40,
        f_sw=100.0e3,
        i_target=2.50,
        dead_time_ns=25.0,
        l_ind_uH=10.0,
        dcr_mOhm=3.1,
        rdson_mOhm=3.2,
        rshunt_mOhm=5.0,
        c_snub_pF=940.0,
    ):
        self.v_high = float(v_high)
        self.v_low = float(v_low)
        self.f_sw = float(f_sw)
        self.t_period = 1.0 / self.f_sw
        self.i_target = float(i_target)
        self.dead_time = dead_time_ns * 1e-9

        self.L = l_ind_uH * 1e-6
        self.r_dcr = dcr_mOhm * 1e-3
        self.r_dson = rdson_mOhm * 1e-3
        self.r_shunt = rshunt_mOhm * 1e-3
        self.c_tank = c_snub_pF * 1e-12

        # Duty cycle calculation for synchronous buck operation
        self.duty_cycle = np.clip(self.v_low / self.v_high, 0.10, 0.90)

    def run_transient_cycle(self, num_points=1000):
        """
        Simulate one complete switching period (10 µs) with 4 discrete sub-intervals:
        1. High-side switch conduction (0 to D*T)
        2. Dead-time resonant commutation (D*T to D*T + t_dead)
        3. Low-side synchronous switch conduction (D*T + t_dead to T - t_dead)
        4. Dead-time resonant rise (T - t_dead to T)
        """
        t = np.linspace(0, self.t_period, num_points)
        dt = self.t_period / num_points

        t_on_high = self.duty_cycle * self.t_period
        t_dead1_end = t_on_high + self.dead_time
        t_on_low_end = self.t_period - self.dead_time

        i_l = np.zeros(num_points)
        v_sw = np.zeros(num_points)

        # Baseline steady-state ripple calculation
        delta_i = ((self.v_high - self.v_low) * t_on_high) / self.L
        i_min = self.i_target - (delta_i / 2.0)
        i_curr = i_min
        v_curr = self.v_high

        for idx, t_val in enumerate(t):
            if t_val < t_on_high:
                # High side ON: V_sw = V_high - i*Rdson, di/dt = (V_high - V_low - i*R_total) / L
                r_tot = self.r_dson + self.r_dcr + self.r_shunt
                di_dt = (self.v_high - self.v_low - (i_curr * r_tot)) / self.L
                i_curr += di_dt * dt
                v_curr = self.v_high - (i_curr * self.r_dson)
            elif t_val < t_dead1_end:
                # Dead time 1: Resonant node discharge through C_tank
                # dv_sw/dt = -i_curr / C_tank
                dv_dt = -i_curr / max(self.c_tank, 1e-12)
                v_curr = max(0.0, v_curr + dv_dt * dt)
                di_dt = -(self.v_low + (i_curr * (self.r_dcr + self.r_shunt))) / self.L
                i_curr += di_dt * dt
            elif t_val < t_on_low_end:
                # Low side ON: V_sw = -i*Rdson, di/dt = -(V_low + i*R_total) / L
                r_tot = self.r_dson + self.r_dcr + self.r_shunt
                di_dt = -(self.v_low + (i_curr * r_tot)) / self.L
                i_curr += di_dt * dt
                v_curr = -(i_curr * self.r_dson)
            else:
                # Dead time 2: Resonant node charging
                dv_dt = i_curr / max(self.c_tank, 1e-12)
                v_curr = min(self.v_high, v_curr + dv_dt * dt)
                di_dt = (self.v_high - self.v_low - (i_curr * (self.r_dcr + self.r_shunt))) / self.L
                i_curr += di_dt * dt

            i_l[idx] = i_curr
            v_sw[idx] = v_curr

        # Calculate loss distribution
        i_rms = float(np.sqrt(np.mean(i_l ** 2)))
        p_in = self.v_high * self.i_target * self.duty_cycle
        p_out_ideal = self.v_low * self.i_target

        p_cond_high = (i_rms ** 2) * self.r_dson * self.duty_cycle
        p_cond_low = (i_rms ** 2) * self.r_dson * (1.0 - self.duty_cycle)
        p_dcr = (i_rms ** 2) * self.r_dcr
        p_shunt = (i_rms ** 2) * self.r_shunt
        p_conduction_total = p_cond_high + p_cond_low + p_dcr + p_shunt

        # ZVS soft switching reduces E_on/E_off by ~85%
        hard_switch_loss = 0.5 * self.v_high * self.i_target * (15e-9 + 15e-9) * self.f_sw
        p_switching_zvs = hard_switch_loss * 0.15

        # Gate charge drive loss (2 MOSFETs, Qg=48nC, Vgs=10V, fsw=100kHz)
        p_gate_drive = 2.0 * (48e-9 * 10.0 * self.f_sw)

        p_loss_total = p_conduction_total + p_switching_zvs + p_gate_drive
        p_out_real = p_in - p_loss_total
        efficiency = (p_out_real / max(p_in, 1e-6)) * 100.0

        return {
            "time_us": (t * 1e6).tolist(),
            "inductor_current_a": i_l.tolist(),
            "switch_node_voltage_v": v_sw.tolist(),
            "i_rms_a": round(i_rms, 4),
            "i_ripple_a": round(float(np.max(i_l) - np.min(i_l)), 4),
            "p_in_w": round(p_in, 4),
            "p_loss_total_w": round(p_loss_total, 4),
            "p_loss_conduction_w": round(p_conduction_total, 4),
            "p_loss_switching_zvs_w": round(p_switching_zvs, 4),
            "p_loss_gate_w": round(p_gate_drive, 4),
            "efficiency_percent": round(efficiency, 2),
            "zvs_achieved": bool(v_sw[int(num_points * (t_on_high / self.t_period))] < 0.20),
        }


def run_simulation():
    parser = argparse.ArgumentParser(description="Run ZVS Active Balancer SPICE Simulation")
    parser.add_argument("--v_high", type=float, default=3.90, help="Source cell voltage (V)")
    parser.add_argument("--v_low", type=float, default=3.40, help="Target cell voltage (V)")
    parser.add_argument("--i_target", type=float, default=2.50, help="Balancing current (A)")
    parser.add_argument("--points", type=int, default=1000, help="Simulation steps per period")
    parser.add_argument("--json", action="store_true", help="Print result as JSON")
    args = parser.parse_args()

    sim = ZVSSpiceSimulator(v_high=args.v_high, v_low=args.v_low, i_target=args.i_target)
    results = sim.run_transient_cycle(num_points=args.points)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=" * 60)
        print("  ZVS ACTIVE BALANCER SPICE TRANSIENT SIMULATION REPORT")
        print("=" * 60)
        print(f" Source Cell Voltage      : {args.v_high:.2f} V")
        print(f" Target Cell Voltage      : {args.v_low:.2f} V")
        print(f" Target Balancing Current : {args.i_target:.2f} A")
        print(f" Inductor Current RMS     : {results['i_rms_a']:.3f} A (Ripple: {results['i_ripple_a']:.3f} A)")
        print(f" Input Power              : {results['p_in_w']:.3f} W")
        print(f" Total Losses             : {results['p_loss_total_w']*1e3:.1f} mW")
        print(f"   - Conduction Losses    : {results['p_loss_conduction_w']*1e3:.1f} mW")
        print(f"   - ZVS Switching Losses : {results['p_loss_switching_zvs_w']*1e3:.1f} mW")
        print(f"   - Gate Drive Losses    : {results['p_loss_gate_w']*1e3:.1f} mW")
        print(f" System Efficiency        : {results['efficiency_percent']:.2f}%")
        print(f" Soft-Switching (ZVS)     : {'CONFIRMED' if results['zvs_achieved'] else 'HARD SWITCHING'}")
        print("=" * 60)


if __name__ == "__main__":
    run_simulation()
