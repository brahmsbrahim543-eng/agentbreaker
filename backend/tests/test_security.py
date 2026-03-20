"""Tests for security middleware, honeypot routes, and input validation."""

from __future__ import annotations

import pytest

from app.core.input_validation import (
    MAX_AGENT_ID_LENGTH,
    MAX_INPUT_LENGTH,
    sanitize_text,
    validate_agent_id,
    validate_step_tokens,
)

# ===================================================================
# Security Headers
# ===================================================================

@pytest.mark.asyncio
class TestSecurityHeaders:
    async def test_security_headers_present(self, client):
        """Every response should include OWASP security headers."""
        resp = await client.get("/health")
        assert resp.status_code == 200

        headers = resp.headers
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("x-xss-protection") == "1; mode=block"
        assert "strict-origin" in headers.get("referrer-policy", "")
        assert "camera=()" in headers.get("permissions-policy", "")
        assert "no-store" in headers.get("cache-control", "")
        assert "max-age=" in headers.get("strict-transport-security", "")
        assert "default-src 'none'" in headers.get("content-security-policy", "")

    async def test_security_headers_on_api_route(self, client):
        """Security headers should also be on API error responses."""
        resp = await client.get("/api/v1/agents")  # Missing auth -> error
        headers = resp.headers
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"


# ===================================================================
# Honeypot Routes
# ===================================================================

@pytest.mark.asyncio
class TestHoneypot:
    TRAP_PATHS = [
        "/admin",
        "/wp-admin",
        "/wp-login.php",
        "/phpmyadmin",
        "/.env",
        "/.git/config",
        "/api/debug",
        "/api/internal",
        "/config.json",
        "/server-status",
        "/actuator",
        "/console",
    ]

    @pytest.mark.parametrize("path", TRAP_PATHS)
    async def test_honeypot_returns_404(self, client, path):
        """All honeypot paths should return 404 to avoid tipping off scanners."""
        resp = await client.get(path)
        assert resp.status_code == 404
        data = resp.json()
        assert data["detail"] == "Not found"

    async def test_honeypot_responds_to_post(self, client):
        """Honeypot should handle POST requests too."""
        resp = await client.post("/wp-admin")
        assert resp.status_code == 404

    async def test_honeypot_file_extension_trap(self, client):
        """File extension probes should hit the trap."""
        for ext in [".sql", ".bak", ".zip"]:
            resp = await client.get(f"/backup{ext}")
            assert resp.status_code == 404

    async def test_honeypot_logs_attempt(self, client):
        """Verify honeypot doesn't crash when handling requests.

        We can't easily inspect structlog output in tests, but we verify
        the endpoint works correctly and returns the expected response.
        """
        resp = await client.get(
            "/.env",
            headers={
                "User-Agent": "sqlmap/1.0",
                "Referer": "http://evil.com",
            },
        )
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Not found"}


# ===================================================================
# Input Validation
# ===================================================================

class TestInputValidation:
    def test_sanitize_text_none(self):
        assert sanitize_text(None) == ""

    def test_sanitize_text_empty(self):
        assert sanitize_text("") == ""

    def test_sanitize_text_normal(self):
        assert sanitize_text("Hello world") == "Hello world"

    def test_sanitize_text_truncates_long_text(self):
        long_text = "a" * (MAX_INPUT_LENGTH + 1000)
        result = sanitize_text(long_text)
        assert len(result) == MAX_INPUT_LENGTH

    def test_sanitize_text_strips_control_characters(self):
        text = "Hello\x00World\x01Test\x0b"
        result = sanitize_text(text)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x0b" not in result
        assert "Hello" in result

    def test_sanitize_text_preserves_newlines_and_tabs(self):
        text = "Line1\nLine2\tTabbed\rReturn"
        result = sanitize_text(text)
        assert "\n" in result
        assert "\t" in result
        assert "\r" in result

    def test_validate_agent_id_valid(self):
        assert validate_agent_id("agent-001") == "agent-001"
        assert validate_agent_id("my.agent.v2") == "my.agent.v2"
        assert validate_agent_id("Agent_123") == "Agent_123"

    def test_validate_agent_id_rejects_empty(self):
        with pytest.raises(ValueError, match="between 1 and"):
            validate_agent_id("")

    def test_validate_agent_id_rejects_too_long(self):
        long_id = "a" * (MAX_AGENT_ID_LENGTH + 1)
        with pytest.raises(ValueError, match="between 1 and"):
            validate_agent_id(long_id)

    def test_validate_agent_id_rejects_bad_characters(self):
        with pytest.raises(ValueError, match="alphanumeric"):
            validate_agent_id("agent id with spaces")
        with pytest.raises(ValueError, match="alphanumeric"):
            validate_agent_id("agent;drop table")
        with pytest.raises(ValueError, match="alphanumeric"):
            validate_agent_id("-starts-with-dash")

    def test_validate_agent_id_rejects_special_injection(self):
        """SQL injection and path traversal attempts should be rejected."""
        bad_ids = [
            "'; DROP TABLE agents; --",
            "../../../etc/passwd",
            "agent<script>alert(1)</script>",
            "agent\x00null",
        ]
        for bad_id in bad_ids:
            with pytest.raises(ValueError):
                validate_agent_id(bad_id)

    def test_validate_step_tokens_valid(self):
        assert validate_step_tokens(0) == 0
        assert validate_step_tokens(1000) == 1000
        assert validate_step_tokens(100_000) == 100_000

    def test_validate_step_tokens_rejects_negative(self):
        with pytest.raises(ValueError, match="negative"):
            validate_step_tokens(-1)

    def test_validate_step_tokens_rejects_too_large(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_step_tokens(100_001)


# ===================================================================
# Request Size Limit
# ===================================================================

@pytest.mark.asyncio
class TestRequestSizeLimit:
    async def test_oversized_request_rejected(self, client):
        """Requests with Content-Length > 10MB should be rejected."""
        resp = await client.post(
            "/api/v1/auth/register",
            content=b"x" * 100,  # Small body, but with spoofed header
            headers={"Content-Length": str(11 * 1024 * 1024), "Content-Type": "application/json"},
        )
        assert resp.status_code == 413
