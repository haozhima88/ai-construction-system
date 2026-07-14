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
from platform_db.security import hash_password  # noqa: E402
from platform_db.services.security_catalog import ROLE_PERMISSIONS  # noqa: E402


RUN_DIR = ENGINE_ROOT / "data/private/reference_extraction/runs/ENTERPRISE_QUOTA_CALCULATION_BASIS_AND_COMPONENT_EDITING_MVP_1"
RESULT = RUN_DIR / "enterprise_quota_component_web_smoke.csv"
MANIFEST = ENGINE_ROOT / "data/private/reference_extraction/runs/PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1/building_rc1_release_manifest.csv"
SQLITE = ENGINE_ROOT / "web_collab_prototype/data/web_quota_building_draft.sqlite"
EXPECTED_SQLITE_SHA256 = "e5cd6dfe9f399d2d74c5f28a2dbfedb9b00c4ffcd816cc16d8408663ae72168f"


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
    payload = request(
        client, "POST", "/api/v1/auth/login", 200,
        json={"username": username, "password": password},
    ).json()
    return client, payload


def write_results(rows: list[dict[str, str]]) -> None:
    fields = ["check_id", "check", "expected", "actual", "verification", "status"]
    with RESULT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    verification = (
        "\n## HTTP / RBAC / Transaction Verification\n\n"
        f"- Real HTTP component-workbench checks: `{sum(row['status'] == 'pass' for row in rows)}/{len(rows)} pass`.\n"
        "- Session, CSRF, tenant scope, optimistic row version and role denial were exercised through HTTP.\n"
        "- Successful add/edit/replace/soft-remove/restore/specification, idempotency, Change Set and Audit paths were exercised in PostgreSQL transactions and rolled back.\n"
        "- No UAT component mutation was retained.\n"
    )
    for name in (
        "checkpoint_enterprise_quota_component_editing.md",
        "stage_enterprise_quota_calculation_basis_and_component_editing_mvp_report.md",
    ):
        path = RUN_DIR / name
        content = path.read_text(encoding="utf-8").split("\n## HTTP / RBAC / Transaction Verification\n", 1)[0].rstrip()
        path.write_text(content + "\n" + verification, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8019")
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
            user.password_hash = hash_password(password)
            user.must_change_password = False
        session.commit()
    try:
        anonymous = httpx.get(args.base_url + "/enterprise-quota/a111-pilot", follow_redirects=False, timeout=10)
        rows.append(check(
            "HTTP-001", "anonymous workbench access", "303 /login",
            f"{anonymous.status_code} {anonymous.headers.get('location')}",
            anonymous.status_code == 303 and anonymous.headers.get("location", "").startswith("/login"), "real HTTP",
        ))

        viewer, viewer_auth = login(args.base_url, "uat_viewer", password)
        try:
            tree = request(viewer, "GET", "/api/v1/enterprise-quota/tree", 200).json()
            rows.append(check("RBAC-001", "viewer tenant-scoped read", 137, tree["total"], tree["total"] == 137, "Session + read permission"))
            detail = request(viewer, "GET", f"/api/v1/enterprise-quota/versions/{tree['items'][0]['enterprise_quota_version_id']}", 200).json()
            component = next(row for row in detail["components"] if row["calculation_basis"] == "quantity_unit_price")
            denied = viewer.patch(
                f"/api/v1/enterprise-quota/versions/{detail['version']['enterprise_quota_version_id']}/components/{component['enterprise_quota_component_version_id']}",
                headers={"X-CSRF-Token": viewer_auth["csrf_token"]},
                json={
                    "row_version": component["row_version"], "idempotency_key": f"viewer-denied-{uuid.uuid4()}",
                    "change_reason": "viewer must not edit", "action": "edit_quantity", "enterprise_quantity": "1",
                },
            )
            rows.append(check("RBAC-002", "viewer component write denied", 403, denied.status_code, denied.status_code == 403, "real RBAC"))
            request(viewer, "POST", "/api/v1/auth/logout", 200, headers={"X-CSRF-Token": viewer_auth["csrf_token"]})
        finally:
            viewer.close()

        editor, editor_auth = login(args.base_url, "uat_editor", password)
        try:
            summary = request(editor, "GET", "/api/v1/enterprise-quota/summary", 200).json()
            actual = "/".join(str(summary[key]) for key in (
                "a111_reference_quota_count", "enterprise_quota_draft_count", "enterprise_resource_count",
                "provincial_fallback_price_count", "approved_count", "published_count",
            ))
            rows.append(check("HTTP-002", "stage baseline counts", "137/137/55/54/0/0", actual, actual == "137/137/55/54/0/0", "summary API"))
            basis = "/".join(str(summary[key]) for key in (
                "quantity_unit_price_component_count", "direct_amount_component_count",
                "rate_based_component_count", "formula_based_component_count", "unclassified_component_count",
            ))
            rows.append(check("CALC-001", "component calculation basis counts", "500/129/0/0/0", basis, basis == "500/129/0/0/0", "server classification"))
            coverage = f"{summary['calculable_enterprise_quota_count']}/{summary['blocked_enterprise_quota_count']} ({summary['enterprise_quota_calculation_coverage']})"
            rows.append(check("CALC-002", "quota calculable / blocked", "137/0 (137/137)", coverage, coverage == "137/0 (137/137)", "server Decimal engine"))
            rows.append(check(
                "GATE-001", "allowed final status", "enterprise_quota_component_editing_ready_for_human_uat",
                summary["final_status"], summary["final_status"] == "enterprise_quota_component_editing_ready_for_human_uat", "summary gate",
            ))
            page = request(editor, "GET", "/enterprise-quota/a111-pilot", 200)
            script = request(editor, "GET", "/platform-static/enterprise-quota.js", 200).text
            required_ui = (
                "定额组成", "价格对比", "人工核价", "费用汇总", "工作内容", "工程量规则", "企业换算规则",
                "变更记录", "省定额 PDF", "审核记录", "版本历史",
            )
            rows.append(check("HTTP-003", "authenticated 11-tab workbench", 11, sum(label in page.text for label in required_ui), all(label in page.text for label in required_ui), "authenticated HTML"))
            required_actions = ("编辑消耗量", "编辑直接金额", "增加企业资源", "替换资源", "删除资源", "恢复省定额")
            rows.append(check("HTTP-004", "component action bundle", "all six actions", sum(label in script for label in required_actions), all(label in script for label in required_actions), "served JavaScript"))

            tree = request(editor, "GET", "/api/v1/enterprise-quota/tree", 200).json()
            version_id = tree["items"][0]["enterprise_quota_version_id"]
            detail = request(editor, "GET", f"/api/v1/enterprise-quota/versions/{version_id}", 200).json()
            required_fields = {
                "calculation_basis", "source_consumption", "consumption", "consumption_delta", "provincial_unit_price",
                "selected_enterprise_price", "provincial_component_amount", "enterprise_component_amount",
                "component_status", "lifecycle_status", "price_variance", "consumption_variance", "structure_variance",
                "rate_variance", "component_total_variance", "row_version",
            }
            rows.append(check("HTTP-005", "composition and variance payload", "all fields", len(required_fields & set(detail["components"][0])), required_fields <= set(detail["components"][0]), "detail API"))
            labor = next(row for row in detail["components"] if row["resource_code"] == "00010010")
            labor_actual = f"{labor['calculation_basis']}/{labor['unit']}/{labor['selected_enterprise_price']}/{labor['enterprise_direct_amount']}/{labor['enterprise_component_amount']}"
            labor_ok = (
                labor["calculation_basis"] == "direct_amount" and labor["unit"] == "元"
                and labor["selected_enterprise_price"] is None and labor["enterprise_direct_amount"] is not None
                and labor["enterprise_component_amount"] == labor["enterprise_direct_amount"]
            )
            rows.append(check("CALC-003", "00010010 labor direct amount", "direct_amount/元/null/direct=amount", labor_actual, labor_ok, "no inferred labor unit price"))
            cost = detail["cost_summary"]
            variance_keys = {"price_variance", "consumption_variance", "structure_variance", "rate_variance", "total_variance"}
            rows.append(check("CALC-004", "five-way variance attribution", "all five", len(variance_keys & set(cost)), variance_keys <= set(cost), "server-side detail summary"))

            quantity = next(row for row in detail["components"] if row["calculation_basis"] == "quantity_unit_price")
            stale_payload = {
                "row_version": 999999, "idempotency_key": f"component-stale-{uuid.uuid4()}",
                "change_reason": "stale request must not mutate", "action": "edit_quantity", "enterprise_quantity": "1",
            }
            path = f"/api/v1/enterprise-quota/versions/{version_id}/components/{quantity['enterprise_quota_component_version_id']}"
            no_csrf = editor.patch(path, json={**stale_payload, "row_version": quantity["row_version"]})
            stale = editor.patch(path, headers={"X-CSRF-Token": editor_auth["csrf_token"]}, json=stale_payload)
            rows.append(check("GATE-002", "component write CSRF", 403, no_csrf.status_code, no_csrf.status_code == 403, "real CSRF rejection"))
            rows.append(check("GATE-003", "component write row_version", 409, stale.status_code, stale.status_code == 409, "real optimistic-lock rejection"))
            request(editor, "POST", "/api/v1/auth/logout", 200, headers={"X-CSRF-Token": editor_auth["csrf_token"]})
        finally:
            editor.close()

        permission_ok = (
            "enterprise_quota.edit" in ROLE_PERMISSIONS["editor"]
            and "enterprise_quota.review" in ROLE_PERMISSIONS["reviewer"]
            and "enterprise_quota.approve" not in ROLE_PERMISSIONS["editor"]
        )
        rows.append(check("RBAC-003", "component edit/review separation", "editor/edit; reviewer/review", permission_ok, permission_ok, "frozen role catalog"))

        test_env = os.environ.copy()
        test_env["DATABASE_URL"] = "postgresql+psycopg://platform_dev:platform_dev_only@127.0.0.1:55432/construction_platform_rc1_dev"
        test = subprocess.run(
            [sys.executable, "-m", "pytest", "platform_db/tests/test_enterprise_quota_pilot.py", "-q"],
            cwd=ENGINE_ROOT, env=test_env, capture_output=True, text=True, timeout=120,
        )
        tail = next((line for line in reversed(test.stdout.splitlines()) if "passed" in line or "failed" in line), f"exit={test.returncode}")
        rows.append(check("TEST-001", "component unit/integration suite", "13 passed", tail, test.returncode == 0 and "13 passed" in tail, "pytest + PostgreSQL rollback"))

        uat_rows = list(csv.DictReader((RUN_DIR / "a111_component_editing_uat_20.csv").open("r", encoding="utf-8-sig", newline="")))
        uat_ok = len(uat_rows) == 20 and all(row["human_confirmed"].lower() == "false" for row in uat_rows)
        rows.append(check("UAT-001", "20 representative component UAT rows", "20 / human_confirmed=false", f"{len(uat_rows)} / {sorted({row['human_confirmed'] for row in uat_rows})}", uat_ok, "prepared evidence only"))
        guard = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
        rows.append(check("GUARD-001", "Source/Baseline/Mapping hash guard", "pass", "pass" if guard["ok"] else guard["failures"], guard["ok"], "current RC1 manifest"))
        sqlite_hash = hashlib.sha256(SQLITE.read_bytes()).hexdigest()
        rows.append(check("GUARD-002", "SQLite hash unchanged", EXPECTED_SQLITE_SHA256, sqlite_hash, sqlite_hash == EXPECTED_SQLITE_SHA256, "current SHA256"))
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
        raise RuntimeError("Enterprise quota component HTTP smoke failed")
    print(json.dumps({"passed": len(rows), "total": len(rows), "output": str(RESULT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
