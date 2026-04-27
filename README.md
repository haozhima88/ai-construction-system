# AI Construction Management System

## 项目简介

本项目是一个基于 FastAPI + PostgreSQL 构建的施工项目管理系统（个人学习项目）。

目标是模拟真实企业中的项目管理逻辑，包括项目、成本、数据分析等模块，并逐步引入AI能力。

---

## 当前功能（Day 1 - Day 4）

### 1️⃣ 项目管理

* 创建项目（POST /projects）
* 查询项目（GET /projects）

---

### 2️⃣ 数据分析

* GET /analysis

支持：

* 总预算（SUM）
* 平均预算（AVG）
* 项目数量（COUNT）

---

### 3️⃣ 成本系统（核心升级）

* 建立 costs 表（多对一关系）
* 一个项目对应多个成本项

#### 成本字段

* project_id（关联项目）
* cost_type（成本类型）
* amount（金额）

---

### 4️⃣ 成本统计接口

* GET /project_cost/{project_id}

示例返回：

```json
{
  "project_id": 1,
  "total_cost": 230000
}
```

---

## 技术栈

* Python
* FastAPI
* PostgreSQL
* psycopg2

---

## 项目结构

```
ai-system/
├── main.py
├── db.py
├── README.md
```

---

## 如何运行

```bash
# 启动虚拟环境
venv\Scripts\activate

# 安装依赖
pip install fastapi uvicorn psycopg2-binary

# 启动服务
uvicorn main:app --reload
```

访问接口文档：
http://127.0.0.1:8000/docs

---

## 数据库结构

### projects 表

* id
* name
* budget

### costs 表

* id
* project_id（外键）
* cost_type
* amount

---

## 学习进度

* Day 1：FastAPI基础
* Day 2：数据库接入
* Day 3：数据分析（SUM / AVG / COUNT）
* Day 4：多表关系 + 成本系统

---

## 下一步计划

* 成本明细查询（JOIN）
* 项目利润分析（预算 vs 成本）
* AI分析模块（未来）
