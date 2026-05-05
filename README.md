# 🏗️ AI Construction Management System（AI 建築管理系統）

---

## 📌 Project Overview｜專案簡介

This project is a backend system built with:

本專案基於以下技術構建：

```text id="1a1"
FastAPI + PostgreSQL + (Optional) AI Integration
```

---

### Purpose｜目標

```text id="1a2"
✔ Transform construction business logic into structured systems  
✔ 將建築業務邏輯轉換為結構化系統  

✔ Build scalable API architecture  
✔ 建立可擴展的 API 架構  

✔ Enable cost & profit analysis  
✔ 支持成本與利潤分析  

✔ Build decision-support capabilities  
✔ 建立決策支持能力  

✔ Prepare structured data for AI  
✔ 為 AI 提供高質量結構化數據  
```

---

## 🎯 Project Positioning｜專案定位

```text id="1a3"
Tool API → Decision System  
工具型API → 決策系統
```

---

## 🧭 System Evolution｜系統演進

```text id="1a4"
Day1–5   → CRUD  
Day6–9   → API standardization  
Day10    → AI integration  
Day11    → Portfolio analysis  
Day12    → Cost breakdown  
Day13    → Health scoring system  

CRUD → API → 分析 → 結構 → 多專案 → 決策系統
```

---

## 🧠 Architecture｜系統架構

```text id="1a5"
Database Layer → PostgreSQL（SQL）
Logic Layer    → FastAPI（Python）
Semantic Layer → AI（Optional）

資料層 → SQL  
邏輯層 → Python  
語意層 → AI（可選）
```

---

## ⚠️ AI Design Principle｜AI設計原則

```text id="1a6"
✔ SQL = Calculation  
✔ Python = Logic  
✔ AI = Interpretation  

✔ SQL 負責計算  
✔ Python 負責邏輯  
✔ AI 負責解讀  

❌ AI 不應替代計算
```

---

## 📂 Project Structure｜專案結構

```text id="1a7"
ai-system/
├── main.py
├── db.py
├── ai_analysis.py
├── README.md
├── LEARNING.md
├── .env              (NOT committed)
├── .env.example
├── .gitignore
├── __pycache__/      (ignored)
├── .vscode/          (ignored)
```

---

## 🔐 Environment & Security｜環境與安全

```text id="1a8"
OPENAI_API_KEY=your_api_key
```

---

### Rules｜規範

```text id="1a9"
✔ Never commit .env  
✔ 不提交 .env  

✔ Use .gitignore  
✔ 使用 .gitignore  

✔ Use .env.example  
✔ 提供範例文件  

✔ No hardcoded keys  
✔ 不寫死 API key  
```

---

## 🚀 API Overview｜API總覽

---

### Project Management｜專案管理

```text id="1a10"
POST /projects  
GET  /projects
```

---

### Cost Management｜成本管理

```text id="1a11"
人工費 / 材料費 / 機械費
Labor / Material / Equipment
```

---

### Analysis｜基礎分析

```text id="1a12"
GET /analysis
```

---

### Profit｜利潤分析

```text id="1a13"
GET /project-profit/{id}
GET /project-profit-join/{id}
```

---

### Portfolio Analysis｜多專案分析

```text id="1a14"
GET /projects/portfolio-analysis
```

---

### Cost Breakdown｜成本分類

```text id="1a15"
GET /project-cost-breakdown/{id}
```

---

### ⭐ Portfolio Health｜健康度分析

```text id="1a16"
GET /projects/portfolio-health
```

---

## 📊 Portfolio Health Model｜健康度模型

---

### Cost Ratio｜成本率

```text id="1a17"
cost_ratio = total_cost / budget
```

---

### Scoring｜評分模型

```text id="1a18"
< 0.6   → Healthy / 健康  
0.6–0.8 → Normal / 正常  
0.8–1.0 → Warning / 警告  
> 1.0   → Dangerous / 危險  
```

---

## 🧠 Data Transformation｜數據重構（核心）

---

### SQL（Flat）

```text id="1a19"
(1, 人工費, 100000)
(1, 材料費, 120000)
```

---

### Python（Structured）

```python id="1a20"
cost_map = {
    1: {
        "人工費": 100000,
        "材料費": 120000
    }
}
```

---

### Key Logic｜核心代碼

```python id="1a21"
cost_map[pid][ctype] = amount
```

---

## ⚠️ SQL Rules｜SQL設計原則

```text id="1a22"
SQL structure → string building  
SQL結構 → 拼接  

Values → parameterized (%s)  
數據值 → %s  
```

---

## 🧪 Testing Strategy｜測試數據

```text id="1a23"
✔ Normal case  
✔ 正常  

✔ Boundary case  
✔ 邊界  

✔ Failure case  
✔ 異常  

✔ Business scenario  
✔ 業務場景  
```

---

## ⚙️ Run｜運行方式

```bash id="1a24"
venv\Scripts\activate
pip install fastapi psycopg2-binary openai python-dotenv
uvicorn main:app --reload
```

---

## 🔗 Docs｜接口文檔

```text id="1a25"
http://127.0.0.1:8000/docs
```

---

## 📈 Capabilities｜能力總結

```text id="1a26"
✔ API design  
✔ SQL aggregation  
✔ Data modeling  
✔ Portfolio analysis  
✔ Cost structure analysis  
✔ Decision scoring  
✔ Secure config  
```

---

## 🔮 Next｜下一步

```text id="1a27"
Day14 → AI-generated report  
Day15 → Business simulation  
Day20 → System refactor  
```

---

## 🎯 Final Insight｜最終定位

```text id="1a28"
You are NOT writing APIs  
You are building a decision system  

你不是在寫API  
你在構建決策系統
```
