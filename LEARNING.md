# LEARNING.md

# Day 27-28
# Construction ETL Pipeline Engineering

今天正式完成：

# Construction Bid ETL Engine v1

這是整個 AI Construction System：

第一次真正完成：

```text
Excel
↓
Business Entity
```

完整轉換。

---

# 一、今天最大的認知升級

以前：

```text
Excel = 表格
```

現在：

```text
Excel = 半結構化文檔
```

而：

真正業務數據：

其實需要：

# 重建。

---

# 二、真正理解：

# 物理行 ≠ 邏輯行

例如：

---

main_row：

```text
挖基坑土方
```

---

continuation_row：

```text
400kN...
```

---

在 Excel：

它們是：

```text
兩個 physical rows
```

但：

在業務語義：

它們其實是：

```text
一個 logical record
```

---

# 三、真正建立：

# Row Semantic Parsing

不再只是：

```text
遍歷 DataFrame
```

而是：

```text
理解 row 的業務語義
```

---

# 四、建立的 Row Types

目前已建立：

- document_title_row
- page_info_row
- real_header_row
- header_sub_row
- category_row
- main_row
- continuation_row
- subtotal_row
- empty_row
- unknown_row

---

# 五、今天最重要的認知

# ETL：

不是：

```text
函數堆砌
```

而是：

# 數據狀態逐步演化

---

# 六、真正建立：

# Pipeline State Model

```text
classified_rows
↓
cleaned_rows
↓
metadata_attached_rows
↓
merged_rows
↓
logical_records
↓
normalized_records
↓
quality_report
```

---

# 七、真正理解：

# classify 與 pipeline 分離

---

# parser

負責：

```text
這是什麼 row
```

---

# pipeline

負責：

```text
如何處理 row
```

---

# 八、真正理解：

# clean_row_data()

作用：

```text
清理 useless rows
```

包括：

- empty_row
- header_row
- subtotal_row
- unknown_row

---

# 九、真正理解：

# attach_category()

作用：

```text
將 category metadata
掛載到後續 main_row
```

例如：

```text
土石方工程
```

↓

```python
row["category"]
```

---

# 十、真正理解：

# merge_continuation_rows()

作用：

```text
補充描述行
↓
merge 到上一個 main_row
```

---

# 十一、真正理解：

# build_logical_records()

作用：

```text
row_data
↓
Business Entity
```

即：

```python
{
    "item_code": "...",
    "item_name": "...",
    "quantity": ...
}
```

---

# 十二、真正理解：

# Business Entity Reconstruction

以前：

```text
操作 Excel
```

現在：

```text
重建業務數據
```

這是本質級提升。

---

# 十三、真正理解：

# Data Normalization

建立：

---

# safe_float()

作用：

```text
字符串
↓
float
```

支持：

- None
- NaN
- 空格
- 1,234.56

---

# clean_text()

作用：

```text
清理 feature 文本
```

包括：

- \n
- \t
- 空格
- None

---

# 十四、真正理解：

# normalize_records

作用：

```text
統一數據類型
```

例如：

```python
"quantity": 26.914
```

而不是：

```python
"quantity": "26.914"
```

---

# 十五、真正理解：

# Data Quality Engine

建立：

---

# validate_record()

檢查：

- item_name
- quantity
- unit_price
- total_price

---

# build_quality_report()

輸出：

```json
{
  "quality_score": 1.0,
  "warnings": []
}
```

---

# 十六、真正理解：

# Parser 的核心：

不是：

```text
字段越多越準
```

而是：

```text
哪些字段最具區分性
```

---

# 十七、真正理解：

# Parser Rule：

不是：

```text
理論正確
```

而是：

```text
對真實數據穩定
```

---

# 十八、真正理解：

# 固定列索引

目前：

```python
row_data.get(11)
```

屬：

# 技術債。

下一步：

將建立：

# Dynamic Header Mapping Engine

---

# 十九、真正理解：

# ETL 的真正價值

不是：

```text
Excel 轉 JSON
```

而是：

# 半結構化文檔
↓
標準化業務數據

---

# 二十、目前真正進入的能力區

不是：

```text
普通 Python CRUD
```

而是：

# ETL Engineering

包括：

- Semantic Parsing
- Data Normalization
- Business Reconstruction
- Data Governance
- Parser Engineering

---

# 二十一、目前真正建立的是：

# Construction ETL Engine

而不是：

```text
普通 Web API
```

這是目前整個項目最重要的方向。