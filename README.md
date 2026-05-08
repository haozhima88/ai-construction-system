# 🏗️ AI Construction Management System

# 🏗️ AI 建築管理系統

---

# 📌 Project Overview｜專案概覽

This project is an AI-assisted backend system focused on construction cost management, portfolio analysis, and bidding decision support.

本專案是一套以建築成本管理、多專案分析與投標決策支持為核心的 AI 輔助後端系統。

Core technologies：

核心技術：

```text id="r15_1"
FastAPI + PostgreSQL + Python + AI Integration
```

---

# 🎯 Project Goals｜專案目標

```text id="r15_2"
✔ Transform construction business logic into structured systems
✔ 將建築業務邏輯轉化為結構化系統

✔ Build scalable backend APIs
✔ 建立可擴展後端 API

✔ Build portfolio & bidding analysis capabilities
✔ 建立多專案與投標分析能力

✔ Combine SQL + Python + AI into one workflow
✔ 將 SQL + Python + AI 整合為完整工作流

✔ Create AI-assisted decision systems
✔ 建立 AI 輔助決策系統
```

---

# 🧭 System Evolution｜系統演進

```text id="r15_3"
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
Portfolio Health Scoring

Day14
AI-generated Management Reports

Day15
AI-assisted Bid Decision System
```

---

# 🧠 System Architecture｜系統架構

```text id="r15_4"
Database Layer
PostgreSQL + SQL

Logic Layer
FastAPI + Python

Business Layer
Portfolio / Cost / Bid Analysis

Decision Layer
Rule-based Scoring

Semantic Layer
AI-generated Reports & Suggestions
```

---

# ⚠️ AI Design Principles｜AI 設計原則

```text id="r15_5"
✔ SQL handles calculations
✔ SQL 負責計算

✔ Python handles logic and structure
✔ Python 負責邏輯與資料結構

✔ Rule system handles decisions
✔ 規則系統負責決策

✔ AI handles interpretation & reporting
✔ AI 負責解讀與報告

❌ AI should NOT replace deterministic calculations
❌ AI 不應替代確定性邏輯
```

---

# 📂 Project Structure｜專案結構

```text id="r15_6"
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

```env id="r15_7"
OPENAI_API_KEY=your_api_key
```

---

## Security Rules｜安全規範

```text id="r15_8"
✔ Never commit .env
✔ 不提交 .env

✔ Use .gitignore
✔ 使用 .gitignore

✔ Avoid hardcoded secrets
✔ 避免硬編碼敏感資訊

✔ Use .env.example
✔ 使用 .env.example
```

---

# 🚀 API Overview｜API 功能總覽

---

# 1️⃣ Project Management｜專案管理

```text id="r15_9"
POST /projects
GET  /projects
```

---

# 2️⃣ Cost Management｜成本管理

Supported categories：

支持分類：

```text id="r15_10"
人工費｜Labor
材料費｜Material
機械費｜Equipment
```

Relationship：

```text id="r15_11"
One Project → Many Costs
一個專案 → 多筆成本
```

---

# 3️⃣ Basic Analysis｜基礎分析

```text id="r15_12"
GET /analysis
```

Functions：

```text id="r15_13"
✔ Total budget
✔ Average budget
✔ Project count
```

---

# 4️⃣ Profit Analysis｜利潤分析

```text id="r15_14"
GET /project-profit/{id}
GET /project-profit-join/{id}
```

---

# 5️⃣ Cost Detail｜成本明細

```text id="r15_15"
GET /project-cost-detail/{id}
```

---

# 6️⃣ Filtering & Pagination｜篩選與分頁

```text id="r15_16"
GET /projects/filter
GET /projects/page
GET /projects/search
```

---

# 7️⃣ Portfolio Analysis｜多專案分析

```text id="r15_17"
GET /projects/portfolio-analysis
```

Provides：

```text id="r15_18"
✔ Multi-project comparison
✔ Profit ranking
✔ Cost ratio analysis
```

---

# 8️⃣ Cost Breakdown｜成本結構分析

```text id="r15_19"
GET /project-cost-breakdown/{id}
```

Provides：

```text id="r15_20"
✔ Cost grouping
✔ Ratio analysis
✔ Highest-cost category detection
```

---

# 9️⃣ Portfolio Health System｜健康度分析系統

```text id="r15_21"
GET /projects/portfolio-health
```

---

## Health Formula｜健康度公式

```text id="r15_22"
cost_ratio = total_cost / budget
```

---

## Health Scoring｜健康度評分

```text id="r15_23"
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

```text id="r15_24"
GET /projects/portfolio-report
```

Workflow：

```text id="r15_25"
SQL
↓
Python Structure
↓
Portfolio Analysis
↓
Prompt Construction
↓
AI-generated Report
```

---

# 1️⃣1️⃣ ⭐ Bid Decision System｜投標決策系統（Day15 核心）

```text id="r15_26"
GET /projects/bid-decision/{project_id}
```

---

# 🎯 Purpose｜目標

```text id="r15_27"
✔ Determine whether a project should be bid
✔ 判斷是否應投標

✔ Analyze project risk
✔ 分析專案風險

✔ Evaluate profitability
✔ 評估利潤

✔ Detect abnormal cost structures
✔ 發現異常成本結構

✔ Generate AI-assisted bidding suggestions
✔ AI 輔助投標建議
```

---

# 🧠 Core Principle｜核心原則

```text id="r15_28"
Rules first
AI second

規則優先
AI其次
```

---

# 📊 Bid Decision Logic｜投標決策邏輯

---

## Cost Ratio｜成本率

```text id="r15_29"
cost_ratio < 0.7
→ Excellent｜優秀

0.7–0.9
→ Acceptable｜正常

> 0.9
→ High Risk｜高風險
```

---

## Profit Analysis｜利潤分析

```text id="r15_30"
profit > 100000
→ Good Profit｜利潤良好

profit < 0
→ Reject｜禁止投標
```

---

## Material Ratio｜材料占比

```text id="r15_31"
material_ratio > 0.6
→ Material Risk｜材料風險
```

---

# 🤖 AI Responsibilities｜AI 職責

```text id="r15_32"
✔ Explain decisions
✔ 解釋決策

✔ Identify risks
✔ 識別風險

✔ Generate bidding strategies
✔ 生成投標策略

✔ Produce management-level reports
✔ 生成管理層報告
```

---

# 🧠 Data Flow｜資料流（重要）

```text id="r15_33"
SQL
↓
tuple
↓
Python variables
↓
dict
↓
list.append()
↓
JSON
↓
AI
```

---

# 🧠 Data Transformation｜數據重構

---

## SQL Output

```text id="r15_34"
(1, '住宅A', 300000, 160000, 140000)
```

---

## Python Structure

```python id="r15_35"
{
    "project_id": 1,
    "name": "住宅A"
}
```

---

## Grouped Structure

```python id="r15_36"
results = [
    {...},
    {...}
]
```

---

# ⚠️ Important Debugging Lessons｜重要 Debug 經驗

---

## Python Indentation

```text id="r15_37"
Indentation = Program structure

縮排 = 程式結構
```

---

## Common Mistake

```text id="r15_38"
append outside loop
→ only one result

append 在 loop 外
→ 只會保留一筆
```

---

## Debug Thinking

```text id="r15_39"
Check:
✔ SQL result
✔ Python variables
✔ loop scope
✔ append position
✔ return position
```

---

# ⚙️ Run Project｜運行方式

```bash id="r15_40"
venv\Scripts\activate

pip install fastapi[standard]
pip install psycopg2-binary
pip install python-dotenv
pip install openai

uvicorn main:app --reload
```

---

# 🔗 Swagger API Docs｜接口文檔

```text id="r15_41"
http://127.0.0.1:8000/docs
```

---

# 📈 Current Capabilities｜目前能力

```text id="r15_42"
✔ API Design
✔ SQL Aggregation
✔ Portfolio Analysis
✔ Cost Structure Analysis
✔ Health Scoring
✔ Bid Decision Logic
✔ AI-generated Reports
✔ Rule-based Systems
✔ Data Reshaping
✔ Backend Debugging
✔ Environment Management
```

---

# 🔮 Next Stage｜下一階段

```text id="r15_43"
Day16
Excel Import System

Day17
Bid Item Parsing

Day18
Cost Benchmark Database

Day19
Historical Trend Analysis

Day20+
Low-code System Refactor
```

---

# 🎯 Final Positioning｜最終定位

```text id="r15_44"
This is NOT just a backend API project.

It is an AI-assisted construction business decision system.

這不只是後端 API 專案。

而是一套 AI 輔助建築業務決策系統。
```
