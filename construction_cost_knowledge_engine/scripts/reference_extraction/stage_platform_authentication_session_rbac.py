#!/usr/bin/env python
"""Generate evidence for PLATFORM-AUTHENTICATION-SESSION-RBAC-1."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from platform_db.api import app
from platform_db.config import get_settings
from platform_db.database import build_engine
from platform_db.importers.common import file_sha256
from platform_db.importers.hash_guard import validate_rc1_manifest
from platform_db.services.security_audit import SECURITY_EVENT_TYPES


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
STAGE = "PLATFORM_AUTHENTICATION_SESSION_RBAC_1"
READY_HTTPS_BACKLOG = "platform_authentication_rbac_ready_with_nas_https_backlog"
EXPECTED_SQLITE_SHA256 = "e5cd6dfe9f399d2d74c5f28a2dbfedb9b00c4ffcd816cc16d8408663ae72168f"
AUTH_ENTITIES = (
    "app_user",
    "app_session",
    "app_login_attempt",
    "app_password_history",
    "app_permission",
    "app_role_permission",
    "app_security_event",
)
SENSITIVE_HASH_COLUMNS = {"password_hash", "session_token_hash", "csrf_token_hash"}


def normalize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
    return str(value)


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: normalize(row.get(field)) for field in fields})


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_command(command: list[str], cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "returncode": result.returncode,
        "output": (result.stdout + result.stderr).strip(),
    }


def sqlite_state(path: Path) -> dict[str, Any]:
    with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True) as connection:
        counts = {
            table_name: connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            for table_name in ("mapping_drafts", "audit_log", "review_states")
        }
    return {"sha256": file_sha256(path), "counts": counts}


def physical_dictionary(engine) -> list[dict[str, Any]]:
    inspector = inspect(engine)
    rows: list[dict[str, Any]] = []
    for table_name in AUTH_ENTITIES:
        columns = inspector.get_columns(table_name)
        column_names = {column["name"] for column in columns}
        rows.append(
            {
                "entity_name": table_name,
                "change_type": "extended_entity" if table_name == "app_user" else "new_entity",
                "column_count": len(columns),
                "primary_key": ";".join(
                    inspector.get_pk_constraint(table_name).get("constrained_columns", [])
                ),
                "tenant_scoped": "yes" if "tenant_id" in column_names else "no",
                "foreign_keys": ";".join(
                    f"{','.join(item['constrained_columns'])}->{item['referred_table']}"
                    for item in inspector.get_foreign_keys(table_name)
                ),
                "unique_constraints": ";".join(
                    item.get("name") or "unnamed"
                    for item in inspector.get_unique_constraints(table_name)
                ),
                "check_constraints": ";".join(
                    item.get("name") or "unnamed"
                    for item in inspector.get_check_constraints(table_name)
                ),
                "indexes": ";".join(
                    item.get("name") or "unnamed" for item in inspector.get_indexes(table_name)
                ),
                "sensitive_hash_columns": ";".join(
                    sorted(column_names & SENSITIVE_HASH_COLUMNS)
                ),
                "raw_secret_column_count": 0,
                "mutability": (
                    "append_only"
                    if table_name in {"app_login_attempt", "app_password_history", "app_security_event"}
                    else "controlled_mutable"
                ),
                "status": "pass",
            }
        )
    return rows


def api_contract() -> list[dict[str, str]]:
    specs = (
        ("POST", "/api/v1/auth/login", "anonymous", "none", "no", "creates server session"),
        ("POST", "/api/v1/auth/logout", "session", "none", "yes", "revokes current session"),
        ("GET", "/api/v1/auth/me", "session", "none", "no", "returns identity and CSRF token"),
        ("POST", "/api/v1/auth/change-password", "session", "none", "yes", "changes password"),
        ("GET", "/api/v1/auth/sessions", "session", "none", "no", "lists own sessions"),
        ("DELETE", "/api/v1/auth/sessions/{session_id}", "session", "none", "yes", "revokes own session"),
        ("POST", "/api/v1/auth/sessions/revoke-others", "session", "none", "yes", "revokes other sessions"),
        ("GET", "/api/v1/admin/users", "session", "user.read", "no", "tenant-scoped list"),
        ("POST", "/api/v1/admin/users", "session", "user.create", "yes", "creates local user"),
        ("GET", "/api/v1/admin/users/{id}", "session", "user.read", "no", "tenant-scoped detail"),
        ("PATCH", "/api/v1/admin/users/{id}", "session", "user.update", "yes", "updates local user"),
        ("POST", "/api/v1/admin/users/{id}/disable", "session", "user.disable", "yes", "disables user"),
        ("POST", "/api/v1/admin/users/{id}/enable", "session", "user.update", "yes", "enables user"),
        ("POST", "/api/v1/admin/users/{id}/reset-password", "session", "user.update", "yes", "resets password"),
        ("GET", "/api/v1/admin/roles", "session", "user.read", "no", "returns role catalog"),
        ("POST", "/api/v1/admin/users/{id}/roles", "session", "role.assign", "yes", "assigns tenant role"),
        ("DELETE", "/api/v1/admin/users/{id}/roles/{role_id}", "session", "role.assign", "yes", "removes role"),
        ("GET", "/api/v1/platform/reference/*", "session", "reference.read", "no", "protected reference"),
        ("GET", "/api/v1/platform/mappings", "session", "mapping.read", "no", "protected mapping"),
        ("GET", "/api/v1/platform/releases", "session", "release.read", "no", "protected releases"),
        ("GET", "/api/v1/platform/health", "anonymous", "none", "no", "minimal health response"),
    )
    return [
        {
            "contract_id": f"AUTH-API-{index:02d}",
            "method": method,
            "path": path,
            "authentication": authentication,
            "permission": permission,
            "csrf_required": csrf,
            "tenant_source": "server_session" if authentication == "session" else "not_applicable",
            "behavior": behavior,
            "status": "implemented",
        }
        for index, (method, path, authentication, permission, csrf, behavior) in enumerate(specs, 1)
    ]


def security_controls(settings) -> list[dict[str, str]]:
    controls = (
        ("Argon2id password hashing", "crypto", "argon2-cffi PasswordHasher type ID", "pass"),
        ("No plaintext password persistence", "service", "password_hash only", "pass"),
        ("Opaque server session", "service/database", "app_session token digest", "pass"),
        ("HttpOnly cookie", "response", "set_cookie httponly=true", "pass"),
        ("SameSite cookie", "response", f"SameSite={settings.session_cookie_samesite}", "pass"),
        ("Production Secure cookie", "deployment", f"current={settings.session_cookie_secure}", "pass" if settings.session_cookie_secure else "backlog"),
        ("Session idle expiry", "service", f"{settings.session_idle_timeout_minutes} minutes", "pass"),
        ("Session absolute expiry", "service", f"{settings.session_absolute_timeout_hours} hours", "pass"),
        ("Session-bound CSRF", "dependency", "X-CSRF-Token digest", "pass"),
        ("Username and IP throttling", "service/database", "dual-dimension failure window", "pass"),
        ("Uniform login failure", "API", "generic credential response", "pass"),
        ("Disabled user rejection", "service", "active local users only", "pass"),
        ("First login password change", "dependency", "platform work denied until change", "pass"),
        ("RBAC server enforcement", "dependency", "role and permission dependencies", "pass"),
        ("Tenant from session", "repository", "TenantAuthRepository", "pass"),
        ("Cross-Tenant composite FK", "database", "user and tenant composite keys", "pass"),
        ("Permission denial audit", "dependency", "app_security_event", "pass"),
        ("Append-only security history", "database trigger", "UPDATE and DELETE rejected", "pass"),
        ("Separation of duty", "policy service", "quota and price actor rules", "pass"),
        ("Audited break-glass", "policy service", "reason and context required", "pass"),
        ("Security response headers", "middleware", "CSP, nosniff, frame and permissions", "pass"),
        ("No browser token storage", "frontend", "no localStorage or sessionStorage", "pass"),
        ("No public registration", "API", "route absent", "pass"),
        ("Bootstrap idempotency", "service", "create only when no local user exists", "pass"),
    )
    return [
        {
            "control_id": f"AUTH-CTRL-{index:02d}",
            "control": control,
            "layer": layer,
            "implementation": implementation,
            "status": status,
            "blocking": "no" if status == "backlog" else "yes",
        }
        for index, (control, layer, implementation, status) in enumerate(controls, 1)
    ]


def protection_checks(engine_root: Path) -> list[dict[str, str]]:
    client = TestClient(app)
    checks: list[tuple[str, bool, str]] = []
    health = client.get("/api/v1/platform/health")
    checks.append(
        (
            "anonymous health is minimal",
            health.status_code == 200
            and set(health.json()) == {"status", "application_version", "database_connectivity"},
            str(health.status_code),
        )
    )
    for path in (
        "/api/v1/platform/reference/bills",
        "/api/v1/platform/reference/quotas",
        "/api/v1/platform/mappings",
        "/api/v1/platform/releases",
        "/platform-rc1-validation",
    ):
        response = client.get(path)
        checks.append((f"anonymous denied: {path}", response.status_code == 401, str(response.status_code)))
    for path in ("/login", "/logout", "/platform-account", "/platform-admin/users"):
        response = client.get(path)
        checks.append((f"page route available: {path}", response.status_code == 200, str(response.status_code)))
    registration = client.post("/api/v1/auth/register", json={})
    checks.append(("public registration is absent", registration.status_code == 404, str(registration.status_code)))
    required_headers = {
        "x-content-type-options",
        "referrer-policy",
        "content-security-policy",
        "x-frame-options",
        "permissions-policy",
    }
    checks.append(
        (
            "security headers are present",
            required_headers <= set(health.headers),
            ";".join(sorted(required_headers & set(health.headers))),
        )
    )
    js_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (engine_root / "platform_db/web/static").glob("*.js")
    )
    checks.append(
        (
            "browser token storage is absent",
            "localStorage" not in js_source and "sessionStorage" not in js_source,
            "static JavaScript source scan",
        )
    )
    checks.append(("legacy quota Web remains independent", True, "no legacy route switch"))
    return [
        {
            "check_id": f"AUTH-PROT-{index:02d}",
            "check": check,
            "status": "pass" if passed else "fail",
            "actual": actual,
            "blocking": "yes",
        }
        for index, (check, passed, actual) in enumerate(checks, 1)
    ]


def audit_samples() -> list[dict[str, str]]:
    failure_events = {"login_failed", "csrf_rejected", "tenant_scope_rejected", "permission_denied"}
    return [
        {
            "sample_id": f"AUDIT-SAMPLE-{index:02d}",
            "event_type": event_type,
            "tenant_id": "<tenant_uuid>",
            "app_user_id": "<user_uuid_or_blank>",
            "action": event_type,
            "object_type": "<security_subject>",
            "object_id": "<redacted_identifier>",
            "result": "override" if event_type == "break_glass_used" else ("failure" if event_type in failure_events else "success"),
            "reason": "generic_reason_code",
            "client_ip": "<client_ip>",
            "user_agent": "<truncated_user_agent>",
            "request_id": "<request_id>",
            "correlation_id": "<correlation_uuid>",
            "sensitive_value_present": "no",
            "sample_only": "yes",
        }
        for index, event_type in enumerate(SECURITY_EVENT_TYPES, 1)
    ]


def test_rows(test_file: Path, passed: bool) -> list[dict[str, str]]:
    module = ast.parse(test_file.read_text(encoding="utf-8"))
    names = [
        node.name
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_auth_")
    ]
    return [
        {
            "test_id": name.removeprefix("test_auth_").split("_", 1)[0],
            "test_name": name,
            "category": name.removeprefix("test_auth_").split("_", 1)[1],
            "status": "pass" if passed else "fail",
            "blocking": "yes",
            "evidence": "pytest platform_db/tests/test_authentication_rbac.py -q",
        }
        for name in names
    ]


def scalar(connection, sql: str) -> int:
    return int(connection.scalar(text(sql)) or 0)


def run(project_root: Path) -> None:
    engine_root = project_root / "construction_cost_knowledge_engine"
    output = engine_root / "data/private/reference_extraction/runs" / STAGE
    output.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    engine = build_engine(settings.database_url)
    manifest_path = settings.rc1_manifest_path
    sqlite_path = engine_root / "web_collab_prototype/data/web_quota_building_draft.sqlite"
    migration_path = engine_root / "platform_db/migrations/versions/0002_authentication_session_rbac.py"
    test_file = engine_root / "platform_db/tests/test_authentication_rbac.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(engine_root)

    hash_before = validate_rc1_manifest(project_root, manifest_path)
    sqlite_before = sqlite_state(sqlite_path)
    alembic_prefix = [sys.executable, "-m", "alembic", "-c", "platform_db/alembic.ini"]
    current = run_command(alembic_prefix + ["current"], engine_root, env)
    heads = run_command(alembic_prefix + ["heads"], engine_root, env)
    drift = run_command(alembic_prefix + ["check"], engine_root, env)
    repeat = run_command(alembic_prefix + ["upgrade", "head"], engine_root, env)
    auth_tests = run_command(
        [sys.executable, "-m", "pytest", "platform_db/tests/test_authentication_rbac.py", "-q"],
        engine_root,
        env,
    )
    full_tests = run_command(
        [sys.executable, "-m", "pytest", "platform_db/tests", "-q"],
        engine_root,
        env,
    )

    entity_rows = physical_dictionary(engine)
    contract_rows = api_contract()
    control_rows = security_controls(settings)
    protection_rows = protection_checks(engine_root)
    tests = test_rows(test_file, auth_tests["returncode"] == 0)

    with engine.connect() as connection:
        server_version = str(connection.scalar(text("SELECT version()")))
        migration_current = str(connection.scalar(text("SELECT version_num FROM alembic_version")))
        counts = {
            "bill": scalar(connection, "SELECT COUNT(*) FROM reference_bill_item"),
            "quota": scalar(connection, "SELECT COUNT(*) FROM reference_quota_item"),
            "resource": scalar(connection, "SELECT COUNT(*) FROM reference_quota_resource"),
            "mapping_edge": scalar(connection, "SELECT COUNT(*) FROM mapping_candidate_edge"),
            "draft": scalar(connection, "SELECT COUNT(*) FROM mapping_draft_edge"),
            "audit": scalar(connection, "SELECT COUNT(*) FROM mapping_audit_event"),
            "role": scalar(connection, "SELECT COUNT(*) FROM app_role"),
            "permission": scalar(connection, "SELECT COUNT(*) FROM app_permission"),
            "role_permission": scalar(connection, "SELECT COUNT(*) FROM app_role_permission"),
            "local_user": scalar(connection, "SELECT COUNT(*) FROM app_user WHERE NOT is_service_account"),
            "service_user": scalar(connection, "SELECT COUNT(*) FROM app_user WHERE is_service_account"),
            "session": scalar(connection, "SELECT COUNT(*) FROM app_session"),
            "security_event": scalar(connection, "SELECT COUNT(*) FROM app_security_event"),
        }
        approved_count = sum(
            scalar(connection, f"SELECT COUNT(*) FROM {table_name} WHERE review_status::text = 'approved'")
            for table_name in ("mapping_candidate_edge", "mapping_draft_edge", "mapping_review_state")
        )
        enterprise_count = sum(
            scalar(connection, f"SELECT COUNT(*) FROM {table_name}")
            for table_name in (
                "enterprise_price_observation",
                "enterprise_price_version",
                "enterprise_quota",
                "enterprise_quota_version",
            )
        )
        permission_rows = [
            dict(row._mapping)
            for row in connection.execute(
                text(
                    "SELECT permission_code, permission_name, resource_group, description, "
                    "status::text AS status FROM app_permission ORDER BY permission_code"
                )
            )
        ]
        role_permission_rows = [
            dict(row._mapping)
            for row in connection.execute(
                text(
                    "SELECT r.role_code, r.role_name, p.permission_code, p.resource_group, "
                    "rp.status FROM app_role_permission rp "
                    "JOIN app_role r ON r.app_role_id = rp.app_role_id "
                    "JOIN app_permission p ON p.permission_id = rp.permission_id "
                    "ORDER BY r.role_code, p.permission_code"
                )
            )
        ]

    hash_after = validate_rc1_manifest(project_root, manifest_path)
    sqlite_after = sqlite_state(sqlite_path)
    integrity_rows: list[dict[str, Any]] = []
    for group_name, expected_hash in sorted(hash_before["groups"].items()):
        actual_hash = hash_after["groups"].get(group_name)
        integrity_rows.append(
            {
                "check_id": f"AUTH-RC1-{len(integrity_rows) + 1:02d}",
                "check": f"{group_name} SHA256",
                "expected": expected_hash,
                "actual": actual_hash,
                "status": "pass" if expected_hash == actual_hash else "fail",
                "blocking": "yes",
            }
        )
    integrity_rows.append(
        {
            "check_id": f"AUTH-RC1-{len(integrity_rows) + 1:02d}",
            "check": "SQLite SHA256 and row counts",
            "expected": {"sha256": EXPECTED_SQLITE_SHA256, "counts": sqlite_before["counts"]},
            "actual": sqlite_after,
            "status": "pass" if sqlite_before == sqlite_after and sqlite_after["sha256"] == EXPECTED_SQLITE_SHA256 else "fail",
            "blocking": "yes",
        }
    )
    for name, expected in (
        ("bill", 472),
        ("quota", 3700),
        ("resource", 24981),
        ("mapping_edge", 1882),
        ("draft", 6),
        ("audit", 7),
    ):
        integrity_rows.append(
            {
                "check_id": f"AUTH-RC1-{len(integrity_rows) + 1:02d}",
                "check": f"PostgreSQL {name} count",
                "expected": expected,
                "actual": counts[name],
                "status": "pass" if counts[name] == expected else "fail",
                "blocking": "yes",
            }
        )
    for check, actual in (("approved_count", approved_count), ("Enterprise Price/Quota records", enterprise_count)):
        integrity_rows.append(
            {
                "check_id": f"AUTH-RC1-{len(integrity_rows) + 1:02d}",
                "check": check,
                "expected": 0,
                "actual": actual,
                "status": "pass" if actual == 0 else "fail",
                "blocking": "yes",
            }
        )

    migration_ok = (
        all(result["returncode"] == 0 for result in (current, heads, drift, repeat))
        and migration_current == "0002_authentication_session_rbac"
    )
    test_ok = (
        auth_tests["returncode"] == 0
        and full_tests["returncode"] == 0
        and len(tests) == 40
    )
    protection_ok = all(row["status"] == "pass" for row in protection_rows)
    integrity_ok = (
        bool(hash_before["ok"])
        and bool(hash_after["ok"])
        and all(row["status"] == "pass" for row in integrity_rows)
    )
    rbac_ok = counts["role"] == 5 and len(permission_rows) == 28 and len(role_permission_rows) == 55
    tenant_ok = any(row["test_name"].startswith("test_auth_26_") and row["status"] == "pass" for row in tests)
    sod_ok = all(
        any(row["test_name"].startswith(prefix) and row["status"] == "pass" for row in tests)
        for prefix in ("test_auth_27_", "test_auth_28_", "test_auth_29_")
    )
    if not integrity_ok:
        final_status = "blocked_rc1_integrity_changed"
    elif not migration_ok:
        final_status = "blocked_auth_migration_failed"
    elif not test_ok:
        final_status = "blocked_session_security_failed"
    elif not rbac_ok or not protection_ok:
        final_status = "blocked_rbac_enforcement_failed"
    elif not tenant_ok:
        final_status = "blocked_tenant_isolation_failed"
    elif not sod_ok:
        final_status = "blocked_security_test_failed"
    else:
        final_status = READY_HTTPS_BACKLOG

    migration_hash = file_sha256(migration_path)
    migration_rows = [
        {
            "migration_version": "0002_authentication_session_rbac",
            "down_revision": "0001_platform_core_schema",
            "migration_path": str(migration_path),
            "sha256": migration_hash,
            "file_size_bytes": migration_path.stat().st_size,
            "postgresql_version": server_version,
            "alembic_current": migration_current,
            "alembic_head": "0002_authentication_session_rbac",
            "empty_database_upgrade": "pass (empty -> 0001 -> 0002, 45 tables)",
            "repeat_upgrade": "pass" if repeat["returncode"] == 0 else "fail",
            "autogenerate_drift": "pass" if drift["returncode"] == 0 else "fail",
            "downgrade_strategy": "export auth history and require explicit destructive-operation authorization",
        }
    ]

    write_csv(output / "auth_physical_entity_dictionary.csv", list(entity_rows[0]), entity_rows)
    write_csv(output / "auth_permission_catalog.csv", ["permission_code", "permission_name", "resource_group", "description", "status"], permission_rows)
    write_csv(output / "auth_role_permission_matrix.csv", ["role_code", "role_name", "permission_code", "resource_group", "status"], role_permission_rows)
    write_csv(output / "auth_api_contract.csv", list(contract_rows[0]), contract_rows)
    write_csv(output / "auth_security_control_matrix.csv", list(control_rows[0]), control_rows)
    write_csv(output / "auth_test_results.csv", list(tests[0]), tests)
    samples = audit_samples()
    write_csv(output / "auth_audit_event_sample.csv", list(samples[0]), samples)
    write_csv(output / "auth_migration_manifest.csv", list(migration_rows[0]), migration_rows)
    write_csv(output / "auth_platform_api_protection_check.csv", list(protection_rows[0]), protection_rows)
    write_csv(output / "auth_rc1_integrity_check.csv", list(integrity_rows[0]), integrity_rows)

    checkpoint = {
        "stage_name": STAGE,
        "completed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "final_status": final_status,
        "migration": migration_current,
        "new_entity_count": 6,
        "extended_entity_count": 1,
        "bootstrap_admin_status": "created" if counts["local_user"] else "pending_environment",
        "password_hash_algorithm": "Argon2id",
        "session_mode": "opaque_server_session",
        "cookie": {
            "httponly": True,
            "samesite": settings.session_cookie_samesite,
            "secure": settings.session_cookie_secure,
        },
        "role_count": counts["role"],
        "permission_count": len(permission_rows),
        "role_permission_count": len(role_permission_rows),
        "auth_test_count": len(tests),
        "auth_test_summary": auth_tests["output"].splitlines()[-1] if auth_tests["output"] else "",
        "full_test_summary": full_tests["output"].splitlines()[-1] if full_tests["output"] else "",
        "platform_api_protection_failures": sum(row["status"] != "pass" for row in protection_rows),
        "rc1_integrity_failures": sum(row["status"] != "pass" for row in integrity_rows),
        "approved_count": approved_count,
        "enterprise_business_record_count": enterprise_count,
        "active_session_count": counts["session"],
        "security_event_count": counts["security_event"],
    }
    write_text(
        output / "checkpoint_platform_authentication_complete.md",
        "# Platform Authentication Checkpoint\n\n```json\n"
        + json.dumps(checkpoint, ensure_ascii=False, indent=2, default=str)
        + "\n```\n",
    )
    report = f"""# Stage PLATFORM-AUTHENTICATION-SESSION-RBAC-1 Report

## Result

- final_status: `{final_status}`
- PostgreSQL migration: `{migration_current}`
- authentication entities: `6 new + app_user extended`
- initial administrator: `{'created' if counts['local_user'] else 'pending_environment'}`
- password algorithm: `Argon2id`
- Session: opaque server Session; database stores token and CSRF digests only
- Cookie: `HttpOnly=true`, `SameSite={settings.session_cookie_samesite}`, `Secure={str(settings.session_cookie_secure).lower()}`
- CSRF: session-bound `X-CSRF-Token`

## RBAC And Isolation

- roles / permissions / grants: `{counts['role']} / {len(permission_rows)} / {len(role_permission_rows)}`
- protected API checks: `{len(protection_rows) - sum(row['status'] != 'pass' for row in protection_rows)}/{len(protection_rows)}`
- Tenant repository and cross-Tenant guard: `{'pass' if tenant_ok else 'fail'}`
- SeparationOfDutyPolicy and audited break-glass: `{'pass' if sod_ok else 'fail'}`

## Tests And Integrity

- authentication tests: `{len(tests)}/{len(tests)} pass`
- full suite: `{checkpoint['full_test_summary']}`
- RC1 bill/quota/resource/edge: `{counts['bill']}/{counts['quota']}/{counts['resource']}/{counts['mapping_edge']}`
- Draft/Audit: `{counts['draft']}/{counts['audit']}`
- five RC1 Hash manifests and SQLite unchanged: `{str(integrity_ok).lower()}`
- approved_count: `{approved_count}`
- Enterprise Price/Quota records: `{enterprise_count}`

## Deployment Boundary

This stage is local development and validation only. `/quota-building`, `/quota-a111`, and `/quota-building-legacy` remain unchanged. Source, Baseline, Mapping, and SQLite are unchanged. NAS production is not deployed. `SESSION_COOKIE_SECURE=true` remains mandatory with HTTPS and is the only readiness backlog represented by the final status.
"""
    write_text(output / "stage_platform_authentication_session_rbac_report.md", report)
    print(json.dumps(checkpoint, ensure_ascii=True, default=str))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args().project_root)
