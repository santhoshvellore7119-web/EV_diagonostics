"""
State machine for active rebalancing decision engine with personalized recovery actions.
Enhanced version that accepts DiagnosticFrame input and outputs standardized rebalancing commands.
"""

from enum import Enum, auto
from typing import Dict, Any, Optional, List
import time
import numpy as np


class SystemState(Enum):
    """Possible states of the battery diagnostic and rebalancing system."""
    IDLE = auto()
    SENSING = auto()
    ANALYZING = auto()
    REBALANCING = auto()
    VERIFYING = auto()
    ERROR = auto()
    COMPLETE = auto()


class DegradationMode(Enum):
    """Degradation modes as classified by the ML model."""
    HEALTHY = 0
    LI_PLATING = 1
    ACTIVE_MATERIAL_LOSS = 2
    ELECTROLYTE_DECOMPOSITION = 3
    GAS_GENERATION = 4
    INTERNAL_SHORT = 5


class RecoveryAction(Enum):
    """Possible recovery actions."""
    NONE = auto()
    PULSE_DEPLATING = auto()  # For lithium plating
    EQUILIBRATION = auto()    # For active material loss / electrolyte decomposition
    GAS_RECOMBINATION = auto()  # For gas generation (if applicable)
    SHORT_ISOLATION = auto()  # For internal short (attempt to isolate)
    BALANCING = auto()        # General cell balancing


class RecoveryHistory:
    """Tracks recovery action effectiveness for personalization."""

    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []

    def add_record(self, cell_id: str, action: RecoveryAction,
                   params: Dict[str, Any], soh_before: float,
                   soh_after: float, success: bool):
        """Add a recovery action record to history."""
        record = {
            'cell_id': cell_id,
            'action': action,
            'params': params.copy(),
            'soh_before': soh_before,
            'soh_after': soh_after,
            'soh_improvement': soh_after - soh_before,
            'success': success,
            'timestamp': time.time()
        }
        self.history.append(record)
        # Keep only recent history
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def get_effectiveness(self, action: RecoveryAction,
                         cell_characteristics: Optional[Dict] = None) -> float:
        """Get estimated effectiveness for an action based on history."""
        relevant_records = [
            r for r in self.history
            if r['action'] == action
        ]

        if not relevant_records:
            return 0.5  # Default effectiveness when no history

        # Calculate average improvement
        improvements = [r['soh_improvement'] for r in relevant_records if r['success']]
        if not improvements:
            return 0.2  # Low effectiveness if no successful records

        return np.mean(improvements)

    def get_optimal_params(self, action: RecoveryAction,
                          base_params: Dict[str, Any],
                          cell_characteristics: Optional[Dict] = None) -> Dict[str, Any]:
        """Get personalized parameters based on historical effectiveness."""
        relevant_records = [
            r for r in self.history
            if r['action'] == action and r['success']
        ]

        if not relevant_records:
            return base_params.copy()

        # Average successful parameters
        param_sums = {}
        param_counts = {}

        for record in relevant_records:
            for key, value in record['params'].items():
                if key not in param_sums:
                    param_sums[key] = 0
                    param_counts[key] = 0
                if isinstance(value, (int, float)):
                    param_sums[key] += value
                    param_counts[key] += 1

        # Calculate averages
        optimal_params = base_params.copy()
        for key in param_sums:
            if param_counts[key] > 0:
                optimal_params[key] = param_sums[key] / param_counts[key]

        return optimal_params


class DecisionEngine:
    """
    Implements the state machine and decision logic for triggering recovery actions.
    Enhanced with personalized recovery actions based on degradation severity,
    historical response, and cell-specific characteristics.
    Now accepts DiagnosticFrame input and outputs standardized rebalancing commands.
    """

    def __init__(self):
        self.state = SystemState.IDLE
        self.last_transition_time = time.time()
        self.recovery_action = RecoveryAction.NONE
        self.cell_under_test = None
        self.ml_results = {}  # Will hold {degradation_mode: prob, soh: value}
        self.recovery_parameters = {}  # Parameters for the recovery action
        self.max_recovery_time = 300  # seconds (5 minutes max per recovery attempt)
        self.recovery_start_time = None
        self.verification_soh = None  # SOH after recovery for effectiveness calculation

        # Personalization components
        self.recovery_history = RecoveryHistory()
        self.cell_characteristics = {}  # Cell-specific info (age, chemistry, etc.)
        self.historical_soh_values = []  # Track SOH over time for progression analysis

        # Thresholds for decision making
        self.soh_threshold_recoverable = 80.0  # If SOH > 80%, consider recovery
        self.soh_threshold_severe = 60.0       # If SOH < 60%, severe degradation
        self.degradation_prob_threshold = 0.6  # Probability threshold to trust classification
        self.soh_improvement_threshold = 2.0   # Minimum SOH improvement to consider successful

        # Mapping from degradation mode to recovery action (base mapping)
        self.mode_to_action = {
            DegradationMode.HEALTHY: RecoveryAction.NONE,
            DegradationMode.LI_PLATING: RecoveryAction.PULSE_DEPLATING,
            DegradationMode.ACTIVE_MATERIAL_LOSS: RecoveryAction.EQUILIBRATION,
            DegradationMode.ELECTROLYTE_DECOMPOSITION: RecoveryAction.EQUILIBRATION,
            DegradationMode.GAS_GENERATION: RecoveryAction.GAS_RECOMBINATION,
            DegradationMode.INTERNAL_SHORT: RecoveryAction.SHORT_ISOLATION
        }

        # Base parameters for each recovery action (to be personalized)
        self.base_action_parameters = {
            RecoveryAction.PULSE_DEPLATING: {
                'voltage_pulse': 4.2,  # V
                'pulse_width_ms': 10,
                'pulse_interval_s': 1,
                'num_pulses': 100,
                'direction': 'discharge'  # or charge? Typically discharge pulses for deplating
            },
            RecoveryAction.EQUILIBRATION: {
                'voltage': 3.7,  # V
                'duration_s': 300,
                'direction': 'charge'  # or discharge depending on imbalance
            },
            RecoveryAction.GAS_RECOMBINATION: {
                'voltage': 3.9,
                'duration_s': 600,
                'direction': 'charge'
            },
            RecoveryAction.SHORT_ISOLATION: {
                'voltage': 0.0,  # Open circuit or apply reverse polarity?
                'duration_s': 10,
                'direction': 'none'
            },
            RecoveryAction.BALANCING: {
                'target_voltage': 3.7,
                'tolerance': 0.01,
                'direction': 'both'  # can charge or discharge
            }
        }

        # SOH-dependent parameter adjustment factors
        self.soh_adjustment_factors = {
            RecoveryAction.PULSE_DEPLATING: {
                'voltage_pulse': lambda soh: 4.0 + (soh - 60) * 0.02 / 20,  # 4.0-4.4V for SOH 60-80
                'num_pulses': lambda soh: int(50 + (soh - 60) * 50 / 20),   # 50-100 pulses for SOH 60-80
                'pulse_width_ms': lambda soh: 5 + (soh - 60) * 10 / 20,    # 5-15ms for SOH 60-80
            },
            RecoveryAction.EQUILIBRATION: {
                'duration_s': lambda soh: int(180 + (soh - 60) * 120 / 20), # 180-300s for SOH 60-80
                'voltage': lambda soh: 3.5 + (soh - 60) * 0.4 / 20,       # 3.5-3.9V for SOH 60-80
            },
            RecoveryAction.GAS_RECOMBINATION: {
                'duration_s': lambda soh: int(300 + (soh - 60) * 300 / 20), # 300-600s for SOH 60-80
                'voltage': lambda soh: 3.7 + (soh - 60) * 0.4 / 20,       # 3.7-4.1V for SOH 60-80
            }
        }

    def update_ml_results(self, degradation_mode_idx: int, degradation_prob: float, soh: float):
        """
        Update the engine with latest ML inference results.
        BACKWARD COMPATIBLE METHOD - maintains original interface.
        Args:
            degradation_mode_idx: Index of predicted degradation mode.
            degradation_prob: Probability of the predicted mode.
            soh: Estimated State of Health (0-100).
        """
        self._update_ml_results_internal(degradation_mode_idx, degradation_prob, soh)

    def update_ml_results_from_frame(self, diagnostic_frame: Dict[str, Any]):
        """
        Update the engine with ML results from a DiagnosticFrame object.
        NEW METHOD - accepts standardized DiagnosticFrame input.
        Args:
            diagnostic_frame: Dictionary containing at least:
                - degradation_mode_idx: int (index of predicted degradation mode)
                - degradation_prob: float (probability of the predicted mode)
                - soh: float (estimated State of Health, 0-100)
                - cell_id: str (optional, identifier for the cell being processed)
        """
        # Extract ML results from the DiagnosticFrame
        degradation_mode_idx = diagnostic_frame.get('degradation_mode_idx', 0)
        degradation_prob = diagnostic_frame.get('degradation_prob', 0.0)
        soh = diagnostic_frame.get('soh', 100.0)
        cell_id = diagnostic_frame.get('cell_id', None)

        # Update internal ML results
        self._update_ml_results_internal(degradation_mode_idx, degradation_prob, soh)

        # Set cell ID if provided
        if cell_id:
            self.set_cell_under_test(cell_id)

    def _update_ml_results_internal(self, degradation_mode_idx: int, degradation_prob: float, soh: float):
        """Internal method to update ML results."""
        self.ml_results = {
            'degradation_mode': DegradationMode(degradation_mode_idx),
            'degradation_prob': degradation_prob,
            'soh': soh
        }

        # Track SOH history for progression analysis
        self.historical_soh_values.append({
            'soh': soh,
            'timestamp': time.time(),
            'mode': DegradationMode(degradation_mode_idx).name if degradation_prob > self.degradation_prob_threshold else 'UNCERTAIN'
        })

        # Keep only recent history
        if len(self.historical_soh_values) > 100:
            self.historical_soh_values.pop(0)

    def transition_to(self, new_state: SystemState):
        """Transition to a new state."""
        old_state = self.state
        self.state = new_state
        self.last_transition_time = time.time()
        print(f"[{time.time()}] Transition: {old_state.name} -> {new_state.name}")

    def execute(self) -> Dict[str, Any]:
        """
        Execute one step of the state machine.
        Returns a dictionary with STANDARDIZED commands for easy mapping to DiagnosticFrame.
        """
        commands = {
            'state': self.state.name,
            'action': None,
            'parameters': {},
            'done': False
        }

        if self.state == SystemState.IDLE:
            # Wait for trigger (e.g., external command or scheduled time)
            # For now, we'll automatically go to sensing after a short delay
            if time.time() - self.last_transition_time > 1.0:
                self.transition_to(SystemState.SENSING)

        elif self.state == SystemState.SENSING:
            # Trigger the sensing hardware (DAQ) to collect data
            # In a real system, this would send a command to the MCU to start a measurement cycle
            commands['action'] = 'trigger_sensing'
            self.transition_to(SystemState.ANALYZING)

        elif self.state == SystemState.ANALYZING:
            # Wait for ML results (in a real system, we'd wait for a message from the host)
            # For this simulation, we'll assume ml_results have been updated externally
            if self.ml_results:
                self._analyze_results()
                self.transition_to(SystemState.REBALANCING)
            else:
                # If no results yet, stay in analyzing (or timeout)
                if time.time() - self.last_transition_time > 5.0:  # 5 second timeout
                    print("Analysis timeout, no ML results received")
                    self.transition_to(SystemState.ERROR)

        elif self.state == SystemState.REBALANCING:
            if self.recovery_action == RecoveryAction.NONE:
                print("No recovery action needed.")
                self.transition_to(SystemState.VERIFYING)
            else:
                # Start recovery action
                self.recovery_start_time = time.time()
                commands['action'] = f'start_{self.recovery_action.name.lower()}'
                commands['parameters'] = self.recovery_parameters
                print(f"Starting personalized recovery action: {self.recovery_action.name}")
                print(f"Parameters: {self.recovery_parameters}")
                # We'll stay in REBALANCING state until recovery is done (checked via timeout or completion signal)

        elif self.state == SystemState.VERIFYING:
            # Trigger post-recovery sensing to verify effectiveness
            commands['action'] = 'trigger_sensing'
            self.transition_to(SystemState.ANALYZING)  # Go to analyzing to get post-recovery ML results

        elif self.state == SystemState.ERROR:
            # Handle error (e.g., log, alert, safe shutdown)
            commands['action'] = 'error_handler'
            # After error, we might go to idle or remain in error
            self.transition_to(SystemState.IDLE)

        elif self.state == SystemState.COMPLETE:
            # Process is done
            commands['done'] = True
            commands['action'] = 'complete'

        # Check for recovery timeout
        if self.state == SystemState.REBALANCING and self.recovery_start_time:
            if time.time() - self.recovery_start_time > self.max_recovery_time:
                print("Recovery timeout exceeded")
                self.transition_to(SystemState.ERROR)

        return commands

    def _analyze_results(self):
        """
        Internal method to decide on personalized recovery action based on ML results.
        """
        mode = self.ml_results['degradation_mode']
        prob = self.ml_results['degradation_prob']
        soh = self.ml_results['soh']

        print(f"Analysis: Mode={mode.name} (prob={prob:.2f}), SOH={soh:.1f}%")

        # Only consider recovery if probability is high enough and SOH is not too low
        if prob < self.degradation_prob_threshold:
            print("Degradation probability too low, considering as healthy")
            self.recovery_action = RecoveryAction.NONE
            return

        if mode == DegradationMode.HEALTHY:
            self.recovery_action = RecoveryAction.NONE
            return

        # Determine personalized recovery action and parameters
        self._determine_personalized_recovery(mode, prob, soh)

    def _determine_personalized_recovery(self, mode: DegradationMode,
                                       prob: float, soh: float):
        """
        Determine personalized recovery action and parameters based on:
        - Degradation mode and probability
        - Current SOH and SOH progression trend
        - Historical effectiveness of actions for this cell
        - Cell-specific characteristics
        """
        # Base action from mode mapping
        base_action = self.mode_to_action.get(mode, RecoveryAction.NONE)

        if base_action == RecoveryAction.NONE:
            self.recovery_action = RecoveryAction.NONE
            self.recovery_parameters = {}
            return

        # Check if degradation is severe enough to skip recovery
        if soh < self.soh_threshold_severe:
            print(f"Severe degradation (SOH={soh:.1f}%), recovery unlikely to be effective")
            self.recovery_action = RecoveryAction.NONE
            self.recovery_parameters = {}
            return

        # Get base parameters for this action
        base_params = self.base_action_parameters.get(base_action, {}).copy()

        # Personalize parameters based on SOH
        personalized_params = self._personalize_parameters_by_soh(base_action, base_params, soh)

        # Further personalize based on historical effectiveness
        final_params = self.recovery_history.get_optimal_params(
            base_action, personalized_params, self.cell_characteristics
        )

        # Determine if we should attempt this action based on predicted effectiveness
        predicted_effectiveness = self.recovery_history.get_effectiveness(
            base_action, self.cell_characteristics
        )

        # Only proceed if predicted effectiveness is above threshold
        if predicted_effectiveness < 0.5:  # Less than 0.5 SOH points improvement expected
            print(f"Low predicted effectiveness ({predicted_effectiveness:.2f}) for {base_action.name}")
            # Try a less aggressive action or general balancing
            if base_action != RecoveryAction.BALANCING:
                print(f"Falling back to general balancing action")
                base_action = RecoveryAction.BALANCING
                base_params = self.base_action_parameters[RecoveryAction.BALANCING].copy()
                personalized_params = self._personalize_parameters_by_soh(base_action, base_params, soh)
                final_params = self.recovery_history.get_optimal_params(
                    base_action, personalized_params, self.cell_characteristics
                )
            else:
                # Even balancing not effective, skip recovery
                self.recovery_action = RecoveryAction.NONE
                self.recovery_parameters = {}
                print("Even general balancing not predicted to be effective, skipping recovery")
                return

        # Set the final recovery action and parameters
        self.recovery_action = base_action
        self.recovery_parameters = final_params

        print(f"Selected personalized recovery action: {self.recovery_action.name}")
        print(f"Base SOH: {soh:.1f}%, Predicted effectiveness: {predicted_effectiveness:.2f}")
        print(f"Personalized parameters: {self.recovery_parameters}")

    def _personalize_parameters_by_soh(self, action: RecoveryAction,
                                     base_params: Dict[str, Any],
                                     soh: float) -> Dict[str, Any]:
        """
        Personalize recovery parameters based on current SOH using SOH-dependent formulas.
        """
        personalized = base_params.copy()

        # Only apply SOH personalization for SOH in recoverable range (60-80%)
        if soh < 60.0 or soh > 85.0:
            return personalized  # Use base parameters outside personalization range

        # Apply SOH-dependent adjustments
        if action in self.soh_adjustment_factors:
            adjustments = self.soh_adjustment_factors[action]
            for param_name, adjustment_func in adjustments.items():
                if param_name in personalized:
                    try:
                        personalized[param_name] = adjustment_func(soh)
                    except Exception as e:
                        print(f"Warning: Could not apply SOH adjustment for {param_name}: {e}")

        return personalized

    def update_recovery_effectiveness(self, cell_id: str, soh_after: float):
        """
        Update recovery effectiveness history after verification sensing.
        Should be called after getting post-recovery ML results in VERIFYING state.
        """
        if (self.state == SystemState.VERIFYING and
            self.recovery_action != RecoveryAction.NONE and
            self.recovery_start_time is not None and
            self.ml_results):

            # Get pre-recovery SOH that was stored when starting recovery
            soh_before = getattr(self, '_last_pre_recovery_soh', self.ml_results.get('soh', 0.0))

            soh_improvement = soh_after - soh_before
            success = soh_improvement >= self.soh_improvement_threshold

            self.recovery_history.add_record(
                cell_id=cell_id or "unknown",
                action=self.recovery_action,
                params=self.recovery_parameters,
                soh_before=soh_before,
                soh_after=soh_after,
                success=success
            )

            print(f"Recovery effectiveness updated: SOH {soh_before:.1f}% -> {soh_after:.1f}% "
                  f"(change: {soh_improvement:.1f}%, success: {success})")

            # Reset for next cycle
            self._last_pre_recovery_soh = None

    def set_cell_under_test(self, cell_id: Any):
        """Set the identifier for the cell being processed."""
        self.cell_under_test = cell_id

    def set_cell_characteristics(self, characteristics: Dict[str, Any]):
        """Set cell-specific characteristics for personalization."""
        self.cell_characteristics = characteristics.copy()

    def store_prerecovery_soh(self, soh: float):
        """Store the SOH value before starting recovery for effectiveness calculation."""
        self._last_pre_recovery_soh = soh

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the decision engine."""
        return {
            'state': self.state.name,
            'cell_under_test': self.cell_under_test,
            'ml_results': self.ml_results,
            'recovery_action': self.recovery_action.name if self.recovery_action else None,
            'recovery_parameters': self.recovery_parameters,
            'time_in_state': time.time() - self.last_transition_time,
            'history_size': len(self.recovery_history.history),
            'soh_history_size': len(self.historical_soh_values)
        }


if __name__ == "__main__":
    # Simple test of the enhanced decision engine
    print("Testing enhanced DecisionEngine with DiagnosticFrame input...")
    engine = DecisionEngine()

    # Set some cell characteristics for personalization
    engine.set_cell_characteristics({
        'age_months': 18,
        'chemistry': 'NMC',
        'form_factor': 'cylindrical',
        'nominal_capacity_ah': 3.0
    })

    # Create a sample DiagnosticFrame for testing
    sample_frame = {
        'timestamp': 1000.0,
        'frameId': 'test_001',
        'source': 'live',
        'cellId': 'TEST_CELL_001',
        'packId': 'TEST_PACK_001',
        'electrical_voltage': 3.7,
        'electrical_current': 2.0,
        'electrical_power': 7.4,
        'electrical_resistance': 0.05,
        'electrical_uncertainty': 0.01,
        'ultrasonic_timeOfFlight': 8.0,
        'ultrasonic_amplitude': 1.0,
        'ultrasonic_phaseShift': 0.0,
        'ultrasonic_speedOfSound': 2500.0,
        'ultrasonic_uncertainty': 0.1,
        'thermal_temperature': 25.0,
        'thermal_tempGradient': 0.1,
        'thermal_heatFlux': 10.0,
        'thermal_uncertainty': 0.5,
        # ML fields
        'degradation_mode_idx': 1,  # LI_PLATING
        'degradation_prob': 0.85,
        'soh': 75.0,
        'stateOfHealth_value': 75.0,
        'stateOfHealth_confidenceInterval_lower': 73.0,
        'stateOfHealth_confidenceInterval_upper': 77.0,
        'stateOfHealth_method': 'ml',
        'degradation_mode': 'li_plating',
        'degradation_probability': 0.85,
        'degradation_perClass_healthy': 0.05,
        'degradation_perClass_li_plating': 0.85,
        'degradation_perClass_active_material_loss': 0.02,
        'degradation_perClass_electrolyte_decomposition': 0.02,
        'degradation_perClass_gas_generation': 0.03,
        'degradation_perClass_internal_short': 0.03,
        'degradation_entropy': 0.5,
        # Rebalancing fields (will be updated by engine)
        'rebalancing_state': 'idle',
        'rebalancing_selectedAction': 'none',
        'rebalancing_actionReason': 'Pending',
        'rebalancing_powerStage_targetCurrent': 0.0,
        'rebalancing_powerStage_actualCurrent': 0.0,
        'rebalancing_powerStage_targetVoltage': 0.0,
        'rebalancing_powerStage_actualVoltage': 0.0,
        'rebalancing_powerStage_pwmDutyCycle': 0.0,
        'rebalancing_executionTime': 0.0
    }

    # Simulate a cycle with recovery using DiagnosticFrame input
    for i in range(15):
        if engine.state == SystemState.IDLE:
            # Inject some fake ML results after first sensing using DiagnosticFrame input
            if i == 2:
                # Update the frame with new ML results
                sample_frame['degradation_mode_idx'] = 1  # LI_PLATING
                sample_frame['degradation_prob'] = 0.85
                sample_frame['soh'] = 75.0
                sample_frame['degradation_mode'] = 'li_plating'
                sample_frame['degradation_probability'] = 0.85

                # Use the new DiagnosticFrame input method
                engine.update_ml_results_from_frame(sample_frame)
                engine.store_prerecovery_soh(75.0)  # Store pre-recovery SOH
        elif engine.state == SystemState.VERIFYING and i == 8:
            # Simulate post-recovery sensing with improved SOH
            sample_frame['degradation_mode_idx'] = 1  # Still LI_PLATING but improving
            sample_frame['degradation_prob'] = 0.30
            sample_frame['soh'] = 78.0  # Improved SOH
            sample_frame['degradation_mode'] = 'li_plating'
            sample_frame['degradation_probability'] = 0.30

            engine.update_ml_results_from_frame(sample_frame)

        result = engine.execute()
        if i < 5 or i >= 10:  # Show interesting steps
            print(f"Step {i}: {result.get('state', 'N/A')}", end="")
            if result.get('action'):
                print(f", Action: {result['action']}", end="")
            if result.get('parameters'):
                print(f", Params: {list(result['parameters'].keys())}", end="")
            print()

        time.sleep(0.1)  # Simulate time passing

        if result.get('done'):
            break

    # Show final status
    print("\nFinal status:")
    status = engine.get_status()
    for key, value in status.items():
        if key not in ['ml_results', 'recovery_parameters']:  # Skip detailed dicts for brevity
            print(f"  {key}: {value}")