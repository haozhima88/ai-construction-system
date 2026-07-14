# Reference Artifact Manifest

`construction_cost_knowledge_engine/data/private/` 不进入 Git，但 private artifact 必须登记 row_count、sha256 和可再生成来源。
mock sqlite 和 seed CSV 不能作为 source of truth；Web 原型 SQLite 只服务交互预览与草稿测试。

## WEB_COLLAB_PROTOTYPE_STABILIZATION_1

| Artifact | Exists | Rows | SHA256 | Status |
| --- | --- | ---: | --- | --- |
| web_price_field_mapping_audit.csv | true | 3 | 5104eec08dc3... | ready |
| web_price_display_quality_check.csv | true | 12 | f5fb65f0e874... | ready |
| web_tree_state_bugfix_check.csv | true | 3 | 6cf982a9e483... | ready |
| web_use_province_price_check.csv | true | 1 | 377a5b83d7dd... | ready |
| draft_persistence_guard_check.csv | true | 10 | 0da1a3d6b142... | ready |
| draft_autosave_test_result.csv | true | 1 | b5fada16b938... | ready |
| draft_export_snapshot_manifest.csv | true | 1 | 0ff0b416c514... | ready |
| audit_log_export_snapshot_manifest.csv | true | 1 | f7c3683ba790... | ready |
| stage_web_collab_prototype_stabilization_report.md | true |  | 351bdf022a2c... | ready |
| web_collab_readonly.sqlite | true |  | 708c5615d990... | ready |

## BID_COLLAB_READONLY_TREE_PROTOTYPE_1

| Artifact | Exists | Rows | SHA256 | Status |
| --- | --- | ---: | --- | --- |
| import_bid_records_schema_audit.csv | true | 1 | 977d071576cb... | ready |
| bid_item_code_normalization_audit.csv | true | 609 | 902465613c74... | ready |
| web_bid_tree_nodes.csv | true | 1017 | b096333174df... | ready |
| web_bid_item_display_rows.csv | true | 609 | e4ce352c1395... | ready |
| web_bid_item_to_bill_edges.csv | true | 609 | 224c1f93f04c... | ready |
| web_bid_item_quota_candidate_rows.csv | true | 27814 | 8118da95f245... | ready |
| bid_readonly_tree_smoke_result.csv | true | 15 | ff19f1d45443... | ready |
| stage_bid_collab_readonly_tree_prototype_report.md | true |  | 6e151d53d2e7... | ready |
| web_collab_readonly.sqlite | true |  | d705aeb034a0... | ready |
| build_bid_view_model.py | true |  | ff40b7176ae9... | ready |
| bid_index.html | true |  | 8d2ec56365e0... | ready |
| bid_app.js | true |  | 116eb0698989... | ready |
| bid_style.css | true |  | 53cf7c7b69a7... | ready |

## BID_COLLAB_UI_STRUCTURE_ALIGNMENT_1

| Artifact | Exists | Rows | SHA256 | Status |
| --- | --- | ---: | --- | --- |
| bid_code_name_consistency_audit.csv | true | 609 | 319c18ddbe11... | generated_consistency_audit |
| web_bid_candidate_pool_ranked.csv | true | 27814 | bf713cbcc6b8... | generated_ranked_candidate_pool |
| bid_candidate_ranking_audit.csv | true | 607 | e8aae885586e... | generated_ranking_audit |
| web_bid_composition_preview_rows.csv | true | 3832 | 2953bb12054f... | generated_composition_preview |
| bid_ui_structure_alignment_check.csv | true | 17 | 460ad191a2f8... | smoke_passed |
| bid_workbench_layout_density_check.csv | true | 16 | f08b6862f44b... | layout_density_passed |
| stage_bid_collab_ui_structure_alignment_report.md | true |  | 6a4aeeffc7c7... | ready |
| app.py | true |  | bb11674de335... | ready |
| smoke.py | true |  | 66e2031bec8c... | ready |
| bid_index.html | true |  | c15ecfa7a41d... | ready |
| bid_app.js | true |  | 7bbce5e37a7d... | ready |
| bid_style.css | true |  | 2a275acd4d6b... | ready |
| README.md | true |  | c93caf13edc6... | ready |

## BID_COLLAB_STANDARD_FIRST_STRUCTURE_1

| Artifact | Exists | Rows | SHA256 | Status |
| --- | --- | ---: | --- | --- |
| web_gb_standard_tree_nodes.csv | true | 572 | 74572c29ee46... | generated_standard_tree |
| web_gb_bill_bid_item_rows.csv | true | 609 | 2cd67dfd5103... | generated_bid_item_grouping |
| web_gb_bill_quota_composition_rows.csv | true | 4305 | e7d6b3b9b835... | generated_composition_rows |
| web_bid_source_filter_nodes.csv | true | 96 | 947d781e8c8e... | generated_source_filters |
| bid_standard_first_structure_check.csv | true | 19 | df7c66943cc6... | smoke_passed |
| stage_bid_collab_standard_first_structure_report.md | true |  | 0ed524a59187... | ready |
| app.py | true |  | 8bb57e5cafae... | ready |
| smoke.py | true |  | b4ff4fdd2dc8... | ready |
| bid_index.html | true |  | e54c76f99a48... | ready |
| bid_app.js | true |  | 362de692679c... | ready |
| bid_style.css | true |  | 9173cb2ad47e... | ready |
| README.md | true |  | e7d2f6c781c6... | ready |

## BID_COLLAB_GLODON_STRUCTURE_REFINEMENT_1

| Artifact | Exists | Rows | SHA256 | Status |
| --- | --- | ---: | --- | --- |
| bid_encoding_mojibake_audit.csv | true | 7 | 61973c6619e9... | ready |
| bid_encoding_fix_result.csv | true | 5 | 59049622926f... | ready |
| web_bid_bottom_tabs_model.csv | true | 6 | c65be5e9a782... | ready |
| web_bid_query_panel_model.csv | true | 5 | ac8e7f02007a... | ready |
| bid_glodon_structure_alignment_check.csv | true | 22 | f0d7d4884539... | ready |
| stage_bid_collab_glodon_structure_refinement_report.md | true |  | 624ed85787e8... | ready |
| app.py | true |  | 172eba8cb108... | ready |
| smoke.py | true |  | 78000cac18b3... | ready |
| bid_index.html | true |  | fa5945c48cde... | ready |
| bid_app.js | true |  | 3de437fea04c... | ready |
| bid_style.css | true |  | 5994a6652803... | ready |
| README.md | true |  | d7de34126345... | ready |

## Governance Notes

- source baseline、mapping reference、内部价格源文件不得由 Web 原型回写。
- Web 原型只允许写入 SQLite 草稿表 `web_price_review_draft`、审计表 `web_audit_log` 和只读预览表 `web_bid_*`。
- `import_bid_records` 本轮只读，不写回；后续才会增加 `bid_item_mapping_draft`。
- `approved` 不允许由本阶段生成。
- 每个阶段完成后应备份 `data/private/reference_extraction/runs/` 到 Git 之外的受控位置。

## REFERENCE_FAMILY_FRAMEWORK_LOCK_1

| Artifact | Exists | Rows | SHA256 | Status |
| --- | --- | ---: | --- | --- |
| source_document_registry.csv | true | 32 | 20a1155f17f2... | framework_locked |
| standard_family_registry.csv | true | 9 | d2ef5297d4ce... | framework_locked |
| source_family_routing_matrix.csv | true | 5 | 2603152a6415... | framework_locked |
| reference_layer_contract.csv | true | 6 | f8fb87894861... | framework_locked |
| reference_entity_dictionary.csv | true | 21 | a5be2bf0e13a... | framework_locked |
| golden_slice_A111_registry.csv | true | 1 | 0f6272013dfe... | framework_locked |
| framework_validation_issues.csv | true | 13 | 46d561e50753... | framework_locked |
| Reference_Family_Framework_Review.xlsx | true |  | 2a20147e047e... | framework_locked |
| stage_reference_family_framework_lock_report.md | true |  | 08edf3112450... | framework_locked |
| REFERENCE_FAMILY_ARCHITECTURE.md | true |  | 1bf54618f3fa... | framework_locked |
| REFERENCE_ENTITY_DICTIONARY.md | true |  | 028ff0ba4e1e... | framework_locked |
| BUILDING_FAMILY_EXECUTION_PLAN.md | true |  | d807c65fdbc0... | framework_locked |

Scope: framework/registry/doc generation only; no A01/A02/A03 full parse, no Mapping execution, no Web business page modification, no DB writes.
