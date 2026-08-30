"""
Evidence generation backend for publication/patent submission.

This module provides functionality for:
- Modality ablation studies (systematically disabling sensor modalities)
- Baseline comparison (comparing against healthy cell or baseline performance)
- Before/after rebalancing trends (tracking SOH and other metrics over recovery cycles)
- Session recording and replay (for debugging and demonstration)
- Statistical analysis and report generation
"""

import json
import time
import numpy as np
from typing import Dict, List, Optional, Any
from collections import deque
import os
from datetime import datetime


class EvidenceGenerator:
    """
    Main evidence generation class that handles recording, analysis,
    and report generation for battery diagnostic data.
    """

    def __init__(self, max_buffer_size: int = 10000):
        """
        Initialize the evidence generator.

        Args:
            max_buffer_size: Maximum number of frames to store in memory
        """
        self.max_buffer_size = max_buffer_size
        self.frame_buffer: deque = deque(maxlen=max_buffer_size)
        self.session_start_time = time.time()
        self.is_recording = False
        self.baseline_data: Optional[Dict[str, Any]] = None
        self.rebalancing_cycles: List[Dict[str, Any]] = []
        self.current_cycle: Optional[Dict[str, Any]] = None
        self.ablation_studies: List[Dict[str, Any]] = []

        # Metadata for the evidence session
        self.session_metadata = {
            'start_time': None,
            'end_time': None,
            'total_frames': 0,
            'cell_id': None,
            'pack_id': None,
            'source_modes': set(),  # live, simulink, 3d
        }

    def start_recording(self, metadata: Optional[Dict[str, Any]] = None):
        """
        Start recording a new evidence session.

        Args:
            metadata: Optional metadata to associate with the session
        """
        self.is_recording = True
        self.session_start_time = time.time()
        self.session_metadata['start_time'] = datetime.fromtimestamp(
            self.session_start_time).isoformat()
        self.frame_buffer.clear()
        self.rebalancing_cycles.clear()
        self.ablation_studies.clear()

        if metadata:
            self.session_metadata.update(metadata)

        print(f"Evidence recording started at {self.session_metadata['start_time']}")

    def stop_recording(self):
        """Stop the current evidence session."""
        if self.is_recording:
            self.is_recording = False
            self.session_metadata['end_time'] = datetime.fromtimestamp(
                time.time()).isoformat()
            self.session_metadata['total_frames'] = len(self.frame_buffer)
            print(f"Evidence recording stopped. "
                  f"Total frames recorded: {self.session_metadata['total_frames']}")

    def record_frame(self, frame: Dict[str, Any]):
        """
        Record a single DiagnosticFrame for evidence generation.

        Args:
            frame: DiagnosticFrame dictionary to record
        """
        if not self.is_recording:
            return

        # Add timestamp if not present
        if 'timestamp' not in frame:
            frame['timestamp'] = time.time()

        # Update session metadata
        if 'cellId' in frame and self.session_metadata['cell_id'] is None:
            self.session_metadata['cell_id'] = frame['cellId']
        if 'packId' in frame and self.session_metadata['pack_id'] is None:
            self.session_metadata['pack_id'] = frame['packId']
        if 'source' in frame:
            self.session_metadata['source_modes'].add(frame['source'])

        # Store the frame
        self.frame_buffer.append(frame.copy())

    def set_baseline(self, baseline_frame: Dict[str, Any]):
        """
        Set a baseline frame for comparison studies.

        Args:
            baseline_frame: DiagnosticFrame representing baseline/healthy condition
        """
        self.baseline_data = baseline_frame.copy()
        print("Baseline data set for evidence comparison")

    def start_rebalancing_cycle(self, trigger_frame: Dict[str, Any]):
        """
        Mark the start of a rebalancing cycle for before/after analysis.

        Args:
            trigger_frame: Frame that triggered the rebalancing action
        """
        if self.current_cycle is not None:
            # Complete previous cycle if not already completed
            self._finalize_rebalancing_cycle()

        self.current_cycle = {
            'start_time': time.time(),
            'start_frame': trigger_frame.copy(),
            'end_frame': None,
            'rebalancing_action': None,
            'soh_before': trigger_frame.get('stateOfHealth_value', 0.0),
            'soh_after': None,
            'soh_change': None,
            'effectiveness': None
        }

        print(f"Started rebalancing cycle at {self.current_cycle['start_time']}")

    def end_rebalancing_cycle(self, end_frame: Dict[str, Any]):
        """
        Mark the end of a rebalancing cycle and compute effectiveness.

        Args:
            end_frame: Frame after rebalancing completion
        """
        if self.current_cycle is None:
            print("Warning: No active rebalancing cycle to end")
            return

        self.current_cycle['end_frame'] = end_frame.copy()
        self.current_cycle['end_time'] = time.time()
        self.current_cycle['soh_after'] = end_frame.get('stateOfHealth_value', 0.0)
        self.current_cycle['soh_change'] = (
            self.current_cycle['soh_after'] - self.current_cycle['soh_before']
        )
        # Effectiveness: positive SOH change indicates successful recovery
        self.current_cycle['effectiveness'] = (
            self.current_cycle['soh_change'] > 0.5  # threshold of 0.5% improvement
        )

        # Extract rebalancing action from frame if available
        if 'rebalancing_selectedAction' in end_frame:
            self.current_cycle['rebalancing_action'] = end_frame['rebalancing_selectedAction']

        self.rebalancing_cycles.append(self.current_cycle)
        print(f"Completed rebalancing cycle: SOH change = "
              f"{self.current_cycle['soh_change']:.2f}% "
              f"(Effective: {self.current_cycle['effectiveness']})")

        self.current_cycle = None

    def record_ablation_study(self, modality_disabled: str,
                            baseline_metrics: Dict[str, float],
                            ablated_metrics: Dict[str, float]):
        """
        Record results from a modality ablation study.

        Args:
            modality_disabled: Name of the modality that was disabled
            baseline_metrics: Performance metrics with all modalities enabled
            ablated_metrics: Performance metrics with the modality disabled
        """
        study = {
            'timestamp': time.time(),
            'modality_disabled': modality_disabled,
            'baseline_metrics': baseline_metrics.copy(),
            'ablated_metrics': ablated_metrics.copy(),
            'metric_changes': {}
        }

        # Compute percentage changes for each metric
        for key in baseline_metrics:
            if key in ablated_metrics and baseline_metrics[key] != 0:
                change = ((ablated_metrics[key] - baseline_metrics[key]) /
                         baseline_metrics[key]) * 100
                study['metric_changes'][key] = change

        self.ablation_studies.append(study)
        print(f"Ablation study recorded for modality: {modality_disabled}")

    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current evidence session.

        Returns:
            Dictionary containing session summary statistics
        """
        if not self.frame_buffer:
            return {'error': 'No frames recorded'}

        frames = list(self.frame_buffer)

        # Compute basic statistics
        soh_values = [f.get('stateOfHealth_value', 0) for f in frames if 'stateOfHealth_value' in f]
        voltage_values = [f.get('electrical_voltage', 0) for f in frames if 'electrical_voltage' in f]
        temperature_values = [f.get('thermal_temperature', 0) for f in frames if 'thermal_temperature' in f]

        summary = {
            'session_metadata': self.session_metadata.copy(),
            'frame_count': len(frames),
            'time_duration': time.time() - self.session_start_time if self.is_recording else (
                datetime.fromisoformat(self.session_metadata['end_time']) -
                datetime.fromisoformat(self.session_metadata['start_time'])
            ).total_seconds() if self.session_metadata.get('end_time') else 0,
            'soh_statistics': {
                'mean': np.mean(soh_values) if soh_values else 0,
                'std': np.std(soh_values) if soh_values else 0,
                'min': np.min(soh_values) if soh_values else 0,
                'max': np.max(soh_values) if soh_values else 0,
                'trend': self._compute_trend(soh_values) if len(soh_values) > 1 else 0
            } if soh_values else {},
            'voltage_statistics': {
                'mean': np.mean(voltage_values) if voltage_values else 0,
                'std': np.std(voltage_values) if voltage_values else 0,
                'min': np.min(voltage_values) if voltage_values else 0,
                'max': np.max(voltage_values) if voltage_values else 0
            } if voltage_values else {},
            'temperature_statistics': {
                'mean': np.mean(temperature_values) if temperature_values else 0,
                'std': np.std(temperature_values) if temperature_values else 0,
                'min': np.min(temperature_values) if temperature_values else 0,
                'max': np.max(temperature_values) if temperature_values else 0
            } if temperature_values else {},
            'rebalancing_cycles': len(self.rebalancing_cycles),
            'successful_recoveries': sum(1 for c in self.rebalancing_cycles if c.get('effectiveness', False)),
            'ablation_studies': len(self.ablation_studies)
        }

        # Convert source_modes set to list for JSON serialization
        if 'source_modes' in summary['session_metadata']:
            summary['session_metadata']['source_modes'] = list(
                summary['session_metadata']['source_modes'])

        return summary

    def generate_report(self, include_raw_data: bool = False) -> Dict[str, Any]:
        """
        Generate a comprehensive evidence report.

        Args:
            include_raw_data: Whether to include raw frame data in the report

        Returns:
            Dictionary containing the full evidence report
        """
        report = {
            'report_generated': datetime.fromtimestamp(time.time()).isoformat(),
            'session_summary': self.get_session_summary(),
            'rebalancing_analysis': self._analyze_rebalancing_cycles(),
            'ablation_analysis': self._analyze_ablation_studies(),
            'baseline_comparison': self._generate_baseline_comparison() if self.baseline_data else None
        }

        if include_raw_data and self.frame_buffer:
            report['raw_frames'] = list(self.frame_buffer)

        return report

    def save_report(self, filepath: str, include_raw_data: bool = False):
        """
        Save the evidence report to a JSON file.

        Args:
            filepath: Path where the report should be saved
            include_raw_data: Whether to include raw frame data
        """
        report = self.generate_report(include_raw_data=include_raw_data)

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"Evidence report saved to {filepath}")

    def load_report(self, filepath: str) -> Dict[str, Any]:
        """
        Load a previously saved evidence report.

        Args:
            filepath: Path to the JSON report file

        Returns:
            Dictionary containing the loaded report
        """
        with open(filepath, 'r') as f:
            return json.load(f)

    def replay_session(self, speed_factor: float = 1.0):
        """
        Replay the recorded session (generator yields frames at original timing).

        Args:
            speed_factor: Factor to speed up/slow down replay (1.0 = real-time)

        Yields:
            DiagnosticFrame dictionaries in original order with timing
        """
        if not self.frame_buffer:
            return

        frames = list(self.frame_buffer)
        if len(frames) < 2:
            for frame in frames:
                yield frame
            return

        start_time = frames[0].get('timestamp', time.time())
        prev_timestamp = start_time

        for frame in frames:
            current_timestamp = frame.get('timestamp', time.time())
            if len(frames) > 1:
                # Calculate delay based on original timing
                delay = (current_timestamp - prev_timestamp) / speed_factor
                if delay > 0:
                    time.sleep(delay)
                prev_timestamp = current_timestamp
            yield frame

    # Private helper methods

    def _finalize_rebalancing_cycle(self):
        """Finalize the current rebalancing cycle if incomplete."""
        if self.current_cycle and self.current_cycle['end_frame'] is None:
            # Use the last recorded frame as end frame
            if self.frame_buffer:
                last_frame = self.frame_buffer[-1]
                self.end_rebalancing_cycle(last_frame)
            else:
                # Just mark as incomplete
                self.current_cycle['end_frame'] = self.current_cycle['start_frame']
                self.current_cycle['soh_after'] = self.current_cycle['soh_before']
                self.current_cycle['soh_change'] = 0.0
                self.current_cycle['effectiveness'] = False
                self.rebalancing_cycles.append(self.current_cycle)
            self.current_cycle = None

    def _compute_trend(self, values: List[float]) -> float:
        """
        Compute linear trend (slope) of values over time.

        Args:
            values: List of numeric values

        Returns:
            Slope of linear regression (positive = increasing trend)
        """
        if len(values) < 2:
            return 0.0

        x = np.arange(len(values))
        y = np.array(values)
        slope = np.polyfit(x, y, 1)[0]
        return slope

    def _analyze_rebalancing_cycles(self) -> Dict[str, Any]:
        """Analyze recorded rebalancing cycles."""
        if not self.rebalancing_cycles:
            return {'message': 'No rebalancing cycles recorded'}

        effective_cycles = [c for c in self.rebalancing_cycles if c.get('effectiveness', False)]
        soh_changes = [c.get('soh_change', 0) for c in self.rebalancing_cycles if c.get('soh_change') is not None]
        cycle_durations = [
            c.get('end_time', 0) - c.get('start_time', 0)
            for c in self.rebalancing_cycles
            if c.get('end_time') and c.get('start_time')
        ]

        analysis = {
            'total_cycles': len(self.rebalancing_cycles),
            'effective_cycles': len(effective_cycles),
            'effectiveness_rate': len(effective_cycles) / len(self.rebalancing_cycles) if self.rebalancing_cycles else 0,
            'soh_change_statistics': {
                'mean': np.mean(soh_changes) if soh_changes else 0,
                'std': np.std(soh_changes) if soh_changes else 0,
                'min': np.min(soh_changes) if soh_changes else 0,
                'max': np.max(soh_changes) if soh_changes else 0
            } if soh_changes else {},
            'cycle_duration_statistics': {
                'mean': np.mean(cycle_durations) if cycle_durations else 0,
                'std': np.std(cycle_durations) if cycle_durations else 0,
                'min': np.min(cycle_durations) if cycle_durations else 0,
                'max': np.max(cycle_durations) if cycle_durations else 0
            } if cycle_durations else {},
            'action_distribution': {}
        }

        # Count actions taken
        actions = [c.get('rebalancing_action', 'unknown') for c in self.rebalancing_cycles]
        for action in set(actions):
            analysis['action_distribution'][action] = actions.count(action)

        return analysis

    def _analyze_ablation_studies(self) -> Dict[str, Any]:
        """Analyze recorded ablation studies."""
        if not self.ablation_studies:
            return {'message': 'No ablation studies recorded'}

        # Aggregate changes by modality
        modality_changes = {}
        for study in self.ablation_studies:
            modality = study['modality_disabled']
            if modality not in modality_changes:
                modality_changes[modality] = []

            for metric, change in study['metric_changes'].items():
                if metric not in modality_changes[modality]:
                    modality_changes[modality][metric] = []
                modality_changes[modality][metric].append(change)

        # Compute statistics for each modality
        analysis = {}
        for modality, metrics in modality_changes.items():
            analysis[modality] = {}
            for metric, changes in metrics.items():
                analysis[modality][metric] = {
                    'mean_change': np.mean(changes),
                    'std_change': np.std(changes),
                    'min_change': np.min(changes),
                    'max_change': np.max(changes),
                    'study_count': len(changes)
                }

        return analysis

    def _generate_baseline_comparison(self) -> Dict[str, Any]:
        """Generate comparison against baseline data."""
        if not self.baseline_data or not self.frame_buffer:
            return {'message': 'Insufficient data for baseline comparison'}

        frames = list(self.frame_buffer)
        if not frames:
            return {'message': 'No frames to compare against baseline'}

        # Compare recent frames to baseline
        recent_frames = frames[-min(100, len(frames)):]  # Last 100 frames or all if fewer

        # Compute averages for recent frames
        recent_soh = np.mean([f.get('stateOfHealth_value', 0) for f in recent_frames if 'stateOfHealth_value' in f])
        recent_voltage = np.mean([f.get('electrical_voltage', 0) for f in recent_frames if 'electrical_voltage' in f])
        recent_temperature = np.mean([f.get('thermal_temperature', 0) for f in recent_frames if 'thermal_temperature' in f])

        baseline_soh = self.baseline_data.get('stateOfHealth_value', 0)
        baseline_voltage = self.baseline_data.get('electrical_voltage', 0)
        baseline_temperature = self.baseline_data.get('thermal_temperature', 0)

        comparison = {
            'baseline_values': {
                'stateOfHealth': baseline_soh,
                'electrical_voltage': baseline_voltage,
                'thermal_temperature': baseline_temperature
            },
            'recent_average_values': {
                'stateOfHealth': float(recent_soh) if not np.isnan(recent_soh) else 0,
                'electrical_voltage': float(recent_voltage) if not np.isnan(recent_voltage) else 0,
                'thermal_temperature': float(recent_temperature) if not np.isnan(recent_temperature) else 0
            },
            'percentage_changes': {
                'stateOfHealth': ((recent_soh - baseline_soh) / baseline_soh * 100) if baseline_soh != 0 else 0,
                'electrical_voltage': ((recent_voltage - baseline_voltage) / baseline_voltage * 100) if baseline_voltage != 0 else 0,
                'thermal_temperature': ((recent_temperature - baseline_temperature) / baseline_temperature * 100) if baseline_temperature != 0 else 0
            },
            'improvement_detected': recent_soh > baseline_soh,
            'frames_compared': len(recent_frames)
        }

        return comparison


# Convenience function for quick evidence recording
def create_evidence_recorder(max_buffer_size: int = 10000) -> EvidenceGenerator:
    """
    Factory function to create an evidence recorder.

    Args:
        max_buffer_size: Maximum number of frames to store

    Returns:
        Configured EvidenceGenerator instance
    """
    return EvidenceGenerator(max_buffer_size=max_buffer_size)


# Example usage for testing
if __name__ == "__main__":
    import asyncio

    async def test_evidence_generator():
        # Create evidence generator
        evidence = EvidenceGenerator(max_buffer_size=1000)

        # Start recording
        evidence.start_recording({
            'cell_id': 'TEST_001',
            'pack_id': 'PACK_001',
            'test_purpose': 'Unit testing evidence generation'
        })

        # Simulate recording some frames
        for i in range(10):
            frame = {
                'timestamp': time.time() + i,
                'frameId': str(i),
                'source': 'live',
                'cellId': 'TEST_001',
                'packId': 'PACK_001',
                'electrical_voltage': 3.5 + np.random.normal(0, 0.1),
                'electrical_current': 2.0 + np.random.normal(0, 0.1),
                'electrical_power': 0.0,  # Will be calculated
                'electrical_resistance': 0.05,
                'stateOfHealth_value': 85.0 + np.random.normal(0, 0.5),
                'stateOfHealth_confidenceInterval_lower': 84.0,
                'stateOfHealth_confidenceInterval_upper': 86.0,
                'degradation_mode': 'healthy',
                'degradation_probability': 0.95,
                'rebalancing_state': 'idle',
                'rebalancing_selectedAction': 'none',
                'rebalancing_actionReason': 'No action needed',
                'rebalancing_executionTime': 0.0
            }
            frame['electrical_power'] = frame['electrical_voltage'] * frame['electrical_current']
            evidence.record_frame(frame)
            await asyncio.sleep(0.01)

        # Stop recording and generate report
        evidence.stop_recording()
        report = evidence.generate_report()
        print(f"Generated report with {report['session_summary']['frame_count']} frames")

        # Save report
        evidence.save_report('/tmp/evidence_test_report.json')

    asyncio.run(test_evidence_generator())