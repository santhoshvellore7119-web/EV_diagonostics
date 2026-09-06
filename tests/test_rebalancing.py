#!/usr/bin/env python
"""
Unit tests for the RebalancingProcessor module.
"""

import sys
import os
import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'backend'))

from backend.rebalancing import RebalancingProcessor


def test_rebalancing_processor_init():
    """Verify RebalancingProcessor initialization."""
    rp = RebalancingProcessor()
    assert rp.decision_engine is not None


def test_rebalancing_processor_frame_handling():
    """Verify processing diagnostic frames with ML inference outputs."""
    rp = RebalancingProcessor()
    enhanced_frame = {
        'degradation_mode_idx': 1,  # Li plating
        'degradation_prob': 0.92,
        'soh': 82.5,
        'cell_id': 'CELL-01'
    }
    result = rp.process_frame(enhanced_frame)
    assert result is not None
    assert 'rebalancing_state' in result or 'state' in result or 'selected_action' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
