# Import Rules

The importer reads the first eight columns as:

`分类 | 分类 | 名称 | 人 | 材 | 机 | 单位 | 备注`

Rules:

- Preserve every non-empty source row in `raw_cost_price_rows`.
- Keep both category columns as `category_level_1` and `category_level_2`; if level 2 is blank, copy level 1.
- Clean text with Unicode normalization, invisible-character removal, trimming, and repeated-space collapse.
- Normalize common units such as `m3` to `m³`, `m2` to `㎡`, and `吨` to `t`.
- Unknown units are preserved and flagged as `UNKNOWN_UNIT`.
- Blank unit is flagged as `MISSING_UNIT`.
- Blank price cells do not create price components.
- Zero prices create components and receive `ZERO_PRICE_COMPONENT`.
- Non-numeric prices do not create components and receive `INVALID_PRICE`.
- Duplicate normalized item name plus normalized unit receives `DUPLICATE_ITEM_NAME_UNIT`.
- Rows with remarks receive `HAS_REMARK`.

Reports must include only aggregate statistics, issue counts, and source row numbers needing review.
