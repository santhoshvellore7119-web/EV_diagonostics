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
from backend.ingest.firmware import FirmwareIngestor


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


def test_firmware_ingestor_init():
    """Verify Firmware ingestor initialization."""
    ingestor = FirmwareIngestor()
    assert ingestor is not None
    assert not ingestor.is_connected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
