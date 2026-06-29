import sqlite3
from pathlib import Path

from openpyxl import Workbook

from cost_engine.db import init_db
from cost_engine.etl.importer import import_price_table
from cost_engine.matching.matcher import match_boq_line


def _mock_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "人材机"
    ws.append(["分类", "分类", "名称", "人", "材", "机", "单位", "备注"])
    ws.append(["土建", "土建", "C30混凝土", "10", "20", "30", "m3", "泵送 含税"])
    ws.append(["安装", "安装", "给水管安装", "5", "15", "0", "m", ""])
    wb.save(path)


def test_boq_name_matches_candidate(tmp_path):
    xlsx = tmp_path / "mock.xlsx"
    _mock_workbook(xlsx)
    conn = sqlite3.connect(tmp_path / "cost.sqlite")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    import_price_table(conn, xlsx, "人材机")

    candidates = match_boq_line(conn, "C30混凝土", "泵送", "m3")

    assert candidates[0].item_name == "C30混凝土"
    assert candidates[0].total_unit_cost == 60
    assert candidates[0].match_score >= 0.75
    assert candidates[0].need_human_review is False


def test_low_score_match_needs_human_review(tmp_path):
    xlsx = tmp_path / "mock.xlsx"
    _mock_workbook(xlsx)
    conn = sqlite3.connect(tmp_path / "cost.sqlite")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    import_price_table(conn, xlsx, "人材机")

    candidates = match_boq_line(conn, "完全无关项目", "", "kg")

    assert candidates[0].need_human_review is True
