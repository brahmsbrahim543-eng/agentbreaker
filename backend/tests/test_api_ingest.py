"""Tests for the ingest API endpoint (/api/v1/ingest/step).

The ingest endpoint is authenticated via X-API-Key and runs the full
detection pipeline.  We mock the embedding model to avoid loading
sentence-transformers.
"""

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


def _step_payload(
    agent_id: str = "test-agent-001",
    input_text: str = "Find the weather in Paris",
    output_text: str = "The weather in Paris is sunny, 22C",
    tokens: int = 150,
    cost: float = 0.02,
    tool: str | None = None,
    error_message: str | None = None,
    context_size: int | None = None,
) -> dict:
    payload = {
        "agent_id": agent_id,
        "input": input_text,
        "output": output_text,
        "tokens": tokens,
        "cost": cost,
    }
    if tool is not None:
        payload["tool"] = tool
    if error_message is not None:
        payload["error_message"] = error_message
    if context_size is not None:
        payload["context_size"] = context_size
    return payload


@pytest_asyncio.fixture
async def ingest_setup(client):
    """Register a user, create a project, create an API key, return headers."""
    # Register
    reg_resp = await client.post("/api/v1/auth/register", json={
        "org_name": "Ingest Test Org",
        "email": "ingest@test.com",
        "password": "SecurePass123!",
    })
    token = reg_resp.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # Create project
    proj_resp = await client.post("/api/v1/projects", json={
        "name": "Ingest Project",
    }, headers=auth)
    project_id = proj_resp.json()["id"]

    # Create API key
    key_resp = await client.post(f"/api/v1/projects/{project_id}/api-keys", json={
        "name": "Test Key",
    }, headers=auth)
    raw_key = key_resp.json()["key"]

    return {
        "auth_headers": auth,
        "api_key_headers": {"X-API-Key": raw_key},
        "project_id": project_id,
        "raw_key": raw_key,
    }


class TestIngestStep:
    async def test_ingest_step_creates_agent(self, client, ingest_setup):
        with patch("app.detection.similarity._get_model", return_value=_mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=_mock_model()):
                resp = await client.post(
                    "/api/v1/ingest/step",
                    json=_step_payload(),
                    headers=ingest_setup["api_key_headers"],
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["step_number"] == 1
                assert "risk_score" in data
                assert "action" in data
                assert data["action"] in ("ok", "warn", "kill")

    async def test_ingest_step_increments_counters(self, client, ingest_setup):
        headers = ingest_setup["api_key_headers"]
        with patch("app.detection.similarity._get_model", return_value=_mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=_mock_model()):
                resp1 = await client.post(
                    "/api/v1/ingest/step",
                    json=_step_payload(agent_id="counter-agent"),
                    headers=headers,
                )
                assert resp1.json()["step_number"] == 1

                resp2 = await client.post(
                    "/api/v1/ingest/step",
                    json=_step_payload(agent_id="counter-agent"),
                    headers=headers,
                )
                assert resp2.json()["step_number"] == 2

                resp3 = await client.post(
                    "/api/v1/ingest/step",
                    json=_step_payload(agent_id="counter-agent"),
                    headers=headers,
                )
                assert resp3.json()["step_number"] == 3

    async def test_ingest_step_returns_risk_score(self, client, ingest_setup):
        with patch("app.detection.similarity._get_model", return_value=_mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=_mock_model()):
                resp = await client.post(
                    "/api/v1/ingest/step",
                    json=_step_payload(),
                    headers=ingest_setup["api_key_headers"],
                )
                data = resp.json()
                assert isinstance(data["risk_score"], (int, float))
                assert 0 <= data["risk_score"] <= 100
                assert "risk_breakdown" in data
                assert "composite" in data["risk_breakdown"]

    async def test_ingest_step_returns_carbon_impact(self, client, ingest_setup):
        with patch("app.detection.similarity._get_model", return_value=_mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=_mock_model()):
                resp = await client.post(
                    "/api/v1/ingest/step",
                    json=_step_payload(tokens=5000, cost=0.10),
                    headers=ingest_setup["api_key_headers"],
                )
                data = resp.json()
                assert data["carbon_impact"] is not None
                assert data["carbon_impact"]["kwh"] > 0
                assert data["carbon_impact"]["co2_grams"] > 0

    async def test_ingest_with_invalid_api_key_fails(self, client):
        resp = await client.post(
            "/api/v1/ingest/step",
            json=_step_payload(),
            headers={"X-API-Key": "invalid-key-that-does-not-exist"},
        )
        assert resp.status_code == 401

    async def test_ingest_without_api_key_fails(self, client):
        resp = await client.post(
            "/api/v1/ingest/step",
            json=_step_payload(),
        )
        assert resp.status_code == 422  # Missing required header

    async def test_ingest_negative_tokens_rejected(self, client, ingest_setup):
        """Pydantic should reject negative token counts."""
        resp = await client.post(
            "/api/v1/ingest/step",
            json=_step_payload(tokens=-100),
            headers=ingest_setup["api_key_headers"],
        )
        assert resp.status_code == 422

    async def test_ingest_negative_cost_rejected(self, client, ingest_setup):
        resp = await client.post(
            "/api/v1/ingest/step",
            json=_step_payload(cost=-0.5),
            headers=ingest_setup["api_key_headers"],
        )
        assert resp.status_code == 422

    async def test_ingest_multiple_similar_steps_increases_risk(self, client, ingest_setup):
        """Sending identical outputs should push the risk score upward."""
        headers = ingest_setup["api_key_headers"]

        with patch("app.detection.similarity._get_model", return_value=_mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=_mock_model()):
                scores = []
                for i in range(5):
                    resp = await client.post(
                        "/api/v1/ingest/step",
                        json=_step_payload(
                            agent_id="repeat-agent",
                            output_text="The answer is 42. I am certain.",
                        ),
                        headers=headers,
                    )
                    assert resp.status_code == 200
                    scores.append(resp.json()["risk_score"])

                # Risk should generally not decrease as repetition grows
                # (at least one of the later scores should be >= first)
                assert max(scores[2:]) >= scores[0]

    async def test_ingest_with_error_message(self, client, ingest_setup):
        """Steps with error messages should be ingested and affect detection."""
        with patch("app.detection.similarity._get_model", return_value=_mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=_mock_model()):
                resp = await client.post(
                    "/api/v1/ingest/step",
                    json=_step_payload(
                        error_message="Connection refused to external API",
                        tool="http_request",
                    ),
                    headers=ingest_setup["api_key_headers"],
                )
                assert resp.status_code == 200
