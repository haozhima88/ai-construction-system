# PostgreSQL Web Backend Architecture

## Runtime Boundary

The quota-building workbench reads immutable RC1 reference and Mapping Candidate entities from PostgreSQL and applies tenant-scoped review overlays. `QUOTA_BUILDING_BACKEND=postgres` serves the PostgreSQL workbench at both `/quota-building-pg` and `/quota-building`. `QUOTA_BUILDING_SQLITE_FALLBACK_ENABLED=true` retains `/quota-building-sqlite` and `/quota-building-legacy` as read-only rollback views.

There is no dual write. PostgreSQL is the only write backend. The SQLite file is opened only by GET handlers and is never synchronized back from PostgreSQL.

## Components

- `BillReviewRepository`: bill tree, search, counts, and review priority.
- `MappingReviewRepository`: immutable candidate rows plus tenant Draft Overlay.
- `QuotaDetailRepository`: quota, resources, structured rules, evidence, and source documents.
- `MappingDraftRepository`: Copy, Move, Exclude, Restore with row version and idempotency enforcement.
- `MappingReviewWriteRepository`: non-approved review-state transitions.
- `MappingAuditRepository`: tenant-scoped append-only operational history.
- `QuotaCostSummaryService`: Decimal resource amounts and cost reconciliation.

All write requests require a valid server Session, permission, CSRF token, `row_version`, and `idempotency_key`. Draft/Review and Mapping Audit are committed in one database transaction. Candidate Mapping, reference entities, source files, and SQLite are immutable.

## Routes

- PostgreSQL API: `/api/v1/review/*`
- SQLite read-only API: `/api/v1/review-sqlite/*`
- Parallel validation page: `/quota-building-pg`
- Cutover page: `/quota-building`
- Read-only rollback: `/quota-building-sqlite`

Protected PostgreSQL pages redirect anonymous users to `/login`. PDF responses are same-origin, inline, and protected by the same Session and reference-read permission.

## Preview Layout

The workbench is a dense three-pane operational surface with stable split dimensions. A `ResizeObserver` measures the actual PDF region after navigation, split changes, detail collapse, toolbar changes, and viewport resize. Preview preferences persist only layout and view mode in localStorage; authentication and CSRF secrets are never persisted there.

