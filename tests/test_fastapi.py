#!/usr/bin/env python
"""
Unit tests for FastAPI backend routes and diagnostic frame endpoints.
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'backend'))

from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_root_endpoint(client):
    """Test health check / root status endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data or "message" in data or "name" in data or "version" in data


def test_status_endpoint(client):
    """Test backend status API."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "active_mode" in data


def test_frames_historical(client):
    """Test historical frames endpoint."""
    response = client.get("/api/frames/historical?start=0")
    assert response.status_code == 200
    data = response.json()
    assert "frames" in data
    assert "count" in data


def test_mode_management(client):
    """Test mode switching endpoint."""
    response = client.get("/api/mode/current")
    assert response.status_code == 200
    assert "mode" in response.json()

    # Switch mode to 3d
    set_res = client.post("/api/mode/set?mode=3d")
    assert set_res.status_code == 200
    assert set_res.json()["mode"] == "3d"


def test_gazebo_endpoints(client):
    """Test Gazebo viewer HTML delivery and open redirect API."""
    res_page = client.get("/gazebo")
    assert res_page.status_code == 200
    assert "Diagnostic Machine" in res_page.text or "3D Studio" in res_page.text

    res_api = client.get("/api/gazebo/open")
    assert res_api.status_code == 200
    data = res_api.json()
    assert data["status"] == "success"
    assert data["url"] == "/gazebo"


def test_simulink_open_endpoint(client):
    """Test MATLAB Simulink open launcher endpoint."""
    res = client.post("/api/simulink/open")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "ev_cell_digital_twin" in data["model_name"]
    assert "launch_script" in data
    assert "matlab_command" in data

