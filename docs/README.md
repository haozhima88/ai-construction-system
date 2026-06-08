# README.md

# AI Construction System

## Construction Data Engineering Platform Prototype

---

# Project Position

AI Construction System is a Construction Data Engineering Platform Prototype.

The project focuses on transforming unstructured construction bid Excel files into structured business data assets.

Core objective:

```text
Construction Excel
        ↓
Parser
        ↓
Schema
        ↓
Logical Records
        ↓
Database
        ↓
BI / AI Analysis
```

---

# Why This Project

Construction companies generate massive amounts of:

* Bid documents
* BOQ (Bill of Quantities)
* Cost spreadsheets
* Engineering records

Most data remains trapped inside Excel files.

This project aims to convert these files into:

```text
Queryable
Analyzable
Reusable
Traceable
```

business data.

---

# Current Architecture

```text
┌────────────────────┐
│ Construction Excel │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Header Detector    │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Schema Builder     │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Row Parser         │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Context Engine     │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Logical Records    │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ PostgreSQL         │
└────────────────────┘
```

---

# Current ETL Pipeline

```text
Excel
 ↓
find_header_rows()
 ↓
merge_header_rows()
 ↓
build_schema()
 ↓
classify_rows()
 ↓
clean_row_data()
 ↓
attach_category()
 ↓
build_logical_records()
 ↓
import_bid_records
```

---

# Current Milestones

## Completed

### Environment

* Python
* FastAPI
* PostgreSQL
* Git
* VS Code

### Parser V1

* main_row
* category_row
* continuation_row

### Parser V2

* Header Detection
* Header Merge
* Dynamic Schema
* Schema Driven Parsing

### Context Engine

* Category Attachment
* Page Information Attachment

### Logical Record Engine

Output:

```json
{
  "category": "天棚工程",
  "serial_number": "212",
  "item_code": "011301001001",
  "item_name": "天棚抹灰 S2 水池顶棚抹灰",
  "feature": "...",
  "unit": "m2",
  "quantity": "789.95",
  "unit_price": "40.27",
  "total_price": "31811.29"
}
```

---

# Current Database Design

## import_bid_records

Import staging table.

Purpose:

```text
Excel
 ↓
Parser
 ↓
Import Staging
```

---

## bid_records

Formal business table.

Purpose:

```text
Reviewed Records
 ↓
Business Data
```

---

# Technology Stack

Backend

* Python 3.11
* FastAPI

Database

* PostgreSQL

Data Processing

* Pandas

Development

* Git
* VS Code

---

# Next Milestone

Review Workflow

```text
import_bid_records
 ↓
Approve
 ↓
Sync
 ↓
bid_records
```

---

# Long-Term Vision

```text
Construction Excel
 ↓
Construction Data Platform
 ↓
Power BI
 ↓
AI Cost Analysis
 ↓
AI Tender Assistant
```

---

# Author

Mahahao

AI × Construction × Data Engineering
