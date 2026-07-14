from __future__ import annotations

import json

from sqlalchemy.orm import Session

from platform_db.config import get_settings
from platform_db.database import build_engine
from platform_db.importers.rc1 import import_rc1
from platform_db.services.security_catalog import bootstrap_initial_administrator, seed_security_catalog


def main() -> int:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    imported = import_rc1(engine, settings)
    with Session(engine) as session:
        catalog = seed_security_catalog(session, settings)
        administrator = bootstrap_initial_administrator(session, settings)
        session.commit()
    print(json.dumps({
        "rc1_import_job_id": str(imported.import_job_id),
        "rc1_duplicate": imported.duplicate_run,
        "catalog": catalog,
        "administrator_status": administrator["status"],
    }, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
