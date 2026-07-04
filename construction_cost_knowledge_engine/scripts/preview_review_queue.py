from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def preview_review_queue(db_path: str | Path, limit: int = 20) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT
            krr.id AS review_record_id,
            ci.id AS cost_item_id,
            ci.original_name,
            krr.suggested_standard_name,
            krr.suggested_keywords,
            krr.review_status
        FROM knowledge_review_records krr
        JOIN cost_items ci ON ci.id = krr.cost_item_id
        ORDER BY krr.id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview pending cost knowledge review records.")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--limit", type=int, default=20, help="Maximum rows to print")
    args = parser.parse_args()

    rows = preview_review_queue(args.db, args.limit)
    for row in rows:
        print(
            "\t".join(
                [
                    str(row["review_record_id"]),
                    str(row["cost_item_id"]),
                    row["original_name"] or "",
                    row["suggested_standard_name"] or "",
                    row["suggested_keywords"] or "",
                    row["review_status"] or "",
                ]
            )
        )


if __name__ == "__main__":
    main()
