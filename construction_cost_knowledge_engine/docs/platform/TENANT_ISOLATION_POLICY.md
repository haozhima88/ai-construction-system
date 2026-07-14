# Tenant Isolation Policy

## Source of Tenant

Tenant identity comes exclusively from the authenticated `app_session`. The API does not trust `tenant_id` from query strings, JSON bodies, form fields, or custom browser headers. `require_tenant_scope` exposes the authenticated Tenant to route and service code.

## Database Controls

All authentication entities containing Tenant data have non-null `tenant_id` foreign keys. Composite foreign keys bind Sessions, login attempts, password history, security events, role grants, and role assignments to an `app_user` in the same Tenant. Cross-Tenant user references are rejected by PostgreSQL.

## Repository Controls

`TenantAuthRepository` requires a Tenant UUID at construction and automatically includes it in every user, Session, and role-assignment query. Admin routes derive this UUID from `AuthContext`; request payloads cannot override it.

Reference and immutable Mapping Candidate releases are shared platform reference data rather than Tenant-owned rows. Access to them is still authenticated and permission-controlled.

## Administrative Crossing

This stage is single-Tenant at runtime. Administrator remains Tenant-scoped. A future explicit cross-Tenant administration context must require a dedicated permission, select a target Tenant outside ordinary request payloads, and emit `tenant_scope_rejected` or audited cross-Tenant actions. No implicit administrator bypass exists.
