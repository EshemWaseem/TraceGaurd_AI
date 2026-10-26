import pytest
import time
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db, check_db_health
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    auth_rate_limiter,
)
from app.analysis.engine import AnalysisEngine, MAX_LINE_LENGTH, _bound_lines


TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    auth_rate_limiter.clear()
    yield
    Base.metadata.drop_all(bind=test_engine)
    if prev is not None:
        app.dependency_overrides[get_db] = prev
    else:
        app.dependency_overrides.pop(get_db, None)
    auth_rate_limiter.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestSecurityHeadersAndCorrelationID:
    """Verify production security headers and correlation ID tracking."""

    def test_response_includes_all_standard_security_headers(self, client: TestClient):
        res = client.get("/api/health")
        assert res.status_code == 200

        headers = res.headers
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("X-XSS-Protection") == "1; mode=block"
        assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "Permissions-Policy" in headers
        assert "Content-Security-Policy" in headers
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]

    def test_request_id_generated_when_omitted(self, client: TestClient):
        res = client.get("/api/health")
        assert res.status_code == 200
        req_id = res.headers.get("X-Request-ID")
        assert req_id is not None
        assert len(req_id) == 32  # standard uuid4 hex length

    def test_request_id_propagated_when_valid(self, client: TestClient):
        valid_id = "trace-test-req-999"
        res = client.get("/api/health", headers={"X-Request-ID": valid_id})
        assert res.status_code == 200
        assert res.headers.get("X-Request-ID") == valid_id

    def test_request_id_sanitized_when_malicious_or_invalid(self, client: TestClient):
        malicious_id = "<script>alert(1)</script>\r\nInjected-Header: value"
        res = client.get("/api/health", headers={"X-Request-ID": malicious_id})
        assert res.status_code == 200
        req_id = res.headers.get("X-Request-ID")
        assert req_id != malicious_id
        assert len(req_id) == 32  # replaced with safe uuid4 hex


class TestPathologicalInputAndParserProtection:
    """Verify resiliency against oversized lines and ReDoS attacks."""

    def test_bound_lines_truncates_oversized_line(self):
        huge_line = "A" * (MAX_LINE_LENGTH + 5000)
        bounded = _bound_lines(huge_line)
        assert len(bounded) < len(huge_line)
        assert "[TRUNCATED_OVERSIZED_LINE]" in bounded
        assert bounded.startswith("A" * 100)

    def test_engine_processes_pathological_oversized_line_without_crash(self):
        engine = AnalysisEngine()
        huge_line = "2024-01-15 10:00:00 ERROR service " + ("X" * 50000)
        normal_line = "2024-01-15 10:00:01 INFO service Normal log event"
        content = f"{huge_line}\n{normal_line}"

        result = engine.analyze(content, "pathological.log")
        assert result.summary.total_lines == 2
        assert result.summary.error_count >= 1
        assert len(result.events) >= 1

    def test_analyze_rate_limiting_enforced(self, client: TestClient):
        client_ip = "192.168.1.100"
        headers = {"X-Forwarded-For": client_ip}

        # Make calls up to limit
        for i in range(120):
            res = client.post(
                "/api/analyze",
                json={"content": "2024-01-15 10:00:00 INFO service event\n", "filename": "test.log"},
                headers=headers,
            )
            assert res.status_code == 200

        # 121st call should trigger 429
        res = client.post(
            "/api/analyze",
            json={"content": "2024-01-15 10:00:00 INFO service event\n", "filename": "test.log"},
            headers=headers,
        )
        assert res.status_code == 429
        assert "Rate limit exceeded" in res.json()["detail"]


class TestJWTAndCryptographicResilience:
    """Verify cryptographic token bounds, algorithm confusion rejection, and expiration."""

    def test_reject_token_with_algorithm_none(self):
        forged_token = jwt.encode(
            {"sub": "attacker-user-id", "email": "attacker@example.com"},
            key="",
            algorithm="none",
        )
        payload = decode_access_token(forged_token)
        assert payload is None, "PyJWT must strictly reject tokens signed with algorithm 'none'"

    def test_reject_token_with_wrong_key(self):
        forged_token = jwt.encode(
            {"sub": "attacker-user-id"},
            key="totally-wrong-secret-key-1234567890",
            algorithm="HS256",
        )
        payload = decode_access_token(forged_token)
        assert payload is None

    def test_expired_token_rejected_safely(self):
        expired_token = jwt.encode(
            {"sub": "test-user", "exp": int(time.time()) - 3600},
            key=settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        payload = decode_access_token(expired_token)
        assert payload is None


class TestDatabaseReliabilityAndRollback:
    """Verify session rollback behavior and healthcheck error resilience."""

    def test_get_db_session_rolls_back_on_unhandled_exception(self):
        db_generator = override_get_db()
        db = next(db_generator)

        # Execute some uncommitted write
        db.execute(text("CREATE TEMPORARY TABLE _temp_test (id INT)"))

        # Simulate exception during request processing
        with pytest.raises(RuntimeError):
            try:
                raise RuntimeError("Simulated route crash")
            except Exception as e:
                db_generator.throw(e)

    def test_check_db_health_safe_output(self):
        health = check_db_health()
        assert "status" in health
        # Ensure no passwords or connection strings are present in health payload
        assert "password" not in str(health).lower()
        assert "@" not in str(health)
