# AI 建築管理系統（AI Construction Management System）

## 📌 專案簡介

本專案使用 FastAPI + PostgreSQL 建立一個模擬建築專案管理系統。

目標：

* 建立資料模型（專案 / 成本）
* 完成資料分析（預算 / 成本 / 利潤）
* 提升 API 設計能力
* 為 AI 分析做準備

---

## 🚀 功能進度（Day 1 - Day 7）

### 1️⃣ 專案管理

* POST /projects
* GET /projects

---

### 2️⃣ 數據分析

* GET /analysis
* 支援 SUM / AVG / COUNT

---

### 3️⃣ 成本系統

* projects（主表）
* costs（子表）
* 一對多關係

---

### 4️⃣ 成本統計

* GET /project-cost/{project_id}

---

### 5️⃣ 利潤分析（Python）

* GET /project-profit/{project_id}

---

### 6️⃣ 利潤分析（JOIN）

* GET /project-profit-join/{project_id}

---

### 7️⃣ 成本明細（新增 ⭐）

* GET /project-cost-detail/{project_id}

#### 回傳格式：

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

## 🧠 技術重點

### fetchone vs fetchall

```text
fetchone → 單筆資料
fetchall → 多筆資料（list）
```

---

### JOIN 查詢（核心）

```sql
SELECT 
    p.id,
    p.budget,
    COALESCE(SUM(c.amount), 0) AS total_cost
FROM projects p
LEFT JOIN costs c ON p.id = c.project_id
GROUP BY p.id;
```

---

### API 設計升級

```text
✔ 扁平 → 結構化（dict）
✔ 單值 → 列表（list）
```

---

## 📂 專案結構

```
ai-system/
├── main.py
├── db.py
├── README.md
├── LEARNING.md
```

---

## ⚙️ 執行方式

```bash
venv\Scripts\activate
pip install fastapi[standard] psycopg2-binary
uvicorn main:app --reload
```

---

## 🔗 API 文件

http://127.0.0.1:8000/docs

---

## 🔮 下一步

* 查詢參數（filter）
* 分頁（pagination）
* API 標準化
* AI 分析功能
