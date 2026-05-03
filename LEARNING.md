# 📚 Learning Notes（完整知識體系）

---

## 🧠 1️⃣ 資料流

```text
DB → tuple → Python → dict → API → JSON
```

---

## 🧠 2️⃣ fetchone vs fetchall

```text
fetchone → 單筆
fetchall → 多筆
```

---

## 🧠 3️⃣ SQL 核心

---

### JOIN

```sql
LEFT JOIN costs ON p.id = c.project_id
```

---

### GROUP BY

```sql
GROUP BY p.id
GROUP BY cost_type
```

---

### COALESCE

```sql
COALESCE(SUM(amount), 0)
```

---

## 🧠 4️⃣ API 設計

```text
/path → 單資源
?query → 篩選
limit/offset → 分頁
```

---

## 🧠 5️⃣ Pydantic

```text
✔ 定義資料結構
✔ API 契約
✔ 自動文件
```

---

## 🧠 6️⃣ HTTPException

```text
標準錯誤處理
```

---

## 🧠 7️⃣ 分頁

```sql
LIMIT + OFFSET
```

---

## 🧠 8️⃣ 環境變數

```text
.env 管理 API key
setx 需重開 terminal
```

---

## 🧠 9️⃣ AI 使用原則

```text
✔ 解讀
✔ 建議
❌ 計算
```

---

## 🧠 🔟 錯誤碼

```text
401 → API Key錯誤
429 → 無配額
```

---

## 🧠 11️⃣ 安全

```text
✔ .env 不提交
✔ .gitignore
✔ .env.example
```

---

## 🧠 12️⃣ Portfolio Analysis

```text
多專案分析（管理視角）
```

---

## 🧠 13️⃣ 成本率

```text
cost_ratio = cost / budget
```

---

## 🧠 14️⃣ 成本分類分析（Day12核心）

```text
GROUP BY cost_type
```

---

## 🧠 15️⃣ 成本占比

```text
ratio = 部分 / 總體
```

---

## 🧠 16️⃣ 成本結構

```text
不是總數
而是「分佈」
```

---

## 🧠 17️⃣ SQL 設計原則

```text
SQL結構 → 拼接
數據值 → %s
```

---

## 🧠 18️⃣ 工程思維

```text
能跑 ≠ 專業
可維護 > 能跑
安全 = 基礎能力
```

---

## 🧠 核心理解

```text
你不是在學語法
你在學「如何把業務變成系統」
```
