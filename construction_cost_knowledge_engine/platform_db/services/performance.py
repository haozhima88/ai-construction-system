from __future__ import annotations

import json
import statistics
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


QUERIES = {
    "bill_tree_load": """
        SELECT appendix_code, section_code, count(*) AS row_count
        FROM reference_bill_item WHERE reference_release_id = :release_id
        GROUP BY appendix_code, section_code ORDER BY appendix_code, section_code
    """,
    "bill_candidate_mapping_load": """
        SELECT e.source_key, e.mapping_role, e.routing_class, e.semantic_score, q.source_code, q.quota_name
        FROM mapping_candidate_edge e
        JOIN reference_bill_item b ON b.reference_bill_item_id = e.reference_bill_item_id
        JOIN reference_quota_item q ON q.reference_quota_item_id = e.reference_quota_item_id
        WHERE b.bill_code_9 = :bill_code ORDER BY e.candidate_rank
    """,
    "quota_detail_load": """
        SELECT quota_uid, source_code, quota_name, unit, pdf_page_no,
               labor_fee, material_fee, machine_fee, management_fee, total_fee
        FROM reference_quota_item WHERE quota_uid = :quota_uid
    """,
    "resource_list_load": """
        SELECT r.resource_category, r.resource_code, r.resource_name, r.unit,
               r.consumption, r.unit_price, r.component_amount, r.source_page_no
        FROM reference_quota_resource r
        JOIN reference_quota_item q ON q.reference_quota_item_id = r.reference_quota_item_id
        WHERE q.quota_uid = :quota_uid ORDER BY r.source_row_order
    """,
    "mapping_search": """
        SELECT e.source_key, b.bill_code_9, b.bill_name, q.source_code, q.quota_name,
               e.mapping_role, e.risk_level, e.review_status
        FROM mapping_candidate_edge e
        JOIN reference_bill_item b ON b.reference_bill_item_id = e.reference_bill_item_id
        JOIN reference_quota_item q ON q.reference_quota_item_id = e.reference_quota_item_id
        WHERE b.bill_name ILIKE :search OR q.quota_name ILIKE :search
        ORDER BY b.bill_code_9, e.candidate_rank LIMIT 200
    """,
}


def _p95(values: list[float]) -> float:
    return sorted(values)[max(0, int(len(values) * 0.95) - 1)]


def run_performance_baseline(engine: Engine, iterations: int = 30) -> list[dict[str, Any]]:
    params = {
        "release_id": "BUILDING_A01_A03_REFERENCE_RC1", "bill_code": "010102004",
        "quota_uid": "GD:2018:A:A1-1-8", "search": "%土方%",
    }
    output = []
    with engine.connect() as connection:
        params["quota_uid"] = connection.scalar(text("""
            SELECT q.quota_uid FROM reference_quota_item q
            JOIN reference_quota_resource r ON r.reference_quota_item_id = q.reference_quota_item_id
            GROUP BY q.quota_uid ORDER BY count(*) DESC, q.quota_uid LIMIT 1
        """))
        params["bill_code"] = connection.scalar(text("""
            SELECT b.bill_code_9 FROM reference_bill_item b
            JOIN mapping_candidate_edge e ON e.reference_bill_item_id = b.reference_bill_item_id
            GROUP BY b.bill_code_9 ORDER BY count(*) DESC, b.bill_code_9 LIMIT 1
        """))
        for name, sql in QUERIES.items():
            statement = text(sql)
            durations: list[float] = []
            row_count = 0
            connection.execute(statement, params).fetchall()
            for _ in range(iterations):
                started = time.perf_counter()
                rows = connection.execute(statement, params).fetchall()
                durations.append((time.perf_counter() - started) * 1000)
                row_count = len(rows)
            plan_raw = connection.execute(text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}"), params).scalar_one()
            plan = plan_raw[0]["Plan"] if isinstance(plan_raw, list) else json.loads(plan_raw)[0]["Plan"]
            output.append({
                "query_name": name, "iterations": iterations, "p50_ms": round(statistics.median(durations), 3),
                "p95_ms": round(_p95(durations), 3), "max_ms": round(max(durations), 3),
                "row_count": row_count, "plan_node": plan.get("Node Type"),
                "plan_total_cost": plan.get("Total Cost"), "plan_actual_ms": plan.get("Actual Total Time"),
                "shared_hit_blocks": plan.get("Shared Hit Blocks", 0),
                "status": "pass" if _p95(durations) <= 500 else "review",
            })
    return output
