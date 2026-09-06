import os
import sys
import json
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.diagnostic_schema import (
    DiagnosticFrame, DegradationModeEnum, RebalancingActionEnum, SafetyStatusEnum
)
from backend.ml_processor import MLProcessor
from backend.rebalancing import RebalancingProcessor


def test_diagnostic_frame_defaults_and_roundtrip():
    """Verify DiagnosticFrame default initialization, to_dict, and from_dict round-trip."""
    frame = DiagnosticFrame()
    d = frame.to_dict()
    
    assert isinstance(d, dict)
    assert 'frameId' in d
    assert 'timestamp' in d
    assert 'electrical_voltage' in d
    assert 'ultrasonic_timeOfFlight' in d
    assert 'thermal_temperature' in d
    assert 'stateOfHealth_value' in d
    assert 'degradation_mode' in d
    assert 'rebalancing_state' in d
    assert 'attention_weight_electrical' in d
    assert 'electrical_power' in d
    
    # Power is derived correctly: voltage * current
    assert d['electrical_power'] == d['electrical_voltage'] * d['electrical_current']
    
    # Round-trip reconstruction
    frame_reconstructed = DiagnosticFrame.from_dict(d)
    d2 = frame_reconstructed.to_dict()
    
    for k in d:
        assert d[k] == d2[k], f"Field '{k}' altered during roundtrip serialization"


def test_schema_conformance_across_pipeline():
    """
    Simulate full data pipeline passing DiagnosticFrame through MLProcessor and RebalancingProcessor.
    Asserts zero field drops and total type conformance.
    """
    import asyncio
    
    async def run_pipeline():
        processor = MLProcessor(sequence_length=256)
        await processor.initialize()
        
        rebalancer = RebalancingProcessor()
        
        raw_frame = {
            'source': 'gazebo',
            'cellId': 'CELL_TEST_01',
            'electrical_voltage': 3.42,
            'electrical_current': 0.50,
            'electrical_resistance': 0.068,
            'ultrasonic_timeOfFlight': 8.45,
            'ultrasonic_amplitude': 0.72,
            'ultrasonic_phaseShift': 0.1,
            'ultrasonic_speedOfSound': 2360.0,
            'thermal_temperature': 34.2,
            'thermal_tempGradient': 0.25,
            'simulation_soc': 0.40
        }
        
        # 1. Ingest into DiagnosticFrame
        diag_in = DiagnosticFrame.from_dict(raw_frame)
        in_dict = diag_in.to_dict()
        
        # 2. Process through ML
        ml_dict = await processor.process_frame(in_dict)
        diag_ml = DiagnosticFrame.from_dict(ml_dict)
        
        assert diag_ml.stateOfHealth_value > 0.0
        assert diag_ml.degradation_mode in [m.value for m in DegradationModeEnum]
        assert 0.0 <= diag_ml.degradation_probability <= 1.0
        assert diag_ml.stateOfHealth_confidenceInterval_lower <= diag_ml.stateOfHealth_value <= diag_ml.stateOfHealth_confidenceInterval_upper
        
        # 3. Process through Rebalancing Processor
        reb_dict = rebalancer.process_frame(diag_ml.to_dict())
        diag_out = DiagnosticFrame.from_dict(reb_dict)
        
        assert diag_out.rebalancing_state != ''
        assert diag_out.rebalancing_safetyStatus in [s.value for s in SafetyStatusEnum]
        
        # Final JSON serialization test
        json_str = json.dumps(diag_out.to_dict())
        parsed = json.loads(json_str)
        assert parsed['frameId'] == diag_out.frameId
        assert parsed['cellId'] == 'CELL_TEST_01'

    asyncio.run(run_pipeline())
