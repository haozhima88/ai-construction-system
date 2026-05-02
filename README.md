# 🏗️ AI 建築管理系統（AI Construction Management System）

---

## 📌 專案簡介

本專案基於 **FastAPI + PostgreSQL + AI（可選）** 建立一套建築專案管理與分析系統。

核心目標：

```text
✔ 將建築業務數據結構化
✔ 建立可擴展 API 系統
✔ 實現成本與利潤分析
✔ 引入 AI 作為決策輔助（非核心依賴）
```

---

## 🎯 專案定位

```text
業務 + 系統 + AI 整合能力實驗
```

---

## 🚀 功能總覽（Day1–Day11）

---

### 1️⃣ 專案管理（Projects）

```text
POST /projects
GET /projects
```

---

### 2️⃣ 成本管理（Costs）

* 一對多關係（Project → Costs）
* 支援成本分類（人工 / 材料 / 機械）

---

### 3️⃣ 基礎數據分析

```text
GET /analysis
```

支援：

```text
✔ SUM（總預算）
✔ AVG（平均預算）
✔ COUNT（專案數量）
```

---

### 4️⃣ 利潤分析

```text
GET /project-profit/{project_id}
GET /project-profit-join/{project_id}
```

---

### 5️⃣ 成本明細（結構化輸出）

```text
GET /project-cost-detail/{project_id}
```

---

### 6️⃣ 查詢與分頁（企業級 API）

```text
GET /projects/filter
GET /projects/page
GET /projects/search
```

---

### 7️⃣ API 標準化（Day9）

```text
✔ Pydantic（response_model）
✔ HTTPException
✔ 結構統一
```

---

### 8️⃣ AI 分析（Day10｜可選）

```text
GET /project-analysis/{project_id}
```

---

### 9️⃣ ⭐ 多專案分析（Day11 核心）

```text
GET /projects/portfolio-analysis
```

---

## 📊 Portfolio Analysis（核心能力）

---

### 功能

```text
✔ 多專案總覽
✔ 成本 / 利潤計算
✔ 成本率（Cost Ratio）
✔ 排序（最賺 / 最虧）
```

---

### 成本率公式

```text
cost_ratio = total_cost / budget
```

---

### 解讀標準

```text
< 0.6 → 健康
0.6–0.8 → 注意
> 0.8 → 高風險
> 1 → 虧損
```

---

### API 範例

```text
/projects/portfolio-analysis?sort=profit_desc
```

---

### 回傳範例

```json
{
  "count": 3,
  "projects": [
    {
      "id": 1,
      "name": "項目A",
      "budget": 300000,
      "total_cost": 250000,
      "profit": 50000,
      "cost_ratio": 0.83
    }
  ]
}
```

---

## 🧠 系統架構（關鍵）

```text
資料層 → PostgreSQL
邏輯層 → FastAPI
語意層 → AI（可選）
```

---

## ❗ AI 使用原則

```text
✔ AI 負責「解讀」
✔ SQL 負責「計算」
✔ Python 負責「邏輯」
```

---

## 🔐 環境變數與安全

---

### .env 設定

```text
OPENAI_API_KEY=your_api_key
```

---

### 安全規範

```text
✔ .env 不可上傳
✔ 已加入 .gitignore
✔ 使用 .env.example
```

---

## ⚠️ SQL 設計注意（Day11 關鍵）

---

### ❌ 錯誤

```text
ORDER BY = %s
```

---

### ✅ 正確

```text
使用白名單 + SQL 拼接
```

---

### 原則

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
✔ SQL（JOIN / 聚合）
✔ 分頁與查詢
✔ 資料建模（Pydantic）
✔ 多專案分析
✔ AI 接入（可選）
✔ 環境與安全管理
```

---

## 🔮 下一步

```text
✔ 成本分類分析（Day12）
✔ AI 報告生成
✔ Excel / 招標系統整合
```

---

## 🎯 專案價值

```text
從「寫 API」
→ 到「建系統」
→ 到「做決策分析」
```
