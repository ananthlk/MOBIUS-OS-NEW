"""
PostgreSQL connection via SQLAlchemy with psycopg3.

This is the authoritative system of record for all PRD entities.
"""

from sqlalchemy import create_engine, event, text
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
            pool_recycle=300,  # Recycle connections every 5 minutes
            pool_reset_on_return="rollback",  # Auto-rollback when connection returns to pool
        )
        
        # Add event listener to rollback any pending transaction when checking out
        @event.listens_for(_engine, "checkout")
        def checkout_listener(dbapi_conn, connection_record, connection_proxy):
            """Ensure connection is in clean state when checked out."""
            try:
                # Execute ROLLBACK to clear any pending transaction state
                cursor = dbapi_conn.cursor()
                cursor.execute("ROLLBACK")
                cursor.close()
            except Exception:
                pass  # Ignore errors - connection might already be clean
    
    return _engine


def get_db_session():
    """Get a scoped database session.
    
    Returns the thread-local session from the scoped session factory.
    The session is cleaned up at the end of each request via close_db_session().
    """
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
    """Remove the current session (call at end of request).
    
    Always rollback to ensure clean state for next request,
    then remove the session from the registry.
    """
    if _session_factory is not None:
        try:
            # Always rollback - if there was a commit, this is a no-op
            # If there was an error, this cleans up the transaction
            _session_factory.rollback()
        except Exception:
            pass
        finally:
            try:
                _session_factory.remove()
            except Exception:
                pass


def rollback_session():
    """Explicitly rollback the current session.
    
    Call this at the start of a request to ensure clean state,
    especially after a previous request may have left the session dirty.
    """
    if _session_factory is not None:
        try:
            session = _session_factory()
            # Only rollback if there's something to rollback
            if session.is_active:
                session.rollback()
        except Exception:
            # If the session is in a really bad state, remove it entirely
            try:
                _session_factory.remove()
            except Exception:
                pass


# Alias for convenience
db = Base
