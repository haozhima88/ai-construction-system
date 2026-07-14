# Enterprise Price Import and Matching Policy

## Scope

This policy governs tenant-owned Enterprise Price evidence and its use in the GD2018 A1.1 pilot. It does not authorize a file merely because its name contains “internal price,” does not create synthetic prices, and never changes Reference or Mapping Candidate records.

## Source registration

Every candidate is registered with an immutable ID, absolute path, SHA256, file type, record count, field-completeness statuses, source role, authority status, and review status. Allowed source roles are:

- `enterprise_price_source_candidate`
- `enterprise_historical_observation`
- `market_reference`
- `unknown_price_source`

Authority is an independent decision. File names, historical parser labels, previous matching output, and composite quota fees are evidence, not authority. Confirmation must identify the business owner, price semantics, applicable tenant, tax basis, region, effective period, and whether each row is a resource unit price.

## Current A1.1 decision

The existing internal-price workbook contains composite labor/material/machine observations. It lacks the governed resource-code/specification/tax/effective-date/region contract required for resource pricing. Its derived CSV and review workbooks remain historical observations. Therefore:

- Enterprise Price record count remains zero;
- missing prices remain null and are never filled with zero;
- `enterprise_approved` cannot be selected;
- a blank resource-level import template is produced; and
- the pilot status is `enterprise_price_source_confirmation_required`.

## Import contract

The import template requires `enterprise_resource_id`, resource code/name/specification/unit/category, `price_value`, `price_type`, `tax_mode`, currency, region, project type, supplier/source, effective range, source document ID, confidence, and review status. The importer must reject an unknown resource, negative price, invalid effective range, missing source, cross-tenant link, duplicate idempotency key, or a unit/tax conversion without a governed rule.

Prices are stored as PostgreSQL `numeric` and processed as Python `Decimal`. Browser floating-point output is never authoritative.

## Matching policy

Allowed resource link methods are `exact_code`, `normalized_code`, `exact_name_spec_unit`, `semantic_candidate`, `manual_link`, and `unmatched`.

- Exact and normalized matches must retain field-level comparison results.
- Semantic output is a candidate only and cannot be auto-approved.
- Manual links require actor, reason, timestamp, row version, idempotency key, and Audit.
- Unmatched resources remain visible and priced as null.

Price precedence is display/selection policy only: `enterprise_approved`, `enterprise_observed`, `enterprise_aggregated`, `market_reference`, then `provincial_baseline`. A Draft may preview a governed non-rejected Enterprise Price version, but publication must freeze the selected version and evidence in an immutable snapshot.

## Write controls

Every price write requires Session, CSRF, Tenant scope, RBAC, row version, idempotency key, and Audit. Approved or published price versions and all snapshot history are immutable. The A1.1 pilot disables formal publication.
