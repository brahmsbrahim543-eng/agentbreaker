"""Tests for the incidents API endpoints (list, detail, stats)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio

from app.detection.base import DetectionResult

pytestmark = pytest.mark.asyncio


def _mock_model():
    mock = MagicMock()
    def _encode(texts, convert_to_numpy=True):
        return np.random.rand(len(texts), 384).astype(np.float32)
    mock.encode = _encode
    return mock


async def _mock_analyze_step_kill(steps, thresholds=None):
    """Replacement for DetectionEngine.analyze_step that always returns kill."""
    return {
        "score": 95.0,
        "action": "kill",
        "breakdown": {
            "similarity": 90.0,
            "reasoning_loop": 90.0,
            "error_cascade": 95.0,
            "diminishing_returns": 85.0,
            "goal_drift": 80.0,
            "token_entropy": 75.0,
            "cost_velocity": 70.0,
            "context_inflation": 65.0,
            "composite": 95.0,
        },
        "warnings": ["Forced high score for testing"],
        "flags": ["error_cascade"],
    }


@pytest_asyncio.fixture
async def incidents_setup(client):
    """Set up org, project, API key, and generate incidents by forcing kills."""
    reg_resp = await client.post("/api/v1/auth/register", json={
        "org_name": "Incident Test Org",
        "email": "incidents@test.com",
        "password": "SecurePass123!",
    })
    token = reg_resp.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    proj_resp = await client.post("/api/v1/projects", json={
        "name": "Incident Project",
    }, headers=auth)
    project_id = proj_resp.json()["id"]

    key_resp = await client.post(f"/api/v1/projects/{project_id}/api-keys", json={
        "name": "Incident Key",
    }, headers=auth)
    api_key = key_resp.json()["key"]
    api_headers = {"X-API-Key": api_key}

    # Patch the detection engine's analyze_step to always return kill
    with patch("app.services.ingest._engine.analyze_step", side_effect=_mock_analyze_step_kill):
        for agent_id in ["kill-agent-1", "kill-agent-2"]:
            resp = await client.post("/api/v1/ingest/step", json={
                "agent_id": agent_id,
                "input": "do something",
                "output": "failed miserably",
                "tokens": 200,
                "cost": 0.05,
                "error_message": "Timeout",
            }, headers=api_headers)
            assert resp.status_code == 200
            assert resp.json()["action"] == "kill"

    return {"auth": auth, "api_headers": api_headers, "project_id": project_id}


class TestListIncidents:
    async def test_list_incidents(self, client, incidents_setup):
        resp = await client.get("/api/v1/incidents", headers=incidents_setup["auth"])
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2  # We created 2 kill incidents
        assert len(data["items"]) >= 2

        # Verify incident structure
        incident = data["items"][0]
        assert "id" in incident
        assert "agent_id" in incident
        assert "agent_name" in incident
        assert "incident_type" in incident
        assert "risk_score_at_kill" in incident
        assert "cost_avoided" in incident
        assert "co2_avoided_grams" in incident
        assert "steps_at_kill" in incident
        assert "created_at" in incident

    async def test_list_incidents_filter_by_type(self, client, incidents_setup):
        resp = await client.get(
            "/api/v1/incidents?incident_type=error_cascade",
            headers=incidents_setup["auth"],
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["incident_type"] == "error_cascade"

    async def test_list_incidents_without_auth_fails(self, client):
        resp = await client.get("/api/v1/incidents")
        assert resp.status_code == 422


class TestGetIncidentDetail:
    async def test_get_incident_detail_with_snapshot(self, client, incidents_setup):
        # First list to get an incident ID
        list_resp = await client.get("/api/v1/incidents", headers=incidents_setup["auth"])
        incident_id = list_resp.json()["items"][0]["id"]

        resp = await client.get(
            f"/api/v1/incidents/{incident_id}",
            headers=incidents_setup["auth"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == incident_id
        assert "snapshot" in data
        assert isinstance(data["snapshot"], dict)
        assert "kill_reason_detail" in data

    async def test_get_incident_not_found(self, client, incidents_setup):
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/incidents/{fake_id}",
            headers=incidents_setup["auth"],
        )
        assert resp.status_code == 404


class TestIncidentStats:
    async def test_incident_stats_aggregation(self, client, incidents_setup):
        resp = await client.get(
            "/api/v1/incidents/stats",
            headers=incidents_setup["auth"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_count" in data
        assert data["total_count"] >= 2
        assert "by_type" in data
        assert isinstance(data["by_type"], dict)
        assert "total_cost_avoided" in data
        assert data["total_cost_avoided"] >= 0
        assert "total_co2_avoided_grams" in data
        assert data["total_co2_avoided_grams"] >= 0

    async def test_incident_stats_empty_org(self, client):
        """A fresh org with no incidents should return zero stats."""
        reg_resp = await client.post("/api/v1/auth/register", json={
            "org_name": "Empty Org",
            "email": "empty@test.com",
            "password": "SecurePass123!",
        })
        token = reg_resp.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        resp = await client.get("/api/v1/incidents/stats", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 0
        assert data["total_cost_avoided"] == 0
        assert data["total_co2_avoided_grams"] == 0
        assert data["by_type"] == {}
