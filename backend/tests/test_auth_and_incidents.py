import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    auth_rate_limiter,
)
from app.models.db import User, Organization, OrganizationMember, Incident

# Create an isolated test SQLite in-memory database with StaticPool
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
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure clean database tables, rate limiters, and client cookies for each test."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    auth_rate_limiter.clear()
    client.cookies.clear()
    yield
    client.cookies.clear()


# ==============================================================================
# Security & Hashing Tests
# ==============================================================================

def test_password_hashing_not_plaintext():
    raw = "MySuperSecretPassword123!"
    hashed = hash_password(raw)

    assert hashed != raw
    assert hashed.startswith("$argon2")  # Confirms Argon2 format
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


def test_token_expiration_and_rejection():
    # Valid token
    token = create_access_token({"sub": "user-123", "email": "test@traceguard.io"}, expires_delta=timedelta(minutes=5))
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"

    # Expired token
    expired_token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(seconds=-10))
    assert decode_access_token(expired_token) is None

    # Tampered / invalid token
    tampered = token[:-4] + "xxxx"
    assert decode_access_token(tampered) is None


# ==============================================================================
# Signup & Login API Tests
# ==============================================================================

def test_signup_success():
    res = client.post(
        "/api/auth/signup",
        json={
            "email": "alice@example.com",
            "password": "Password123!",
            "full_name": "Alice Smith",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["full_name"] == "Alice Smith"
    assert len(data["organizations"]) == 1
    assert data["organizations"][0]["role"] == "owner"


def test_signup_duplicate_email_rejected():
    client.post(
        "/api/auth/signup",
        json={"email": "duplicate@example.com", "password": "Password123!"},
    )
    res = client.post(
        "/api/auth/signup",
        json={"email": "duplicate@example.com", "password": "AnotherPassword123!"},
    )
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"]


def test_signup_invalid_email_format():
    res = client.post(
        "/api/auth/signup",
        json={"email": "not-an-email", "password": "Password123!"},
    )
    assert res.status_code == 422


def test_login_success():
    client.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "BobPassword123!"},
    )
    res = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "BobPassword123!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "bob@example.com"


def test_login_invalid_password():
    client.post(
        "/api/auth/signup",
        json={"email": "carol@example.com", "password": "CarolPassword123!"},
    )
    res = client.post(
        "/api/auth/login",
        json={"email": "carol@example.com", "password": "WrongPassword!"},
    )
    assert res.status_code == 401
    assert "Incorrect email or password" in res.json()["detail"]


# ==============================================================================
# Protected Routes & Current User Profile Tests
# ==============================================================================

def test_protected_routes_reject_unauthenticated():
    res = client.get("/api/auth/me")
    assert res.status_code == 401

    res = client.get("/api/incidents")
    assert res.status_code == 401


def test_get_current_user_profile():
    signup_res = client.post(
        "/api/auth/signup",
        json={"email": "dave@example.com", "password": "DavePassword123!"},
    )
    token = signup_res.json()["access_token"]

    res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["email"] == "dave@example.com"
    assert len(data["organizations"]) >= 1


def test_logout_endpoint():
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


# ==============================================================================
# Multi-Tenant Isolation & Anti-IDOR Tests
# ==============================================================================

def test_multi_tenant_incident_isolation():
    """
    User A creates an incident in Org A.
    User B (in Org B) MUST NOT be able to view, list, or delete User A's incident.
    """
    # 1. Signup User A
    res_a = client.post(
        "/api/auth/signup",
        json={"email": "user_a@tenant-a.com", "password": "PasswordA123!", "org_name": "Org A"},
    )
    token_a = res_a.json()["access_token"]
    org_a_id = res_a.json()["active_organization_id"]

    # 2. Signup User B
    res_b = client.post(
        "/api/auth/signup",
        json={"email": "user_b@tenant-b.com", "password": "PasswordB123!", "org_name": "Org B"},
    )
    token_b = res_b.json()["access_token"]
    org_b_id = res_b.json()["active_organization_id"]

    assert org_a_id != org_b_id

    # 3. User A creates an incident
    create_res = client.post(
        "/api/incidents",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "organization_id": org_a_id,
            "title": "Database Connection Spike",
            "filename": "db_error.log",
            "file_format": "json_application",
            "summary_json": {"total_lines": 50, "error_count": 5, "anomalies_flagged": 2},
            "anomalies_json": [{"id": "anom-1", "title": "Connection Pool Exhaustion"}],
            "raw_content_preview": "2024-01-15 ERROR db connection failed",
        },
    )
    assert create_res.status_code == 201
    incident_id = create_res.json()["id"]

    # 4. User A can list and retrieve their incident
    list_res_a = client.get("/api/incidents", headers={"Authorization": f"Bearer {token_a}"})
    assert list_res_a.status_code == 200
    assert len(list_res_a.json()) == 1
    assert list_res_a.json()[0]["id"] == incident_id

    get_res_a = client.get(f"/api/incidents/{incident_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert get_res_a.status_code == 200
    assert get_res_a.json()["title"] == "Database Connection Spike"

    # 5. User B CANNOT see User A's incident in their list
    list_res_b = client.get("/api/incidents", headers={"Authorization": f"Bearer {token_b}"})
    assert list_res_b.status_code == 200
    assert len(list_res_b.json()) == 0  # Isolation verified!

    # 6. User B CANNOT retrieve User A's incident by ID (Anti-IDOR: returns 404)
    get_res_b = client.get(f"/api/incidents/{incident_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert get_res_b.status_code == 404

    # 7. User B CANNOT delete User A's incident (Anti-IDOR: returns 404)
    del_res_b = client.delete(f"/api/incidents/{incident_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert del_res_b.status_code == 404

    # 8. User A CAN delete their own incident
    del_res_a = client.delete(f"/api/incidents/{incident_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert del_res_a.status_code == 200
    assert del_res_a.json()["status"] == "ok"


def test_bounded_raw_log_storage():
    """Verify raw log preview is bounded and does not store unbounded files."""
    signup_res = client.post(
        "/api/auth/signup",
        json={"email": "storage_tester@example.com", "password": "Password123!"},
    )
    token = signup_res.json()["access_token"]

    huge_raw = "A" * (50 * 1024)  # 50 KB raw log
    create_res = client.post(
        "/api/incidents",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Large Raw Test",
            "filename": "huge.log",
            "file_format": "plaintext",
            "summary_json": {"total_lines": 1000},
            "raw_content_preview": huge_raw,
        },
    )
    assert create_res.status_code == 201
    stored_preview = create_res.json()["raw_content_preview"]
    assert len(stored_preview.encode("utf-8")) <= 20 * 1024  # Capped at 20 KB


def test_incident_search_filtering_and_pagination():
    """Verify search by keyword, format filtering, and sort/pagination."""
    signup_res = client.post(
        "/api/auth/signup",
        json={"email": "search_tester@example.com", "password": "Password123!"},
    )
    token = signup_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create 3 distinct incidents
    client.post(
        "/api/incidents",
        headers=headers,
        json={
            "title": "Nginx Outage Alpha",
            "filename": "nginx_access.log",
            "file_format": "nginx_apache",
            "summary_json": {"total_lines": 100, "error_count": 10, "anomalies_flagged": 2},
        },
    )
    client.post(
        "/api/incidents",
        headers=headers,
        json={
            "title": "Postgres Deadlock Beta",
            "filename": "db_cluster.log",
            "file_format": "json_application",
            "summary_json": {"total_lines": 50, "error_count": 2, "anomalies_flagged": 1},
        },
    )
    client.post(
        "/api/incidents",
        headers=headers,
        json={
            "title": "Worker Crash Gamma",
            "filename": "worker.log",
            "file_format": "plaintext",
            "summary_json": {"total_lines": 20, "error_count": 1, "anomalies_flagged": 0},
        },
    )

    # Search by title keyword
    search_res = client.get("/api/incidents?search=deadlock", headers=headers)
    assert search_res.status_code == 200
    results = search_res.json()
    assert len(results) == 1
    assert results[0]["title"] == "Postgres Deadlock Beta"

    # Filter by format
    fmt_res = client.get("/api/incidents?format=nginx_apache", headers=headers)
    assert fmt_res.status_code == 200
    fmt_results = fmt_res.json()
    assert len(fmt_results) == 1
    assert fmt_results[0]["file_format"] == "nginx_apache"

    # Pagination: limit=1
    page_res = client.get("/api/incidents?limit=1&offset=0", headers=headers)
    assert page_res.status_code == 200
    assert len(page_res.json()) == 1


def test_incident_stats_and_multi_tenant_isolation():
    """Verify aggregated stats and strict tenant isolation for telemetry."""
    # Org A
    res_a = client.post(
        "/api/auth/signup",
        json={"email": "stats_a@tenant-a.com", "password": "PasswordA123!", "org_name": "Org A Stats"},
    )
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Org B
    res_b = client.post(
        "/api/auth/signup",
        json={"email": "stats_b@tenant-b.com", "password": "PasswordB123!", "org_name": "Org B Stats"},
    )
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Org A creates an incident with 15 errors and 3 anomalies
    client.post(
        "/api/incidents",
        headers=headers_a,
        json={
            "title": "Org A Production Issue",
            "filename": "prod.log",
            "file_format": "json_application",
            "summary_json": {"total_lines": 200, "error_count": 15, "anomalies_flagged": 3},
        },
    )

    # Org A checks stats
    stats_a = client.get("/api/incidents/stats", headers=headers_a).json()
    assert stats_a["total_incidents"] == 1
    assert stats_a["total_errors"] == 15
    assert stats_a["total_anomalies"] == 3
    assert stats_a["by_format"].get("json_application") == 1
    assert len(stats_a["recent_incidents"]) == 1

    # Org B checks stats -> must be 0 (isolated!)
    stats_b = client.get("/api/incidents/stats", headers=headers_b).json()
    assert stats_b["total_incidents"] == 0
    assert stats_b["total_errors"] == 0
    assert stats_b["total_anomalies"] == 0
    assert len(stats_b["recent_incidents"]) == 0


def test_no_password_hash_leakage():
    """Verify that password hash is never exposed in user responses."""
    signup_res = client.post(
        "/api/auth/signup",
        json={"email": "hash_check@example.com", "password": "SuperSecretPassword123!"},
    )
    data = signup_res.json()
    assert "hashed_password" not in data["user"]
    assert "password" not in data["user"]

    token = data["access_token"]
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    me_data = me_res.json()
    assert "hashed_password" not in me_data["user"]
    assert "password" not in me_data["user"]
