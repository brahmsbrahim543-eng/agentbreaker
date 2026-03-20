"""Unit tests for the AgentBreaker Python SDK client."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import json as json_mod

import httpx

from agentbreaker import AgentBreaker, AgentBreakerAPIError, AgentKilledError
from agentbreaker.types import StepResult

_FAKE_REQUEST = httpx.Request("POST", "http://test/api/v1/ingest/step")


def _make_response(status_code: int, json_data: dict | None = None, text: str = "") -> httpx.Response:
    """Build a fake httpx.Response for testing."""
    if json_data is not None:
        content = json_mod.dumps(json_data).encode()
        headers = {"content-type": "application/json"}
    else:
        content = text.encode()
        headers = {"content-type": "text/plain"}
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers=headers,
        request=_FAKE_REQUEST,
    )


class TestTrackStepOk(unittest.TestCase):
    """track_step returns a StepResult when the API responds with action=ok."""

    def test_returns_step_result(self) -> None:
        response_body = {
            "step_number": 1,
            "risk_score": 0.15,
            "risk_breakdown": {"loop": 0.1, "cost": 0.05},
            "action": "ok",
            "warnings": [],
            "carbon_impact": {
                "kwh": 0.0001,
                "co2_grams": 0.05,
                "total_kwh": 0.0003,
                "total_co2_grams": 0.15,
            },
        }

        with patch.object(
            httpx.Client, "post", return_value=_make_response(200, response_body)
        ):
            ab = AgentBreaker(api_key="ab_test_key")
            result = ab.track_step(
                agent_id="agent-1",
                input="hello",
                output="world",
                tokens=100,
                cost=0.003,
                tool="search",
                duration_ms=200,
                context_size=4096,
            )

        self.assertIsInstance(result, StepResult)
        self.assertEqual(result.step_number, 1)
        self.assertAlmostEqual(result.risk_score, 0.15)
        self.assertEqual(result.action, "ok")
        self.assertEqual(result.risk_breakdown, {"loop": 0.1, "cost": 0.05})
        self.assertIsNotNone(result.carbon_impact)
        ab.close()


class TestTrackStepKill(unittest.TestCase):
    """track_step raises AgentKilledError when the API responds with action=kill."""

    def test_raises_agent_killed(self) -> None:
        response_body = {
            "step_number": 42,
            "risk_score": 0.95,
            "risk_breakdown": {"loop": 0.9, "cost": 0.8},
            "action": "kill",
            "warnings": ["Infinite loop detected: repeated output 10 times"],
            "carbon_impact": {"kwh": 0.01, "co2_grams": 5.0, "total_kwh": 0.1, "total_co2_grams": 50.0},
        }

        with patch.object(
            httpx.Client, "post", return_value=_make_response(200, response_body)
        ):
            ab = AgentBreaker(api_key="ab_test_key")
            with self.assertRaises(AgentKilledError) as ctx:
                ab.track_step(
                    agent_id="agent-2",
                    input="do something",
                    output="doing it again",
                    tokens=500,
                    cost=0.05,
                )

        err = ctx.exception
        self.assertEqual(err.agent_id, "agent-2")
        self.assertIn("Infinite loop", err.reason)
        self.assertAlmostEqual(err.risk_score, 0.95)
        self.assertAlmostEqual(err.co2_avoided, 5.0)
        self.assertIn("agent-2", str(err))
        self.assertIn("Saved $", str(err))
        ab.close()


class TestTrackStepRetry(unittest.TestCase):
    """track_step retries on transient transport errors."""

    @patch("agentbreaker.client.time.sleep")
    def test_retries_on_transport_error(self, mock_sleep: MagicMock) -> None:
        ok_response = _make_response(
            200,
            {
                "step_number": 1,
                "risk_score": 0.1,
                "risk_breakdown": {},
                "action": "ok",
                "warnings": [],
            },
        )

        call_count = 0
        original_post = httpx.Client.post

        def flaky_post(self_client: httpx.Client, *args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise httpx.ConnectError("Connection refused")
            return ok_response

        with patch.object(httpx.Client, "post", flaky_post):
            ab = AgentBreaker(api_key="ab_test_key")
            result = ab.track_step(
                agent_id="agent-3",
                input="retry me",
                output="ok",
                tokens=10,
                cost=0.001,
            )

        self.assertEqual(result.action, "ok")
        self.assertEqual(call_count, 3)
        # Verify backoff sleeps happened (2^0=1, 2^1=2)
        self.assertEqual(mock_sleep.call_count, 2)
        ab.close()

    @patch("agentbreaker.client.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep: MagicMock) -> None:
        with patch.object(
            httpx.Client,
            "post",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            ab = AgentBreaker(api_key="ab_test_key")
            with self.assertRaises(AgentBreakerAPIError) as ctx:
                ab.track_step(
                    agent_id="agent-4",
                    input="fail",
                    output="fail",
                    tokens=10,
                    cost=0.001,
                )

        self.assertEqual(ctx.exception.status_code, 0)
        self.assertIn("3 attempts", ctx.exception.message)
        ab.close()


class TestAPIError(unittest.TestCase):
    """track_step raises AgentBreakerAPIError on non-200 responses."""

    def test_401_unauthorized(self) -> None:
        with patch.object(
            httpx.Client,
            "post",
            return_value=_make_response(401, text="Invalid API key"),
        ):
            ab = AgentBreaker(api_key="ab_test_bad_key")
            with self.assertRaises(AgentBreakerAPIError) as ctx:
                ab.track_step(
                    agent_id="agent-5",
                    input="test",
                    output="test",
                    tokens=10,
                    cost=0.001,
                )

        self.assertEqual(ctx.exception.status_code, 401)
        ab.close()

    def test_500_server_error(self) -> None:
        with patch.object(
            httpx.Client,
            "post",
            return_value=_make_response(500, text="Internal server error"),
        ):
            ab = AgentBreaker(api_key="ab_test_key")
            with self.assertRaises(AgentBreakerAPIError) as ctx:
                ab.track_step(
                    agent_id="agent-6",
                    input="test",
                    output="test",
                    tokens=10,
                    cost=0.001,
                )

        self.assertEqual(ctx.exception.status_code, 500)
        ab.close()


class TestClientLifecycle(unittest.TestCase):
    """Context manager and close() work correctly."""

    def test_context_manager(self) -> None:
        with AgentBreaker(api_key="ab_test_key") as ab:
            self.assertIsNotNone(ab._client)

    def test_empty_api_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgentBreaker(api_key="")

    def test_base_url_trailing_slash_stripped(self) -> None:
        ab = AgentBreaker(api_key="ab_test_key", base_url="http://localhost:8000/")
        self.assertEqual(ab.base_url, "http://localhost:8000")
        ab.close()


if __name__ == "__main__":
    unittest.main()
