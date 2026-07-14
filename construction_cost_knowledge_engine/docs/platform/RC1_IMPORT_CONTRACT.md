# RC1 Import Contract

## Inputs

- Reference Release: `BUILDING_A01_A03_REFERENCE_RC1`
- Mapping Release: `BUILDING_A01_A03_MAPPING_RC1`
- Web slice: `WEB_REVIEW_RC1` remains on its current backend.
- Normative manifest: architecture-lock `building_rc1_release_manifest.csv`.

The importer recomputes every file SHA, five aggregate Manifest hashes, and `472/3700/24981/1882` counts before opening an import transaction. A failure blocks the job before data mutation.

## Transaction and Idempotency

The idempotency key is `rc1:<manifest_file_sha256>` per tenant. First execution creates one `platform_import_job`, imports all targets in one transaction, writes one `platform_import_job_item` per source record with source key and canonical payload SHA, and completes the job. Re-execution returns the completed job and performs no target insert/update.

An existing Release ID with a different Manifest hash is a conflict, not an update path. Source CSV, Manifest, and SQLite are opened read-only and never normalized in place.

## RC1 Mapping

| Source | Target |
|---|---|
| source role registry and A01/A02/A03 document registry | `source_document` |
| A01/A02/A03 page registry plus GB authority backlog/sample | `source_page_evidence` |
| 472 GB bill rows | `reference_bill_item` |
| 3,700 GD quotas plus frozen fee snapshot fields | `reference_quota_item` |
| 24,981 GD components | `reference_quota_resource` |
| bill context/work/quantity/conversion/note rows | `reference_rule_block` |
| work and quantity scope rows | `reference_scope_link` |
| 1,882 Mapping Candidate edges | `mapping_candidate_edge` |
| 87 Release Manifest rows | `release_artifact` |

All Reference and Mapping statuses remain `pending`; their enum cannot represent `approved`.

## Draft/Audit Overlay

SQLite is opened with `mode=ro`. Every Draft must map source bill, optional target bill, quota UID, and Mapping Edge. Every Audit must map its Draft/bill/quota keys and retain unique chronological order. Only a 100% result permits creation of one tenant `mapping_workspace` and import into development PostgreSQL. Otherwise all rows remain in SQLite and the result is `manual_migration_required`.

The overlay import has its own idempotency key based on the SQLite file SHA and does not become part of immutable Mapping Candidate data.

