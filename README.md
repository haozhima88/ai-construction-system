# AI Construction System
# AI 建築管理與成本分析系統

---

# Project Overview｜專案概覽

AI Construction System 是一套基於：

- FastAPI
- PostgreSQL
- Pandas
- OpenAI / DeepSeek API
- Excel Data Engineering

建立的 AI 建築管理與成本分析後端系統。

This project focuses on transforming:

```text
Unstructured / Semi-structured Construction Excel Data
```

into:

```text
Structured AI-ready Business Data
```

---

# Core Direction｜核心方向

本專案並不是：

```text
AI Chatbot Demo
```

而是：

```text
AI + Construction Business System
```

核心方向包括：

- Construction Cost Analysis
- Bid Excel Processing
- Data Normalization
- AI-assisted Cost Analysis
- Backend Engineering
- Business Data Engineering

---

# Current Technical Stack｜目前技術棧

| Layer | Technology |
|---|---|
| Backend Framework | FastAPI |
| Database | PostgreSQL |
| Data Processing | Pandas |
| AI Integration | OpenAI / DeepSeek |
| Environment | Python 3.11 |
| API Testing | Swagger |
| Version Control | Git + GitHub |

---

# Current Architecture｜目前工程架構

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

# Engineering Architecture｜工程化架構思想

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

- Cost analysis
- Excel transformation
- AI integration
- Data processing

---

## utils/

Infrastructure Layer

負責：

- PostgreSQL connection
- Data normalization
- Shared utility logic

---

## models/

Schema Layer

負責：

- Pydantic schema
- Response validation
- Data structure definition

---

# Data Normalization System｜數據標準化系統

中國建築業的 Excel 文件存在大量：

- 簡繁混用
- 命名不統一
- 欄位格式混亂

例如：

```text
清單項目
清单项目名称
項目名稱
名称
```

系統內部會統一映射為：

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

# ETL Pipeline｜Excel 數據管線

```text
Excel
↓
Pandas DataFrame
↓
dict records
↓
Field normalization
↓
Business logic
↓
AI analysis
↓
API response
```

---

# Current APIs｜目前 API

---

## Portfolio Health API

```text
GET /projects/portfolio-health/
```

功能：

- 專案成本率分析
- 健康評分
- 成本結構分析
- AI 成本分析報告

---

## Upload Bid Excel API

```text
POST /upload-bid-excel
```

功能：

- Excel upload
- Data normalization
- Structured transformation

---

# Environment Setup｜環境配置

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

# .env Example｜環境變量範例

```env
DB_HOST=localhost
DB_NAME=construction_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_PORT=5432

OPENAI_API_KEY=your_key
```

---

# Run Project｜啟動專案

```bash
uvicorn main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

# Git Ignore Strategy｜Git 忽略策略

```gitignore
venv/
.env
uploads/
archive/
.vscode/
__pycache__/
```

---

# Engineering Transition｜工程能力轉型

本專案不只是：

```text
Learning Python
```

而是：

```text
從：
低代碼平台使用者

轉向：

AI Business System Engineer
```

核心能力方向：

- Construction Business Knowledge
- Backend Engineering
- Data Engineering
- AI Integration
- System Architecture

---

# Future Roadmap｜未來規劃

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

---

# Core Insight｜目前最大理解

真正企業 AI 系統：

```text
不是：
AI 聊天

而是：

資料結構
+
規則系統
+
AI
```