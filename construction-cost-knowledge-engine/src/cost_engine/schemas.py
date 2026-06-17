from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PriceRow:
    source_row_no: int
    category_level_1: str = ""
    category_level_2: str = ""
    item_name: str = ""
    labor_price: str = ""
    material_price: str = ""
    machine_price: str = ""
    unit: str = ""
    remark: str = ""


@dataclass
class NormalizedRow:
    raw: PriceRow
    category_level_1: str
    category_level_2: str
    item_name: str
    normalized_item_name: str
    unit: str
    normalized_unit: str
    remark: str
    prices: dict[str, float | None]
    invalid_price_components: list[str] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)


@dataclass
class MatchCandidate:
    cost_item_id: int
    item_name: str
    unit: str
    labor_unit_price: float
    material_unit_price: float
    machine_unit_price: float
    total_unit_cost: float
    match_score: float
    match_reason: str
    quality_flags: list[str]
    need_human_review: bool
