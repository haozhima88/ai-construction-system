from cost_engine.etl.normalizer import generate_keywords, normalize_item_name, normalize_unit


def test_m3_normalizes_to_cubic_meter_symbol():
    assert normalize_unit("m3") == ("m³", [])


def test_empty_unit_flags_missing_unit():
    assert normalize_unit(" ")[1] == ["MISSING_UNIT"]


def test_unknown_unit_is_preserved_and_flagged():
    assert normalize_unit("mock-unit") == ("mock-unit", ["UNKNOWN_UNIT"])


def test_item_name_preserves_specs_and_unifies_multiply_symbol():
    assert normalize_item_name(" C30 100 x 200 ") == "C30 100×200"


def test_keywords_are_generated_from_normalized_name():
    assert generate_keywords("C30混凝土 100×200") == "C30;混凝土;100;200"
