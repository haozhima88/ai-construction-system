from __future__ import annotations

from collections import Counter

from cost_engine.schemas import NormalizedRow


def flag_duplicates(rows: list[NormalizedRow]) -> None:
    keys = [
        (row.normalized_item_name, row.normalized_unit)
        for row in rows
        if row.normalized_item_name and row.normalized_unit
    ]
    duplicates = {key for key, count in Counter(keys).items() if count > 1}
    for row in rows:
        if (row.normalized_item_name, row.normalized_unit) in duplicates:
            row.quality_flags = sorted(set(row.quality_flags + ["DUPLICATE_ITEM_NAME_UNIT"]))


def rows_needing_review(rows: list[NormalizedRow]) -> list[int]:
    review_flags = {
        "MISSING_ITEM_NAME",
        "MISSING_UNIT",
        "NO_PRICE_COMPONENT",
        "ZERO_PRICE_COMPONENT",
        "INVALID_PRICE",
        "DUPLICATE_ITEM_NAME_UNIT",
        "CATEGORY_MISMATCH",
        "UNKNOWN_UNIT",
    }
    return [
        row.raw.source_row_no
        for row in rows
        if review_flags.intersection(row.quality_flags)
    ]
