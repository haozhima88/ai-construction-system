# LEARNING.md

# Learning Journey

## AI × Construction × Data Engineering

---

# Project Background

I have worked in the construction industry for over 10 years.

My experience includes:

* Construction project management
* Enterprise informatization
* Low-code platforms
* Power BI
* ERP-related systems

This project is my transition path from:

```text
Construction IT Support
```

to:

```text
Data Engineering
ERP
BI
AI Application
```

---

# Major Realizations

## Realization 001

The real problem is not data rows.

The real problem is:

```text
Header Detection
```

Before:

```text
Find main rows
```

After:

```text
Find headers
 ↓
Build schema
 ↓
Parse rows
```

---

## Realization 002

Fixed column parsing is technical debt.

Old:

```python
row_dict.get(3)
```

New:

```python
row_dict.get(
    schema["item_name"]
)
```

---

## Realization 003

Excel Row is not Business Record.

Before:

```text
Excel Row
```

After:

```text
Business Record
```

Example:

```json
{
  "category": "天棚工程",
  "item_name": "天棚抹灰",
  "quantity": "789.95"
}
```

---

## Realization 004

Context is more important than data.

Rows like:

```text
category_row
page_info_row
```

do not contain quantities.

But they contain business meaning.

---

## Realization 005

The value of AI is not writing code.

The value of AI is helping with:

* Architecture
* Data structures
* Design decisions
* Edge cases

---

# Technical Growth

Current Skills

## Python

* Functions
* Modules
* Dictionaries
* Lists
* Pandas

## FastAPI

* Routing
* Upload APIs
* JSON Responses

## PostgreSQL

* Table Design
* Insert
* Query

## Data Engineering

* ETL
* Schema Design
* Data Pipeline

---

# Current Project Status

```text
Environment
██████████ 100%

Parser
█████████░ 90%

Database
██████░░░░ 60%

Export
███░░░░░░░ 30%

BI
░░░░░░░░░░ 0%

AI
░░░░░░░░░░ 0%
```

---

# Current Design Philosophy

Priority Order:

```text
Correctness
 >
Reusability
 >
Performance
 >
Beauty
```

For this project:

```text
A parser that works
 >
A parser that looks elegant
```

---

# Next Learning Target

Milestone 5

Review Workflow

Goals:

* review_status
* approve records
* reject records
* sync records

---

# Long-Term Career Goal

Build capability in:

```text
ERP
BI
Data Engineering
AI Applications
```

rather than becoming a traditional software developer.

The objective is:

```text
Business + Data + AI
```

instead of:

```text
Code Only
```
