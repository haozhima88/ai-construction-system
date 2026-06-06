# README.md

# AI Construction System

# AI 建築工程清單解析系統

## 1. Project Overview / 專案概述

**AI Construction System** is a local AI + ETL + PostgreSQL engineering project for parsing Chinese construction bid Excel files.

**AI Construction System** 是一個面向中國建築工程招標清單的本地化 AI × ETL × PostgreSQL 工程系統。

Its core goal is:

```text
Messy Excel Bid Files
        ↓
Header Detection
        ↓
Dynamic Schema
        ↓
Row Classification
        ↓
Logical Records
        ↓
PostgreSQL / Excel Export / AI Analysis
```

核心目標是：

```text
混亂的招標 Excel
        ↓
表頭識別
        ↓
動態 Schema
        ↓
行分類
        ↓
標準業務記錄
        ↓
PostgreSQL / Excel 導出 / AI 分析
```

---

## 2. Current Stage / 目前階段

Current version:

```text
Parser V2 - Dynamic Schema Driven Parser
```

目前版本：

```text
Parser V2 - 動態 Schema 驅動解析器
```

The system has moved from:

```text
Fixed Column Parser
```

to:

```text
Header → Schema → Parser
```

系統已從：

```text
固定列號解析
```

升級為：

```text
表頭 → Schema → 行解析
```

---

## 3. Key Problem Solved / 已解決的核心問題

Different bid Excel files may have different column positions.

不同招標清單中，欄位位置可能不同。

Example A:

```text
item_name = column 3
quantity  = column 8
total     = column 11
```

Example B:

```text
item_name = column 2
quantity  = column 6
total     = column 9
```

The new parser solves this by generating:

```python
schema = {
    "serial_number": 0,
    "item_code": 1,
    "item_name": 3,
    "feature": 4,
    "unit": 7,
    "quantity": 8,
    "unit_price": 9,
    "total_price": 11
}
```

---

## 4. Current ETL Pipeline / 目前 ETL 管道

```text
Excel File
    ↓
find_header_rows()
    ↓
merge_header_rows()
    ↓
build_schema()
    ↓
classify_rows(schema)
    ↓
clean_row_data()
    ↓
attach_category()
    ↓
merge_continuation_rows()
    ↓
build_logical_records()
    ↓
build_normalized_records()
    ↓
PostgreSQL / Excel Export
```

---

## 5. Main Modules / 主要模組

```text
ai-construction-system/
│
├── api/
│   └── bid_api.py
│
├── services/
│   ├── schema_service.py
│   ├── excel_row_parser.py
│   ├── excel_row_pipeline.py
│   ├── db_service.py
│   └── export_service.py
│
├── utils/
│   ├── column_mapping.py
│   └── db.py
│
├── uploads/
├── exports/
├── .env
├── requirements.txt
├── README.md
└── LEARNING.md
```

---

## 6. Module Responsibilities / 模組職責

| Module                  | Responsibility                   | 中文說明            |
| ----------------------- | -------------------------------- | --------------- |
| `schema_service.py`     | Detect headers and build schema  | 表頭識別與 Schema 建立 |
| `excel_row_parser.py`   | Classify rows using schema       | 使用 Schema 進行行分類 |
| `excel_row_pipeline.py` | Clean, attach, merge, normalize  | 清洗、分類掛載、補充行合併   |
| `db_service.py`         | Insert records into PostgreSQL   | 寫入 PostgreSQL   |
| `export_service.py`     | Export database records to Excel | 導出 Excel        |

---

## 7. Supported Row Types / 支援的行類型

| Row Type             | Meaning               | 中文      |
| -------------------- | --------------------- | ------- |
| `document_title_row` | Document title        | 文檔標題行   |
| `page_info_row`      | Page / project info   | 頁面資訊行   |
| `real_header_row`    | Main table header     | 主表頭     |
| `header_sub_row`     | Sub header            | 副表頭     |
| `category_row`       | Category row          | 分部分項分類行 |
| `main_row`           | Real data row         | 主數據行    |
| `continuation_row`   | Continuation text row | 補充描述行   |
| `subtotal_row`       | Page subtotal         | 本頁小計    |
| `empty_row`          | Empty row             | 空行      |
| `unknown_row`        | Unknown row           | 未識別行    |

---

## 8. Database / 資料庫

Current main table:

```sql
CREATE TABLE bid_records (
    id SERIAL PRIMARY KEY,
    category TEXT,
    serial_number TEXT,
    item_code TEXT,
    item_name TEXT,
    feature TEXT,
    unit TEXT,
    quantity NUMERIC,
    unit_price NUMERIC,
    total_price NUMERIC,
    created_at TIMESTAMP DEFAULT NOW()
);
```

Recommended import staging table:

```sql
CREATE TABLE import_bid_records (
    id SERIAL PRIMARY KEY,
    batch_id TEXT,
    source_file_name TEXT,
    source_sheet_name TEXT,
    source_row_index INTEGER,
    review_status TEXT DEFAULT 'pending',
    category TEXT,
    serial_number TEXT,
    item_code TEXT,
    item_name TEXT,
    feature TEXT,
    unit TEXT,
    quantity NUMERIC,
    unit_price NUMERIC,
    total_price NUMERIC,
    imported_at TIMESTAMP DEFAULT NOW()
);
```

---

## 9. Important Notes / 重要注意事項

1. Do not rely on fixed column indexes anymore.
   不再依賴固定列號。

2. `schema` should be built once and passed downward.
   Schema 應只建立一次，向下傳遞。

3. `excel_row_pipeline.py` should not rebuild schema.
   Pipeline 不應重新建立 Schema。

4. Temporary files like `_copy.py` are acceptable during validation.
   驗證階段可以暫時保留 `_copy.py` 文件。

5. After validation, merge useful logic and remove temporary copies.
   測試穩定後，再合併有價值邏輯並刪除臨時副本。

---

## 10. Next Milestone / 下一階段

```text
Parser V2 Stabilization
    ↓
Multiple Excel Format Testing
    ↓
Import Staging Table
    ↓
Excel Export API
    ↓
Data Review Workflow
    ↓
Official Database Sync
```

下一階段：

```text
穩定 Parser V2
    ↓
多 Excel 格式測試
    ↓
導入暫存表
    ↓
Excel 導出 API
    ↓
人工審核工作流
    ↓
同步正式資料表
```

---

## 11. Project Positioning / 專案定位

This project is not just an Excel parser.

It is becoming:

```text
Construction Data Platform
```

本專案不是普通 Excel 解析腳本，而是在逐步形成：

```text
建築工程數據平台
```
