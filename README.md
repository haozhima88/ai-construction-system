# 🏗️ AI 建築管理系統（AI Construction Management System）

---

## 📌 專案簡介

本專案基於 **FastAPI + PostgreSQL + AI（可選）** 建立一套建築專案管理與成本分析系統。

核心目標：

```text id="d1qhz6"
✔ 將建築業務數據結構化
✔ 建立可擴展 API 系統
✔ 支持成本與利潤分析
✔ 建立決策支持能力（Portfolio Analysis）
✔ 為 AI 提供高質量結構化輸入
```

---

## 🎯 專案定位

```text id="d9nn6p"
從「工具型API」 → 「決策分析系統」
```

---

## 🚀 功能總覽（Day1–Day13）

---

### 1️⃣ 專案管理

```text id="uxt3zi"
POST /projects
GET /projects
```

---

### 2️⃣ 成本管理

* 一對多關係（Project → Costs）
* 成本分類（人工 / 材料 / 機械）

---

### 3️⃣ 基礎數據分析

```text id="udys0r"
GET /analysis
```

---

### 4️⃣ 利潤分析

```text id="a1cz2y"
GET /project-profit/{project_id}
GET /project-profit-join/{project_id}
```

---

### 5️⃣ 成本明細

```text id="76zlfh"
GET /project-cost-detail/{project_id}
```

---

### 6️⃣ 查詢與分頁

```text id="65haxw"
GET /projects/filter
GET /projects/page
GET /projects/search
```

---

### 7️⃣ API 標準化

```text id="b3l06u"
✔ Pydantic
✔ HTTPException
✔ 統一結構
```

---

### 8️⃣ AI 分析（可選）

```text id="3g2y1p"
GET /project-analysis/{project_id}
```

---

### 9️⃣ 多專案分析

```text id="s1ayf5"
GET /projects/portfolio-analysis
```

---

### 🔟 成本分類分析

```text id="b96dzf"
GET /project-cost-breakdown/{project_id}
```

---

### ⭐ 1️⃣1️⃣ 多專案健康度分析（Day13 核心）

```text id="1h8paf"
GET /projects/portfolio-health
```

---

## 📊 Portfolio Health（核心能力）

---

### 功能

```text id="96onzd"
✔ 多專案成本與利潤分析
✔ 成本率（Cost Ratio）
✔ 健康度評分（Score）
✔ 風險分層（健康 / 正常 / 警告 / 危險）
✔ 成本結構分析
```

---

### 健康度模型

```text id="r4i83r"
cost_ratio = total_cost / budget
```

---

### 評分標準

```text id="4qs7yr"
< 0.6  → 健康（90分）
0.6–0.8 → 正常（70分）
0.8–1.0 → 警告（50分）
> 1.0 → 危險（30分）
```

---

### 回傳範例

```json id="zz6exy"
{
  "count": 3,
  "projects": [
    {
      "project_id": 1,
      "name": "住宅A",
      "budget": 300000,
      "total_cost": 250000,
      "profit": 50000,
      "cost_ratio": 0.83,
      "health": "警告",
      "score": 50,
      "cost_breakdown": {
        "人工費": 100000,
        "材料費": 120000
      }
    }
  ]
}
```

---

## 🧠 系統架構（關鍵）

```text id="h6vij9"
資料層 → PostgreSQL（SQL）
邏輯層 → FastAPI（Python）
語意層 → AI（可選）
```

---

## 🔥 核心技術能力

```text id="j06pqs"
✔ SQL（JOIN / GROUP BY / 聚合）
✔ API 設計
✔ 分頁與查詢
✔ 成本分析建模
✔ Python 分組（cost_map）
✔ 決策模型（Scoring Model）
```

---

## ⚠️ SQL 設計原則

```text id="c6w1n3"
SQL結構 → 拼接
數據值 → %s
```

---

## 🧠 Python 分組（重要）

```text id="gqpx7h"
cost_map[project_id][cost_type] = amount
```

👉 用於：

```text id="a4k4p3"
將 SQL 平面數據轉為結構化數據
```

---

## 🔐 環境與安全

---

### .env

```text id="jb0p9k"
OPENAI_API_KEY=your_api_key
```

---

### 規範

```text id="h4xxy5"
✔ .env 不提交
✔ 使用 .gitignore
✔ .env.example
```

---

## 📂 專案結構

```text id="ht9kru"
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

```bash id="5lvnjf"
venv\Scripts\activate
pip install fastapi[standard] psycopg2-binary openai python-dotenv
uvicorn main:app --reload
```

---

## 📈 能力演進

```text id="6d6tx9"
CRUD → API → 分析 → 結構 → 多專案 → 決策系統
```

---

## 🔮 下一步

```text id="6a5vva"
✔ AI 管理報告生成（Day14）
✔ 投標分析模型
✔ Excel / 招標整合
```

---

## 🎯 專案價值

```text id="7zxaqr"
從「寫程式」
→ 到「建系統」
→ 到「做決策」
```
