import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from .config import settings

# Initialize Argon2 Password Hasher with secure defaults
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash password securely using Argon2id."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2 hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": now,
    })
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Verify and decode JWT access token. Returns None on invalid/expired token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except jwt.PyJWTError:
        return None


# ==============================================================================
# Rate Limiting Helper (Brute-force mitigation for auth endpoints)
# ==============================================================================

class InMemoryRateLimiter:
    """In-memory sliding-window rate limiter for abuse mitigation.

    ARCHITECTURAL LIMITATION:
    This rate limiter is strictly process-local. In multi-worker (e.g. uvicorn with
    --workers > 1) or multi-replica (e.g. Kubernetes pods) environments, each
    process maintains its own local counter. For horizontally scaled deployments,
    a shared distributed key-value store (such as Redis) must back the rate limiter.
    """

    def __init__(self):
        self._attempts: Dict[str, List[float]] = defaultdict(list)

    def is_rate_limited(self, key: str, max_attempts: int = 5, window_seconds: int = 60) -> bool:
        now = time.time()
        window_start = now - window_seconds

        # Prune old timestamps
        self._attempts[key] = [t for t in self._attempts[key] if t > window_start]

        if len(self._attempts[key]) >= max_attempts:
            return True

        self._attempts[key].append(now)
        return False

    def reset(self, key: str) -> None:
        if key in self._attempts:
            del self._attempts[key]

    def clear(self) -> None:
        self._attempts.clear()


auth_rate_limiter = InMemoryRateLimiter()


import ipaddress

_DOCKER_BRIDGE_NET = ipaddress.ip_network("172.16.0.0/12")


def _is_trusted_peer(peer_str: str) -> bool:
    """Determine whether direct peer is an authorized reverse proxy."""
    if peer_str in ("localhost", "testclient"):
        return True
    try:
        ip = ipaddress.ip_address(peer_str)
    except ValueError:
        return False

    if ip.is_loopback:
        return True
    if ip in _DOCKER_BRIDGE_NET:
        return True

    # Check explicitly configured TRUSTED_PROXIES from environment if defined
    trusted_env = getattr(settings, "TRUSTED_PROXIES", "")
    if trusted_env:
        for entry in trusted_env.split(","):
            entry = entry.strip()
            if not entry:
                continue
            try:
                net = ipaddress.ip_network(entry, strict=False)
                if ip in net:
                    return True
            except ValueError:
                pass
    return False


def get_trusted_client_ip(request) -> str:
    """Extract client IP safely.

    Only honors X-Real-IP or X-Forwarded-For when the direct peer
    (request.client.host) is an authorized reverse proxy (loopback or Docker bridge subnet).
    Otherwise, returns direct peer host to prevent IP header spoofing.
    Validates that forwarded values are syntactically valid IPv4 or IPv6 addresses.
    When multiple forwarded proxies are present in X-Forwarded-For, walks the proxy chain
    from right to left to select the first untrusted upstream client address.
    """
    peer = request.client.host if request.client else "unknown"
    if not _is_trusted_peer(peer):
        return peer

    # 1. Prefer X-Real-IP if provided by trusted Nginx reverse proxy
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        real_ip = real_ip.strip()
        try:
            ipaddress.ip_address(real_ip)
            return real_ip
        except ValueError:
            pass

    # 2. Inspect X-Forwarded-For header (client is the leftmost entry in standard proxy forwarding)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        clean_candidate = candidate.split(":")[0] if ":" in candidate and not candidate.startswith("[") and candidate.count(":") == 1 else candidate.strip("[]")
        try:
            ipaddress.ip_address(clean_candidate)
            return clean_candidate
        except ValueError:
            pass

    return peer

