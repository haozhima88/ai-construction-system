# DATABASE.md

# Database Design

## Architecture

```text
Excel
↓
import_bid_records
↓
Review
↓
bid_records
```

---

# import_bid_records

Purpose:

Import staging table.

Status:

```text
pending
approved
rejected
synced
```

---

## Main Fields

| Field             | Description     |
| ----------------- | --------------- |
| id                | PK              |
| batch_id          | Import batch    |
| source_file_name  | Source file     |
| source_sheet_name | Source sheet    |
| source_row_index  | Original row    |
| mapping_version   | Schema version  |
| review_status     | Workflow status |
| project_name      | Project         |
| category          | Category        |
| item_code         | BOQ code        |
| item_name         | Item name       |
| quantity          | Quantity        |
| unit_price        | Unit price      |
| total_price       | Total price     |

---

# bid_records

Purpose:

Formal business records.

Only approved data enters this table.

---

## Main Fields

| Field            | Description   |
| ---------------- | ------------- |
| id               | PK            |
| import_record_id | Source record |
| batch_id         | Batch         |
| project_name     | Project       |
| category         | Category      |
| item_code        | BOQ code      |
| item_name        | Item name     |
| quantity         | Quantity      |
| unit_price       | Unit price    |
| total_price      | Total price   |

---

# Data Flow

```text
pending
↓
approved
↓
synced
↓
bid_records
```
