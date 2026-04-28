# 📚 Learning Notes（關鍵知識總結）

## 1️⃣ FastAPI 路由設計

### 關鍵點

* 路徑（URL）對外
* 函數對內
* 參數名稱必須一致

```python
@app.get("/project/{id}")
def get_project(id: int):
```

---

## 2️⃣ SQL 查詢類型區分

### 查資料

```sql
SELECT * FROM projects;
```

### 查統計

```sql
SELECT COUNT(*) FROM projects;
SELECT SUM(budget) FROM projects;
```

---

## 3️⃣ fetchone() 使用差異

### 問題點

```python
cursor.fetchone()
```

返回：

```text
(300000,)
```

---

### 正確使用

#### 查是否存在（主表）

```python
result = cursor.fetchone()
if not result:
    return error
value = result[0]
```

---

#### 查統計（可能為 NULL）

```python
value = cursor.fetchone()[0] or 0
```

---

## 4️⃣ Python 元組陷阱

```python
(project_id)   # ❌ 不是元組
(project_id,)  # ✅ 單元素元組
```

---

## 5️⃣ SQL 參數化查詢

### 正確寫法

```python
cursor.execute(
    "SELECT * FROM projects WHERE id = %s",
    (project_id,)
)
```

---

### 錯誤寫法（危險）

```python
f"WHERE id = {project_id}"
```

---

## 6️⃣ 外鍵關聯

```text
projects.id ←→ costs.project_id
```

---

## 7️⃣ 常見錯誤

### 拼寫錯誤

* excute ❌ → execute ✅
* fechone ❌ → fetchone ✅

---

### 邏輯錯誤

* 用 SELECT * 代替 COUNT ❌
* 忘記處理 None ❌

---

## 8️⃣ API 設計分類

```text
/analysis → 系統統計
/project/{id} → 單一資源
/projects?min=1000 → 篩選條件
```

---

## 9️⃣ 工程思維

```text
能跑 ≠ 正確
正確 ≠ 健壯
健壯 ≠ 可維護
```

---

## 🔟 學習方法

```text
自己寫 → 出錯 → AI輔助 → 修正 → 固化
```
