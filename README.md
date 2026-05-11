# AI Construction System
# AI 建築管理與成本分析系統

---

# 1. Project Overview｜專案概覽

AI Construction System 是一套基於：

- FastAPI
- PostgreSQL
- Pandas
- OpenAI / DeepSeek API
- Python 3.11

建立的：

```text
AI + Construction Business Backend System
```

本專案的核心方向不是：

```text
Chat AI Demo
```

而是：

```text
Construction Business Intelligence System
```

目標是：

> 將中國建築行業中大量混亂、半結構化的 Excel / 招標清單資料，
> 轉換為可分析、可管理、可 AI 化的結構化業務系統。

---

# 2. Core Direction｜核心方向

本專案聚焦於：

- Construction Cost Analysis
- Excel Bid Processing
- Data Engineering
- Backend Engineering
- AI-assisted Cost Analysis
- Rule-based Business Intelligence

---

# 3. Current Technology Stack｜目前技術棧

| Layer | Technology |
|---|---|
| Backend Framework | FastAPI |
| Database | PostgreSQL |
| Data Processing | Pandas |
| AI Integration | OpenAI / DeepSeek |
| API Testing | Swagger |
| Environment | Python 3.11 |
| Version Control | Git + GitHub |

---

# 4. Engineering Architecture｜工程化架構

```text
ai-construction-system/
│
├── main.py
│
├── api/
│   ├── project_api.py
│   ├── bid_api.py
│
├── services/
│   ├── cost_service.py
│   ├── excel_service.py
│   ├── ai_analysis.py
│   ├── rule_engine.py
│
├── utils/
│   ├── db.py
│   ├── column_mapping.py
│
├── models/
│   ├── schemas.py
│
├── uploads/
│
├── archive/
│
├── .env
│
├── requirements.txt
│
├── README.md
│
└── LEARNING.md
```

---

# 5. Layered Architecture｜分層架構思想

---

## main.py

System Entry Point

只負責：

- FastAPI initialization
- Router registration
- Global configuration

不負責：

- SQL
- AI
- Excel logic
- Business logic

---

## api/

HTTP Layer

負責：

- API endpoint
- Request / Response
- Router management

---

## services/

Business Logic Layer

負責：

- Excel processing
- Cost analysis
- AI integration
- Rule Engine
- Data transformation

---

## utils/

Infrastructure Layer

負責：

- PostgreSQL connection
- Data normalization
- Shared utilities

---

## models/

Schema Layer

負責：

- Pydantic schema
- Response validation
- Data structure definition

---

# 6. Data Engineering Pipeline｜數據工程管線

本專案核心已逐漸轉向：

```text
Business Data Engineering
```

---

## ETL Pipeline

```text
Excel
↓
Pandas DataFrame
↓
dict records
↓
Field normalization
↓
Rule Engine
↓
Business logic
↓
AI analysis
↓
API response
```

---

# 7. Data Normalization System｜數據標準化系統

中國建築業 Excel 存在：

- 簡繁混用
- 欄位名稱混亂
- 不同軟體格式不統一

例如：

```text
清單項目
清单项目名称
項目名稱
名称
```

全部統一映射為：

```python
item_name
```

透過：

```python
COLUMN_MAPPING
```

建立：

```text
Data Standardization Layer
```

---

# 8. Business Rule Engine｜業務規則引擎

建立：

```python
services/rule_engine.py
```

功能：

- 材料費識別
- 人工費識別
- 機械費識別

---

## Current Rule Logic

例如：

```text
混凝土 → 材料費
鋼筋 → 材料費
吊車 → 機械費
安裝 → 人工費
```

---

# 9. AI Integration｜AI 分析系統

目前支援：

- OpenAI API
- DeepSeek API

功能：

- 成本分析
- 專案健康分析
- AI 報告生成

---

# 10. Current APIs｜目前 API

---

## Portfolio Health API

```text
GET /projects/portfolio-health/
```

功能：

- 專案成本率分析
- 健康評分
- 成本分類分析
- AI 分析報告

---

## Upload Bid Excel API

```text
POST /upload-bid-excel
```

功能：

- Excel upload
- Data normalization
- Cost type classification
- Structured transformation

---

# 11. Environment Setup｜環境配置

---

## Python Version

Recommended:

```text
Python 3.11
```

---

## Create Virtual Environment

```bash
py -3.11 -m venv venv
```

---

## Activate

```bash
venv\Scripts\activate
```

---

## Install Dependencies

```bash
pip install fastapi[standard]
pip install psycopg2-binary
pip install pandas
pip install openpyxl
pip install python-dotenv
pip install openai
pip install python-multipart
```

---

# 12. .env Example｜環境變量配置

```env
DB_HOST=localhost
DB_NAME=construction_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_PORT=5432

OPENAI_API_KEY=your_key
```

---

# 13. Run Project｜啟動專案

```bash
uvicorn main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

# 14. Git Ignore Strategy｜Git 忽略策略

```gitignore
venv/
.env
uploads/
archive/
.vscode/
__pycache__/
```

---

# 15. Current Engineering Transition｜目前工程能力轉型

本專案代表：

```text
從：
低代碼平台使用者

轉向：

AI Business System Engineer
```

---

# 16. Core Engineering Insight｜目前核心理解

真正企業 AI 系統：

```text
不是：
AI 聊天
```

而是：

```text
資料結構
+
規則系統
+
AI
```

---

# 17. Future Roadmap｜未來規劃

---

## Backend

- SQLAlchemy
- Async PostgreSQL
- JWT Authentication
- Redis

---

## AI

- DeepSeek Integration
- OpenAI Integration
- RAG Knowledge Base
- AI Bid Strategy

---

## Deployment

- Docker
- Ubuntu Server
- Nginx
- CI/CD