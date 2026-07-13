# Enterprise Quota Domain

## Ownership

An Enterprise Quota is a tenant-owned production object derived from a pinned Reference quota or created with an explicit enterprise rationale. It does not alter Reference or Mapping and is not a renamed Mapping Draft.

## Aggregate

- `enterprise_quota`: stable identity and enterprise code.
- `enterprise_quota_version`: lifecycle root, reference release pin, predecessor, rationale, and state.
- `enterprise_quota_component_version`: labor/material/machine or enterprise resource lines owned by one quota version.
- `enterprise_quota_rule_version`: work content, quantity, conversion, and enterprise applicability rules.
- `enterprise_quota_change_set`: structured changes and reasons between versions.
- `enterprise_quota_review_event`: append-only workflow evidence.
- `enterprise_quota_release`: immutable set of published versions plus a price snapshot.

## Derivation Rules

1. Creation pins `reference_release_id` and the originating `reference_quota_item_id` when one exists.
2. Imported Reference fields remain traceable; enterprise overrides are explicit, field-level, and reasoned.
3. Mapping Candidate or Draft may be supporting context but cannot be silently copied as authoritative enterprise content.
4. Components reference `enterprise_resource`; links to Reference resource candidates are retained as provenance.
5. Enterprise rules preserve raw source text and distinguish enterprise additions from source-derived rules.

## Mutability

Only `draft` aggregate content is editable. Submission seals the Change Set and freezes the submitted snapshot. A returned version resumes `draft` with a new Change Set revision. `reviewed`, `approved`, `published`, and `superseded` payloads are immutable.

## Change Set

A Change Set records business reason, affected paths, before/after values, reference impact, component/rule deltas, creator, timestamps, and review disposition. Submission requires a sealed Change Set. A new version references its predecessor and begins with a generated baseline Change Set.

## Publication

Publication requires:

- state `approved` with separation-of-duties evidence;
- pinned Reference Release;
- immutable Enterprise Price snapshot release;
- complete component and rule validation;
- release manifest hashes and database schema compatibility;
- successful migration/import dry run and smoke checks.

Publishing never updates an existing version. The release stores membership and snapshot references, then marks the version `published` through an audited transition.

## Next Version and Rollback

Editing a published quota clones it into the next monotonic `draft` version, links the predecessor, and opens a Change Set. Rollback creates a new release manifest that activates a previously published immutable payload; it does not change or delete the failed release or mutate a superseded version.

## Current Stage Boundary

This document is a production-domain contract only. No enterprise quota identity, version, component, approval, or release is created in this stage.
