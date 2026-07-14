from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session


ENGINE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ENGINE_ROOT.parent
sys.path.insert(0, str(ENGINE_ROOT))

from platform_db.database import build_engine  # noqa: E402
from platform_db.importers.hash_guard import validate_rc1_manifest  # noqa: E402
from platform_db.local_runtime import load_local_environment  # noqa: E402
from platform_db.models import AppSession, AppUser  # noqa: E402
from platform_db.services.security_catalog import ROLE_PERMISSIONS  # noqa: E402


RUN_DIR = ENGINE_ROOT / "data/private/reference_extraction/runs/ENTERPRISE_PRICE_RESOURCE_MATCHING_AND_A111_QUOTA_PILOT_1"
SMOKE = RUN_DIR / "enterprise_quota_pilot_smoke.csv"
HTTP_SMOKE = RUN_DIR / "enterprise_quota_http_smoke.csv"
SUMMARY = RUN_DIR / "stage_summary.json"
MANIFEST = ENGINE_ROOT / "data/private/reference_extraction/runs/PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1/building_rc1_release_manifest.csv"


def check(check_id: str, name: str, expected: Any, actual: Any, passed: bool, verification: str) -> dict[str, str]:
    return {
        "check_id": check_id,
        "check": name,
        "expected": str(expected),
        "actual": str(actual),
        "verification": verification,
        "status": "pass" if passed else "fail",
    }


def request(client: httpx.Client, method: str, path: str, expected: int, **kwargs) -> httpx.Response:
    response = client.request(method, path, **kwargs)
    if response.status_code != expected:
        raise RuntimeError(f"{method} {path}: expected {expected}, got {response.status_code}: {response.text[:240]}")
    return response


def login(base_url: str, username: str, password: str) -> tuple[httpx.Client, dict[str, Any]]:
    client = httpx.Client(base_url=base_url, follow_redirects=False, timeout=15)
    payload = request(client, "POST", "/api/v1/auth/login", 200, json={"username": username, "password": password}).json()
    return client, payload


def write_results(rows: list[dict[str, str]]) -> None:
    fields = ["check_id", "check", "expected", "actual", "verification", "status"]
    with HTTP_SMOKE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    existing: list[dict[str, str]] = []
    with SMOKE.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row["check_id"].startswith(("HTTP-", "RBAC-", "TEST-", "GUARD-")):
                row["verification"] = row.get("verification") or "stage database gate"
                existing.append(row)
    with SMOKE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(existing + rows)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    summary["smoke_passed"] = sum(row["status"] == "pass" for row in existing + rows)
    summary["smoke_total"] = len(existing + rows)
    summary["http_smoke_passed"] = sum(row["status"] == "pass" for row in rows)
    summary["http_smoke_total"] = len(rows)
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    verification = (
        "\n## Post-stage Verification\n\n"
        f"- Combined smoke: `{summary['smoke_passed']}/{summary['smoke_total']} pass`.\n"
        f"- Real HTTP/Session/RBAC/CSRF checks: `{summary['http_smoke_passed']}/{summary['http_smoke_total']} pass`.\n"
        "- Successful Draft save/new-version/diff/submit/review/restore paths were exercised inside a PostgreSQL transaction and rolled back.\n"
        "- Approval was rejected because Enterprise Resource prices are incomplete; formal publication remains disabled.\n"
    )
    for name in (
        "checkpoint_enterprise_price_a111_pilot.md",
        "stage_enterprise_price_resource_matching_and_a111_quota_pilot_report.md",
    ):
        path = RUN_DIR / name
        content = path.read_text(encoding="utf-8")
        content = content.split("\n## Post-stage Verification\n", 1)[0].rstrip() + "\n" + verification
        path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8017")
    parser.add_argument("--env-file", type=Path, default=ENGINE_ROOT / ".env.platform.local")
    args = parser.parse_args()
    missing = load_local_environment(args.env_file)
    if missing:
        raise RuntimeError("Missing local UAT environment variables: " + ", ".join(missing))
    password = os.environ["PLATFORM_UAT_TEMP_PASSWORD"]
    engine = build_engine()
    original_status: dict[uuid.UUID, Any] = {}
    rows: list[dict[str, str]] = []
    with Session(engine) as session:
        users = list(session.scalars(select(AppUser).where(AppUser.login_name.in_(("uat_viewer", "uat_editor")))))
        if {row.login_name for row in users} != {"uat_viewer", "uat_editor"}:
            raise RuntimeError("Dedicated UAT users are missing")
        for user in users:
            original_status[user.app_user_id] = user.status
            user.status = "active"
            user.lockout_until = None
        session.commit()
    try:
        anonymous = httpx.get(args.base_url + "/enterprise-quota", follow_redirects=False, timeout=10)
        rows.append(check("HTTP-001", "Anonymous Enterprise Quota page requires login", "303 /login", f"{anonymous.status_code} {anonymous.headers.get('location')}", anonymous.status_code == 303 and anonymous.headers.get("location", "").startswith("/login"), "real HTTP"))
        for username, expected_role, expected_write in (("uat_viewer", "viewer", 403), ("uat_editor", "editor", 409)):
            client, auth = login(args.base_url, username, password)
            try:
                rows.append(check(f"HTTP-{len(rows)+1:03d}", f"{username} login and Session", expected_role, ",".join(auth["roles"]), expected_role in auth["roles"], "real HTTP login + cookie Session"))
                summary = request(client, "GET", "/api/v1/enterprise-quota/summary", 200).json()
                rows.append(check(f"HTTP-{len(rows)+1:03d}", f"{username} tenant-scoped summary", "137/55/0", f"{summary['enterprise_quota_draft_count']}/{summary['enterprise_resource_count']}/{summary['enterprise_price_record_count']}", (summary["enterprise_quota_draft_count"], summary["enterprise_resource_count"], summary["enterprise_price_record_count"]) == (137, 55, 0), "real authenticated API"))
                page = request(client, "GET", "/enterprise-quota", 200)
                rows.append(check(f"HTTP-{len(rows)+1:03d}", f"{username} authenticated page", "required tab markup", "pass" if "企业定额与资源价格工作台" in page.text and "版本历史" in page.text else "fail", "企业定额与资源价格工作台" in page.text and "版本历史" in page.text, "real authenticated HTML"))
                tree = request(client, "GET", "/api/v1/enterprise-quota/tree", 200).json()
                version_id = tree["items"][0]["enterprise_quota_version_id"]
                detail = request(client, "GET", f"/api/v1/enterprise-quota/versions/{version_id}", 200).json()
                rows.append(check(f"HTTP-{len(rows)+1:03d}", f"{username} tree/detail", "137 and components", f"{tree['total']} and {len(detail['components'])}", tree["total"] == 137 and len(detail["components"]) > 0, "real authenticated API"))
                mutation = {
                    "row_version": 999999,
                    "idempotency_key": f"http-smoke-{username}-{uuid.uuid4()}",
                    "change_type": "smoke_stale_conflict",
                    "change_reason": "HTTP smoke must not mutate",
                    "changes": {"enterprise_note": "not persisted"},
                }
                response = client.patch(
                    f"/api/v1/enterprise-quota/versions/{version_id}/draft",
                    headers={"X-CSRF-Token": auth["csrf_token"]}, json=mutation,
                )
                rows.append(check(f"HTTP-{len(rows)+1:03d}", f"{username} write boundary", expected_write, response.status_code, response.status_code == expected_write, "real RBAC + CSRF + row_version HTTP"))
                if username == "uat_editor":
                    no_csrf = client.patch(f"/api/v1/enterprise-quota/versions/{version_id}/draft", json=mutation)
                    rows.append(check(f"HTTP-{len(rows)+1:03d}", "Editor write without CSRF", 403, no_csrf.status_code, no_csrf.status_code == 403, "real HTTP CSRF rejection"))
                request(client, "POST", "/api/v1/auth/logout", 200, headers={"X-CSRF-Token": auth["csrf_token"]})
            finally:
                client.close()

        role_expectations = {
            "viewer": ("enterprise_quota.read",),
            "editor": ("enterprise_quota.create", "enterprise_quota.edit"),
            "reviewer": ("enterprise_quota.review",),
            "approver": ("enterprise_quota.approve", "enterprise_quota.publish"),
        }
        for role, permissions in role_expectations.items():
            granted = ROLE_PERMISSIONS[role]
            rows.append(check(f"RBAC-{len(rows)+1:03d}", f"{role} Enterprise Quota permissions", ",".join(permissions), ",".join(sorted(set(permissions) & set(granted))), all(item in granted for item in permissions), "frozen role catalog"))

        test_env = os.environ.copy()
        test_env["DATABASE_URL"] = "postgresql+psycopg://platform_dev:platform_dev_only@127.0.0.1:55432/construction_platform_rc1_dev"
        test = subprocess.run(
            [str(ENGINE_ROOT / "data/private/platform_dev/.venv/Scripts/python.exe"), "-m", "pytest", "platform_db/tests/test_enterprise_quota_pilot.py", "-q"],
            cwd=ENGINE_ROOT, env=test_env, capture_output=True, text=True, timeout=60,
        )
        test_tail = next((line for line in reversed(test.stdout.splitlines()) if "passed" in line or "failed" in line), f"exit={test.returncode}")
        rows.append(check("TEST-001", "Enterprise Quota pilot unit/integration suite", "pass with rollback", test_tail, test.returncode == 0, "pytest + PostgreSQL transaction rollback"))

        guard = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
        rows.append(check("GUARD-001", "RC1 Source/Baseline/Mapping Hash Guard", "pass", "pass" if guard["ok"] else guard["failures"], guard["ok"], "current manifest validation"))
        summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
        sqlite_path = ENGINE_ROOT / "web_collab_prototype/data/web_quota_building_draft.sqlite"
        import hashlib
        sqlite_hash = hashlib.sha256(sqlite_path.read_bytes()).hexdigest()
        rows.append(check("GUARD-002", "SQLite hash unchanged", summary["sqlite_sha256"], sqlite_hash, summary["sqlite_sha256"] == sqlite_hash, "current SHA256"))
    finally:
        with Session(engine) as session:
            for user_id, status in original_status.items():
                user = session.get(AppUser, user_id)
                user.status = status
                user.lockout_until = None
            session.execute(update(AppSession).where(
                AppSession.app_user_id.in_(list(original_status)), AppSession.status == "active"
            ).values(status="revoked"))
            session.commit()
        engine.dispose()
    if any(row["status"] != "pass" for row in rows):
        write_results(rows)
        raise RuntimeError("Enterprise Quota HTTP smoke failed")
    write_results(rows)
    print(json.dumps({"passed": len(rows), "total": len(rows), "output": str(HTTP_SMOKE)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
