from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from web_collab_prototype import quota_building as legacy


router = APIRouter(prefix="/api/v1/review-sqlite", tags=["sqlite-readonly-fallback"])


def decimal_value(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def resource_payload(row: dict[str, Any]) -> dict[str, Any]:
    source = decimal_value(row.get("component_amount", row.get("amount")))
    consumption = decimal_value(row.get("consumption"))
    unit_price = decimal_value(row.get("unit_price"))
    calculated = consumption * unit_price if source is None and consumption is not None and unit_price is not None else None
    display = source if source is not None else calculated
    return {
        "resource_id": row.get("resource_component_id"),
        "resource_code": row.get("resource_code"),
        "resource_name": row.get("resource_name"),
        "resource_category": row.get("resource_category") or "other",
        "source_resource_category": row.get("resource_category"),
        "category_reason": None,
        "specification": row.get("specification"),
        "unit": row.get("unit"),
        "consumption": decimal_text(consumption),
        "unit_price": decimal_text(unit_price),
        "source_component_amount": decimal_text(source),
        "calculated_component_amount": decimal_text(calculated),
        "display_component_amount": decimal_text(display),
        "display_component_amount_2dp": format(display, ".2f") if display is not None else None,
        "amount_source": "source" if source is not None else ("calculated_fallback" if calculated is not None else "unavailable"),
        "source_page_no": row.get("source_page_no"),
        "source_row_order": row.get("source_row_order"),
    }


@router.get("/summary")
def summary():
    payload = dict(legacy.summary())
    payload["backend"] = "sqlite_readonly_fallback"
    payload["readonly"] = True
    return payload


@router.get("/tree")
def tree(page: int = Query(1, ge=1), page_size: int = Query(500, ge=1, le=500), q: str | None = None):
    payload = legacy.tree()
    items = payload["items"]
    if q:
        term = q.lower()
        items = [item for item in items if term in item["bill_code_9"].lower() or term in item["bill_name"].lower()]
    start = (page - 1) * page_size
    adapted = [{**item, "bill_id": item["bill_code_9"]} for item in items[start:start + page_size]]
    return {"items": adapted, "page": page, "page_size": page_size, "total": len(items)}


@router.get("/bills/{bill_id}")
def bill(bill_id: str):
    payload = legacy.bill_rows(bill_id)
    return {"bill": {**payload["bill"], "bill_id": payload["bill"]["bill_code_9"], "row_version": 1}}


@router.get("/bills/{bill_id}/mappings")
def mappings(bill_id: str):
    payload = legacy.bill_rows(bill_id)
    items = []
    for row in payload["rows"]:
        items.append({
            **row,
            "edge_id": row.get("mapping_edge_id"),
            "quota_id": row.get("quota_uid"),
            "quota_name": row.get("quota_full_name") or row.get("quota_name"),
            "quota_unit": row.get("unit_normalized") or row.get("quota_unit"),
            "quota_pdf_page_no": row.get("pdf_page_no"),
            "review_status": row.get("review_status") or "not_reviewed",
            "review_row_version": 0,
            "row_version": 1,
            "draft_row_version": 1 if row.get("draft_id") else None,
        })
    return {"bill": payload["bill"], "items": items, "count": len(items), "readonly": True}


@router.get("/bills/{bill_id}/authority-evidence")
def bill_authority_evidence(bill_id: str):
    payload = legacy.bill_evidence(bill_id)
    evidence = payload.get("evidence") or {}
    return {
        "bill_id": bill_id,
        "bill_reference_id": payload.get("bill", {}).get("bill_reference_id"),
        "bill_code_9": payload.get("bill", {}).get("bill_code_9", bill_id),
        "authority_document": {
            "source_role": "authority_source",
            "authority_status": "official_standard_evidence",
            "source_available": True,
        },
        "official_pdf_page_no": evidence.get("authority_pdf_page_no"),
        "authority_verification_status": evidence.get("authority_verification_status") or "pending_evidence_link",
        "evidence_type": "bill_authority_evidence",
        "source_locator": evidence.get("source_heading_path"),
        "evidence_link_status": "located" if evidence.get("authority_pdf_page_no") else "pending_evidence_link",
        "readonly": True,
    }


@router.get("/quotas/{quota_id}")
def quota(quota_id: str):
    payload = legacy.quota_detail(quota_id)
    raw = payload["quota"]
    price = payload.get("price") or {}
    return {"quota": {
        "quota_id": quota_id, "quota_uid": quota_id, "source_code": raw.get("source_code"),
        "quota_name": raw.get("raw_name"), "unit": raw.get("unit_normalized"),
        "volume_code": raw.get("volume_code"), "chapter_code": raw.get("chapter_code"),
        "section_code": raw.get("section_code"), "pdf_page_no": raw.get("pdf_page_no"),
        "labor_fee": price.get("labor_fee"), "material_fee": price.get("material_fee"),
        "machine_fee": price.get("machine_fee"), "management_fee": price.get("management_fee"),
        "total_fee": price.get("total_fee"), "source_role": "authority_source",
        "review_status": "pending", "source_document": {"document_name": raw.get("source_file"), "source_role": "authority_source"},
    }}


@router.get("/quotas/{quota_id}/resources")
def resources(quota_id: str, page: int = Query(1, ge=1), page_size: int = Query(200, ge=1, le=500)):
    rows = legacy.quota_resources(quota_id)["items"]
    start = (page - 1) * page_size
    return {"items": [resource_payload(row) for row in rows[start:start + page_size]], "page": page, "page_size": page_size, "total": len(rows)}


@router.get("/quotas/{quota_id}/work-content")
def work_content(quota_id: str):
    payload = legacy.quota_work(quota_id)
    return {"items": [{"rule_text": row.get("content_text"), **row} for row in payload["items"]], "count": payload["count"]}


@router.get("/quotas/{quota_id}/quantity-rules")
def quantity_rules(quota_id: str):
    payload = legacy.quota_rules(quota_id)
    return {"items": [{"rule_text": row.get("rule_text"), **row} for row in payload["items"]], "count": payload["count"]}


@router.get("/quotas/{quota_id}/conversion-rules")
def conversion_rules(quota_id: str):
    payload = legacy.quota_conversions(quota_id)
    return {"items": [{"rule_text": row.get("source_text_raw"), **row} for row in payload["items"]], "count": payload["count"]}


@router.get("/quotas/{quota_id}/notes")
def notes(quota_id: str):
    payload = legacy.quota_notes(quota_id)
    return {"items": [{"rule_text": row.get("clause_text"), **row} for row in payload["items"]], "count": payload["count"]}


@router.get("/quotas/{quota_id}/evidence")
def evidence(quota_id: str):
    detail = legacy.quota_detail(quota_id)["quota"]
    return {"quota_id": quota_id, "page_no": detail.get("pdf_page_no"), "document": {"document_name": detail.get("source_file"), "source_role": "authority_source", "source_available": True}, "items": [], "count": 0}


@router.get("/quotas/{quota_id}/cost-summary")
def cost_summary(quota_id: str):
    rows = [resource_payload(row) for row in legacy.quota_resources(quota_id)["items"]]
    detail = legacy.quota_detail(quota_id)
    price = detail.get("price") or {}
    categories = {name: Decimal("0") for name in ("labor", "material", "machine", "other")}
    source = {name: Decimal("0") for name in categories}
    missing = 0
    for row in rows:
        category = row["resource_category"] if row["resource_category"] in categories else "other"
        raw = decimal_value(row["source_component_amount"])
        display = decimal_value(row["display_component_amount"])
        if raw is not None:
            source[category] += raw
        if display is not None:
            categories[category] += display
        else:
            missing += 1
    resource_total = sum(categories.values(), Decimal("0"))
    management = decimal_value(price.get("management_fee"))
    base = decimal_value(price.get("total_fee"))
    delta = resource_total + (management or Decimal("0")) - base if base is not None else None
    status = "source_blank_preserved" if base is None else ("partial_resource_rows_missing" if missing else ("matched" if delta == 0 else "mismatch_requires_review"))
    return {
        **{f"{name}_source_total": decimal_text(source[name]) for name in source},
        "resource_source_total": decimal_text(sum(source.values(), Decimal("0"))),
        **{f"{name}_calculated_total": decimal_text(categories[name]) for name in categories},
        "resource_calculated_total": decimal_text(resource_total),
        "management_fee": decimal_text(management), "provincial_base_price": decimal_text(base),
        "reconciliation_delta": decimal_text(delta), "reconciliation_status": status,
        "reconciliation_reason": "Frozen SQLite read-only fallback calculation.",
        "resource_row_count": len(rows), "missing_resource_row_count": missing,
    }


@router.get("/audit")
def audit(page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500)):
    payload = legacy.audit_rows(limit=min(1000, page * page_size))
    start = (page - 1) * page_size
    return {"items": payload["items"][start:start + page_size], "page": page, "page_size": page_size, "total": payload["count"], "readonly": True}


@router.get("/quotas/{quota_id}/pdf")
def quota_pdf(quota_id: str):
    volume = legacy.quota_detail(quota_id)["quota"].get("volume_code")
    if not volume:
        raise HTTPException(404, "Province quota PDF not found")
    return legacy.province_pdf(volume)


@router.get("/authority/pdf")
def authority_pdf():
    return legacy.authority_pdf()
