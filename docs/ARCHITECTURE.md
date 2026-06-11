# ARCHITECTURE.md

# System Architecture

## V1.0 Architecture

```text
┌─────────────────────┐
│ Construction Excel  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Header Detector     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Schema Builder      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Row Classifier      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Context Engine      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Logical Records     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Normalized Records  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ import_bid_records  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Review Workflow     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ bid_records         │
└─────────────────────┘
```

---

## Core Engines

### Parser Engine

Responsible for:

* Header Detection
* Schema Building
* Row Classification

### Context Engine

Responsible for:

* Category Attachment
* Project Attachment

### Workflow Engine

Responsible for:

* Review
* Approval
* Sync

### Database Engine

Responsible for:

* Import Storage
* Business Storage
