# Database Development Runbook

## Configuration

Copy values from `.env.example` into an untracked local environment file and replace the development password. Never commit a real password. Required variables are `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `PLATFORM_TENANT_CODE`, and `RC1_MANIFEST_PATH`.

## Docker Compose

From `construction_cost_knowledge_engine`:

```powershell
docker compose --env-file .env.platform-dev -f docker-compose.platform-dev.yml up --build -d
docker compose --env-file .env.platform-dev -f docker-compose.platform-dev.yml ps
```

The Compose file pins `postgres:16.14`, uses a dedicated named development volume, mounts Source and frozen runs read-only, does not mount SQLite as a database, and exposes the independent API at `http://127.0.0.1:8016`. It is not a NAS production topology.

## Portable Windows PG16 Validation

When Docker CLI is unavailable, the private development bundle may run without installing a service:

```powershell
data\private\platform_dev\postgresql16\pgsql\bin\pg_ctl.exe `
  -D data\private\platform_dev\pgdata16 `
  -l data\private\platform_dev\postgresql16.log `
  -o '"-p 55432 -h 127.0.0.1"' -w start
```

This bundle and database directory are private generated tools, not repository artifacts.

## Migration

```powershell
$env:PYTHONPATH='.'
$env:DATABASE_URL='postgresql+psycopg://platform_dev@127.0.0.1:55432/construction_platform_rc1_dev'
data\private\platform_dev\.venv\Scripts\python.exe -m alembic -c platform_db\alembic.ini upgrade head
data\private\platform_dev\.venv\Scripts\python.exe -m alembic -c platform_db\alembic.ini current
data\private\platform_dev\.venv\Scripts\python.exe -m alembic -c platform_db\alembic.ini check
```

Never use application `create_all()` or delete a database to conceal a failed Migration. Create a separate empty validation database, retain failure evidence, fix the revision before release, and prove `current=head` plus no drift.

## Tests and API

```powershell
data\private\platform_dev\.venv\Scripts\python.exe -m pytest platform_db\tests -q
data\private\platform_dev\.venv\Scripts\python.exe -m uvicorn platform_db.api:app --host 127.0.0.1 --port 8016
```

Validation entry: `http://127.0.0.1:8016/platform-rc1-validation`. The existing `/quota-building` backend is not switched.

## Stop

Docker: `docker compose --env-file .env.platform-dev -f docker-compose.platform-dev.yml down`.  
Portable PG16: `pg_ctl -D data\private\platform_dev\pgdata16 -w stop`.
