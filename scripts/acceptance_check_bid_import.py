from __future__ import annotations

from pathlib import Path

import pandas as pd

from services.excel_row_parser import classify_rows, find_header_rows
from services.excel_row_pipeline import (
    attach_category,
    build_logical_records,
    build_normalized_records,
    build_schema,
    merge_header_rows,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "uploads" / "new" / "new2"
TARGET_SHEET_INDEX = 1
TARGET_SHEET_NAME = "分部分项工程项目清单计价表"
EXPECTED = {
    "12": {
        "rows": 364,
        "codes": {"10506001001", "10506001002", "10506001018"},
    },
    "34": {
        "rows": 245,
        "codes": {"10506001065", "10506001077"},
    },
}


def parse_file(path: Path) -> list[dict[str, object]]:
    excel_file = pd.ExcelFile(path)
    source_sheet_name = excel_file.sheet_names[TARGET_SHEET_INDEX]
    header_rows, skip_rows = find_header_rows(path, TARGET_SHEET_INDEX)
    schema = build_schema(merge_header_rows(header_rows))
    rows = classify_rows(path, TARGET_SHEET_INDEX, schema, skip_rows)
    logical_records = build_logical_records(attach_category(rows, schema), schema)
    return build_normalized_records(
        logical_records,
        batch_id="acceptance",
        source_file_name=path.name,
        source_sheet_index=TARGET_SHEET_INDEX,
        source_sheet_name=source_sheet_name,
    )


def main() -> None:
    files = {path.name[:2]: path for path in FIXTURE_DIR.glob("*.xlsx")}
    total = 0
    all_records: list[dict[str, object]] = []
    for prefix, expectation in EXPECTED.items():
        path = files.get(prefix)
        if path is None:
            raise FileNotFoundError(f"Missing acceptance workbook with prefix {prefix} under {FIXTURE_DIR}")
        records = parse_file(path)
        total += len(records)
        all_records.extend(records)
        codes = {str(record["item_code"]) for record in records}
        missing = sorted(expectation["codes"] - codes)
        if len(records) != expectation["rows"]:
            raise AssertionError(f"{path.name}: expected {expectation['rows']} rows, got {len(records)}")
        if missing:
            raise AssertionError(f"{path.name}: missing item_code {missing}")
        print(f"{path.name}: {len(records)} rows ok")

    names = {str(record["item_name"]) for record in all_records}
    required_names = {
        "现浇构混凝土垫层 C15",
        "现浇构混凝土桩承台基础 C35 P8",
    }
    if not required_names.issubset(names):
        raise AssertionError(f"Missing item names: {sorted(required_names - names)}")
    if any(record["source_sheet_name"] != TARGET_SHEET_NAME for record in all_records):
        raise AssertionError("source_sheet_name is not the real sheet name for every record")
    if any(record["source_excel_row_no"] is None for record in all_records):
        raise AssertionError("source_excel_row_no must be populated for every record")
    if total != 609:
        raise AssertionError(f"expected total 609 rows, got {total}")

    print("acceptance ok")
    print(f"total rows: {total}")


if __name__ == "__main__":
    main()
