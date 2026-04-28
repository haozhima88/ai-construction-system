# AI 建築管理系統（AI Construction Management System）

## 📌 專案簡介

本專案基於 FastAPI + PostgreSQL 開發，用於模擬建築企業中的專案管理系統。

目標：

* 建立專案與成本數據模型
* 實現數據分析與業務計算
* 培養 API + SQL + 系統設計能力
* 為 AI 應用打下基礎

---

## 🚀 已實現功能（Day 1 - Day 6）

### 1️⃣ 專案管理

* POST /projects
* GET /projects

---

### 2️⃣ 數據分析

* GET /analysis

支援：

* SUM / AVG / COUNT

---

### 3️⃣ 成本系統（多表）

* projects（主表）
* costs（子表）
* 一對多關係（project → costs）

---

### 4️⃣ 成本統計

* GET /project-cost/{project_id}

---

### 5️⃣ 利潤分析（Python計算）

* GET /project-profit/{project_id}

---

### 6️⃣ 利潤分析（JOIN優化）⭐

* GET /project-profit-join/{project_id}

---

## 🧠 核心技術重點

### SQL JOIN（核心能力）

```sql id="sql_join_readme"
SELECT 
    p.id,
    p.budget,
    COALESCE(SUM(c.amount), 0) AS total_cost,
    p.budget - COALESCE(SUM(c.amount), 0) AS profit
FROM projects p
LEFT JOIN costs c ON p.id = c.project_id
GROUP BY p.id;
```

---

### cursor.execute 使用方式

#### 簡單查詢

```python id="simple_exec"
cursor.execute("SELECT * FROM projects")
```

#### 複雜查詢（推薦）

```python id="multi_exec"
cursor.execute("""
    SELECT ...
    FROM ...
    JOIN ...
""")
```

---

## 🧠 技術棧

* Python
* FastAPI
* PostgreSQL
* psycopg2

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

```bash id="run_cmd"
venv\Scripts\activate
pip install fastapi[standard] psycopg2-binary
uvicorn main:app --reload
```

---

## 🔗 API 文件

http://127.0.0.1:8000/docs

---

## 📈 學習進度

* Day 1：API
* Day 2：資料庫
* Day 3：統計
* Day 4：多表
* Day 5：業務邏輯（利潤）
* Day 6：JOIN優化（核心能力）

---

## 🔮 下一步

* 成本明細 API
* 返回結構優化
* API 設計進階
* AI 數據分析
