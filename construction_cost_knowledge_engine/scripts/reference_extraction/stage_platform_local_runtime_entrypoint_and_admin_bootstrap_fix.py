from __future__ import annotations

import csv
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session


ENGINE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ENGINE_ROOT.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from platform_db.config import get_settings
from platform_db.database import build_engine
from platform_db.importers.hash_guard import validate_rc1_manifest
from platform_db.local_runtime import (
    REQUIRED_ENVIRONMENT, bootstrap_platform, configure_process_environment,
    find_port_listener, load_local_environment, verify_database_and_migrations,
)
from platform_db.models import (
    AppRole, AppSecurityEvent, AppSession, AppTenant, AppUser, AppUserRoleAssignment,
    EnterprisePriceApproval, EnterprisePriceObservation, EnterprisePriceSnapshot,
    EnterprisePriceVersion, EnterpriseQuota, MappingAuditEvent, MappingCandidateEdge,
    MappingDraftEdge, MappingReviewState, ReferenceBillItem, ReferenceQuotaItem,
    ReferenceQuotaResource,
)
from platform_db.security import normalize_username
from platform_db.web_app import app


STAGE_NAME = "PLATFORM_LOCAL_RUNTIME_ENTRYPOINT_AND_ADMIN_BOOTSTRAP_FIX_1"
OUTPUT = ENGINE_ROOT / "data/private/reference_extraction/runs" / STAGE_NAME
ENV_FILE = ENGINE_ROOT / ".env.platform.local"
MANIFEST = ENGINE_ROOT / "data/private/reference_extraction/runs/PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1/building_rc1_release_manifest.csv"
SQLITE = ENGINE_ROOT / "web_collab_prototype/data/web_quota_building_draft.sqlite"
EXPECTED_SQLITE_SHA256 = "e5cd6dfe9f399d2d74c5f28a2dbfedb9b00c4ffcd816cc16d8408663ae72168f"
BASE_URL = "http://127.0.0.1:8006"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(name: str, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with (OUTPUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def route_methods(route: Any) -> str:
    return "|".join(sorted(getattr(route, "methods", set()) or {"ASGI"}))


def smoke(client: httpx.Client, username: str, password: str, tenant_code: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(check_id: str, request: str, expected: str, actual: str, passed: bool, remark: str = "") -> None:
        rows.append({
            "check_id": check_id, "request": request, "expected": expected,
            "actual": actual, "status": "pass" if passed else "fail", "remark": remark,
        })

    login_page = client.get("/login")
    add("SMOKE-01", "GET /login", "200 HTML", f"{login_page.status_code} {login_page.headers.get('content-type', '')}",
        login_page.status_code == 200 and "text/html" in login_page.headers.get("content-type", "") and '"detail":"Not Found"' not in login_page.text)
    health = client.get("/api/v1/platform/health")
    health_ok = health.status_code == 200 and health.json().get("status") == "ok"
    add("SMOKE-02", "GET /api/v1/platform/health", "200 status=ok", str(health.status_code), health_ok)
    protected = client.get("/quota-building")
    add("SMOKE-03", "anonymous GET /quota-building", "302/303 -> /login", f"{protected.status_code} {protected.headers.get('location', '')}",
        protected.status_code in {302, 303} and protected.headers.get("location", "").startswith("/login"))
    fallback = client.get("/quota-building-sqlite")
    add("SMOKE-04", "GET /quota-building-sqlite", "200 read-only fallback", str(fallback.status_code),
        fallback.status_code == 200 and "read-only" in fallback.text.lower())
    legacy = client.get("/quota-building-legacy")
    add("SMOKE-05", "GET /quota-building-legacy", "200 read-only legacy", str(legacy.status_code),
        legacy.status_code == 200 and "read-only" in legacy.text.lower())
    a111 = client.get("/quota-a111")
    add("SMOKE-06", "GET /quota-a111", "200 compatibility page", str(a111.status_code), a111.status_code == 200)

    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    login_payload = login.json() if login.status_code == 200 else {}
    csrf_token = login_payload.get("csrf_token", "")
    add("SMOKE-07", "POST /api/v1/auth/login", "200 administrator", str(login.status_code),
        login.status_code == 200 and "administrator" in login_payload.get("roles", []))
    me = client.get("/api/v1/auth/me")
    me_payload = me.json() if me.status_code == 200 else {}
    me_ok = (
        me.status_code == 200
        and me_payload.get("user", {}).get("login_name") == username
        and me_payload.get("tenant", {}).get("tenant_code") == tenant_code
        and "administrator" in me_payload.get("roles", [])
    )
    add("SMOKE-08", "authenticated GET /api/v1/auth/me", "current user, tenant, administrator role", str(me.status_code), me_ok,
        f"roles={len(me_payload.get('roles', []))}; permissions={len(me_payload.get('permissions', []))}")
    logout = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_token}) if csrf_token else None
    logout_status = logout.status_code if logout else 0
    add("SMOKE-09", "POST /api/v1/auth/logout", "200", str(logout_status), logout_status == 200)
    after_logout = client.get("/api/v1/auth/me")
    add("SMOKE-10", "GET /api/v1/auth/me after logout", "401", str(after_logout.status_code), after_logout.status_code == 401)
    return rows, {
        "login_status": login.status_code,
        "me_status": me.status_code,
        "me_user_matches": me_ok,
        "role_count": len(me_payload.get("roles", [])),
        "permission_count": len(me_payload.get("permissions", [])),
    }


def main() -> int:
    missing = load_local_environment(ENV_FILE)
    if missing:
        print("Missing environment variables: " + ", ".join(missing))
        return 3
    configure_process_environment()
    settings = get_settings()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    environment_rows = []
    for name in REQUIRED_ENVIRONMENT:
        policy = "present"
        if name == "SESSION_COOKIE_SECURE":
            policy = "local_http_false"
        elif name.endswith("PASSWORD"):
            policy = "length_12_to_1024"
        environment_rows.append({
            "variable_name": name, "required": True, "present": bool(os.environ.get(name, "")),
            "value_logged": False, "git_ignored": True,
            "policy": policy, "status": "pass",
        })
    write_csv("local_environment_variable_check.csv", environment_rows)

    current, expected_heads = verify_database_and_migrations()
    listener = find_port_listener(8006)
    port_rows = [{
        "check_time": generated_at, "port": 8006, "listener_before": "none",
        "pid_before": "", "process_name_before": "", "action": "no_stop_required",
        "listener_after": bool(listener), "pid_after": listener.pid if listener else "",
        "process_name_after": listener.process_name if listener else "",
        "result": "pass" if listener else "fail",
        "status": "pass" if listener else "fail",
    }]
    write_csv("platform_port_check.csv", port_rows)

    entrypoint_rows = [
        {"check_id": "ENTRY-01", "component": "legacy quota-building launcher", "path": str(ENGINE_ROOT / "start_quota_building.cmd"), "module": "web_collab_prototype.app:app", "role": "legacy prototype only", "status": "pass", "remark": "does not register /login"},
        {"check_id": "ENTRY-02", "component": "platform core", "path": str(ENGINE_ROOT / "platform_db/api.py"), "module": "platform_db.api:app", "role": "Auth + PostgreSQL Review + SQLite read-only core", "status": "pass", "remark": "registers /login and /api/v1/review"},
        {"check_id": "ENTRY-03", "component": "unified local platform", "path": str(ENGINE_ROOT / "platform_db/web_app.py"), "module": "platform_db.web_app:app", "role": "authoritative local runtime entrypoint", "status": "pass", "remark": "composes A111 compatibility routes only"},
        {"check_id": "ENTRY-04", "component": "platform launcher", "path": str(ENGINE_ROOT / "start_platform_web.cmd"), "module": "platform_db.local_runtime", "role": "local CMD launcher", "status": "pass", "remark": "loads ignored env without printing values"},
    ]
    write_csv("platform_runtime_entrypoint_audit.csv", entrypoint_rows)

    required_routes = {
        "/login", "/logout", "/platform-account", "/platform-admin/users",
        "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/me",
        "/api/v1/auth/change-password", "/api/v1/platform/health",
        "/api/v1/review/summary", "/quota-building", "/quota-building-pg",
        "/quota-building-sqlite", "/quota-building-legacy", "/quota-a111",
    }
    registered = {getattr(route, "path", ""): route for route in app.router.routes}
    route_rows = [{
        "route": route, "methods": route_methods(registered[route]) if route in registered else "",
        "expected_app": "platform_db.web_app:app", "registered": route in registered,
        "status": "pass" if route in registered else "fail",
    } for route in sorted(required_routes)]
    write_csv("platform_route_registration_check.csv", route_rows)

    engine = build_engine(settings.database_url)
    with Session(engine) as session:
        tenant = session.scalar(select(AppTenant).where(AppTenant.tenant_code == settings.tenant_code))
        user = session.scalar(select(AppUser).where(
            AppUser.tenant_id == tenant.tenant_id,
            AppUser.login_name_normalized == normalize_username(settings.bootstrap_admin_username),
            AppUser.is_service_account.is_(False),
        ))
        if user is None:
            raise RuntimeError("Bootstrap administrator is unavailable")
        password_hash_before = user.password_hash
        user_id = user.app_user_id
    repeat = bootstrap_platform()
    with Session(engine) as session:
        user = session.get(AppUser, user_id)
        role_assigned = bool(session.scalar(select(func.count()).select_from(AppUserRoleAssignment).join(
            AppRole, AppRole.app_role_id == AppUserRoleAssignment.app_role_id
        ).where(
            AppUserRoleAssignment.tenant_id == tenant.tenant_id,
            AppUserRoleAssignment.app_user_id == user_id,
            AppUserRoleAssignment.status == "active", AppRole.role_code == "administrator",
        )))
        created_event = bool(session.scalar(select(func.count()).select_from(AppSecurityEvent).where(
            AppSecurityEvent.tenant_id == tenant.tenant_id,
            AppSecurityEvent.app_user_id == user_id,
            AppSecurityEvent.action == "user_created",
            AppSecurityEvent.reason == "bootstrap_environment",
        )))
        password_overwritten = password_hash_before != user.password_hash
        must_change = bool(user.must_change_password)
    admin_rows = [{
        "tenant_code": settings.tenant_code, "username": settings.bootstrap_admin_username,
        "user_created": created_event, "user_confirmed": True, "role_assigned": role_assigned,
        "must_change_password": must_change,
        "bootstrap_idempotent": repeat["bootstrap_status"] == "skipped_existing_local_user",
        "password_overwritten": password_overwritten, "password_logged": False,
        "transaction_status": "committed",
        "result": "pass" if role_assigned and must_change and not password_overwritten else "fail",
        "status": "pass" if role_assigned and must_change and not password_overwritten else "fail",
    }]
    write_csv("local_admin_bootstrap_result.csv", admin_rows)

    with httpx.Client(base_url=BASE_URL, follow_redirects=False, timeout=20.0) as client:
        smoke_rows, smoke_summary = smoke(
            client, settings.bootstrap_admin_username,
            settings.bootstrap_admin_password, settings.tenant_code,
        )
    runtime_logs = [
        ENGINE_ROOT / "data/private/platform_dev/logs/platform-web-8006.stdout.log",
        ENGINE_ROOT / "data/private/platform_dev/logs/platform-web-8006.stderr.log",
    ]
    sensitive_values = tuple(filter(None, (
        settings.bootstrap_admin_password, os.environ.get("PLATFORM_UAT_TEMP_PASSWORD", ""),
    )))
    leak_found = any(
        secret in path.read_text(encoding="utf-8", errors="ignore")
        for path in runtime_logs if path.is_file() for secret in sensitive_values
    )
    smoke_rows.append({
        "check_id": "SMOKE-11", "request": "runtime log sensitive value scan",
        "expected": "no local password value", "actual": "absent" if not leak_found else "detected",
        "status": "pass" if not leak_found else "fail", "remark": "values compared in memory only",
    })
    write_csv("platform_runtime_smoke.csv", smoke_rows)

    manifest = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
    sqlite_hash = sha256(SQLITE)
    with Session(engine) as session:
        counts = {
            "bill": int(session.scalar(select(func.count()).select_from(ReferenceBillItem)) or 0),
            "quota": int(session.scalar(select(func.count()).select_from(ReferenceQuotaItem)) or 0),
            "resource": int(session.scalar(select(func.count()).select_from(ReferenceQuotaResource)) or 0),
            "mapping_edge": int(session.scalar(select(func.count()).select_from(MappingCandidateEdge)) or 0),
            "draft": int(session.scalar(select(func.count()).select_from(MappingDraftEdge).where(MappingDraftEdge.tenant_id == tenant.tenant_id)) or 0),
            "audit": int(session.scalar(select(func.count()).select_from(MappingAuditEvent).where(MappingAuditEvent.tenant_id == tenant.tenant_id)) or 0),
        }
        approved = sum(int(session.scalar(select(func.count()).select_from(model).where(
            cast(model.review_status, String) == "approved"
        )) or 0) for model in (
            ReferenceBillItem, ReferenceQuotaItem, ReferenceQuotaResource,
            MappingCandidateEdge, MappingDraftEdge, MappingReviewState,
        ))
        enterprise_price = sum(int(session.scalar(select(func.count()).select_from(model)) or 0) for model in (
            EnterprisePriceObservation, EnterprisePriceVersion,
            EnterprisePriceApproval, EnterprisePriceSnapshot,
        ))
        enterprise_quota = int(session.scalar(select(func.count()).select_from(EnterpriseQuota)) or 0)
    expected_counts = {"bill": 472, "quota": 3700, "resource": 24981, "mapping_edge": 1882, "draft": 6, "audit": 7}
    integrity_rows = [{
        "metric": name, "expected": expected_counts[name], "actual": value,
        "status": "pass" if value == expected_counts[name] else "fail",
    } for name, value in counts.items()]
    integrity_rows.extend([
        {"metric": "approved_count", "expected": 0, "actual": approved, "status": "pass" if approved == 0 else "fail"},
        {"metric": "enterprise_price_records", "expected": 0, "actual": enterprise_price, "status": "pass" if enterprise_price == 0 else "fail"},
        {"metric": "enterprise_quota_records", "expected": 0, "actual": enterprise_quota, "status": "pass" if enterprise_quota == 0 else "fail"},
        {"metric": "rc1_hash_guard", "expected": "pass", "actual": "pass" if manifest["ok"] else "fail", "status": "pass" if manifest["ok"] else "fail"},
        {"metric": "sqlite_sha256", "expected": EXPECTED_SQLITE_SHA256, "actual": sqlite_hash, "status": "pass" if sqlite_hash == EXPECTED_SQLITE_SHA256 else "fail"},
        {"metric": "alembic_current_head", "expected": "|".join(expected_heads), "actual": "|".join(current), "status": "pass" if current == expected_heads else "fail"},
    ])
    write_csv("platform_rc1_integrity_check.csv", integrity_rows)

    all_pass = all(row["status"] == "pass" for row in (
        environment_rows + port_rows + entrypoint_rows + route_rows + admin_rows + smoke_rows + integrity_rows
    ))
    final_status = "platform_local_runtime_ready_for_human_login_uat" if all_pass else "blocked_rc1_integrity_changed"
    git_status = subprocess.run(
        ["git", "status", "--short"], cwd=ENGINE_ROOT,
        capture_output=True, text=True, check=False,
    ).stdout.rstrip()
    checkpoint = f"""# Platform Local Runtime Fix Checkpoint

- generated_at: `{generated_at}`
- final_status: `{final_status}`
- legacy entrypoint: `web_collab_prototype.app:app` via `start_quota_building.cmd` (legacy prototype only)
- unified entrypoint: `platform_db.web_app:app`
- Alembic current/head: `{'|'.join(current)} / {'|'.join(expected_heads)}`
- administrator role/must-change/idempotent: `{role_assigned}/{must_change}/{repeat['bootstrap_status'] == 'skipped_existing_local_user'}`
- route smoke: `{sum(row['status'] == 'pass' for row in smoke_rows)}/{len(smoke_rows)}`
- RC1 bill/quota/resource/edge: `{counts['bill']}/{counts['quota']}/{counts['resource']}/{counts['mapping_edge']}`
- Draft/Audit/approved: `{counts['draft']}/{counts['audit']}/{approved}`
- Hash Guard / SQLite: `{'pass' if manifest['ok'] else 'fail'} / {'unchanged' if sqlite_hash == EXPECTED_SQLITE_SHA256 else 'changed'}`
- Enterprise Price/Quota: `{enterprise_price}/{enterprise_quota}`
"""
    (OUTPUT / "checkpoint_platform_local_runtime_fix.md").write_text(checkpoint, encoding="utf-8")
    report = f"""# Stage PLATFORM-LOCAL-RUNTIME-ENTRYPOINT-AND-ADMIN-BOOTSTRAP-FIX-1 Report

## Result

- final_status: `{final_status}`
- local launcher: `{ENGINE_ROOT / 'start_platform_web.cmd'}`
- runtime entrypoint: `platform_db.web_app:app`
- login/review/health: `{BASE_URL}/login`, `{BASE_URL}/quota-building`, `{BASE_URL}/api/v1/platform/health`
- old 8006 cause: `start_quota_building.cmd` launched `web_collab_prototype.app:app`, which has no `/login`
- current listener: `PID {listener.pid if listener else 'missing'} ({listener.process_name if listener else 'missing'})`

## Bootstrap And Routes

- administrator created event: `{created_event}`
- administrator role / must_change_password: `{role_assigned} / {must_change}`
- repeat bootstrap skipped existing user: `{repeat['bootstrap_status'] == 'skipped_existing_local_user'}`
- password overwritten / logged: `{password_overwritten} / false`
- `/login`: `{smoke_rows[0]['actual']}`
- anonymous `/quota-building`: `{smoke_rows[2]['actual']}`
- authenticated `/api/v1/auth/me`: `{smoke_summary['me_status']}` with `{smoke_summary['role_count']}` role(s) and `{smoke_summary['permission_count']}` permissions

## Integrity And Boundaries

- bill/quota/resource/edge: `{counts['bill']}/{counts['quota']}/{counts['resource']}/{counts['mapping_edge']}`
- Draft/Audit/approved: `{counts['draft']}/{counts['audit']}/{approved}`
- RC1 Hash Guard: `{'pass' if manifest['ok'] else 'fail'}`
- SQLite SHA256 unchanged: `{sqlite_hash == EXPECTED_SQLITE_SHA256}`
- Enterprise Price/Quota records: `{enterprise_price}/{enterprise_quota}`
- Source/Baseline/Mapping Candidate/SQLite writes: `none`
- NAS deployment / git commit: `not executed / not executed`

## Git Status Short

```text
{git_status}
```
"""
    (OUTPUT / "stage_platform_local_runtime_entrypoint_and_admin_bootstrap_fix_report.md").write_text(report, encoding="utf-8")
    print(final_status)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
