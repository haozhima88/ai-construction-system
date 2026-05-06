# 🏗️ AI Construction Management System

# 🏗️ AI 建築管理系統

---

# 📌 Project Overview｜專案概覽

This project is a backend-oriented AI-assisted construction management system built with:

本專案是一套基於後端架構的 AI 輔助建築管理系統，核心技術包括：

```text
FastAPI + PostgreSQL + Python + AI Integration
```

The project simulates real-world construction management workflows including:

本專案模擬真實建築管理流程，包括：

```text
✔ Project Management｜專案管理
✔ Cost Management｜成本管理
✔ Profit Analysis｜利潤分析
✔ Portfolio Analysis｜多專案分析
✔ Health Scoring｜健康度評分
✔ AI-generated Management Reports｜AI 管理報告
```

---

# 🎯 Core Objectives｜核心目標

```text
✔ Transform construction business logic into structured systems
✔ 將建築業務邏輯轉換為結構化系統

✔ Build scalable backend APIs
✔ 建立可擴展後端 API

✔ Create decision-support capabilities
✔ 建立決策支持能力

✔ Combine SQL + Python + AI into one workflow
✔ 將 SQL + Python + AI 整合為完整工作流

✔ Prepare high-quality structured data for AI reasoning
✔ 為 AI 推理準備高質量結構化數據
```

---

# 🧭 System Evolution｜系統演進路線

```text
Day1–5
CRUD + Database + API Basics

Day6–9
Filtering + Pagination + API Standardization

Day10
AI Integration Layer

Day11
Portfolio Analysis

Day12
Cost Breakdown Analysis

Day13
Portfolio Health Scoring System

Day14
AI-generated Management Report System
```

---

# 🧠 System Architecture｜系統架構

```text
Database Layer
PostgreSQL + SQL

Logic Layer
FastAPI + Python

Analysis Layer
Portfolio / Cost / Health Analysis

Semantic Layer
AI-generated Reports & Suggestions
```

---

# ⚠️ AI Design Principles｜AI 設計原則

```text
✔ SQL handles calculations
✔ SQL 負責計算

✔ Python handles logic and structure
✔ Python 負責邏輯與結構

✔ AI handles interpretation and reporting
✔ AI 負責解讀與報告

❌ AI should NOT replace deterministic calculations
❌ AI 不應替代確定性計算
```

---

# 📂 Project Structure｜專案結構

```text
ai-system/
│
├── main.py
├── db.py
├── ai_analysis.py
│
├── README.md
├── LEARNING.md
│
├── .env
├── .env.example
├── .gitignore
│
├── __pycache__/      (ignored)
├── .vscode/          (ignored)
└── venv/             (ignored)
```

---

# 🔐 Environment & Security｜環境與安全

---

## Environment Variables｜環境變數

```env
OPENAI_API_KEY=your_api_key
```

---

## Security Rules｜安全規範

```text
✔ Never commit .env
✔ 不提交 .env

✔ Use .gitignore
✔ 使用 .gitignore

✔ Avoid hardcoded API keys
✔ 不寫死 API key

✔ Use .env.example
✔ 提供 .env.example
```

---

# 🚀 API Overview｜API 功能總覽

---

# 1️⃣ Project Management｜專案管理

```text
POST /projects
GET  /projects
```

Functions｜功能：

```text
✔ Create project
✔ 建立專案

✔ Retrieve projects
✔ 查詢專案
```

---

# 2️⃣ Cost Management｜成本管理

Supports cost categories：

支持成本分類：

```text
人工費｜Labor
材料費｜Material
機械費｜Equipment
```

Relationship：

```text
One Project → Many Costs
一個專案 → 多筆成本
```

---

# 3️⃣ Basic Analysis｜基礎分析

```text
GET /analysis
```

Provides：

```text
✔ SUM(budget)
✔ AVG(budget)
✔ COUNT(projects)
```

---

# 4️⃣ Profit Analysis｜利潤分析

```text
GET /project-profit/{id}
GET /project-profit-join/{id}
```

Calculates：

```text
Profit = Budget - Total Cost
利潤 = 預算 - 成本
```

---

# 5️⃣ Cost Detail｜成本明細

```text
GET /project-cost-detail/{id}
```

Returns structured cost items.

返回結構化成本明細。

---

# 6️⃣ Filtering & Pagination｜篩選與分頁

```text
GET /projects/filter
GET /projects/page
GET /projects/search
```

---

# 7️⃣ Portfolio Analysis｜多專案分析

```text
GET /projects/portfolio-analysis
```

Provides：

```text
✔ Multi-project comparison
✔ 多專案比較

✔ Cost ratio
✔ 成本率

✔ Profit ranking
✔ 利潤排序
```

---

# 8️⃣ Cost Breakdown｜成本結構分析

```text
GET /project-cost-breakdown/{id}
```

Provides：

```text
✔ Cost category grouping
✔ 成本分類統計

✔ Ratio calculation
✔ 占比計算

✔ Highest cost detection
✔ 最高成本識別
```

---

# 9️⃣ Portfolio Health System｜健康度分析系統

```text
GET /projects/portfolio-health
```

---

## Health Scoring Model｜健康度模型

```text
cost_ratio = total_cost / budget
```

---

## Scoring Rules｜評分規則

```text
< 0.6
Healthy｜健康

0.6–0.8
Normal｜正常

0.8–1.0
Warning｜警告

> 1.0
Dangerous｜危險
```

---

# 🔟 AI-generated Management Report｜AI 管理報告

```text
GET /projects/portfolio-report
```

---

## Workflow｜工作流

```text
SQL Data
↓
Python Structure
↓
Portfolio Analysis
↓
Prompt Construction
↓
AI Report Generation
```

---

## AI Responsibilities｜AI 職責

```text
✔ Summarize project status
✔ 總結專案狀態

✔ Identify risk
✔ 識別風險

✔ Generate management suggestions
✔ 生成管理建議

✔ Produce readable reports
✔ 生成可讀報告
```

---

# 🧠 Data Transformation（Critical）

# 🧠 數據重構（核心能力）

---

## SQL Output（Flat Structure）

```text
(1, 人工費, 100000)
(1, 材料費, 120000)
```

---

## Python Grouped Structure

```python
cost_map = {
    1: {
        "人工費": 100000,
        "材料費": 120000
    }
}
```

---

## Core Logic｜核心邏輯

```python
cost_map[pid][ctype] = amount
```

Meaning：

```text
Flat SQL data
→ Structured Python data

SQL 平面數據
→ Python 結構化數據
```

---

# ⚠️ SQL Design Rules｜SQL 設計原則

```text
✔ SQL structure → string building
✔ SQL結構 → 拼接

✔ Values → parameterized (%s)
✔ 數據值 → %s

❌ Never pass SQL syntax as parameters
❌ 不要將 SQL 語法作為參數
```

---

# 🧪 Testing Strategy｜測試策略

The system includes multiple business scenarios：

系統包含多種業務場景：

```text
✔ Healthy project｜健康專案
✔ Warning project｜警告專案
✔ Loss project｜虧損專案
✔ Material-heavy project｜材料異常專案
✔ Boundary cases｜邊界測試
```

---

# ⚙️ Run Project｜運行方式

```bash
venv\Scripts\activate

pip install fastapi[standard]
pip install psycopg2-binary
pip install python-dotenv
pip install openai

uvicorn main:app --reload
```

---

# 🔗 Swagger API Docs｜接口文檔

```text
http://127.0.0.1:8000/docs
```

---

# 📈 Current Capabilities｜目前能力

```text
✔ API Design
✔ API 設計

✔ SQL Aggregation & JOIN
✔ SQL 聚合與 JOIN

✔ Pagination & Filtering
✔ 分頁與篩選

✔ Data Modeling
✔ 數據建模

✔ Portfolio Analysis
✔ 多專案分析

✔ Cost Structure Analysis
✔ 成本結構分析

✔ Health Scoring
✔ 健康度評分

✔ AI-generated Reports
✔ AI 管理報告

✔ Data Reshaping
✔ 數據重構

✔ Environment Management
✔ 環境管理
```

---

# 🔮 Next Stage｜下一階段

```text
Day15
AI-assisted bidding simulation

Day16
Excel import system

Day17
Cost benchmark database

Day18
Historical trend analysis

Day20+
Low-code system refactor
```

---

# 🎯 Final Positioning｜最終定位

```text
This is NOT just an API project.

It is an AI-assisted business decision system.

這不只是 API 專案。

而是一套 AI 輔助業務決策系統。
```
