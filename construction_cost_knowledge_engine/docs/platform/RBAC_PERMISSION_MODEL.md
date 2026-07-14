# RBAC Permission Model

## Catalog

The catalog contains 28 stable permission codes across Reference, Mapping, Mapping Draft/Review, Release, Enterprise Price, Enterprise Quota, identity, audit, and system groups. Permissions are global definitions; `app_role_permission` grants them per Tenant. Users receive roles through effective-dated `app_user_role_assignment` rows.

## Roles

| Role | Intent |
|---|---|
| viewer | Read Reference, Mapping, Draft/Review, Release, Enterprise Price, and Enterprise Quota |
| editor | Viewer plus Mapping Draft and Enterprise Price/Quota draft editing |
| reviewer | Viewer plus Mapping and Enterprise Price/Quota review |
| approver | Viewer plus Enterprise Price/Quota approve and publish |
| administrator | Domain reads plus user, role, audit, and system administration |

Administrator does not automatically receive Enterprise edit, review, approve, or publish permissions. This prevents an administrative account from silently bypassing business separation of duty.

## Enforcement

Frontend menus and buttons use `/api/v1/auth/me`, but they are only convenience controls. FastAPI `require_permission` and `require_role` dependencies are authoritative. Permission denial writes an append-only security event. A user with `must_change_password=true` may access account, password, Session, and logout APIs but cannot use protected platform or administration APIs.

Role grants are Tenant-scoped, effective-dated, overlap-protected, and audited. Public registration and client-supplied permission claims do not exist.

## Separation of Duty

`SeparationOfDutyPolicy` blocks quota creator/reviewer, editor/approver, reviewer/approver, and price submitter/approver identity overlap, including administrator accounts. Break-glass requires explicit enablement, a non-empty reason, actor/Tenant context, and a high-level `break_glass_used` audit event.
