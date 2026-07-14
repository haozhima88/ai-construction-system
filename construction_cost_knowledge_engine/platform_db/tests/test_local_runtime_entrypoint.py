from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from platform_db.local_runtime import REQUIRED_ENVIRONMENT, load_local_environment
from platform_db.web_app import app


ENGINE_ROOT = Path(__file__).resolve().parents[2]


def route_paths() -> set[str]:
    return {getattr(route, "path", "") for route in app.router.routes}


def test_runtime_01_composite_entrypoint_has_required_pages():
    required = {
        "/login", "/logout", "/change-password", "/platform-account", "/platform-admin/users",
        "/quota-building", "/quota-building-pg", "/quota-building-sqlite",
        "/quota-building-legacy", "/quota-a111",
    }
    assert required <= route_paths()


def test_runtime_02_composite_entrypoint_has_required_apis():
    required = {
        "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/me",
        "/api/v1/auth/change-password", "/api/v1/platform/health",
        "/api/v1/review/summary", "/api/quota-a111/tree",
    }
    assert required <= route_paths()


def test_runtime_03_legacy_quota_building_routes_are_not_composed():
    assert "/api/quota-building/summary" not in route_paths()
    assert app.state.legacy_prototype_policy == "quota-a111 compatibility only"


def test_runtime_04_a111_page_is_preserved():
    client = TestClient(app)
    response = client.get("/quota-a111")
    assert response.status_code == 200
    assert "quota_a111_app.js" in response.text
    client.close()


def test_runtime_05_start_script_uses_unified_entrypoint():
    content = (ENGINE_ROOT / "start_platform_web.cmd").read_text(encoding="utf-8")
    assert "platform_db.local_runtime" in content
    assert "web_collab_prototype.app:app" not in content
    assert "legacy prototype only" in content


def test_runtime_06_environment_loader_reports_names_only(tmp_path, monkeypatch):
    for name in REQUIRED_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env.platform.local"
    env_file.write_text("PLATFORM_TENANT_CODE=platform-dev\n", encoding="utf-8")
    missing = load_local_environment(env_file)
    assert "PLATFORM_TENANT_CODE" not in missing
    assert set(missing) == set(REQUIRED_ENVIRONMENT) - {"PLATFORM_TENANT_CODE"}


def test_runtime_07_password_policy_reports_variable_names(monkeypatch):
    from platform_db.local_runtime import RuntimePreflightError, configure_process_environment

    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("PLATFORM_BOOTSTRAP_ADMIN_PASSWORD", "short")
    monkeypatch.setenv("PLATFORM_UAT_TEMP_PASSWORD", "also-short")
    try:
        configure_process_environment()
        raise AssertionError("Password policy should reject short local credentials")
    except RuntimePreflightError as exc:
        message = str(exc)
    assert "PLATFORM_BOOTSTRAP_ADMIN_PASSWORD" in message
    assert "PLATFORM_UAT_TEMP_PASSWORD" in message
    assert "short" not in message
