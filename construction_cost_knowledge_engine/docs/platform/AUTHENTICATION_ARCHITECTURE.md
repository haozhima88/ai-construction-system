# Authentication Architecture

## Scope

`PLATFORM-AUTHENTICATION-SESSION-RBAC-1` adds local identity to the independent Platform API. It does not switch `/quota-building`, `/quota-a111`, or `/quota-building-legacy`, and it creates no Enterprise Price or Enterprise Quota business records.

## Trust Flow

1. A local user submits username and password to `POST /api/v1/auth/login`.
2. The server normalizes the username, applies username and client-IP rate limits, and verifies an Argon2id password hash.
3. Successful authentication creates a random opaque server session. PostgreSQL stores only keyed SHA-256 token and CSRF digests.
4. The browser receives only the raw session token in an `HttpOnly` cookie. It receives the session-bound CSRF value from `/login` or `/me` and keeps it in JavaScript memory.
5. Each protected request resolves user, Tenant, roles, and permissions from the session. Tenant identifiers in query strings or request bodies are not trusted.
6. FastAPI dependencies enforce authentication, role, permission, Tenant, and CSRF rules on the server.

No self-registration route exists. Local users are created only by an administrator. The initial administrator is optional, one-time, environment-driven, idempotent, and marked `must_change_password=true`.

## Components

- `platform_db.security.crypto`: Argon2id, opaque token generation, keyed digests.
- `platform_db.services.authentication`: login, lockout, Session lifecycle, password change.
- `platform_db.services.security_catalog`: 28 permissions, five role mappings, administrator bootstrap.
- `platform_db.dependencies`: `get_current_session`, `get_current_user`, `require_permission`, `require_role`, `require_tenant_scope`, and CSRF enforcement.
- `platform_db.services.security_audit`: append-only, redacted security events.
- `platform_db.services.separation_of_duty`: Enterprise Price/Quota actor separation and audited break-glass.

## Protected Surface

Platform Reference, Mapping, Release, and RC1 validation APIs require a valid server session and the appropriate read permission. `/api/v1/platform/health` remains anonymous and returns only status, application version, and database connectivity.

## Secret Boundary

Passwords, password hashes, raw Session tokens, raw CSRF tokens, cookies, and authorization values are never placed in security events, exception details, or application logs. `PLATFORM_SESSION_HASH_SECRET` and bootstrap credentials are environment secrets and must not be committed.
