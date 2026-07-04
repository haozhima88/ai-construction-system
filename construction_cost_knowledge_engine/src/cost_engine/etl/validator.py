from __future__ import annotations

from collections import Counter

from cost_engine.schemas import NormalizedRow


def flag_duplicates(rows: list[NormalizedRow]) -> None:
    keys = [
        row.normalized_name
        for row in rows
        if row.normalized_name
    ]
    duplicates = {key for key, count in Counter(keys).items() if count > 1}
    for row in rows:
        if row.normalized_name in duplicates:
            row.quality_flags = sorted(set(row.quality_flags + ["DUPLICATE_NORMALIZED_NAME"]))


def rows_needing_review(rows: list[NormalizedRow]) -> list[int]:
    review_flags = {
        "MISSING_ITEM_NAME",
        "MISSING_UNIT",
        "MISSING_PRICE",
        "ZERO_PRICE_COMPONENT",
        "INVALID_PRICE",
        "DUPLICATE_NORMALIZED_NAME",
        "CATEGORY_MISMATCH",
        "UNKNOWN_UNIT",
        "NEEDS_MANUAL_REVIEW",
        "MISSING_CATEGORY",
        "INCONSISTENT_UNIT",
    }
    return [
        row.raw.source_row_no
        for row in rows
        if review_flags.intersection(row.quality_flags)
    ]
