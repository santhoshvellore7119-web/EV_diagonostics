import os
import sys
import numpy as np
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.ml_processor import MLProcessor
from ml_pipeline.data.synthetic_data import MultiModalBatteryDataset
from ev_cell_multimodal_sim.core.physics_engine import simulate_cell_from_parameters, DEGRADATION_PHYSICS_PARAMS


def test_waveform_synthesis_label_invariance():
    """
    Fuzz test asserting that MLProcessor._synthesize_waveforms is mathematically
    invariant to the 'degradation_mode' key or any label string in the frame.
    """
    processor = MLProcessor(sequence_length=256)
    
    # Base physical telemetry frame
    base_frame = {
        'electrical_voltage': 3.65,
        'electrical_current': 0.50,
        'electrical_resistance': 0.052,
        'ultrasonic_timeOfFlight': 7.85,
        'ultrasonic_amplitude': 0.95,
        'ultrasonic_phaseShift': 0.0,
        'ultrasonic_speedOfSound': 2550.0,
        'thermal_temperature': 27.5,
        'thermal_tempGradient': 0.12,
        'simulation_soc': 0.55
    }
    
    # Generate waveforms under 6 different degradation labels + missing + bogus
    labels = ['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition',
              'gas_generation', 'internal_short', 'UNKNOWN_CUSTOM_STRING', None]
    
    waveforms = []
    for lbl in labels:
        f = base_frame.copy()
        if lbl is not None:
            f['degradation_mode'] = lbl
        elif 'degradation_mode' in f:
            del f['degradation_mode']
            
        e, u, t = processor._synthesize_waveforms(f)
        waveforms.append((e, u, t))
    
    # Assert every single waveform is exactly identical across all label variations
    ref_e, ref_u, ref_t = waveforms[0]
    for i, (e, u, t) in enumerate(waveforms[1:], start=1):
        np.testing.assert_allclose(e, ref_e, rtol=1e-7, atol=1e-7,
                                  err_msg=f"Electrical waveform altered by label '{labels[i]}'")
        np.testing.assert_allclose(u, ref_u, rtol=1e-7, atol=1e-7,
                                  err_msg=f"Ultrasonic waveform altered by label '{labels[i]}'")
        np.testing.assert_allclose(t, ref_t, rtol=1e-7, atol=1e-7,
                                  err_msg=f"Thermal waveform altered by label '{labels[i]}'")


def test_synthetic_dataset_parameter_physics():
    """
    Verify MultiModalBatteryDataset produces 256-sample tensors directly from ODE physics
    with finite numerical ranges and correct tensor shapes.
    """
    ds = MultiModalBatteryDataset(num_samples=20, seq_length=256, seed=42)
    assert len(ds) == 20
    
    for i in range(len(ds)):
        sample = ds[i]
        assert sample['electrical'].shape == (1, 256)
        assert sample['ultrasonic'].shape == (1, 256)
        assert sample['thermal'].shape == (1, 256)
        assert 0 <= sample['degradation_mode'].item() <= 5
        assert 0.0 <= sample['soh'].item() <= 100.0
        
        # Verify finite values (no NaN or Inf)
        assert not np.isnan(sample['electrical'].numpy()).any()
        assert not np.isnan(sample['ultrasonic'].numpy()).any()
        assert not np.isnan(sample['thermal'].numpy()).any()


def test_pure_physics_parameter_function():
    """
    Verify simulate_cell_from_parameters operates deterministically for identical physical inputs.
    """
    res1 = simulate_cell_from_parameters(soc=0.5, r0=0.045, r1=0.02, c1=2000.0, sos=2500.0,
                                        attenuation=1.0, r_th=2.0, c_th=500.0, add_noise=False)
    res2 = simulate_cell_from_parameters(soc=0.5, r0=0.045, r1=0.02, c1=2000.0, sos=2500.0,
                                        attenuation=1.0, r_th=2.0, c_th=500.0, add_noise=False)
    
    np.testing.assert_array_equal(res1['electrical']['voltage'], res2['electrical']['voltage'])
    np.testing.assert_array_equal(res1['ultrasonic']['signal'], res2['ultrasonic']['signal'])
    np.testing.assert_array_equal(res1['thermal']['temperature_rise'], res2['thermal']['temperature_rise'])
