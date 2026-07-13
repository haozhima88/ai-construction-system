# GD2018 Normalized Rebuild Report

## 1. Task Scope

Rebuild GD2018 A.1.1 candidates from the human-normalized Excel, then rebuild MAP_A111_quota_to_bill_trial after all preconditions pass. This run did not write databases, migrations, schemas, seed imports, approved records, `internal_price_library`, or bill_code values back into quota references.

## 2. Input Normalized Excel

- file: `construction_cost_knowledge_engine/data/private/reference_extraction/source_excels/广东省房屋建筑与装饰工程综合定额2018_normalized.xlsx`
- exists: true
- sha256: `f30f761348c18568b3124cc0ec34854ba62de8a0fba5d109c690e2d2dd2aa678`

## 3. Excel Contract Check

- contract_status: passed
- selected_sheet: `广东建筑装饰工程综合定额库`
- core_mapping: `项目编码 -> source_code`, `项目名称 -> raw_name`, `计量 单位 -> raw_unit`
- pricing_mapping: `人工费`, `材料费`, `机具费`, `管理费`, `合计` exported only to pricing snapshot.

## 4. Script Changes

- Updated `stage_gd2018_a111_full_extract.py` to default to the normalized Excel.
- Added explicit field alias mapping instead of position-based or multi-row-header parsing.
- Added `source_code` normalization for dash variants and spacing.
- Added `excel_contract_profile_GD2018_normalized.csv` output.
- Kept candidate/pricing CSV schemas stable and did not generate bill_code or approved data.

## 5. GD2018 A111 Rebuild Result

- contract_status: ['passed']
- candidate_rows: 143
- pricing_rows: 143
- missing_required_codes: []
- missing_supplemental_codes: []
- invalid_source_code: 0
- duplicate_source_code: 0
- missing_raw_name: 0
- missing_unit: 0
- non_pending: 0
- bill_code_fields: []

## 6. MAP A111 Rebuild Result

- quota_input_rows: 143
- bill_appendix_A_input_rows: 12
- mapping_rows: 175
- unique_quota_codes_in_mapping: 143
- non_pending: 0
- approved: 0

## 7. Artifact Manifest Update

- registered_artifacts: 16
- existing_artifacts: 16
- manifest_csv: `construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv`
- manifest_doc: `construction_cost_knowledge_engine/docs/reference_extraction/REFERENCE_ARTIFACT_MANIFEST.md`

## 8. Quality Checks

### GB50854
- candidate_rows: 472
- context_rule_rows: 161
- invalid_bill_code_9: 0
- duplicate_bill_code_9: 0
- a1_code_mixed_in: 0
- non_pending: 0

### GD2018 A111
- expected_candidate_rows: 143
- actual_candidate_rows: 143
- pricing_snapshot_rows: 143
- missing_required_codes: []
- missing_supplemental_codes: []
- invalid_source_code: 0
- duplicate_source_code: 0
- missing_raw_name: 0
- missing_unit: 0
- non_pending: 0
- bill_code_fields: []

### MAP A111
- expected_quota_input_rows: 143
- actual_quota_input_rows: 143
- expected_bill_appendix_A_input_rows: 12
- actual_bill_appendix_A_input_rows: 12
- mapping_rows: 175
- unique_quota_codes_in_mapping: 143
- non_pending: 0
- approved: 0

## 9. Remaining Issues

- `data/private` remains ignored by Git and requires external backup governance.
- MAP candidates remain pending and must proceed to MAP-A111-QA1 manual QA before any approval or write-back.
- P1 seed/mock sqlite artifacts remain archived and must not be used as source of truth.

## 10. Recommendation

assets_rebuilt_ready_for_MAP_A111_QA1
