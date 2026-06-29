from cost_engine.etl.normalizer import normalize_row
from cost_engine.etl.validator import flag_duplicates
from cost_engine.schemas import PriceRow


def test_duplicate_item_name_unit_is_flagged():
    rows = [
        normalize_row(PriceRow(2, "土建", "土建", "C30混凝土", "1", "", "", "m3", "")),
        normalize_row(PriceRow(3, "土建", "土建", "C30混凝土", "", "2", "", "m³", "")),
    ]
    flag_duplicates(rows)
    assert all("DUPLICATE_ITEM_NAME_UNIT" in row.quality_flags for row in rows)


def test_category_level_2_defaults_to_level_1():
    row = normalize_row(PriceRow(2, "安装", "", "管道", "1", "", "", "m", ""))
    assert row.category_level_2 == "安装"
