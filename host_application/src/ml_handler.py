"""
ML handler module for the EV Battery Diagnostic System host application.
Processes and formats machine learning results for display.
"""

from .logger import get_logger
import numpy as np


class MLHandler:
    """
    Handles ML result processing, formatting, and display preparation.
    """

    def __init__(self):
        """Initialize the ML handler."""
        self.logger = get_logger(__name__)
        self.logger.debug("MLHandler initialized")

        # ML result storage
        self.degradation_mode = "Unknown"
        self.degradation_probability = 0.0
        self.state_of_health = 0.0
        self.confidence_level = "Low"  # Low, Medium, High
        self.prediction_timestamp = None

        # Degradation mode mapping (should match training)
        self.mode_names = {
            0: "healthy",
            1: "li_plating",
            2: "active_material_loss",
            3: "electrolyte_decomposition",
            4: "gas_generation",
            5: "internal_short"
        }

        # Reverse mapping for lookup
        self.mode_to_index = {v: k for k, v in self.mode_names.items()}

        # Confidence thresholds
        self.confidence_thresholds = {
            'high': 0.8,
            'medium': 0.6,
            'low': 0.0
        }

    def update_ml_results(self, mode_index=None, mode_name=None, probability=0.0, soh=0.0):
        """
        Update ML results from either index or name.

        Args:
            mode_index (int, optional): Degradation mode index (0-5)
            mode_name (str, optional): Degradation mode name
            probability (float): Prediction probability (0.0-1.0)
            soh (float): State of health percentage (0-100)
        """
        try:
            # Determine mode index and name
            if mode_index is not None and 0 <= mode_index <= 5:
                self.degradation_mode = self.mode_names[mode_index]
                self.mode_index = mode_index
            elif mode_name is not None and mode_name in self.mode_to_index:
                self.degradation_mode = mode_name
                self.mode_index = self.mode_to_index[mode_name]
            else:
                self.logger.warning(f"Invalid mode specification: index={mode_index}, name={mode_name}")
                return

            # Validate and store probability
            self.degradation_probability = max(0.0, min(1.0, float(probability)))

            # Validate and store SOH
            self.state_of_health = max(0.0, min(100.0, float(soh)))

            # Update confidence level based on probability
            self._update_confidence_level()

            # Update timestamp
            self.prediction_timestamp = datetime.now()

            self.logger.debug(
                f"ML results updated: Mode={self.degradation_mode} "
                f"(index={self.mode_index}), Prob={self.degradation_probability:.3f}, "
                f"SOH={self.state_of_health:.1f}%, Confidence={self.confidence_level}"
            )

        except Exception as e:
            self.logger.error(f"Error updating ML results: {e}")

    def _update_confidence_level(self):
        """Update confidence level based on prediction probability."""
        prob = self.degradation_probability
        if prob >= self.confidence_thresholds['high']:
            self.confidence_level = "High"
        elif prob >= self.confidence_thresholds['medium']:
            self.confidence_level = "Medium"
        else:
            self.confidence_level = "Low"

    def get_ml_results(self):
        """
        Get current ML results.

        Returns:
            dict: Dictionary containing ML results
        """
        return {
            'degradation_mode': self.degradation_mode,
            'mode_index': self.mode_index,
            'degradation_probability': self.degradation_probability,
            'state_of_health': self.state_of_health,
            'confidence_level': self.confidence_level,
            'timestamp': self.prediction_timestamp.isoformat() if self.prediction_timestamp else None
        }

    def get_display_text(self):
        """
        Get formatted text for display in the UI.

        Returns:
            dict: Formatted strings for UI labels
        """
        return {
            'mode_text': self.degradation_mode.replace('_', ' ').title(),
            'probability_text': f"{self.degradation_probability:.1%}",
            'soh_text': f"{self.state_of_health:.1f}%",
            'confidence_text': self.confidence_level
        }

    def get_status_color(self):
        """
        Get color indicator based on ML results.

        Returns:
            dict: RGB colors for different status indicators
        """
        # Color mapping: Green (good), Yellow (warning), Red (bad)
        colors = {
            'healthy': (0, 255, 0),      # Green
            'li_plating': (255, 165, 0), # Orange
            'active_material_loss': (255, 69, 0), # Red-Orange
            'electrolyte_decomposition': (255, 0, 0), # Red
            'gas_generation': (255, 215, 0), # Gold
            'internal_short': (139, 0, 0)   # Dark Red
        }

        # Get base color for mode
        base_color = colors.get(self.degradation_mode, (128, 128, 128))  # Default gray

        # Adjust brightness based on confidence
        confidence_factor = {
            'High': 1.0,
            'Medium': 0.7,
            'Low': 0.4
        }.get(self.confidence_level, 0.5)

        # Apply confidence factor to brightness
        adjusted_color = tuple(int(c * confidence_factor) for c in base_color)

        return {
            'mode_color': adjusted_color,
            'probability_color': (0, 255, 0) if self.confidence_level == 'High' else
                               (255, 255, 0) if self.confidence_level == 'Medium' else
                               (255, 0, 0),
            'soh_color': (0, 255, 0) if self.state_of_health >= 80 else
                        (255, 255, 0) if self.state_of_health >= 60 else
                        (255, 0, 0)
        }

    def is_healthy(self):
        """
        Check if the battery is predicted to be healthy.

        Returns:
            bool: True if healthy with sufficient confidence
        """
        return (self.degradation_mode == 'healthy' and
                self.degradation_probability >= self.confidence_thresholds['medium'])

    def needs_recovery(self):
        """
        Check if the battery needs recovery action.

        Returns:
            bool: True if recovery is recommended
        """
        # Recovery needed if not healthy OR SOH is low OR medium confidence in degradation
        not_healthy = self.degradation_mode != 'healthy'
        low_soh = self.state_of_health < 80.0
        medium_conf_degradation = (self.degradation_mode != 'healthy' and
                                 self.confidence_level in ['Medium', 'High'])

        return not_healthy or low_soh or medium_conf_degradation

    def get_recommended_action(self):
        """
        Get recommended recovery action based on ML results.

        Returns:
            tuple: (action_type, action_parameters) or (None, None) if no action needed
        """
        if not self.needs_recovery():
            return None, None

        # Map degradation mode to recovery action
        mode_to_action = {
            'li_plating': ('PULSE_DEPLATING', {
                'voltage': 4.2,
                'pulse_width_ms': 10,
                'pulse_interval_s': 1,
                'num_pulses': 100
            }),
            'active_material_loss': ('EQUILIBRATION', {
                'current': 0.5,
                'direction': 'charge'
            }),
            'electrolyte_decomposition': ('EQUILIBRATION', {
                'current': 0.5,
                'direction': 'charge'
            }),
            'gas_generation': ('GAS_RECOMBINATION', {
                'voltage': 3.9
            }),
            'internal_short': ('SHORT_ISOLATION', {
                'duration_s': 10
            }),
            'healthy': None  # No action for healthy
        }

        # Special case: if SOH is very low, recommend balancing regardless of mode
        if self.state_of_health < 60.0:
            return ('BALANCING', {
                'target_voltage': 3.7,
                'tolerance': 0.01
            })

        # Get action for specific mode
        action_tuple = mode_to_action.get(self.degradation_mode)
        if action_tuple:
            return action_tuple

        # Default fallback
        return ('BALANCING', {
            'target_voltage': 3.7,
            'tolerance': 0.01
        })

    def reset(self):
        """Reset ML results to default values."""
        self.logger.debug("Resetting ML results")
        self.degradation_mode = "Unknown"
        self.degradation_probability = 0.0
        self.state_of_health = 0.0
        self.confidence_level = "Low"
        self.prediction_timestamp = None
        self.mode_index = -1

# Import datetime at module level to avoid circular imports
from datetime import datetime