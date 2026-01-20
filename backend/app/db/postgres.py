"""
PostgreSQL connection via SQLAlchemy with psycopg3.

This is the authoritative system of record for all PRD entities.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

from app.config import config

# SQLAlchemy base for model declarations
Base = declarative_base()

# Engine and session factory (initialized lazily)
_engine = None
_session_factory = None


def get_engine():
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        # Use psycopg3 dialect
        db_url = config.get_database_url().replace(
            "postgresql://", "postgresql+psycopg://"
        )
        _engine = create_engine(
            db_url,
            echo=config.DEBUG,  # Log SQL in debug mode
            pool_pre_ping=True,  # Verify connections before use
        )
    return _engine


def get_db_session():
    """Get a scoped database session."""
    global _session_factory
    if _session_factory is None:
        _session_factory = scoped_session(
            sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
        )
    return _session_factory()


def init_db():
    """Initialize database tables (for development/testing)."""
    # Import models so they register with Base.metadata
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def close_db_session(exception=None):
    """Remove the current session (call at end of request)."""
    if _session_factory is not None:
        _session_factory.remove()


# Alias for convenience
db = Base
