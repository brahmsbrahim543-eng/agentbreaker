"""Tests for the agents API endpoints (list, detail)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


def _mock_model():
    mock = MagicMock()
    def _encode(texts, convert_to_numpy=True):
        return np.random.rand(len(texts), 384).astype(np.float32)
    mock.encode = _encode
    return mock


@pytest_asyncio.fixture
async def agents_setup(client):
    """Register, create project, create API key, ingest several agents."""
    reg_resp = await client.post("/api/v1/auth/register", json={
        "org_name": "Agent Test Org",
        "email": "agents@test.com",
        "password": "SecurePass123!",
    })
    token = reg_resp.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    proj_resp = await client.post("/api/v1/projects", json={
        "name": "Agent Project",
    }, headers=auth)
    project_id = proj_resp.json()["id"]

    key_resp = await client.post(f"/api/v1/projects/{project_id}/api-keys", json={
        "name": "Agent Key",
    }, headers=auth)
    api_key = key_resp.json()["key"]
    api_headers = {"X-API-Key": api_key}

    # Ingest steps for multiple agents
    with patch("app.detection.similarity._get_model", return_value=_mock_model()):
        with patch("app.detection.goal_drift._get_model", return_value=_mock_model()):
            for agent_id in ["agent-alpha", "agent-beta", "agent-gamma"]:
                for i in range(3):
                    await client.post("/api/v1/ingest/step", json={
                        "agent_id": agent_id,
                        "input": f"Task {i}",
                        "output": f"Result {i} from {agent_id}",
                        "tokens": 100 + i * 50,
                        "cost": 0.01 + i * 0.005,
                    }, headers=api_headers)

    return {"auth": auth, "api_headers": api_headers, "project_id": project_id}


class TestListAgents:
    async def test_list_agents_returns_data(self, client, agents_setup):
        resp = await client.get("/api/v1/agents", headers=agents_setup["auth"])
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 3
        assert len(data["items"]) == 3

        # Verify agent structure
        agent = data["items"][0]
        assert "id" in agent
        assert "external_id" in agent
        assert "status" in agent
        assert "current_risk_score" in agent
        assert "total_cost" in agent
        assert "total_steps" in agent

    async def test_list_agents_filters_by_status(self, client, agents_setup):
        # Get all agents to find what statuses exist
        all_resp = await client.get("/api/v1/agents", headers=agents_setup["auth"])
        all_agents = all_resp.json()["items"]
        assert len(all_agents) >= 1

        # Pick an existing status to filter by
        existing_status = all_agents[0]["status"]
        expected_count = sum(1 for a in all_agents if a["status"] == existing_status)

        resp = await client.get(
            f"/api/v1/agents?status={existing_status}",
            headers=agents_setup["auth"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == expected_count
        for agent in data["items"]:
            assert agent["status"] == existing_status

        # A status that no agent has should return zero
        resp_idle = await client.get(
            "/api/v1/agents?status=idle",
            headers=agents_setup["auth"],
        )
        assert resp_idle.status_code == 200
        assert resp_idle.json()["total"] == 0

    async def test_list_agents_pagination(self, client, agents_setup):
        resp = await client.get(
            "/api/v1/agents?per_page=2&page=1",
            headers=agents_setup["auth"],
        )
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["per_page"] == 2

        resp2 = await client.get(
            "/api/v1/agents?per_page=2&page=2",
            headers=agents_setup["auth"],
        )
        data2 = resp2.json()
        assert len(data2["items"]) == 1

    async def test_list_agents_without_auth_fails(self, client):
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 422  # Missing Authorization header


class TestGetAgentDetail:
    async def test_get_agent_detail(self, client, agents_setup):
        # First get the list to find an agent ID
        list_resp = await client.get("/api/v1/agents", headers=agents_setup["auth"])
        agent_id = list_resp.json()["items"][0]["id"]

        resp = await client.get(
            f"/api/v1/agents/{agent_id}",
            headers=agents_setup["auth"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == agent_id
        assert "recent_steps" in data
        assert len(data["recent_steps"]) > 0

        # Check step structure
        step = data["recent_steps"][0]
        assert "step_number" in step
        assert "tokens_used" in step
        assert "cost" in step

    async def test_get_agent_not_found(self, client, agents_setup):
        import uuid
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/agents/{fake_id}",
            headers=agents_setup["auth"],
        )
        assert resp.status_code == 404

    async def test_get_agent_invalid_uuid(self, client, agents_setup):
        resp = await client.get(
            "/api/v1/agents/not-a-uuid",
            headers=agents_setup["auth"],
        )
        assert resp.status_code == 422
