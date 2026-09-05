#!/usr/bin/env python
"""
Unit tests for data ingestion modules (3D, Gazebo, Simulink, Firmware).
"""

import sys
import os
import pytest
import asyncio

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'backend'))

from backend.ingest.threed import ThreedIngestor
from backend.ingest.gazebo import GazeboIngestor
from backend.ingest.simulink import SimulinkIngestor
from backend.ingest.firmware import FirmwareIngestor
from backend.ml_processor import MLProcessor


def test_threed_ingestor_step():
    """Verify 3D ingestor generates structured diagnostic frames."""
    async def _run():
        ingestor = ThreedIngestor()
        await ingestor.initialize()
        frame = await ingestor.get_frame()
        assert frame is not None
        assert 'timestamp' in frame
        assert 'electrical_voltage' in frame
        assert 'ultrasonic_timeOfFlight' in frame
        assert 'thermal_temperature' in frame
    asyncio.run(_run())


def test_gazebo_ingestor_step():
    """Verify Gazebo bridge ingestor generates multi-physics frames."""
    async def _run():
        ingestor = GazeboIngestor()
        await ingestor.initialize()
        frame = await ingestor.get_frame()
        assert frame is not None
        assert 'timestamp' in frame
        assert 'electrical_voltage' in frame
    asyncio.run(_run())


def test_simulink_ingestor_step():
    """Verify Simulink ingestor generates physical diagnostic frames."""
    async def _run():
        ingestor = SimulinkIngestor(fmu_path="", soc=0.7, excitation_amplitude=0.5, degradation_mode="li_plating")
        await ingestor.initialize()
        frame = await ingestor.step()
        assert frame is not None
        assert 'timestamp' in frame
        assert 'electrical_voltage' in frame
        assert 'ultrasonic_phaseShift' in frame
        assert frame['degradation_mode'] == 'li_plating'
    asyncio.run(_run())


def test_firmware_ingestor_init():
    """Verify Firmware ingestor initialization."""
    ingestor = FirmwareIngestor()
    assert ingestor is not None
    assert not ingestor.is_connected


def test_all_ingestors_multimodal_live_diagnostic_accuracy():
    """Verify all ingestor sources produce signals classified accurately by MLProcessor."""
    async def _run():
        ml_proc = MLProcessor()
        await ml_proc.initialize()

        modes = [
            'healthy', 'li_plating', 'active_material_loss',
            'electrolyte_decomposition', 'gas_generation', 'internal_short'
        ]

        # 1. Test ThreedIngestor across all modes
        threed_correct = 0
        for mode in modes:
            ingestor = ThreedIngestor(degradation_mode=mode, soc=0.6, noise_level=0.02)
            await ingestor.initialize()
            frame = await ingestor.get_frame()
            processed = await ml_proc.process_frame(frame)
            if processed.get('degradation_mode') == mode:
                threed_correct += 1
        assert threed_correct == len(modes), f"ThreedIngestor accuracy {threed_correct}/{len(modes)}"

        # 2. Test GazeboIngestor across all modes
        gazebo_correct = 0
        for mode in modes:
            ingestor = GazeboIngestor(degradation_mode=mode, soc=0.6, noise_level=0.02)
            await ingestor.initialize()
            frame = await ingestor.get_frame()
            processed = await ml_proc.process_frame(frame)
            if processed.get('degradation_mode') == mode:
                gazebo_correct += 1
        assert gazebo_correct == len(modes), f"GazeboIngestor accuracy {gazebo_correct}/{len(modes)}"

        # 3. Test SimulinkIngestor across all modes
        simulink_correct = 0
        for mode in modes:
            ingestor = SimulinkIngestor(fmu_path="", soc=0.6, excitation_amplitude=0.5, degradation_mode=mode, noise_level=0.02)
            await ingestor.initialize()
            frame = await ingestor.step()
            processed = await ml_proc.process_frame(frame)
            if processed.get('degradation_mode') == mode:
                simulink_correct += 1
        assert simulink_correct == len(modes), f"SimulinkIngestor accuracy {simulink_correct}/{len(modes)}"

    asyncio.run(_run())


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
