# PostgreSQL Physical Model

Stage: `POSTGRESQL-RC1-PHYSICAL-SCHEMA-AND-IMPORT-FOUNDATION-1`  
Target and validated database: PostgreSQL 16.14.

## Module Boundary

The independent `platform_db/` module owns SQLAlchemy 2.x models, Alembic migrations, RC1 importers, repositories, read-only API, services, and PostgreSQL integration tests. The existing `/quota-building` application imports none of this module and retains its current backend.

Runtime table creation is forbidden. The schema is created only through Alembic revision `0001_platform_core_schema`.

## Entity Inventory

The 30 architecture entities are implemented together with eight physical supplements:

| Supplemental entity | Purpose |
|---|---|
| `app_tenant` | tenant root and lifecycle |
| `app_user_role_assignment` | tenant-scoped effective role grants |
| `mapping_workspace` | tenant overlay boundary for Mapping Draft |
| `release_artifact` | file-level Release Manifest evidence |
| `enterprise_price_snapshot` | immutable quota publication price snapshot header |
| `enterprise_price_snapshot_line` | exact selected resource price versions |
| `platform_import_job` | idempotent import lifecycle and totals |
| `platform_import_job_item` | source key, target ID, status, and payload SHA per imported record |

Total physical business entities: 38. `alembic_version` is migration infrastructure and is not counted as a business entity.

## Physical Conventions

- Primary business keys use PostgreSQL UUID; governed Release IDs use stable text identifiers.
- Import UUIDs are deterministic UUIDv5 values derived from entity and source key.
- Tenant-owned entities have a non-null FK to `app_tenant`.
- Mutable governed rows share `created_at`, `created_by`, `updated_at`, `updated_by`, `row_version`, and `correlation_id`.
- `row_version` is positive and increments in a database trigger; repositories use expected-version predicates.
- Source payloads and imported entities retain a SHA256; Release artifacts require a 64-character SHA256.
- Monetary and quantity values use fixed-precision `numeric`, never floating-point storage.
- Raw rules, names, evidence, and explanations use `text` where source length is not safely bounded.

## Release Integrity

Mapping Candidate uses composite foreign keys to prove that Mapping Release, bill, and quota all reference the same Reference Release. Mapping Draft uses composite foreign keys to prove that Candidate and Workspace share one Mapping Release. Published Reference/Mapping and their imported child rows are trigger-protected from update/delete.

## Enterprise Empty Structures

Enterprise Price and Enterprise Quota tables are present for forward-compatible migration design. This stage inserts zero Enterprise Resource, Price, Snapshot, Quota, Component, Rule, Approval, or Release records.

The generated `physical_entity_dictionary.csv` is the normative table-level inventory of keys, constraints, indexes, tenant scope, audit fields, mutability, and delete policy.

