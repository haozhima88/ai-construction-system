from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from cost_engine.schemas import NormalizedRow, PriceRow


SPACE_RE = re.compile(r"\s+")
INVISIBLE_RE = re.compile(r"[\u200b-\u200f\ufeff]")
KEYWORD_PATTERNS = [
    re.compile(r"[A-Za-z]+[0-9]*"),
    re.compile(r"[\u4e00-\u9fff]{2,}"),
    re.compile(r"(?<![A-Za-z0-9.])[0-9]+(?:\.[0-9]+)?(?![A-Za-z0-9.])"),
]
KNOWLEDGE_VERSION = "V0.1"
DEFAULT_REVIEW_STATUS = "pending"
DEFAULT_CONFIDENCE = 0.5

UNIT_ALIASES = {
    "m3": "m³",
    "M3": "m³",
    "ｍ3": "m³",
    "m³": "m³",
    "m2": "㎡",
    "M2": "㎡",
    "㎡": "㎡",
    "m²": "㎡",
    "kg": "kg",
    "KG": "kg",
    "t": "t",
    "T": "t",
    "吨": "t",
    "台班": "台班",
    "工日": "工日",
    "m": "m",
    "M": "m",
    "根": "根",
    "个": "个",
    "套": "套",
    "项": "项",
}


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.lower() == "nan":
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = INVISIBLE_RE.sub("", text)
    text = text.replace("\u3000", " ")
    return SPACE_RE.sub(" ", text).strip()


def normalize_unit(raw_unit: str | None) -> tuple[str, list[str]]:
    cleaned = clean_text(raw_unit)
    if not cleaned:
        return "", ["MISSING_UNIT"]
    normalized = UNIT_ALIASES.get(cleaned)
    if normalized:
        return normalized, []
    return cleaned, ["UNKNOWN_UNIT"]


def normalize_item_name(item_name: str) -> str:
    text = clean_text(item_name)
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s*[xX＊*×]\s*", "×", text)
    text = re.sub(r"\bm3\b", "m³", text, flags=re.IGNORECASE)
    text = re.sub(r"\bm2\b", "㎡", text, flags=re.IGNORECASE)
    return text


def generate_keywords(normalized_name: str) -> str:
    keywords: list[str] = []
    seen: set[str] = set()
    for pattern in KEYWORD_PATTERNS:
        for match in pattern.finditer(normalized_name):
            keyword = match.group(0).strip()
            if keyword and keyword not in seen:
                seen.add(keyword)
                keywords.append(keyword)
    return ";".join(keywords)


def parse_price(value: object) -> tuple[float | None, str | None]:
    text = clean_text(value)
    if not text:
        return None, None
    text = text.replace(",", "")
    try:
        return float(Decimal(text)), None
    except (InvalidOperation, ValueError):
        return None, "INVALID_PRICE"


def normalize_row(row: PriceRow) -> NormalizedRow:
    category_1 = clean_text(row.category_level_1)
    category_2 = clean_text(row.category_level_2) or category_1
    item_name = clean_text(row.item_name)
    remark = clean_text(row.remark)
    normalized_unit, unit_flags = normalize_unit(row.unit)
    prices: dict[str, float | None] = {}
    invalid_components: list[str] = []
    flags = list(unit_flags)

    for component, value in {
        "labor": row.labor_price,
        "material": row.material_price,
        "machine": row.machine_price,
    }.items():
        parsed, flag = parse_price(value)
        prices[component] = parsed
        if flag:
            invalid_components.append(component)
            flags.append(flag)
        if parsed == 0:
            flags.append("ZERO_PRICE_COMPONENT")

    if not item_name:
        flags.append("MISSING_ITEM_NAME")
    if not any(value is not None for value in prices.values()):
        flags.append("MISSING_PRICE")
    if remark:
        flags.append("HAS_REMARK")
    if category_1 and category_2 and category_1 != category_2:
        flags.append("CATEGORY_MISMATCH")
    if not category_1:
        flags.append("MISSING_CATEGORY")

    normalized_name = normalize_item_name(item_name)
    return NormalizedRow(
        raw=row,
        category_level_1=category_1,
        category_level_2=category_2,
        item_name=item_name,
        normalized_item_name=normalized_name,
        standard_name=normalized_name,
        keywords=generate_keywords(normalized_name),
        unit=clean_text(row.unit),
        normalized_unit=normalized_unit,
        remark=remark,
        original_remark=remark,
        needs_review=1,
        review_status=DEFAULT_REVIEW_STATUS,
        confidence=DEFAULT_CONFIDENCE,
        knowledge_version=KNOWLEDGE_VERSION,
        prices=prices,
        invalid_price_components=invalid_components,
        quality_flags=sorted(set(flags + ["NEEDS_MANUAL_REVIEW"])),
    )
