from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = BASE_DIR.parent
READONLY_DB = BASE_DIR / "data" / "web_quota_building_readonly.sqlite"
DRAFT_DB = BASE_DIR / "data" / "web_quota_building_draft.sqlite"
TEMPLATE = BASE_DIR / "templates" / "quota_building_index.html"
LEGACY_TEMPLATE = BASE_DIR / "templates" / "quota_building_legacy.html"
SOURCE_DIR = ENGINE_ROOT / "data" / "private" / "reference_extraction" / "source_standards"
GD_SOURCE_DIR = SOURCE_DIR / "广东省建设工程综合定额(2018)"
AUTHORITY_PDF = SOURCE_DIR / "国家标准" / "房屋建筑与装饰工程工程量计算标准.pdf"
VOLUME_PDFS = {
    "A01": GD_SOURCE_DIR / "A01_广东省房屋建筑与装饰工程定额(上册).pdf",
    "A02": GD_SOURCE_DIR / "A02_广东省房屋建筑与装饰工程定额(中册).pdf",
    "A03": GD_SOURCE_DIR / "A03_广东省房屋建筑与装饰工程定额(下册).pdf",
}
ALLOWED_ACTIONS = {"copy", "move", "exclude"}
ALLOWED_REVIEW = {"reviewed_candidate", "needs_followup", "reviewed_mismatch", "not_reviewed"}

router = APIRouter()


class DraftAction(BaseModel):
    source_edge_id: str
    target_bill_code_9: str = ""
    action_type: str
    operation_reason: str = ""


class ReviewAction(BaseModel):
    bill_code_9: str
    quota_uid: str = ""
    review_status: str
    comment: str = ""


@contextmanager
def readonly_connect():
    if not READONLY_DB.exists():
        raise HTTPException(500, f"Readonly view model is missing: {READONLY_DB}")
    con = sqlite3.connect(f"file:{READONLY_DB.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


@contextmanager
def draft_connect():
    if not DRAFT_DB.exists():
        raise HTTPException(500, f"Draft database is missing: {DRAFT_DB}")
    con = sqlite3.connect(DRAFT_DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def rows(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in con.execute(sql, params).fetchall()]


def row(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    value = con.execute(sql, params).fetchone()
    return dict(value) if value else None


def natural_code(code: str) -> tuple[int, ...]:
    values = [int(value) for value in re.findall(r"\d+", code or "")]
    return tuple(values + [0] * (4 - len(values)))


def code_in_range(code: str, start: str, end: str) -> bool:
    return bool(start and end) and natural_code(start) <= natural_code(code) <= natural_code(end)


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def unit_dimension(value: Any) -> str:
    text = str(value or "").lower().replace("³", "3").replace("²", "2").replace("㎡", "m2")
    text = text.replace("立方米", "m3").replace("平方米", "m2").replace("延长米", "m")
    text = re.sub(r"^(?:10|100|1000)", "", text)
    if "m3" in text:
        return "volume"
    if "m2" in text:
        return "area"
    if re.search(r"(^|[^a-z])m([^a-z]|$)", text):
        return "length"
    for token, dimension in [("kg", "mass"), ("t", "mass"), ("个", "count"), ("樘", "count"), ("套", "count"), ("台", "count")]:
        if token in text:
            return dimension
    return ""


def edge_review_priority(item: dict[str, Any], candidate_count: int = 0) -> tuple[str, str]:
    p0_reasons: list[str] = []
    if item.get("risk_level") == "high":
        p0_reasons.append("high_risk")
    if item.get("routing_class") == "manual_review_required":
        p0_reasons.append("manual_review_required")
    bill_dimension = unit_dimension(item.get("bill_unit"))
    quota_dimension = unit_dimension(item.get("quota_unit"))
    if bill_dimension and quota_dimension and bill_dimension != quota_dimension:
        p0_reasons.append("unit_incompatible")
    if as_float(item.get("chapter_score"), 0.0) == 0:
        p0_reasons.append("cross_chapter_mapping")
    if item.get("has_parse_issue"):
        p0_reasons.append("parse_issue")
    if p0_reasons:
        return "P0", ";".join(dict.fromkeys(p0_reasons))
    p1_reasons: list[str] = []
    if candidate_count >= 5:
        p1_reasons.append("candidate_count>=5")
    if int(item.get("quota_bill_count") or 0) > 1:
        p1_reasons.append("quota_mapped_to_multiple_bills")
    if item.get("routing_class") in {"conversion_component", "shared_component", "measure_item"}:
        p1_reasons.append(item["routing_class"])
    if p1_reasons:
        return "P1", ";".join(dict.fromkeys(p1_reasons))
    return "P2", "low_risk_direct_candidate"


def csv_response(filename: str, data: list[dict[str, Any]]) -> Response:
    fields = list(data[0]) if data else ["status"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    if data:
        writer.writerows(data)
    payload = "\ufeff" + output.getvalue()
    return Response(payload.encode("utf-8"), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def audit(con: sqlite3.Connection, event: str, draft_id: str, bill: str, quota: str, before: Any, after: Any) -> None:
    con.execute(
        "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            f"AUDIT-{uuid4().hex}", event, draft_id, bill, quota,
            json.dumps(before, ensure_ascii=False, default=str) if before is not None else "",
            json.dumps(after, ensure_ascii=False, default=str) if after is not None else "",
            datetime.now().astimezone().isoformat(), "quota_building_user",
        ),
    )


@router.get("/quota-building", response_class=HTMLResponse)
def page() -> HTMLResponse:
    return HTMLResponse(TEMPLATE.read_text(encoding="utf-8"))


@router.get("/quota-building-legacy", response_class=HTMLResponse)
def legacy_page() -> HTMLResponse:
    return HTMLResponse(LEGACY_TEMPLATE.read_text(encoding="utf-8"))


@router.get("/api/quota-building/summary")
def summary() -> dict[str, Any]:
    with readonly_connect() as con:
        metadata = {item["key"]: item["value"] for item in rows(con, "SELECT key, value FROM metadata")}
        route_counts = {item["routing_class"]: item["count"] for item in rows(con, "SELECT routing_class, COUNT(*) count FROM mapping_edges GROUP BY routing_class")}
        volumes = rows(con, "SELECT volume_code, COUNT(*) quota_count FROM quota_items GROUP BY volume_code ORDER BY volume_code")
        zero_count = row(con, "SELECT COUNT(*) count FROM zero_candidate_bills")["count"]
        unrouted_count = row(con, "SELECT COUNT(*) count FROM unrouted_quotas")["count"]
        priority_edges = rows(
            con,
            """
            SELECT e.*, m.candidate_count,
              (SELECT COUNT(*) FROM mapping_edges x WHERE x.quota_uid=e.quota_uid) quota_bill_count,
              EXISTS(SELECT 1 FROM parse_issues p WHERE p.volume_code=e.volume_code AND p.source_code=e.source_code AND p.source_code!='') has_parse_issue
            FROM mapping_edges e JOIN bill_matrix m USING (bill_reference_id)
            """,
        )
        priority_counts: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0}
        for edge in priority_edges:
            priority, _ = edge_review_priority(edge, int(edge.get("candidate_count") or 0))
            priority_counts[priority] += 1
    with draft_connect() as con:
        draft_count = row(con, "SELECT COUNT(*) count FROM mapping_drafts WHERE draft_status != 'reverted'")["count"]
        audit_count = row(con, "SELECT COUNT(*) count FROM audit_log")["count"]
    return {
        "final_status": "building_mapping_ready_with_manual_review_backlog",
        "bill_count": int(metadata["bill_count"]), "quota_count": int(metadata["quota_count"]),
        "mapping_edge_count": int(metadata["mapping_edge_count"]), "zero_candidate_bill_count": zero_count,
        "unrouted_quota_count": unrouted_count, "routing_counts": route_counts, "volumes": volumes,
        "review_priority_counts": priority_counts,
        "draft_count": draft_count, "audit_count": audit_count, "approved_count": 0,
        "authority_role": "authority_source", "extraction_proxy_role": "extraction_proxy",
        "baseline_role": "derived_reference_candidate", "conflict_resolution_rule": "official_pdf_wins",
    }


@router.get("/api/quota-building/tree")
def tree() -> dict[str, Any]:
    with readonly_connect() as con:
        bills = rows(
            con,
            """
            SELECT b.bill_reference_id, b.bill_code_9, b.bill_name, b.appendix_code, b.appendix_name,
                   b.section_code, b.section_name, b.unit, b.project_feature_raw,
                   m.candidate_count, m.manual_review_required, m.authority_evidence_status
            FROM bill_items b JOIN bill_matrix m USING (bill_reference_id)
            ORDER BY b.appendix_code, b.section_code, b.bill_code_9
            """,
        )
        all_edges = rows(
            con,
            """
            SELECT e.*,
              (SELECT COUNT(*) FROM mapping_edges x WHERE x.quota_uid=e.quota_uid) quota_bill_count,
              EXISTS(
                SELECT 1 FROM parse_issues p
                WHERE p.volume_code=e.volume_code
                  AND p.source_code=e.source_code AND p.source_code!=''
              ) has_parse_issue
            FROM mapping_edges e
            """,
        )
        issue_bills = {
            item["bill_code_9"]
            for item in rows(con, "SELECT DISTINCT bill_code_9 FROM mapping_issues WHERE bill_code_9!=''")
        }
    with draft_connect() as con:
        stats = rows(
            con,
            """
            SELECT source_bill_code_9 bill_code_9,
              SUM(CASE WHEN action_type='copy' AND draft_status!='reverted' THEN 1 ELSE 0 END) copy_count,
              SUM(CASE WHEN action_type='move' AND draft_status!='reverted' THEN 1 ELSE 0 END) move_out_count,
              SUM(CASE WHEN action_type='exclude' AND draft_status!='reverted' THEN 1 ELSE 0 END) exclude_count
            FROM mapping_drafts GROUP BY source_bill_code_9
            """,
        )
        incoming = rows(
            con,
            """
            SELECT target_bill_code_9 bill_code_9,
              SUM(CASE WHEN action_type='copy' AND draft_status!='reverted' THEN 1 ELSE 0 END) copy_in_count,
              SUM(CASE WHEN action_type='move' AND draft_status!='reverted' THEN 1 ELSE 0 END) move_in_count
            FROM mapping_drafts WHERE target_bill_code_9!='' GROUP BY target_bill_code_9
            """,
        )
        review = {item["bill_code_9"]: item["review_status"] for item in rows(con, "SELECT bill_code_9, review_status FROM review_states WHERE quota_uid='' ")}
    by_bill = {item["bill_code_9"]: item for item in stats}
    incoming_by_bill = {item["bill_code_9"]: item for item in incoming}
    edges_by_bill: dict[str, list[dict[str, Any]]] = {}
    for edge in all_edges:
        edges_by_bill.setdefault(edge["bill_code_9"], []).append(edge)
    for bill in bills:
        outbound, inbound = by_bill.get(bill["bill_code_9"], {}), incoming_by_bill.get(bill["bill_code_9"], {})
        bill.update({
            "original_count": int(bill["candidate_count"] or 0), "copy_count": outbound.get("copy_count", 0) or 0,
            "copy_in_count": inbound.get("copy_in_count", 0) or 0, "move_in_count": inbound.get("move_in_count", 0) or 0,
            "move_out_count": outbound.get("move_out_count", 0) or 0, "exclude_count": outbound.get("exclude_count", 0) or 0,
            "review_state": review.get(bill["bill_code_9"], "not_reviewed"),
        })
        bill["effective_count"] = bill["original_count"] + bill["copy_in_count"] + bill["move_in_count"] - bill["move_out_count"] - bill["exclude_count"]
        priorities = [edge_review_priority(edge, bill["original_count"]) for edge in edges_by_bill.get(bill["bill_code_9"], [])]
        if bill["original_count"] == 0:
            priorities.append(("P0", "zero_candidate_bill"))
        if bill["bill_code_9"] in issue_bills:
            priorities.append(("P0", "mapping_issue"))
        priority_order = {"P0": 0, "P1": 1, "P2": 2}
        selected = min(priorities, key=lambda value: priority_order[value[0]]) if priorities else ("P0", "zero_candidate_bill")
        bill["review_priority"], bill["priority_reason"] = selected
        bill["manual_review_count"] = sum(priority == "P0" for priority, _ in priorities)
        bill["has_issue"] = bill["bill_code_9"] in issue_bills or any(edge.get("has_parse_issue") for edge in edges_by_bill.get(bill["bill_code_9"], []))
    return {"items": bills, "count": len(bills)}


@router.get("/api/quota-building/search")
def search(q: str = "") -> dict[str, Any]:
    query = q.strip()
    if not query:
        return {"bill_codes": [], "items": [], "count": 0}
    like = f"%{query}%"
    with readonly_connect() as con:
        bill_hits = rows(
            con,
            "SELECT bill_code_9, bill_name, 'bill' match_type, bill_name match_text FROM bill_items WHERE bill_code_9 LIKE ? OR bill_name LIKE ? LIMIT 200",
            (like, like),
        )
        quota_hits = rows(
            con,
            """
            SELECT DISTINCT e.bill_code_9, e.bill_name, 'quota' match_type,
                   q.source_code || ' ' || q.raw_name match_text
            FROM mapping_edges e JOIN quota_items q USING (quota_uid)
            WHERE q.source_code LIKE ? OR q.raw_name LIKE ? LIMIT 300
            """,
            (like, like),
        )
        resource_hits = rows(
            con,
            """
            SELECT DISTINCT e.bill_code_9, e.bill_name, 'resource' match_type,
                   r.resource_code || ' ' || r.resource_name match_text
            FROM resources r JOIN mapping_edges e USING (quota_uid)
            WHERE r.resource_code LIKE ? OR r.resource_name LIKE ? LIMIT 300
            """,
            (like, like),
        )
    items = bill_hits + quota_hits + resource_hits
    return {"bill_codes": sorted({item["bill_code_9"] for item in items}), "items": items[:500], "count": len(items)}


@router.get("/api/quota-building/bill/{bill_code_9}/rows")
def bill_rows(bill_code_9: str) -> dict[str, Any]:
    with readonly_connect() as con:
        bill = row(con, "SELECT * FROM bill_items WHERE bill_code_9=?", (bill_code_9,))
        if not bill:
            raise HTTPException(404, "Bill item not found")
        original = rows(
            con,
            """
            SELECT e.*, q.raw_name quota_full_name, q.unit_normalized, q.pdf_page_no, q.volume_code,
                   q.source_file, q.source_sha256, p.labor_fee, p.material_fee, p.machine_fee,
                   p.management_fee, p.total_fee,
                   (SELECT COUNT(*) FROM mapping_edges x WHERE x.quota_uid=e.quota_uid) quota_bill_count,
                   EXISTS(
                     SELECT 1 FROM parse_issues pi
                     WHERE pi.volume_code=e.volume_code
                       AND pi.source_code=e.source_code AND pi.source_code!=''
                   ) has_parse_issue
            FROM mapping_edges e
            LEFT JOIN quota_items q USING (quota_uid)
            LEFT JOIN price_snapshots p USING (quota_uid)
            WHERE e.bill_code_9=? ORDER BY CAST(e.candidate_rank AS INTEGER)
            """,
            (bill_code_9,),
        )
    with draft_connect() as con:
        drafts = rows(con, "SELECT * FROM mapping_drafts WHERE (source_bill_code_9=? OR target_bill_code_9=?) AND draft_status!='reverted' ORDER BY created_at", (bill_code_9, bill_code_9))
        review_states = rows(con, "SELECT * FROM review_states WHERE bill_code_9=?", (bill_code_9,))
    by_edge = {item["source_edge_id"]: item for item in drafts if item["source_bill_code_9"] == bill_code_9}
    for item in original:
        draft = by_edge.get(item["mapping_edge_id"])
        item["row_origin"] = "original_candidate"
        item["draft_action"] = draft["action_type"] if draft else ""
        item["draft_status"] = draft["draft_status"] if draft else ""
        item["effective"] = not bool(draft and draft["action_type"] in {"move", "exclude"})
        item["review_priority"], item["priority_reason"] = edge_review_priority(item, len(original))
    incoming = [item for item in drafts if item["target_bill_code_9"] == bill_code_9 and item["action_type"] in {"copy", "move"}]
    if incoming:
        edge_ids = [item["source_edge_id"] for item in incoming]
        placeholders = ",".join("?" for _ in edge_ids)
        with readonly_connect() as con:
            source_rows = {item["mapping_edge_id"]: item for item in rows(con, f"SELECT e.*, q.raw_name quota_full_name, q.unit_normalized, q.pdf_page_no, q.volume_code, q.source_file, q.source_sha256, p.labor_fee, p.material_fee, p.machine_fee, p.management_fee, p.total_fee FROM mapping_edges e LEFT JOIN quota_items q USING (quota_uid) LEFT JOIN price_snapshots p USING (quota_uid) WHERE e.mapping_edge_id IN ({placeholders})", tuple(edge_ids))}
        for draft in incoming:
            source = dict(source_rows.get(draft["source_edge_id"], {}))
            if source:
                source.update({"bill_code_9": bill_code_9, "row_origin": f"draft_{draft['action_type']}", "draft_action": draft["action_type"], "draft_status": draft["draft_status"], "draft_id": draft["draft_id"], "effective": True})
                source["review_priority"], source["priority_reason"] = edge_review_priority(source, len(original))
                original.append(source)
    return {"bill": bill, "rows": original, "review_states": review_states, "count": len(original)}


def quota_or_404(con: sqlite3.Connection, quota_uid: str) -> dict[str, Any]:
    quota = row(con, "SELECT * FROM quota_items WHERE quota_uid=?", (quota_uid,))
    if not quota:
        raise HTTPException(404, "Quota not found")
    return quota


@router.get("/api/quota-building/quota/{quota_uid}/detail")
def quota_detail(quota_uid: str) -> dict[str, Any]:
    with readonly_connect() as con:
        quota = quota_or_404(con, quota_uid)
        price = row(con, "SELECT * FROM price_snapshots WHERE quota_uid=?", (quota_uid,))
        mappings = rows(con, "SELECT * FROM mapping_edges WHERE quota_uid=? ORDER BY bill_code_9", (quota_uid,))
    return {"quota": quota, "price": price, "mappings": mappings}


@router.get("/api/quota-building/quota/{quota_uid}/resources")
def quota_resources(quota_uid: str) -> dict[str, Any]:
    with readonly_connect() as con:
        quota_or_404(con, quota_uid)
        data = rows(con, "SELECT * FROM resources WHERE quota_uid=? ORDER BY resource_component_id", (quota_uid,))
    return {"items": data, "count": len(data)}


def scoped_records(quota_uid: str, block_table: str, link_table: str, block_id: str) -> list[dict[str, Any]]:
    with readonly_connect() as con:
        quota = quota_or_404(con, quota_uid)
        links = rows(con, f"SELECT * FROM {link_table} WHERE volume_code=?", (quota["volume_code"],))
        matching = [item for item in links if item.get("quota_uid") == quota_uid or code_in_range(quota["source_code"], item.get("scope_start_code", ""), item.get("scope_end_code", ""))]
        ids = list(dict.fromkeys(item[block_id] for item in matching if item.get(block_id)))
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        block_rows = rows(con, f"SELECT * FROM {block_table} WHERE {block_id} IN ({placeholders})", tuple(ids))
    scope_by_id = {item[block_id]: item for item in matching}
    for item in block_rows:
        item["scope"] = scope_by_id.get(item[block_id], {})
    return block_rows


@router.get("/api/quota-building/quota/{quota_uid}/work-content")
def quota_work(quota_uid: str) -> dict[str, Any]:
    data = scoped_records(quota_uid, "work_blocks", "work_scope_links", "work_content_block_id")
    return {"items": data, "count": len(data)}


@router.get("/api/quota-building/quota/{quota_uid}/quantity-rules")
def quota_rules(quota_uid: str) -> dict[str, Any]:
    data = scoped_records(quota_uid, "quantity_rule_blocks", "quantity_rule_scope_links", "quantity_rule_block_id")
    return {"items": data, "count": len(data)}


@router.get("/api/quota-building/quota/{quota_uid}/conversions")
def quota_conversions(quota_uid: str) -> dict[str, Any]:
    with readonly_connect() as con:
        quota = quota_or_404(con, quota_uid)
        data = rows(con, "SELECT * FROM conversion_rules WHERE volume_code=? AND (chapter_code=? OR section_code=?) ORDER BY pdf_page_no", (quota["volume_code"], quota["chapter_code"], quota["section_code"]))
    return {"items": data, "count": len(data)}


@router.get("/api/quota-building/quota/{quota_uid}/notes")
def quota_notes(quota_uid: str) -> dict[str, Any]:
    with readonly_connect() as con:
        quota = quota_or_404(con, quota_uid)
        data = rows(con, "SELECT * FROM note_clauses WHERE volume_code=? AND (chapter_code=? OR section_code=?) ORDER BY pdf_page_no", (quota["volume_code"], quota["chapter_code"], quota["section_code"]))
    return {"items": data, "count": len(data)}


@router.get("/api/quota-building/quota/{quota_uid}/issues")
def quota_issues(quota_uid: str) -> dict[str, Any]:
    with readonly_connect() as con:
        quota = quota_or_404(con, quota_uid)
        data = rows(con, "SELECT * FROM parse_issues WHERE volume_code=? AND (source_code=? OR chapter_code=?)", (quota["volume_code"], quota["source_code"], quota["chapter_code"]))
        mapping = rows(con, "SELECT * FROM mapping_issues WHERE quota_uid=?", (quota_uid,))
    return {"items": data, "mapping_items": mapping, "count": len(data) + len(mapping)}


@router.get("/api/quota-building/bill/{bill_code_9}/evidence")
def bill_evidence(bill_code_9: str) -> dict[str, Any]:
    with readonly_connect() as con:
        bill = row(con, "SELECT * FROM bill_items WHERE bill_code_9=?", (bill_code_9,))
        if not bill:
            raise HTTPException(404, "Bill item not found")
        evidence = row(con, "SELECT * FROM evidence_backlog WHERE bill_reference_id=?", (bill["bill_reference_id"],))
        samples = rows(con, "SELECT * FROM authority_samples WHERE bill_reference_id=?", (bill["bill_reference_id"],))
    return {"bill": bill, "evidence": evidence, "samples": samples, "authority_pdf_url": "/api/quota-building/pdf/authority"}


@router.get("/api/quota-building/v1-v2")
def v1_v2() -> dict[str, Any]:
    with readonly_connect() as con:
        data = rows(con, "SELECT * FROM v1_v2_registry ORDER BY version_id")
    return {"items": data, "count": len(data)}


@router.get("/api/quota-building/pdf/province/{volume_code}")
def province_pdf(volume_code: str) -> FileResponse:
    path = VOLUME_PDFS.get(volume_code.upper())
    if not path or not path.exists():
        raise HTTPException(404, "Province quota PDF not found")
    return FileResponse(path, media_type="application/pdf")


@router.get("/api/quota-building/pdf/authority")
def authority_pdf() -> FileResponse:
    if not AUTHORITY_PDF.exists():
        raise HTTPException(404, "Authority PDF not found")
    return FileResponse(AUTHORITY_PDF, media_type="application/pdf")


@router.post("/api/quota-building/draft/action")
def draft_action(payload: DraftAction) -> dict[str, Any]:
    if payload.action_type not in ALLOWED_ACTIONS:
        raise HTTPException(400, "Unsupported draft action")
    with readonly_connect() as con:
        edge = row(con, "SELECT * FROM mapping_edges WHERE mapping_edge_id=?", (payload.source_edge_id,))
        if not edge:
            raise HTTPException(404, "Source mapping edge not found")
        if payload.action_type in {"copy", "move"}:
            target = row(con, "SELECT bill_code_9 FROM bill_items WHERE bill_code_9=?", (payload.target_bill_code_9,))
            if not target:
                raise HTTPException(400, "Target bill item is required")
            if payload.target_bill_code_9 == edge["bill_code_9"]:
                raise HTTPException(400, "Target bill must differ from source bill")
    now, draft_id = datetime.now().astimezone().isoformat(), f"DRAFT-{uuid4().hex}"
    relation = {"copy": "draft_copy", "move": "draft_move", "exclude": "draft_excluded"}[payload.action_type]
    data = {
        "draft_id": draft_id, "source_edge_id": payload.source_edge_id,
        "source_bill_code_9": edge["bill_code_9"], "target_bill_code_9": payload.target_bill_code_9,
        "quota_uid": edge["quota_uid"], "action_type": payload.action_type, "relation_type": relation,
        "draft_status": "active", "review_status": "not_reviewed", "operation_reason": payload.operation_reason,
        "created_at": now, "updated_at": now,
    }
    with draft_connect() as con:
        con.execute("INSERT INTO mapping_drafts VALUES (:draft_id,:source_edge_id,:source_bill_code_9,:target_bill_code_9,:quota_uid,:action_type,:relation_type,:draft_status,:review_status,:operation_reason,:created_at,:updated_at)", data)
        audit(con, "draft_action", draft_id, edge["bill_code_9"], edge["quota_uid"], None, data)
        con.commit()
    return {"draft": data, "approved": False}


@router.post("/api/quota-building/draft/{draft_id}/restore")
def restore_draft(draft_id: str) -> dict[str, Any]:
    with draft_connect() as con:
        before = row(con, "SELECT * FROM mapping_drafts WHERE draft_id=?", (draft_id,))
        if not before:
            raise HTTPException(404, "Draft not found")
        now = datetime.now().astimezone().isoformat()
        con.execute("UPDATE mapping_drafts SET draft_status='reverted', updated_at=? WHERE draft_id=?", (now, draft_id))
        after = row(con, "SELECT * FROM mapping_drafts WHERE draft_id=?", (draft_id,))
        audit(con, "restore", draft_id, before["source_bill_code_9"], before["quota_uid"], before, after)
        con.commit()
    return {"draft": after, "approved": False}


@router.post("/api/quota-building/review-state")
def review_state(payload: ReviewAction) -> dict[str, Any]:
    if payload.review_status not in ALLOWED_REVIEW:
        raise HTTPException(400, "Unsupported review status")
    key = f"{payload.bill_code_9}|{payload.quota_uid}"
    now = datetime.now().astimezone().isoformat()
    with draft_connect() as con:
        before = row(con, "SELECT * FROM review_states WHERE review_key=?", (key,))
        con.execute(
            "INSERT INTO review_states VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(review_key) DO UPDATE SET review_status=excluded.review_status, comment=excluded.comment, updated_at=excluded.updated_at",
            (key, payload.bill_code_9, payload.quota_uid, payload.review_status, payload.comment, before["created_at"] if before else now, now),
        )
        after = row(con, "SELECT * FROM review_states WHERE review_key=?", (key,))
        audit(con, "review_state", "", payload.bill_code_9, payload.quota_uid, before, after)
        con.commit()
    return {"review": after, "approved": False}


@router.get("/api/quota-building/draft/stats")
def draft_stats() -> dict[str, Any]:
    with draft_connect() as con:
        data = rows(con, "SELECT action_type, draft_status, COUNT(*) count FROM mapping_drafts GROUP BY action_type, draft_status")
        review = rows(con, "SELECT review_status, COUNT(*) count FROM review_states GROUP BY review_status")
        audit_count = row(con, "SELECT COUNT(*) count FROM audit_log")["count"]
    return {"drafts": data, "reviews": review, "audit_count": audit_count, "approved_count": 0}


@router.get("/api/quota-building/audit")
def audit_rows(limit: int = 200) -> dict[str, Any]:
    with draft_connect() as con:
        data = rows(con, "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (min(max(limit, 1), 1000),))
    return {"items": data, "count": len(data)}


@router.get("/api/quota-building/export/current/{bill_code_9}")
def export_current(bill_code_9: str) -> Response:
    payload = bill_rows(bill_code_9)
    return csv_response(f"quota_building_{bill_code_9}_current.csv", payload["rows"])


@router.get("/api/quota-building/export/drafts")
def export_drafts() -> Response:
    with draft_connect() as con:
        data = rows(con, "SELECT * FROM mapping_drafts ORDER BY created_at")
    return csv_response("quota_building_drafts.csv", data)


@router.get("/api/quota-building/export/audit")
def export_audit() -> Response:
    with draft_connect() as con:
        data = rows(con, "SELECT * FROM audit_log ORDER BY created_at")
    return csv_response("quota_building_audit.csv", data)
