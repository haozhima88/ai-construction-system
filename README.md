# 🏗️ AI 建築管理系統（AI Construction Management System）

---

## 📌 專案簡介

本專案基於 **FastAPI + PostgreSQL + AI（可選）** 建立一套建築專案管理與成本分析系統。

核心目標：

```text
✔ 將建築業務數據結構化
✔ 建立可擴展 API 系統
✔ 支持成本與利潤分析
✔ 為 AI 決策提供數據基礎
```

---

## 🎯 專案定位

```text
業務 + 系統 + AI 的整合實驗
```

---

## 🚀 功能總覽（Day1–Day12）

---

### 1️⃣ 專案管理

```text
POST /projects
GET /projects
```

---

### 2️⃣ 成本管理

* 一對多關係（Project → Costs）
* 支援成本分類（人工 / 材料 / 機械）

---

### 3️⃣ 基礎數據分析

```text
GET /analysis
```

支援：

```text
✔ 總預算（SUM）
✔ 平均預算（AVG）
✔ 專案數量（COUNT）
```

---

### 4️⃣ 利潤分析

```text
GET /project-profit/{project_id}
GET /project-profit-join/{project_id}
```

---

### 5️⃣ 成本明細

```text
GET /project-cost-detail/{project_id}
```

---

### 6️⃣ 查詢與分頁

```text
GET /projects/filter
GET /projects/page
GET /projects/search
```

---

### 7️⃣ API 標準化

```text
✔ Pydantic（response_model）
✔ HTTPException
✔ 結構統一
```

---

### 8️⃣ AI 分析（可選）

```text
GET /project-analysis/{project_id}
```

---

### 9️⃣ 多專案分析（Portfolio）

```text
GET /projects/portfolio-analysis
```

---

### 🔟 ⭐ 成本分類分析（Day12 核心）

```text
GET /project-cost-breakdown/{project_id}
```

---

## 📊 成本分類分析（Cost Breakdown）

---

### 功能

```text
✔ 按成本類型分類（人工 / 材料 / 機械）
✔ 計算各類成本總額
✔ 計算成本占比（ratio）
✔ 找出最高成本類型
```

---

### SQL 核心

```sql
SELECT 
    cost_type,
    SUM(amount)
FROM costs
WHERE project_id = %s
GROUP BY cost_type;
```

---

### 成本占比公式

```text
ratio = 某類成本 / 總成本
```

---

### 回傳範例

```json
{
  "project_id": 1,
  "total_cost": 250000,
  "breakdown": [
    {"type": "人工費", "amount": 100000, "ratio": 0.4},
    {"type": "材料費", "amount": 120000, "ratio": 0.48},
    {"type": "機械費", "amount": 30000, "ratio": 0.12}
  ],
  "highest_cost": {
    "type": "材料費",
    "amount": 120000
  }
}
```

---

## 🧠 系統能力演進

```text
Day1-5   → CRUD
Day6-9   → API + 結構化
Day10    → AI 接入
Day11    → 多專案分析
Day12    → 成本結構分析（核心）
```

---

## ❗ AI 設計原則

```text
✔ SQL → 計算
✔ Python → 邏輯
✔ AI → 解讀（非必需）
```

---

## 🔐 安全與環境變數

---

### .env

```text
OPENAI_API_KEY=your_api_key
```

---

### 規範

```text
✔ .env 不提交
✔ 使用 .gitignore
✔ 使用 .env.example
```

---

## ⚠️ SQL 設計原則

```text
SQL 結構 → 拼接
數據值 → %s
```

---

## 📂 專案結構

```text
ai-system/
├── main.py
├── ai_analysis.py
├── db.py
├── .env              ❌ 不提交
├── .env.example      ✔ 提交
├── .gitignore
├── README.md
├── LEARNING.md
```

---

## ⚙️ 執行方式

```bash
venv\Scripts\activate
pip install fastapi[standard] psycopg2-binary openai python-dotenv
uvicorn main:app --reload
```

---

## 🔗 API 文件

```text
http://127.0.0.1:8000/docs
```

---

## 📈 能力總結

```text
✔ API 設計
✔ SQL（JOIN / 聚合 / 分組）
✔ 分頁與查詢
✔ 資料建模（Pydantic）
✔ 多專案分析
✔ 成本結構分析
✔ AI 接入（可選）
✔ 安全與環境管理
```

---

## 🔮 下一步

```text
✔ 多專案成本對比（Day13）
✔ AI 報告生成
✔ 投標決策系統
✔ Excel / 招標數據整合
```

---

## 🎯 專案價值

```text
從「寫 API」
→ 到「建系統」
→ 到「做成本決策」
```
