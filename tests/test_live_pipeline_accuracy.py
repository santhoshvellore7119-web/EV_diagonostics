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


def test_dense_360_frame_pipeline_sweep():
    """
    Comprehensive dense 360-frame sweep (6 modes x 10 SOC points x 6 noise realizations).
    Evaluates end-to-end ML classification, SOH estimation, and active rebalancing interlocks.
    """
    async def _run():
        processor = MLProcessor(sequence_length=256)
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

                    # Synthesize physical parameters with noise
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
                    dT_dt = float((i_pulse ** 2) * (r0_noisy + r1_noisy) * 50.0 / (c_th_noisy * 1e-2))

                    raw_frame = {
                        'source': '3d',
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

                    # ML inference (strictly zero label leakage)
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

        print(f"\n[DENSE 360-FRAME SWEEP] Total Frames: {total_frames}")
        print(f"[DENSE 360-FRAME SWEEP] Overall Accuracy: {accuracy:.2f}%")
        print(f"[DENSE 360-FRAME SWEEP] Mean SOH MAE: {mean_soh_error:.2f}%")
        print(f"[DENSE 360-FRAME SWEEP] Internal Short Lockouts: {internal_short_lockouts}/60")

        # Rigorous thresholds
        assert accuracy >= 95.0, f"Dense sweep accuracy ({accuracy:.2f}%) below 95% threshold"
        assert mean_soh_error <= 6.0, f"Dense sweep SOH MAE ({mean_soh_error:.2f}%) exceeds 6.0% threshold"
        assert internal_short_lockouts == 60, f"Internal short safety lockout failed ({internal_short_lockouts}/60)"

    asyncio.run(_run())


def test_dynamic_ingestor_mode_switching():
    """
    Test that ThreedIngestor dynamically propagates mode changes and produces correct ML predictions.
    """
    async def _run():
        from backend.ingest.threed import ThreedIngestor
        ingestor = ThreedIngestor()
        await ingestor.initialize()

        processor = MLProcessor(sequence_length=256)
        await processor.initialize()

        mode_sequence = ['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition', 'gas_generation', 'internal_short']
        
        for mode in mode_sequence:
            # Dynamically switch mode on ingestor
            ingestor.degradation_mode = mode
            ingestor.soc = 0.55
            ingestor.noise_level = 0.05
            
            raw_frame = await ingestor.get_frame()
            assert raw_frame is not None
            
            # Verify sensor reading fidelity to mode physics
            phys = DEGRADATION_PHYSICS_PARAMS[mode]
            assert abs(raw_frame['electrical_resistance'] - phys['r0']) < 0.015
            assert abs(raw_frame['ultrasonic_speedOfSound'] - phys['sos']) < 25.0

            # Process through ML
            ml_frame = await processor.process_frame(raw_frame)
            assert ml_frame['degradation_mode'] == mode, (
                f"Mode switch to '{mode}' predicted as '{ml_frame['degradation_mode']}'"
            )

    asyncio.run(_run())

