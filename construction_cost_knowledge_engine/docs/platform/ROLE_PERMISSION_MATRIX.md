# Role Permission Matrix

## Roles

- `viewer`: read released Reference, Mapping, enterprise releases, and public manifests.
- `reviewer`: viewer access plus review queues and review/audit evidence.
- `editor`: viewer access plus Mapping Draft, price observation/version Draft, and Enterprise Quota Draft operations.
- `approver`: viewer access plus Enterprise Price and Enterprise Quota approval decisions.
- `administrator`: deployment, release, migration, backup/restore, user, and policy administration; business-state guards still apply.

## Core Matrix

| Capability | viewer | reviewer | editor | approver | administrator |
|---|---:|---:|---:|---:|---:|
| Read published Reference/Mapping | yes | yes | yes | yes | yes |
| Edit Reference or Mapping Candidate | no | no | no | no | no |
| Create/edit Mapping Draft overlay | no | no | yes | no | yes |
| Review Mapping Draft | no | yes | no | no | yes |
| Create price observation/version Draft | no | no | yes | no | yes |
| Review Enterprise Price | no | yes | no | no | yes |
| Approve Enterprise Price | no | no | no | yes | guarded |
| Create/edit/submit Enterprise Quota Draft | no | no | yes | no | guarded |
| Review Enterprise Quota | no | yes | no | no | guarded |
| Approve Enterprise Quota | no | no | no | yes | guarded |
| Publish or rollback a release | no | no | no | no | yes |
| Overwrite published payload | no | no | no | no | no |
| Run schema migration or restore | no | no | no | no | yes |

The complete action-level matrix and guards are in the private `role_permission_matrix.csv`.

## Authorization Rules

- Default deny. API authorization is server-side and tenant-scoped.
- Role assignment and policy changes are audited and versioned.
- Object-level grants may narrow access but never bypass immutable state or separation-of-duties rules.
- `approved` actions exist only in Enterprise Price and Enterprise Quota.
- Administrator is an operational role, not an automatic substitute for reviewer or approver.
- Hard delete has no interactive permission; retention administration is a separate controlled process.

## Authentication and Sessions

The physical implementation should integrate a NAS-compatible OIDC provider or trusted reverse-proxy identity, use short-lived sessions, CSRF protection for browser commands, secure cookies, rate limits, and correlation IDs. Local bootstrap credentials are permitted only for installation and must be rotated.

