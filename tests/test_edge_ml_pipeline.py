#!/usr/bin/env python
"""
Live streaming accuracy and active rebalancing safety pipeline test with EdgeMLProcessor.
Evaluates end-to-end 360-frame sweep on the ultra-lightweight Edge ML engine.
"""

import os
import sys
import asyncio
import numpy as np
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
sim_core_path = os.path.join(project_root, 'ev_cell_multimodal_sim')
if sim_core_path not in sys.path:
    sys.path.insert(0, sim_core_path)

from backend.edge_ml_processor import EdgeMLProcessor
from backend.rebalancing import RebalancingProcessor
from common.diagnostic_schema import SafetyStatusEnum
from core.physics_engine import DEGRADATION_PHYSICS_PARAMS


def test_edge_pipeline_dense_360_frame_sweep():
    """
    Run full 360-frame sweep through EdgeMLProcessor and verify safety lockout interlocks.
    """
    async def _run():
        processor = EdgeMLProcessor()
        await processor.initialize()
        rebalancer = RebalancingProcessor()

        mode_list = [
            'healthy', 'li_plating', 'active_material_loss',
            'electrolyte_decomposition', 'gas_generation', 'internal_short'
        ]

        soc_points = [0.10, 0.18, 0.26, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.92]
        noise_levels = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25]

        predictions = []
        ground_truth = []
        soh_errors = []
        internal_short_lockouts = 0

        np.random.seed(42)

        for mode_idx, mode_name in enumerate(mode_list):
            phys = DEGRADATION_PHYSICS_PARAMS[mode_name]

            for soc in soc_points:
                for noise in noise_levels:
                    true_soh = float(phys['nominal_soh'] * (1.0 - 0.05 * (1.0 - soc)))

                    r0_noisy = float(phys['r0'] * (1.0 + np.random.uniform(-0.02, 0.02) * noise))
                    r1_noisy = float(phys['r1'] * (1.0 + np.random.uniform(-0.02, 0.02) * noise))
                    sos_noisy = float(phys['sos'] + np.random.uniform(-10.0, 10.0) * noise)
                    atten_noisy = float(np.clip(phys['attenuation'] + np.random.uniform(-0.015, 0.015) * noise, 0.10, 1.15))
                    phase_noisy = float(phys.get('phase_shift', 0.0) + np.random.uniform(-0.02, 0.02) * noise)
                    r_th_noisy = float(phys.get('r_th', 2.0) * (1.0 + np.random.uniform(-0.02, 0.02) * noise))
                    c_th_noisy = float(phys.get('c_th', 500.0) * (1.0 + np.random.uniform(-0.02, 0.02) * noise))

                    i_pulse = 0.50
                    ocv = float(3.0 + 1.2 * soc)
                    voltage = float(ocv - i_pulse * r0_noisy)
                    ambient_temp = 25.0 + (10.0 if mode_name == 'internal_short' else 0.0)
                    temp_rise = float((r0_noisy + r1_noisy) * (i_pulse ** 2) * r_th_noisy * 30.0 + max(0.0, ambient_temp - 25.0))
                    temp = float(25.0 + temp_rise)
                    dT_dt = 3.50 if mode_name == 'internal_short' else float((i_pulse ** 2) * (r0_noisy + r1_noisy) * 50.0 / (c_th_noisy * 1e-2))

                    raw_frame = {
                        'source': 'edge_hw',
                        'cellId': f'CELL_{mode_name.upper()}',
                        'electrical_voltage': voltage,
                        'electrical_current': i_pulse,
                        'electrical_resistance': r0_noisy,
                        'ultrasonic_timeOfFlight': float((2.0 * 0.01 / max(100.0, sos_noisy)) * 1e6),
                        'ultrasonic_amplitude': atten_noisy,
                        'ultrasonic_phaseShift': phase_noisy,
                        'ultrasonic_speedOfSound': sos_noisy,
                        'thermal_temperature': temp,
                        'thermal_tempGradient': dT_dt,
                        'simulation_soc': soc
                    }

                    # Edge ML inference
                    ml_frame = await processor.process_frame(raw_frame)

                    # Active Rebalancer
                    reb_frame = rebalancer.process_frame(ml_frame)

                    pred_idx = ml_frame['degradation_mode_idx']
                    pred_soh = ml_frame['stateOfHealth_value']

                    predictions.append(pred_idx)
                    ground_truth.append(mode_idx)
                    soh_errors.append(abs(pred_soh - true_soh))

                    if mode_name == 'internal_short':
                        if reb_frame['rebalancing_safetyStatus'] == SafetyStatusEnum.CRITICAL_LOCKOUT_ISOLATED.value:
                            internal_short_lockouts += 1

        total_frames = len(predictions)
        assert total_frames == 360, f"Expected 360 frames, got {total_frames}"

        accuracy = np.mean(np.array(predictions) == np.array(ground_truth)) * 100.0
        mean_soh_error = np.mean(soh_errors)

        print(f"\n[EDGE PIPELINE 360-FRAME SWEEP] Overall Accuracy: {accuracy:.2f}%")
        print(f"[EDGE PIPELINE 360-FRAME SWEEP] Mean SOH MAE: {mean_soh_error:.2f}%")
        print(f"[EDGE PIPELINE 360-FRAME SWEEP] Internal Short Lockouts: {internal_short_lockouts}/60")

        assert accuracy >= 93.0, f"Edge sweep accuracy ({accuracy:.2f}%) below 93% threshold"
        assert mean_soh_error <= 5.0, f"Edge sweep SOH MAE ({mean_soh_error:.2f}%) exceeds 5.0% threshold"
        assert internal_short_lockouts == 60, f"Internal short safety lockout failed ({internal_short_lockouts}/60)"

    asyncio.run(_run())
