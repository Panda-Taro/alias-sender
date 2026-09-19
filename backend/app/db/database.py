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


def _ensure_columns() -> None:
    """create_all()は既存テーブルへのカラム追加を反映しないため、モデルに
    追加されたカラムを不足分だけALTER TABLEで補う(REQ-E07,
    registration_source_port追加時の既存DBファイル互換のため)。"""
    with engine.connect() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        if "zone_rds_configs" not in tables:
            return
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(zone_rds_configs)")}
        if "registration_source_port" not in cols:
            conn.exec_driver_sql("ALTER TABLE zone_rds_configs ADD COLUMN registration_source_port INTEGER")
            conn.commit()
            logger.info("Migrated zone_rds_configs: added registration_source_port column")


def init_db() -> None:
    from app.db import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    logger.info("Database schema ensured (create_all)")


def get_session() -> Session:
    return SessionLocal()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
