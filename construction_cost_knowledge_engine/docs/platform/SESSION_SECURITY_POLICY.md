# Session Security Policy

## Server Session

The cookie name defaults to `ai_construction_session`. It contains a cryptographically random opaque token. PostgreSQL `app_session` stores only a keyed SHA-256 digest, a separate CSRF digest, user/Tenant ownership, client metadata, idle and absolute expiry, revocation state, and optimistic `row_version`.

Defaults:

- idle timeout: 30 minutes;
- absolute timeout: 12 hours;
- cookie: `HttpOnly`, `SameSite=Lax`, `Path=/`;
- local HTTP: `Secure=false`;
- NAS HTTPS: `Secure=true` is mandatory.

All values are environment-configurable. Session tokens are never accepted in URLs, request bodies, or local browser storage.

## Lifecycle

Login always creates a new Session ID. Activity extends only the idle deadline and never the absolute deadline. Expired, revoked, disabled-user, service-account, or inactive-Tenant sessions are rejected. Users can revoke individual sessions or every session except the current browser. User disable and administrator password reset revoke all sessions. Password change revokes every other session.

## CSRF

All authenticated `POST`, `PUT`, `PATCH`, and `DELETE` operations require `X-CSRF-Token`. The value is deterministically session-bound, returned by `/me`, retained only in page memory, and checked against the database digest using constant-time comparison. SameSite is an additional control, not the sole defense.

## Login Protection

Failures are counted within configurable windows for both normalized username and client IP. Reaching `AUTH_MAX_FAILED_ATTEMPTS` causes a configurable temporary lock. Unknown, disabled, locked, and incorrect-password users receive the same credential failure response. Login success/failure, logout, revocation, and CSRF denial are audited without secret material.
