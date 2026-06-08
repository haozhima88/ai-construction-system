# ARCHITECTURE.md

# AI Construction System Architecture

## Project Position

AI Construction System is a Construction Data Engineering Platform Prototype.

Core Goal:

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

# System Architecture

```text
┌──────────────────────┐
│ Construction Excel   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Header Detector      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Schema Builder       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Row Parser           │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Context Engine       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Logical Records      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ PostgreSQL           │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ BI / AI Layer        │
└──────────────────────┘
```

---

# Current Modules

## Parser Layer

Responsible for:

* Header detection
* Schema generation
* Row classification

## Context Layer

Responsible for:

* Category attachment
* Page information attachment

## Record Layer

Responsible for:

* Logical record generation

## Database Layer

Responsible for:

* Import staging
* Formal storage

---

# Future Architecture

```text
Excel
 ↓
Parser
 ↓
Database
 ↓
Power BI
 ↓
AI Cost Analysis
 ↓
AI Tender Assistant
```
