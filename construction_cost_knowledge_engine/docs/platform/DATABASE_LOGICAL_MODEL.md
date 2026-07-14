# Database Logical Model

Target: PostgreSQL. This is a logical contract, not a migration or production schema.

## Conventions

- UUID primary keys are generated server-side; governed release IDs use stable text identifiers.
- Timestamps are `timestamptz` in UTC. Money is `numeric(20,6)` with an explicit currency and tax mode.
- Mutable tables carry `revision_no`, `updated_at`, and optimistic locking. Immutable tables reject `UPDATE` and `DELETE` after their freeze gate.
- Provenance columns use explicit foreign keys plus structured `provenance_json`; hashes remain scalar searchable columns.
- Tenant isolation applies to Enterprise and user data. Reference and published Mapping releases are shared read-only catalogs.
- Hard deletes are forbidden for published, approved, evidence, release, migration, and audit records.

## Entity Inventory

| Domain | Entities |
|---|---|
| Reference | `source_document`, `source_page_evidence`, `standard_family`, `reference_release`, `reference_bill_item`, `reference_quota_item`, `reference_quota_resource`, `reference_rule_block`, `reference_scope_link` |
| Mapping | `mapping_release`, `mapping_candidate_edge`, `mapping_draft_edge`, `mapping_review_state`, `mapping_audit_event` |
| Enterprise Price | `enterprise_resource`, `enterprise_price_observation`, `enterprise_price_version`, `enterprise_price_approval` |
| Enterprise Quota | `enterprise_quota`, `enterprise_quota_version`, `enterprise_quota_component_version`, `enterprise_quota_rule_version`, `enterprise_quota_change_set`, `enterprise_quota_review_event`, `enterprise_quota_release` |
| Platform | `app_user`, `app_role`, `release_manifest`, `schema_migration`, `system_audit_event` |

Total: 30 entities. The private `platform_entity_dictionary.csv` is the normative row-level dictionary for PK, FK, unique constraint, mutability, lifecycle, provenance, version relation, audit, and delete policy.

## Key Relationships

```text
standard_family 1--N source_document 1--N source_page_evidence
standard_family 1--N reference_release
reference_release 1--N reference_bill_item
reference_release 1--N reference_quota_item 1--N reference_quota_resource
reference_release 1--N reference_rule_block 1--N reference_scope_link

reference_release 1--N mapping_release 1--N mapping_candidate_edge
mapping_candidate_edge 1--N mapping_draft_edge
mapping_candidate_edge/mapping_draft_edge 1--N mapping_review_state
mapping_draft_edge 1--N mapping_audit_event

enterprise_resource 1--N enterprise_price_observation
enterprise_resource 1--N enterprise_price_version 1--N enterprise_price_approval

enterprise_quota 1--N enterprise_quota_version
enterprise_quota_version 1--N component/rule/change_set/review_event
enterprise_quota_release N--N published enterprise_quota_version
enterprise_quota_release N--1 immutable price snapshot release
```

The two N:N release memberships should be implemented with association tables during physical design; they are not additional business entities in this 30-entity logical inventory.

## State and Integrity Rules

- Reference release rows are immutable after `published`; their children inherit immutability.
- Mapping Candidate rows are immutable and remain non-authoritative candidates. Draft rows are overlays keyed to a candidate and revision.
- Enterprise Price approval applies only to a specific immutable price version.
- Enterprise Quota components and rules are editable only while their parent is `draft`; submission freezes the submitted snapshot.
- `published` Enterprise Quota versions require a release membership, approved review evidence, and price snapshot release ID.
- Partial unique indexes enforce one active enterprise identity and one active Draft revision without erasing history.
- Database constraints prevent `approved` in Reference or Mapping status columns.

## Audit and Delete Policy

Business transitions and mutations emit append-only domain audit events and a correlation-linked `system_audit_event`. Soft retirement is allowed only for mutable identities. Evidence, published versions, manifests, approvals, and audit events are retained according to governance policy and are never application-deleted.

## Physical Design Follow-up

The next stage converts this model into PostgreSQL migrations, enums/check constraints, association tables, row-level security, immutable-row triggers, indexes, seed roles, and migration tests. No production database is created in this stage.

