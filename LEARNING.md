# 📚 Learning Notes（完整知識整理）

---

## 🧠 一、資料流理解（核心）

```text
資料庫 → tuple
Python → dict
API → JSON
```

---

## 🧠 二、fetchone vs fetchall

```text
fetchone → 單筆
fetchall → 多筆
```

---

## 🧠 三、SQL 核心

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

## 🧠 四、API 設計

```text
/path → 單資源
?query → 篩選
limit/offset → 分頁
```

---

## 🧠 五、Pydantic（專業感來源）

```python
class CostItem(BaseModel):
```

---

### List[CostItem]

```text
✔ 定義結構
✔ API 契約
✔ 自動文件
```

---

## 🧠 六、HTTPException

```python
raise HTTPException(status_code=404)
```

---

## 🧠 七、分頁

```sql
LIMIT + OFFSET
```

---

## 🧠 八、環境變數

```text
setx → 需重開 terminal
.env → 推薦方式
```

---

## 🧠 九、AI 使用原則

```text
✔ 解讀
✔ 建議
❌ 計算
```

---

## 🧠 十、錯誤碼理解

```text
401 → Key錯
429 → 沒額度
```

---

## 🧠 十一、安全

```text
✔ .env 不上傳
✔ 使用 .gitignore
✔ 使用 .env.example
```

---

## 🧠 十二、工程思維（最重要）

```text
能跑 ≠ 專業
可維護 ≠ 能跑
安全 ≠ 可選
```

---

## 🧠 十三、AI 系統本質

```text
AI ≠ 系統
AI = 語意層
```

---

## 🧠 核心理解（總結）

```text
你不是在學 Python
你在學「如何把業務變成系統」
```
