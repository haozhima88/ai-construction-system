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

## 🎯 專案定位（非常重要）

本專案不是單純後端練習，而是：

```text
「業務 + 系統 + AI」整合實驗
```

---

## 🚀 已實現功能（Day 1 - Day 10）

---

### 1️⃣ 專案管理（Projects）

* 建立專案
* 查詢專案

```text
POST /projects
GET /projects
```

---

### 2️⃣ 成本系統（Costs）

* 一對多關係（project → costs）
* 成本分類（人工 / 材料 / 機械）

---

### 3️⃣ 數據分析（Analysis）

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

### 4️⃣ 利潤分析（Profit）

#### Python 計算

```text
GET /project-profit/{project_id}
```

#### SQL JOIN 優化（核心能力）

```text
GET /project-profit-join/{project_id}
```

---

### 5️⃣ 成本明細（結構化輸出）

```text
GET /project-cost-detail/{project_id}
```

回傳：

```json
{
  "project_id": 1,
  "costs": [
    {"type": "人工費", "amount": 100000},
    {"type": "材料費", "amount": 80000}
  ]
}
```

---

### 6️⃣ 查詢與分頁（企業級 API）

#### 篩選（Filter）

```text
GET /projects/filter?min_budget=100000
```

#### 分頁（Pagination）

```text
GET /projects/page?limit=10&offset=0
```

#### 查詢 + 分頁

```text
GET /projects/search?min_budget=100000&limit=10&offset=0
```

---

### 7️⃣ API 標準化（Day 9）

* 使用 Pydantic（response_model）
* 統一資料格式
* HTTPException 錯誤處理

---

### 8️⃣ AI 分析（Day 10，選用）

```text
GET /project-analysis/{project_id}
```

功能：

```text
✔ 自動計算（預算 / 成本 / 利潤）
✔ 規則判斷（正常 / 偏高 / 虧損）
✔ AI 自然語言分析（可選）
```

---

## 🧠 系統架構設計（核心價值）

```text
資料層（SQL） → PostgreSQL
邏輯層（Python） → FastAPI
語意層（AI） → OpenAI API
```

---

## ❗ AI 設計原則（非常關鍵）

```text
✔ AI = 解讀層（Interpretation）
✔ SQL = 計算
✔ Python = 邏輯
```

---

## 🔐 環境變數與安全

### 使用 `.env`

```text
OPENAI_API_KEY=your_api_key
```

---

### 安全規範

```text
✔ .env 已加入 .gitignore
✔ 不可上傳 GitHub
✔ 使用 .env.example 提供範本
```

---

## 📂 專案結構

```
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

## 📊 技術能力總結

```text
✔ API 設計（FastAPI）
✔ SQL（JOIN / 聚合）
✔ 資料建模（Pydantic）
✔ 分頁 / 查詢設計
✔ AI 接入（OpenAI）
✔ 環境與安全管理
```

---

## 🔮 未來規劃

```text
✔ 多專案比較分析
✔ 自動報告生成（AI）
✔ 成本優化建議系統
✔ Excel / 招標系統整合
```

---

## 🎯 專案價值

```text
從「會寫程式」
→ 到「設計業務系統」
→ 到「AI賦能決策」
```
