# Building Family Execution Gate

Stage: `REFERENCE_FRAMEWORK_PRECONDITION_RECONCILIATION_1`

## Gate Status

`reference_framework_ready_for_building_family_execution`

## Why The Original Framework Was Not Ready

The original `REFERENCE_FAMILY_FRAMEWORK_LOCK_1` report status is `framework_locked_with_manual_source_inventory_warnings` because framework-level source inventory warnings remained for missing standards outside the A01-A03 building/decorating route. This document does not edit that historical report.

## Non-Blocking Warnings

| issue_id | source_family | blocking_level | disposition | evidence | required_action |
| --- | --- | --- | --- | --- | --- |
| RF-005 | GB/T 50500-2024 pricing/specification family | non_blocking | accepted_for_building_family_only | A01/A02/A03 route to GB/T 50854-2024; current building-family gate does not require GB/T 50500-2024. | Add GB/T 50500 source before pricing/general valuation stages, not before A-building parse/mapping. |
| RF-006 | GB/T 50855-2024 other professional family | non_blocking | out_of_scope_for_this_stage | GB/T 50855 is not the target for GD2018 A01/A02/A03; routing matrix targets GB/T 50854-2024. | Add source before executing that separate standard family. |

## Retained Warnings

| issue_id | source_family | blocking_level | disposition | required_action |
| --- | --- | --- | --- | --- |
| RF-005 | GB/T 50500-2024 pricing/specification family | non_blocking | accepted_for_building_family_only | Add GB/T 50500 source before pricing/general valuation stages, not before A-building parse/mapping. |
| RF-006 | GB/T 50855-2024 other professional family | non_blocking | out_of_scope_for_this_stage | Add source before executing that separate standard family. |

## Building-Family Decision

The gate evaluates only GD2018 A01/A02/A03 -> GB/T 50854-2024 execution readiness. A01, A02, A03, the official GB/T 50854 PDF, and the validated DOCX baseline source are present and hash-registered. The GB/T 50854 472-row baseline is reused because its source hash matches the registered `current_gbt50854_baseline` DOCX. The official PDF and DOCX are role-distinct evidence sources, not competing versions.

Next stage should read:

`construction_cost_knowledge_engine/data/private/reference_extraction/runs/REFERENCE_FRAMEWORK_PRECONDITION_RECONCILIATION_1/stage_reference_framework_precondition_reconciliation_report.md`

Detailed report:

`construction_cost_knowledge_engine/data/private/reference_extraction/runs/REFERENCE_FRAMEWORK_PRECONDITION_RECONCILIATION_1/stage_reference_framework_precondition_reconciliation_report.md`
