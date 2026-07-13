# Current Reference Pipeline State

## Source of Truth

当前主线以 `construction_cost_knowledge_engine/data/private/reference_extraction/runs/` 下的候选 CSV 为准，不以 mock SQLite 或 seed CSV 为准。

`standard_cost_reference_mvp.sqlite` and `standard_cost_item_reference_A111_seed.csv` are archived P1-COST-REF-1 artifacts and must not be treated as current reference pipeline inputs.

## Completed Stages

1. GB50854_2024_stageB_docx_full
2. GD2018_stage2R_A111_full
3. MAP_A111_quota_to_bill_trial

## Current Next Stage

MAP-A111-QA1：Generate manual QA pack for A.1.1 quota-to-bill mapping candidates.

## Current Valid Inputs

- `bill_item_reference_all_candidate.csv`
- `bill_context_rules_all.csv`
- `standard_cost_item_reference_A111_candidate.csv`
- `reference_quota_pricing_snapshot_A111.csv`
- `quota_to_bill_mapping_A111_candidate.csv`
- `quota_to_bill_mapping_A111_issues.csv`

## Prohibited Actions Before Manual QA

- no database migration
- no schema integration
- no seed import
- no approved
- no internal_price_library
- no write-back bill_code to quota references
- no full-book quota-to-bill mapping
- no use of standard_cost_reference_mvp.sqlite as source of truth

## Naming Convention

Correct next stage output directory:

`construction_cost_knowledge_engine/data/private/reference_extraction/runs/MAP_A111_manual_QA_pack/`
