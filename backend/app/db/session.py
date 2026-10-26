import logging
from typing import Generator, Union
from sqlalchemy import create_engine, text, URL
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from ..core.config import settings

logger = logging.getLogger("traceguard.db")


class Base(DeclarativeBase):
    pass


def _create_engine(primary_url: Union[str, URL]):
    """
    Create the SQLAlchemy engine using the configured PostgreSQL connection.
    Fails loudly and immediately on connectivity or authentication errors;
    no silent fallback to SQLite.
    """
    driver_name = primary_url.drivername if isinstance(primary_url, URL) else str(primary_url)

    connect_args = {}
    engine_kwargs = {
        "pool_pre_ping": True,
        "echo": False,
    }
    if "postgresql" in driver_name:
        connect_args["connect_timeout"] = 5
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20
        engine_kwargs["pool_recycle"] = 1800
        engine_kwargs["pool_timeout"] = 10
    elif "sqlite" in driver_name:
        connect_args["check_same_thread"] = False

    engine = create_engine(
        primary_url,
        connect_args=connect_args,
        **engine_kwargs,
    )

    target_host = engine.url.host or "unknown"
    target_port = engine.url.port or 5432

    try:
        # Verify connection immediately upon startup if database service is reachable
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connected to PostgreSQL successfully on %s:%s.", target_host, target_port)
    except Exception as exc:
        err_str = str(exc).lower()
        if "password authentication failed" in err_str:
            logger.warning(
                "PostgreSQL authentication failed for user on %s:%s. "
                "Database persistence will be unavailable until credentials are resolved.",
                target_host, target_port,
            )
        else:
            logger.warning(
                "Could not connect to PostgreSQL on %s:%s (%s). "
                "Database persistence will be unavailable until the database service is reachable.",
                target_host, target_port, type(exc).__name__,
            )

    return engine


engine = _create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """FastAPI dependency for database session lifecycle with automatic rollback on error."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_health() -> dict:
    """Healthcheck helper for database status without exposing secrets or credentials."""
    target_host = engine.url.host or "unknown"
    target_port = engine.url.port or 5432
    backend_type = "sqlite" if "sqlite" in (engine.url.drivername or "") else "postgresql"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "backend": backend_type,
            "host": target_host,
            "port": target_port,
        }
    except Exception as exc:
        err_str = str(exc).lower()
        if "password authentication failed" in err_str:
            msg = "PostgreSQL authentication failed."
        elif "connection refused" in err_str or "could not connect" in err_str:
            msg = f"Could not connect to database on {target_host}:{target_port}."
        else:
            msg = f"Database error ({type(exc).__name__})."
        return {
            "status": "error",
            "backend": backend_type,
            "host": target_host,
            "port": target_port,
            "error": msg,
        }