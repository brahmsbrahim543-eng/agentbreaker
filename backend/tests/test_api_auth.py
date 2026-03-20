"""Tests for authentication API endpoints (register, login, me)."""

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


class TestRegister:
    async def test_register_creates_org_and_user(self, client):
        resp = await client.post("/api/v1/auth/register", json={
            "org_name": "Acme Corp",
            "email": "founder@acme.com",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20

    async def test_register_duplicate_email_fails(self, client):
        # First registration succeeds
        payload = {
            "org_name": "First Org",
            "email": "dup@example.com",
            "password": "SecurePass123!",
        }
        resp1 = await client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        # Second registration with same email fails
        payload["org_name"] = "Second Org"
        resp2 = await client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 422
        assert "already registered" in resp2.json()["message"].lower()

    async def test_register_short_password_rejected(self, client):
        resp = await client.post("/api/v1/auth/register", json={
            "org_name": "Test Org",
            "email": "short@test.com",
            "password": "abc",  # Too short
        })
        assert resp.status_code == 422  # Pydantic validation error

    async def test_register_invalid_email_rejected(self, client):
        resp = await client.post("/api/v1/auth/register", json={
            "org_name": "Test Org",
            "email": "not-an-email",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 422

    async def test_register_missing_org_name_rejected(self, client):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "test@test.com",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 422


class TestLogin:
    async def _register(self, client, email="login@test.com", password="SecurePass123!"):
        """Helper: register a user and return the response."""
        return await client.post("/api/v1/auth/register", json={
            "org_name": "Login Test Org",
            "email": email,
            "password": password,
        })

    async def test_login_success(self, client):
        await self._register(client)
        resp = await client.post("/api/v1/auth/login", json={
            "email": "login@test.com",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client):
        await self._register(client, email="wrongpw@test.com")
        resp = await client.post("/api/v1/auth/login", json={
            "email": "wrongpw@test.com",
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401
        assert "invalid" in resp.json()["message"].lower()

    async def test_login_nonexistent_email(self, client):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@nowhere.com",
            "password": "Whatever123!",
        })
        assert resp.status_code == 401

    async def test_login_returns_valid_token_for_me(self, client):
        """End-to-end: register -> login -> /me works."""
        await self._register(client, email="e2e@test.com")
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "e2e@test.com",
            "password": "SecurePass123!",
        })
        token = login_resp.json()["access_token"]

        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "e2e@test.com"


class TestMe:
    async def test_me_returns_user_info(self, client):
        # Register to get a token
        reg_resp = await client.post("/api/v1/auth/register", json={
            "org_name": "Me Test Org",
            "email": "me@test.com",
            "password": "SecurePass123!",
        })
        token = reg_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@test.com"
        assert data["role"] == "admin"
        assert "organization" in data
        assert data["organization"]["name"] == "Me Test Org"
        assert "id" in data
        assert "created_at" in data

    async def test_me_without_token_fails(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 422  # Missing required header

    async def test_me_with_invalid_token_fails(self, client):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    async def test_me_with_malformed_header_fails(self, client):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "NotBearer token"},
        )
        assert resp.status_code == 401
