# LEARNING.md

# Day 26 - Construction Parser Engineering

今天正式進入：

# Construction Document Semantic Parsing

階段。

這是整個 AI Construction System 真正開始具備工程價值的重要節點。

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

這是本質級差異。

---

# 二、真正理解：

# 物理行 ≠ 邏輯行

例如：

main_row：

```text
挖基坑土方
```

continuation_row：

```text
400kN...
```

在 Excel 中：

它們是：

```text
兩個 physical rows
```

但：

在業務語義中：

它們其實是：

```text
一個 logical record
```

---

# 三、真正開始建立：

# Row Semantic Parsing

不再只是：

```text
遍歷 DataFrame
```

而是：

```text
理解 row 的語義
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

# 五、真正理解：

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

# 六、main_row 的重要認知

曾經錯誤：

```python
pd.isna(...)
```

判斷 main_row。

導致：

真正數據行：

被誤判。

---

後來真正理解：

Parser：

應該：

```text
尋找存在的特徵
```

而不是：

```text
檢查所有字段是否為空
```

---

# 七、真正理解：

# Parser Rule ≠ 理論正確

而是：

```text
對真實數據穩定
```

例如：

加入：

```python
total_price
```

之後：

main_row 與 header_row：

真正被區分。

這是：

# 真實數據驅動 Parser

的重要認知。

---

# 八、真正理解：

# Data Structure Layer

建立了：

```text
Excel
↓
DataFrame
↓
records(list)
↓
row_dict(dict)
↓
values(list)
```

的數據結構理解。

---

# 九、真正理解：

# Python Import Root

曾經：

```bash
cd services
uvicorn main:app
```

導致：

```text
Could not import module "main"
```

---

後來真正理解：

Python import：

不是：

```text
文件在哪
```

而是：

```text
從哪裡啟動
```

---

# 十、真正理解：

# classify 與 pipeline 分離

以前：

```python
classify_row()
```

試圖做所有事情。

現在：

真正理解：

---

excel_row_parser.py：

```text
只負責：
這是什麼 row
```

---

excel_row_pipeline.py：

```text
負責：
如何處理 row
```

---

# 十一、真正理解：

# Metadata Context

例如：

```text
土石方工程
```

不是：

```text
普通數據
```

而是：

```text
metadata context
```

後續：

所有 main_row：

都應：

```python
row["category"] = current_category
```

---

# 十二、真正理解：

# continuation merge

continuation_row：

不是：

```text
獨立 row
```

而是：

```text
上一個 main_row 的補充
```

---

# 十三、真正開始接近：

# ETL Engineering

目前已開始涉及：

- Rule-based Parser
- Semantic Detection
- Metadata Attachment
- Context-aware Parsing
- Logical Record Reconstruction

---

# 十四、真正開始 Debug Parser Rule

不再只是：

```text
讓代碼跑
```

而是：

```text
讓 Parser 穩定
```

這是非常大的工程化提升。

---

# 十五、目前真正進入的能力區

不是：

```text
普通 Python CRUD
```

而是：

# Semi-structured Data Engineering

方向。

---

# 十六、下一步方向

接下來：

將正式進入：

- clean_rows
- metadata attach
- continuation merge
- logical_records

完整 Parser Pipeline。

---

# 十七、目前真正建立的是：

# Construction Document Semantic Parsing Engine

而不是：

```text
普通 Web API
```

這是目前整個項目最重要的方向。