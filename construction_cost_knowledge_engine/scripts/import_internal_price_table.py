from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cost_engine.db import connect
from cost_engine.etl.importer import import_price_table


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an internal price table into SQLite.")
    parser.add_argument("--input", required=True, help="Path to .xls/.xlsx file")
    parser.add_argument("--sheet", default=None, help="Sheet name")
    parser.add_argument("--db", required=True, help="SQLite database path under data/private")
    args = parser.parse_args()

    with connect(args.db) as conn:
        stats = import_price_table(conn, args.input, args.sheet)

    print(f"batch_id: {stats['batch_id']}")
    print(f"row_count: {stats['row_count']}")
    print(f"item_count: {stats['item_count']}")
    print(f"component_count: {stats['component_count']}")
    print(f"quality_issue_types: {len(stats['quality_counts'])}")
    print(f"manual_review_rows: {len(set(stats['review_rows']))}")


if __name__ == "__main__":
    main()
