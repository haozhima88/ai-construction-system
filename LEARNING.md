# LEARNING.md

# Learning Notes

# 學習記錄

## Day Topic

## 今日主題

```text
Parser V2 - Dynamic Schema Driven Excel Parser
```

```text
Parser V2 - 動態 Schema 驅動 Excel 解析器
```

---

## 1. Main Realization / 核心認知

The biggest issue in real construction Excel files is not row classification first.

The real issue is:

```text
Column positions are unstable.
```

真實建築招標清單中，最大問題不是先判斷哪一行是數據行，而是：

```text
欄位位置不穩定。
```

Earlier parser logic used:

```python
row_dict.get(3)
row_dict.get(8)
row_dict.get(11)
```

This worked only for one format.

之前的解析器依賴固定列號，只能處理某一種模板。

---

## 2. Old Parser Problem / 舊解析器問題

Old logic:

```text
Assume item_name is always column 3
Assume quantity is always column 8
Assume total_price is always column 11
```

Problem:

```text
Different Excel files have different layouts.
```

舊邏輯問題：

```text
想當然認為欄位位置固定。
```

但真實清單中：

```text
第一份清單 item_name 在第 3 列
第二份清單 item_name 在第 2 列
```

所以固定列號不可長期維護。

---

## 3. New Parser Thinking / 新解析思路

New flow:

```text
Do not parse data rows first.
First parse header.
```

新思路：

```text
不要先解析數據行。
先解析表頭。
```

Full logic:

```text
Excel
    ↓
Find header rows
    ↓
Merge main header and sub header
    ↓
Build schema
    ↓
Use schema to classify rows
```

---

## 4. Header Merge / 表頭合併

Some Excel files split headers into two rows:

```text
Main header:
序号 | 项目编码 | 项目名称 | 项目特征描述 | 计量单位 | 工程量

Sub header:
综合单价 | 合价
```

After merge:

```python
{
    "0": "序号",
    "1": "项目编码",
    "3": "项目名称",
    "4": "项目特征描述",
    "7": "计量单位",
    "8": "工程量",
    "9": "综合单价",
    "11": "合价"
}
```

這一步的本質是：

```text
physical header rows
        ↓
logical header row
```

---

## 5. Schema Builder / Schema 建立

After header merge, build schema:

```python
schema = {
    "serial_number": 0,
    "item_code": 1,
    "item_name": 3,
    "feature": 4,
    "unit": 7,
    "quantity": 8,
    "unit_price": 9,
    "total_price": 11
}
```

Schema means:

```text
standard field name → actual Excel column index
```

Schema 的意義是：

```text
標準字段名 → 實際 Excel 列號
```

這是 Parser V2 的核心。

---

## 6. Parser V2 Mental Model / Parser V2 心智模型

Old:

```text
row_dict.get(3)
```

New:

```python
row_dict.get(schema["item_name"])
```

Old:

```text
fixed column parser
```

New:

```text
schema driven parser
```

舊版：

```text
固定列解析器
```

新版：

```text
Schema 驅動解析器
```

---

## 7. Skip Header Rows / 剔除表頭行

After headers are used to build schema, they should not enter row classification.

表頭完成使命後，不應再進入數據行分類。

Flow:

```text
Header rows
    ↓
Build schema
    ↓
Add to skip_rows
    ↓
classify_rows skips them
```

Example:

```python
skip_rows = {2, 3, 17, 18, 29, 30}
```

This prevents:

```text
header row being classified as main_row
```

這可以避免：

```text
表頭被誤判為主數據行。
```

---

## 8. Data Structure Learning / 數據結構學習

Today exposed the importance of:

```text
list
dict
set
state management
```

今日真正練到的是：

```text
list / dict / set / 狀態管理
```

Examples:

```python
merged_rows = []
skip_rows = set()
schema = {}
```

These are not syntax details.

They are engineering models.

這些不是語法細節，而是工程建模方式。

---

## 9. Key Engineering Principle / 工程原則

```text
Build once, pass downward.
```

Schema should be created once in the API flow, then passed to parser and pipeline.

```text
Schema 只建立一次，向下傳遞。
```

Avoid:

```text
bid_api.py builds schema
excel_row_parser.py builds schema again
excel_row_pipeline.py builds schema again
```

That would create inconsistency.

---

## 10. Current Temporary Files / 當前臨時副本文件

Current temporary files:

```text
excel_row_parser_copy.py
excel_row_pipeline_copy.py
```

Purpose:

```text
Protect working code during Parser V2 validation.
```

目前保留 `_copy.py` 是合理的，因為目前仍在驗證階段。

Recommendation:

```text
Keep copies during validation.
After testing multiple Excel formats:
    merge useful logic
    delete temporary copies
```

---

## 11. Current Known Issues / 當前已知問題

1. `unit_price ` has a trailing space.
   `unit_price ` 有尾部空格，應修正為 `unit_price`。

2. Some files may not contain price columns.
   部分清單可能沒有單價與合價，需要允許缺失。

3. `合   计` should be recognized as final total row.
   `合   计` 應識別為 final_total_row。

4. Need to stabilize `attach_category()`.
   需要穩定 category 掛載邏輯。

5. Need to confirm continuation row merge under multiple formats.
   需要驗證不同格式下的補充行合併。

---

## 12. Next Tasks / 下一步任務

### Task 1

Fix mapping:

```python
"综合单价": "unit_price"
```

Do not allow:

```python
"unit_price "
```

---

### Task 2

Make parser schema-driven:

```python
item_name = row_dict.get(schema["item_name"])
quantity = row_dict.get(schema["quantity"])
```

---

### Task 3

Clean temporary copies after validation:

```text
excel_row_parser_copy.py
excel_row_pipeline_copy.py
```

---

### Task 4

Add import staging table:

```text
import_bid_records
```

---

### Task 5

Build export API:

```text
PostgreSQL
    ↓
DataFrame
    ↓
Excel
```

---

## 13. Personal Learning Reflection / 個人學習反思

The most important learning today:

```text
Code ability is not only writing syntax.
It is the ability to convert business logic into data structures.
```

今天最重要的收穫：

```text
代碼能力不是單純寫語法。
而是把業務邏輯轉換成數據結構的能力。
```

For AI era learning:

```text
Do not only let AI generate code.
Use AI to verify thinking, architecture, and edge cases.
```

AI 時代不應只是讓 AI 生成代碼，而應讓 AI 幫助檢查：

```text
架構
數據結構
邊界條件
工程流程
```

---

## 14. Current Milestone / 當前里程碑

```text
Parser V2 Core Validation Passed
```

```text
Parser V2 核心驗證已通過
```

The project has moved from:

```text
Excel script
```

toward:

```text
Construction Data Engineering System
```

本專案已從：

```text
Excel 小腳本
```

進入：

```text
建築工程數據工程系統
```
