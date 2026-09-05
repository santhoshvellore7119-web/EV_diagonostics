#!/usr/bin/env python
"""
Unit tests for the EvidenceGenerator module.
"""

import sys
import os
import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'backend'))

from backend.evidence import EvidenceGenerator


def test_evidence_generator_init():
    """Verify evidence generator initialization and default buffer state."""
    eg = EvidenceGenerator(max_buffer_size=100)
    assert not eg.is_recording
    assert len(eg.frame_buffer) == 0


def test_evidence_recording_lifecycle():
    """Verify session recording start, frame addition, and stop lifecycle."""
    eg = EvidenceGenerator(max_buffer_size=100)
    eg.start_recording({'test_id': 'bench_01'})
    assert eg.is_recording

    # Add a mock diagnostic frame
    mock_frame = {
        'timestamp': 1000.0,
        'frameId': 'frm_001',
        'source': 'test',
        'cellId': 'cell_01',
        'electrical_voltage': 3.85,
        'stateOfHealth_value': 94.2
    }
    eg.frame_buffer.append(mock_frame)
    assert len(eg.frame_buffer) == 1

    eg.stop_recording()
    assert not eg.is_recording


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
