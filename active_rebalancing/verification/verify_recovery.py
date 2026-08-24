"""
Verification script for active recovery.
Calculates percentage capacity restored and other metrics.
"""

import numpy as np
from typing import Dict, List, Tuple
import json


class RecoveryVerifier:
    """
    Verifies the effectiveness of recovery actions by comparing
    pre- and post-recovery measurements.
    """

    def __init__(self):
        self.pre_recovery_data = {}
        self.post_recovery_data = {}
        self.recovery_action = None

    def set_pre_recovery_data(
        self,
        capacity: float,
        voltage_profile: np.ndarray = None,
        resistance: float = None,
        soh_estimate: float = None
    ):
        """
        Store pre-recovery baseline data.
        Args:
            capacity: Capacity in Ah (or mAh).
            voltage_profile: Voltage vs. time/profile during standard test.
            resistance: Internal resistance (optional).
            soh_estimate: State of Health estimate from ML model (optional).
        """
        self.pre_recovery_data = {
            'capacity': capacity,
            'voltage_profile': voltage_profile,
            'resistance': resistance,
            'soh_estimate': soh_estimate,
            'timestamp': np.datetime64('now')
        }

    def set_post_recovery_data(
        self,
        capacity: float,
        voltage_profile: np.ndarray = None,
        resistance: float = None,
        soh_estimate: float = None
    ):
        """
        Store post-recovery data.
        """
        self.post_recovery_data = {
            'capacity': capacity,
            'voltage_profile': voltage_profile,
            'resistance': resistance,
            'soh_estimate': soh_estimate,
            'timestamp': np.datetime64('now')
        }

    def set_recovery_action(self, action: str):
        """Set the recovery action that was applied."""
        self.recovery_action = action

    def compute_capacity_restored(self) -> float:
        """
        Compute percentage capacity restored.
        Returns:
            Percentage capacity restored: ((post - pre) / pre) * 100
            If post < pre, returns negative (capacity loss).
        """
        if not self.pre_recovery_data or not self.post_recovery_data:
            raise ValueError("Pre and post recovery data must be set.")

        pre_cap = self.pre_recovery_data['capacity']
        post_cap = self.post_recovery_data['capacity']

        if pre_cap == 0:
            return 0.0

        restored = ((post_cap - pre_cap) / pre_cap) * 100.0
        return restored

    def compute_soh_change(self) -> float:
        """
        Compute change in SOH estimate (if available).
        Returns:
            Change in SOH percentage points.
        """
        pre_soh = self.pre_recovery_data.get('soh_estimate')
        post_soh = self.post_recovery_data.get('soh_estimate')
        if pre_soh is None or post_soh is None:
            return None
        return post_soh - pre_soh

    def compute_resistance_change(self) -> float:
        """
        Compute change in internal resistance.
        Returns:
            Percentage change in resistance.
        """
        pre_res = self.pre_recovery_data.get('resistance')
        post_res = self.post_recovery_data.get('resistance')
        if pre_res is None or post_res is None or pre_res == 0:
            return None
        return ((post_res - pre_res) / pre_res) * 100.0

    def verify_recovery(self) -> Dict[str, any]:
        """
        Perform verification and return a report.
        """
        report = {
            'recovery_action': self.recovery_action,
            'pre_recovery_data': self.pre_recovery_data,
            'post_recovery_data': self.post_recovery_data,
            'capacity_restored_percent': self.compute_capacity_restored(),
            'soh_change': self.compute_soh_change(),
            'resistance_change_percent': self.compute_resistance_change(),
            'success': False
        }

        # Define success criteria: at least 5% capacity restored
        cap_restored = report['capacity_restored_percent']
        if cap_restored is not None and cap_restored >= 5.0:
            report['success'] = True

        return report

    def print_report(self):
        """Print a human-readable report."""
        report = self.verify_recovery()
        print("=" * 50)
        print("Recovery Verification Report")
        print("=" * 50)
        print(f"Recovery Action: {report['recovery_action']}")
        print(f"Pre-Recovery Capacity: {report['pre_recovery_data'].get('capacity', 'N/A')} Ah")
        print(f"Post-Recovery Capacity: {report['post_recovery_data'].get('capacity', 'N/A')} Ah")
        print(f"Capacity Restored: {report['capacity_restored_percent']:.2f}%")
        if report['soh_change'] is not None:
            print(f"SOH Change: {report['soh_change']:.2f}% points")
        if report['resistance_change_percent'] is not None:
            print(f"Resistance Change: {report['resistance_change_percent']:.2f}%")
        print(f"Success (>=5% capacity restored): {report['success']}")
        print("=" * 50)


def simulate_recovery():
    """
    Simulate a recovery process for demonstration.
    """
    verifier = RecoveryVerifier()

    # Simulate a degraded cell
    pre_capacity = 2.0  # Ah (degraded from 2.5 Ah nominal)
    verifier.set_pre_recovery_data(capacity=pre_capacity, soh_estimate=80.0)

    # Simulate applying a recovery action (e.g., pulse deplating)
    verifier.set_recovery_action("PULSE_DEPLATING")

    # Simulate post-recovery improvement
    post_capacity = 2.3  # Ah after recovery
    verifier.set_post_recovery_data(capacity=post_capacity, soh_estimate=92.0)

    # Print report
    verifier.print_report()

    # Also return report as dict for further use
    return verifier.verify_recovery()


if __name__ == "__main__":
    simulate_recovery()