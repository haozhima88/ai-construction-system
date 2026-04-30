# 📚 Learning Notes（完整知識整理）

---

## 1️⃣ fetchone vs fetchall

### fetchone

```python
cursor.fetchone()
```

回傳：

```text
("人工費", 100000)
```

---

### fetchall

```python
cursor.fetchall()
```

回傳：

```text
[
  ("人工費", 100000),
  ("材料費", 80000)
]
```

---

### ❗判斷原則

```text
單筆 → fetchone
多筆 → fetchall
```

---

## 2️⃣ 常見錯誤

```python
result = cursor.fetchone()

for row in result ❌
```

---

## 3️⃣ tuple → dict → list

```python
costs = [
    {"type": row[0], "amount": row[1]}
    for row in rows
]
```

---

## 4️⃣ SQL JOIN

```sql
LEFT JOIN costs ON p.id = c.project_id
```

---

## 5️⃣ GROUP BY

```sql
GROUP BY p.id
```

---

## 6️⃣ COALESCE

```sql
COALESCE(SUM(amount), 0)
```

---

## 7️⃣ 查詢參數 vs 路徑參數

```text
/project/1 → path
/projects?min=100 → query
```

---

## 8️⃣ 分頁（Pagination）

```sql
LIMIT 10 OFFSET 0
```

---

### 含義

```text
LIMIT → 筆數
OFFSET → 起點
```

---

## 9️⃣ API 結構設計

```text
不要扁平
使用：
{
  "query": {},
  "pagination": {},
  "count": 10,
  "data": []
}
```

---

## 🔟 Python tuple 陷阱

```python
(project_id)   ❌
(project_id,)  ✅
```

---

## 11️⃣ SQL 參數化

```python
cursor.execute(
    "SELECT * FROM projects WHERE id = %s",
    (project_id,)
)
```

---

## 🧠 核心理解

```text
資料庫 → tuple
Python → dict
API → JSON
```

---

## 🚀 學習方法

```text
自己寫 → 出錯 → 修正 → 記錄
```
