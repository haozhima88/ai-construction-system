# AI Construction System

AI Construction System 是一個面向中國建築招標清單的：

- AI × ETL × FastAPI
- Construction Document Parsing
- 半結構化數據工程
- 招標清單標準化
- AI 成本分析

工程化系統。

本項目目前的核心方向：

不是普通 CRUD 系統，

而是：

# Construction Document Semantic Parsing Engine

即：

中國建築招標清單語義解析引擎。

---

# 一、當前工程結構

```text
ai-construction-system/
│
├── main.py
│
├── api/
│   ├── cost_api.py
│   ├── bid_api.py
│
├── services/
│   ├── excel_service.py
│   ├── cost_service.py
│   ├── ai_analysis.py
│   ├── excel_row_parser.py
│   ├── excel_row_pipeline.py
│
├── utils/
│   ├── column_mapping.py
│   ├── mappings/
│   │   ├── basic_mapping.py
│   │   ├── bid_mapping.py
│   │   ├── cost_mapping.py
│   │   ├── material_mapping.py
│   │   ├── tax_mapping.py
│   │
│   ├── db.py
│   ├── helpers.py
│
├── uploads/
│
├── archive/
│
├── models/
│   ├── schemas.py
│
├── requirements.txt
├── .env
├── README.md
└── LEARNING.md
```

---

# 二、當前核心能力

## 1. Excel 多 Sheet 解析

支持：

- sheet_name 指定
- 真實招標清單解析
- 中國建築業常見格式

---

## 2. Row Semantic Parsing

已建立：

| Row Type | 說明 |
|---|---|
| document_title_row | 文檔標題 |
| page_info_row | 頁碼/工程信息 |
| real_header_row | 真實表頭 |
| header_sub_row | 表頭補充 |
| category_row | 分部工程分類 |
| main_row | 主數據行 |
| continuation_row | 補充描述行 |
| subtotal_row | 小計行 |
| empty_row | 空行 |
| unknown_row | 未識別行 |

---

# 三、核心數據流

目前系統：

```text
Excel
↓
Pandas DataFrame
↓
records(list)
↓
row_dict(dict)
↓
normalize_values()
↓
classify_rows()
↓
clean_rows()
↓
attach_metadata()
↓
merge_continuation_rows()
↓
logical_records
↓
API Response
```

---

# 四、Parser Engineering 核心思想

本系統：

不是：

```text
Excel CRUD
```

而是：

# 半結構化文檔語義解析

核心思想：

- 物理行 ≠ 邏輯行
- 表格 ≠ 真實數據
- continuation row 需要 merge
- category row 是 metadata
- parser 的核心是 semantic pattern

---

# 五、目前已完成

## FastAPI 工程化

- API 拆分
- service 拆分
- utils 拆分
- mapping 模塊化
- .env 管理
- PostgreSQL 接入

---

## ETL 能力

- Excel 讀取
- 多 Sheet 支持
- column mapping
- row semantic parsing
- continuation row detection
- category row detection
- real header detection
- subtotal detection

---

## Parser 架構

已建立：

- Rule-based Parser
- Semantic Row Classification
- Context-aware Parsing
- Metadata State
- Parser Pipeline

---






# 六、當前 Parser Pipeline

## excel_row_parser.py

負責：

```text
“這是什麼 row”
```

包括：

- semantic detection
- row classification
- row pattern recognition

---

## excel_row_pipeline.py

負責：

```text
“如何處理 row”
```

包括：

- clean rows
- metadata attach
- continuation merge
- logical record reconstruction

---

# 七、目前重要工程能力

## 1. continuation merge

支持：

```text
多個 physical rows
↓
一個 logical record
```

---

## 2. category metadata

例如：

```text
土石方工程
```

將作為：

```python
row["category"]
```

掛載到後續 main_row。

---

## 3. Rule-based Semantic Detection

Parser：

不是：

```text
字段越多越準
```

而是：

```text
哪些字段最具區分性
```

---

# 八、啟動方式

## 1. 進入工程根目錄

```bash
cd ai-construction-system
```

---

## 2. 啟動虛擬環境

```bash
venv\Scripts\activate

```

---

## 3. 啟動 FastAPI

```bash
uvicorn main:app --reload
```

---

# 九、重要工程化原則

## 1. 永遠從工程根目錄啟動

不要：

```bash
cd services
python xxx.py
```

應：

```bash
uvicorn main:app --reload
```

---

## 2. classify 與 pipeline 分離

### excel_row_parser.py

只負責：

```text
這是什麼 row
```

---

### excel_row_pipeline.py

負責：

```text
如何處理 row
```

---

## 3. Parser Rule 原則

Parser：

- 使用最少的穩定特徵
- 使用最強的語義特徵
- 不依賴完整字段
- 不假設數據完整

---

# 十、Git 建議

## 每日提交

```bash
git add .
git commit -m "feat(parser): add semantic row classification"
```

---

## Parser 類提交建議

```bash
feat(parser): add continuation row merge

feat(parser): improve main row detection

refactor(parser): split parser and pipeline

fix(parser): fix header row conflict
```

---

# 十一、下一階段方向

## ETL 強化

- dynamic schema inference
- multi-header reconstruction
- repeated header clean
- logical record reconstruction

---

## AI 分析

- 成本結構分析
- 材料價格風險
- 歷史價格比對
- AI 招標分析

---

# 十二、當前項目定位

目前本項目：

已不再是：

```text
Python 練習
```

而是：

# Construction Document Semantic Parsing Engine