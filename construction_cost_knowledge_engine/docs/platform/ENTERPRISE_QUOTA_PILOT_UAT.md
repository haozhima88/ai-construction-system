# Enterprise Quota A1.1 Pilot UAT

## Entry criteria

UAT begins only after PostgreSQL health, Alembic head, authenticated Session/RBAC, `/quota-building` acceptance, RC1 counts, formal Draft/Audit `6/7`, all RC1 Hash Guards, `approved_count=0`, and the RC1 Git checkpoint pass.

The pricing portion cannot be accepted until a business owner confirms a resource-level Enterprise Price source. The current workbook is registered as a candidate only. Testers must not treat composite quota fees as resource unit prices.

## Representative pack

The run directory contains at least 20 A1.1 samples selected for resource count and observed category diversity. The pack identifies labor/material/machine emphasis, multiple-resource rows, rules/notes where present, provincial price completeness, and the current Enterprise price gap.

For every sample, verify:

- Reference Release, quota UID/code and source hash are visible;
- Enterprise quota/version identity is separate from Reference;
- resource code/name/specification/unit/category and link status are correct;
- provincial and Enterprise consumptions are shown side by side;
- provincial price/amount and Enterprise price/amount are distinct;
- a missing Enterprise price is blank, never zero;
- fee summary is calculated by the backend with Decimal;
- work content, rules, Change Sets, audit and version history are traceable;
- the source PDF route remains accessible to an authenticated reader; and
- no action changes Reference, Mapping Candidate, or SQLite.

## Role cases

| Role | Expected result |
|---|---|
| viewer | Read-only page/API; write returns 403 |
| editor | Save Draft, save as new, restore, submit; cannot review/approve/publish |
| reviewer | Read and review/return; cannot review own version |
| approver | Approval rejected until price completeness/authority and separation conditions pass |
| administrator | No implicit editor/reviewer/approver bypass; explicit roles still apply |

Every write must reject missing/invalid CSRF, cross-tenant IDs, stale row version, short/missing idempotency key, invalid state transition, and attempts to edit immutable history.

## Snapshot cases

The preview snapshot must preserve price value, unit, tax basis, region, effective dates, source, resource mapping and calculation-rule version. A null-price snapshot round trip must remain null. A mock historical-price test must prove that a prior non-null value restores unchanged after a later Draft price changes.

## Current exit decision

Automated prechecks and the 20-row sample pack may pass while manual price acceptance remains pending. Until source ownership and field semantics are confirmed, the required exit status is `enterprise_price_source_confirmation_required`; approved and published counts remain zero.
