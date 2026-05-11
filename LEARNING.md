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
Business Data Structure
```

開始理解：

- Request / Response
- SQL basics
- Backend fundamentals

---

# Day 6–10
# 成本分析系統

---

## 建立內容

- projects table
- costs table
- 成本分析 API

---

## 學習內容

- SQL JOIN
- GROUP BY
- SUM()
- COALESCE()

---

## 理解

資料庫並不是：

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
- data mapping
- structured business data

---

# Day 14–15
# AI Integration

---

## 建立

- OpenAI API integration
- AI 成本分析

---

## 學習

- .env
- API Key
- Environment Variables

---

## 理解

真正工程：

```text
不會把秘密寫死在代碼裡
```

---

# Day 16–17
# Data Engineering + Architecture Refactor

---

## 1. Excel Data Normalization

發現：

中國建築業 Excel：

- 簡繁混用
- 命名混亂
- 欄位不統一

例如：

```text
清單項目
清单项目名称
項目名稱
名称
```

因此建立：

```python
COLUMN_MAPPING
```

---

## 理解

```text
外部資料混亂，
系統內部必須統一。
```

---

# 2. ETL Thinking

開始理解：

```text
Extract
Transform
Load
```

---

## Pipeline

```text
Excel
↓
DataFrame
↓
dict
↓
normalized dict
↓
business logic
↓
AI analysis
```

---

# 3. dict.items()

錯誤：

```python
row.item()
```

正確：

```python
row.items()
```

---

## 理解

```python
for key, value in row.items()
```

本質：

```text
遍歷 dict key-value pair
```

---

# 4. Engineering Refactor

開始從：

```text
Single File Script
```

轉向：

```text
Layered Backend Architecture
```

---

## 建立

```text
api/
services/
utils/
models/
```

---

# 5. Engineering Thinking

---

## main.py

不是：

```text
做業務
```

而是：

```text
組裝系統
```

---

## api/

負責：

```text
HTTP Layer
```

---

## services/

負責：

```text
Business Logic
```

---

## utils/

負責：

```text
Infrastructure
```

---

# 6. Import Chain Understanding

開始理解：

```text
main.py
↓
api
↓
service
↓
utils
↓
db
```

---

## 理解

```python
import
```

不是單純引用。

而是：

```text
整個文件都會執行
```

---

# 7. Git Engineering

學習：

- .gitignore
- archive/
- repository hygiene

---

## 理解

Git：

```text
不是備份
而是版本演進系統
```

---

# Current Understanding｜目前理解層級

目前已開始接觸：

- Backend Engineering
- Data Engineering
- AI Integration
- Layered Architecture
- Data Normalization
- ETL Thinking

---

# Current Weaknesses｜目前弱點

仍需加強：

- dict intuition
- async understanding
- SQL optimization
- deployment engineering
- Python fluency

---

# Most Important Insight｜目前最大收穫

真正企業 AI 系統：

```text
不是：
AI 聊天

而是：

資料結構
+
規則系統
+
AI
```

---

# Long-term Direction｜長期方向

目標不是：

```text
普通 Python 程式員
```

而是：

```text
懂建築業務的 AI 系統工程方向
```

核心能力：

- Construction Business
- Backend Engineering
- Data Engineering
- AI Business System