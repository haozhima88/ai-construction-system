# Web Backend Rollback Runbook

## Trigger

Rollback is appropriate for PostgreSQL unavailability, failed cutover gates, material field parity failure, tenant leakage, write/audit non-atomicity, or an unresolved security defect.

## Procedure

1. Stop PostgreSQL review writes at the application boundary.
2. Set `QUOTA_BUILDING_BACKEND=sqlite` while retaining `QUOTA_BUILDING_SQLITE_FALLBACK_ENABLED=true`.
3. Restart the API and verify `/quota-building` shows `SQLite read-only fallback`.
4. Confirm every `/api/v1/review-sqlite/*` mutation path returns 404/405.
5. Preserve PostgreSQL Draft, Review, and Audit rows for diagnosis. Do not delete or rewrite Audit.
6. Do not copy PostgreSQL changes into SQLite and do not resume dual writes.
7. Re-run the cutover gate before returning to PostgreSQL.

The rollback surface is intentionally read-only. It provides reference continuity, not collaborative editing.

