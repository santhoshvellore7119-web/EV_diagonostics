"""
Rebalancing module that wraps the decision_engine state machine with strict safety interlocks.
Provides RebalancingProcessor to evaluate multi-modal telemetry, enforce safety rules,
compute ZVS power-stage efficiency, and generate hardware-gated rebalancing commands.
"""

import sys
import os
from typing import Dict, Any, Optional

# Add the active_rebalancing directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
active_reb_path = os.path.join(project_root, 'active_rebalancing')
if active_reb_path not in sys.path:
    sys.path.insert(0, active_reb_path)

from decision_engine.state_machine import DecisionEngine, SystemState, RecoveryAction
try:
    from backend.efficiency_benchmark import calculate_rebalancing_efficiency
except ImportError:
    from efficiency_benchmark import calculate_rebalancing_efficiency


class RebalancingProcessor:
    """
    Wrapper around the DecisionEngine state machine for processing
    enhanced DiagnosticFrames and enforcing multi-layer safety interlocks.
    """

    def __init__(self):
        self.decision_engine = DecisionEngine()
        self.prerecovery_soh = None
        self.manual_override_until: float = 0.0

    def trigger_rebalance(self, action: Optional[str] = None) -> Dict[str, Any]:
        """Manually trigger an active rebalancing cycle."""
        import time
        self.manual_override_until = time.time() + 8.0
        return self.decision_engine.trigger_manual_rebalance(action)

    def reset(self):
        """Reset decision engine state machine."""
        self.prerecovery_soh = None
        self.manual_override_until = 0.0
        self.decision_engine.reset()

    def process_frame(self, enhanced_frame: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an enhanced DiagnosticFrame (with ML & physics telemetry)
        and enforce safety interlocks before returning rebalancing commands.
        """
        import time
        degradation_mode_idx = enhanced_frame.get('degradation_mode_idx', 0)
        degradation_prob = float(enhanced_frame.get('degradation_prob', enhanced_frame.get('degradation_probability', 0.0)))
        soh = float(enhanced_frame.get('soh', enhanced_frame.get('stateOfHealth_value', 100.0)))
        cell_id = enhanced_frame.get('cell_id', enhanced_frame.get('cellId', 'CELL_001'))

        soh_std = float(enhanced_frame.get('stateOfHealth_uncertainty_std', 1.0))
        voltage = float(enhanced_frame.get('electrical_voltage', 3.70))
        temperature = float(enhanced_frame.get('thermal_temperature', 25.0))
        temp_gradient = float(enhanced_frame.get('thermal_tempGradient', 0.10))
        mode_str = str(enhanced_frame.get('degradation_mode', 'healthy')).lower()

        # Update decision engine with ML results unless manual override is active on a healthy cell
        if time.time() < self.manual_override_until and degradation_mode_idx == 0:
            self.decision_engine.update_ml_results(1, 0.90, min(85.0, soh))
        else:
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
        action_reason = self._generate_action_reason(degradation_mode_idx, degradation_prob, soh, recovery_action)
        target_current = self._get_target_current(commands, recovery_action)
        target_voltage = self._get_target_voltage(commands, recovery_action)
        pwm_duty = self._get_pwm_duty_cycle(commands, target_voltage)

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

        elif mode_str != 'healthy' and degradation_prob < 0.65 and time.time() >= self.manual_override_until:
            state = 'IDLE'
            recovery_action = 'none'
            safety_interlock_engaged = False
            safety_status = 'WARNING_ELEVATED_RISK'
            target_current = 0.0
            pwm_duty = 0.0
            action_reason = f"Classification confidence P={degradation_prob*100:.1f}% below recovery threshold (65%). Monitoring in passive mode."

        actual_current = float(target_current * 0.98 if target_current > 0 else 0.0)
        rebalancing_active = bool(actual_current > 0.0 and not safety_interlock_engaged)

        # Compute physical ZVS power stage efficiency
        if rebalancing_active:
            eff_info = calculate_rebalancing_efficiency(
                i_transfer_a=actual_current,
                v_source_v=max(3.0, target_voltage),
                v_target_v=max(2.5, voltage),
            )
            zvs_eff_pct = round(float(eff_info['efficiency_pct']), 2)
        else:
            zvs_eff_pct = 0.0

        result = enhanced_frame.copy()
        result.update({
            'rebalancing_state': state,
            'rebalancing_active': rebalancing_active,
            'rebalancing_selectedAction': recovery_action,
            'rebalancing_actionReason': action_reason,
            'rebalancing_safetyInterlock_engaged': safety_interlock_engaged,
            'rebalancing_safetyStatus': safety_status,
            'rebalancing_powerStage_targetCurrent': float(target_current),
            'rebalancing_powerStage_actualCurrent': actual_current,
            'rebalancing_powerStage_targetVoltage': float(target_voltage),
            'rebalancing_powerStage_actualVoltage': float(voltage),
            'rebalancing_powerStage_pwmDutyCycle': float(pwm_duty),
            'rebalancing_executionTime': float(status['time_in_state']),
            'zvs_efficiency_pct': zvs_eff_pct
        })

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

    def _get_target_current(self, commands: Dict[str, Any], recovery_action: str = '') -> float:
        action = (commands.get('action') or recovery_action or '').lower()
        if not action or action == 'none':
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

    def _get_target_voltage(self, commands: Dict[str, Any], recovery_action: str = '') -> float:
        params = commands.get('parameters', {})
        action = (commands.get('action') or recovery_action or '').lower()
        if not action or action == 'none':
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

    def _get_pwm_duty_cycle(self, commands: Dict[str, Any], target_voltage: float = 0.0) -> float:
        if target_voltage <= 0:
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
            soh_after = float(enhanced_frame.get('stateOfHealth_value', enhanced_frame.get('soh', 0.0)))
            cell_id = str(enhanced_frame.get('cellId', enhanced_frame.get('cell_id', "CELL_001")))
            self.decision_engine.update_recovery_effectiveness(cell_id, soh_after)
            self.prerecovery_soh = None

    def rank_pack_cells_weakest_first(self, pack_frames: list) -> list:
        """
        Rank a multi-cell pack from weakest to strongest using composite health-SOC-voltage
        scoring and assign active ZVS shuttling roles ('ISOLATE', 'RECIPIENT', 'NEUTRAL', 'DONOR').
        """
        if not pack_frames:
            return []

        socs = [float(f.get('soc', f.get('electrical_soc', 0.5))) for f in pack_frames]
        mean_soc = sum(socs) / len(socs)
        ranked = []

        for idx, f in enumerate(pack_frames):
            cell_id = str(f.get('cell_id', f.get('cellId', f"CELL_{idx+1:03d}")))
            soh = float(f.get('soh', f.get('stateOfHealth_value', 90.0)))
            soc = float(f.get('soc', f.get('electrical_soc', 0.5)))
            v = float(f.get('electrical_voltage', 3.0 + 1.2 * soc))
            mode_idx = int(f.get('degradation_mode_idx', 0))
            prob = float(f.get('degradation_prob', f.get('degradation_probability', 0.0)))

            v_norm = max(0.0, min(1.0, (v - 3.0) / 1.2))
            penalty = prob * (1.0 if mode_idx == 5 else (0.35 if mode_idx > 0 else 0.0))
            score = 0.45 * (soh / 100.0) + 0.35 * soc + 0.20 * v_norm - 0.25 * penalty

            if mode_idx == 5 and prob >= 0.65:
                role = 'ISOLATE'
            elif soc < mean_soc - 0.015 or soh < 82.0:
                role = 'RECIPIENT'
            elif soc > mean_soc + 0.015 and soh >= 85.0 and mode_idx == 0:
                role = 'DONOR'
            else:
                role = 'NEUTRAL'

            ranked.append({
                'cell_id': cell_id,
                'soh': soh,
                'soc': soc,
                'voltage': v,
                'degradation_mode_idx': mode_idx,
                'composite_score': round(score, 4),
                'shuttling_role': role,
            })

        ranked.sort(key=lambda item: item['composite_score'])
        for r_idx, item in enumerate(ranked, start=1):
            item['priority_rank'] = r_idx
        return ranked