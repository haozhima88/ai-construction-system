from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from platform_db import __version__
from platform_db.config import get_settings
from platform_db.dependencies import SessionFactory, get_db_session, require_permission
from platform_db.models import MappingCandidateEdge, ReferenceBillItem, ReferenceQuotaItem, ReferenceQuotaResource
from platform_db.repositories import PlatformReadRepository
from platform_db.routers import admin_router, auth_router, enterprise_quota_router, review_router, sqlite_fallback_router
from platform_db.services.authentication import AuthContext, load_auth_context
from platform_db.services.security_catalog import bootstrap_initial_administrator, seed_security_catalog


WEB_ROOT = Path(__file__).resolve().parent / "web"
STATIC_ROOT = WEB_ROOT / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionFactory() as session:
        settings = get_settings()
        seed_security_catalog(session, settings)
        bootstrap_initial_administrator(session, settings)
        session.commit()
    yield


app = FastAPI(
    title="AI Construction Platform API",
    version=__version__,
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(enterprise_quota_router)
app.include_router(review_router)
app.include_router(sqlite_fallback_router)
app.mount("/platform-static", StaticFiles(directory=STATIC_ROOT), name="platform-static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    supplied_request_id = request.headers.get("x-request-id", "")
    try:
        request.state.request_id = uuid.UUID(supplied_request_id)
    except (ValueError, TypeError, AttributeError):
        request.state.request_id = uuid.uuid4()
    response = await call_next(request)
    response.headers["X-Request-ID"] = str(request.state.request_id)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    is_pdf_preview = request.url.path.endswith("/pdf")
    frame_ancestors = "'self'" if is_pdf_preview else "'none'"
    response.headers["X-Frame-Options"] = "SAMEORIGIN" if is_pdf_preview else "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; "
        f"frame-ancestors {frame_ancestors}; form-action 'self'"
    )
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith(
        ("/api/v1/auth", "/api/v1/admin", "/api/v1/review", "/api/v1/enterprise-quota")
    ) else "no-cache"
    return response


def response(payload) -> JSONResponse:
    return JSONResponse(jsonable_encoder(payload))


def pagination(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500)) -> tuple[int, int]:
    return page, page_size


@app.get("/api/v1/platform/health")
def health(db: Session = Depends(get_db_session)):
    connected = False
    try:
        connected = db.scalar(text("SELECT 1")) == 1
    except Exception:
        connected = False
    return {"status": "ok" if connected else "degraded", "application_version": __version__, "database_connectivity": connected}


@app.get("/api/v1/platform/reference/bills")
def bills(
    paging: tuple[int, int] = Depends(pagination), sort: str = "bill_code_9", q: str | None = None,
    release_id: str | None = None, source_family: str | None = None,
    _: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session),
):
    return response(PlatformReadRepository(db).bills(
        page=paging[0], page_size=paging[1], sort=sort, q=q, release_id=release_id, source_family=source_family,
    ))


@app.get("/api/v1/platform/reference/bills/{item_id}")
def bill(
    item_id: uuid.UUID,
    _: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session),
):
    item = PlatformReadRepository(db).bill(item_id)
    if item is None:
        raise HTTPException(404, "Bill item not found")
    return response(item)


@app.get("/api/v1/platform/reference/quotas")
def quotas(
    paging: tuple[int, int] = Depends(pagination), sort: str = "source_code", q: str | None = None,
    release_id: str | None = None, source_family: str | None = None,
    _: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session),
):
    return response(PlatformReadRepository(db).quotas(
        page=paging[0], page_size=paging[1], sort=sort, q=q, release_id=release_id, source_family=source_family,
    ))


@app.get("/api/v1/platform/reference/quotas/{item_id}")
def quota(
    item_id: uuid.UUID,
    _: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session),
):
    item = PlatformReadRepository(db).quota(item_id)
    if item is None:
        raise HTTPException(404, "Quota item not found")
    return response(item)


@app.get("/api/v1/platform/reference/quotas/{item_id}/resources")
def quota_resources(
    item_id: uuid.UUID, paging: tuple[int, int] = Depends(pagination),
    _: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session),
):
    repository = PlatformReadRepository(db)
    if repository.quota(item_id) is None:
        raise HTTPException(404, "Quota item not found")
    return response(repository.quota_resources(item_id, paging[0], paging[1]))


@app.get("/api/v1/platform/reference/quotas/{item_id}/rules")
def quota_rules(
    item_id: uuid.UUID,
    _: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session),
):
    repository = PlatformReadRepository(db)
    if repository.quota(item_id) is None:
        raise HTTPException(404, "Quota item not found")
    items = repository.quota_rules(item_id)
    return response({"items": items, "total": len(items)})


@app.get("/api/v1/platform/mappings")
def mappings(
    paging: tuple[int, int] = Depends(pagination), sort: str = "bill_code_9", q: str | None = None,
    release_id: str | None = None, source_family: str | None = None,
    _: AuthContext = Depends(require_permission("mapping.read")), db: Session = Depends(get_db_session),
):
    return response(PlatformReadRepository(db).mappings(
        page=paging[0], page_size=paging[1], sort=sort, q=q, release_id=release_id, source_family=source_family,
    ))


@app.get("/api/v1/platform/releases")
def releases(
    _: AuthContext = Depends(require_permission("release.read")), db: Session = Depends(get_db_session),
):
    return response(PlatformReadRepository(db).releases())


@app.get("/platform-rc1-validation")
def platform_rc1_validation(
    _: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session),
):
    counts = {
        "bill": db.scalar(select(func.count()).select_from(ReferenceBillItem)),
        "quota": db.scalar(select(func.count()).select_from(ReferenceQuotaItem)),
        "resource": db.scalar(select(func.count()).select_from(ReferenceQuotaResource)),
        "mapping_edge": db.scalar(select(func.count()).select_from(MappingCandidateEdge)),
    }
    expected = {"bill": 472, "quota": 3700, "resource": 24981, "mapping_edge": 1882}
    return {"status": "pass" if counts == expected else "fail", "counts": counts, "expected": expected}


def _page(name: str) -> FileResponse:
    return FileResponse(WEB_ROOT / name, media_type="text/html; charset=utf-8")


def _review_page(api_base: str, mode: str, mode_label: str) -> HTMLResponse:
    content = (WEB_ROOT / "review.html").read_text(encoding="utf-8")
    content = content.replace("{{API_BASE}}", api_base)
    content = content.replace("{{MODE}}", mode)
    content = content.replace("{{MODE_LABEL}}", mode_label)
    return HTMLResponse(content)


def _page_context(request: Request, db: Session) -> AuthContext | None:
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name, "")
    return load_auth_context(db, settings, raw_token)


def _login_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(url=f"/login?next={request.url.path}", status_code=303)


def _change_password_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(url=f"/change-password?next={request.url.path}", status_code=303)


def _protected_page_context(request: Request, db: Session) -> AuthContext | RedirectResponse:
    context = _page_context(request, db)
    if context is None:
        return _login_redirect(request)
    if context.user.must_change_password:
        return _change_password_redirect(request)
    return context


@app.get("/login", include_in_schema=False)
def login_page():
    return _page("login.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/logout", include_in_schema=False)
def logout_page():
    return _page("logout.html")


@app.get("/change-password", include_in_schema=False)
def change_password_page(request: Request, db: Session = Depends(get_db_session)):
    if _page_context(request, db) is None:
        return _login_redirect(request)
    return _page("change-password.html")


@app.get("/platform-account", include_in_schema=False)
def account_page(request: Request, db: Session = Depends(get_db_session)):
    if _page_context(request, db) is None:
        return _login_redirect(request)
    return _page("account.html")


@app.get("/platform-admin/users", include_in_schema=False)
def users_page(request: Request, db: Session = Depends(get_db_session)):
    context = _protected_page_context(request, db)
    if isinstance(context, RedirectResponse):
        return context
    if "administrator" not in context.roles:
        raise HTTPException(403, "Administrator role required")
    return _page("users.html")


@app.get("/quota-building-pg", include_in_schema=False)
def quota_building_pg(request: Request, db: Session = Depends(get_db_session)):
    context = _protected_page_context(request, db)
    if isinstance(context, RedirectResponse):
        return context
    return _review_page("/api/v1/review", "postgres", "PostgreSQL RC1")


@app.get("/enterprise-quota", include_in_schema=False)
@app.get("/enterprise-quota/a111-pilot", include_in_schema=False)
def enterprise_quota_page(request: Request, db: Session = Depends(get_db_session)):
    context = _protected_page_context(request, db)
    if isinstance(context, RedirectResponse):
        return context
    if "enterprise_quota.read" not in context.permissions:
        raise HTTPException(403, "Enterprise Quota read permission required")
    return _page("enterprise-quota.html")


@app.get("/quota-building", include_in_schema=False)
def quota_building(request: Request, db: Session = Depends(get_db_session)):
    settings = get_settings()
    if settings.quota_building_backend == "postgres":
        context = _protected_page_context(request, db)
        if isinstance(context, RedirectResponse):
            return context
        return _review_page("/api/v1/review", "postgres", "PostgreSQL RC1")
    if settings.quota_building_sqlite_fallback_enabled:
        return _review_page("/api/v1/review-sqlite", "sqlite", "SQLite read-only fallback")
    raise HTTPException(503, "Quota-building backend is unavailable")


@app.get("/quota-building-sqlite", include_in_schema=False)
def quota_building_sqlite():
    if not get_settings().quota_building_sqlite_fallback_enabled:
        raise HTTPException(404, "SQLite fallback is disabled")
    return _review_page("/api/v1/review-sqlite", "sqlite", "SQLite read-only fallback")


@app.get("/quota-building-legacy", include_in_schema=False)
def quota_building_legacy():
    if not get_settings().quota_building_sqlite_fallback_enabled:
        raise HTTPException(404, "SQLite fallback is disabled")
    return _review_page("/api/v1/review-sqlite", "sqlite", "Legacy SQLite read-only")
