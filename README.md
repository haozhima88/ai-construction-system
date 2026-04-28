# AI 建築管理系統（AI Construction Management System）

## 📌 專案簡介

本專案基於 FastAPI + PostgreSQL 開發，用於模擬建築企業中的專案管理系統。

核心目標：

* 建立專案與成本數據模型
* 實現資料分析與業務計算
* 為未來 AI 分析能力做準備

---

## 🚀 已實現功能（Day 1 - Day 5）

### 1️⃣ 專案管理

* 建立專案（POST /projects）
* 查詢專案（GET /projects）

---

### 2️⃣ 數據分析

* GET /analysis

支援：

* 總預算（SUM）
* 平均預算（AVG）
* 專案數量（COUNT）

---

### 3️⃣ 成本系統（多表結構）

* 建立 costs 表
* 一個專案對應多筆成本資料

#### 成本欄位

* project_id（外鍵）
* cost_type（成本類型）
* amount（金額）

---

### 4️⃣ 成本統計

* GET /project-cost/{project_id}

---

### 5️⃣ 利潤分析（核心業務）

* GET /project-profit/{project_id}

計算邏輯：

```text
利潤 = 預算 - 成本
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
```

---

## ⚙️ 執行方式

```bash
# 啟動虛擬環境
venv\Scripts\activate

# 安裝依賴
pip install fastapi[standard] psycopg2-binary

# 啟動服務
uvicorn main:app --reload
```

---

## 🔗 API 文件

http://127.0.0.1:8000/docs

---

## 🗄️ 資料庫設計

### projects 表

* id（主鍵）
* name
* budget

### costs 表

* id（主鍵）
* project_id（外鍵）
* cost_type
* amount

---

## 📈 學習進度

* Day 1：FastAPI 基礎
* Day 2：資料庫接入
* Day 3：數據分析（SUM / AVG / COUNT）
* Day 4：多表關聯（projects + costs）
* Day 5：利潤計算（業務邏輯）

---

## 🔮 下一步規劃

* JOIN 優化查詢
* 成本明細接口
* API 結構優化
* AI 輔助分析（未來）
