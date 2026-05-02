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

## 🧠 6️⃣ List[CostItem]

```text
列表 + 結構型資料
```

---

## 🧠 7️⃣ HTTPException

```text
標準錯誤處理
```

---

## 🧠 8️⃣ 分頁

```sql
LIMIT + OFFSET
```

---

## 🧠 9️⃣ 環境變數

```text
setx → 需重開 terminal
.env → 推薦
```

---

## 🧠 🔟 AI 原則

```text
✔ 解讀
✔ 建議
❌ 計算
```

---

## 🧠 11️⃣ 錯誤碼

```text
401 → API Key錯
429 → 沒額度
```

---

## 🧠 12️⃣ 安全

```text
✔ .env 不上傳
✔ .gitignore
✔ .env.example
```

---

## 🧠 13️⃣ Portfolio Analysis

```text
多專案分析（管理視角）
```

---

## 🧠 14️⃣ 成本率

```text
成本 / 預算
```

---

## 🧠 15️⃣ SQL 排序

```sql
ORDER BY profit DESC
```

---

## 🧠 16️⃣ SQL 設計原則（關鍵）

```text
SQL結構 → 拼接
數據值 → %s
```

---

## 🧠 17️⃣ 工程思維

```text
能跑 ≠ 專業
可維護 > 能跑
安全 = 基礎能力
```

---

## 🧠 核心理解（最重要）

```text
你不是在學語法
你在學「如何把業務變成系統」
```
