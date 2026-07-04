# Construction Cost Knowledge Engine Data Model

This document is a short implementation summary of
`docs/Cost数据库模型_V0_1.md`.

`docs/Cost数据库模型_V0_1.md` is the source of truth. If this summary,
README files, migration SQL, Python code, or tests conflict with that
document, the source-of-truth document wins.

## Position

Construction Cost Knowledge Engine V0.1 is a local SQLite knowledge
foundation layer for enterprise internal construction cost knowledge.

It is responsible for:

- preserving raw internal price table evidence;
- normalizing names, units, categories, prices, and features;
- generating reviewable standard-name and keyword suggestions;
- routing generated knowledge through human review;
- publishing approved knowledge to the internal price library.

It is not responsible for bid import workflow, contract workflow,
payment approval, settlement, procurement, accounting, or production
permission management.

## Core Data Flow

```text
Internal Price Excel
        ↓
Raw Import
        ↓
Raw Cost Price Rows
        ↓
Normalizer
        ↓
AI / Rule Suggestion
        ↓
Knowledge Review Queue
        ↓
Human Review
        ↓
Approved Knowledge
        ↓
Enterprise Cost Knowledge Library
        ↓
Internal Price Library
        ↓
Future Bid Cost Analyzer / AI / BI / ERP
```

## V0.1 Core Tables

### source_import_batches

Records one import operation and preserves batch-level traceability.

Key fields:

- `source_file_name`
- `source_file_hash`
- `source_sheet_name`
- `imported_at`
- `row_count`
- `success_count`
- `warning_count`
- `error_count`
- `knowledge_version`
- `note`

### raw_cost_price_rows

Stores original imported row evidence.

Rules:

- raw rows are immutable evidence;
- raw rows are not final matching knowledge;
- source row number and original category/name/unit/remark/price values
  must remain traceable.

### cost_categories

Stores hierarchical construction cost categories.

The V0.1 source model requires `created_at`. The migration currently also
keeps `sort_order` and `is_active` as backward-compatible auxiliary fields
for existing category sorting and soft-activation needs. They are not V0.1
core fields.

### unit_dictionary

Stores raw-to-normalized unit mappings.

Unknown or missing units should produce quality flags and remain
reviewable. `created_at` is required by the V0.1 aligned schema.

### cost_items

Stores standardized cost knowledge items. This is the V0.1 core table.

Important fields:

- `original_name`: exact original Excel item name;
- `normalized_name`: parser-cleaned item name;
- `standard_name`: enterprise standard name and first-priority matching
  field;
- `keywords`: semicolon-separated search and matching terms;
- `original_remark`: original Excel remark;
- `remark`: standardized remark;
- `needs_review`: whether human review is required;
- `review_status`: `pending`, `approved`, `rejected`, or `needs_fix`;
- `confidence`: AI/rule suggestion confidence;
- `quality_flags`: JSON quality flags;
- `knowledge_version`: version of the generated knowledge.

### cost_price_components

Stores labor, material, and machine unit price components separately.

Allowed `component_type` values:

```text
labor
material
machine
```

### cost_item_features

Stores structured features extracted from item names or remarks, such as
specification, thickness, strength grade, construction method, applicable
scope, or transportation distance.

Features assist review and future matching; they do not replace
`standard_name`.

### knowledge_review_records

Stores the human review queue and review history.

AI/rule suggestions should enter this table as pending records. Reviewers
may approve, reject, request fixes, or edit and approve standard names,
keywords, and remarks.

Approved review records can generate or update `internal_price_library`.

### internal_price_library

Stores approved enterprise internal price knowledge.

Only approved knowledge should enter this table. It is the formal V0.1
output for future bid cost analysis, AI suggestions, BI, report engines,
and ERP integration.

## Prototype / Future Tables

The migration temporarily retains:

- `boq_match_rules`
- `boq_match_logs`

These tables belong to the earlier BOQ matcher prototype and future
matching work. They are not V0.1 core tables and should not be treated as
the approved internal price library workflow.

## Compatibility View

`v_cost_item_unit_prices` is retained as a compatibility query surface for
aggregated labor/material/machine prices. It should be considered a helper
view, not the formal approved knowledge surface.

The formal approved knowledge surface for V0.1 is
`internal_price_library`.

## Quality Flags

V0.1 suggested quality flags include:

- `MISSING_UNIT`
- `UNKNOWN_UNIT`
- `MISSING_PRICE`
- `ZERO_PRICE_COMPONENT`
- `DUPLICATE_NORMALIZED_NAME`
- `LONG_NAME_WITH_REMARK`
- `NEEDS_MANUAL_REVIEW`
- `LOW_CONFIDENCE`
- `MISSING_CATEGORY`
- `INCONSISTENT_UNIT`

Implementation should align flags with `docs/Cost数据库模型_V0_1.md`
during importer, normalizer, validator, and tests work.
