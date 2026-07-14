# Authentication Runbook

## Required Environment

Set a random `PLATFORM_SESSION_HASH_SECRET` of at least 32 characters. For first initialization only, set `PLATFORM_BOOTSTRAP_ADMIN_USERNAME`, `PLATFORM_BOOTSTRAP_ADMIN_PASSWORD`, and optional display name. Placeholder values are rejected. Bootstrap creates an administrator only when the Tenant has no local user, requires password change, never logs the password, and never overwrites an existing account.

Local HTTP uses `SESSION_COOKIE_SECURE=false`. Set it to `true` before any NAS HTTPS deployment. Keep `SESSION_COOKIE_SAMESITE=lax` or use `strict` after workflow validation.

## Migration and Bootstrap

```powershell
$env:PYTHONPATH='.'
python -m alembic -c platform_db/alembic.ini upgrade head
python -m platform_db.bootstrap
```

`platform_db.bootstrap` revalidates and idempotently imports RC1, initializes 28 permissions and five roles, and performs optional one-time administrator creation. Re-running it does not duplicate RC1, permissions, role grants, or administrator accounts.

## Start

```powershell
python -m uvicorn platform_db.api:app --host 127.0.0.1 --port 8016
```

Open `/login`, then change the bootstrap password at `/platform-account`. User management is at `/platform-admin/users`. Existing `/quota-building` routes remain on their current backend and are not changed by this service.

## Compose

```powershell
docker compose --env-file .env.platform-dev -f docker-compose.platform-dev.yml up --build -d
```

The container runs Alembic, idempotent RC1/security bootstrap, then Uvicorn. Source and frozen runs remain read-only, SQLite is not mounted as the database, and the volume is development-only.

## Verification

```powershell
python -m alembic -c platform_db/alembic.ini current
python -m alembic -c platform_db/alembic.ini check
python -m pytest platform_db/tests -q
```

Expected head is `0002_authentication_session_rbac`. Expected full suite is 56 passed. Authentication tests use isolated rolled-back transactions and must leave RC1 counts and protected Hash manifests unchanged.

## Downgrade

Downgrade removes Session, login attempt, password history, permission grant, and security audit data. It is not an ordinary rollback path. Export required audit evidence, revoke active sessions, obtain explicit authorization, and verify retention obligations before executing a downgrade. Never delete or recreate the RC1 database to conceal migration errors.
