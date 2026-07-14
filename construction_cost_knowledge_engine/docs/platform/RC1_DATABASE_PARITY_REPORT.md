# RC1 Database Parity Report

Validated on PostgreSQL 16.14 with Alembic head `0001_platform_core_schema`.

## Count Parity

| Entity | Source | PostgreSQL | Mismatch |
|---|---:|---:|---:|
| Bill | 472 | 472 | 0 |
| Quota | 3,700 | 3,700 | 0 |
| Resource | 24,981 | 24,981 | 0 |
| Mapping Edge | 1,882 | 1,882 | 0 |
| Source Document | 5 | 5 | 0 |
| Page/Evidence | 2,135 | 2,135 | 0 |
| Rule Block | 1,842 | 1,842 | 0 |
| Scope Link | 1,295 | 1,295 | 0 |
| Draft | 6 | 6 | 0 |
| Audit | 7 | 7 | 0 |

## Field Parity

Full-key comparisons reported zero mismatch for:

- bill code, name, unit, project features, quantity rule, work content, heading/table locator, and status;
- quota code, name, unit, PDF page, labor/material/machine/management/total fees, and status;
- resource category/code/name/specification/unit/consumption/unit price/amount/PDF page/status;
- Mapping role, routing class, risk, evidence status, and review status.

`approved_count=0`. The generated `rc1_postgres_parity_check.csv` is the normative check-level evidence.

## Import and Overlay

First RC1 import created 36,399 item-level lineage records. Repeating the same Manifest reused the same import job and changed no target count. Draft/Audit mapped 100%, created one Workspace, imported 6/7 rows, and repeated idempotently. Existing SQLite remained byte-identical.

## API and Performance

All required read-only API routes passed smoke checks for health, counts, detail, pagination, sorting, search, Release filter, source-family filter, resources, rules, mappings, and releases. Five local review queries met the 500 ms P95 gate; exact values and plan summaries are in `postgres_query_performance.csv`.

