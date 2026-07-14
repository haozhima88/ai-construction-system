# Implementation Roadmap

## Guiding Order

Build governance and immutable import paths before enterprise workflow automation. Each stage produces a reviewable migration/release artifact and may stop without changing production state.

## Stage P1: PostgreSQL Foundation

- Translate the 30-entity logical model into physical tables, association tables, enums/checks, indexes, RLS, immutable triggers, and append-only audit controls.
- Seed the five roles and test default deny/separation of duties.
- Implement migration registry and disposable-database migration tests.
- Deliverable: development-only schema and test fixtures, not production deployment.

Exit: schema contract, migrations, rollback/roll-forward notes, and automated integrity tests pass.

## Stage P2: Immutable RC1 Import

- Implement idempotent import of `BUILDING_A01_A03_REFERENCE_RC1` and `BUILDING_A01_A03_MAPPING_RC1` by release ID and hash.
- Reconcile 472 bill items, 3,700 quota items, 24,981 resource components, and 1,882 Mapping Candidate edges.
- Prove Reference/Mapping cannot contain `approved` and Draft Overlay cannot write upstream.

Exit: import report, provenance readback, count/hash equality, and repeat-import no-op pass.

## Stage P3: API V1 Read Plane and Identity

- Implement authentication, tenant context, role policy, `/reference`, `/mappings`, `/releases`, and audit correlation.
- Add compatibility headers, cursor pagination, problem details, health/readiness, and smoke tests.
- Keep current Web behavior unchanged until parity is demonstrated against RC1.

Exit: read API and authorization contract tests pass.

## Stage P4: Mapping Draft Migration

- Design an explicit migration for the current Draft/Audit overlay without mutating its source SQLite database.
- Implement `/mapping-drafts` and `/reviews` with optimistic locking and complete audit.
- Reconcile source and destination counts/hashes before cutover; keep rollback export.

Exit: overlay parity, audit continuity, and no Reference/Mapping write-back pass.

## Stage P5: Enterprise Price MVP

- Confirm business rules for tax, currency, unit conversion, region/project applicability, effective overlap, confidence, and approval separation.
- Implement resource identity, observation capture, version workflow, approval, and price release/snapshot creation.
- Do not enable automatic precedence calculation until explainability and exception rules are approved.

Exit: manual governed price release and immutable snapshot tests pass.

## Stage P6: Enterprise Quota MVP

- Implement quota aggregate, components/rules, Change Sets, six-state machine, review events, and next-version behavior.
- Implement publication gates using pinned Reference and Enterprise Price snapshot releases.
- Verify published immutability and release-pointer rollback.

Exit: end-to-end draft-to-published test with separation of duties passes; no formal production quota is created during development validation.

## Stage P7: NAS Release Candidate

- Produce Compose, secret templates, pinned images, reverse proxy, backup job, observability, restore drill, and upgrade/rollback runbook.
- Build a staging NAS Composite Release and execute disaster-recovery and smoke tests.

Exit: signed manifest, successful restore drill, rollback evidence, and operational acceptance.

## Stage P8: Family Expansion

Approve and implement adapters one family at a time: A04, then C + GB/T 50856, D + GB/T 50857, and E + GB/T 50858. Each starts with a separate source/governance lock and does not alter Building RC1.

## Recommended Next Stage

`PLATFORM-POSTGRESQL-LOGICAL-MODEL-TO-MIGRATION-1`: implement P1 in a disposable development database with migrations and tests only. Manual business confirmation for Enterprise Price tax/effective-date policy and Enterprise Quota separation-of-duties exceptions can proceed in parallel, but does not block the technical schema foundation.
