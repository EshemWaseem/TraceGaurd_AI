"""Automated security tests for production hardening mitigations (SEC-01 through SEC-07)."""

import pytest
from starlette.datastructures import Headers
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.security import get_trusted_client_ip
from app.db.session import check_db_health


class DummyClient:
    def __init__(self, host: str):
        self.host = host


class DummyRequest:
    def __init__(self, host: str, headers: dict):
        self.client = DummyClient(host)
        self.headers = Headers(headers)


@pytest.fixture
def client():
    return TestClient(app)


def test_cors_rejects_arbitrary_third_party_vercel_domain(client: TestClient):
    """Verify that an arbitrary third-party Vercel app cannot get credentialed CORS access."""
    res = client.options(
        "/api/health",
        headers={
            "Origin": "https://evil-attacker.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    # The origin must NOT be reflected
    allow_origin = res.headers.get("access-control-allow-origin")
    assert allow_origin != "https://evil-attacker.vercel.app"


def test_cors_accepts_canonical_traceguard_frontend(client: TestClient):
    """Verify that the official TraceGuard AI production frontend is allowed with credentials."""
    res = client.options(
        "/api/health",
        headers={
            "Origin": "https://trace-gaurd-ai.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.headers.get("access-control-allow-origin") == "https://trace-gaurd-ai.vercel.app"
    assert res.headers.get("access-control-allow-credentials") == "true"


def test_cors_accepts_official_project_preview_branch(client: TestClient):
    """Verify that project preview deployments are allowed."""
    res = client.options(
        "/api/health",
        headers={
            "Origin": "https://trace-gaurd-ai-git-preview-eshem.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.headers.get("access-control-allow-origin") == "https://trace-gaurd-ai-git-preview-eshem.vercel.app"


def test_cf_connecting_ip_honored_from_trusted_cloud_proxy():
    """Verify that CF-Connecting-IP is extracted when direct peer is an RFC1918 cloud proxy."""
    req = DummyRequest(
        host="10.0.12.34",  # Cloud proxy on Render RFC1918 subnet
        headers={
            "cf-connecting-ip": "203.0.113.88",
            "x-forwarded-for": "203.0.113.88, 10.0.12.34",
        },
    )
    assert get_trusted_client_ip(req) == "203.0.113.88"


def test_cf_connecting_ip_ignored_from_untrusted_public_peer():
    """Verify that direct public connections cannot spoof CF-Connecting-IP."""
    req = DummyRequest(
        host="198.51.100.22",  # Untrusted public IP
        headers={
            "cf-connecting-ip": "1.1.1.1",
        },
    )
    assert get_trusted_client_ip(req) == "198.51.100.22"


def test_db_health_sanitized_in_production(monkeypatch):
    """Verify that /api/health/db does not reveal host or port when running in production."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    health = check_db_health()
    assert health.get("status") in ("connected", "error")
    # Host, port, and backend details must NOT be leaked
    assert "host" not in health
    assert "port" not in health
    assert "backend" not in health
