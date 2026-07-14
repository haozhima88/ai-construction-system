from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from platform_db.models import ReferenceQuotaItem, ReferenceQuotaResource


ZERO = Decimal("0")
ROUNDING_TOLERANCE = Decimal("0.05")
CATEGORIES = ("labor", "material", "machine", "other")


def as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def display_text(value: Decimal | None, places: int = 2) -> str | None:
    return None if value is None else format(value, f".{places}f")


def normalized_category(resource: ReferenceQuotaResource) -> tuple[str, str | None]:
    category = (resource.resource_category or "other").lower()
    if resource.resource_code == "99450760" and "其他材料费" in resource.resource_name:
        return "other", "99450760 other material fee reclassified from material to other"
    return (category if category in CATEGORIES else "other"), None


class QuotaCostSummaryService:
    @staticmethod
    def resource_amount(resource: ReferenceQuotaResource) -> dict[str, Any]:
        source = as_decimal(resource.component_amount)
        consumption = as_decimal(resource.consumption)
        unit_price = as_decimal(resource.unit_price)
        calculated = None
        if source is None and consumption is not None and unit_price is not None:
            calculated = consumption * unit_price
        if source is not None:
            display, amount_source = source, "source"
        elif calculated is not None:
            display, amount_source = calculated, "calculated_fallback"
        else:
            display, amount_source = None, "unavailable"
        category, category_reason = normalized_category(resource)
        return {
            "resource_id": str(resource.reference_quota_resource_id),
            "resource_code": resource.resource_code,
            "resource_name": resource.resource_name,
            "resource_category": category,
            "source_resource_category": resource.resource_category,
            "category_reason": category_reason,
            "specification": resource.specification,
            "unit": resource.unit,
            "consumption": decimal_text(consumption),
            "unit_price": decimal_text(unit_price),
            "source_component_amount": decimal_text(source),
            "calculated_component_amount": decimal_text(calculated),
            "display_component_amount": decimal_text(display),
            "display_component_amount_2dp": display_text(display),
            "amount_source": amount_source,
            "source_page_no": resource.source_page_no,
            "source_row_order": resource.source_row_order,
        }

    def resources(self, rows: Iterable[ReferenceQuotaResource]) -> list[dict[str, Any]]:
        return [self.resource_amount(row) for row in rows]

    def summarize(
        self, quota: ReferenceQuotaItem, rows: Iterable[ReferenceQuotaResource]
    ) -> dict[str, Any]:
        resources = self.resources(rows)
        source_totals = {category: ZERO for category in CATEGORIES}
        calculated_totals = {category: ZERO for category in CATEGORIES}
        missing_rows = []
        category_reasons = []
        for resource in resources:
            category = resource["resource_category"]
            source = as_decimal(resource["source_component_amount"])
            display = as_decimal(resource["display_component_amount"])
            if source is not None:
                source_totals[category] += source
            if display is not None:
                calculated_totals[category] += display
            else:
                missing_rows.append(resource)
            if resource["category_reason"]:
                category_reasons.append(resource["category_reason"])

        resource_source_total = sum(source_totals.values(), ZERO)
        resource_calculated_total = sum(calculated_totals.values(), ZERO)
        management_fee = as_decimal(quota.management_fee)
        provincial_base_price = as_decimal(quota.total_fee)
        reconciliation_delta = None
        if provincial_base_price is not None:
            reconciliation_delta = (
                resource_calculated_total + (management_fee or ZERO) - provincial_base_price
            )

        if provincial_base_price is None:
            status = "source_blank_preserved"
            reason = "Provincial base price is blank and remains blank."
        elif missing_rows:
            unpriced_material = any(row["resource_category"] == "material" for row in missing_rows)
            status = "unpriced_material_excluded" if unpriced_material else "partial_resource_rows_missing"
            reason = f"{len(missing_rows)} resource rows have no source or calculable amount."
        elif reconciliation_delta == ZERO:
            status = "matched"
            reason = "Displayed resource total plus management fee matches the provincial base price."
        elif reconciliation_delta is not None and abs(reconciliation_delta) <= ROUNDING_TOLERANCE:
            status = "rounding_only"
            reason = "Difference is within the 0.05 display-rounding tolerance."
        elif category_reasons:
            status = "category_boundary_explained"
            reason = "; ".join(sorted(set(category_reasons)))
        else:
            status = "mismatch_requires_review"
            reason = "Source values are preserved; the unexplained delta requires cost-engineer review."

        return {
            **{f"{category}_source_total": decimal_text(source_totals[category]) for category in CATEGORIES},
            "resource_source_total": decimal_text(resource_source_total),
            **{
                f"{category}_calculated_total": decimal_text(calculated_totals[category])
                for category in CATEGORIES
            },
            "resource_calculated_total": decimal_text(resource_calculated_total),
            "management_fee": decimal_text(management_fee),
            "provincial_base_price": decimal_text(provincial_base_price),
            "reconciliation_delta": decimal_text(reconciliation_delta),
            "reconciliation_status": status,
            "reconciliation_reason": reason,
            "resource_row_count": len(resources),
            "missing_resource_row_count": len(missing_rows),
            "calculation_precision": "Decimal; no intermediate rounding",
            "display_precision": 2,
        }
