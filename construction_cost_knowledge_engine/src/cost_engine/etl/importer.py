from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from cost_engine.db import init_db
from cost_engine.etl.excel_reader import read_price_rows
from cost_engine.etl.normalizer import normalize_row
from cost_engine.etl.validator import flag_duplicates
from cost_engine.matching.feature_extractor import extract_features
from cost_engine.schemas import NormalizedRow


def file_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def import_price_table(
    conn: sqlite3.Connection,
    input_path: str | Path,
    sheet_name: str | None = None,
    note: str = "",
) -> dict[str, object]:
    init_db(conn)
    rows, _headers = read_price_rows(input_path, sheet_name)
    normalized_rows = [normalize_row(row) for row in rows]
    flag_duplicates(normalized_rows)

    batch_id = _create_batch(conn, input_path, sheet_name, len(rows), note)
    stats = {
        "batch_id": batch_id,
        "row_count": len(rows),
        "item_count": 0,
        "component_count": 0,
        "category_count": 0,
        "unit_count": 0,
        "quality_counts": {},
        "review_rows": [],
    }
    for row in normalized_rows:
        _insert_raw_row(conn, batch_id, row)
        item_id = _upsert_cost_item(conn, batch_id, row)
        stats["item_count"] += 1
        for component_type, price in row.prices.items():
            if price is None:
                continue
            flags = ["ZERO_PRICE_COMPONENT"] if price == 0 else []
            _insert_component(conn, batch_id, item_id, row.raw.source_row_no, component_type, price, flags)
            stats["component_count"] += 1
        for feature in extract_features(row.item_name, row.remark):
            conn.execute(
                """
                INSERT INTO cost_item_features
                (cost_item_id, feature_key, feature_value, source_field, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (item_id, feature["key"], feature["value"], feature["source_field"], feature["confidence"], now_iso()),
            )
        for flag in row.quality_flags:
            stats["quality_counts"][flag] = stats["quality_counts"].get(flag, 0) + 1
        if row.quality_flags:
            stats["review_rows"].append(row.raw.source_row_no)

    stats["category_count"] = conn.execute("SELECT COUNT(*) FROM cost_categories").fetchone()[0]
    stats["unit_count"] = conn.execute("SELECT COUNT(*) FROM unit_dictionary").fetchone()[0]
    warning_count = len(set(stats["review_rows"]))
    conn.execute(
        """
        UPDATE source_import_batches
        SET success_count = ?, warning_count = ?, error_count = ?
        WHERE id = ?
        """,
        (stats["item_count"], warning_count, 0, batch_id),
    )
    conn.commit()
    return stats


def _create_batch(conn: sqlite3.Connection, input_path: str | Path, sheet_name: str | None, row_count: int, note: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO source_import_batches
        (source_file_name, source_file_hash, source_sheet_name, imported_at, row_count, note)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (Path(input_path).name, file_hash(input_path), sheet_name, now_iso(), row_count, note),
    )
    return int(cursor.lastrowid)


def _insert_raw_row(conn: sqlite3.Connection, batch_id: int, row: NormalizedRow) -> None:
    raw = row.raw
    conn.execute(
        """
        INSERT INTO raw_cost_price_rows
        (batch_id, source_row_no, raw_category_1, raw_category_2, raw_item_name,
         raw_labor_price, raw_material_price, raw_machine_price, raw_unit, raw_remark, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            batch_id,
            raw.source_row_no,
            raw.category_level_1,
            raw.category_level_2,
            raw.item_name,
            raw.labor_price,
            raw.material_price,
            raw.machine_price,
            raw.unit,
            raw.remark,
            now_iso(),
        ),
    )


def _upsert_unit(conn: sqlite3.Connection, raw_unit: str, normalized_unit: str, flags: list[str]) -> int | None:
    if not raw_unit and not normalized_unit:
        return None
    unit_type = "unknown" if "UNKNOWN_UNIT" in flags else None
    conn.execute(
        """
        INSERT INTO unit_dictionary (raw_unit, normalized_unit, unit_type, note)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(raw_unit) DO UPDATE SET normalized_unit = excluded.normalized_unit
        """,
        (raw_unit or normalized_unit, normalized_unit or raw_unit, unit_type, ",".join(flags)),
    )
    return conn.execute("SELECT id FROM unit_dictionary WHERE raw_unit = ?", (raw_unit or normalized_unit,)).fetchone()[0]


def _upsert_category(conn: sqlite3.Connection, name: str, level: int, parent_id: int | None = None) -> int | None:
    if not name:
        return None
    conn.execute(
        """
        INSERT OR IGNORE INTO cost_categories (parent_id, category_name, category_level)
        VALUES (?, ?, ?)
        """,
        (parent_id, name, level),
    )
    row = conn.execute(
        "SELECT id FROM cost_categories WHERE parent_id IS ? AND category_name = ? AND category_level = ?",
        (parent_id, name, level),
    ).fetchone()
    return int(row[0])


def _upsert_cost_item(conn: sqlite3.Connection, batch_id: int, row: NormalizedRow) -> int:
    category_1_id = _upsert_category(conn, row.category_level_1, 1)
    category_2_id = _upsert_category(conn, row.category_level_2, 2, category_1_id)
    unit_id = _upsert_unit(conn, row.unit, row.normalized_unit, row.quality_flags)
    flags_json = json.dumps(row.quality_flags, ensure_ascii=False)
    cursor = conn.execute(
        """
        INSERT INTO cost_items
        (category_level_1_id, category_level_2_id, item_name, normalized_item_name,
         unit_id, remark, source_row_no, source_batch_id, quality_flags, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            category_1_id,
            category_2_id,
            row.item_name,
            row.normalized_item_name,
            unit_id,
            row.remark,
            row.raw.source_row_no,
            batch_id,
            flags_json,
            now_iso(),
            now_iso(),
        ),
    )
    return int(cursor.lastrowid)


def _insert_component(
    conn: sqlite3.Connection,
    batch_id: int,
    item_id: int,
    source_row_no: int,
    component_type: str,
    price: float,
    flags: list[str],
) -> None:
    conn.execute(
        """
        INSERT INTO cost_price_components
        (cost_item_id, component_type, unit_price, source_row_no, source_batch_id, quality_flags, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (item_id, component_type, price, source_row_no, batch_id, json.dumps(flags, ensure_ascii=False), now_iso()),
    )
