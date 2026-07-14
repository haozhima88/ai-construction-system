# Private Runs Rebuild Report

## 1. Task Scope

Rebuild `data/private/reference_extraction/runs/` mainline artifacts only from original DOCX/Excel source files and verified extraction scripts. This run did not write databases, migrations, schemas, approved records, `internal_price_library`, mock seed imports, or MAP-A111-QA1 outputs.

## 2. Source File Check

- `construction_cost_knowledge_engine/data/private/reference_extraction/source_standards/房屋建筑与装饰工程工程量计算标准 GB_T 50854-2024.docx`: exists
- `construction_cost_knowledge_engine/data/private/reference_extraction/source_excels/广东省房屋建筑与装饰工程综合定额（2018 ）.xlsx`: exists

## 3. Script Availability Check

- `construction_cost_knowledge_engine/scripts/reference_extraction/stageB_docx_extract_gb50854_full.py`: exists
- `construction_cost_knowledge_engine/scripts/reference_extraction/stage_gd2018_a111_full_extract.py`: exists
- `construction_cost_knowledge_engine/scripts/reference_extraction/stage_map_a111_quota_to_bill.py`: exists

## 4. Rebuilt Stages

- `GB50854_2024_stageB_docx_full`: rebuilt successfully from DOCX source.
- `GD2018_stage2R_A111_full`: attempted but failed at expected-header validation against the current Excel layout.
- `MAP_A111_quota_to_bill_trial`: not run because GD2018 A.1.1 candidate/pricing inputs were not rebuilt.

## 5. Artifact Manifest Summary

- registered_artifacts: 15
- existing_artifacts: 5
- missing_or_blocked_artifacts: 10
- manifest_csv: `construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv`
- manifest_doc: `construction_cost_knowledge_engine/docs/reference_extraction/REFERENCE_ARTIFACT_MANIFEST.md`

## 6. Quality Checks

### GB50854_2024_stageB_docx_full

- status: rebuilt
- candidate_rows: 472
- context_rule_rows: 161
- invalid_bill_code_9: 0
- duplicate_bill_code_9: 0
- a1_code_mixed_in: 0
- non_pending: 0

### GD2018_stage2R_A111_full

- status: failed
- script: `construction_cost_knowledge_engine/scripts/reference_extraction/stage_gd2018_a111_full_extract.py`
- failure: Missing expected headers: 序号; 定额编号; 项目名称; 规格型号; 计量单位; 主材系数; 工程数量; 主材单价（元）; 人工费; 材料费; 机具费; 管理费; 合计; 主材合价（元）
- observed_source_layout: row 1 is title, row 2/3 are split table headers, and quota code appears under `项目编码`, while the verified script expects row 1 headers including `定额编号`.

### MAP_A111_quota_to_bill_trial

- status: blocked_not_run
- reason: missing rebuilt `standard_cost_item_reference_A111_candidate.csv` and `reference_quota_pricing_snapshot_A111.csv`.

## 7. Missing / Failed Items

- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/GD2018_stage2R_A111_full/standard_cost_item_reference_A111_candidate.csv`: missing_failed_generation - GD2018 script failed because source Excel header layout does not match expected headers.
- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/GD2018_stage2R_A111_full/reference_quota_pricing_snapshot_A111.csv`: missing_failed_generation - GD2018 script failed because source Excel header layout does not match expected headers.
- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/GD2018_stage2R_A111_full/raw_reference_excel_rows_A111.csv`: missing_failed_generation - GD2018 script failed because source Excel header layout does not match expected headers.
- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/GD2018_stage2R_A111_full/gd2018_a111_extraction_issues.csv`: missing_failed_generation - GD2018 script failed because source Excel header layout does not match expected headers.
- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/GD2018_stage2R_A111_full/stage_gd2018_a111_full_report.md`: missing_failed_generation - GD2018 script failed because source Excel header layout does not match expected headers.
- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/MAP_A111_quota_to_bill_trial/quota_to_bill_mapping_A111_candidate.csv`: blocked_missing_gd2018_inputs - MAP stage was not run because GD2018 A.1.1 candidate/pricing outputs were not rebuilt.
- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/MAP_A111_quota_to_bill_trial/quota_to_bill_mapping_A111_issues.csv`: blocked_missing_gd2018_inputs - MAP stage was not run because GD2018 A.1.1 candidate/pricing outputs were not rebuilt.
- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/MAP_A111_quota_to_bill_trial/quota_reference_A111_input_snapshot.csv`: blocked_missing_gd2018_inputs - MAP stage was not run because GD2018 A.1.1 candidate/pricing outputs were not rebuilt.
- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/MAP_A111_quota_to_bill_trial/bill_reference_appendix_A_input_snapshot.csv`: blocked_missing_gd2018_inputs - MAP stage was not run because GD2018 A.1.1 candidate/pricing outputs were not rebuilt.
- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/MAP_A111_quota_to_bill_trial/stage_map_A111_report.md`: blocked_missing_gd2018_inputs - MAP stage was not run because GD2018 A.1.1 candidate/pricing outputs were not rebuilt.

## 8. Backup Recommendation

After a successful full rebuild, copy the complete `construction_cost_knowledge_engine/data/private/reference_extraction/runs/` directory to a timestamped backup under `construction_cost_knowledge_engine/data/private/reference_extraction/backups/`. The manifest must record row counts and SHA256 hashes for private artifacts because `data/private` is not tracked by Git.

## 9. Recommendation

partially_rebuilt_manual_intervention_required
