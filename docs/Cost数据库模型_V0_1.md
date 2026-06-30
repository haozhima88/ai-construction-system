# Cost 数据库模型 V0.1

**Project:** AI Construction System  
**Subproject:** Construction Cost Knowledge Engine  
**Document Type:** Domain Specification / Data Model Specification  
**Version:** V0.1  
**Status:** Draft  
**Source of Truth:** Yes  
**Primary Users:** Technical Lead / ChatGPT / Codex / Cost Department Reviewer  
**Recommended Path:** `E:\workspace\01_Projects\ai-construction-system\docs\Cost数据库模型_V0_1.md`

---

## Revision History

| Version | Date | Author | Description |
|---|---|---|---|
| V0.1 | 2026-06 | AI Construction System Team | Initial cost knowledge database model specification |

---

## Table of Contents

1. [Document Position](#1-document-position)  
2. [Project Goal](#2-project-goal)  
3. [Scope](#3-scope)  
4. [Architecture Boundary](#4-architecture-boundary)  
5. [Design Principles](#5-design-principles)  
6. [Core Data Flow](#6-core-data-flow)  
7. [Database Overview](#7-database-overview)  
8. [Core Tables](#8-core-tables)  
9. [Knowledge Review Workflow](#9-knowledge-review-workflow)  
10. [Matching Strategy](#10-matching-strategy)  
11. [Naming Rules](#11-naming-rules)  
12. [Quality Flags](#12-quality-flags)  
13. [Change Rules](#13-change-rules)  
14. [Codex Working Rules](#14-codex-working-rules)  
15. [Responsibilities](#15-responsibilities)  
16. [Acceptance Criteria V0.1](#16-acceptance-criteria-v01)  
17. [Future Extension](#17-future-extension)  
18. [Repository Context](#18-repository-context)  
19. [Appendix A: Recommended Codex Prompt](#19-appendix-a-recommended-codex-prompt)  
20. [Final Statement](#20-final-statement)

---

# 1. Document Position

This document is the **Source of Truth** for the `Construction Cost Knowledge Engine` V0.1.

It is not a README.  
It is not a temporary implementation note.  
It is not a script-level instruction.

It defines:

- The domain boundary.
- The data model.
- The knowledge workflow.
- The review rules.
- The core database tables.
- The principles Codex must follow when modifying code.
- The acceptance criteria for V0.1.

If there is any conflict between this document and:

- Old README files.
- Old migration SQL files.
- Temporary files.
- Existing Python implementation.
- Existing tests.
- Existing Codex-generated code.

Then this document takes precedence.

---

# 2. Project Goal

`Construction Cost Knowledge Engine` is designed to transform enterprise internal construction cost price tables into a structured, reviewable, traceable, versioned, AI-ready cost knowledge base.

The goal is not simply to import an Excel file.

The goal is to build:

```text
Enterprise Construction Cost Knowledge
```

This project belongs to:

```text
Knowledge Engineering
+
Master Data Governance
+
Construction Cost Domain Modeling
```

It is not merely:

```text
Excel Import
+
Database Storage
```

---

# 3. Scope

## 3.1 In Scope

V0.1 includes:

- Importing internal construction cost price spreadsheets.
- Preserving original raw Excel rows.
- Normalizing item names and units.
- Splitting labor, material, and machine price components.
- Generating standard names.
- Generating keywords.
- Extracting structured cost item features.
- Marking quality issues.
- Marking records that need human review.
- Maintaining import batch traceability.
- Maintaining knowledge version.
- Preparing data for Web Review Center.
- Preparing approved data for internal price library.
- Supporting future AI matching and bid cost analysis.

---

## 3.2 Out of Scope

V0.1 does not include:

- Full bid cost analysis.
- Final AI matching.
- Full province-level standard quota library.
- ERP contract management.
- Payment workflow.
- Project settlement workflow.
- Supplier management.
- Production-grade permission system.
- Multi-tenant enterprise SaaS architecture.
- Final AI decision-making without human review.

---

# 4. Architecture Boundary

`Construction Cost Knowledge Engine` only manages construction cost knowledge.

It provides standardized cost knowledge to other modules, such as:

```text
Bid Cost Analyzer
ERP Integration
BI Dashboard
AI Agent
Report Engine
```

It does not directly own:

- Bid import workflow.
- Contract workflow.
- Payment approval workflow.
- Project settlement workflow.
- Procurement workflow.
- Financial accounting workflow.

The engine should be treated as a **knowledge foundation layer**.

---

# 5. Design Principles

## 5.1 Preserve Original Data

All original Excel data must be preserved.

The system must retain:

- Original file name.
- Original file hash.
- Original sheet name.
- Original row number.
- Original category.
- Original item name.
- Original unit.
- Original remark.
- Original labor price.
- Original material price.
- Original machine price.

Raw data is immutable after import.

---

## 5.2 AI Suggestion Only

AI can suggest:

- `standard_name`
- `keywords`
- `remark`
- `features`
- `confidence`
- `needs_review`

AI must not directly write final approved enterprise knowledge.

AI output must be treated as a suggestion, not as truth.

---

## 5.3 Human Review Required

All AI-generated or rule-generated standardized knowledge must support human review.

Review statuses:

```text
pending
approved
rejected
needs_fix
```

Only approved knowledge can enter `internal_price_library`.

---

## 5.4 Traceability

Every approved cost knowledge item must be traceable through this chain:

```text
Excel File
↓
Sheet
↓
Row
↓
Import Batch
↓
Raw Row
↓
Normalized Item
↓
Review Record
↓
Approved Knowledge
↓
Internal Price Library
```

---

## 5.5 Knowledge Before Price

Price is not the only value of this system.

The engine must also preserve and standardize:

- Standard name.
- Applicable scope.
- Construction method.
- Specification.
- Unit.
- Keywords.
- Remarks.
- Review comments.
- Match rules.
- Source traceability.

Price is one component of knowledge.

---

## 5.6 Version First

Knowledge must support versioning.

Examples:

```text
knowledge_version = V0.1
knowledge_version = V0.2
knowledge_version = V1.0
```

Future AI reports, bid cost estimates, and matching results should record the knowledge version used.

---

# 6. Core Data Flow

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
Bid Cost Analyzer
        ↓
AI Suggestion / BI / ERP Integration
```

This flow must guide all V0.1 implementation.

---

# 7. Database Overview

V0.1 uses SQLite as the local knowledge database.

Default database location:

```text
construction_cost_knowledge_engine/data/private/cost_engine.sqlite
```

Private data must not be committed to Git.

Recommended private data paths:

```text
construction_cost_knowledge_engine/data/private/
```

Recommended mock/test data paths:

```text
construction_cost_knowledge_engine/data/mock/
```

---

# 8. Core Tables

V0.1 contains the following core tables:

```text
source_import_batches
raw_cost_price_rows
cost_categories
unit_dictionary
cost_items
cost_price_components
cost_item_features
knowledge_review_records
internal_price_library
```

---

## 8.1 source_import_batches

### Purpose

Records each import batch.

### Rules

- Each import operation must create one batch.
- Each batch must record file hash.
- Batch records enable source traceability.
- Batch records support future rollback, comparison, and version tracking.

### Fields

| Field | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Import batch ID |
| source_file_name | TEXT | Original file name |
| source_file_hash | TEXT | File hash |
| source_sheet_name | TEXT | Sheet name |
| imported_at | TEXT | Import timestamp |
| row_count | INTEGER | Original row count |
| success_count | INTEGER | Successfully processed rows |
| warning_count | INTEGER | Warning count |
| error_count | INTEGER | Error count |
| knowledge_version | TEXT | Knowledge version |
| note | TEXT | Import note |

---

## 8.2 raw_cost_price_rows

### Purpose

Stores original internal price table rows.

This is the raw traceability layer.

### Rules

- Raw rows must not be modified.
- Raw rows must not be used directly for final matching.
- Raw rows must remain available for audit and correction.
- Raw rows are the evidence layer.

### Fields

| Field | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Raw row ID |
| batch_id | INTEGER | Import batch ID |
| source_row_no | INTEGER | Original Excel row number |
| raw_category_1 | TEXT | Original level-1 category |
| raw_category_2 | TEXT | Original level-2 category |
| raw_item_name | TEXT | Original item name |
| raw_labor_price | REAL | Original labor price |
| raw_material_price | REAL | Original material price |
| raw_machine_price | REAL | Original machine price |
| raw_unit | TEXT | Original unit |
| raw_remark | TEXT | Original remark |
| created_at | TEXT | Created timestamp |

---

## 8.3 cost_categories

### Purpose

Stores construction cost category dictionary.

### Rules

- Supports hierarchical categories.
- Normalizes category expressions from internal price tables.
- Does not directly perform matching.
- Categories are auxiliary dimensions for filtering, review, and analysis.

### Fields

| Field | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Category ID |
| parent_id | INTEGER | Parent category ID |
| category_name | TEXT | Category name |
| category_level | INTEGER | Category level |
| created_at | TEXT | Created timestamp |

---

## 8.4 unit_dictionary

### Purpose

Stores unit normalization dictionary.

### Rules

- Normalizes expressions such as `m3`, `m³`, and `立方米`.
- Unit is an important constraint for matching and cost calculation.
- Unknown units must generate quality flags.
- Unit normalization must be reviewable and extendable.

### Fields

| Field | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Unit ID |
| raw_unit | TEXT | Original unit |
| normalized_unit | TEXT | Normalized unit |
| unit_type | TEXT | Quantity type |
| note | TEXT | Note |
| created_at | TEXT | Created timestamp |

---

## 8.5 cost_items

### Purpose

Stores standardized cost knowledge items.

This is the core table of V0.1.

### Rules

- `original_name` preserves the original Excel item name.
- `normalized_name` is generated by parser/normalizer.
- `standard_name` is the enterprise standard name.
- `standard_name` is the first-priority matching field.
- `keywords` are used for rule matching, AI recall, and search.
- `needs_review = 1` means the item requires human review.
- `review_status` tracks review state.
- `confidence` records AI/rule confidence.

### Fields

| Field | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Cost item ID |
| category_level_1_id | INTEGER | Level-1 category ID |
| category_level_2_id | INTEGER | Level-2 category ID |
| original_name | TEXT | Original item name |
| normalized_name | TEXT | Cleaned item name |
| standard_name | TEXT | Enterprise standard name |
| keywords | TEXT | Keywords, semicolon-separated |
| unit_id | INTEGER | Unit dictionary ID |
| remark | TEXT | Standardized remark |
| original_remark | TEXT | Original remark |
| needs_review | INTEGER | Whether human review is needed |
| review_status | TEXT | Review status |
| confidence | REAL | AI / rule confidence |
| source_row_no | INTEGER | Source row number |
| source_batch_id | INTEGER | Source batch ID |
| quality_flags | TEXT | Quality flags JSON |
| knowledge_version | TEXT | Knowledge version |
| created_at | TEXT | Created timestamp |
| updated_at | TEXT | Updated timestamp |

---

## 8.6 cost_price_components

### Purpose

Stores labor, material, and machine price components.

### Rules

- Labor, material, and machine prices must not be merged into one field only.
- `component_type` must use one of:

```text
labor
material
machine
```

- `unit_cost` can be calculated from components.
- Zero price components should be flagged if meaningful.

### Fields

| Field | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Component ID |
| cost_item_id | INTEGER | Cost item ID |
| component_type | TEXT | labor / material / machine |
| unit_price | REAL | Unit price |
| source_row_no | INTEGER | Source row number |
| source_batch_id | INTEGER | Source batch ID |
| quality_flags | TEXT | Quality flags JSON |
| created_at | TEXT | Created timestamp |

---

## 8.7 cost_item_features

### Purpose

Stores structured features extracted from item names or remarks.

Examples:

- Specification.
- Thickness.
- Strength grade.
- Transportation method.
- Transportation distance.
- Construction method.
- Applicable scope.

### Rules

- Features do not replace `standard_name`.
- Features assist matching.
- Features can be generated by rules or AI.
- Features must carry confidence.

### Fields

| Field | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Feature ID |
| cost_item_id | INTEGER | Cost item ID |
| feature_key | TEXT | Feature name |
| feature_value | TEXT | Feature value |
| source_field | TEXT | Source field |
| confidence | REAL | Confidence |
| created_at | TEXT | Created timestamp |

---

## 8.8 knowledge_review_records

### Purpose

Stores human review records.

This is the core table for the future Web Review Center.

### Rules

- AI/rule suggestions must enter review queue.
- Reviewer may edit `standard_name`, `keywords`, and `remark`.
- Review records must be preserved.
- Review should not overwrite raw evidence.
- Approved records can generate/update `internal_price_library`.

### Fields

| Field | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Review record ID |
| cost_item_id | INTEGER | Cost item ID |
| suggested_standard_name | TEXT | Suggested standard name |
| reviewed_standard_name | TEXT | Human-reviewed standard name |
| suggested_keywords | TEXT | Suggested keywords |
| reviewed_keywords | TEXT | Human-reviewed keywords |
| suggested_remark | TEXT | Suggested remark |
| reviewed_remark | TEXT | Human-reviewed remark |
| review_status | TEXT | pending / approved / rejected / needs_fix |
| reviewer | TEXT | Reviewer |
| review_comment | TEXT | Review comment |
| reviewed_at | TEXT | Reviewed timestamp |
| created_at | TEXT | Created timestamp |

---

## 8.9 internal_price_library

### Purpose

Stores approved enterprise internal price knowledge.

This is the formal source for future cost estimation and bid analysis.

### Rules

- Only approved knowledge can enter this table.
- AI suggestions must not directly enter this table.
- This table provides cost knowledge to `Bid Cost Analyzer`.
- This table should support active/inactive status.
- This table should preserve knowledge version.

### Fields

| Field | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Internal price library ID |
| cost_item_id | INTEGER | Source cost item ID |
| standard_name | TEXT | Standard name |
| keywords | TEXT | Keywords |
| unit | TEXT | Unit |
| labor_price | REAL | Labor price |
| material_price | REAL | Material price |
| machine_price | REAL | Machine price |
| unit_cost | REAL | Total unit cost |
| remark | TEXT | Remark |
| knowledge_version | TEXT | Knowledge version |
| active | INTEGER | Whether active |
| created_at | TEXT | Created timestamp |
| updated_at | TEXT | Updated timestamp |

---

# 9. Knowledge Review Workflow

```text
AI / Rule Suggestion
        ↓
knowledge_review_records.pending
        ↓
Human Review
        ↓
approved / rejected / needs_fix
        ↓
internal_price_library
```

## 9.1 Review Actions

| Action | Meaning |
|---|---|
| Approve | Accept suggestion |
| Edit + Approve | Modify and accept |
| Reject | Reject suggestion |
| Needs Fix | Send back for correction |

## 9.2 Review Fields

Review should focus on:

- `standard_name`
- `keywords`
- `remark`
- `unit`
- `confidence`
- `quality_flags`
- price reasonableness

---

# 10. Matching Strategy

Future matching priority:

1. `standard_name`
2. `keywords`
3. `unit`
4. `cost_item_features`
5. `remark`
6. historical match rules
7. embedding / AI semantic matching

V0.1 does not implement full AI matching.

V0.1 prepares the standardized knowledge foundation for AI matching.

---

# 11. Naming Rules

## 11.1 original_name

The exact original Excel item name.

Must not be changed.

## 11.2 normalized_name

Parser-cleaned item name.

Examples:

- Remove extra spaces.
- Normalize punctuation.
- Normalize full-width / half-width symbols.
- Normalize common unit symbols.

## 11.3 standard_name

Enterprise standard name.

Rules:

- Must be concise.
- Must be stable.
- Must be unambiguous.
- Must not include long remarks.
- Must not include temporary human notes.
- Must be suitable for matching.

## 11.4 keywords

Used for:

- search
- rule matching
- AI recall
- future semantic matching

Recommended format:

```text
土方;开挖;机械;场内运输
```

## 11.5 remark

Used for:

- applicable scope
- construction method
- special condition
- transportation distance
- assumptions
- constraints

Remark should not be mixed into `standard_name`.

---

# 12. Quality Flags

Suggested quality flags:

| Flag | Meaning |
|---|---|
| MISSING_UNIT | Unit missing |
| UNKNOWN_UNIT | Unit cannot be normalized |
| MISSING_PRICE | Labor/material/machine price all missing |
| ZERO_PRICE_COMPONENT | Zero price component exists |
| DUPLICATE_NORMALIZED_NAME | Duplicate normalized name |
| LONG_NAME_WITH_REMARK | Item name may contain remark |
| NEEDS_MANUAL_REVIEW | Human review required |
| LOW_CONFIDENCE | Low AI/rule confidence |
| MISSING_CATEGORY | Category missing |
| INCONSISTENT_UNIT | Unit inconsistent with item type |

---

# 13. Change Rules

Any change to the following must update this document first:

- Database tables.
- Field meanings.
- Review workflow.
- Matching strategy.
- Knowledge versioning.
- Naming rules.
- Quality flag definitions.
- Core data flow.

Then update:

```text
migration
Python code
tests
docs/data_model.md
Web UI
README
```

Do not directly modify implementation before updating this specification.

---

# 14. Codex Working Rules

Codex must follow these rules:

1. Do not use temporary files as design source.
2. Do not infer the current model from old README files.
3. Do not infer the current model from old migration SQL.
4. Always read this document first.
5. If this document conflicts with existing code, this document wins.
6. If field meaning is unclear, stop and ask.
7. Do not commit real price data.
8. Do not commit files under `data/private`.
9. Tests must use mock data.
10. After changes, provide commands and test results.
11. Keep functions small and testable.
12. Do not mix Web UI logic into ETL engine.
13. Do not mix Bid Cost Analyzer logic into Cost Knowledge Engine.

---

# 15. Responsibilities

## 15.1 Technical Lead

Responsible for:

- Business boundary.
- Cost knowledge rules.
- Review standards.
- Acceptance decisions.
- Coordination with cost department.

## 15.2 ChatGPT

Responsible for:

- Architecture design.
- Data model specification.
- Domain modeling.
- Codex instruction design.
- Review support.

## 15.3 Codex

Responsible for:

- SQLite migration.
- Python importer.
- Normalizer.
- Validator.
- Matcher prototype.
- Tests.
- Web Review UI implementation when requested.

## 15.4 Cost Department Reviewer

Responsible for:

- Confirming standard names.
- Confirming keywords.
- Confirming remarks.
- Confirming price reasonableness.
- Providing domain correction.

---

# 16. Acceptance Criteria V0.1

V0.1 is complete when:

- Full internal price table can be imported.
- All raw rows are preserved.
- Standardized cost items are generated.
- Labor/material/machine prices are split.
- `standard_name` is generated.
- `keywords` are generated.
- `needs_review` is marked.
- `knowledge_review_records` are generated.
- Review-needed records can be queried.
- Approved records can generate `internal_price_library`.
- All core workflows have mock tests.
- Private real price data is not committed to Git.

---

# 17. Future Extension

Future extensions may include:

- Province standard cost item library.
- Historical project cost library.
- Supplier price library.
- Rule engine.
- Regex matching.
- Embedding matching.
- Knowledge graph.
- Bid Cost Analyzer.
- AI Report Engine.
- ERP Integration.
- BI Dashboard.
- Multi-user review workflow.
- Permission control.
- Audit trail.

---

# 18. Repository Context

Recommended structure:

```text
ai-construction-system/
├── docs/
│   └── Cost数据库模型_V0_1.md
│
├── construction_cost_knowledge_engine/
│   ├── migrations/
│   ├── src/
│   │   └── cost_engine/
│   ├── scripts/
│   ├── tests/
│   ├── data/
│   │   ├── private/
│   │   └── mock/
│   └── PROJECT_CONTEXT.md
│
├── api/
├── services/
├── static/
└── README.md
```

---

# 19. Appendix A: Recommended Codex Prompt

Use the following prompt when asking Codex to align implementation with this document:

```text
当前仓库根目录是：
E:\workspace\01_Projects\ai-construction-system

当前子工程目录是：
E:\workspace\01_Projects\ai-construction-system\construction_cost_knowledge_engine

唯一事实来源文档是：
E:\workspace\01_Projects\ai-construction-system\docs\Cost数据库模型_V0_1.md

请先读取该文档。

本次任务：
按照 Cost 数据库模型 V0.1，更新 construction_cost_knowledge_engine 的 SQLite migration、Python importer、normalizer、validator、review record generation 和 mock tests。

允许修改：
- construction_cost_knowledge_engine/migrations/
- construction_cost_knowledge_engine/src/cost_engine/
- construction_cost_knowledge_engine/tests/
- construction_cost_knowledge_engine/docs/data_model.md

不允许修改：
- Web UI
- FastAPI 主系统
- 真实 data/private 数据
- 与本任务无关的 README

要求：
1. 保留原始 Excel 行。
2. 生成 cost_items。
3. 拆分 labor/material/machine components。
4. 生成 standard_name / keywords / needs_review / confidence。
5. 生成 knowledge_review_records。
6. 支持 approved 后生成 internal_price_library。
7. 使用 mock 测试数据。
8. 不提交任何真实价格数据。
9. 如果现有代码与 Cost数据库模型_V0_1.md 冲突，以文档为准。
10. 如果字段含义不清楚，请停止并报告，不要猜。
```

---

# 20. Final Statement

This document is the Source of Truth for `Construction Cost Knowledge Engine V0.1`.

In V0.1, any database, code, test, Web UI, README, or implementation change must remain consistent with this document.

End.
