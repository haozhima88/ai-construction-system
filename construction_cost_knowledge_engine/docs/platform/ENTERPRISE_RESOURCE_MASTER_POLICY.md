# Enterprise Resource Master Policy

## Ownership and separation

`enterprise_resource` is tenant-owned master data. `reference_quota_resource` is immutable source evidence. Copying an A1.1 resource into the Enterprise layer creates a new identity; it never updates or annotates the Reference row.

The minimum master record contains Enterprise Resource ID, tenant, resource code, name, normalized name, specification, unit, category, lifecycle status, creator/time, and row version. The natural candidate key is normalized code/name/specification/unit/category, but the UUID remains the durable identity.

## Reference links

`enterprise_resource_reference_link` records an independent relationship for every source component row. It stores both IDs, the source code, matching method and score, field-level name/specification/unit/category results, review status, and risk reason.

The A1.1 initial fork is allowed to use exact code or exact name/specification/unit because the Enterprise candidate is copied directly from the frozen Reference row. This is a provenance link, not semantic approval. Every link initially remains `pending`. Semantic candidates require manual review; they cannot be automatically approved.

## Lifecycle

Enterprise Resources begin as `draft`. Activation requires confirmed ownership, normalized identity, unit/category review, and resolution of duplicate or conflicting links. Archived/retired resources remain addressable by historical Enterprise Quota versions and snapshots.

Resource replacement inside a Draft changes only the Enterprise Quota Component version and creates a Change Set. It does not alter the resource used by older versions.

## Tenant and concurrency controls

All master and link queries are tenant-scoped. Writes require Session, CSRF, permission, `row_version`, an idempotency key, and Audit. Cross-tenant IDs are rejected. Optimistic concurrency conflicts return HTTP 409 rather than overwriting a newer edit.
