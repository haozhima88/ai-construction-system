import sqlite3
from pathlib import Path

from openpyxl import Workbook

from cost_engine.db import init_db
from cost_engine.etl.importer import import_price_table


def _mock_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "人材机"
    ws.append(["分类", "分类", "名称", "人", "材", "机", "单位", "备注"])
    ws.append(["土建", "土建", "C30混凝土", "10", "20", "30", "m3", "含税"])
    ws.append(["土建", "土建", "空价格项", "", "", "", "m2", ""])
    ws.append(["安装", "安装", "零价机械", "", "", "0", "台班", ""])
    ws.append(["安装", "安装", "非法价格", "abc", "", "", "", ""])
    wb.save(path)


def test_importer_splits_components_and_flags_quality(tmp_path):
    xlsx = tmp_path / "mock.xlsx"
    _mock_workbook(xlsx)
    conn = sqlite3.connect(tmp_path / "cost.sqlite")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    stats = import_price_table(conn, xlsx, "人材机")

    assert stats["row_count"] == 4
    assert conn.execute("SELECT COUNT(*) FROM raw_cost_price_rows").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(*) FROM cost_items").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(*) FROM cost_price_components").fetchone()[0] == 4
    assert stats["quality_counts"]["NO_PRICE_COMPONENT"] == 2
    assert stats["quality_counts"]["ZERO_PRICE_COMPONENT"] == 1
    assert stats["quality_counts"]["INVALID_PRICE"] == 1
    assert stats["quality_counts"]["MISSING_UNIT"] == 1

    total = conn.execute(
        "SELECT total_unit_cost FROM v_cost_item_unit_prices WHERE item_name = ?",
        ("C30混凝土",),
    ).fetchone()[0]
    assert total == 60


def test_empty_price_does_not_create_component(tmp_path):
    xlsx = tmp_path / "mock.xlsx"
    _mock_workbook(xlsx)
    conn = sqlite3.connect(tmp_path / "cost.sqlite")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    import_price_table(conn, xlsx, "人材机")

    item_id = conn.execute("SELECT id FROM cost_items WHERE item_name = ?", ("空价格项",)).fetchone()[0]
    assert conn.execute("SELECT COUNT(*) FROM cost_price_components WHERE cost_item_id = ?", (item_id,)).fetchone()[0] == 0
