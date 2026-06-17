from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cost_engine.etl.excel_reader import read_price_rows, sheet_names
from cost_engine.etl.normalizer import clean_text, normalize_unit


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile an internal cost price table without printing price details.")
    parser.add_argument("--input", required=True, help="Path to .xls/.xlsx file")
    parser.add_argument("--sheet", default=None, help="Sheet name")
    args = parser.parse_args()

    path = Path(args.input)
    rows, headers = read_price_rows(path, args.sheet)
    categories = Counter(clean_text(row.category_level_1) for row in rows if clean_text(row.category_level_1))
    units = Counter(normalize_unit(row.unit)[0] or "<missing>" for row in rows)
    empty_fields = Counter()
    for row in rows:
        for field in ("category_level_1", "category_level_2", "item_name", "labor_price", "material_price", "machine_price", "unit", "remark"):
            if not clean_text(getattr(row, field)):
                empty_fields[field] += 1

    print(f"sheet names: {sheet_names(path)}")
    print(f"headers: {headers}")
    print(f"row count: {len(rows)}")
    print(f"category count: {len(categories)}")
    print(f"unit count: {len(units)}")
    print("empty field statistics:")
    for field, count in sorted(empty_fields.items()):
        print(f"  {field}: {count}")


if __name__ == "__main__":
    main()
