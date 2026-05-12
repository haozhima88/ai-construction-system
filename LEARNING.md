# LEARNING.md
# AI Construction System Learning Journey

---

# Day 1–5
# FastAPI + PostgreSQL 基礎

---

## 學習內容

- FastAPI basics
- PostgreSQL basics
- CRUD API
- Swagger testing

---

## 理解

API 本質：

```text
HTTP Interface
```

資料庫本質：

```text
Business Relationship Structure
```

---

# Day 6–10
# 成本分析系統

---

## 建立

- projects table
- costs table
- 成本分析 API

---

## 學習

- SQL JOIN
- GROUP BY
- SUM()
- COALESCE()

---

## 理解

資料庫不是：

```text
單純存資料
```

而是：

```text
業務關係模型
```

---

# Day 11–13
# Portfolio Health System

---

## 建立

- 成本率分析
- 健康評分
- 成本分類映射

---

## 關鍵理解

```python
cost_map[pid][ctype] = amount
```

本質：

```text
Project ID
↓
Cost Type
↓
Amount
```

開始真正理解：

- nested dict
- business mapping
- structured data

---

# Day 14–17
# Data Engineering + Architecture Refactor

---

## 建立

- api/
- services/
- utils/
- models/

---

## 理解

開始從：

```text
Single File Script
```

轉向：

```text
Layered Backend Architecture
```

---

# 建立

```python
COLUMN_MAPPING
```

---

## 理解

中國建築業 Excel：

- 簡繁混用
- 欄位混亂
- 格式不統一

因此：

```text
系統內部必須建立統一資料語言
```

---

# Day 18
# Rule Engine

---

## 建立

```python
services/rule_engine.py
```

---

## 建立

```python
classify_cost_type()
```

---

## 理解

真正企業 AI 系統：

```text
Rule First
AI Second
```

---

## 理解

Rule Engine：

```text
不是處理資料
而是：
理解資料
```

---

# Day 19
# Intelligence Engine + Debugger World

---

# 1. Intelligence Engine

建立：

```python
services/intelligence_engine.py
```

功能：

- 成本占比分析
- 異常分析
- 成本結構分析

---

## 理解

開始從：

```text
Data Processing
```

進入：

```text
Business Intelligence
```

---

# 2. 數據完整性問題（重要）

第一次測試時：

```json
total_amount = 0
```

---

## AI 指導

AI 分析指出：

問題不是：

```text
代碼錯誤
```

而是：

```text
Excel 缺少 unit_price
```

---

## 理解

開始真正理解：

```text
Data Completeness
數據完整性
```

---

## 理解

真正 BI 系統：

```text
Garbage In
Garbage Out
```

---

# 3. VS Code Engineering Workflow

建立：

- Python Debugger
- Pylance
- Breakpoint
- Variable Observation
- Call Stack

---

# 4. launch.json

建立：

```json
FastAPI Debug
```

配置。

---

# 5. Breakpoint Understanding（重要）

第一次 breakpoint：

```python
df = pd.read_excel(file_path)
```

時：

```text
VARIABLES
沒有 df
```

---

## AI 指導（重要）

AI 指出：

```text
Breakpoint 停下時，
該行還沒執行。
```

因此：

```python
df
```

尚未建立。

---

## 理解

開始真正理解：

```text
變量生命周期
```

以及：

```text
Runtime State
```

---

# 6. 第一次真正觀察 Data Pipeline（重要）

完整 Debug：

```text
Excel
↓
DataFrame
↓
dict records
↓
normalized_row
↓
Rule Engine
↓
Intelligence Engine
↓
FastAPI JSON response
```

---

# 7. 最大突破（非常重要）

之前：

```text
只能“讀代碼”
```

現在：

```text
能真正“觀察程序運行”
```

---

# 8. 第一次真正理解：

- DataFrame
- row
- dict
- normalized_row
- append()
- import chain
- Call Stack

---

# 9. 對 Debugger 的理解（重要）

Debugger：

```text
不是：
找 bug 工具
```

而是：

```text
程序世界觀測器
```

---

# 10. 最大收穫（非常重要）

第一次真正建立：

```text
數據在內存中的流動感
```

---

## 理解

之前：

```text
dict 是抽象概念
```

現在：

```text
dict 開始“活起來”
```

---

# Current Understanding｜目前理解層級

目前已開始接觸：

- Backend Engineering
- Data Engineering
- ETL Thinking
- Rule Engine
- Business Intelligence
- Debug Workflow
- Runtime State
- Data Flow Thinking

---

# Current Weaknesses｜目前弱點

仍需加強：

- Python syntax fluency
- async understanding
- deployment engineering
- SQL optimization
- advanced pandas

---

# Most Important Insight｜目前最大收穫

真正工程能力：

```text
不是：
背語法
```

而是：

```text
觀察：
數據如何在程序世界中流動
```

---

# Long-term Direction｜長期方向

目標不是：

```text
普通 Python 程式員
```

而是：

```text
Construction Business Intelligence Engineer
```

核心方向：

- Backend Engineering
- Data Engineering
- Business Intelligence
- AI System Architecture