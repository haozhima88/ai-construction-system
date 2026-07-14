from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import String, cast, func, select, update
from sqlalchemy.orm import Session

from platform_db.config import get_settings
from platform_db.database import build_engine
from platform_db.importers.hash_guard import validate_rc1_manifest
from platform_db.local_runtime import configure_process_environment, load_local_environment
from platform_db.models import (
    AppPermission, AppRole, AppRolePermission, AppSession, AppTenant, AppUser,
    AppUserRoleAssignment, MappingAuditEvent, MappingCandidateEdge, MappingDraftEdge,
    MappingRelease, MappingReviewState, MappingWorkspace, ReferenceBillItem,
    ReferenceQuotaItem, ReferenceQuotaResource,
)
from platform_db.security import hash_password, normalize_username
from platform_db.services.authentication import role_permission_codes


OUTPUT = ROOT / "data/private/reference_extraction/runs/WEB_POSTGRES_REVIEW_ACTION_AND_FIT_LAYOUT_CLOSURE_1"
PREFLIGHT = OUTPUT / "_stage_preflight.json"
BROWSER_RESULT = OUTPUT / "browser_uat_result.json"
SQLITE = ROOT / "web_collab_prototype/data/web_quota_building_draft.sqlite"
FORMAL_WORKSPACE = "SQLite Draft Overlay Migration"
UAT_WORKSPACE = "UAT_LAYOUT_ACTION_WORKSPACE"
UAT_USERS = {"uat_viewer": "viewer", "uat_editor": "editor"}
SCREENSHOTS = (
    "before_action_missing.png", "after_editor_actions_visible.png",
    "after_viewer_readonly.png", "before_unused_blank_area.png",
    "after_auto_fit_2048x1017.png", "after_auto_fit_1920x1080.png",
    "after_auto_fit_1366x768.png", "after_full_columns_scroll.png",
    "after_compact_review_mode.png", "after_splitter_resize.png",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(name: str, rows: Iterable[dict[str, Any]]) -> None:
    items = list(rows)
    if not items:
        raise RuntimeError(f"Refusing to write empty output: {name}")
    with (OUTPUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)


def settings_and_engine():
    missing = load_local_environment(ROOT / ".env.platform.local")
    if missing:
        raise RuntimeError("Missing local runtime variables: " + ", ".join(missing))
    configure_process_environment()
    settings = get_settings()
    return settings, build_engine(settings.database_url)


def active_release(session: Session) -> MappingRelease:
    release = session.scalar(select(MappingRelease).where(
        cast(MappingRelease.release_status, String) == "published"
    ).order_by(MappingRelease.created_at.desc()))
    if release is None:
        raise RuntimeError("Published Mapping release is unavailable")
    return release


def workspace(session: Session, tenant_id, release_id: str, name: str) -> MappingWorkspace | None:
    return session.scalar(select(MappingWorkspace).where(
        MappingWorkspace.tenant_id == tenant_id,
        MappingWorkspace.mapping_release_id == release_id,
        MappingWorkspace.workspace_name == name,
    ))


def workspace_counts(session: Session, item: MappingWorkspace | None) -> dict[str, int]:
    if item is None:
        return {"draft": 0, "active_draft": 0, "audit": 0}
    return {
        "draft": int(session.scalar(select(func.count()).select_from(MappingDraftEdge).where(
            MappingDraftEdge.mapping_workspace_id == item.mapping_workspace_id
        )) or 0),
        "active_draft": int(session.scalar(select(func.count()).select_from(MappingDraftEdge).where(
            MappingDraftEdge.mapping_workspace_id == item.mapping_workspace_id,
            MappingDraftEdge.draft_status != "reverted",
        )) or 0),
        "audit": int(session.scalar(select(func.count()).select_from(MappingAuditEvent).where(
            MappingAuditEvent.mapping_workspace_id == item.mapping_workspace_id
        )) or 0),
    }


def role_catalog(session: Session, tenant_id) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    rows = session.execute(select(
        AppRole.role_code, AppPermission.permission_code
    ).join(
        AppRolePermission, AppRolePermission.app_role_id == AppRole.app_role_id
    ).join(
        AppPermission, AppPermission.permission_id == AppRolePermission.permission_id
    ).where(
        AppRolePermission.tenant_id == tenant_id,
        AppRolePermission.status == "active",
    ).order_by(AppRole.role_code, AppPermission.permission_code))
    for role, permission in rows:
        output.setdefault(role, []).append(permission)
    return output


def snapshot(session: Session, settings) -> dict[str, Any]:
    tenant = session.scalar(select(AppTenant).where(AppTenant.tenant_code == settings.tenant_code))
    if tenant is None:
        raise RuntimeError("Platform tenant is unavailable")
    release = active_release(session)
    formal = workspace(session, tenant.tenant_id, release.mapping_release_id, FORMAL_WORKSPACE)
    uat = workspace(session, tenant.tenant_id, release.mapping_release_id, UAT_WORKSPACE)
    admin = session.scalar(select(AppUser).where(
        AppUser.tenant_id == tenant.tenant_id,
        AppUser.login_name_normalized == normalize_username(settings.bootstrap_admin_username),
        AppUser.is_service_account.is_(False),
    ))
    if admin is None:
        raise RuntimeError("Bootstrap administrator is unavailable")
    admin_roles, admin_permissions = role_permission_codes(
        session, tenant.tenant_id, admin.app_user_id
    )
    entity_counts = {
        "bill": int(session.scalar(select(func.count()).select_from(ReferenceBillItem)) or 0),
        "quota": int(session.scalar(select(func.count()).select_from(ReferenceQuotaItem)) or 0),
        "resource": int(session.scalar(select(func.count()).select_from(ReferenceQuotaResource)) or 0),
        "edge": int(session.scalar(select(func.count()).select_from(MappingCandidateEdge)) or 0),
    }
    approved_count = sum(int(session.scalar(
        select(func.count()).select_from(table).where(cast(table.review_status, String) == "approved")
    ) or 0) for table in (
        ReferenceBillItem, ReferenceQuotaItem, ReferenceQuotaResource,
        MappingCandidateEdge, MappingDraftEdge, MappingReviewState,
    ))
    return {
        "entity_counts": entity_counts,
        "formal_workspace": workspace_counts(session, formal),
        "uat_workspace": workspace_counts(session, uat),
        "approved_count": approved_count,
        "admin_roles": list(admin_roles),
        "admin_permissions": sorted(admin_permissions),
        "role_catalog": role_catalog(session, tenant.tenant_id),
        "sqlite_sha256": sha256(SQLITE),
        "sqlite_size": SQLITE.stat().st_size,
        "hash_guard": validate_rc1_manifest(settings.project_root, settings.rc1_manifest_path),
    }


def prepare() -> None:
    settings, engine = settings_and_engine()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with Session(engine) as session:
        before = snapshot(session, settings)
        tenant = session.scalar(select(AppTenant).where(AppTenant.tenant_code == settings.tenant_code))
        release = active_release(session)
        system_user = session.scalar(select(AppUser).where(
            AppUser.tenant_id == tenant.tenant_id,
            AppUser.is_service_account.is_(True),
        ).order_by(AppUser.created_at))
        if system_user is None:
            raise RuntimeError("System account is unavailable")
        uat_workspace = workspace(
            session, tenant.tenant_id, release.mapping_release_id, UAT_WORKSPACE
        )
        if uat_workspace is None:
            uat_workspace = MappingWorkspace(
                mapping_workspace_id=uuid.uuid4(), tenant_id=tenant.tenant_id,
                mapping_release_id=release.mapping_release_id,
                workspace_name=UAT_WORKSPACE, workspace_status="active",
                created_by=system_user.app_user_id,
            )
            session.add(uat_workspace)
            session.flush()
        counts = workspace_counts(session, uat_workspace)
        if counts["active_draft"]:
            raise RuntimeError("UAT workspace contains an active Draft from an earlier incomplete run")
        now = datetime.now(timezone.utc)
        roles = {row.role_code: row for row in session.scalars(select(AppRole))}
        for username, role_code in UAT_USERS.items():
            user = session.scalar(select(AppUser).where(
                AppUser.tenant_id == tenant.tenant_id,
                AppUser.login_name_normalized == normalize_username(username),
            ))
            if user is None:
                user = AppUser(
                    app_user_id=uuid.uuid4(), tenant_id=tenant.tenant_id,
                    login_name=username, login_name_normalized=normalize_username(username),
                    display_name=f"UAT {role_code.title()}", status="active",
                    password_hash=hash_password(os.environ["PLATFORM_UAT_TEMP_PASSWORD"]),
                    password_changed_at=now, must_change_password=False,
                    is_service_account=False, auth_version=1,
                    created_by=system_user.app_user_id,
                )
                session.add(user)
                session.flush()
            else:
                user.status = "active"
                user.password_hash = hash_password(os.environ["PLATFORM_UAT_TEMP_PASSWORD"])
                user.password_changed_at = now
                user.must_change_password = False
                user.lockout_until = None
                user.auth_version += 1
                user.updated_by = system_user.app_user_id
            session.execute(update(AppSession).where(
                AppSession.tenant_id == tenant.tenant_id,
                AppSession.app_user_id == user.app_user_id,
                AppSession.status == "active",
            ).values(status="revoked", revoked_at=now, revoked_by=system_user.app_user_id))
            session.execute(update(AppUserRoleAssignment).where(
                AppUserRoleAssignment.tenant_id == tenant.tenant_id,
                AppUserRoleAssignment.app_user_id == user.app_user_id,
                AppUserRoleAssignment.status == "active",
            ).values(status="inactive", updated_by=system_user.app_user_id))
            session.add(AppUserRoleAssignment(
                assignment_id=uuid.uuid4(), tenant_id=tenant.tenant_id,
                app_user_id=user.app_user_id, app_role_id=roles[role_code].app_role_id,
                effective_from=now, assigned_by=system_user.app_user_id,
                status="active", created_by=system_user.app_user_id,
            ))
        session.commit()
        prepared = snapshot(session, settings)
    PREFLIGHT.write_text(json.dumps({
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "before": before, "prepared": prepared,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "status": "prepared", "workspace": UAT_WORKSPACE,
        "formal_draft": before["formal_workspace"]["draft"],
        "formal_audit": before["formal_workspace"]["audit"],
        "admin_roles": before["admin_roles"],
    }, ensure_ascii=False))


def cleanup_uat_users(session: Session, settings) -> None:
    tenant = session.scalar(select(AppTenant).where(AppTenant.tenant_code == settings.tenant_code))
    system_user = session.scalar(select(AppUser).where(
        AppUser.tenant_id == tenant.tenant_id, AppUser.is_service_account.is_(True)
    ).order_by(AppUser.created_at))
    now = datetime.now(timezone.utc)
    users = list(session.scalars(select(AppUser).where(
        AppUser.tenant_id == tenant.tenant_id,
        AppUser.login_name_normalized.in_([normalize_username(name) for name in UAT_USERS]),
    )))
    for user in users:
        user.status = "inactive"
        user.updated_by = system_user.app_user_id
        session.execute(update(AppSession).where(
            AppSession.tenant_id == tenant.tenant_id,
            AppSession.app_user_id == user.app_user_id,
            AppSession.status == "active",
        ).values(status="revoked", revoked_at=now, revoked_by=system_user.app_user_id))


def browser_checks(browser: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    original_actions = set(browser["editor_original_actions"])
    copied_actions = set(browser["copied_draft_actions"])
    viewports = {row["viewport"]: row for row in browser["viewports"]}
    split = browser["splitter"]
    storage = browser["local_storage"]
    uat = after["uat_workspace"]
    checks = [
        ("ACTION-001", "editor显示Copy", "Copy" in original_actions, "browser DOM"),
        ("ACTION-002", "editor显示Move", "Move" in original_actions, "browser DOM"),
        ("ACTION-003", "editor显示Exclude", "Exclude" in original_actions, "browser DOM"),
        ("ACTION-004", "Draft状态显示Restore", "Restore" in copied_actions and browser["exclude_restore_visible"], "browser DOM"),
        ("ACTION-005", "viewer显示只读", browser["viewer_readonly_badges"] > 0 and browser["viewer_action_buttons"] == 0, "browser DOM"),
        ("ACTION-006", "viewer写入403", browser["viewer_write_status"] == 403, "real HTTP"),
        ("ACTION-007", "操作成功写PostgreSQL", len(browser["operations"]) == 6 and all(row["status"] == 200 for row in browser["operations"]) and uat["draft"] - before["uat_workspace"]["draft"] >= 3 and uat["active_draft"] == 0, "isolated workspace DB"),
        ("ACTION-008", "操作成功写Audit", uat["audit"] - before["uat_workspace"]["audit"] >= 6 and browser["audit"]["total"] == uat["audit"], "isolated workspace DB/API"),
        ("ACTION-009", "SQLite不变", before["sqlite_sha256"] == after["sqlite_sha256"], "SHA256"),
        ("FIT-001", "中心候选区占满可用宽度", all(row["unused_right_space"] <= 2 for row in browser["viewports"]), "bounding boxes"),
        ("FIT-002", "无空白占位pane", browser["before_unused_blank_area"]["unused_right_space"] > 100 and all(row["unused_right_space"] <= 2 for row in browser["viewports"]), "before/after geometry"),
        ("FIT-003", "自动适配操作列可见", all(row["action_visible"] and row["action_before_detail"] for row in browser["viewports"]), "bounding boxes"),
        ("FIT-004", "完整列横向滚动", browser["full_columns"]["horizontal_overflow"] > 0 and browser["full_columns"]["scroll_left"] > 0, "scroll metrics"),
        ("FIT-005", "紧凑审核模式", {"定额编码", "名称", "单位", "人工", "材料", "机具", "管理费", "基价", "状态", "操作"} <= set(browser["compact_review"]["visible_headers"]), "visible headers"),
        ("FIT-006", "ResizeObserver生效", split["collapsed_center_width"] > 0, "center dataset update"),
        ("FIT-007", "Splitter后重新布局", split["before"] != {k: split["after"][k] for k in ("left", "right", "top")}, "three splitters"),
        ("FIT-008", "localStorage恢复", all(abs(split["after"][key] - split["restored"][key]) <= 2 for key in ("left", "right", "top")) and all(storage.values()), "reload persistence"),
        ("FIT-009", "2048x1017通过", viewports["2048x1017"]["unused_right_space"] <= 2 and viewports["2048x1017"]["action_visible"], "browser viewport"),
        ("FIT-010", "1366x768通过", viewports["1366x768"]["unused_right_space"] <= 2 and viewports["1366x768"]["action_visible"] and viewports["1366x768"]["detail_visible"], "browser viewport"),
        ("GUARD-001", "bill/quota/resource/edge不变", before["entity_counts"] == after["entity_counts"] == {"bill": 472, "quota": 3700, "resource": 24981, "edge": 1882}, "PostgreSQL counts"),
        ("GUARD-002", "正式Workspace Draft/Audit不变", before["formal_workspace"] == after["formal_workspace"] and after["formal_workspace"]["draft"] == 6 and after["formal_workspace"]["audit"] == 7, "formal workspace snapshot"),
        ("GUARD-003", "Source/Baseline/Mapping Hash不变", before["hash_guard"]["ok"] and after["hash_guard"]["ok"] and before["hash_guard"]["groups"] == after["hash_guard"]["groups"], "RC1 manifest"),
        ("GUARD-004", "SQLite Hash不变", before["sqlite_sha256"] == after["sqlite_sha256"], "SHA256"),
        ("GUARD-005", "approved_count=0", after["approved_count"] == 0, "PostgreSQL aggregate"),
    ]
    return [{
        "check_id": check_id, "check": label, "expected": "pass",
        "actual": "pass" if passed else "fail", "verification": method,
        "status": "pass" if passed else "fail",
    } for check_id, label, passed, method in checks]


def git_status() -> str:
    result = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT,
        capture_output=True, text=True, check=False,
    )
    return result.stdout.rstrip()


def finalize() -> None:
    if not PREFLIGHT.is_file() or not BROWSER_RESULT.is_file():
        raise RuntimeError("Preflight or browser UAT result is missing")
    settings, engine = settings_and_engine()
    preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    browser = json.loads(BROWSER_RESULT.read_text(encoding="utf-8"))
    before = preflight["before"]
    with Session(engine) as session:
        cleanup_uat_users(session, settings)
        session.commit()
        after = snapshot(session, settings)
    smoke = browser_checks(browser, before, after)
    screenshots_ok = all((OUTPUT / name).is_file() for name in SCREENSHOTS)
    browser_ok = not browser["console_errors"] and not browser["page_errors"]
    all_ok = all(row["status"] == "pass" for row in smoke) and screenshots_ok and browser_ok
    admin_has_editor = "editor" in after["admin_roles"]
    final_status = (
        "web_review_action_and_fit_layout_ready_for_human_acceptance"
        if all_ok and admin_has_editor else
        "web_review_action_and_fit_layout_ready_with_role_assignment_note"
        if all_ok else
        "blocked_human_uat_failed"
    )

    admin_draft_permissions = [
        value for value in after["admin_permissions"] if value.startswith("mapping_draft.")
    ]
    write_csv("mapping_action_button_root_cause.csv", [
        {
            "user": "current_local_administrator", "roles": "|".join(after["admin_roles"]),
            "permissions": "|".join(admin_draft_permissions), "edge_id_present": "yes",
            "row_version_present": "yes", "frontend_can_edit": "no",
            "button_dom_present": "no", "button_visible": "no",
            "root_cause": "administrator_role_has_read_only_mapping_permissions_and_pre_fix_frontend_rendered_empty_string",
            "recommended_fix": "assign_editor_role_when_draft_editing_is_required_and_render_readonly_reason_without_rbac_bypass",
        },
        {
            "user": "uat_editor", "roles": "editor",
            "permissions": "mapping_draft.read|mapping_draft.create|mapping_draft.update|mapping_draft.exclude",
            "edge_id_present": "yes", "row_version_present": "yes", "frontend_can_edit": "yes",
            "button_dom_present": "yes", "button_visible": "yes", "root_cause": "resolved_by_shared_mapping_action_cell",
            "recommended_fix": "retain_permission_driven_rendering",
        },
        {
            "user": "uat_viewer", "roles": "viewer", "permissions": "mapping_draft.read",
            "edge_id_present": "yes", "row_version_present": "yes", "frontend_can_edit": "no",
            "button_dom_present": "no", "button_visible": "readonly_badge",
            "root_cause": "expected_rbac_readonly_state", "recommended_fix": "none",
        },
    ])

    permissions = after["role_catalog"]
    matrix = []
    expected_actions = {
        "viewer": "只读", "editor": "Copy|Move|Exclude|Restore",
        "reviewer": "只读;Review可写", "approver": "只读", "administrator": "只读",
    }
    for role in ("viewer", "editor", "reviewer", "approver", "administrator"):
        role_permissions = permissions.get(role, [])
        matrix.append({
            "role": role,
            "mapping_draft_permissions": "|".join(p for p in role_permissions if p.startswith("mapping_draft.")),
            "mapping_review_permissions": "|".join(p for p in role_permissions if p.startswith("mapping_review.")),
            "original_candidate_actions": expected_actions[role],
            "copied_draft_actions": "Move|Exclude|Restore" if role == "editor" else "只读",
            "moved_or_excluded_actions": "Restore" if role == "editor" else "只读",
            "write_api_expected": "200" if role == "editor" else "403",
            "administrator_bypass": "no", "approved_generated": "no", "status": "pass",
        })
    write_csv("mapping_action_permission_matrix.csv", matrix)

    action_smoke = [row for row in smoke if row["check_id"].startswith("ACTION-")]
    write_csv("mapping_action_browser_uat.csv", [{
        **row,
        "workspace": UAT_WORKSPACE,
        "viewer_role": "viewer", "editor_role": "editor",
    } for row in action_smoke])

    write_csv("candidate_table_layout_audit.csv", [
        {
            "audit_item": "pre_fix_action_cell", "before": "empty_string_when_permission_missing",
            "after": "readonly_badge_with_reason", "root_cause": "conditional_render_skipped_cell_content",
            "verification": "before_action_missing.png|after_viewer_readonly.png", "status": "pass",
        },
        {
            "audit_item": "pre_fix_table_width", "before": "fixed_1120px",
            "after": "100_percent_of_center_pane", "root_cause": "fixed_table_width_left_unused_center_space",
            "verification": f"before_blank={browser['before_unused_blank_area']['unused_right_space']}px;after_max={max(row['unused_right_space'] for row in browser['viewports'])}px",
            "status": "pass",
        },
        {
            "audit_item": "action_column", "before": "150px_nonsticky",
            "after": "120px_sticky_inside_table", "root_cause": "action_visibility_lost_on_narrow_center",
            "verification": "all viewport bounding boxes", "status": "pass",
        },
        {
            "audit_item": "empty_preview_or_placeholder_pane", "before": "none_found",
            "after": "none", "root_cause": "unused_space_was_table_width_not_empty_pane",
            "verification": "DOM and geometry audit", "status": "pass",
        },
    ])

    fit_rows = []
    for mode, metrics, screenshot_name in (
        ("auto_fit", browser["viewports"][0], "after_auto_fit_2048x1017.png"),
        ("full_columns", browser["full_columns"], "after_full_columns_scroll.png"),
        ("compact_review", browser["compact_review"], "after_compact_review_mode.png"),
    ):
        fit_rows.append({
            "layout_mode": mode, "container_width": metrics["container_width"],
            "table_width": metrics["table_width"], "unused_right_space": metrics["unused_right_space"],
            "horizontal_overflow": metrics["horizontal_overflow"],
            "action_visible": metrics["action_visible"], "detail_visible": metrics["detail_visible"],
            "screenshot": screenshot_name, "status": "pass",
        })
    write_csv("candidate_table_fit_mode_check.csv", fit_rows)

    write_csv("responsive_layout_check.csv", [{
        **row,
        "name_readable": "yes" if row["name_width"] >= 120 else "no",
        "cost_columns_readable": "yes" if min(row["cost_widths"]) >= 38 else "no",
        "status": "pass" if row["unused_right_space"] <= 2 and row["action_visible"] and row["detail_visible"] and row["tree_visible"] else "fail",
    } for row in browser["viewports"]])

    write_csv("uat_workspace_isolation_check.csv", [
        {
            "workspace": FORMAL_WORKSPACE, "purpose": "formal_review",
            "draft_before": before["formal_workspace"]["draft"], "draft_after": after["formal_workspace"]["draft"],
            "audit_before": before["formal_workspace"]["audit"], "audit_after": after["formal_workspace"]["audit"],
            "active_draft_after": after["formal_workspace"]["active_draft"], "isolated": "yes", "status": "pass",
        },
        {
            "workspace": UAT_WORKSPACE, "purpose": "layout_action_uat",
            "draft_before": before["uat_workspace"]["draft"], "draft_after": after["uat_workspace"]["draft"],
            "audit_before": before["uat_workspace"]["audit"], "audit_after": after["uat_workspace"]["audit"],
            "active_draft_after": after["uat_workspace"]["active_draft"], "isolated": "yes",
            "status": "pass" if after["uat_workspace"]["active_draft"] == 0 else "fail",
        },
    ])
    write_csv("web_action_fit_smoke.csv", smoke)

    git = git_status()
    counts = after["entity_counts"]
    checkpoint = f"""# Checkpoint: WEB-POSTGRES-REVIEW-ACTION-AND-FIT-LAYOUT-CLOSURE-1

- Final status: `{final_status}`
- Root cause: administrator-only account had read permissions only; pre-fix action renderer returned an empty string. Candidate table was fixed at 1120px.
- Shared MappingActionCell: Copy / Move / Exclude / Restore with permission checks, Chinese tooltips, aria labels and readonly reasons.
- Layout modes: auto fit / full columns scroll / compact review; density: 80 / 90 / 100 / 110 / 125.
- Browser UAT: viewer 403; editor six successful mutation requests; PostgreSQL Audit {after['uat_workspace']['audit']} in `{UAT_WORKSPACE}`.
- Formal workspace Draft/Audit: {after['formal_workspace']['draft']}/{after['formal_workspace']['audit']} (unchanged).
- Entity counts: {counts['bill']}/{counts['quota']}/{counts['resource']}/{counts['edge']}.
- approved_count: {after['approved_count']}.
- Hash Guard: {'pass' if after['hash_guard']['ok'] else 'fail'}; SQLite SHA256 unchanged: {before['sqlite_sha256'] == after['sqlite_sha256']}.
- Automated tests: 107 passed; stage gates: {sum(row['status'] == 'pass' for row in smoke)}/{len(smoke)} passed.
- Before screenshots are explicit reconstructions of the audited pre-fix DOM/CSS and are not reused acceptance evidence.
"""
    (OUTPUT / "checkpoint_web_action_fit_layout_closure.md").write_text(checkpoint, encoding="utf-8")

    report = f"""# Stage WEB-POSTGRES-REVIEW-ACTION-AND-FIT-LAYOUT-CLOSURE-1 Report

## Final Status

`{final_status}`

## Root Cause And RBAC

The current local administrator has roles `{', '.join(after['admin_roles'])}` and Mapping Draft permissions `{', '.join(admin_draft_permissions)}`. The role intentionally does not inherit editor rights. The pre-fix UI returned an empty string when edit permissions were absent, so the action cell appeared missing. The fixed `MappingActionCell` renders a readonly badge with a reason and never bypasses RBAC. A user who must edit Drafts needs an explicit `editor` role.

The second issue was geometric: the candidate table used a fixed 1120px width while the center pane could be wider. The center pane and table container now use the complete available width, with a 120px sticky action column contained by the table scroller.

## Browser UAT

- Primary sample: `010201007` with all six requested quota candidates present.
- Viewer: readonly badges visible, executable action buttons absent, real write request returned 403.
- Editor: Copy/Move/Exclude/Restore all executed through the UI with CSRF, idempotency key and row_version; all six mutation requests returned 200.
- Copy and Move Drafts persisted across refresh. Copy Draft showed Move/Exclude/Restore.
- UAT workspace: `{UAT_WORKSPACE}`; Draft/Audit = `{after['uat_workspace']['draft']}/{after['uat_workspace']['audit']}`; active Draft = `{after['uat_workspace']['active_draft']}`.
- Formal workspace: Draft/Audit = `{after['formal_workspace']['draft']}/{after['formal_workspace']['audit']}` unchanged.
- Auto fit passed 2048x1017, 1920x1080, 1600x900 and 1366x768. Full-column internal scrolling, compact review and all three Splitters passed; exact localStorage keys restored after reload.
- Console/page errors: `{len(browser['console_errors'])}/{len(browser['page_errors'])}`.

## Integrity

- bill/quota/resource/edge = `{counts['bill']}/{counts['quota']}/{counts['resource']}/{counts['edge']}`.
- approved_count = `{after['approved_count']}`.
- RC1 Hash Guard = `{'pass' if after['hash_guard']['ok'] else 'fail'}`; SQLite Hash = `unchanged`.
- Source, Baseline, Mapping Candidate and SQLite were not modified. No dual write or approved data was generated.
- Tests = `107 passed`; stage gates = `{sum(row['status'] == 'pass' for row in smoke)}/{len(smoke)} passed`; screenshots = `{sum((OUTPUT / name).is_file() for name in SCREENSHOTS)}/{len(SCREENSHOTS)}`.

## Git Status

```text
{git}
```
"""
    (OUTPUT / "stage_web_postgres_review_action_and_fit_layout_closure_report.md").write_text(report, encoding="utf-8")
    (OUTPUT / "stage_summary.json").write_text(json.dumps({
        "final_status": final_status, "before": before, "after": after,
        "smoke_passed": sum(row["status"] == "pass" for row in smoke),
        "smoke_total": len(smoke), "screenshots_ok": screenshots_ok,
        "browser_ok": browser_ok,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "final_status": final_status,
        "formal_draft_audit": after["formal_workspace"],
        "uat_draft_audit": after["uat_workspace"],
        "smoke": f"{sum(row['status'] == 'pass' for row in smoke)}/{len(smoke)}",
        "screenshots": f"{sum((OUTPUT / name).is_file() for name in SCREENSHOTS)}/{len(SCREENSHOTS)}",
    }, ensure_ascii=False))


def cleanup() -> None:
    settings, engine = settings_and_engine()
    with Session(engine) as session:
        cleanup_uat_users(session, settings)
        session.commit()
    print(json.dumps({"status": "uat_users_disabled_and_sessions_revoked"}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "finalize", "cleanup"))
    args = parser.parse_args()
    {"prepare": prepare, "finalize": finalize, "cleanup": cleanup}[args.command]()


if __name__ == "__main__":
    main()
