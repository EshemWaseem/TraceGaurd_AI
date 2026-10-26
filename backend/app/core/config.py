import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import URL, make_url
from typing import List

# Reliably locate and load root .env first, then backend .env
_backend_dir = Path(__file__).resolve().parent.parent.parent
_root_dir = _backend_dir.parent

if (_root_dir / ".env").is_file():
    load_dotenv(_root_dir / ".env")
elif (_backend_dir / ".env").is_file():
    load_dotenv(_backend_dir / ".env")
else:
    load_dotenv()


# Determine database connection URL:
# 1. If POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB are defined, use them as authoritative credentials.
#    Host and port default safely for the environment:
#    - Inside container: POSTGRES_HOST=db, POSTGRES_PORT=5432
#    - On host dev/test: POSTGRES_HOST=127.0.0.1, POSTGRES_PORT=5434 (mapped container port)
# 2. If discrete credentials are not set, fall back to explicit DATABASE_URL (for PaaS / CI).
_raw_database_url = os.getenv("DATABASE_URL")
_pg_user = os.getenv("POSTGRES_USER")
_pg_pass = os.getenv("POSTGRES_PASSWORD")
_pg_db = os.getenv("POSTGRES_DB")

if _pg_user and _pg_pass and _pg_db:
    _pg_host = os.getenv("POSTGRES_HOST")
    _pg_port_env = os.getenv("POSTGRES_PORT")

    # If host/port not set via POSTGRES_HOST/PORT, check if DATABASE_URL provides non-localhost host
    if not _pg_host and _raw_database_url:
        try:
            _parsed_temp = make_url(_raw_database_url.strip())
            if _parsed_temp.host and _parsed_temp.host not in ("127.0.0.1", "localhost"):
                _pg_host = _parsed_temp.host
                if not _pg_port_env and _parsed_temp.port:
                    _pg_port_env = str(_parsed_temp.port)
        except Exception:
            pass

    _pg_host = _pg_host or "127.0.0.1"
    _default_port = 5434 if _pg_host in ("127.0.0.1", "localhost") else 5432
    try:
        _pg_port = int(_pg_port_env or str(_default_port))
    except ValueError:
        _pg_port = _default_port

    _DATABASE_URL = URL.create(
        drivername="postgresql+psycopg",
        username=_pg_user,
        password=_pg_pass,
        host=_pg_host,
        port=_pg_port,
        database=_pg_db,
    )
elif _raw_database_url and _raw_database_url.strip():
    _parsed = make_url(_raw_database_url.strip())
    if _parsed.drivername in ("postgresql", "postgres"):
        _DATABASE_URL = _parsed.set(drivername="postgresql+psycopg")
    else:
        _DATABASE_URL = _parsed
else:
    raise RuntimeError(
        "Missing required database configuration: provide POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB, "
        "or a valid DATABASE_URL in your environment or root .env file."
    )


class Settings:
    PROJECT_NAME: str = "TraceGuard AI"
    VERSION: str = "0.2.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Central database URL object constructed from approved environment variables
    DATABASE_URL: URL = _DATABASE_URL

    # Security & JWT
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "dev_secret_key_change_me_to_a_secure_random_string_32_chars_min",
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # Cookie settings
    COOKIE_NAME: str = "traceguard_access_token"
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
    COOKIE_SAMESITE: str = "lax"

    # Network & Reverse Proxy settings
    TRUSTED_PROXIES: str = os.getenv("TRUSTED_PROXIES", "")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "")

    def get_cors_origins(self) -> List[str]:
        """Return configured CORS origins with safe localhost/container defaults."""
        defaults = [
            "http://localhost:5173",  # Vite dev
            "http://127.0.0.1:5173",  # Vite dev IP
            "http://localhost:4173",  # Vite preview
            "http://localhost:8080",  # Production Compose frontend proxy
            "http://127.0.0.1:8080",  # Production Compose frontend proxy IP
        ]
        if self.CORS_ORIGINS:
            extra = [
                o.strip().rstrip("/")
                for o in self.CORS_ORIGINS.split(",")
                if o.strip() and o.strip() != "*"
            ]
            for item in extra:
                if item not in defaults:
                    defaults.append(item)
        return defaults

    def validate_production_secrets(self) -> None:
        if self.ENVIRONMENT == "production":
            if (
                not self.SECRET_KEY
                or "dev_secret" in self.SECRET_KEY
                or len(self.SECRET_KEY) < 32
            ):
                raise RuntimeError(
                    "FATAL: In production, SECRET_KEY must be explicitly set to a cryptographically secure random string with at least 32 characters."
                )


settings = Settings()
settings.validate_production_secrets()