# API V1 Contract

Base path: `/api/v1`. This stage defines logical resources and behavior only; no endpoint is implemented.

## Cross-Cutting Contract

- JSON uses UTF-8 and stable IDs. Timestamps are ISO 8601 UTC.
- List endpoints support cursor pagination, deterministic sort, field filters, and release ID pins.
- Read responses include `provenance`, `version`, `release_id`, and `links` where applicable.
- Mutating commands require authentication, authorization, `Idempotency-Key`, `If-Match`/revision, reason, and correlation ID.
- Errors follow `application/problem+json` with `type`, `title`, `status`, `code`, `detail`, `correlation_id`, and field violations.
- Reference and published release resources reject mutation with `405` or `409`.

## Resource Groups

### `/reference`

Read-only families, releases, source documents/page evidence, bill items, quota items, resources, rules, and scope links. Every query may pin `reference_release_id`; unpinned reads resolve the active release and disclose it.

### `/mappings`

Read-only Mapping Releases, candidate edges, bill matrices, routing, risk, and evidence status. The API never exposes a Mapping Candidate as `approved`.

### `/mapping-drafts`

Create/update/archive/restore Draft overlays and read their revision history. Commands never update `/reference` or `/mappings`; publish of a future Mapping Release is an administrator release operation, not Draft approval.

### `/prices`

Enterprise resources, observations, price versions, approvals, effective ranges, and immutable price releases. A decision response identifies precedence class and evidence but V1 does not promise an automatic calculation endpoint.

### `/enterprise-quotas`

Quota identities, versions, components, rules, Change Sets, validation, state commands, and immutable releases. Published content is read-only; edits use a `create-next-version` command.

### `/reviews`

Role-scoped review queues, review detail, comments, decisions, and audit-readable transition history. Decision commands call domain state machines and do not patch state directly.

### `/releases`

Read manifests, component release compatibility, validation/smoke results, and active release pointers. Assemble, activate, supersede, and rollback commands are administrator-only and fully audited.

### `/admin`

Users, role assignments, policy versions, migration status, health metadata, backup/restore job metadata, and system audit queries. Secrets and raw database operations are never exposed.

## Representative Routes

| Method | Route | Semantics |
|---|---|---|
| GET | `/reference/releases/{id}/bill-items` | immutable released bills |
| GET | `/mappings/releases/{id}/edges` | immutable candidate edges |
| POST | `/mapping-drafts` | create overlay revision |
| POST | `/prices/versions/{id}/submit` | workflow command |
| POST | `/prices/versions/{id}/approve` | approver command |
| POST | `/enterprise-quotas/{id}/versions` | create initial/next Draft version |
| POST | `/enterprise-quotas/versions/{id}/transitions` | guarded state command |
| GET | `/reviews/queue` | current actor queue |
| POST | `/releases/manifests/{id}/activate` | activate validated composite release |
| GET | `/admin/migrations` | migration history |

## Compatibility

V1 permits additive response fields and new optional filters. Removing/renaming fields, changing state semantics, or broadening mutation rights requires a new major API version. Each response advertises API version and compatible database schema range.
