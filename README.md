# AI Construction Management System

## 项目简介

这是一个基于 FastAPI + PostgreSQL 构建的施工管理系统（个人学习项目）。

目标是模拟真实企业中的项目管理系统，并逐步加入数据分析与AI能力。

---

## 当前功能（Day 1 - Day 3）

### 接口能力

* GET /hello（基础测试接口）
* POST /projects（创建项目）
* GET /projects（查询项目列表）

---

### 数据分析能力

* GET /analysis（数据统计接口）

支持指标：

* 总预算（SUM）
* 项目数量（COUNT）
* 平均预算（AVG）

---

## 示例返回

```json
{
  "total_budget": 600000,
  "avg_budget": 200000,
  "total_projects": 3
}
```

---

## 技术栈

* Python
* FastAPI
* PostgreSQL
* psycopg2

---

## 如何运行

```bash
# 激活虚拟环境
venv\Scripts\activate

# 安装依赖
pip install fastapi uvicorn psycopg2-binary

# 启动服务
uvicorn main:app --reload
```

---

访问接口文档：
http://127.0.0.1:8000/docs

---

## 项目结构（当前）

```
ai-system/
├── main.py
├── db.py
├── README.md
```

---

## 学习进度

* Day 1：基础API（FastAPI）
* Day 2：数据库接入（PostgreSQL）
* Day 3：数据分析（SUM / AVG / COUNT）

---

## 下一步计划

* 成本明细（Cost Table）
* 多表关联（JOIN）
* 项目成本分析
* AI辅助分析（未来）
