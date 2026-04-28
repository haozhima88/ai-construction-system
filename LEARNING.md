# 📚 Learning Notes（核心知識總結）

---

## 1️⃣ cursor.execute 使用

### 單行

```python id="exec1"
cursor.execute("SELECT * FROM projects")
```

### 多行（推薦）

```python id="exec2"
cursor.execute("""
    SELECT ...
    FROM ...
    JOIN ...
""")
```

### 原理

```text id="exec_rule"
""" 是 Python 多行字串
本質仍然是 SQL 字串
```

---

## 2️⃣ SQL 參數化

```python id="param"
cursor.execute(
    "SELECT * FROM projects WHERE id = %s",
    (project_id,)
)
```

---

### 關鍵

```text id="param_rule"
%s = 占位符
(project_id,) = tuple
```

---

## 3️⃣ Python tuple 陷阱

```python id="tuple1"
(project_id)   ❌
(project_id,)  ✅
```

---

## 4️⃣ fetchone 差異

### 寫法1

```python id="fetch1"
result = cursor.fetchone()
```

返回：

```text id="fetch1_res"
(300000,)
```

---

### 寫法2（推薦）

```python id="fetch2"
value = cursor.fetchone()[0] or 0
```

---

### 原因

```text id="fetch_reason"
避免 NULL → None → 計算錯誤
```

---

## 5️⃣ SQL 查詢類型

### 查資料

```sql id="select_all"
SELECT * FROM projects;
```

### 查統計

```sql id="select_count"
SELECT COUNT(*) FROM projects;
```

---

## 6️⃣ JOIN 核心

```sql id="join1"
LEFT JOIN costs ON p.id = c.project_id
```

---

### 含義

```text id="join_mean"
保留左表所有資料
```

---

## 7️⃣ GROUP BY

```sql id="group1"
GROUP BY p.id
```

---

## 8️⃣ COALESCE

```sql id="coal"
COALESCE(SUM(amount), 0)
```

---

### 含義

```text id="coal_mean"
NULL → 0
```

---

## 9️⃣ API 設計

```text id="api_design"
/analysis → 全局
/project/{id} → 單個
/projects?min=1000 → 篩選
```

---

## 🔟 常見錯誤

### 拼寫

* excute ❌
* fetchone ❌

---

### 邏輯

* SELECT * 用來計數 ❌
* 忘記處理 NULL ❌

---

## 🧠 核心提升

```text id="core_upgrade"
SQL 可以直接完成業務計算
```

---

## 🚀 學習方法

```text id="method"
自己寫 → 出錯 → AI輔助 → 修正 → 記錄
```
