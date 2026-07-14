from __future__ import annotations

import argparse
import os
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import uvicorn
from sqlalchemy import select
from sqlalchemy.orm import Session

ENGINE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ENGINE_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Rollback-only browser UAT server for spreadsheet Draft editing")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8020)
    parser.add_argument("--env-file", type=Path, default=ENGINE_ROOT / ".env.platform.local")
    args = parser.parse_args()

    # Settings are instantiated while the application module is imported, so
    # the local environment must be loaded before any platform module import.
    from platform_db.local_runtime import configure_process_environment, load_local_environment

    missing = load_local_environment(args.env_file)
    if missing:
        raise RuntimeError("Missing local UAT environment variables: " + ", ".join(missing))
    configure_process_environment()

    from platform_db.api import app
    from platform_db.database import build_engine
    from platform_db.dependencies import get_db_session
    from platform_db.models import AppUser
    from platform_db.security import hash_password

    engine = build_engine()
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    users = list(session.scalars(select(AppUser).where(AppUser.login_name.in_(("uat_viewer", "uat_editor")))))
    for user in users:
        user.status = "active"
        user.lockout_until = None
        user.must_change_password = False
        user.password_hash = hash_password(os.environ["PLATFORM_UAT_TEMP_PASSWORD"])
    session.flush()
    # FastAPI may enter and finalize a sync generator dependency on different
    # worker threads; a primitive Lock can therefore be released safely by the
    # finalizer thread, unlike an owner-bound RLock.
    request_lock = threading.Lock()

    def rollback_only_session() -> Iterator[Session]:
        # A browser loads several authenticated resources concurrently. They
        # must be serialized because all rollback-only requests intentionally
        # share one PostgreSQL connection and outer transaction.
        request_lock.acquire()
        savepoint = session.begin_nested()
        try:
            yield session
            session.flush()
            savepoint.commit()
        except Exception:
            if savepoint.is_active:
                savepoint.rollback()
            session.expire_all()
            raise
        finally:
            request_lock.release()

    app.dependency_overrides[get_db_session] = rollback_only_session
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        if outer_transaction.is_active:
            outer_transaction.rollback()
        session.close()
        connection.close()
        engine.dispose()


if __name__ == "__main__":
    main()
