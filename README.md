# AI 建築管理系統（AI Construction Management System）

## 📌 專案簡介

本專案使用 FastAPI + PostgreSQL 建立一個建築專案管理系統。

目標：

* 建立專案與成本資料模型
* 實現預算 / 成本 / 利潤分析
* 設計可擴展 API 結構
* 為 AI 分析能力做準備

---

## 🚀 功能進度（Day 1 - Day 8）

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

### 7️⃣ 成本明細 ⭐

* GET /project-cost-detail/{project_id}

---

### 8️⃣ 查詢與分頁（新增 ⭐⭐）

#### 查詢（Filter）

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

## 📊 API 回傳結構（升級）

```json
{
  "query": {
    "min_budget": 100000
  },
  "pagination": {
    "limit": 10,
    "offset": 0
  },
  "count": 2,
  "projects": [
    {"id": 1, "name": "A", "budget": 200000}
  ]
}
```

---

## 🧠 技術重點

### 1️⃣ fetchone vs fetchall

```text
fetchone → 單筆
fetchall → 多筆（list）
```

---

### 2️⃣ JOIN

```sql
LEFT JOIN costs ON p.id = c.project_id
```

---

### 3️⃣ COALESCE

```sql
COALESCE(SUM(amount), 0)
```

---

### 4️⃣ 分頁

```sql
LIMIT + OFFSET
```

---

### 5️⃣ API 設計

```text
✔ 使用 list 表示多筆資料
✔ 使用 dict 表示結構
✔ 加入 query / pagination metadata
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

## 🔮 下一步（Day 9）

* API 標準化（Response Model）
* 錯誤處理（HTTPException）
* AI 分析模組（開始引入）
