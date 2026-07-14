from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable


PRICE_SCALE = Decimal("0.000001")
CONSUMPTION_SCALE = Decimal("0.00000001")
CALCULATION_RULE_VERSION = "enterprise_decimal_v1"


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def quantized_price(value: Any) -> Decimal | None:
    decimal = decimal_or_none(value)
    return None if decimal is None else decimal.quantize(PRICE_SCALE, rounding=ROUND_HALF_UP)


def authoritative_amount(consumption: Any, selected_price: Any) -> Decimal | None:
    """Return an authoritative Decimal amount; a missing price stays missing."""
    quantity = decimal_or_none(consumption)
    price = decimal_or_none(selected_price)
    if quantity is None or price is None:
        return None
    return (quantity * price).quantize(PRICE_SCALE, rounding=ROUND_HALF_UP)


def component_amount_by_basis(component: dict[str, Any]) -> tuple[Decimal | None, str | None]:
    """Calculate one component without converting missing business inputs to zero."""
    if component.get("lifecycle_status", "active") == "removed":
        return Decimal("0.000000"), None
    basis = component.get("calculation_basis") or "quantity_unit_price"
    if basis == "quantity_unit_price":
        amount = authoritative_amount(component.get("consumption"), component.get("selected_enterprise_price"))
        return amount, None if amount is not None else "missing_price_component"
    if basis == "direct_amount":
        amount = quantized_price(component.get("enterprise_direct_amount"))
        return amount, None if amount is not None else "missing_direct_amount"
    if basis == "rate_based":
        base = decimal_or_none(component.get("calculation_base"))
        rate = decimal_or_none(component.get("enterprise_rate"))
        if base is None or rate is None:
            return None, "missing_rate_input"
        return quantized_price(base * rate), None
    if basis == "formula_based":
        formula = component.get("formula_code")
        version = component.get("formula_version")
        if (formula, version) == ("quantity_times_selected_price", "v1"):
            amount = authoritative_amount(component.get("consumption"), component.get("selected_enterprise_price"))
            return amount, None if amount is not None else "formula_missing_input"
        if (formula, version) == ("base_times_rate", "v1"):
            base = decimal_or_none(component.get("calculation_base"))
            rate = decimal_or_none(component.get("enterprise_rate"))
            if base is None or rate is None:
                return None, "formula_missing_input"
            return quantized_price(base * rate), None
        return None, "formula_error"
    return None, "unclassified_component"


def component_comparison(component: dict[str, Any]) -> dict[str, Any]:
    source_consumption = decimal_or_none(component.get("source_consumption"))
    enterprise_consumption = decimal_or_none(component.get("consumption"))
    provincial_unit_price = quantized_price(component.get("provincial_unit_price"))
    provincial_amount = quantized_price(component.get("provincial_component_amount"))
    if provincial_amount is None:
        provincial_amount = authoritative_amount(source_consumption, provincial_unit_price)
    enterprise_price = quantized_price(component.get("selected_enterprise_price"))
    enterprise_amount, calculation_error = component_amount_by_basis({
        **component,
        "consumption": enterprise_consumption,
        "selected_enterprise_price": enterprise_price,
    })
    price_delta = None
    if component.get("calculation_basis", "quantity_unit_price") == "quantity_unit_price" and enterprise_price is not None and provincial_unit_price is not None:
        price_delta = quantized_price(enterprise_price - provincial_unit_price)
    consumption_delta = None
    if component.get("calculation_basis", "quantity_unit_price") == "quantity_unit_price" and enterprise_consumption is not None and source_consumption is not None:
        consumption_delta = (enterprise_consumption - source_consumption).quantize(
            CONSUMPTION_SCALE, rounding=ROUND_HALF_UP
        )
    status = component.get("component_status") or "inherited"
    lifecycle = component.get("lifecycle_status") or "active"
    price_variance = consumption_variance = structure_variance = rate_variance = None
    component_total_variance = None
    source_amount_for_variance = provincial_amount
    if status == "resource_added" and source_amount_for_variance is None:
        source_amount_for_variance = Decimal("0.000000")
    if enterprise_amount is not None and source_amount_for_variance is not None:
        component_total_variance = quantized_price(enterprise_amount - source_amount_for_variance)
        basis = component.get("calculation_basis") or "quantity_unit_price"
        if lifecycle == "removed" or status in {"resource_added", "resource_replaced"} or component.get("source_reference_resource_id") is None:
            structure_variance = component_total_variance
        elif basis == "quantity_unit_price":
            if source_consumption is not None and enterprise_price is not None and provincial_unit_price is not None:
                price_variance = quantized_price(source_consumption * (enterprise_price - provincial_unit_price))
            if enterprise_consumption is not None and source_consumption is not None and enterprise_price is not None:
                consumption_variance = quantized_price((enterprise_consumption - source_consumption) * enterprise_price)
        elif basis == "direct_amount":
            consumption_variance = component_total_variance
        else:
            rate_variance = component_total_variance
    return {
        **component,
        "source_consumption": source_consumption,
        "consumption": enterprise_consumption,
        "provincial_unit_price": provincial_unit_price,
        "provincial_component_amount": provincial_amount,
        "selected_enterprise_price": enterprise_price,
        "enterprise_component_amount": enterprise_amount,
        "calculation_error": calculation_error,
        "price_delta": price_delta,
        "consumption_delta": consumption_delta,
        "price_variance": price_variance,
        "consumption_variance": consumption_variance,
        "structure_variance": structure_variance,
        "rate_variance": rate_variance,
        "component_total_variance": component_total_variance,
        "amount_source": component.get("amount_source") or (
            "enterprise_price_missing" if enterprise_price is None else "enterprise_draft_price"
        ),
    }


def summarize_components(
    components: Iterable[dict[str, Any]],
    *,
    reference_total_fee: Any = None,
    management_fee: Any = None,
) -> dict[str, Any]:
    totals = {"labor": Decimal("0"), "material": Decimal("0"), "machine": Decimal("0"), "other": Decimal("0")}
    compared = [component_comparison(component) for component in components]
    missing = 0
    missing_price = 0
    missing_direct = 0
    formula_errors = 0
    unclassified = 0
    variance = {"price": Decimal("0"), "consumption": Decimal("0"), "structure": Decimal("0"), "rate": Decimal("0")}
    for component in compared:
        category = str(component.get("resource_category") or "other").lower()
        bucket = category if category in totals else "other"
        amount = component["enterprise_component_amount"]
        if amount is None:
            missing += 1
            error = component.get("calculation_error")
            missing_price += error == "missing_price_component"
            missing_direct += error == "missing_direct_amount"
            formula_errors += error in {"formula_error", "formula_missing_input", "missing_rate_input"}
            unclassified += error == "unclassified_component"
        else:
            totals[bucket] += amount
        for key in variance:
            contribution = component.get(f"{key}_variance")
            if contribution is not None:
                variance[key] += contribution

    management = quantized_price(management_fee)
    enterprise_base = None
    if missing == 0:
        enterprise_base = quantized_price(sum(totals.values()) + (management or Decimal("0")))
    provincial_base = quantized_price(reference_total_fee)
    difference = None
    percentage = None
    if enterprise_base is not None and provincial_base is not None:
        difference = quantized_price(enterprise_base - provincial_base)
        if provincial_base != 0:
            percentage = ((difference / provincial_base) * Decimal("100")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
    return {
        "labor_total": quantized_price(totals["labor"]),
        "material_total": quantized_price(totals["material"]),
        "machine_total": quantized_price(totals["machine"]),
        "other_total": quantized_price(totals["other"]),
        "management_fee": management,
        "enterprise_base_price": enterprise_base,
        "provincial_base_price": provincial_base,
        "difference": difference,
        "difference_percentage": percentage,
        "missing_enterprise_price_resource_count": missing,
        "missing_price_component_count": missing_price,
        "missing_direct_amount_count": missing_direct,
        "formula_error_count": formula_errors,
        "unclassified_component_count": unclassified,
        "price_variance": quantized_price(variance["price"]),
        "consumption_variance": quantized_price(variance["consumption"]),
        "structure_variance": quantized_price(variance["structure"]),
        "rate_variance": quantized_price(variance["rate"]),
        "total_variance": difference,
        "calculation_rule_version": CALCULATION_RULE_VERSION,
    }


def _canonical(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def canonical_snapshot_payload(lines: Iterable[dict[str, Any]]) -> bytes:
    normalized = [_canonical(line) for line in lines]
    normalized.sort(key=lambda row: (str(row.get("enterprise_resource_id", "")), str(row.get("snapshot_line_id", ""))))
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def snapshot_sha256(lines: Iterable[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_snapshot_payload(lines)).hexdigest()


def restore_snapshot_payload(payload: bytes) -> list[dict[str, Any]]:
    """Decode the immutable representation without filling missing prices with zero."""
    rows = json.loads(payload.decode("utf-8"))
    for row in rows:
        if row.get("price_value") is not None:
            row["price_value"] = Decimal(row["price_value"])
    return rows
