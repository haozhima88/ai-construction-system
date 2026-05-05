# 📚 Learning Notes（完整知識體系）

---

## 🧠 1️⃣ 資料流

```text id="ru1v7q"
DB → tuple → Python → dict → JSON
```

---

## 🧠 2️⃣ SQL 核心

---

### JOIN

```sql id="21w4ut"
LEFT JOIN costs ON p.id = c.project_id
```

---

### GROUP BY

```sql id="4q4hbd"
GROUP BY p.id
GROUP BY cost_type
```

---

### 聚合

```sql id="43nq3u"
SUM()
AVG()
COUNT()
```

---

## 🧠 3️⃣ API 設計

```text id="nsx4yf"
/path → 資源
?query → 篩選
limit/offset → 分頁
```

---

## 🧠 4️⃣ 成本率

```text id="gh41wk"
cost_ratio = cost / budget
```

---

## 🧠 5️⃣ 成本分類分析

```text id="lpgmqp"
GROUP BY cost_type
```

---

## 🧠 6️⃣ 成本結構

```text id="u3m6u9"
總成本 ≠ 本質
結構 = 本質
```

---

## 🧠 7️⃣ Portfolio Analysis

```text id="ij29rg"
多專案整體分析
```

---

## 🧠 8️⃣ 健康度模型（核心）

```text id="drh3r3"
cost_ratio → score
```

---

## 🧠 9️⃣ 分組（最重要）

```python id="09bkl9"
cost_map[pid][ctype] = amount
```

---

### 本質

```text id="gr3e7u"
SQL → 平面
Python → 結構
```

---

## 🧠 🔟 dict.get()

```python id="y8m7kb"
value = dict.get(key, default)
```

---

### 含義

```text id="v7k5nt"
有 → 返回
無 → default
```

---

## 🧠 11️⃣ 工程思維

```text id="jz44zv"
能跑 ≠ 專業
可維護 > 能跑
```

---

## 🧠 12️⃣ 安全

```text id="cb6c1m"
✔ .env
✔ .gitignore
✔ 不暴露 key
```

---

## 🧠 13️⃣ 測試數據設計

```text id="4ej9g9"
正常 / 邊界 / 異常
```

---

## 🧠 核心理解（最重要）

```text id="xf3b8p"
你在學的是：
「如何把業務變成決策系統」
```
