# Enterprise Price Domain

## Purpose

The domain versions enterprise-specific resource prices independently from Reference. It records evidence and governance decisions; this stage deliberately defines no calculation engine.

## Required Price Contract

| Field | Contract |
|---|---|
| `resource_id` | FK to `enterprise_resource` |
| `resource_name` | normalized display name, with original name preserved in provenance |
| `specification` | nullable controlled text |
| `unit` | normalized unit plus original unit when imported |
| `price_value` | `numeric(20,6)`, positive or explicitly allowed zero |
| `price_type` | one of the governed precedence classes |
| `tax_mode` | explicit included/excluded/unknown policy value |
| `region` | governed region code and label |
| `project_type` | nullable classification |
| `supplier_or_source` | supplier ID, market source, document, or provincial source |
| `effective_from`, `effective_to` | non-overlapping effective range per governed version policy |
| `source_document` | provenance FK or immutable external evidence descriptor |
| `confidence` | bounded decimal with method metadata |
| `review_status` | observation or version workflow status; `approved` only here in Enterprise |
| `version` | monotonic version for the enterprise resource |

Currency, tenant, timestamps, creator, reviewer, and evidence hash are mandatory platform fields even though they are not repeated in the minimum business list.

## Precedence Policy

Highest to lowest:

1. `enterprise_approved`
2. `enterprise_observed`
3. `enterprise_aggregated`
4. `market_reference`
5. `provincial_baseline`

This is selection policy, not an implemented formula. Physical implementation must define applicability windows, region/project compatibility, unit conversion governance, tax normalization, outlier handling, tie-breaks, and an explainable decision trace before any automatic price selection is enabled.

## Versioning and Approval

- Observations are append-only evidence and may be reviewed or rejected.
- A price version references the exact observation set and decision rationale used to produce it.
- Approval is a separate append-only record, never a mutable flag on an observation.
- Corrections create a new price version; approved or released versions are not edited.
- Overlapping effective versions are blocked unless an explicit business rule and approval exception exists.

## Quota Release Snapshot

Every Enterprise Quota publication must capture an immutable price snapshot containing the selected `enterprise_price_version_id`, value, unit, tax mode, currency, effective date, precedence class, and source/approval evidence for every priced component. Later price releases do not change an already published quota release.

## Current Stage Boundary

No observations are imported, no precedence is executed, no enterprise price is calculated, and no approval record or price release is created here.

