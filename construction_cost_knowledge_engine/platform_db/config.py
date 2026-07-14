from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ENGINE_ROOT.parent
DEFAULT_RUN = ENGINE_ROOT / "data/private/reference_extraction/runs/PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1"


@dataclass(frozen=True)
class Settings:
    database_url: str
    tenant_code: str
    rc1_manifest_path: Path
    project_root: Path
    session_idle_timeout_minutes: int
    session_absolute_timeout_hours: int
    session_cookie_secure: bool
    session_cookie_samesite: str
    session_cookie_name: str
    session_hash_secret: str
    auth_max_failed_attempts: int
    auth_failure_window_minutes: int
    auth_lockout_minutes: int
    bootstrap_admin_username: str
    bootstrap_admin_password: str
    bootstrap_admin_display_name: str
    quota_building_backend: str
    quota_building_sqlite_fallback_enabled: bool
    mapping_workspace_name: str = ""


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def get_settings() -> Settings:
    same_site = os.getenv("SESSION_COOKIE_SAMESITE", "lax").strip().lower()
    if same_site not in {"lax", "strict"}:
        same_site = "lax"
    quota_backend = os.getenv("QUOTA_BUILDING_BACKEND", "postgres").strip().lower()
    if quota_backend not in {"postgres", "sqlite"}:
        quota_backend = "postgres"
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://platform_dev:platform_dev_only@127.0.0.1:55432/construction_platform_rc1_dev",
        ),
        tenant_code=os.getenv("PLATFORM_TENANT_CODE", "platform-dev"),
        rc1_manifest_path=Path(os.getenv("RC1_MANIFEST_PATH", str(DEFAULT_RUN / "building_rc1_release_manifest.csv"))),
        project_root=Path(os.getenv("PLATFORM_PROJECT_ROOT", str(PROJECT_ROOT))),
        session_idle_timeout_minutes=_int_env("SESSION_IDLE_TIMEOUT_MINUTES", 30),
        session_absolute_timeout_hours=_int_env("SESSION_ABSOLUTE_TIMEOUT_HOURS", 12),
        session_cookie_secure=_bool_env("SESSION_COOKIE_SECURE", False),
        session_cookie_samesite=same_site,
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "ai_construction_session").strip() or "ai_construction_session",
        session_hash_secret=os.getenv("PLATFORM_SESSION_HASH_SECRET", ""),
        auth_max_failed_attempts=_int_env("AUTH_MAX_FAILED_ATTEMPTS", 5),
        auth_failure_window_minutes=_int_env("AUTH_FAILURE_WINDOW_MINUTES", 15),
        auth_lockout_minutes=_int_env("AUTH_LOCKOUT_MINUTES", 15),
        bootstrap_admin_username=os.getenv("PLATFORM_BOOTSTRAP_ADMIN_USERNAME", ""),
        bootstrap_admin_password=os.getenv("PLATFORM_BOOTSTRAP_ADMIN_PASSWORD", ""),
        bootstrap_admin_display_name=os.getenv("PLATFORM_BOOTSTRAP_ADMIN_DISPLAY_NAME", "Platform Administrator"),
        quota_building_backend=quota_backend,
        quota_building_sqlite_fallback_enabled=_bool_env("QUOTA_BUILDING_SQLITE_FALLBACK_ENABLED", True),
        mapping_workspace_name=os.getenv("PLATFORM_MAPPING_WORKSPACE_NAME", "").strip(),
    )
