from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from platform_db.models import AppSecurityEvent


SECURITY_EVENT_TYPES = (
    "login_success", "login_failed", "logout", "session_revoked", "password_changed",
    "password_reset", "user_created", "user_disabled", "role_assigned", "role_removed",
    "permission_denied", "csrf_rejected", "tenant_scope_rejected", "break_glass_used",
)
SENSITIVE_PATTERN = re.compile(
    r"(?i)(password|password_hash|session_token|csrf_token|cookie|authorization|\$argon2)"
)


def sanitize_reason(reason: str | None) -> str | None:
    if not reason:
        return None
    return "[redacted]" if SENSITIVE_PATTERN.search(reason) else reason[:512]


def request_metadata(request: Request | None) -> dict[str, str | None]:
    if request is None:
        return {"client_ip": None, "user_agent": None, "request_id": None}
    state_request_id = getattr(request.state, "request_id", None)
    return {
        "client_ip": (request.client.host if request.client else None),
        "user_agent": request.headers.get("user-agent", "")[:1024] or None,
        "request_id": str(state_request_id) if state_request_id else (
            request.headers.get("x-request-id", "")[:128] or None
        ),
    }


def record_security_event(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    action: str,
    object_type: str,
    result: str,
    app_user_id: uuid.UUID | None = None,
    object_id: str | uuid.UUID | None = None,
    reason: str | None = None,
    request: Request | None = None,
    correlation_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> AppSecurityEvent:
    metadata = request_metadata(request)
    event = AppSecurityEvent(
        security_event_id=uuid.uuid4(),
        tenant_id=tenant_id,
        app_user_id=app_user_id,
        action=action,
        object_type=object_type,
        object_id=str(object_id) if object_id is not None else None,
        result=result,
        reason=sanitize_reason(reason),
        client_ip=metadata["client_ip"],
        user_agent=metadata["user_agent"],
        request_id=metadata["request_id"],
        correlation_id=correlation_id,
        created_by=actor_user_id,
    )
    session.add(event)
    return event


def event_contains_sensitive_value(event: AppSecurityEvent) -> bool:
    values: list[Any] = [event.reason, event.object_id, event.request_id]
    return any(SENSITIVE_PATTERN.search(str(value)) for value in values if value)
