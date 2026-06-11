# README.md

# AI-CONSTRUCTION-SYSTEM

## Construction Data Engineering Platform Prototype

---

# Project Overview | 專案概覽

## English

AI-CONSTRUCTION-SYSTEM is a Construction Data Engineering Platform Prototype.

Its purpose is to transform unstructured construction bidding Excel documents into structured, traceable and reusable business data.

Core workflow:

```text
Construction Excel
        ↓
Header Detection
        ↓
Schema Builder
        ↓
Row Classification
        ↓
Context Attachment
        ↓
Logical Records
        ↓
Import Database
        ↓
Review Workflow
        ↓
Business Database
```

---

## 繁體中文

AI-CONSTRUCTION-SYSTEM 是一套建築工程數據工程平台原型系統。

主要目標：

將建築工程招標清單、工程量清單等 Excel 文件轉換為：

* 可查詢
* 可分析
* 可追溯
* 可複用

的標準化數據資產。

---

# Current Architecture | 當前系統架構

```text
┌─────────────────────┐
│ Construction Excel  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Header Detection    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Schema Builder      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Row Parser          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Context Engine      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Logical Records     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ import_bid_records  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Review Workflow     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ bid_records         │
└─────────────────────┘
```

---

# Current ETL Pipeline

```text
Excel
 ↓
find_header_rows()
 ↓
merge_header_rows()
 ↓
build_schema()
 ↓
classify_rows()
 ↓
attach_category()
 ↓
build_logical_records()
 ↓
build_normalized_records()
 ↓
insert_import_records()
 ↓
review_status
 ↓
approved_to_bid_records()
```

---

# Database Design

## import_bid_records

Import staging area.

Purpose:

```text
Raw Data
↓
Review
↓
Approval
```

Key Fields:

| Field             | Description                            |
| ----------------- | -------------------------------------- |
| batch_id          | Import batch identifier                |
| source_file_name  | Source Excel file                      |
| source_sheet_name | Source sheet                           |
| source_row_index  | Original row                           |
| review_status     | pending / approved / rejected / synced |

---

## bid_records

Formal business records.

Purpose:

```text
Reviewed
↓
Approved
↓
Business Data
```

---

# Example Output

```json
{
  "batch_id":"3a9f734c-c10d-4dfc-ba74-91ea7402474c",
  "source_file_name":"(单位)1001基坑支护.xlsx",
  "source_sheet_name":"1",
  "source_row_index":49,
  "mapping_version":"v1.0",
  "project_name":"基坑支护",
  "category":"混凝土及钢筋混凝土工程",
  "serial_number":"22",
  "item_code":"010506001008",
  "item_name":"现浇混凝土基础及联系梁钢筋",
  "unit":"t",
  "quantity":0.36,
  "unit_price":5468.92,
  "total_price":1968.81
}
```

---

# Technology Stack

Backend

* Python 3.11
* FastAPI

Database

* PostgreSQL

Data Processing

* Pandas

Development

* Git
* VS Code

---

# Roadmap

## V1.0

Completed

* Parser Engine
* Schema Builder
* Context Engine
* Import Workflow
* Review Workflow
* Sync Workflow

## V1.1

Planned

* Export Workflow
* Batch Review
* Batch Sync
* Data Validation

## V2.0

Planned

* Cost Database
* Cost Analysis
* AI Cost Suggestions

## V3.0

Planned

* Construction Data Platform
* BI Dashboard
* AI Tender Assistant
* Cost Agent

---

# Author

Mahahao

AI × Construction × Data Engineering
