# GB50854 Dual Source Governance

Stage: `GB50854_DUAL_SOURCE_EVIDENCE_LOCK_1`

## Roles

- `GB50854_AUTHORITY_PDF_2024`: `source_role = authority_source`, `authority_status = official_standard_evidence`.
- `GB50854_EXTRACTION_PROXY_DOCX_2024`: `source_role = extraction_proxy`, `authority_status = non_authoritative_structured_source`.
- `GB50854_BASELINE_472_DERIVED_REFERENCE`: `source_role = derived_reference_candidate`, `authority_status = derived_pending_reference`.

The DOCX is a structured extraction proxy only. It must not be treated as the authority source for conflicts.

## Conflict Rule

All source relationships use:

`conflict_resolution_rule = official_pdf_wins`

When the authority PDF and extraction proxy or derived baseline conflict, the authority PDF governs. A conflict must be recorded in `gb50854_authority_conflicts.csv`; it must not be silently resolved in place.

## Evidence Link Policy

The authority PDF currently has no detected machine text layer in this stage. Therefore the stage does not claim automatic row-level text verification and does not rerun OCR. Records without an authority page/table link stay:

`authority_verification_status = pending_evidence_link`

Future work should add `official_pdf_page_no` and table/page visual evidence incrementally through the backlog. Unlinked records must not be shown as verified.

## Web Display Policy

Future Web screens should display source roles separately:

- authority PDF evidence;
- extraction proxy source;
- derived pending reference baseline.

The Web must not present the DOCX proxy as the authority source and must not hide pending evidence links.

## Supplemental Gate

`gb50854_dual_source_gate.csv` final status:

`gb50854_baseline_ready_with_evidence_backlog`
