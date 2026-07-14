from __future__ import annotations

import argparse
import csv
import os
import re
import secrets
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ENGINE_ROOT / ".env.platform.local"
REQUIRED_ENVIRONMENT = (
    "PLATFORM_TENANT_CODE",
    "PLATFORM_BOOTSTRAP_ADMIN_USERNAME",
    "PLATFORM_BOOTSTRAP_ADMIN_DISPLAY_NAME",
    "PLATFORM_BOOTSTRAP_ADMIN_PASSWORD",
    "PLATFORM_UAT_TEMP_PASSWORD",
    "SESSION_COOKIE_SECURE",
)


class RuntimePreflightError(RuntimeError):
    pass


@dataclass(frozen=True)
class PortListener:
    pid: int
    process_name: str


def load_local_environment(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        return REQUIRED_ENVIRONMENT
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            os.environ[key] = value
    return tuple(name for name in REQUIRED_ENVIRONMENT if not os.environ.get(name, "").strip())


def configure_process_environment() -> None:
    if os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower() != "false":
        raise RuntimePreflightError("SESSION_COOKIE_SECURE must be false for local HTTP")
    invalid_password_variables = tuple(
        name for name in (
            "PLATFORM_BOOTSTRAP_ADMIN_PASSWORD", "PLATFORM_UAT_TEMP_PASSWORD"
        ) if not 12 <= len(os.environ.get(name, "")) <= 1024
    )
    if invalid_password_variables:
        raise RuntimePreflightError(
            "Password policy failed for: " + ", ".join(invalid_password_variables)
        )
    os.environ.setdefault("QUOTA_BUILDING_BACKEND", "postgres")
    os.environ.setdefault("QUOTA_BUILDING_SQLITE_FALLBACK_ENABLED", "true")
    os.environ.setdefault("PLATFORM_PROJECT_ROOT", str(ENGINE_ROOT.parent))
    if not os.environ.get("PLATFORM_SESSION_HASH_SECRET", "").strip():
        os.environ["PLATFORM_SESSION_HASH_SECRET"] = secrets.token_urlsafe(48)


def _process_name(pid: int) -> str:
    try:
        output = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            check=False, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if output and not output.startswith("INFO:"):
            return next(csv.reader([output]))[0]
    except (OSError, subprocess.SubprocessError, StopIteration, csv.Error):
        pass
    return "unknown"


def find_port_listener(port: int) -> PortListener | None:
    try:
        output = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"], check=False,
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    pattern = re.compile(rf"^\s*TCP\s+\S*:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$", re.I)
    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            pid = int(match.group(1))
            return PortListener(pid=pid, process_name=_process_name(pid))
    return None


def verify_database_and_migrations() -> tuple[tuple[str, ...], tuple[str, ...]]:
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import text

    from platform_db.config import get_settings
    from platform_db.database import build_engine

    settings = get_settings()
    engine = build_engine(settings.database_url)
    config = Config(str(ENGINE_ROOT / "platform_db/alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    expected = tuple(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:
        if connection.scalar(text("SELECT 1")) != 1:
            raise RuntimePreflightError("PostgreSQL connectivity check failed")
        current = tuple(MigrationContext.configure(connection).get_current_heads())
    if current != expected:
        raise RuntimePreflightError("Alembic current revision is not head")
    return current, expected


def bootstrap_platform() -> dict[str, object]:
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from platform_db.config import get_settings
    from platform_db.database import build_engine
    from platform_db.importers.rc1 import import_rc1
    from platform_db.models import AppRole, AppSession, AppTenant, AppUser, AppUserRoleAssignment
    from platform_db.security import normalize_username
    from platform_db.services.security_catalog import bootstrap_initial_administrator, seed_security_catalog

    settings = get_settings()
    engine = build_engine(settings.database_url)
    imported = import_rc1(engine, settings)
    with Session(engine) as session:
        try:
            catalog = seed_security_catalog(session, settings)
            bootstrap = bootstrap_initial_administrator(session, settings)
            tenant = session.scalar(select(AppTenant).where(AppTenant.tenant_code == settings.tenant_code))
            user = session.scalar(select(AppUser).where(
                AppUser.tenant_id == tenant.tenant_id,
                AppUser.login_name_normalized == normalize_username(settings.bootstrap_admin_username),
                AppUser.is_service_account.is_(False),
            )) if tenant else None
            role_assigned = bool(user and session.scalar(select(func.count()).select_from(
                AppUserRoleAssignment
            ).join(AppRole, AppRole.app_role_id == AppUserRoleAssignment.app_role_id).where(
                AppUserRoleAssignment.tenant_id == tenant.tenant_id,
                AppUserRoleAssignment.app_user_id == user.app_user_id,
                AppUserRoleAssignment.status == "active",
                AppRole.role_code == "administrator",
            )))
            session_count = int(session.scalar(select(func.count()).select_from(AppSession).where(
                AppSession.tenant_id == tenant.tenant_id,
                AppSession.app_user_id == user.app_user_id,
            )) or 0) if tenant and user else 0
            if user is None or not role_assigned:
                raise RuntimePreflightError("Bootstrap administrator verification failed")
            result = {
                "bootstrap_status": bootstrap["status"],
                "user_created": bool(bootstrap["created"]),
                "must_change_password": bool(user.must_change_password),
                "role_assigned": role_assigned,
                "session_count": session_count,
                "catalog_permission_count": catalog["permission_count"],
                "rc1_duplicate": imported.duplicate_run,
            }
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise


def run(host: str, port: int, env_file: Path, check_only: bool) -> int:
    missing = load_local_environment(env_file)
    if missing:
        print("[ERROR] Missing environment variables: " + ", ".join(missing))
        return 3
    try:
        configure_process_environment()
    except RuntimePreflightError as exc:
        print(f"[ERROR] {exc}")
        return 3

    listener = find_port_listener(port)
    if listener is not None:
        print(f"[ERROR] Port {port} is occupied by PID {listener.pid} ({listener.process_name}).")
        return 4

    try:
        current, expected = verify_database_and_migrations()
        print(f"[OK] PostgreSQL connected; Alembic current=head ({','.join(current)}).")
        if check_only:
            return 0
        bootstrap = bootstrap_platform()
        print(
            "[OK] Administrator bootstrap: "
            f"status={bootstrap['bootstrap_status']}; "
            f"role_assigned={str(bootstrap['role_assigned']).lower()}; "
            f"must_change_password={str(bootstrap['must_change_password']).lower()}."
        )
    except Exception as exc:
        print(f"[ERROR] Runtime preflight failed ({type(exc).__name__}).")
        return 5

    print(f"Login:  http://{host}:{port}/login")
    print(f"Review: http://{host}:{port}/quota-building")
    print(f"Health: http://{host}:{port}/api/v1/platform/health")
    import uvicorn

    uvicorn.run("platform_db.web_app:app", host=host, port=port, log_level="info")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Local authenticated platform runtime")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8006)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    return run(args.host, args.port, args.env_file.resolve(), args.check_only)


if __name__ == "__main__":
    raise SystemExit(main())
