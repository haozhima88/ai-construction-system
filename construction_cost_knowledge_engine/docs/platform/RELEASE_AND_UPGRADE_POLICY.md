# Release and Upgrade Policy

## Release Manifest

Every deployable platform state is identified by an immutable manifest with at least:

| Field | Meaning |
|---|---|
| `application_version` | Web/API/worker release version |
| `database_schema_version` | latest compatible applied migration |
| `reference_release_id` | immutable Reference payload |
| `mapping_release_id` | immutable candidate Mapping payload |
| `enterprise_price_release_id` | immutable approved price release or explicit `not_created` |
| `enterprise_quota_release_id` | immutable quota release or explicit `not_created` |
| `source_hash_manifest` | digest of authority/proxy file hash inventory |
| `docker_image_tag` | human tag plus immutable digest in manifest details |
| `generated_at` | timezone-aware generation timestamp |

The manifest also records its own SHA256, artifact hashes, parser/import versions, API compatibility, migration hashes, actor, validation results, predecessor, and rollback target.

## Release Types

- Reference Release: immutable source-derived catalog; requires source roles, hashes, counts, integrity, and evidence policy.
- Mapping Release: immutable Candidate set pinned to one Reference Release. It contains no `approved` state.
- Enterprise Price Release: immutable set of approved price versions with effective-date and overlap checks.
- Enterprise Quota Release: immutable published quota versions plus captured price snapshot.
- Application Release: immutable container image digest and API/schema compatibility.
- Database Schema Release: ordered, hashed PostgreSQL migrations.
- Composite Release: exact compatible tuple of all component releases.

The private `release_type_matrix.csv` defines gates and rollback units.

## Build and Promotion

1. Assemble artifacts in staging and calculate hashes.
2. Verify Source roles and Source Hash Manifest.
3. Import into release-scoped staging tables; reject count/key/provenance/state violations.
4. Apply schema migrations in an isolated copy and run migration tests.
5. Validate component compatibility and produce a candidate Composite Manifest.
6. Run API, permission, lifecycle, and representative UI smoke checks.
7. Record required business approvals for Enterprise releases.
8. Sign/freeze the manifest and activate its pointer atomically.

Development, test, and production promotion reuse identical artifact hashes. Environment-specific secrets and host paths are not release artifacts.

## Data Import Rules

- Imports are idempotent by release ID plus artifact hash.
- A conflicting hash for an existing release ID is a blocking error.
- Released rows are inserted into release-scoped immutable partitions/tables; imports do not update prior releases.
- Draft Overlay data is neither bundled into nor overwritten by Reference/Mapping imports.
- Every import emits counts, rejects, provenance checks, and a system audit event.

## Schema Migration

- Use expand/migrate/contract. Application versions declare a compatible schema range.
- Preflight verifies backup, disk space, locks, migration ordering, and script hashes.
- Migrations are transactional where PostgreSQL permits; long data backfills are resumable jobs.
- A migration record is append-only. Editing an applied migration is forbidden.
- Contract/removal occurs only after all supported application versions stop using the old shape.

## Smoke Gate

Smoke covers health/readiness, login and role denial, pinned Reference and Mapping counts, Draft isolation, provenance lookup, price/quota workflow guards, manifest readback, export, and audit correlation. Enterprise publication smoke additionally verifies the price snapshot and immutable payload.

## Rollback

- Application/data rollback activates a new Composite Manifest referencing the last compatible immutable releases and image.
- Database rollback normally rolls forward with a repair migration. Restore is used when compatibility cannot be recovered safely.
- Rollback is audited, requires a known restore point, and retains failed artifacts for investigation.
- A published Enterprise Quota is never edited to simulate rollback.

## Current RC1

`BUILDING_A01_A03_REFERENCE_RC1`, `BUILDING_A01_A03_MAPPING_RC1`, and `WEB_REVIEW_RC1` are architecture freeze inputs. No Docker image, Enterprise Price Release, Enterprise Quota Release, or production PostgreSQL schema is created by this stage.

