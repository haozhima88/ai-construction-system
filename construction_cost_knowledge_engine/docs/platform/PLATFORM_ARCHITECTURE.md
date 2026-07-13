# Platform Architecture

Status: architecture lock for `PLATFORM-FOUNDATION-AND-ENTERPRISE-QUOTA-ARCHITECTURE-LOCK-1`.

## Frozen Inputs

- `BUILDING_A01_A03_REFERENCE_RC1`: immutable GB/T 50854 bill candidates and GD2018 A01/A02/A03 quota reference.
- `BUILDING_A01_A03_MAPPING_RC1`: immutable candidate edges and routing metadata.
- `WEB_REVIEW_RC1`: reviewed Web source slice. Its Draft/Audit database is an external mutable overlay, not release payload.

The exact files, hashes, counts, parser provenance, and Web version are recorded in `BUILDING_RC1_RELEASE_MANIFEST.md` and the private run manifest.

## Four Domains

| Domain | Owns | May mutate | Must not do |
|---|---|---|---|
| Reference | source evidence, released bill/quota/resource/rule records | assemble a new release before publish | edit a published row; contain `approved` |
| Mapping | released candidate edges, Draft overlay, review state, audit | Draft overlay and workflow state only | write back to Reference; call a candidate `approved` |
| Enterprise Price | enterprise resources, observations, price versions, approvals | draft versions and workflow | rewrite an approved/published price version |
| Enterprise Quota | enterprise quota identity, versions, components, rules, Change Sets, reviews, releases | `draft` version only | overwrite `published`; publish without a price snapshot |

`approved` is an Enterprise-domain workflow state only. Reference and Mapping use `pending`, `reviewed`, evidence, risk, and release validation vocabulary, never `approved`.

## Dependency Direction

```text
Authority Source -> Reference Release -> Mapping Release -> Mapping Draft Overlay
                              |
                              +-> Enterprise Quota Version
Enterprise observations -> Enterprise Price Release -> price snapshot in Quota Release
```

Dependencies are referenced by immutable release IDs. Downstream changes never alter upstream data. A new upstream release requires explicit compatibility validation and a new dependent release.

## Runtime Planes

- Evidence plane: read-only source files and source-page evidence.
- Data plane: PostgreSQL logical domains and immutable release manifests.
- Application plane: `/api/v1`, Web UI, optional asynchronous worker.
- Control plane: identity, role policy, migration registry, release activation, audit, backup, and restore.

## Invariants

1. Every governed record resolves to a source or enterprise creation event.
2. Every published payload resolves to an immutable `release_manifest` and artifact hashes.
3. Draft data is never silently promoted into a released Reference or Mapping artifact.
4. Enterprise Quota derives from a pinned Reference Release and publishes against a pinned price snapshot.
5. Published versions are append-only. Corrections create a higher version and a Change Set.
6. Rollback changes the active release pointer through an audited manifest; it does not rewrite old rows.
7. Source storage is mounted read-only in all application services.

## Current Scope

This lock defines architecture and contracts only. It does not create PostgreSQL, calculate enterprise prices, create enterprise quotas, parse A04/C/D/E, alter Mapping Draft/Audit, or modify current Web behavior.

