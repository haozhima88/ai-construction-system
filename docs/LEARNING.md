# LEARNING.md

# AI × Construction × Data Engineering Learning Journal

---

# Project Mission

## English

This project is not intended to become a commercial ERP system.

Its primary purpose is:

```text
Skill Growth
        +
Portfolio Project
        +
Data Engineering Practice
```

The project serves as a bridge from:

```text
Construction IT
```

to:

```text
ERP
BI
Data Engineering
AI Applications
```

---

## 繁體中文

本專案並非以商業 ERP 為第一目標。

其核心價值：

```text
技能升維
+
作品展示
+
數據工程實踐
```

作為從：

```text
建築信息化
```

轉向：

```text
ERP
BI
數據工程
AI應用
```

的重要轉型載體。

---

# Major Realizations

## Realization 001

Headers are more important than rows.

Before:

```text
Find main rows
```

After:

```text
Find headers
↓
Build schema
↓
Parse rows
```

---

## Realization 002

Schema Driven Parsing

Old:

```python
row_dict.get(3)
```

New:

```python
row_data.get(
    schema["item_name"]
)
```

Meaning:

```text
Dynamic Structure
>
Fixed Columns
```

---

## Realization 003

Excel Row ≠ Business Record

Before:

```text
Excel Row
```

After:

```text
Logical Record
```

Example:

```json
{
  "item_code":"010506001008",
  "item_name":"现浇混凝土基础及联系梁钢筋"
}
```

---

## Realization 004

Context Is Data

Rows like:

```text
category_row
page_info_row
```

contain no quantity.

Yet they carry:

```text
Business Meaning
```

---

## Realization 005

Import Database ≠ Business Database

New understanding:

```text
Excel
↓
Import Staging
↓
Review
↓
Business Database
```

This is the first enterprise-grade workflow inside the project.

---

# Technical Growth

## Python

Current Understanding:

* Functions
* Dictionaries
* Lists
* Schema Mapping
* Data Cleaning

---

## FastAPI

Current Understanding:

* Router
* Upload API
* Review API
* Sync API

---

## PostgreSQL

Current Understanding:

* Table Design
* Insert
* Query
* Update
* Review Workflow

---

## Data Engineering

Current Understanding:

```text
Parser
↓
Normalize
↓
Import
↓
Review
↓
Sync
```

---

# Current Project Status

```text
Environment
██████████ 100%

Parser
██████████ 100%

Import Workflow
██████████ 100%

Review Workflow
██████████ 100%

Sync Workflow
██████████ 100%

Export Workflow
████░░░░░░ 40%

Cost Analysis
░░░░░░░░░░ 0%

AI Analysis
░░░░░░░░░░ 0%
```

---

# Human-AI Collaboration Model

Current Model:

```text
Mahahao
=
Business Expert
+
Junior Architect
+
Data Engineering Learner

ChatGPT
=
Chief Architect
+
Career Coach

Codex
=
Senior Engineer
+
Coding Mentor
```

Workflow:

```text
Business Requirement
        ↓
Architecture Design
        ↓
Codex Implementation
        ↓
Testing
        ↓
Learning
        ↓
Git Commit
```

---

# Future Branches

After V1.0:

## Branch A

AI Bid Cost Analyzer

```text
Tender BOQ
↓
Cost Library
↓
Manual Adjustment
↓
Budget
↓
AI Suggestions
```

---

## Branch B

Construction Project Management System

```text
Form Engine
Workflow Engine
Report Engine
```

---

## Branch C

Construction Data Platform

```text
Documents
↓
Parser
↓
Database
↓
BI
↓
AI
```

---

# Long-Term Goal

Become:

```text
Business
+
Data
+
AI
```

instead of:

```text
Code Only
```

Build capability in:

* ERP
* BI
* Data Engineering
* AI Applications

while maintaining deep construction industry expertise.
