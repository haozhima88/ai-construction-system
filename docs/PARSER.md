# PARSER.md

# Parser Design

---

# Parser Evolution

## V1

Fixed Column Parser

```python
item_name = row_dict.get(3)
```

Problem:

Different Excel formats fail.

---

## V2

Schema Driven Parser

```python
item_name = row_dict.get(
    schema["item_name"]
)
```

Advantage:

Supports multiple formats.

---

# Parser Pipeline

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
```

---

# Supported Row Types

* document_title_row
* page_info_row
* real_header_row
* header_sub_row
* category_row
* main_row
* continuation_row
* subtotal_row

---

# Current Output

```json
{
  "category": "天棚工程",
  "serial_number": "212",
  "item_code": "011301001001",
  "item_name": "天棚抹灰",
  "feature": "...",
  "unit": "m2",
  "quantity": "789.95",
  "unit_price": "40.27",
  "total_price": "31811.29"
}
```
