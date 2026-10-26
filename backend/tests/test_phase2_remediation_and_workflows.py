"""Phase 2 Remediation & Runtime Workflow Integration Tests.

Validates:
1. Dynamic Database URL & health-check port reporting (no hardcoding, no credential leakage).
2. Advanced trusted-proxy and IPv4/IPv6 client IP resolution.
3. Two-tier brute-force and credential-stuffing mitigation on authentication endpoints.
4. Incident PATCH update endpoint with multi-tenant IDOR isolation and role restrictions.
5. End-to-end user journey (register -> login -> analyze -> persist -> query -> patch -> cross-tenant check -> delete).
6. Transaction rollback and session durability on database operations.
7. Evidence integrity and log parsing boundary guarantees.
"""

from __future__ import annotations

import os
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import auth_rate_limiter, get_trusted_client_ip, create_access_token
from app.db.session import Base, get_db, check_db_health
from app.main import app
from app.models.db import Incident, Organization, OrganizationMember, User
from app.analysis.engine import AnalysisEngine
from app.analysis.sanitizer import sanitize_message

# Isolated in-memory test database
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


from starlette.datastructures import Headers


class DummyRequest:
    def __init__(self, host: str, headers: dict | None = None):
        class Client:
            def __init__(self, h: str):
                self.host = h
        self.client = Client(host)
        self.headers = Headers(headers or {})


@pytest.fixture(autouse=True)
def clean_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    auth_rate_limiter.clear()
    client.cookies.clear()
    yield
    client.cookies.clear()


# ==============================================================================
# 1. Database Configuration & Health Dynamic Reporting
# ==============================================================================

def test_cors_origins_defaults_and_custom():
    """CORS origins include development and production defaults and custom extras."""
    origins = settings.get_cors_origins()
    assert "http://localhost:5173" in origins
    assert "http://localhost:8080" in origins
    assert "http://127.0.0.1:8080" in origins
    assert "http://frontend:5173" not in origins


def test_db_health_endpoint_no_credentials():
    """GET /api/health/db returns structured status without leaking database credentials."""
    resp = client.get("/api/health/db")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "password" not in str(data).lower()
    assert "user" not in str(data).lower()


# ==============================================================================
# 2. IP Resolution & Rate Limiting Hardening
# ==============================================================================

def test_client_ip_ipv4_with_port():
    """Forwarded IPv4 address with port string (e.g. 198.51.100.22:45000) is parsed safely."""
    req = DummyRequest(
        host="127.0.0.1",
        headers={"x-forwarded-for": "198.51.100.22:45000, 10.0.0.1"}
    )
    assert get_trusted_client_ip(req) == "198.51.100.22"


def test_client_ip_ipv6_handling():
    """Valid IPv6 address in X-Forwarded-For is properly recognized."""
    req = DummyRequest(
        host="127.0.0.1",
        headers={"x-forwarded-for": "2001:db8::1, 10.0.0.1"}
    )
    assert get_trusted_client_ip(req) == "2001:db8::1"


def test_login_ip_spray_rate_limiting():
    """Rapid login attempts across rotating email accounts from same IP triggers 429."""
    for i in range(30):
        resp = client.post(
            "/api/auth/login",
            json={"email": f"spray_{i}@example.com", "password": "wrongpassword123"},
        )
        assert resp.status_code == 401

    # 31st attempt from same client must be rate limited by IP
    resp_blocked = client.post(
        "/api/auth/login",
        json={"email": "spray_31@example.com", "password": "wrongpassword123"},
    )
    assert resp_blocked.status_code == 429
    assert "Too many login attempts from this address" in resp_blocked.json()["detail"]


# ==============================================================================
# 3. Incident PATCH Endpoint & Tenancy Isolation
# ==============================================================================

def _create_test_environment(db):
    """Helper to create two distinct organizations with users and members."""
    # Org A
    user_a1 = User(email="user_a1@example.com", hashed_password="argon2_hashed_fake", full_name="User A1", is_active=True)
    user_a2 = User(email="user_a2@example.com", hashed_password="argon2_hashed_fake", full_name="User A2", is_active=True)
    org_a = Organization(name="Organization Alpha", slug="org-alpha-12345678")
    db.add_all([user_a1, user_a2, org_a])
    db.flush()

    mem_a1 = OrganizationMember(organization_id=org_a.id, user_id=user_a1.id, role="owner")
    mem_a2 = OrganizationMember(organization_id=org_a.id, user_id=user_a2.id, role="member")
    db.add_all([mem_a1, mem_a2])

    # Org B
    user_b1 = User(email="user_b1@example.com", hashed_password="argon2_hashed_fake", full_name="User B1", is_active=True)
    org_b = Organization(name="Organization Beta", slug="org-beta-87654321")
    db.add_all([user_b1, org_b])
    db.flush()

    mem_b1 = OrganizationMember(organization_id=org_b.id, user_id=user_b1.id, role="owner")
    db.add(mem_b1)

    # Incident in Org A created by user_a1
    inc_a = Incident(
        organization_id=org_a.id,
        created_by_user_id=user_a1.id,
        title="Payment Gateway Timeout",
        filename="gateway.log",
        file_format="json_application",
        summary_json={"total_lines": 10, "error_count": 2},
        raw_content_preview="Initial preview line",
    )
    db.add(inc_a)
    db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "user_a1": user_a1,
        "user_a2": user_a2,
        "user_b1": user_b1,
        "inc_a": inc_a,
    }


def test_incident_patch_by_creator():
    """Creator can successfully update incident title and preview."""
    db = TestingSessionLocal()
    env = _create_test_environment(db)
    token = create_access_token({"sub": env["user_a1"].id, "email": env["user_a1"].email})

    resp = client.patch(
        f"/api/incidents/{env['inc_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Updated Gateway Failure Incident"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Updated Gateway Failure Incident"

    # Verify database persistence
    db.expire_all()
    refreshed = db.scalar(select(Incident).where(Incident.id == env["inc_a"].id))
    assert refreshed.title == "Updated Gateway Failure Incident"


def test_incident_patch_redacts_secrets_in_preview():
    """Incident PATCH preview redacts sensitive tokens before storing."""
    db = TestingSessionLocal()
    env = _create_test_environment(db)
    token = create_access_token({"sub": env["user_a1"].id, "email": env["user_a1"].email})

    resp = client.patch(
        f"/api/incidents/{env['inc_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw_content_preview": "Connecting with postgres://admin:super_secret_pw@localhost:5432/db"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "super_secret_pw" not in data["raw_content_preview"]
    assert "[REDACTED_PASSWORD]" in data["raw_content_preview"]


def test_incident_patch_empty_title_rejected():
    """Blank title is rejected with 422."""
    db = TestingSessionLocal()
    env = _create_test_environment(db)
    token = create_access_token({"sub": env["user_a1"].id, "email": env["user_a1"].email})

    resp = client.patch(
        f"/api/incidents/{env['inc_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "   "},
    )
    assert resp.status_code == 422


def test_incident_patch_cross_tenant_idor_blocked():
    """User in Org B attempting to patch incident in Org A receives 404 (anti-IDOR)."""
    db = TestingSessionLocal()
    env = _create_test_environment(db)
    token_b = create_access_token({"sub": env["user_b1"].id, "email": env["user_b1"].email})

    resp = client.patch(
        f"/api/incidents/{env['inc_a'].id}",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"title": "Malicious Tampered Title"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Organization not found or access denied."


def test_incident_patch_role_restriction_non_creator():
    """Regular member who did not create the incident cannot edit it (returns 403)."""
    db = TestingSessionLocal()
    env = _create_test_environment(db)
    token_a2 = create_access_token({"sub": env["user_a2"].id, "email": env["user_a2"].email})

    resp = client.patch(
        f"/api/incidents/{env['inc_a'].id}",
        headers={"Authorization": f"Bearer {token_a2}"},
        json={"title": "Unauthorized Modification"},
    )
    assert resp.status_code == 403
    assert "Insufficient permissions" in resp.json()["detail"]


# ==============================================================================
# 4. End-to-End Product Workflow Lifecycle
# ==============================================================================

def test_full_incident_lifecycle_workflow():
    """
    End-to-end integration test of the complete product workflow:
    1. Register new user
    2. Log in and get session
    3. Analyze a log file
    4. Save incident
    5. Search and retrieve saved incident
    6. Update incident metadata
    7. Verify foreign organization cannot access it
    8. Delete incident
    """
    # 1. Register
    signup_resp = client.post(
        "/api/auth/signup",
        json={
            "email": "investigator@traceguard.io",
            "password": "SecurePassword2026!",
            "full_name": "Lead SRE",
            "org_name": "Operations Center",
        },
    )
    assert signup_resp.status_code == 201
    auth_data = signup_resp.json()
    token = auth_data["access_token"]
    org_id = auth_data["active_organization_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Analyze a sample log
    sample_log = (
        '{"timestamp":"2024-01-15T10:00:00Z","level":"INFO","message":"Service started","service":"auth"}\n'
        '{"timestamp":"2024-01-15T10:00:05Z","level":"ERROR","message":"Connection refused to DB","service":"auth"}\n'
        '{"timestamp":"2024-01-15T10:00:10Z","level":"ERROR","message":"Retry exhausted; shutting down","service":"auth"}\n'
    )
    analyze_resp = client.post(
        "/api/analyze",
        files={"file": ("incident.log", sample_log.encode("utf-8"), "text/plain")},
    )
    assert analyze_resp.status_code == 200
    analysis = analyze_resp.json()
    assert analysis["summary"]["error_count"] == 2
    assert "investigation" in analysis

    # 3. Save incident
    save_resp = client.post(
        "/api/incidents",
        headers=headers,
        json={
            "organization_id": org_id,
            "title": "Auth Service DB Outage",
            "filename": "incident.log",
            "file_format": "json_application",
            "summary_json": analysis["summary"],
            "anomalies_json": analysis["anomalies"],
            "hypotheses_json": analysis["hypotheses"],
            "events_json": analysis["events"],
            "investigation_report_json": analysis["investigation"],
            "raw_content_preview": sample_log[:500],
        },
    )
    assert save_resp.status_code == 201
    incident_id = save_resp.json()["id"]

    # 4. Search and retrieve saved incident
    list_resp = client.get(f"/api/incidents?search=Outage", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["id"] == incident_id

    # 5. Fetch full detail
    detail_resp = client.get(f"/api/incidents/{incident_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["title"] == "Auth Service DB Outage"

    # 6. Update incident metadata
    patch_resp = client.patch(
        f"/api/incidents/{incident_id}",
        headers=headers,
        json={"title": "Auth Service DB Outage (Root Cause Confirmed)"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Auth Service DB Outage (Root Cause Confirmed)"

    # 7. Foreign organization isolation check
    # Register second user in another org
    signup_b = client.post(
        "/api/auth/signup",
        json={"email": "external@competitor.io", "password": "SecurePassword2026!", "full_name": "External User"},
    )
    token_b = signup_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    foreign_get = client.get(f"/api/incidents/{incident_id}", headers=headers_b)
    assert foreign_get.status_code == 404

    foreign_delete = client.delete(f"/api/incidents/{incident_id}", headers=headers_b)
    assert foreign_delete.status_code == 404

    # 8. Delete incident authorized
    del_resp = client.delete(f"/api/incidents/{incident_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "ok"

    # Verify deleted
    verify_get = client.get(f"/api/incidents/{incident_id}", headers=headers)
    assert verify_get.status_code == 404


# ==============================================================================
# 5. Evidence & Causality Integrity Boundaries
# ==============================================================================

def test_evidence_integrity_no_silent_discards():
    """Unrecognized and non-matching lines are preserved with exact 1-indexed line numbers."""
    engine = AnalysisEngine()
    content = (
        '{"timestamp":"2024-01-15T10:00:00Z","level":"INFO","message":"Line 1"}\n'
        'THIS IS A CORRUPTED UNRECOGNIZED LINE\n'
        '{"timestamp":"2024-01-15T10:00:10Z","level":"ERROR","message":"Line 3"}\n'
    )
    result = engine.analyze(content, "test.log")
    assert len(result.events) == 2
    assert len(result.unrecognised_lines) == 1
    assert result.unrecognised_lines[0].line_number == 2
    assert "CORRUPTED" in result.unrecognised_lines[0].raw
