# Web Authorization Policy

## Authentication

PostgreSQL review pages and APIs require an opaque server Session. The browser receives an HttpOnly Session cookie and an in-memory CSRF value from `/api/v1/auth/me`. Session tokens and CSRF values must not be stored in localStorage or sessionStorage.

State-changing requests require all of the following:

1. Active Session and active tenant.
2. Required RBAC permission.
3. Session-bound `X-CSRF-Token`.
4. Current `row_version`.
5. Unique `idempotency_key`.

## Role Policy

| Role | Reference/Mapping read | Draft Overlay | Review state | Approval/Publish | User/System admin |
|---|---:|---:|---:|---:|---:|
| viewer | yes | no | no | no | no |
| editor | yes | Copy/Move/Exclude/Restore | no | no | no |
| reviewer | yes | no | non-approved review states | no | no |
| approver | yes | no | no | enterprise approval only | no |
| administrator | yes | catalog permissions | catalog permissions | subject to SOD | yes |

Mapping review in this workbench never produces `approved`. The permitted states are `reviewed_candidate`, `needs_followup`, and `reviewed_mismatch`.

## Tenant And SOD

Every Draft, Review, Audit, Session, and user assignment is scoped by `tenant_id`. Repository scope is resolved from the authenticated Session, never from a client-supplied tenant identifier. Cross-tenant objects are not returned.

Administrator status does not bypass Separation of Duty. Enterprise creator/reviewer and submitter/approver conflicts remain blocked unless the documented, audited break-glass policy applies. This workbench does not expose break-glass operations.

