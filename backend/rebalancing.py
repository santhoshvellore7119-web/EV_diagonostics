"""
Rebalancing module that wraps the decision_engine state machine.
Provides a RebalancingProcessor class to process enhanced DiagnosticFrames
and execute the decision engine to get rebalancing commands.
"""

import sys
import os
from typing import Dict, Any

# Add the active_rebalancing directory to the path so we can import decision_engine
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'active_rebalancing'))

from decision_engine.state_machine import DecisionEngine, SystemState, RecoveryAction


class RebalancingProcessor:
    """
    Wrapper around the DecisionEngine state machine for processing
    enhanced DiagnosticFrames (with ML results) and generating rebalancing commands.
    """

    def __init__(self):
        """Initialize the RebalancingProcessor with a DecisionEngine instance."""
        self.decision_engine = DecisionEngine()
        self.prerecovery_soh = None  # To store SOH before recovery for effectiveness calculation

    def process_frame(self, enhanced_frame: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an enhanced DiagnosticFrame (with ML results) and update the decision engine.

        Args:
            enhanced_frame: Dictionary containing at least:
                - degradation_mode_idx: int (index of predicted degradation mode)
                - degradation_prob: float (probability of the predicted mode)
                - soh: float (estimated State of Health, 0-100)
                - cell_id: str (optional, identifier for the cell being processed)

        Returns:
            Dictionary with rebalancing state, selected action, action reason,
            power stage telemetry, and execution time (to be merged into the DiagnosticFrame)
        """
        # Extract ML results from the enhanced frame
        degradation_mode_idx = enhanced_frame.get('degradation_mode_idx', 0)
        degradation_prob = enhanced_frame.get('degradation_prob', 0.0)
        soh = enhanced_frame.get('soh', 100.0)
        cell_id = enhanced_frame.get('cell_id', None)

        # Update the decision engine with ML results
        self.decision_engine.update_ml_results(degradation_mode_idx, degradation_prob, soh)

        # Set cell ID if provided
        if cell_id:
            self.decision_engine.set_cell_under_test(cell_id)

        # Execute the decision engine state machine to get commands
        commands = self.decision_engine.execute()

        # Extract information from commands and decision engine status
        status = self.decision_engine.get_status()

        # Build the result dictionary to merge into DiagnosticFrame
        result = {
            # Rebalancing state (string)
            'rebalancing_state': status['state'],

            # Selected action (string, from recovery_action.name)
            'rebalancing_selectedAction': status['recovery_action'].lower() if status['recovery_action'] else 'none',

            # Action reason (string, we'll generate based on ML results)
            'rebalancing_actionReason': self._generate_action_reason(
                degradation_mode_idx, degradation_prob, soh, status['recovery_action']
            ),

            # Power stage telemetry (we'll compute based on action and parameters)
            'rebalancing_powerStage_targetCurrent': self._get_target_current(commands),
            'rebalancing_powerStage_actualCurrent': 0.0,  # Would be measured in real system
            'rebalancing_powerStage_targetVoltage': self._get_target_voltage(commands),
            'rebalancing_powerStage_actualVoltage': 0.0,  # Would be measured in real system
            'rebalancing_powerStage_pwmDutyCycle': self._get_pwm_duty_cycle(commands),

            # Execution time (time in current state)
            'rebalancing_executionTime': status['time_in_state']
        }

        # Store pre-recovery SOH when starting a recovery action
        self._store_prerecovery_soh_if_needed(status, soh)

        # Update recovery effectiveness if we're in VERIFYING state and have post-recovery data
        self._update_recovery_effectiveness_if_needed(enhanced_frame, status)

        return result

    def _generate_action_reason(self, degradation_mode_idx: int, degradation_prob: float,
                               soh: float, recovery_action: str) -> str:
        """
        Generate a human-readable reason for the selected action.

        Args:
            degradation_mode_idx: Index of predicted degradation mode
            degradation_prob: Probability of the predicted mode
            soh: Estimated State of Health (0-100)
            recovery_action: Selected recovery action name

        Returns:
            String describing the reason for the action
        """
        if recovery_action == 'none':
            if degradation_prob < 0.6:
                return "Degradation probability too low to justify recovery action"
            elif soh < 60.0:
                return "Severe degradation (SOH < 60%), recovery unlikely to be effective"
            else:
                return "No significant degradation detected"

        # Map degradation mode index to name (matching DecisionEngine.DegradationMode)
        mode_names = [
            'HEALTHY', 'LI_PLATING', 'ACTIVE_MATERIAL_LOSS',
            'ELECTROLYTE_DECOMPOSITION', 'GAS_GENERATION', 'INTERNAL_SHORT'
        ]

        if degradation_mode_idx < len(mode_names):
            mode_name = mode_names[degradation_mode_idx]
        else:
            mode_name = 'UNKNOWN'

        if recovery_action == 'pulse_deplating':
            return f"Li-plating detected ({mode_name}) with {degradation_prob*100:.1f}% probability, SOH={soh:.1f}%"
        elif recovery_action == 'equilibration':
            return f"Active material loss/electrolyte decomposition detected ({mode_name}) with {degradation_prob*100:.1f}% probability, SOH={soh:.1f}%"
        elif recovery_action == 'gas_recombination':
            return f"Gas generation detected ({mode_name}) with {degradation_prob*100:.1f}% probability, SOH={soh:.1f}%"
        elif recovery_action == 'short_isolation':
            return f"Internal short detected ({mode_name}) with {degradation_prob*100:.1f}% probability, SOH={soh:.1f}%"
        elif recovery_action == 'balancing':
            return f"Cell imbalance detected with {degradation_prob*100:.1f}% probability, SOH={soh:.1f}%"
        else:
            return f"Recovery action {recovery_action} selected for {mode_name} degradation"

    def _get_target_current(self, commands: Dict[str, Any]) -> float:
        """
        Extract target current from commands or compute based on action parameters.

        Args:
            commands: Dictionary returned by decision_engine.execute()

        Returns:
            Target current in Amperes
        """
        # If we have specific parameters, use them to compute target current
        params = commands.get('parameters', {})
        action = commands.get('action')

        # Simple mapping based on action type
        if action and 'pulse_deplating' in action:
            voltage_pulse = params.get('voltage_pulse', 4.2)
            # Simplified: assume 1A for pulsing (would depend on resistance in real system)
            return 1.0
        elif action and 'equilibration' in action:
            voltage = params.get('voltage', 3.7)
            # Simplified: assume 0.5A for equilibration
            return 0.5
        elif action and 'gas_recombination' in action:
            voltage = params.get('voltage', 3.9)
            # Simplified: assume 0.3A for gas recombination
            return 0.3
        elif action and 'short_isolation' in action:
            # For short isolation, we might apply reverse polarity or open circuit
            return 0.0
        elif action and 'balancing' in action:
            # For balancing, current depends on voltage difference
            return 0.2
        else:
            return 0.0

    def _get_target_voltage(self, commands: Dict[str, Any]) -> float:
        """
        Extract target voltage from commands or compute based on action parameters.

        Args:
            commands: Dictionary returned by decision_engine.execute()

        Returns:
            Target voltage in Volts
        """
        params = commands.get('parameters', {})
        action = commands.get('action')

        # Extract voltage from parameters based on action type
        if action and 'pulse_deplating' in action:
            return params.get('voltage_pulse', 4.2)
        elif action and 'equilibration' in action:
            return params.get('voltage', 3.7)
        elif action and 'gas_recombination' in action:
            return params.get('voltage', 3.9)
        elif action and 'short_isolation' in action:
            return params.get('voltage', 0.0)
        elif action and 'balancing' in action:
            return params.get('target_voltage', 3.7)
        else:
            return 0.0

    def _get_pwm_duty_cycle(self, commands: Dict[str, Any]) -> float:
        """
        Compute PWM duty cycle based on target voltage and system constraints.

        Args:
            commands: Dictionary returned by decision_engine.execute()

        Returns:
            PWM duty cycle as percentage (0-100)
        """
        target_voltage = self._get_target_voltage(commands)

        # Simplified conversion: assume system voltage range 0-5V maps to 0-100% PWM
        # In a real system, this would depend on the specific hardware design
        max_voltage = 5.0  # Maximum voltage the power stage can produce
        duty_cycle = (target_voltage / max_voltage) * 100.0

        # Clamp to valid range
        return max(0.0, min(100.0, duty_cycle))

    def _store_prerecovery_soh_if_needed(self, status: Dict[str, Any], current_soh: float):
        """
        Store the SOH value before starting recovery for effectiveness calculation.

        Args:
            status: Current status from decision_engine.get_status()
            current_soh: Current SOH value
        """
        # Store pre-recovery SOH when transitioning to REBALANCING state
        if status['state'] == 'REBALANCING' and self.prerecovery_soh is None:
            self.decision_engine.store_prerecovery_soh(current_soh)
            self.prerecovery_soh = current_soh

        # Reset prerecovery_soh when we finish a recovery cycle
        if status['state'] == 'IDLE' or status['state'] == 'COMPLETE':
            self.prerecovery_soh = None

    def _update_recovery_effectiveness_if_needed(self, enhanced_frame: Dict[str, Any],
                                                status: Dict[str, Any]):
        """
        Update recovery effectiveness if we're in VERIFYING state and have post-recovery data.

        Args:
            enhanced_frame: The current enhanced frame (should contain post-recovery SOH)
            status: Current status from decision_engine.get_status()
        """
        # Update recovery effectiveness when in VERIFYING state
        if status['state'] == 'VERIFYING':
            # Get post-recovery SOH from the enhanced frame
            soh_after = enhanced_frame.get('soh', 0.0)
            cell_id = enhanced_frame.get('cell_id', "unknown")

            # Call the decision engine's update_recovery_effectiveness method
            self.decision_engine.update_recovery_effectiveness(cell_id, soh_after)

            # Reset prerecovery_soh after updating effectiveness
            self.prerecovery_soh = None