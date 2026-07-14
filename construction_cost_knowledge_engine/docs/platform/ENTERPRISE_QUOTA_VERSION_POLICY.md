# Enterprise Quota Version Policy

## Derivation contract

Each Enterprise Quota is a tenant-owned aggregate derived from a pinned Reference quota. Every version records the Reference Release, quota UID/code, canonical source-version hash, Enterprise version number, state, creator/time, change reason, calculation-rule version, and row version.

The source hash covers the frozen Reference quota payload and its ordered resource component payloads. It proves derivation; it does not make the Enterprise copy part of Reference.

## States

The governed states are `draft`, `submitted`, `reviewed`, `approved`, `published`, and `superseded`.

- Editors create and edit Drafts and submit them.
- Reviewers may review or return submitted work, but cannot review a version they created.
- Approvers may approve only a reviewed, price-complete version backed by a confirmed price source and with separation of duties.
- The A1.1 pilot blocks formal publication even for a user holding the publish permission.

No operation automatically produces reviewed, approved, or published data. Approved/published counts must remain zero for this stage.

## Version and restore behavior

Saving a Draft updates that Draft with optimistic concurrency and creates a Change Set. “Save as new version” clones the selected version, its components, and rules into a new Draft with a predecessor link. Restore also creates a new Draft; it never overwrites the historical version.

Published and superseded versions cannot be updated or deleted. Child components and rules are editable only while their parent is Draft.

## Price snapshots

Drafts may create a `preview` snapshot. A publication workflow, when enabled in a later stage, must create a `frozen` snapshot before release. The snapshot freezes price value, unit, tax basis, region, effective dates, price/source IDs, resource-reference mapping, and calculation-rule version.

Snapshot headers and lines are append-only. Null prices remain null. A later price change cannot alter the cost of a historical Enterprise Quota release.
