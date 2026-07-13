# Building Family Execution Plan

Stage: `REFERENCE_FAMILY_FRAMEWORK_LOCK_1`

This is a plan-only downstream sequence. Only the framework lock stage is executed now.

| stage | status | purpose | inputs | outputs | explicit_no_go |
| --- | --- | --- | --- | --- | --- |
| REFERENCE_FAMILY_FRAMEWORK_LOCK_1 | executed_this_round | Lock source family registry, routing matrix, six-layer contracts, entity dictionary, and A1.1 golden slice registration. | source_standards scan; existing A1.1 runs; existing Web draft/audit counts | framework docs, private registry CSVs, review workbook, manifest updates | no A01/A02/A03 full parse; no Mapping execution; no Web business page modification |
| GD2018_BUILDING_A_FULL_PARSE_1 | planned_only | Parse GD2018 A01/A02/A03 building/decorating quota family into L2 Parsed Reference. | L0 source registry; A01/A02/A03 PDFs; A1.1 parser lessons | gd_quota_item, fee/resource/work/rule/note/conversion candidates and parse issues | must not write Source/Baseline/Web; must not create final mapping or enterprise quota |
| MAP_GB50854_TO_GD2018_BUILDING_1 | planned_only | Map GB/T 50854 bill items to GD2018 A family quota candidates in L3 Mapping Reference. | GB/T 50854 L1 baseline; GD2018 A-family L2 parsed references | bill_quota_mapping_candidate and bill_quota_mapping_issue | no final promotion; no Source Candidate write-back; no enterprise price output |
| WEB_QUOTA_BUILDING_PROTOTYPE_1 | planned_only | Extend Web collaboration from A1.1 slice to building-family review draft workflows. | read-only L3 candidate view model; L4 draft/audit schema | read-only APIs plus Review Draft/Audit writes only | no business page mutation in this framework stage; Web must not mutate L0-L3 |

## Acceptance Gate For Next Stage

- A01/A02/A03 must use `GB/T 50854-2024` as bill standard family.
- `quota_uid` must follow `GD:2018:{family}:{source_code_normalized}`.
- Parsed outputs must carry source document, page/block, parser version, run id, and source hash trace fields.
- Existing A1.1 golden slice counts and Web smoke must remain stable before expanding to the whole A family.
- Copy/Move/Exclude/Restore semantics stay in L4 Review Draft and never mutate Source Candidate.
