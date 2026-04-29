# 📚 Learning Notes（關鍵知識整理）

---

## 1️⃣ fetchone vs fetchall（重要）

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
查一筆 → fetchone
查多筆 → fetchall
```

---

## 2️⃣ 常見錯誤（本次踩坑）

```python
result = cursor.fetchone()

for row in result: ❌
```

---

### 原因

```text
result 是 tuple，不是 list
```

---

### 正確

```python
rows = cursor.fetchall()

for row in rows:
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

## 5️⃣ COALESCE

```sql
COALESCE(SUM(amount), 0)
```

---

### 含義

```text
NULL → 0
```

---

## 6️⃣ API 設計

```text
✔ 使用 list（多筆）
✔ 使用 dict（結構化）
✔ 不要扁平設計
```

---

## 7️⃣ Python tuple 陷阱

```python
(project_id)   ❌
(project_id,)  ✅
```

---

## 8️⃣ SQL 參數化

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
自己寫 → 出錯 → 修正 → 記錄（LEARNING.md）
```
