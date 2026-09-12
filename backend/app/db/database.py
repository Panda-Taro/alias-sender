import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _create_engine():
    return create_engine(
        settings.sqlalchemy_url,
        connect_args={"check_same_thread": False},
    )


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def reopen_engine() -> None:
    """Re-open the SQLite connection after the DB file has been replaced
    (used by the DB import feature, REQ-H08)."""
    global engine, SessionLocal
    engine.dispose()
    engine = _create_engine()
    SessionLocal.configure(bind=engine)
    logger.info("Database engine re-opened after import")


def init_db() -> None:
    from app.db import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    logger.info("Database schema ensured (create_all)")


def get_session() -> Session:
    return SessionLocal()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
