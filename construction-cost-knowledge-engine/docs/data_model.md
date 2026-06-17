# Data Model

The SQLite schema is PostgreSQL-friendly and keeps source traceability through `source_batch_id` and `source_row_no`.

Core tables:

- `source_import_batches`: one row per import run, including source hash and aggregate counts.
- `raw_cost_price_rows`: semi-clean raw row capture before business modeling.
- `unit_dictionary`: raw-to-normalized unit mapping.
- `cost_categories`: hierarchical category records for current two-level and future multi-level expansion.
- `cost_items`: normalized cost item master data with quality flags.
- `cost_price_components`: labor, material, and machine unit-price components.
- `cost_item_features`: rule-extracted features from item names and remarks.
- `boq_match_rules`: future curated matching rules.
- `boq_match_logs`: audit trail for BOQ matching results.

`v_cost_item_unit_prices` provides the main query surface for item-level unit costs and totals.
