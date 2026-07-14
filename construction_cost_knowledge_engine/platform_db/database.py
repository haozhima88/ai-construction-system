from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings


def build_engine(database_url: str | None = None, *, echo: bool = False) -> Engine:
    return create_engine(database_url or get_settings().database_url, echo=echo, pool_pre_ping=True)


def session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or build_engine(), expire_on_commit=False)


def session_scope(factory: sessionmaker[Session] | None = None) -> Iterator[Session]:
    local_factory = factory or session_factory()
    session = local_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

