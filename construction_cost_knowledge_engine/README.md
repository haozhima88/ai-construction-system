# Construction Cost Knowledge Engine

Python v0.1 project for importing a private internal construction cost price table into a structured SQLite knowledge base. The engine keeps raw row traceability, normalizes categories and units, splits labor/material/machine prices, records quality flags, and provides a first-pass BOQ matcher.

## Privacy Rules

- Do not commit the original Excel workbook.
- Put real input files, generated databases, converted workbooks, reports, and real-data CSV exports only under `data/private/`.
- Do not paste real price details into README, docs, tests, logs, or issues.
- Use `data/mock/` and tests for mock-only examples.

## Setup

```bash
pip install -e ".[test]"
```

For `.xls` input, install `xlrd` or make LibreOffice/soffice available for headless conversion. `.xlsx` input uses `openpyxl`.

## Commands

```bash
python scripts/profile_price_table.py --input data/private/内部价格表.xls
python scripts/import_internal_price_table.py --input data/private/内部价格表.xls --sheet 人材机 --db data/private/cost_engine.sqlite
python scripts/export_import_report.py --db data/private/cost_engine.sqlite --output data/private/import_report.md
pytest
```

The profile and import commands only print statistics, counts, issue types, and row counts. The import report does not include full price details.

## Query View

After import, use `v_cost_item_unit_prices` to inspect category, item name, normalized unit, labor/material/machine prices, total unit cost, remark, quality flags, and source row number.
