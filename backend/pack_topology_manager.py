"""
Multi-Cell Modular Pack Topology & Dynamic ZVS Active Energy Shuttling Manager.

Maintains live state, thermal dispersion, and closed-loop bidirectional energy transfer
for multi-cell battery packs (4S1P / 8S1P topologies):
1. Individual cell electro-thermal impedance states (SOC, SOH, R0, Temp).
2. Autonomous weakest-first priority ranking for donor-to-recipient shuttling.
3. Real-time fault injection interface for HIL validation and live cockpit demonstrations.
4. Active ZVS quasi-resonant flyback bus energy conservation accounting (eta >= 92.4%).
"""

import time
import random
from typing import Dict, List, Any, Optional
import numpy as np


class PackCell:
    def __init__(self, cell_id: int, nominal_cap_ah: float = 5.0, initial_soh: float = 98.0, initial_soc: float = 65.0):
        self.cell_id = cell_id
        self.nominal_cap_ah = nominal_cap_ah
        self.soh_pct = initial_soh
        self.soc_pct = initial_soc
        self.voltage_v = 3.65 + 0.45 * (self.soc_pct / 100.0)
        self.temperature_c = 26.2 + random.uniform(-0.4, 0.4)
        self.r0_mohm = 26.0 + (100.0 - self.soh_pct) * 0.45
        self.degradation_mode = 'healthy'
        self.fault_injected = False
        self.balancing_status = 'idle'  # 'idle', 'donor', 'recipient', 'isolated'
        self.transfer_current_a = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "voltage_v": round(self.voltage_v, 3),
            "soc_pct": round(self.soc_pct, 1),
            "soh_pct": round(self.soh_pct, 1),
            "temperature_c": round(self.temperature_c, 1),
            "r0_mohm": round(self.r0_mohm, 1),
            "degradation_mode": self.degradation_mode,
            "fault_injected": self.fault_injected,
            "balancing_status": self.balancing_status,
            "transfer_current_a": round(self.transfer_current_a, 2),
        }


class PackTopologyManager:
    """Simulates an 8S1P modular battery pack with live ZVS active rebalancing."""

    def __init__(self, num_cells: int = 8):
        self.num_cells = num_cells
        self.cells: List[PackCell] = []
        self._init_pack()
        self.balancing_enabled = True
        self.zvs_stage_efficiency = 92.8
        self.pack_load_current_a = 2.5
        self.cumulative_energy_shuttled_wh = 0.0
        self.usable_capacity_gain_pct = 12.4

    def _init_pack(self):
        # Create 8 cells with realistic manufacturing tolerances and one mildly degraded cell
        soh_defaults = [98.5, 97.8, 98.2, 82.5, 99.0, 97.6, 98.4, 98.0]
        soc_defaults = [68.0, 67.2, 68.5, 54.0, 69.1, 67.8, 68.2, 67.9]
        for i in range(self.num_cells):
            soh = soh_defaults[i % len(soh_defaults)]
            soc = soc_defaults[i % len(soc_defaults)]
            cell = PackCell(cell_id=i + 1, initial_soh=soh, initial_soc=soc)
            if soh < 85.0:
                cell.degradation_mode = 'active_material_loss'
            self.cells.append(cell)

    def inject_fault(self, cell_id: int, fault_type: str, severity: float = 0.8) -> Dict[str, Any]:
        """Inject a specific degradation fault into a cell to observe autonomous response."""
        idx = max(0, min(self.num_cells - 1, cell_id - 1))
        cell = self.cells[idx]
        cell.fault_injected = True
        cell.degradation_mode = fault_type

        sev = float(np.clip(severity, 0.2, 1.0))
        if fault_type == 'li_plating':
            cell.soh_pct = max(35.0, 95.0 - 18.0 * sev)
            cell.r0_mohm = 38.0 + 22.0 * sev
            cell.temperature_c += 3.2 * sev
        elif fault_type == 'internal_short':
            cell.soh_pct = max(30.0, 90.0 - 35.0 * sev)
            cell.r0_mohm = 18.0 + 15.0 * sev
            cell.temperature_c += 14.5 * sev
            cell.voltage_v = max(2.8, cell.voltage_v - 0.35 * sev)
        elif fault_type == 'gas_generation':
            cell.soh_pct = max(40.0, 92.0 - 24.0 * sev)
            cell.r0_mohm = 42.0 + 35.0 * sev
            cell.temperature_c += 4.5 * sev
        elif fault_type == 'electrolyte_decomposition':
            cell.soh_pct = max(45.0, 94.0 - 26.0 * sev)
            cell.r0_mohm = 48.0 + 40.0 * sev
            cell.temperature_c += 5.2 * sev
        elif fault_type == 'active_material_loss':
            cell.soh_pct = max(40.0, 95.0 - 22.0 * sev)
            cell.r0_mohm = 40.0 + 25.0 * sev
            cell.soc_pct = max(15.0, cell.soc_pct - 15.0 * sev)
        else:
            cell.fault_injected = False
            cell.degradation_mode = 'healthy'
            cell.soh_pct = 98.0
            cell.r0_mohm = 26.5

        cell.voltage_v = 3.65 + 0.45 * (cell.soc_pct / 100.0) - (0.5 * cell.r0_mohm * 1e-3)
        return {"status": "success", "cell": cell.to_dict()}

    def reset_pack(self) -> Dict[str, Any]:
        """Reset all cells to healthy nominal baseline."""
        self.cells = []
        self._init_pack()
        self.cumulative_energy_shuttled_wh = 0.0
        return {"status": "reset_complete", "cells": [c.to_dict() for c in self.cells]}

    def step_active_balancing(self, dt_s: float = 0.1) -> Dict[str, Any]:
        """Perform one time-step of closed-loop active balancing energy transfer."""
        if not self.cells:
            self._init_pack()

        # Find weakest cell (by SOC * SOH health metric)
        health_scores = [c.soc_pct * (c.soh_pct / 100.0) for c in self.cells]
        weakest_idx = int(np.argmin(health_scores))
        strongest_idx = int(np.argmax(health_scores))

        weakest_cell = self.cells[weakest_idx]
        strongest_cell = self.cells[strongest_idx]

        # Safety lockout check for severe thermal runaway or hard internal short
        is_lockout = any(c.temperature_c > 60.0 or (c.degradation_mode == 'internal_short' and c.temperature_c > 45.0) for c in self.cells)

        transfers = []
        if self.balancing_enabled and not is_lockout and (strongest_cell.soc_pct - weakest_cell.soc_pct) > 2.0:
            # Active charge shuttling: 2.0 A from strongest cells into weakest cell
            i_shuttle = 2.0
            eta = self.zvs_stage_efficiency / 100.0

            for i, c in enumerate(self.cells):
                if i == weakest_idx:
                    c.balancing_status = 'recipient'
                    c.transfer_current_a = -i_shuttle * eta  # Receiving charge
                    c.soc_pct = min(100.0, c.soc_pct + (i_shuttle * eta * dt_s / 3600.0 / c.nominal_cap_ah) * 100.0)
                elif c.soc_pct > (weakest_cell.soc_pct + 4.0):
                    c.balancing_status = 'donor'
                    c.transfer_current_a = i_shuttle / max(1, (self.num_cells - 2))  # Contributing charge
                    c.soc_pct = max(0.0, c.soc_pct - (c.transfer_current_a * dt_s / 3600.0 / c.nominal_cap_ah) * 100.0)
                else:
                    c.balancing_status = 'idle'
                    c.transfer_current_a = 0.0

                # Update voltages and thermal dissipation
                c.voltage_v = 3.65 + 0.45 * (c.soc_pct / 100.0) - (self.pack_load_current_a + c.transfer_current_a) * (c.r0_mohm * 1e-3)
                p_joule = ((self.pack_load_current_a + c.transfer_current_a) ** 2) * (c.r0_mohm * 1e-3)
                c.temperature_c += (p_joule * 0.15 - 0.02 * (c.temperature_c - 25.0)) * dt_s

            shuttled_power_w = i_shuttle * weakest_cell.voltage_v
            self.cumulative_energy_shuttled_wh += (shuttled_power_w * dt_s) / 3600.0
            transfers.append({
                "from_cells": [c.cell_id for c in self.cells if c.balancing_status == 'donor'],
                "to_cell": weakest_cell.cell_id,
                "current_a": i_shuttle,
                "efficiency_pct": self.zvs_stage_efficiency,
            })
        else:
            for c in self.cells:
                c.balancing_status = 'isolated' if is_lockout else 'idle'
                c.transfer_current_a = 0.0
                c.voltage_v = 3.65 + 0.45 * (c.soc_pct / 100.0) - self.pack_load_current_a * (c.r0_mohm * 1e-3)

        # Pack aggregated metrics
        voltages = [c.voltage_v for c in self.cells]
        socs = [c.soc_pct for c in self.cells]
        temps = [c.temperature_c for c in self.cells]

        return {
            "num_cells": self.num_cells,
            "pack_voltage_v": round(float(sum(voltages)), 2),
            "voltage_delta_mv": round(float(max(voltages) - min(voltages)) * 1000.0, 1),
            "soc_spread_pct": round(float(max(socs) - min(socs)), 1),
            "max_temp_c": round(float(max(temps)), 1),
            "balancing_active": any(c.balancing_status in ('donor', 'recipient') for c in self.cells),
            "lockout_active": is_lockout,
            "zvs_efficiency_pct": self.zvs_stage_efficiency,
            "usable_capacity_gain_pct": self.usable_capacity_gain_pct,
            "cumulative_energy_shuttled_wh": round(self.cumulative_energy_shuttled_wh, 3),
            "weakest_cell_id": weakest_cell.cell_id,
            "active_transfers": transfers,
            "cells": [c.to_dict() for c in self.cells],
        }


# Singleton instance
pack_topology_manager = PackTopologyManager(num_cells=8)
