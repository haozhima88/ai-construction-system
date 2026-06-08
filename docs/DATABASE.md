# DATABASE.md

# Database Design

---

# import_bid_records

Purpose:

Import staging table.

Workflow:

```text
Excel
 ↓
Parser
 ↓
import_bid_records
```

Fields:

* id
* batch_id
* source_file_name
* source_sheet_name
* source_row_index
* review_status
* page_info
* category
* serial_number
* item_code
* item_name
* feature
* unit
* quantity
* unit_price
* total_price
* created_at

---

# bid_records

Purpose:

Formal business records.

Workflow:

```text
import_bid_records
 ↓
review
 ↓
sync
 ↓
bid_records
```

Fields:

* id
* import_record_id
* batch_id
* page_info
* category
* serial_number
* item_code
* item_name
* feature
* unit
* quantity
* unit_price
* total_price
* created_at

---

# Review Status

pending

approved

rejected

synced
