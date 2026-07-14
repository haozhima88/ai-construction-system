from __future__ import annotations

import os
import secrets
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import String, cast, func, inspect, select, text
from sqlalchemy.orm import Session

from platform_db.api import app
from platform_db.config import Settings, get_settings
from platform_db.dependencies import enforce_tenant_scope, get_db_session
from platform_db.importers.hash_guard import validate_rc1_manifest
from platform_db.models import (
    AppLoginAttempt, AppPermission, AppRole, AppSecurityEvent, AppSession, AppTenant,
    AppUser, AppUserRoleAssignment, MappingCandidateEdge, ReferenceBillItem,
    ReferenceQuotaItem, ReferenceQuotaResource,
)
from platform_db.repositories import TenantAuthRepository
from platform_db.security import hash_password, token_hash, verify_password
from platform_db.services.authentication import AuthContext, load_auth_context
from platform_db.services.security_catalog import (
    PERMISSIONS, ROLE_PERMISSIONS, bootstrap_initial_administrator, seed_security_catalog,
)
from platform_db.services.separation_of_duty import DutyActors, SeparationOfDutyPolicy, SeparationOfDutyViolation


@dataclass
class Harness:
    session: Session
    client: TestClient
    settings: Settings
    tenant: AppTenant
    system_user: AppUser
    users: dict[str, AppUser]
    passwords: dict[str, str]
    roles: dict[str, AppRole]

    def login(self, label: str, client: TestClient | None = None):
        target = client or self.client
        return target.post("/api/v1/auth/login", json={
            "username": self.users[label].login_name,
            "password": self.passwords[label],
        })


@pytest.fixture(scope="module")
def auth_harness(engine):
    keys = {
        "PLATFORM_TENANT_CODE": f"auth-test-{uuid.uuid4().hex[:10]}",
        "PLATFORM_SESSION_HASH_SECRET": secrets.token_urlsafe(48),
        "SESSION_IDLE_TIMEOUT_MINUTES": "30",
        "SESSION_ABSOLUTE_TIMEOUT_HOURS": "12",
        "SESSION_COOKIE_SECURE": "false",
        "SESSION_COOKIE_SAMESITE": "lax",
        "SESSION_COOKIE_NAME": "ai_construction_session",
        "AUTH_MAX_FAILED_ATTEMPTS": "3",
        "AUTH_FAILURE_WINDOW_MINUTES": "15",
        "AUTH_LOCKOUT_MINUTES": "15",
        "PLATFORM_BOOTSTRAP_ADMIN_USERNAME": "",
        "PLATFORM_BOOTSTRAP_ADMIN_PASSWORD": "",
    }
    previous = {name: os.environ.get(name) for name in keys}
    os.environ.update(keys)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    tenant = AppTenant(
        tenant_id=uuid.uuid4(), tenant_code=keys["PLATFORM_TENANT_CODE"],
        tenant_name="Authentication Test Tenant", status="active",
    )
    session.add(tenant)
    system_user = AppUser(
        app_user_id=uuid.uuid4(), tenant_id=tenant.tenant_id,
        login_name="platform-system-import", login_name_normalized="platform-system-import",
        display_name="Authentication Test System", status="active",
        is_service_account=True, must_change_password=False, auth_version=1,
    )
    session.add(system_user)
    session.flush()
    settings = replace(
        get_settings(), tenant_code=tenant.tenant_code,
        session_hash_secret=keys["PLATFORM_SESSION_HASH_SECRET"],
        auth_max_failed_attempts=3,
        bootstrap_admin_username="", bootstrap_admin_password="",
    )
    seed_security_catalog(session, settings)
    roles = {role.role_code: role for role in session.scalars(select(AppRole)).all()}
    users: dict[str, AppUser] = {}
    passwords: dict[str, str] = {}

    def add_user(label: str, role_code: str, *, active: bool = True, must_change: bool = False) -> None:
        password = f"{secrets.token_urlsafe(18)}Aa1!"
        user = AppUser(
            app_user_id=uuid.uuid4(), tenant_id=tenant.tenant_id,
            login_name=f"{label}-{uuid.uuid4().hex[:6]}", login_name_normalized="",
            display_name=label.replace("_", " ").title(), status="active" if active else "inactive",
            password_hash=hash_password(password), password_changed_at=datetime.now(timezone.utc),
            must_change_password=must_change, is_service_account=False, auth_version=1,
            created_by=system_user.app_user_id,
        )
        user.login_name_normalized = user.login_name.casefold()
        session.add(user)
        session.flush()
        session.add(AppUserRoleAssignment(
            assignment_id=uuid.uuid4(), tenant_id=tenant.tenant_id,
            app_user_id=user.app_user_id, app_role_id=roles[role_code].app_role_id,
            effective_from=datetime.now(timezone.utc), assigned_by=system_user.app_user_id,
            status="active", created_by=system_user.app_user_id,
        ))
        users[label] = user
        passwords[label] = password

    for label, role in (
        ("admin", "administrator"), ("viewer", "viewer"), ("editor", "editor"),
        ("reviewer", "reviewer"), ("approver", "approver"),
        ("forced", "viewer"), ("disabled", "viewer"), ("session_user", "viewer"),
        ("password_user", "viewer"), ("reset_user", "viewer"),
    ):
        add_user(label, role, active=label != "disabled", must_change=label == "forced")
    session.flush()

    def override_db():
        yield session
        session.flush()

    app.dependency_overrides[get_db_session] = override_db
    client = TestClient(app)
    harness = Harness(session, client, settings, tenant, system_user, users, passwords, roles)
    yield harness
    app.dependency_overrides.pop(get_db_session, None)
    client.close()
    session.close()
    transaction.rollback()
    connection.close()
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def _csrf(response) -> dict[str, str]:
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_auth_01_authentication_schema_is_migrated(engine):
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) in {
            "0002_authentication_session_rbac", "0003_postgres_review_cutover",
        }
    assert {"app_session", "app_login_attempt", "app_password_history", "app_permission", "app_role_permission", "app_security_event"} <= set(inspect(engine).get_table_names())


def test_auth_02_bootstrap_admin_is_idempotent(auth_harness):
    h = auth_harness
    tenant = AppTenant(tenant_id=uuid.uuid4(), tenant_code=f"bootstrap-{uuid.uuid4().hex[:8]}", tenant_name="Bootstrap Test", status="active")
    h.session.add(tenant)
    service = AppUser(
        app_user_id=uuid.uuid4(), tenant_id=tenant.tenant_id, login_name="platform-system-import",
        login_name_normalized="platform-system-import", display_name="Bootstrap Service", status="active",
        is_service_account=True, must_change_password=False, auth_version=1,
    )
    h.session.add(service); h.session.flush()
    password = f"{secrets.token_urlsafe(18)}Aa1!"
    settings = replace(h.settings, tenant_code=tenant.tenant_code, bootstrap_admin_username="initial-admin", bootstrap_admin_password=password)
    seed_security_catalog(h.session, settings)
    first = bootstrap_initial_administrator(h.session, settings)
    second = bootstrap_initial_administrator(h.session, settings)
    assert first == {"status": "created", "created": True}
    assert second == {"status": "skipped_existing_local_user", "created": False}


def test_auth_03_password_hash_is_argon2id(auth_harness):
    stored = auth_harness.users["viewer"].password_hash
    assert stored.startswith("$argon2id$")
    assert verify_password(stored, auth_harness.passwords["viewer"])


def test_auth_04_plaintext_password_is_not_persisted(auth_harness):
    h = auth_harness
    plain = h.passwords["viewer"]
    assert plain not in h.users["viewer"].password_hash
    assert h.session.scalar(select(func.count()).select_from(AppSecurityEvent).where(AppSecurityEvent.reason.ilike(f"%{plain}%"))) == 0


def test_auth_05_login_success(auth_harness):
    response = auth_harness.login("viewer")
    assert response.status_code == 200
    assert response.json()["user"]["login_name"] == auth_harness.users["viewer"].login_name


def test_auth_06_login_failure_is_generic(auth_harness):
    client = TestClient(app, client=("failed-user-client", 50001))
    response = client.post("/api/v1/auth/login", json={"username": auth_harness.users["viewer"].login_name, "password": "incorrect-password"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"
    client.close()


def test_auth_07_unknown_user_has_same_failure(auth_harness):
    client = TestClient(app, client=("missing-user-client", 50002))
    response = client.post("/api/v1/auth/login", json={"username": f"missing-{uuid.uuid4()}", "password": "incorrect-password"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"
    client.close()


def test_auth_08_disabled_user_cannot_login(auth_harness):
    client = TestClient(app, client=("disabled-user-client", 50003))
    response = auth_harness.login("disabled", client)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"
    client.close()


def test_auth_09_must_change_password_blocks_platform(auth_harness):
    response = auth_harness.login("forced")
    assert response.status_code == 200 and response.json()["user"]["must_change_password"] is True
    assert auth_harness.client.get("/api/v1/platform/reference/bills").status_code == 403


def test_auth_10_session_stores_only_token_hash(auth_harness):
    response = auth_harness.login("session_user")
    raw = auth_harness.client.cookies.get("ai_construction_session")
    row = auth_harness.session.scalar(select(AppSession).where(
        AppSession.app_user_id == auth_harness.users["session_user"].app_user_id,
        AppSession.status == "active",
    ).order_by(AppSession.created_at.desc()))
    assert raw and row.session_token_hash == token_hash(raw, auth_harness.settings.session_hash_secret)
    assert raw != row.session_token_hash and response.json()["csrf_token"] != row.csrf_token_hash


def test_auth_11_session_idle_timeout(auth_harness):
    response = auth_harness.login("session_user")
    raw = auth_harness.client.cookies.get("ai_construction_session")
    context = load_auth_context(auth_harness.session, auth_harness.settings, raw, touch=False)
    expired_at = context.app_session.expires_at + timedelta(seconds=1)
    assert load_auth_context(auth_harness.session, auth_harness.settings, raw, now=expired_at, touch=False) is None
    assert context.app_session.status == "expired"


def test_auth_12_session_can_be_individually_revoked(auth_harness):
    first, second = TestClient(app), TestClient(app)
    first_login = auth_harness.login("session_user", first)
    second_login = auth_harness.login("session_user", second)
    second_id = auth_harness.session.scalar(select(AppSession.session_id).where(
        AppSession.app_user_id == auth_harness.users["session_user"].app_user_id,
        AppSession.session_token_hash == token_hash(second.cookies.get("ai_construction_session"), auth_harness.settings.session_hash_secret),
    ))
    result = first.delete(f"/api/v1/auth/sessions/{second_id}", headers=_csrf(first_login))
    assert result.status_code == 200
    assert second.get("/api/v1/auth/me").status_code == 401
    first.close(); second.close()


def test_auth_13_password_change_revokes_other_sessions(auth_harness):
    first, second = TestClient(app), TestClient(app)
    first_login = auth_harness.login("password_user", first)
    auth_harness.login("password_user", second)
    new_password = f"{secrets.token_urlsafe(18)}Bb2!"
    result = first.post("/api/v1/auth/change-password", headers=_csrf(first_login), json={
        "current_password": auth_harness.passwords["password_user"], "new_password": new_password,
    })
    assert result.status_code == 200
    assert second.get("/api/v1/auth/me").status_code == 401
    first.close(); second.close()


def test_auth_14_cookie_is_httponly(auth_harness):
    response = auth_harness.login("viewer")
    assert "httponly" in response.headers["set-cookie"].lower()


def test_auth_15_cookie_is_samesite_lax(auth_harness):
    response = auth_harness.login("viewer")
    assert "samesite=lax" in response.headers["set-cookie"].lower()


def test_auth_16_secure_cookie_is_configurable(auth_harness):
    previous = os.environ["SESSION_COOKIE_SECURE"]
    os.environ["SESSION_COOKIE_SECURE"] = "true"
    try:
        response = auth_harness.login("viewer")
        assert "secure" in response.headers["set-cookie"].lower()
    finally:
        os.environ["SESSION_COOKIE_SECURE"] = previous


def test_auth_17_valid_csrf_is_accepted(auth_harness):
    response = auth_harness.login("viewer")
    result = auth_harness.client.post("/api/v1/auth/sessions/revoke-others", headers=_csrf(response))
    assert result.status_code == 200


def test_auth_18_invalid_csrf_is_rejected_and_audited(auth_harness):
    auth_harness.login("viewer")
    result = auth_harness.client.post("/api/v1/auth/sessions/revoke-others", headers={"X-CSRF-Token": "invalid"})
    assert result.status_code == 403
    assert auth_harness.session.scalar(select(func.count()).select_from(AppSecurityEvent).where(AppSecurityEvent.action == "csrf_rejected")) > 0


def test_auth_19_viewer_can_read_reference(auth_harness):
    auth_harness.login("viewer")
    response = auth_harness.client.get("/api/v1/platform/reference/bills", params={"page_size": 3})
    assert response.status_code == 200 and response.json()["total"] == 472


def test_auth_20_viewer_cannot_manage_users(auth_harness):
    response = auth_harness.login("viewer")
    denied = auth_harness.client.get("/api/v1/admin/users", headers=_csrf(response))
    assert denied.status_code == 403


def test_auth_21_editor_has_draft_permissions(auth_harness):
    payload = auth_harness.login("editor").json()
    assert {"mapping_draft.create", "mapping_draft.update", "mapping_draft.exclude"} <= set(payload["permissions"])
    assert "mapping_review.update" not in payload["permissions"]


def test_auth_22_reviewer_has_review_permission(auth_harness):
    payload = auth_harness.login("reviewer").json()
    assert {"mapping_review.update", "enterprise_price.review", "enterprise_quota.review"} <= set(payload["permissions"])
    assert "enterprise_quota.approve" not in payload["permissions"]


def test_auth_23_approver_has_approve_publish_permissions(auth_harness):
    payload = auth_harness.login("approver").json()
    assert {"enterprise_price.approve", "enterprise_price.publish", "enterprise_quota.approve", "enterprise_quota.publish"} <= set(payload["permissions"])
    assert "enterprise_quota.edit" not in payload["permissions"]


def test_auth_24_administrator_can_create_user(auth_harness):
    login = auth_harness.login("admin")
    username = f"created-{uuid.uuid4().hex[:8]}"
    response = auth_harness.client.post("/api/v1/admin/users", headers=_csrf(login), json={
        "username": username, "display_name": "Created User", "email": None,
        "initial_password": f"{secrets.token_urlsafe(18)}Cc3!",
    })
    assert response.status_code == 200
    assert response.json()["must_change_password"] is True


def test_auth_25_permission_denied_is_audited(auth_harness):
    auth_harness.login("viewer")
    auth_harness.client.get("/api/v1/admin/users")
    assert auth_harness.session.scalar(select(func.count()).select_from(AppSecurityEvent).where(AppSecurityEvent.action == "permission_denied")) > 0


def test_auth_26_tenant_repository_and_guard_isolate(auth_harness):
    h = auth_harness
    other = AppTenant(tenant_id=uuid.uuid4(), tenant_code=f"other-{uuid.uuid4().hex[:8]}", tenant_name="Other Tenant", status="active")
    h.session.add(other); h.session.flush()
    other_user = AppUser(
        app_user_id=uuid.uuid4(), tenant_id=other.tenant_id, login_name="other-user",
        login_name_normalized="other-user", display_name="Other User", status="active",
        password_hash=hash_password(f"{secrets.token_urlsafe(18)}Dd4!"), must_change_password=False,
        is_service_account=False, auth_version=1,
    )
    h.session.add(other_user); h.session.flush()
    assert TenantAuthRepository(h.session, h.tenant.tenant_id).user(other_user.app_user_id) is None
    login = h.login("viewer")
    context = load_auth_context(h.session, h.settings, h.client.cookies.get("ai_construction_session"))
    with pytest.raises(HTTPException):
        enforce_tenant_scope(h.session, context, other.tenant_id)


def test_auth_27_quota_separation_of_duty(auth_harness):
    actor = auth_harness.users["admin"].app_user_id
    with pytest.raises(SeparationOfDutyViolation):
        SeparationOfDutyPolicy.enforce("enterprise_quota", DutyActors(creator_id=actor, reviewer_id=actor))
    with pytest.raises(SeparationOfDutyViolation):
        SeparationOfDutyPolicy.enforce("enterprise_quota", DutyActors(editor_id=actor, approver_id=actor))


def test_auth_28_price_separation_applies_to_administrator(auth_harness):
    actor = auth_harness.users["admin"].app_user_id
    with pytest.raises(SeparationOfDutyViolation):
        SeparationOfDutyPolicy.enforce("enterprise_price", DutyActors(submitter_id=actor, approver_id=actor))


def test_auth_29_break_glass_requires_reason_and_audit(auth_harness):
    h = auth_harness; actor = h.users["admin"].app_user_id
    with pytest.raises(SeparationOfDutyViolation):
        SeparationOfDutyPolicy.enforce("enterprise_price", DutyActors(submitter_id=actor, approver_id=actor), break_glass=True)
    SeparationOfDutyPolicy.enforce(
        "enterprise_price", DutyActors(submitter_id=actor, approver_id=actor),
        break_glass=True, break_glass_reason="documented validation override",
        session=h.session, tenant_id=h.tenant.tenant_id, actor_user_id=actor,
    )
    assert h.session.scalar(select(func.count()).select_from(AppSecurityEvent).where(AppSecurityEvent.action == "break_glass_used")) > 0


def test_auth_30_rc1_counts_unchanged(auth_harness):
    session = auth_harness.session
    assert (
        session.scalar(select(func.count()).select_from(ReferenceBillItem)),
        session.scalar(select(func.count()).select_from(ReferenceQuotaItem)),
        session.scalar(select(func.count()).select_from(ReferenceQuotaResource)),
        session.scalar(select(func.count()).select_from(MappingCandidateEdge)),
    ) == (472, 3700, 24981, 1882)


def test_auth_31_source_baseline_mapping_hash_guard(project_root):
    result = validate_rc1_manifest(project_root, get_settings().rc1_manifest_path)
    assert result["ok"] is True and result["failures"] == []


def test_auth_32_approved_count_remains_zero(auth_harness):
    session = auth_harness.session
    total = 0
    for table in (ReferenceBillItem, ReferenceQuotaItem, ReferenceQuotaResource, MappingCandidateEdge):
        total += int(session.scalar(select(func.count()).select_from(table).where(cast(table.review_status, String) == "approved")) or 0)
    assert total == 0


def test_auth_33_security_headers_present(auth_harness):
    response = auth_harness.client.get("/login")
    for name in ("x-content-type-options", "referrer-policy", "content-security-policy", "x-frame-options", "permissions-policy"):
        assert name in response.headers


def test_auth_34_health_is_anonymous_and_minimal(auth_harness):
    response = auth_harness.client.get("/api/v1/platform/health")
    assert response.status_code == 200
    assert set(response.json()) == {"status", "application_version", "database_connectivity"}


def test_auth_35_no_public_registration_route(auth_harness):
    response = auth_harness.client.post("/api/v1/auth/register", json={})
    assert response.status_code == 404


def test_auth_36_frontend_does_not_use_local_storage():
    root = Path(__file__).resolve().parents[1] / "web"
    auth_scripts = ("auth.js", "login.js", "logout.js", "account.js", "users.js")
    scripts = "\n".join(
        (root / "static" / name).read_text(encoding="utf-8")
        for name in auth_scripts if (root / "static" / name).exists()
    )
    assert "localStorage" not in scripts and "sessionStorage" not in scripts
    review_script = (root / "static" / "review.js").read_text(encoding="utf-8")
    assert "session_token" not in review_script and "csrf_token:" not in review_script


def test_auth_37_username_and_ip_rate_limit(auth_harness):
    username = f"rate-{uuid.uuid4().hex}"
    client = TestClient(app, client=("rate-limit-client", 50004))
    statuses = [client.post("/api/v1/auth/login", json={"username": username, "password": "wrong-password"}).status_code for _ in range(4)]
    assert statuses[:3] == [401, 401, 401] and statuses[3] == 429
    client.close()


def test_auth_38_password_reset_revokes_sessions(auth_harness):
    user_client = TestClient(app)
    auth_harness.login("reset_user", user_client)
    admin_login = auth_harness.login("admin")
    response = auth_harness.client.post(
        f"/api/v1/admin/users/{auth_harness.users['reset_user'].app_user_id}/reset-password",
        headers=_csrf(admin_login), json={"new_password": f"{secrets.token_urlsafe(18)}Ee5!"},
    )
    assert response.status_code == 200
    assert user_client.get("/api/v1/auth/me").status_code == 401
    user_client.close()


def test_auth_39_permission_catalog_is_complete(auth_harness):
    assert len(PERMISSIONS) == 28
    assert set(ROLE_PERMISSIONS) == {"viewer", "editor", "reviewer", "approver", "administrator"}
    assert auth_harness.session.scalar(select(func.count()).select_from(AppPermission)) >= 28


def test_auth_40_login_and_logout_are_audited(auth_harness):
    response = auth_harness.login("viewer")
    assert auth_harness.client.post("/api/v1/auth/logout", headers=_csrf(response)).status_code == 200
    actions = set(auth_harness.session.scalars(select(AppSecurityEvent.action).where(
        AppSecurityEvent.app_user_id == auth_harness.users["viewer"].app_user_id,
        AppSecurityEvent.action.in_(("login_success", "logout")),
    )))
    assert actions == {"login_success", "logout"}
