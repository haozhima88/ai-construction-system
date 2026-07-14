from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cost_engine.db import connect, init_db


DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "mock" / "standard_cost_reference_mvp.sqlite"


def _count_rows(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM standard_cost_item_reference").fetchone()[0])


def _print_distribution(conn: sqlite3.Connection, title: str, column: str) -> None:
    print(title)
    rows = conn.execute(
        f"""
        SELECT {column}, COUNT(*) AS count
        FROM standard_cost_item_reference
        GROUP BY {column}
        ORDER BY {column}
        """
    ).fetchall()
    if not rows:
        print("  <empty>")
        return
    for row in rows:
        value = row[column] if row[column] else "<blank>"
        print(f"  {value}: {row['count']}")


def preview_standard_reference(conn: sqlite3.Connection, limit: int = 30) -> dict[str, int | bool]:
    init_db(conn)
    total_count = _count_rows(conn)
    non_pending_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM standard_cost_item_reference
            WHERE review_status <> 'pending' OR review_status IS NULL
            """
        ).fetchone()[0]
    )

    print(f"total_count={total_count}")
    print(f"all_pending={total_count > 0 and non_pending_count == 0}")
    _print_distribution(conn, "by_chapter_code", "chapter_code")
    _print_distribution(conn, "by_section_name", "section_name")
    print(f"first_{limit}_rows")

    rows = conn.execute(
        """
        SELECT id, chapter_code, section_name, standard_name_candidate, unit, review_status
        FROM standard_cost_item_reference
        ORDER BY id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    for row in rows:
        print(
            f"{row['id']}\t{row['chapter_code']}\t{row['section_name']}\t"
            f"{row['standard_name_candidate']}\t{row['unit']}\t{row['review_status']}"
        )

    return {
        "total_count": total_count,
        "non_pending_count": non_pending_count,
        "all_pending": total_count > 0 and non_pending_count == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview the standard reference MVP table.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    conn = connect(args.db)
    preview_standard_reference(conn, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
