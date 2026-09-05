"""
Rebalancing module that wraps the decision_engine state machine with strict safety interlocks.
Provides RebalancingProcessor to evaluate multi-modal telemetry, enforce safety rules,
and generate hardware-gated rebalancing commands.
"""

import sys
import os
from typing import Dict, Any

# Add the active_rebalancing directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
active_reb_path = os.path.join(project_root, 'active_rebalancing')
if active_reb_path not in sys.path:
    sys.path.insert(0, active_reb_path)

from decision_engine.state_machine import DecisionEngine, SystemState, RecoveryAction


class RebalancingProcessor:
    """
    Wrapper around the DecisionEngine state machine for processing
    enhanced DiagnosticFrames and enforcing multi-layer safety interlocks.
    """

    def __init__(self):
        self.decision_engine = DecisionEngine()
        self.prerecovery_soh = None

    def process_frame(self, enhanced_frame: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an enhanced DiagnosticFrame (with ML & physics telemetry)
        and enforce safety interlocks before returning rebalancing commands.
        """
        degradation_mode_idx = enhanced_frame.get('degradation_mode_idx', 0)
        degradation_prob = float(enhanced_frame.get('degradation_prob', enhanced_frame.get('degradation_probability', 0.0)))
        soh = float(enhanced_frame.get('soh', enhanced_frame.get('stateOfHealth_value', 100.0)))
        cell_id = enhanced_frame.get('cell_id', enhanced_frame.get('cellId', 'CELL_001'))

        soh_std = float(enhanced_frame.get('stateOfHealth_uncertainty_std', 1.0))
        voltage = float(enhanced_frame.get('electrical_voltage', 3.70))
        temperature = float(enhanced_frame.get('thermal_temperature', 25.0))
        temp_gradient = float(enhanced_frame.get('thermal_tempGradient', 0.10))
        mode_str = str(enhanced_frame.get('degradation_mode', 'healthy')).lower()

        # Update decision engine with ML results
        self.decision_engine.update_ml_results(degradation_mode_idx, degradation_prob, soh)
        if cell_id:
            self.decision_engine.set_cell_under_test(cell_id)

        # Execute decision engine step
        commands = self.decision_engine.execute()
        status = self.decision_engine.get_status()

        state = status['state']
        recovery_action = status['recovery_action'].lower() if status['recovery_action'] else 'none'
        safety_interlock_engaged = False
        safety_status = "SAFE_TO_OPERATE"
        action_reason = self._generate_action_reason(degradation_mode_idx, degradation_prob, soh, status['recovery_action'])
        target_current = self._get_target_current(commands)
        target_voltage = self._get_target_voltage(commands)
        pwm_duty = self._get_pwm_duty_cycle(commands)

        # =========================================================================
        # MULTI-LAYER SAFETY INTERLOCKS & HARDWARE GATING
        # =========================================================================
        if mode_str == 'internal_short' or degradation_mode_idx == 5:
            state = 'SAFETY_LOCKOUT_ISOLATED'
            recovery_action = 'short_isolation'
            safety_interlock_engaged = True
            safety_status = 'CRITICAL_LOCKOUT_ISOLATED'
            target_current = 0.0
            target_voltage = 0.0
            pwm_duty = 0.0
            action_reason = f"EMERGENCY SAFETY LOCKOUT: Internal short circuit classified (P={degradation_prob*100:.1f}%). Contactor OPEN, current 0.0A."

        elif temp_gradient > 3.0 or temperature > 55.0:
            state = 'SAFETY_LOCKOUT_ISOLATED'
            safety_interlock_engaged = True
            safety_status = 'CRITICAL_LOCKOUT_ISOLATED'
            target_current = 0.0
            target_voltage = 0.0
            pwm_duty = 0.0
            action_reason = f"THERMAL INTERLOCK: Temp={temperature:.1f}C / Grad={temp_gradient:.2f}C/cm exceeds safety limit. Power stage isolated."

        elif voltage < 2.80 or voltage > 4.25:
            state = 'SAFETY_LOCKOUT_ISOLATED'
            safety_interlock_engaged = True
            safety_status = 'CRITICAL_LOCKOUT_ISOLATED'
            target_current = 0.0
            target_voltage = 0.0
            pwm_duty = 0.0
            action_reason = f"VOLTAGE BOUNDS FAULT: Terminal voltage {voltage:.3f}V out of safe window [2.80V, 4.25V]. Rebalancer disabled."

        elif soh_std > 3.0:
            state = 'IDLE'
            recovery_action = 'none'
            safety_interlock_engaged = True
            safety_status = 'WARNING_ELEVATED_RISK'
            target_current = 0.0
            pwm_duty = 0.0
            action_reason = f"UNCERTAINTY INTERLOCK: SOH epistemic uncertainty (sigma={soh_std:.2f}%) exceeds 3.0% threshold. Rebalancing gated."

        elif mode_str != 'healthy' and degradation_prob < 0.65:
            state = 'IDLE'
            recovery_action = 'none'
            safety_interlock_engaged = False
            safety_status = 'WARNING_ELEVATED_RISK'
            target_current = 0.0
            pwm_duty = 0.0
            action_reason = f"Classification confidence P={degradation_prob*100:.1f}% below recovery threshold (65%). Monitoring in passive mode."

        result = {
            'rebalancing_state': state,
            'rebalancing_selectedAction': recovery_action,
            'rebalancing_actionReason': action_reason,
            'rebalancing_safetyInterlock_engaged': safety_interlock_engaged,
            'rebalancing_safetyStatus': safety_status,
            'rebalancing_powerStage_targetCurrent': float(target_current),
            'rebalancing_powerStage_actualCurrent': float(target_current * 0.98 if target_current > 0 else 0.0),
            'rebalancing_powerStage_targetVoltage': float(target_voltage),
            'rebalancing_powerStage_actualVoltage': float(voltage),
            'rebalancing_powerStage_pwmDutyCycle': float(pwm_duty),
            'rebalancing_executionTime': float(status['time_in_state'])
        }

        self._store_prerecovery_soh_if_needed(status, soh)
        self._update_recovery_effectiveness_if_needed(enhanced_frame, status)

        return result

    def _generate_action_reason(self, degradation_mode_idx: int, degradation_prob: float,
                               soh: float, recovery_action: str) -> str:
        if not recovery_action or str(recovery_action).lower() == 'none':
            if degradation_mode_idx == 0:
                return "System operating nominally. Cell balance verified."
            elif degradation_prob < 0.60:
                return "Degradation probability too low to justify active recovery."
            elif soh < 60.0:
                return "Severe degradation (SOH < 60%), active recovery unlikely to be effective."
            else:
                return "Cell under passive monitoring. No rebalancing required."

        mode_names = [
            'HEALTHY', 'LI_PLATING', 'ACTIVE_MATERIAL_LOSS',
            'ELECTROLYTE_DECOMPOSITION', 'GAS_GENERATION', 'INTERNAL_SHORT'
        ]
        mode_name = mode_names[degradation_mode_idx] if degradation_mode_idx < len(mode_names) else 'UNKNOWN'

        if recovery_action == 'pulse_deplating':
            return f"Lithium plating detected ({mode_name}, P={degradation_prob*100:.1f}%). Applying localized deplating pulse sequence."
        elif recovery_action == 'equilibration':
            return f"Active material loss / electrolyte decomp detected ({mode_name}, P={degradation_prob*100:.1f}%). Applying CCCV equilibration."
        elif recovery_action == 'gas_recombination':
            return f"Gas generation detected ({mode_name}, P={degradation_prob*100:.1f}%). Applying mild potential holding."
        elif recovery_action == 'short_isolation':
            return f"Internal short detected ({mode_name}, P={degradation_prob*100:.1f}%). Contactors opened, isolating cell."
        elif recovery_action == 'balancing':
            return f"Active cell charge balancing engaged (SOH={soh:.1f}%)."
        else:
            return f"Action {recovery_action} engaged for {mode_name} degradation."

    def _get_target_current(self, commands: Dict[str, Any]) -> float:
        params = commands.get('parameters', {})
        action = commands.get('action', '')
        if not action:
            return 0.0
        if 'pulse_deplating' in action:
            return 1.0
        elif 'equilibration' in action:
            return 0.5
        elif 'gas_recombination' in action:
            return 0.3
        elif 'short_isolation' in action:
            return 0.0
        elif 'balancing' in action:
            return 0.25
        return 0.0

    def _get_target_voltage(self, commands: Dict[str, Any]) -> float:
        params = commands.get('parameters', {})
        action = commands.get('action', '')
        if not action:
            return 0.0
        if 'pulse_deplating' in action:
            return float(params.get('voltage_pulse', 4.20))
        elif 'equilibration' in action:
            return float(params.get('voltage', 3.70))
        elif 'gas_recombination' in action:
            return float(params.get('voltage', 3.90))
        elif 'short_isolation' in action:
            return 0.0
        elif 'balancing' in action:
            return float(params.get('target_voltage', 3.70))
        return 0.0

    def _get_pwm_duty_cycle(self, commands: Dict[str, Any]) -> float:
        target_voltage = self._get_target_voltage(commands)
        if target_voltage <= 0:
            return 0.0
        max_voltage = 5.0
        duty_cycle = (target_voltage / max_voltage) * 100.0
        return float(max(0.0, min(100.0, duty_cycle)))

    def _store_prerecovery_soh_if_needed(self, status: Dict[str, Any], current_soh: float):
        if status['state'] == 'REBALANCING' and self.prerecovery_soh is None:
            self.decision_engine.store_prerecovery_soh(current_soh)
            self.prerecovery_soh = current_soh
        if status['state'] in ['IDLE', 'COMPLETE']:
            self.prerecovery_soh = None

    def _update_recovery_effectiveness_if_needed(self, enhanced_frame: Dict[str, Any], status: Dict[str, Any]):
        if status['state'] == 'VERIFYING':
            soh_after = enhanced_frame.get('soh', 0.0)
            cell_id = enhanced_frame.get('cell_id', "CELL_001")
            self.decision_engine.update_recovery_effectiveness(cell_id, soh_after)
            self.prerecovery_soh = None