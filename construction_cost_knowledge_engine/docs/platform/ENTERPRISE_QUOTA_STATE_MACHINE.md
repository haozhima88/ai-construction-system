# Enterprise Quota State Machine

The normative machine has six persisted states: `draft`, `submitted`, `reviewed`, `approved`, `published`, and `superseded`.

## State Contract

| State | Payload mutability | Owner | Exit condition |
|---|---|---|---|
| `draft` | editable | editor | validation and sealed Change Set |
| `submitted` | frozen | reviewer queue | return with reason or complete review |
| `reviewed` | frozen | reviewer/approver queue | rework or approval |
| `approved` | frozen | approver/release queue | withdraw before publish or publish gate |
| `published` | immutable | platform | replacement version is published |
| `superseded` | immutable, retained | platform | terminal for payload state |

## Allowed Transitions

| From | To | Actor | Mandatory guard |
|---|---|---|---|
| none | `draft` | editor | create permission and Reference anchor/rationale |
| `draft` | `submitted` | editor | validation pass and sealed Change Set |
| `submitted` | `draft` | reviewer | return reason and audit event |
| `submitted` | `reviewed` | reviewer | checklist complete; reviewer is not submitter |
| `reviewed` | `submitted` | reviewer | rework reason |
| `reviewed` | `approved` | approver | evidence complete; separation of duties |
| `approved` | `reviewed` | approver | withdrawal reason; not published |
| `approved` | `published` | administrator | immutable manifest, price snapshot, migration/import/smoke gates |
| `published` | `superseded` | administrator | replacement version published |

The private `enterprise_quota_state_transition.csv` is normative for allowed and explicitly forbidden transitions.

## Separation of Duties

- Editors create, modify, and submit.
- Reviewers review or return and cannot review their own submission.
- Approvers approve or withdraw approval and cannot be the editor or reviewer for the same version.
- Administrators execute release activation after business approval; administrator privilege does not waive business separation.

In a small organization, one person may hold multiple roles globally, but the same quota-version workflow must still enforce actor separation. Emergency exceptions require a separate two-person break-glass audit policy in a future business-confirmation stage.

## Backtrack, Next Version, and Rollback

- Before publication, return transitions preserve the same version and open or revise a Change Set.
- After publication, any content change creates a higher `draft` version linked by `predecessor_id`.
- `published -> draft`, in-place `published -> published`, and payload mutation are forbidden.
- Rollback creates and activates a new release manifest referencing an earlier immutable published payload. The failed release remains addressable and audited.
- A superseded payload is not changed back to published; a new release pointer is the rollback mechanism.

## Concurrency and Audit

Every command supplies expected `revision_no`, actor, reason, correlation ID, and idempotency key. A transition atomically writes the state change, domain review event, Change Set disposition when applicable, and system audit event. Conflicts return `409`; policy failures return `422` or `403`.

