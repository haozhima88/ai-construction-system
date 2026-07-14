# Enterprise Quota Editing Policy

## Draft operations

The following operations are allowed only on a Draft:

1. change the Enterprise Quota name;
2. change the unit with an explicit reason;
3. change resource consumption;
4. replace a resource;
5. add a resource;
6. remove an Enterprise component;
7. change work content;
8. add an Enterprise note;
9. add an Enterprise conversion rule; and
10. restore the Reference-derived value through a new Change Set or new Draft version.

Selecting a price requires a governed Enterprise Price version for the same tenant and resource. Rejected or superseded prices are invalid. Missing price remains null, so the Enterprise component amount and complete Enterprise base price also remain null.

## Change Set

Every mutation writes `before_value`, `after_value`, `change_type`, `change_reason`, actor, timestamp, request ID, and idempotency key. The Change Set is stored with the Enterprise Quota and linked to the current version. A repeated idempotency key returns the existing result.

The same request also creates a system Audit event. API writes require Session, CSRF, Tenant scope, permission, row version, and idempotency key. A stale row version returns HTTP 409.

## Save and workflow commands

- **Save Draft**: edit the current Draft and record a Change Set.
- **Save as new version**: clone components/rules, apply changes, and create a new Draft.
- **Submit review**: `draft → submitted`.
- **Review**: `submitted → reviewed`, with creator/reviewer separation.
- **Return for changes**: `submitted|reviewed → draft` with a review event.
- **Compare versions**: field and line-level read-only diff.
- **Restore**: clone the selected version into a new Draft.

Approval requires reviewed state, complete Enterprise resource prices, confirmed price authority, and separation of duties. Formal publication is disabled during this pilot. Direct update/delete of published versions or any historical price snapshot is prohibited by database triggers.
