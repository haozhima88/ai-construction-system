# PostgreSQL Constraint Policy

## Enforcement Layers

| Rule | Database enforcement | Service enforcement |
|---|---|---|
| Reference Release immutable after publish | release trigger | importer never updates an existing Release ID |
| Mapping Release immutable after publish | release trigger | importer is insert/idempotency only |
| Reference children business read-only | parent-release trigger | no mutation repository/API exists |
| Mapping Candidate business read-only | parent-release trigger | no mutation repository/API exists |
| Published Enterprise Quota UPDATE/DELETE forbidden | state trigger | state machine creates next version |
| Reference/Mapping cannot be approved | enum excludes `approved` | API vocabulary excludes approval |
| Tenant isolation | non-null FK plus tenant indexes | tenant context is mandatory in repositories |
| Release artifact SHA required | not-null and length check | Manifest Hash Guard before import |
| Authority/proxy role semantics | `source_role` enum and authority-status check | role registry importer maps explicit values |
| Mapping edge same Reference Release | three composite FKs | source key maps are release-pinned |
| Mapping Draft belongs to Workspace | composite Workspace/Candidate FKs | migration creates one pinned Workspace |
| Reviewer/approver separation | quota/price triggers | command actor guards before transition |
| Active role periods do not overlap | range-overlap trigger | role assignment service preflight |
| Optimistic concurrency | positive and bump trigger | `WHERE row_version = expected` repository update |

## Immutability

Source documents and page evidence are append-only in the physical RC1 schema. Released artifacts marked immutable cannot be updated or deleted. Audit/import history is retained through restrictive foreign keys and has no delete API.

## Responsibilities

Database constraints protect invariants under every client. Service guards provide actor context, meaningful errors, idempotency, workflow authorization, and expected-version checks. A Service Guard may strengthen but cannot weaken a database rule.

## Delete Policy

Published/evidence/audit/approval/release rows use `RESTRICT` and immutable triggers. Mutable identities use lifecycle status rather than hard deletion. Development database disposal is an environment operation, never a business delete or migration substitute.

The generated `physical_constraint_matrix.csv` is the executable evidence index for these rules and their tests.

