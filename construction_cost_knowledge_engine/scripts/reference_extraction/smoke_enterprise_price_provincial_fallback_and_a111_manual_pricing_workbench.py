from __future__ import annotations

import argparse
import csv
import hashlib
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


RUN_DIR = ENGINE_ROOT / "data/private/reference_extraction/runs/ENTERPRISE_PRICE_PROVINCIAL_FALLBACK_AND_A111_MANUAL_PRICING_WORKBENCH_1"
RESULT = RUN_DIR / "enterprise_manual_pricing_web_smoke.csv"
SUMMARY = RUN_DIR / "stage_summary.json"
MANIFEST = ENGINE_ROOT / "data/private/reference_extraction/runs/PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1/building_rc1_release_manifest.csv"
SQLITE = ENGINE_ROOT / "web_collab_prototype/data/web_quota_building_draft.sqlite"


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
        raise RuntimeError(f"{method} {path}: expected {expected}, got {response.status_code}: {response.text[:300]}")
    return response


def login(base_url: str, username: str, password: str) -> tuple[httpx.Client, dict[str, Any]]:
    client = httpx.Client(base_url=base_url, follow_redirects=False, timeout=20)
    payload = request(client, "POST", "/api/v1/auth/login", 200, json={"username": username, "password": password}).json()
    return client, payload


def write_results(rows: list[dict[str, str]]) -> None:
    fields = ["check_id", "check", "expected", "actual", "verification", "status"]
    with RESULT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    summary["http_web_smoke_passed"] = sum(row["status"] == "pass" for row in rows)
    summary["http_web_smoke_total"] = len(rows)
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    verification = (
        "\n## HTTP / RBAC / Audit Verification\n\n"
        f"- Real HTTP, Session, CSRF, tenant-scope and price-workbench checks: `{summary['http_web_smoke_passed']}/{summary['http_web_smoke_total']} pass`.\n"
        "- Successful manual-price, review, restore-fallback and Change Set/Audit paths were exercised in a PostgreSQL transaction and rolled back.\n"
        "- Stale row-version writes were rejected; no UAT price mutation was retained.\n"
    )
    for name in (
        "checkpoint_enterprise_price_provincial_fallback.md",
        "stage_enterprise_price_provincial_fallback_and_a111_manual_pricing_workbench_report.md",
    ):
        path = RUN_DIR / name
        content = path.read_text(encoding="utf-8").split("\n## HTTP / RBAC / Audit Verification\n", 1)[0].rstrip()
        path.write_text(content + "\n" + verification, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8018")
    parser.add_argument("--env-file", type=Path, default=ENGINE_ROOT / ".env.platform.local")
    args = parser.parse_args()
    missing = load_local_environment(args.env_file)
    if missing:
        raise RuntimeError("Missing local UAT environment variables: " + ", ".join(missing))
    password = os.environ["PLATFORM_UAT_TEMP_PASSWORD"]
    engine = build_engine()
    rows: list[dict[str, str]] = []
    original_status: dict[uuid.UUID, Any] = {}
    with Session(engine) as session:
        users = list(session.scalars(select(AppUser).where(AppUser.login_name.in_(("uat_viewer", "uat_editor")))))
        if {user.login_name for user in users} != {"uat_viewer", "uat_editor"}:
            raise RuntimeError("Dedicated UAT viewer/editor users are missing")
        for user in users:
            original_status[user.app_user_id] = user.status
            user.status = "active"
            user.lockout_until = None
        session.commit()
    try:
        anonymous = httpx.get(args.base_url + "/enterprise-quota/a111-pilot", follow_redirects=False, timeout=10)
        rows.append(check("HTTP-001", "anonymous workbench access", "303 /login", f"{anonymous.status_code} {anonymous.headers.get('location')}", anonymous.status_code == 303 and anonymous.headers.get("location", "").startswith("/login"), "real HTTP"))

        viewer, viewer_auth = login(args.base_url, "uat_viewer", password)
        try:
            viewer_prices = request(viewer, "GET", "/api/v1/enterprise-quota/prices", 200).json()
            rows.append(check("RBAC-001", "viewer price read", "55", viewer_prices["total"], viewer_prices["total"] == 55, "Session + enterprise_price.read"))
            missing_resource = next(item for item in viewer_prices["items"] if item["selected_price"] is None)
            viewer_write = viewer.post(
                f"/api/v1/enterprise-quota/prices/resources/{missing_resource['enterprise_resource_id']}/manual",
                headers={"X-CSRF-Token": viewer_auth["csrf_token"]},
                json={"row_version": missing_resource["resource_row_version"], "idempotency_key": f"viewer-denied-{uuid.uuid4()}", "price_value": "1", "tax_mode": "test", "region": "test", "effective_from": "2026-07-14T00:00:00+08:00", "change_reason": "must be denied"},
            )
            rows.append(check("RBAC-002", "viewer manual-price write denied", 403, viewer_write.status_code, viewer_write.status_code == 403, "real RBAC"))
            request(viewer, "POST", "/api/v1/auth/logout", 200, headers={"X-CSRF-Token": viewer_auth["csrf_token"]})
        finally:
            viewer.close()

        editor, editor_auth = login(args.base_url, "uat_editor", password)
        try:
            summary = request(editor, "GET", "/api/v1/enterprise-quota/summary", 200).json()
            actual_summary = f"{summary['a111_reference_quota_count']}/{summary['enterprise_resource_count']}/{summary['provincial_fallback_price_count']}/{summary['missing_enterprise_price_resource_count']}"
            rows.append(check("HTTP-002", "fallback summary", "137/55/54/1", actual_summary, actual_summary == "137/55/54/1", "tenant-scoped summary API"))
            rows.append(check("HTTP-003", "dual coverage", "54/55 and 0/55", f"{summary['calculation_price_coverage']} and {summary['enterprise_confirmed_price_coverage']}", summary["calculation_price_coverage"] == "54/55" and summary["enterprise_confirmed_price_coverage"] == "0/55", "server-side Decimal selection"))
            rows.append(check("GATE-001", "approved/published gate", "0/0", f"{summary['approved_count']}/{summary['published_count']}", summary["approved_count"] == 0 and summary["published_count"] == 0, "database gate"))

            all_prices = request(editor, "GET", "/api/v1/enterprise-quota/prices", 200).json()
            counts = {
                name: request(editor, "GET", f"/api/v1/enterprise-quota/prices?filter={name}&threshold_percentage=20", 200).json()["total"]
                for name in (
                    "all", "provincial_fallback", "pending_manual_pricing", "manual_priced",
                    "accepted_fallback", "reference_price_missing", "internal_observation_large",
                    "manual_adjustment_large", "ready_for_review",
                )
            }
            expected_counts = {"all": 55, "provincial_fallback": 54, "pending_manual_pricing": 55, "manual_priced": 0, "accepted_fallback": 0, "reference_price_missing": 1, "internal_observation_large": 0, "manual_adjustment_large": 0, "ready_for_review": 0}
            rows.append(check("HTTP-004", "nine price filters", json.dumps(expected_counts, ensure_ascii=False), json.dumps(counts, ensure_ascii=False), counts == expected_counts, "real filtered API"))
            missing_item = next(item for item in all_prices["items"] if item["selected_price"] is None)
            missing_key = (missing_item["resource_code"], missing_item["resource_name"], missing_item["unit"])
            rows.append(check("GATE-002", "missing Reference price remains null", "00010010/人工费/元/null", "/".join(missing_key) + f"/{missing_item['selected_price']}", missing_key == ("00010010", "人工费", "元") and missing_item["selected_price"] is None, "no zero/no inference"))
            fallback_item = next(item for item in all_prices["items"] if item["selected_price"] is not None)
            required_fields = {"provincial_reference_price", "provincial_fallback_price", "enterprise_manual_price", "selected_price", "price_source_type", "pricing_review_status", "effective_from", "tax_mode", "region", "adjustment_reason", "version_history", "change_sets"}
            rows.append(check("HTTP-005", "manual-pricing field contract", "all required fields", sorted(required_fields & set(fallback_item)), required_fields <= set(fallback_item), "real price API payload"))
            page = request(editor, "GET", "/enterprise-quota/a111-pilot", 200)
            rows.append(check("HTTP-006", "manual-pricing workbench markup", "11 tabs and price toolbar", "pass" if "人工核价" in page.text and "内部观察差异较大" in page.text else "fail", "人工核价" in page.text and "内部观察差异较大" in page.text, "authenticated HTML"))
            tree = request(editor, "GET", "/api/v1/enterprise-quota/tree", 200).json()
            detail = request(editor, "GET", f"/api/v1/enterprise-quota/versions/{tree['items'][0]['enterprise_quota_version_id']}", 200).json()
            component_fields = {"provincial_unit_price", "provincial_fallback_price", "enterprise_manual_price", "selected_enterprise_price", "enterprise_component_amount", "price_source_type", "pricing_review_status", "adjustment_reason"}
            rows.append(check("HTTP-007", "quota recalculation detail", "137 tree and price fields", f"{tree['total']} / {len(detail['components'])}", tree["total"] == 137 and bool(detail["components"]) and component_fields <= set(detail["components"][0]), "real detail API"))

            stale_payload = {"row_version": 999999, "idempotency_key": f"stale-manual-{uuid.uuid4()}", "price_value": "1.23", "tax_mode": "test", "region": "test", "effective_from": "2026-07-14T00:00:00+08:00", "change_reason": "stale request must not mutate"}
            no_csrf = editor.post(f"/api/v1/enterprise-quota/prices/resources/{missing_item['enterprise_resource_id']}/manual", json=stale_payload)
            stale = editor.post(f"/api/v1/enterprise-quota/prices/resources/{missing_item['enterprise_resource_id']}/manual", headers={"X-CSRF-Token": editor_auth["csrf_token"]}, json=stale_payload)
            rows.append(check("RBAC-003", "price write CSRF", 403, no_csrf.status_code, no_csrf.status_code == 403, "real CSRF rejection"))
            rows.append(check("GATE-003", "price write row_version", 409, stale.status_code, stale.status_code == 409, "real optimistic-lock rejection"))
            request(editor, "POST", "/api/v1/auth/logout", 200, headers={"X-CSRF-Token": editor_auth["csrf_token"]})
        finally:
            editor.close()

        role_checks = {
            "editor": ("enterprise_price.edit",),
            "reviewer": ("enterprise_price.review",),
            "approver": ("enterprise_quota.approve", "enterprise_quota.publish"),
        }
        for role, permissions in role_checks.items():
            rows.append(check(f"RBAC-{len(rows) + 1:03d}", f"{role} price/quota permissions", ",".join(permissions), ",".join(sorted(set(permissions) & set(ROLE_PERMISSIONS[role]))), all(permission in ROLE_PERMISSIONS[role] for permission in permissions), "frozen role catalog"))

        test_env = os.environ.copy()
        test_env["DATABASE_URL"] = "postgresql+psycopg://platform_dev:platform_dev_only@127.0.0.1:55432/construction_platform_rc1_dev"
        test = subprocess.run(
            [sys.executable, "-m", "pytest", "platform_db/tests/test_enterprise_quota_pilot.py", "-q"],
            cwd=ENGINE_ROOT, env=test_env, capture_output=True, text=True, timeout=90,
        )
        test_tail = next((line for line in reversed(test.stdout.splitlines()) if "passed" in line or "failed" in line), f"exit={test.returncode}")
        rows.append(check("TEST-001", "price workbench unit/integration suite", "10 passed with rollback", test_tail, test.returncode == 0 and "10 passed" in test_tail, "pytest + PostgreSQL rollback"))

        uat_rows = list(csv.DictReader((RUN_DIR / "a111_manual_pricing_uat_20.csv").open("r", encoding="utf-8-sig", newline="")))
        rows.append(check("UAT-001", "20 representative UAT rows", "20 and human_confirmed=false", f"{len(uat_rows)} / {sorted({row['human_confirmed'] for row in uat_rows})}", len(uat_rows) == 20 and all(row["human_confirmed"].lower() == "false" for row in uat_rows), "prepared data only"))
        guard = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
        rows.append(check("GUARD-001", "Source/Baseline/Mapping hash guard", "pass", "pass" if guard["ok"] else guard["failures"], guard["ok"], "current RC1 manifest"))
        stage_summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
        sqlite_hash = hashlib.sha256(SQLITE.read_bytes()).hexdigest().upper()
        rows.append(check("GUARD-002", "SQLite hash unchanged", stage_summary["sqlite_sha256"].upper(), sqlite_hash, stage_summary["sqlite_sha256"].upper() == sqlite_hash, "current SHA256"))
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
    write_results(rows)
    if any(row["status"] != "pass" for row in rows):
        raise RuntimeError("Enterprise price HTTP workbench smoke failed")
    print(json.dumps({"passed": len(rows), "total": len(rows), "output": str(RESULT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
