from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import String, cast, func, select
from sqlalchemy.engine import Engine

from platform_db.models import (
    MappingAuditEvent, MappingCandidateEdge, MappingDraftEdge, MappingWorkspace, ReferenceBillItem,
    ReferenceQuotaItem, ReferenceQuotaResource, ReferenceRuleBlock, ReferenceScopeLink,
    SourceDocument, SourcePageEvidence,
)

from platform_db.importers.common import as_decimal, as_int, read_csv


def _norm_decimal(value: Any) -> Decimal | None:
    return as_decimal(value)


def _sqlite_count(path: Path, table: str) -> int:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def run_parity_checks(
    engine: Engine,
    project_root: Path,
    workspace_name: str = "SQLite Draft Overlay Migration",
) -> list[dict[str, Any]]:
    runs = project_root / "construction_cost_knowledge_engine/data/private/reference_extraction/runs"
    gb = runs / "GB50854_2024_stageB_docx_full"
    gd = runs / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1"
    mapping = runs / "MAP_GB50854_TO_GD2018_BUILDING_A_FULL_1"
    sqlite_path = project_root / "construction_cost_knowledge_engine/web_collab_prototype/data/web_quota_building_draft.sqlite"
    rows: list[dict[str, Any]] = []

    def add(check_id: str, entity: str, field: str, expected: Any, actual: Any, mismatches: int, severity: str = "blocking") -> None:
        rows.append({
            "check_id": check_id, "entity": entity, "field_group": field,
            "expected": expected, "actual": actual, "mismatch_count": mismatches,
            "status": "pass" if mismatches == 0 else "fail", "severity": severity,
        })

    with engine.connect() as connection:
        workspace_id = connection.scalar(select(MappingWorkspace.mapping_workspace_id).where(
            MappingWorkspace.workspace_name == workspace_name
        ).order_by(MappingWorkspace.created_at).limit(1))
        if workspace_id is None:
            raise RuntimeError(f"Mapping workspace is unavailable: {workspace_name}")
        table_counts = {
            "bill": int(connection.scalar(select(func.count()).select_from(ReferenceBillItem)) or 0),
            "quota": int(connection.scalar(select(func.count()).select_from(ReferenceQuotaItem)) or 0),
            "resource": int(connection.scalar(select(func.count()).select_from(ReferenceQuotaResource)) or 0),
            "mapping_edge": int(connection.scalar(select(func.count()).select_from(MappingCandidateEdge)) or 0),
            "source_document": int(connection.scalar(select(func.count()).select_from(SourceDocument)) or 0),
            "source_page_evidence": int(connection.scalar(select(func.count()).select_from(SourcePageEvidence)) or 0),
            "rule_block": int(connection.scalar(select(func.count()).select_from(ReferenceRuleBlock)) or 0),
            "scope_link": int(connection.scalar(select(func.count()).select_from(ReferenceScopeLink)) or 0),
            "mapping_draft": int(connection.scalar(select(func.count()).select_from(MappingDraftEdge).where(
                MappingDraftEdge.mapping_workspace_id == workspace_id
            )) or 0),
            "mapping_audit": int(connection.scalar(select(func.count()).select_from(MappingAuditEvent).where(
                MappingAuditEvent.mapping_workspace_id == workspace_id
            )) or 0),
        }
        expected_counts = {
            "bill": 472, "quota": 3700, "resource": 24981, "mapping_edge": 1882,
            "source_document": 5, "source_page_evidence": 2135, "rule_block": 1842,
            "scope_link": 1295, "mapping_draft": _sqlite_count(sqlite_path, "mapping_drafts"),
            "mapping_audit": _sqlite_count(sqlite_path, "audit_log"),
        }
        for index, (name, expected) in enumerate(expected_counts.items(), start=1):
            add(f"COUNT-{index:02d}", name, "row_count", expected, table_counts[name], abs(expected - table_counts[name]))

        db_bills = {row.source_key: row for row in connection.execute(select(
            ReferenceBillItem.source_key, ReferenceBillItem.bill_code_9, ReferenceBillItem.bill_name,
            ReferenceBillItem.unit, ReferenceBillItem.project_feature_raw,
            ReferenceBillItem.quantity_calculation_rule, ReferenceBillItem.work_content_raw,
            ReferenceBillItem.source_heading_path, ReferenceBillItem.source_table_index,
            cast(ReferenceBillItem.review_status, String).label("review_status"),
        )).mappings()}
        bill_mismatch = 0
        for raw in read_csv(gb / "bill_item_reference_all_candidate.csv"):
            row = db_bills.get(raw["bill_reference_id"])
            expected = (
                raw["bill_code_9"], raw["bill_name"], raw["unit"], raw["project_feature_raw"] or None,
                raw["quantity_calculation_rule"] or None, raw["work_content_raw"] or None,
                raw["source_heading_path"], as_int(raw["source_table_index"]), "pending",
            )
            actual = tuple(row[key] for key in (
                "bill_code_9", "bill_name", "unit", "project_feature_raw", "quantity_calculation_rule",
                "work_content_raw", "source_heading_path", "source_table_index", "review_status",
            )) if row else None
            bill_mismatch += actual != expected
        add("FIELD-01", "bill", "code/name/unit/features/rule/work/locator/review", 0, bill_mismatch, bill_mismatch)

        price = {row["quota_uid"]: row for row in read_csv(gd / "gd_building_quota_price_snapshots.csv")}
        db_quotas = {row.quota_uid: row for row in connection.execute(select(
            ReferenceQuotaItem.quota_uid, ReferenceQuotaItem.source_code, ReferenceQuotaItem.quota_name,
            ReferenceQuotaItem.unit, ReferenceQuotaItem.pdf_page_no, ReferenceQuotaItem.labor_fee,
            ReferenceQuotaItem.material_fee, ReferenceQuotaItem.machine_fee, ReferenceQuotaItem.management_fee,
            ReferenceQuotaItem.total_fee, cast(ReferenceQuotaItem.review_status, String).label("review_status"),
        )).mappings()}
        quota_mismatch = 0
        for raw in read_csv(gd / "gd_building_quota_items.csv"):
            row = db_quotas.get(raw["quota_uid"]); snapshot = price[raw["quota_uid"]]
            expected = (
                raw["source_code"], raw["raw_name"], raw["unit_normalized"] or raw["unit_raw"] or None,
                as_int(raw["pdf_page_no"]), _norm_decimal(snapshot["labor_fee"]),
                _norm_decimal(snapshot["material_fee"]), _norm_decimal(snapshot["machine_fee"]),
                _norm_decimal(snapshot["management_fee"]), _norm_decimal(snapshot["total_fee"]), "pending",
            )
            actual = tuple(row[key] for key in (
                "source_code", "quota_name", "unit", "pdf_page_no", "labor_fee", "material_fee",
                "machine_fee", "management_fee", "total_fee", "review_status",
            )) if row else None
            quota_mismatch += actual != expected
        add("FIELD-02", "quota", "code/name/unit/page/fees/review", 0, quota_mismatch, quota_mismatch)

        db_resources = {row.source_key: row for row in connection.execute(select(
            ReferenceQuotaResource.source_key, ReferenceQuotaResource.resource_category,
            ReferenceQuotaResource.resource_code, ReferenceQuotaResource.resource_name,
            ReferenceQuotaResource.specification, ReferenceQuotaResource.unit,
            ReferenceQuotaResource.consumption, ReferenceQuotaResource.unit_price,
            ReferenceQuotaResource.component_amount, ReferenceQuotaResource.source_page_no,
            cast(ReferenceQuotaResource.review_status, String).label("review_status"),
        )).mappings()}
        resource_mismatch = 0
        for raw in read_csv(gd / "gd_building_resource_components.csv"):
            row = db_resources.get(raw["resource_component_id"])
            expected = (
                raw["resource_category"], raw["resource_code"] or None, raw["resource_name"],
                raw["specification"] or None, raw["unit"] or None, _norm_decimal(raw["consumption"]),
                _norm_decimal(raw["unit_price"]), _norm_decimal(raw["component_amount"]),
                as_int(raw["source_page_no"]), "pending",
            )
            actual = tuple(row[key] for key in (
                "resource_category", "resource_code", "resource_name", "specification", "unit",
                "consumption", "unit_price", "component_amount", "source_page_no", "review_status",
            )) if row else None
            resource_mismatch += actual != expected
        add("FIELD-03", "resource", "category/code/name/spec/unit/quantity/price/page/review", 0, resource_mismatch, resource_mismatch)

        db_edges = {row.source_key: row for row in connection.execute(select(
            MappingCandidateEdge.source_key, MappingCandidateEdge.mapping_role,
            MappingCandidateEdge.routing_class, MappingCandidateEdge.risk_level,
            MappingCandidateEdge.source_evidence_status,
            cast(MappingCandidateEdge.review_status, String).label("review_status"),
        )).mappings()}
        edge_mismatch = 0
        for raw in read_csv(mapping / "building_bill_to_quota_edges.csv"):
            row = db_edges.get(raw["mapping_edge_id"])
            expected = (raw["mapping_role"], raw["routing_class"], raw["risk_level"], raw["source_evidence_status"], "pending")
            actual = tuple(row[key] for key in ("mapping_role", "routing_class", "risk_level", "source_evidence_status", "review_status")) if row else None
            edge_mismatch += actual != expected
        add("FIELD-04", "mapping_edge", "role/routing/risk/evidence/review", 0, edge_mismatch, edge_mismatch)

        approved = 0
        for table in (ReferenceBillItem, ReferenceQuotaItem, ReferenceQuotaResource, ReferenceRuleBlock, ReferenceScopeLink, MappingCandidateEdge):
            approved += int(connection.scalar(select(func.count()).select_from(table).where(cast(table.review_status, String) == "approved")) or 0)
        add("STATE-01", "reference_mapping", "approved_count", 0, approved, approved)
    return rows
