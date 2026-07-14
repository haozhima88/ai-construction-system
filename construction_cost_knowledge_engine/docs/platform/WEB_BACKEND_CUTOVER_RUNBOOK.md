# Web Backend Cutover Runbook

## Preconditions

1. PostgreSQL RC1 state is `postgresql_rc1_foundation_ready_for_web_backend_migration`.
2. Authentication state is accepted by the stage contract.
3. Alembic is at `0003_postgres_review_cutover` and `alembic check` reports no operations.
4. Entity counts are 472 bills, 3700 quotas, 24981 resources, and 1882 candidate edges.
5. SQLite/PostgreSQL Draft and Audit parity is 6/7 with exact legacy keys.
6. Source, parsed, consolidated, Mapping, Web baseline, and SQLite hashes are unchanged.
7. The 20 required cutover gates in `postgres_web_cutover_gate.csv` pass.

## Apply

Set:

```text
QUOTA_BUILDING_BACKEND=postgres
QUOTA_BUILDING_SQLITE_FALLBACK_ENABLED=true
```

Restart the API, confirm `/api/v1/platform/health`, then validate `/quota-building-pg` before opening `/quota-building`. Verify anonymous redirect, viewer/editor/reviewer behavior, CSRF, tenant isolation, idempotency, row-version conflicts, PDF preview, resource amounts, cost summary, and P95 thresholds.

## Acceptance

- Reads P95 below 300 ms.
- Writes P95 below 500 ms.
- PostgreSQL Draft and Audit are atomic.
- No SQLite writes and no dual writes.
- `approved_count=0`.
- `/quota-building-sqlite` remains available and visibly read-only.

Production NAS deployment still requires HTTPS and `SESSION_COOKIE_SECURE=true`.

