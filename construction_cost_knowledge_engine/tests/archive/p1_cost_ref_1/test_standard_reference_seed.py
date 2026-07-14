from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

from cost_engine.db import init_db


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = PROJECT_ROOT / "data" / "mock" / "standard_cost_item_reference_A111_seed.csv"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "import_standard_reference_seed.py"


def _load_import_script():
    spec = importlib.util.spec_from_file_location("import_standard_reference_seed", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def test_standard_cost_item_reference_table_can_create(tmp_path):
    conn = _connect(tmp_path / "cost.sqlite")
    init_db(conn)

    table = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'standard_cost_item_reference'
        """
    ).fetchone()
    assert table is not None

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(standard_cost_item_reference)").fetchall()
    }
    assert {
        "id",
        "source_type",
        "chapter_code",
        "section_code",
        "standard_name_candidate",
        "unit",
        "extraction_confidence",
        "review_status",
        "reviewer",
        "remark",
    }.issubset(columns)


def test_standard_reference_seed_import_is_pending_and_isolated(tmp_path):
    module = _load_import_script()
    conn = _connect(tmp_path / "cost.sqlite")

    first_report = module.import_standard_reference_seed(conn, SEED_PATH)
    first_count = conn.execute("SELECT COUNT(*) FROM standard_cost_item_reference").fetchone()[0]

    assert first_report["import_count"] >= 30
    assert first_count == first_report["import_count"]
    assert (
        conn.execute(
            """
            SELECT COUNT(*)
            FROM standard_cost_item_reference
            WHERE source_type <> 'gd_quota_2018'
            """
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            """
            SELECT COUNT(*)
            FROM standard_cost_item_reference
            WHERE chapter_code <> 'A.1.1'
            """
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            """
            SELECT COUNT(*)
            FROM standard_cost_item_reference
            WHERE review_status <> 'pending'
            """
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            """
            SELECT COUNT(*)
            FROM standard_cost_item_reference
            WHERE standard_name_candidate IS NULL
               OR TRIM(standard_name_candidate) = ''
            """
        ).fetchone()[0]
        == 0
    )
    assert conn.execute("SELECT COUNT(*) FROM internal_price_library").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM cost_items").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM knowledge_review_records").fetchone()[0] == 0

    second_report = module.import_standard_reference_seed(conn, SEED_PATH)
    second_count = conn.execute("SELECT COUNT(*) FROM standard_cost_item_reference").fetchone()[0]

    assert second_report["import_count"] == first_report["import_count"]
    assert second_count == first_count
