from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cost_engine.db import connect, init_db


DEFAULT_SEED_PATH = PROJECT_ROOT / "data" / "mock" / "standard_cost_item_reference_A111_seed.csv"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "mock" / "standard_cost_reference_mvp.sqlite"
SOURCE_TYPE = "gd_quota_2018"
CHAPTER_CODE = "A.1.1"
MOJIBAKE_MARKERS = ("????", "\ufffd")

REFERENCE_COLUMNS = [
    "source_type",
    "source_name",
    "source_file",
    "source_page",
    "chapter_code",
    "chapter_name",
    "section_code",
    "section_name",
    "item_group_name",
    "source_code",
    "standard_name_candidate",
    "unit",
    "work_content",
    "keywords",
    "aliases",
    "feature_template",
    "extraction_confidence",
    "review_status",
    "reviewer",
    "remark",
]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_int(value: Any) -> int | None:
    text = _clean_text(value)
    if not text:
        return None
    return int(text)


def _clean_float(value: Any) -> float:
    text = _clean_text(value)
    if not text:
        return 0.0
    return float(text)


def _read_seed_rows(seed_path: Path) -> list[dict[str, Any]]:
    with seed_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        raise ValueError(f"Seed file is empty: {seed_path}")
    _assert_no_mojibake(rows)
    return rows


def _assert_no_mojibake(rows: list[dict[str, Any]]) -> None:
    for row_number, row in enumerate(rows, start=2):
        for column_name, value in row.items():
            text = _clean_text(value)
            if any(marker in text for marker in MOJIBAKE_MARKERS):
                raise ValueError(
                    f"Mojibake marker found in seed CSV at row {row_number}, "
                    f"column {column_name}: {text}"
                )


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {column: _clean_text(row.get(column)) for column in REFERENCE_COLUMNS}
    normalized["source_page"] = _clean_int(row.get("source_page"))
    normalized["extraction_confidence"] = _clean_float(row.get("extraction_confidence"))
    normalized["reviewer"] = _clean_text(row.get("reviewer"))
    if not normalized["source_type"]:
        normalized["source_type"] = SOURCE_TYPE
    if not normalized["chapter_code"]:
        normalized["chapter_code"] = CHAPTER_CODE
    if not normalized["review_status"]:
        normalized["review_status"] = "pending"
    if not normalized["standard_name_candidate"]:
        raise ValueError(f"Missing standard_name_candidate in seed row: {row}")
    return normalized


def _distribution(conn: sqlite3.Connection, column: str) -> dict[str, int]:
    query = f"""
        SELECT {column}, COUNT(*) AS count
        FROM standard_cost_item_reference
        WHERE source_type = ? AND chapter_code = ?
        GROUP BY {column}
        ORDER BY {column}
    """
    return {
        row[0] if row[0] is not None else "": int(row[1])
        for row in conn.execute(query, (SOURCE_TYPE, CHAPTER_CODE)).fetchall()
    }


def _table_count(conn: sqlite3.Connection, table_name: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def import_standard_reference_seed(
    conn: sqlite3.Connection,
    seed_path: str | Path = DEFAULT_SEED_PATH,
) -> dict[str, Any]:
    seed_path = Path(seed_path)
    if not seed_path.exists():
        raise FileNotFoundError(seed_path)

    init_db(conn)
    rows = [_normalize_row(row) for row in _read_seed_rows(seed_path)]

    conn.execute(
        """
        DELETE FROM standard_cost_item_reference
        WHERE source_type = ? AND chapter_code = ?
        """,
        (SOURCE_TYPE, CHAPTER_CODE),
    )

    placeholders = ", ".join(["?"] * len(REFERENCE_COLUMNS))
    columns_sql = ", ".join(REFERENCE_COLUMNS)
    values = [[row[column] for column in REFERENCE_COLUMNS] for row in rows]
    conn.executemany(
        f"""
        INSERT INTO standard_cost_item_reference ({columns_sql})
        VALUES ({placeholders})
        """,
        values,
    )
    conn.commit()

    return {
        "input_path": str(seed_path),
        "import_count": len(rows),
        "source_type_distribution": dict(Counter(row["source_type"] for row in rows)),
        "review_status_distribution": dict(Counter(row["review_status"] for row in rows)),
        "internal_price_library_count": _table_count(conn, "internal_price_library"),
        "cost_items_count": _table_count(conn, "cost_items"),
        "knowledge_review_records_count": _table_count(conn, "knowledge_review_records"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import the A.1.1 standard reference MVP seed.")
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED_PATH)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    conn = connect(args.db)
    report = import_standard_reference_seed(conn, args.seed)

    print(f"input_path={report['input_path']}")
    print(f"db_path={args.db}")
    print(f"import_count={report['import_count']}")
    print(
        "source_type_distribution="
        + json.dumps(report["source_type_distribution"], ensure_ascii=False, sort_keys=True)
    )
    print(
        "review_status_distribution="
        + json.dumps(report["review_status_distribution"], ensure_ascii=False, sort_keys=True)
    )
    print(f"internal_price_library_count={report['internal_price_library_count']}")
    print(f"cost_items_count={report['cost_items_count']}")
    print(f"knowledge_review_records_count={report['knowledge_review_records_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
