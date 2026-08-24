"""
Decision engine for triaging degradation modes and determining recovery actions.
Updated to include RESENSING state and confidence thresholding.
"""

from enum import Enum, auto
import numpy as np
from config import params as P


class DegradationMode(Enum):
    HEALTHY = 0
    LI_PLATING = 1
    ACTIVE_MATERIAL_LOSS = 2
    ELECTROLYTE_DECOMPOSITION = 3
    GAS_GENERATION = 4
    INTERNAL_SHORT = 5


class RecoveryAction(Enum):
    NONE = auto()
    PULSE_DEPLATING = auto()  # For lithium plating
    EQUILIBRATION = auto()    # For active material loss or electrolyte decomposition
    GAS_RECOMBINATION = auto()  # For gas generation
    SHORT_ISOLATION = auto()  # For internal short
    BALANCING = auto()        # General balancing (fallback)
    RESENSING = auto()        # Request another sensing cycle


class SystemState(Enum):
    IDLE = auto()
    SENSING = auto()
    ANALYZING = auto()
    RESENSING = auto()
    REBALANCING = auto()
    VERIFYING = auto()
    COMPLETE = auto()


class DecisionEngine:
    """
    Implements the decision logic for determining recovery actions based on
    degradation mode classification, state-of-health estimates, and prediction confidence.
    Now includes a RESENSING state when confidence is low.
    """

    def __init__(self):
        # Thresholds from config
        self.soh_threshold_recoverable = P.SOH_THRESHOLD_RECOVERABLE
        self.soh_threshold_severe = P.SOH_THRESHOLD_SEVERE
        self.degradation_prob_threshold = P.DEGRADATION_PROB_THRESHOLD
        # New: confidence threshold for triggering recovery action
        self.confidence_threshold = getattr(P, 'CONFIDENCE_THRESHOLD', 0.7)
        # New: maximum number of re-sense cycles to avoid infinite loops
        self.max_resense_cycles = getattr(P, 'MAX_RESENSE_CYCLES', 3)

        # Mapping from degradation mode to recovery action (for recoverable cases)
        self.mode_to_action = {
            DegradationMode.LI_PLATING: RecoveryAction.PULSE_DEPLATING,
            DegradationMode.ACTIVE_MATERIAL_LOSS: RecoveryAction.EQUILIBRATION,
            DegradationMode.ELECTROLYTE_DECOMPOSITION: RecoveryAction.EQUILIBRATION,
            DegradationMode.GAS_GENERATION: RecoveryAction.GAS_RECOMBINATION,
            DegradationMode.INTERNAL_SHORT: RecoveryAction.SHORT_ISOLATION
        }

        # Parameters for each recovery action (simplified)
        self.action_parameters = {
            RecoveryAction.PULSE_DEPLATING: {
                'type': 'pulse',
                'voltage': 4.2,  # V
                'pulse_width_ms': 10,
                'pulse_interval_s': 1,
                'num_pulses': 100,
                'direction': 'discharge'  # discharge pulses for deplating
            },
            RecoveryAction.EQUILIBRATION: {
                'type': 'constant_current',
                'current': 0.5,  # A
                'duration_s': 300,
                'direction': 'charge'  # or discharge depending on imbalance (we'll assume charge for simplicity)
            },
            RecoveryAction.GAS_RECOMBINATION: {
                'type': 'constant_voltage',
                'voltage': 3.9,
                'duration_s': 600,
                'direction': 'charge'
            },
            RecoveryAction.SHORT_ISOLATION: {
                'type': 'open_circuit',
                'duration_s': 10
            },
            RecoveryAction.BALANCING: {
                'type': 'pid_control',
                'target_voltage': 3.7,
                'tolerance': 0.01,
                'direction': 'both'
            },
            RecoveryAction.RESENSING: {
                'type': 'resense',
                # No additional parameters needed; just trigger another sensing cycle
            }
        }

        # Internal state for tracking re-sense cycles
        self.resense_cycle_count = 0

    def decide(self, degradation_mode_idx, degradation_prob, soh):
        """
        Decide on a recovery action based on the model outputs.
        Args:
            degradation_mode_idx: integer index of the predicted degradation mode.
            degradation_prob: probability of the predicted mode (0-1).
            soh: estimated state of health (percentage, 0-100).
        Returns:
            tuple (RecoveryAction, dict of parameters) for the selected action.
        """
        # Convert index to enum
        try:
            mode = DegradationMode(degradation_mode_idx)
        except ValueError:
            # If the index is out of range, treat as healthy
            mode = DegradationMode.HEALTHY

        # If the probability is too low, we don't trust the classification
        if degradation_prob < self.degradation_prob_threshold:
            mode = DegradationMode.HEALTHY

        # If healthy, no recovery action
        if mode == DegradationMode.HEALTHY:
            return RecoveryAction.NONE, {}

        # Check if the degradation is considered recoverable based on SOH
        if soh < self.soh_threshold_recoverable:
            # SOH too low, degradation likely irreversible
            return RecoveryAction.NONE, {}

        # Check confidence: if below threshold, trigger RESENSING (if we haven't exceeded max cycles)
        if degradation_prob < self.confidence_threshold:
            if self.resense_cycle_count < self.max_resense_cycles:
                self.resense_cycle_count += 1
                return RecoveryAction.RESENSING, {}
            else:
                # Exceeded max re-sense cycles, fall back to NONE to avoid infinite loop
                self.resense_cycle_count = 0  # Reset counter
                return RecoveryAction.NONE, {}

        # Confidence is sufficient, proceed to determine recovery action
        # Reset re-sense cycle count since we are confident
        self.resense_cycle_count = 0

        # Determine the recovery action based on the mode
        action = self.mode_to_action.get(mode, RecoveryAction.NONE)
        if action == RecoveryAction.NONE:
            # Fallback to general balancing if no specific action is mapped
            action = RecoveryAction.BALANCING

        # Get the parameters for the action
        parameters = self.action_parameters.get(action, {})

        return action, parameters

    def get_action_description(self, action):
        """Return a human-readable description of the recovery action."""
        descriptions = {
            RecoveryAction.NONE: "No recovery action",
            RecoveryAction.PULSE_DEPLATING: "Pulse deplating (for lithium plating)",
            RecoveryAction.EQUILIBRATION: "Equilibration (for active material loss or electrolyte decomposition)",
            RecoveryAction.GAS_RECOMBINATION: "Gas recombination (for gas generation)",
            RecoveryAction.SHORT_ISOLATION: "Short isolation (for internal short)",
            RecoveryAction.BALANCING: "General balancing (PID control)",
            RecoveryAction.RESENSING: "Re-sense: request another sensing cycle"
        }
        return descriptions.get(action, "Unknown action")

    def reset_resense_counter(self):
        """Reset the re-sense cycle counter."""
        self.resense_cycle_count = 0