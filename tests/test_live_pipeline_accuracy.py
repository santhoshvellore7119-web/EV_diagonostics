import os
import sys
import asyncio
import numpy as np
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.ml_processor import MLProcessor
from backend.rebalancing import RebalancingProcessor
from common.diagnostic_schema import DiagnosticFrame, DegradationModeEnum, SafetyStatusEnum
from ev_cell_multimodal_sim.core.physics_engine import DEGRADATION_PHYSICS_PARAMS


def test_live_pipeline_sweep_all_modes():
    """
    Simulate live streaming frames for all 6 degradation modes through the end-to-end
    ML inference and active rebalancing safety pipeline.
    """
    async def _run():
        processor = MLProcessor(sequence_length=256)
        await processor.initialize()
        rebalancer = RebalancingProcessor()

        mode_list = [
            'healthy', 'li_plating', 'active_material_loss',
            'electrolyte_decomposition', 'gas_generation', 'internal_short'
        ]

        predictions = []
        ground_truth = []
        soh_errors = []

        for mode_idx, mode_name in enumerate(mode_list):
            phys = DEGRADATION_PHYSICS_PARAMS[mode_name]
            
            # Test across multiple SOCs for each mode
            for soc in [0.25, 0.50, 0.75]:
                true_soh = float(phys['nominal_soh'] * (1.0 - 0.05 * (1.0 - soc)))
                raw_frame = {
                    'source': '3d',
                    'cellId': f'CELL_{mode_name.upper()}',
                    'electrical_voltage': float(3.0 + 1.2 * soc - 0.5 * phys['r0']),
                    'electrical_current': 0.50,
                    'electrical_resistance': float(phys['r0']),
                    'ultrasonic_timeOfFlight': float((2 * 0.01 / phys['sos']) * 1e6),
                    'ultrasonic_amplitude': float(phys['attenuation']),
                    'ultrasonic_phaseShift': float(phys.get('phase_shift', 0.0)),
                    'ultrasonic_speedOfSound': float(phys['sos']),
                    'thermal_temperature': float(25.0 + (phys['r0'] + phys['r1']) * (0.5**2) * 30.0 + (10.0 if mode_name == 'internal_short' else 0.0)),
                    'thermal_tempGradient': 0.15 if mode_name != 'internal_short' else 3.50,
                    'simulation_soc': soc
                }

                # 1. Pipeline step: ML Processor (zero label leakage)
                ml_frame = await processor.process_frame(raw_frame)
                
                # 2. Pipeline step: Active Rebalancer
                reb_frame = rebalancer.process_frame(ml_frame)
                
                pred_idx = ml_frame['degradation_mode_idx']
                pred_mode = ml_frame['degradation_mode']
                pred_soh = ml_frame['stateOfHealth_value']
                
                predictions.append(pred_idx)
                ground_truth.append(mode_idx)
                soh_errors.append(abs(pred_soh - true_soh))

                # Safety Interlock Assertions
                if mode_name == 'internal_short':
                    assert reb_frame['rebalancing_safetyStatus'] == SafetyStatusEnum.CRITICAL_LOCKOUT_ISOLATED.value
                    assert reb_frame['rebalancing_powerStage_targetCurrent'] == 0.0
                    assert reb_frame['rebalancing_safetyInterlock_engaged'] == True

        accuracy = np.mean(np.array(predictions) == np.array(ground_truth)) * 100.0
        mean_soh_error = np.mean(soh_errors)

        print(f"\n[LIVE PIPELINE SWEEP] End-to-End Live Accuracy: {accuracy:.1f}%")
        print(f"[LIVE PIPELINE SWEEP] Mean SOH Error: {mean_soh_error:.2f}%")

        # Assert live streaming performance standards
        assert accuracy >= 80.0, f"Live pipeline accuracy ({accuracy:.1f}%) below 80% threshold"
        assert mean_soh_error <= 8.0, f"Live pipeline SOH MAE ({mean_soh_error:.2f}%) exceeds 8.0% threshold"

    asyncio.run(_run())
