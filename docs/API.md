# API.md

# API Specification

## Version

V1.0

---

# Upload Bid Excel

## POST

```text
/upload-bid-excel
```

Purpose:

Upload construction BOQ Excel files and parse them into logical records.

Workflow:

```text
Excel
↓
Parser
↓
Logical Records
↓
Normalized Records
↓
import_bid_records
```

---

# Query Import Records

## GET

```text
/import-records
```

Purpose:

Query imported staging records.

Returns:

```json
[
  {
    "id":1,
    "review_status":"pending"
  }
]
```

---

# Review Record

## POST

```text
/review-record
```

Purpose:

Approve or reject imported records.

Request:

```json
{
  "record_id":123,
  "review_status":"approved"
}
```

---

# Sync Approved Records

## POST

```text
/sync-approved-records
```

Purpose:

Move approved records into business table.

Workflow:

```text
import_bid_records
↓
approved
↓
bid_records
↓
synced
```

---

# Future APIs

## Export Records

```text
/export-records
```

## Cost Analysis

```text
/cost-analysis
```

## AI Suggestions

```text
/ai-cost-analysis
```
