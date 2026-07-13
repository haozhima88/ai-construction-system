from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from web_collab_prototype.quota_building import router as quota_building_router


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DB_PATH = BASE_DIR / "data" / "web_collab_readonly.sqlite"
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_PATH = BASE_DIR / "templates" / "index.html"
BID_TEMPLATE_PATH = BASE_DIR / "templates" / "bid_index.html"
QUOTA_A111_TEMPLATE_PATH = BASE_DIR / "templates" / "quota_a111_index.html"
RUN_DIR = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs" / "WEB_COLLAB_PROTOTYPE_STABILIZATION_1"
UI_ALIGNMENT_RUN_DIR = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs" / "BID_COLLAB_UI_STRUCTURE_ALIGNMENT_1"
UI_CONSISTENCY_CSV = UI_ALIGNMENT_RUN_DIR / "bid_code_name_consistency_audit.csv"
UI_COMPOSITION_CSV = UI_ALIGNMENT_RUN_DIR / "web_bid_composition_preview_rows.csv"
UI_CANDIDATE_POOL_CSV = UI_ALIGNMENT_RUN_DIR / "web_bid_candidate_pool_ranked.csv"
STANDARD_FIRST_RUN_DIR = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs" / "BID_COLLAB_STANDARD_FIRST_STRUCTURE_1"
GB_STANDARD_TREE_CSV = STANDARD_FIRST_RUN_DIR / "web_gb_standard_tree_nodes.csv"
GB_BILL_BID_ITEM_CSV = STANDARD_FIRST_RUN_DIR / "web_gb_bill_bid_item_rows.csv"
GB_BILL_COMPOSITION_CSV = STANDARD_FIRST_RUN_DIR / "web_gb_bill_quota_composition_rows.csv"
BID_SOURCE_FILTER_CSV = STANDARD_FIRST_RUN_DIR / "web_bid_source_filter_nodes.csv"
GLODON_REFINEMENT_RUN_DIR = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs" / "BID_COLLAB_GLODON_STRUCTURE_REFINEMENT_1"
WEB_BID_BOTTOM_TABS_MODEL_CSV = GLODON_REFINEMENT_RUN_DIR / "web_bid_bottom_tabs_model.csv"
WEB_BID_QUERY_PANEL_MODEL_CSV = GLODON_REFINEMENT_RUN_DIR / "web_bid_query_panel_model.csv"
QUOTA_A111_VIEWER_RUN_DIR = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs" / "WEB_QUOTA_A111_PDF_DETAIL_VIEWER_1"
QUOTA_A111_TREE_CSV = QUOTA_A111_VIEWER_RUN_DIR / "web_quota_a111_bill_tree.csv"
QUOTA_A111_BILL_ROWS_CSV = QUOTA_A111_VIEWER_RUN_DIR / "web_quota_a111_bill_to_quota_rows.csv"
QUOTA_A111_DETAIL_CSV = QUOTA_A111_VIEWER_RUN_DIR / "web_quota_a111_quota_detail_rows.csv"
QUOTA_A111_RESOURCE_CSV = QUOTA_A111_VIEWER_RUN_DIR / "web_quota_a111_resource_rows.csv"
QUOTA_A111_TAB_MODEL_CSV = QUOTA_A111_VIEWER_RUN_DIR / "web_quota_a111_tab_model.csv"
QUOTA_A111_MAPPING_DRAFT_RUN_DIR = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs" / "WEB_QUOTA_A111_MAPPING_DRAFT_1"
QUOTA_A111_MAPPING_DRAFT_EXPORT_CSV = QUOTA_A111_MAPPING_DRAFT_RUN_DIR / "web_quota_a111_mapping_draft_export.csv"
QUOTA_A111_MAPPING_DRAFT_AUDIT_EXPORT_CSV = QUOTA_A111_MAPPING_DRAFT_RUN_DIR / "web_quota_a111_mapping_draft_audit_export.csv"
QUOTA_A111_FULL_REVIEW_RUN_DIR = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs" / "GD2018_PDF_A111_FULL_REVIEW_PACK_1"
QUOTA_A111_WORK_CONTENT_SOURCE_CSV = QUOTA_A111_FULL_REVIEW_RUN_DIR / "work_content_by_quota_137.csv"
QUOTA_A111_QUANTITY_RULE_SOURCE_CSV = QUOTA_A111_FULL_REVIEW_RUN_DIR / "quantity_rule_by_quota_137.csv"
QUOTA_A111_REFINEMENT_RUN_DIR = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs" / "WEB_QUOTA_A111_DRAFT_COUNTS_DETAIL_REFINEMENT_1"
QUOTA_A111_TREE_DRAFT_STATS_CSV = QUOTA_A111_REFINEMENT_RUN_DIR / "web_quota_a111_tree_draft_stats.csv"
QUOTA_A111_WORK_CONTENT_DISPLAY_CSV = QUOTA_A111_REFINEMENT_RUN_DIR / "web_quota_a111_work_content_display_model.csv"
QUOTA_A111_QUANTITY_RULE_DISPLAY_CSV = QUOTA_A111_REFINEMENT_RUN_DIR / "web_quota_a111_quantity_rule_display_model.csv"
QUOTA_A111_PDF_SOURCE = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "source_standards" / "广东省建设工程综合定额(2018)" / "A01_广东省房屋建筑与装饰工程定额(上册).pdf"
QUOTA_A111_QUANTITY_RULE_PAGE_SOURCE_CSV = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs" / "GD2018_PDF_A111_STRUCTURED_CANDIDATE_1" / "quota_pdf_quantity_rule_A111_candidate.csv"
QUOTA_A111_DUAL_VIEW_RUN_DIR = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs" / "WEB_QUOTA_A111_QUANTITY_RULE_DUAL_VIEW_1"
QUOTA_A111_RULE_SOURCE_BLOCKS_CSV = QUOTA_A111_DUAL_VIEW_RUN_DIR / "quantity_rule_source_blocks.csv"
QUOTA_A111_RULE_SCOPE_LINKS_CSV = QUOTA_A111_DUAL_VIEW_RUN_DIR / "quantity_rule_scope_links.csv"
QUOTA_A111_RULE_DUPLICATE_AUDIT_CSV = QUOTA_A111_DUAL_VIEW_RUN_DIR / "quantity_rule_duplicate_audit.csv"
QUOTA_A111_RULE_SOURCE_PAGE_INDEX_CSV = QUOTA_A111_DUAL_VIEW_RUN_DIR / "quantity_rule_source_page_index.csv"
EXPORT_DIR = RUN_DIR / "exports"
CURRENT_EXPORT_PATH = RUN_DIR / "web_review_writeback_test_export.csv"
DRAFT_SNAPSHOT_MANIFEST = RUN_DIR / "draft_export_snapshot_manifest.csv"
AUDIT_SNAPSHOT_MANIFEST = RUN_DIR / "audit_log_export_snapshot_manifest.csv"

DRAFT_EXPORT_FIELDS = [
    "bill_code_9",
    "quota_source_code",
    "selected_price_source",
    "draft_labor_fee",
    "draft_material_fee",
    "draft_machine_fee",
    "draft_management_fee",
    "draft_total_fee",
    "total_manual_override",
    "draft_status",
    "lock_status",
    "draft_version",
    "save_status",
    "cost_engineer_comment",
    "created_at",
    "updated_at",
    "exported_at",
    "exported_batch_id",
]
AUDIT_EXPORT_FIELDS = [
    "log_id",
    "action_type",
    "bill_code_9",
    "quota_source_code",
    "before_json",
    "after_json",
    "created_at",
    "actor",
]

ALLOWED_DRAFT_STATUS = {"draft", "reviewed_test", "deferred", "rejected"}
ALLOWED_SAVE_STATUS = {"saved", "autosaved", "failed_retry", "exported"}
ALLOWED_LOCK_STATUS = {"draft", "reviewed_test", "locked_by_cost_engineer", "deferred", "rejected"}
QUOTA_A111_DRAFT_ACTION_TYPES = {"copy_link", "move_link", "exclude_link", "restore_original"}
QUOTA_A111_DRAFT_RELATION_TYPES = {
    "original_candidate",
    "draft_copy",
    "draft_move_target",
    "draft_move_source_excluded",
    "draft_excluded",
    "restored",
}
QUOTA_A111_DRAFT_STATUSES = {"pending", "active", "excluded", "reverted"}
QUOTA_A111_DRAFT_EDGE_FIELDS = [
    "draft_edge_id",
    "source_edge_id",
    "source_bill_code_9",
    "source_bill_name",
    "target_bill_code_9",
    "target_bill_name",
    "quota_source_code",
    "quota_name",
    "action_type",
    "relation_type",
    "draft_status",
    "operation_reason",
    "created_at",
    "updated_at",
    "reviewer",
    "comment",
]
QUOTA_A111_DRAFT_AUDIT_FIELDS = [
    "audit_id",
    "event_type",
    "draft_edge_id",
    "quota_source_code",
    "source_bill_code_9",
    "target_bill_code_9",
    "action_type",
    "payload_json",
    "created_at",
    "remark",
]
QUOTA_A111_TREE_DRAFT_STATS_FIELDS = [
    "bill_code_9",
    "bill_name",
    "original_candidate_count",
    "copy_in_count",
    "move_in_count",
    "move_out_count",
    "excluded_count",
    "reverted_count",
    "effective_candidate_count",
    "draft_active_count",
    "has_draft_change",
    "risk_level",
]
QUOTA_A111_WORK_CONTENT_DISPLAY_FIELDS = [
    "quota_source_code",
    "quota_name",
    "item_order",
    "item_no",
    "item_text",
    "source_raw_text",
    "split_method",
    "split_confidence",
    "display_status",
    "remark",
]
QUOTA_A111_QUANTITY_RULE_DISPLAY_FIELDS = [
    "quota_source_code",
    "quota_name",
    "rule_group_order",
    "rule_group_no",
    "rule_group_title",
    "clause_order",
    "clause_no",
    "clause_level",
    "clause_text",
    "applicable_section",
    "applicable_quota_code_range",
    "rule_scope",
    "requires_manual_scope_review",
    "pdf_page_no",
    "book_page_no",
    "source_raw_text",
    "split_method",
    "split_confidence",
    "remark",
]
QUOTA_A111_RULE_SOURCE_BLOCK_FIELDS = [
    "rule_block_id",
    "source_file",
    "source_hash",
    "pdf_page_no",
    "book_page_no",
    "source_order",
    "block_type",
    "rule_no",
    "rule_level",
    "rule_title",
    "raw_text",
    "table_json",
    "source_bbox",
    "parse_status",
    "remark",
]
QUOTA_A111_RULE_SCOPE_LINK_FIELDS = [
    "scope_link_id",
    "rule_block_id",
    "scope_type",
    "appendix_code",
    "section_code",
    "quota_code_start",
    "quota_code_end",
    "specific_quota_source_code",
    "scope_confidence",
    "requires_manual_scope_review",
    "remark",
]
QUOTA_A111_RULE_DUPLICATE_AUDIT_FIELDS = [
    "duplicate_group_id",
    "source_signature",
    "original_record_count",
    "distinct_quota_count",
    "representative_quota_source_code",
    "rule_group_order",
    "clause_order",
    "clause_no",
    "rule_level",
    "deduplicated_rule_block_id",
    "duplicate_record_count_removed",
    "status",
    "remark",
]
QUOTA_A111_RULE_SOURCE_PAGE_INDEX_FIELDS = [
    "page_index_id",
    "source_file",
    "source_hash",
    "pdf_page_no",
    "book_page_no",
    "source_url",
    "block_count",
    "rule_block_ids",
    "render_mode",
    "table_render_mode",
    "watermark_policy",
    "status",
    "remark",
]

WORK_CONTENT_MARKER_RE = re.compile(
    r"(?<!\S)(?P<marker>(?:\d{1,2}[.、](?!\d)|（[一二三四五六七八九十]+）|[①-⑳]))"
)
QUANTITY_RULE_MARKER_RE = re.compile(
    r"(?<!\d)(?P<marker>(?:"
    r"[一二三四五六七八九十]+、(?=(?:一般计算规则|土方工程|石方工程|回填方及其他))"
    r"|（[一二三四五六七八九十]+）"
    r"|\d{1,2}[.、](?!\d)"
    r"|\d{1,2}）"
    r"|[（(]\d{1,2}[）)]"
    r"|[①-⑳]"
    r"))"
)

app = FastAPI(title="Construction Cost Web Collaboration Prototype")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(quota_building_router)


class DraftPayload(BaseModel):
    bill_code_9: str
    quota_source_code: str
    decision_scope: str = "bill_quota_context"
    selected_price_source: str = "manual_enterprise_draft"
    draft_labor_fee: float | None = None
    draft_material_fee: float | None = None
    draft_machine_fee: float | None = None
    draft_management_fee: float | None = None
    draft_total_fee: float | None = None
    total_manual_override: bool = False
    draft_status: str = "draft"
    lock_status: str = "draft"
    save_status: str = "saved"
    local_cache_key: str | None = None
    cost_engineer_comment: str | None = ""
    actor: str = "prototype_user"


class ClearDraftPayload(BaseModel):
    bill_code_9: str
    quota_source_code: str
    actor: str = "prototype_user"


class QuotaA111DraftEdgePayload(BaseModel):
    source_edge_id: str
    source_bill_code_9: str
    source_bill_name: str = ""
    target_bill_code_9: str = ""
    target_bill_name: str = ""
    quota_source_code: str
    quota_name: str = ""
    action_type: str
    operation_reason: str = ""
    reviewer: str = ""
    comment: str = ""


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"SQLite view model not found: {DB_PATH}")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    ensure_draft_tables(con)
    return con


def ensure_column(con: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def ensure_draft_tables(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS web_price_review_draft (
            draft_id TEXT PRIMARY KEY,
            bill_code_9 TEXT NOT NULL,
            quota_source_code TEXT NOT NULL,
            decision_scope TEXT DEFAULT 'bill_quota_context',
            selected_price_source TEXT,
            draft_labor_fee REAL,
            draft_material_fee REAL,
            draft_machine_fee REAL,
            draft_management_fee REAL,
            draft_total_fee REAL,
            total_manual_override INTEGER DEFAULT 0,
            draft_status TEXT DEFAULT 'draft',
            cost_engineer_comment TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            draft_version INTEGER DEFAULT 1,
            save_status TEXT DEFAULT 'saved',
            last_saved_at TEXT,
            local_cache_key TEXT,
            exported_at TEXT,
            exported_batch_id TEXT,
            lock_status TEXT DEFAULT 'draft',
            UNIQUE (bill_code_9, quota_source_code)
        )
        """
    )
    for column, ddl in [
        ("draft_version", "INTEGER DEFAULT 1"),
        ("save_status", "TEXT DEFAULT 'saved'"),
        ("last_saved_at", "TEXT"),
        ("local_cache_key", "TEXT"),
        ("exported_at", "TEXT"),
        ("exported_batch_id", "TEXT"),
        ("lock_status", "TEXT DEFAULT 'draft'"),
    ]:
        ensure_column(con, "web_price_review_draft", column, ddl)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS web_audit_log (
            log_id TEXT PRIMARY KEY,
            action_type TEXT NOT NULL,
            bill_code_9 TEXT,
            quota_source_code TEXT,
            before_json TEXT,
            after_json TEXT,
            created_at TEXT NOT NULL,
            actor TEXT DEFAULT 'prototype_user'
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS web_quota_a111_mapping_draft_edges (
            draft_edge_id TEXT PRIMARY KEY,
            source_edge_id TEXT,
            source_bill_code_9 TEXT,
            source_bill_name TEXT,
            target_bill_code_9 TEXT,
            target_bill_name TEXT,
            quota_source_code TEXT NOT NULL,
            quota_name TEXT,
            action_type TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            draft_status TEXT NOT NULL,
            operation_reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            reviewer TEXT,
            comment TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS web_quota_a111_mapping_draft_audit_log (
            audit_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            draft_edge_id TEXT,
            quota_source_code TEXT,
            source_bill_code_9 TEXT,
            target_bill_code_9 TEXT,
            action_type TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            remark TEXT
        )
        """
    )
    con.commit()


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    if "total_manual_override" in result and result["total_manual_override"] is not None:
        result["total_manual_override"] = bool(result["total_manual_override"])
    return result


def fetch_one(con: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    return row_dict(con.execute(sql, params).fetchone())


def fetch_all(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    rows = [dict(row) for row in con.execute(sql, params).fetchall()]
    for row in rows:
        if "total_manual_override" in row and row["total_manual_override"] is not None:
            row["total_manual_override"] = bool(row["total_manual_override"])
    return rows


def draft_id(bill_code_9: str, quota_source_code: str) -> str:
    safe_bill = "".join(ch for ch in bill_code_9 if ch.isalnum())
    safe_quota = "".join(ch for ch in quota_source_code if ch.isalnum())
    return f"DRAFT-{safe_bill}-{safe_quota}"


def normalize_status(value: str, allowed: set[str], fallback: str) -> str:
    return value if value in allowed and value != "approved" else fallback


def normalize_payload(payload: DraftPayload, previous: dict[str, Any] | None) -> dict[str, Any]:
    draft_status = normalize_status(payload.draft_status, ALLOWED_DRAFT_STATUS, "draft")
    save_status = normalize_status(payload.save_status, ALLOWED_SAVE_STATUS, "saved")
    lock_status = normalize_status(payload.lock_status, ALLOWED_LOCK_STATUS, "draft")
    components = [
        payload.draft_labor_fee,
        payload.draft_material_fee,
        payload.draft_machine_fee,
        payload.draft_management_fee,
    ]
    present_components = [v for v in components if v is not None]
    manual_override = payload.total_manual_override
    risk_note = ""
    if manual_override:
        total = payload.draft_total_fee
    elif present_components:
        total = sum(float(v or 0) for v in components)
    elif payload.draft_total_fee is not None:
        total = payload.draft_total_fee
        manual_override = True
        risk_note = "省定额人材机管细项缺失，仅采用合计，需人工确认"
    else:
        total = None
    comment = payload.cost_engineer_comment or ""
    if risk_note and risk_note not in comment:
        comment = f"{comment}；{risk_note}" if comment else risk_note
    previous_version = int(previous.get("draft_version") or 0) if previous else 0
    return {
        "draft_id": draft_id(payload.bill_code_9, payload.quota_source_code),
        "bill_code_9": payload.bill_code_9,
        "quota_source_code": payload.quota_source_code,
        "decision_scope": payload.decision_scope or "bill_quota_context",
        "selected_price_source": payload.selected_price_source or "manual_enterprise_draft",
        "draft_labor_fee": payload.draft_labor_fee,
        "draft_material_fee": payload.draft_material_fee,
        "draft_machine_fee": payload.draft_machine_fee,
        "draft_management_fee": payload.draft_management_fee,
        "draft_total_fee": total,
        "total_manual_override": 1 if manual_override else 0,
        "draft_status": draft_status,
        "lock_status": lock_status,
        "save_status": save_status,
        "local_cache_key": payload.local_cache_key or f"web_collab_draft_cache::{payload.bill_code_9}::{payload.quota_source_code}",
        "draft_version": previous_version + 1,
        "cost_engineer_comment": comment,
    }


def write_audit(
    con: sqlite3.Connection,
    action_type: str,
    bill_code_9: str,
    quota_source_code: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    actor: str,
) -> None:
    con.execute(
        """
        INSERT INTO web_audit_log
        (log_id, action_type, bill_code_9, quota_source_code, before_json, after_json, created_at, actor)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            action_type,
            bill_code_9,
            quota_source_code,
            json.dumps(before, ensure_ascii=False) if before else "",
            json.dumps(after, ensure_ascii=False) if after else "",
            datetime.now().isoformat(timespec="seconds"),
            actor or "prototype_user",
        ),
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


@lru_cache(maxsize=16)
def read_artifact_csv(path_text: str) -> list[dict[str, str]]:
    path = Path(path_text)
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"UI alignment artifact not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def artifact_rows(path: Path) -> list[dict[str, str]]:
    return read_artifact_csv(str(path))


BID_ARTIFACT_BAD_TOKENS = ("????", "???", "锟", "閿", "闁跨喐鏋婚幏", "鑼傜椹", "\ufffd")


def bid_value_has_placeholder(value: str) -> bool:
    return any(token in value for token in BID_ARTIFACT_BAD_TOKENS)


def clean_bid_artifact_value(field: str, value: str) -> str:
    if not bid_value_has_placeholder(value):
        return value
    replacements = {
        "GB/T 50854-2024 ????????????????": "GB/T 50854-2024 房屋建筑与装饰工程工程量计算标准",
        "UNMATCHED ??? / ????": "UNMATCHED 未匹配 / 人工处理",
        "??? / ????": "未匹配 / 人工处理",
        "UNMATCHED ????? GB/T 50854 baseline": "UNMATCHED 无法挂接到 GB/T 50854 baseline",
        "????? GB/T 50854 baseline": "无法挂接到 GB/T 50854 baseline",
        "??????? 040103002": "未匹配国标清单 040103002",
        "???????": "投标来源筛选器",
    }
    cleaned = value
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    if bid_value_has_placeholder(cleaned):
        if field in {"label", "bill_name"}:
            return "未匹配国标清单"
        if field in {"appendix_name"}:
            return "未匹配 / 人工处理"
        if field in {"section_name"}:
            return "无法挂接到 GB/T 50854 baseline"
        if field in {
            "display_name",
            "supplement_name",
            "quota_name_candidate",
            "bid_item_name",
            "gb_bill_name",
        }:
            return "未匹配名称 / 人工复核"
        if field in {"display_code", "supplement_candidate_code", "quota_source_code"}:
            return "manual_review"
        if field in {"remark", "risk_flags", "row_status", "unit_conversion_note", "calculation_process"}:
            return "需人工复核"
        return "需人工复核"
    return cleaned


def clean_bid_artifact_row(row: dict[str, str]) -> dict[str, str]:
    return {key: clean_bid_artifact_value(key, value) for key, value in row.items()}


def clean_bid_artifact_payload(value: Any, field: str = "") -> Any:
    if isinstance(value, dict):
        return {key: clean_bid_artifact_payload(child, key) for key, child in value.items()}
    if isinstance(value, list):
        return [clean_bid_artifact_payload(child, field) for child in value]
    if isinstance(value, str):
        return clean_bid_artifact_value(field, value)
    return value


MOJIBAKE_TOKENS = ("????", "锟", "閿熸枻鎷", "茂禄驴", "\ufffd", "鎷", "鈥", "锛", "銆")


def has_mojibake(value: Any) -> bool:
    text = str(value or "")
    return any(token in text for token in MOJIBAKE_TOKENS)


def clean_bid_tree_row(row: dict[str, str]) -> dict[str, str]:
    cleaned = dict(row)
    if cleaned.get("node_id") == "GBROOT-50854-2024" or has_mojibake(cleaned.get("label")):
        if cleaned.get("node_type") == "root":
            cleaned["label"] = "GB/T 50854-2024 房屋建筑与装饰工程工程量计算标准"
            cleaned["tree_path"] = cleaned["label"]
    return cleaned


def bottom_tabs_model() -> list[dict[str, str]]:
    return [
        {
            "tab_id": "candidate_pool",
            "tab_name": "候选池",
            "data_source": "web_bid_candidate_pool_ranked.csv",
            "implemented_status": "implemented_readonly",
            "display_rule": "默认显示当前 bid item 的 Top 候选，可切换查看全部候选。",
            "remark": "只读预览，不插入，不保存映射草稿。",
        },
        {
            "tab_id": "feature_content",
            "tab_name": "特征及内容",
            "data_source": "web_gb_bill_bid_item_rows.csv + GB/T bill fields",
            "implemented_status": "implemented_readonly",
            "display_rule": "展示投标清单完整项目特征、GB/T 项目特征和工作内容摘要。",
            "remark": "用于造价人员核对清单本体与推荐定额是否同对象。",
        },
        {
            "tab_id": "quantity_detail",
            "tab_name": "工程量明细",
            "data_source": "import_bid_records normalized fields",
            "implemented_status": "implemented_readonly",
            "display_rule": "展示工程量；若无表达式或公式则提示暂未接入计算过程。",
            "remark": "本轮不做工程量复算。",
        },
        {
            "tab_id": "price_breakdown",
            "tab_name": "价格构成",
            "data_source": "web_bid_composition_preview_rows.csv + candidate pool",
            "implemented_status": "implemented_readonly",
            "display_rule": "展示推荐定额省定额合计、企业候选价和差异提示。",
            "remark": "不做成本测算，不生成报价。",
        },
        {
            "tab_id": "resource_preview",
            "tab_name": "工料机预览",
            "data_source": "pending resource detail source",
            "implemented_status": "placeholder_readonly",
            "display_rule": "当前未接入完整工料机明细时显示暂未接入。",
            "remark": "后续接入资源明细后再展开。",
        },
        {
            "tab_id": "notes",
            "tab_name": "说明信息",
            "data_source": "consistency audit + review status + risk flags",
            "implemented_status": "implemented_readonly",
            "display_rule": "展示编码-名称一致性、风险提示和 review_status。",
            "remark": "用于人工复核优先级判断。",
        },
    ]


def query_panel_model() -> list[dict[str, str]]:
    return [
        {
            "panel_tab": "清单索引",
            "source_type": "GB/T 50854 standard bill index",
            "search_supported": "true",
            "filter_supported": "true",
            "insert_enabled": "false",
            "current_status": "readonly_preview",
            "remark": "用于定位 GB/T 清单项，不能插入或保存。",
        },
        {
            "panel_tab": "清单",
            "source_type": "import_bid_records grouped bid item",
            "search_supported": "true",
            "filter_supported": "true",
            "insert_enabled": "false",
            "current_status": "readonly_preview",
            "remark": "展示投标清单实例，后续才进入 draft 保存。",
        },
        {
            "panel_tab": "定额",
            "source_type": "GD2018 recommended quota candidate",
            "search_supported": "true",
            "filter_supported": "true",
            "insert_enabled": "false",
            "current_status": "readonly_preview",
            "remark": "仅预览候选定额，不写入映射结果。",
        },
        {
            "panel_tab": "人材机",
            "source_type": "resource detail placeholder",
            "search_supported": "false",
            "filter_supported": "false",
            "insert_enabled": "false",
            "current_status": "not_connected",
            "remark": "完整工料机明细尚未接入。",
        },
        {
            "panel_tab": "我的数据",
            "source_type": "enterprise supplement / enterprise price candidate",
            "search_supported": "true",
            "filter_supported": "true",
            "insert_enabled": "false",
            "current_status": "readonly_preview",
            "remark": "企业补子目以 ENT-SUP 展示，不伪造成 A1-*。",
        },
    ]


def find_bid_item_from_artifact(bid_item_id: str) -> dict[str, str] | None:
    return next(
        (
            clean_bid_artifact_row(row)
            for row in artifact_rows(GB_BILL_BID_ITEM_CSV)
            if row.get("bid_item_id") == bid_item_id
        ),
        None,
    )


def item_composition_rows(bid_item_id: str) -> list[dict[str, str]]:
    rows = [
        clean_bid_artifact_row(row)
        for row in artifact_rows(UI_COMPOSITION_CSV)
        if row.get("parent_bid_item_id") == bid_item_id
    ]
    rows.sort(key=lambda row: int(row.get("display_order") or 0))
    return rows


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_snapshot_manifest(path: Path, snapshot_type: str, snapshot_path: Path, row_count: int) -> None:
    row = {
        "snapshot_type": snapshot_type,
        "snapshot_file": str(snapshot_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "exists": str(snapshot_path.exists()).lower(),
        "row_count": row_count,
        "sha256": sha256(snapshot_path) if snapshot_path.exists() else "",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "ready" if snapshot_path.exists() else "missing",
        "remark": "prototype snapshot export",
    }
    write_csv(path, [row], ["snapshot_type", "snapshot_file", "exists", "row_count", "sha256", "created_at", "status", "remark"])


@app.get("/")
def index() -> FileResponse:
    return FileResponse(TEMPLATE_PATH)



@app.get("/bid")
def bid_index() -> FileResponse:
    return FileResponse(BID_TEMPLATE_PATH)


@app.get("/quota-a111")
def quota_a111_index() -> FileResponse:
    return FileResponse(QUOTA_A111_TEMPLATE_PATH)


def quota_a111_tree_rows() -> list[dict[str, str]]:
    rows = artifact_rows(QUOTA_A111_TREE_CSV)
    rows.sort(key=lambda row: int(row.get("display_order") or 0))
    return rows


def quota_a111_bill_rows() -> list[dict[str, str]]:
    rows = artifact_rows(QUOTA_A111_BILL_ROWS_CSV)
    rows.sort(key=lambda row: int(row.get("display_order") or 0))
    return rows


def quota_a111_detail_rows() -> list[dict[str, str]]:
    rows = artifact_rows(QUOTA_A111_DETAIL_CSV)
    rows.sort(key=lambda row: row.get("quota_source_code", ""))
    return rows


def quota_a111_resource_rows() -> list[dict[str, str]]:
    rows = artifact_rows(QUOTA_A111_RESOURCE_CSV)
    rows.sort(
        key=lambda row: (
            row.get("quota_source_code", ""),
            int(row.get("resource_display_order") or 0),
        )
    )
    return rows


def quota_a111_work_content_source_rows() -> list[dict[str, str]]:
    rows = artifact_rows(QUOTA_A111_WORK_CONTENT_SOURCE_CSV)
    rows.sort(key=lambda row: row.get("quota_source_code", ""))
    return rows


def quota_a111_quantity_rule_source_rows() -> list[dict[str, str]]:
    rows = artifact_rows(QUOTA_A111_QUANTITY_RULE_SOURCE_CSV)
    rows.sort(key=lambda row: row.get("quota_source_code", ""))
    return rows


def quota_a111_marker_label(marker: str) -> str:
    if re.fullmatch(r"\d{1,2}[.、）]", marker):
        return re.match(r"\d{1,2}", marker).group(0)
    return marker


def quota_a111_work_split_method(marker: str) -> str:
    if marker.endswith("."):
        return "numbered_regex_dot"
    if marker.endswith("、"):
        return "numbered_regex_dunhao"
    if marker.startswith("（"):
        return "numbered_regex_cn_parenthesis"
    return "numbered_regex_circled"


def quota_a111_work_fallback_row(source: dict[str, str], raw_text: str, remark: str) -> dict[str, str]:
    try:
        source_confidence = float(source.get("parse_confidence") or 0)
    except ValueError:
        source_confidence = 0
    return {
        "quota_source_code": source.get("quota_source_code", ""),
        "quota_name": source.get("quota_name_from_pdf", ""),
        "item_order": "1",
        "item_no": "",
        "item_text": raw_text,
        "source_raw_text": raw_text,
        "split_method": "raw_fallback",
        "split_confidence": f"{min(source_confidence or 0.45, 0.45):.2f}",
        "display_status": "needs_manual_review",
        "remark": remark,
    }


def quota_a111_split_work_content(source: dict[str, str]) -> list[dict[str, str]]:
    raw_text = source.get("work_content_raw") or source.get("work_content_normalized") or ""
    matches = list(WORK_CONTENT_MARKER_RE.finditer(raw_text))
    if not raw_text or not matches or raw_text[: matches[0].start()].strip():
        return [quota_a111_work_fallback_row(source, raw_text, "numbered boundary not reliable; raw text preserved")]

    segments: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
        item_text = raw_text[match.end() : end].strip()
        if not item_text:
            return [quota_a111_work_fallback_row(source, raw_text, "empty numbered segment; raw text preserved")]
        segments.append((match.group("marker"), item_text))

    try:
        source_confidence = float(source.get("parse_confidence") or 0.82)
    except ValueError:
        source_confidence = 0.82
    confidence = min(max(source_confidence, 0.70), 0.95)
    return [
        {
            "quota_source_code": source.get("quota_source_code", ""),
            "quota_name": source.get("quota_name_from_pdf", ""),
            "item_order": str(index),
            "item_no": quota_a111_marker_label(marker),
            "item_text": item_text,
            "source_raw_text": raw_text,
            "split_method": quota_a111_work_split_method(marker),
            "split_confidence": f"{confidence:.2f}",
            "display_status": "display_ready",
            "remark": "display-only split; source text and order preserved",
        }
        for index, (marker, item_text) in enumerate(segments, start=1)
    ]


@lru_cache(maxsize=1)
def quota_a111_work_content_display_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source in quota_a111_work_content_source_rows():
        rows.extend(quota_a111_split_work_content(source))
    return rows


def quota_a111_rule_marker_level(marker: str) -> str:
    if re.fullmatch(r"[一二三四五六七八九十]+、", marker):
        return "section"
    if re.fullmatch(r"（[一二三四五六七八九十]+）", marker):
        return "subsection"
    if re.fullmatch(r"\d{1,2}[.、]", marker):
        return "clause"
    return "subclause"


def quota_a111_rule_marker_label(marker: str) -> str:
    if marker.endswith("、") and re.fullmatch(r"[一二三四五六七八九十]+、", marker):
        return marker[:-1]
    if re.fullmatch(r"\d{1,2}[.、）]", marker):
        return re.match(r"\d{1,2}", marker).group(0)
    return marker


def quota_a111_rule_group_title(clause_text: str) -> str:
    for title in ("一般计算规则", "土方工程", "石方工程", "回填方及其他"):
        if clause_text.startswith(title):
            return title
    return clause_text.split(maxsplit=1)[0] if clause_text else "未识别规则组"


def quota_a111_rule_scope(source: dict[str, str]) -> tuple[str, bool]:
    manual = str(source.get("requires_manual_scope_review", "")).strip().lower() in {"1", "true", "yes", "y"}
    source_scope = source.get("rule_scope", "")
    allowed = {"quota_level", "quota_range", "subsection_level", "section_level", "chapter_level"}
    if manual or source_scope not in allowed:
        return "uncertain", True
    return source_scope, False


def quota_a111_quantity_fallback_row(source: dict[str, str], raw_text: str) -> dict[str, str]:
    return {
        "quota_source_code": source.get("quota_source_code", ""),
        "quota_name": source.get("quota_name_from_pdf", ""),
        "rule_group_order": "1",
        "rule_group_no": "",
        "rule_group_title": "未可靠拆分",
        "clause_order": "1",
        "clause_no": "",
        "clause_level": "raw",
        "clause_text": raw_text,
        "applicable_section": source.get("applicable_section", ""),
        "applicable_quota_code_range": source.get("applicable_quota_code_range", ""),
        "rule_scope": "uncertain",
        "requires_manual_scope_review": "true",
        "pdf_page_no": source.get("pdf_page_no", ""),
        "book_page_no": source.get("book_page_no", ""),
        "source_raw_text": raw_text,
        "split_method": "raw_fallback",
        "split_confidence": "0.35",
        "remark": "hierarchy boundary not reliable; raw text preserved",
    }


def quota_a111_split_quantity_rule(source: dict[str, str]) -> list[dict[str, str]]:
    raw_text = source.get("applicable_rule_text") or ""
    matches = list(QUANTITY_RULE_MARKER_RE.finditer(raw_text))
    if not raw_text or not matches:
        return [quota_a111_quantity_fallback_row(source, raw_text)]

    rule_scope, manual_scope = quota_a111_rule_scope(source)
    rows: list[dict[str, str]] = []
    group_order = 0
    group_no = ""
    group_title = "工程量计算规则"
    clause_order_by_group: dict[int, int] = {}

    prefix = raw_text[: matches[0].start()].strip()
    if prefix:
        rows.append(
            {
                "quota_source_code": source.get("quota_source_code", ""),
                "quota_name": source.get("quota_name_from_pdf", ""),
                "rule_group_order": "0",
                "rule_group_no": "",
                "rule_group_title": "工程量计算规则",
                "clause_order": "1",
                "clause_no": "",
                "clause_level": "raw",
                "clause_text": prefix,
                "applicable_section": source.get("applicable_section", ""),
                "applicable_quota_code_range": source.get("applicable_quota_code_range", ""),
                "rule_scope": rule_scope,
                "requires_manual_scope_review": str(manual_scope).lower(),
                "pdf_page_no": source.get("pdf_page_no", ""),
                "book_page_no": source.get("book_page_no", ""),
                "source_raw_text": raw_text,
                "split_method": "hierarchy_regex_preamble",
                "split_confidence": "0.65",
                "remark": "display-only preamble; scope remains pending manual confirmation",
            }
        )

    for index, match in enumerate(matches):
        marker = match.group("marker")
        level = quota_a111_rule_marker_level(marker)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
        clause_text = raw_text[match.end() : end].strip()
        if not clause_text:
            continue
        if level == "section":
            group_order += 1
            group_no = quota_a111_rule_marker_label(marker)
            group_title = quota_a111_rule_group_title(clause_text)
            clause_order_by_group[group_order] = 0
        elif group_order == 0:
            group_order = 1
            group_no = ""
            group_title = "未识别规则组"
            clause_order_by_group[group_order] = 0
        clause_order_by_group[group_order] = clause_order_by_group.get(group_order, 0) + 1
        rows.append(
            {
                "quota_source_code": source.get("quota_source_code", ""),
                "quota_name": source.get("quota_name_from_pdf", ""),
                "rule_group_order": str(group_order),
                "rule_group_no": group_no,
                "rule_group_title": group_title,
                "clause_order": str(clause_order_by_group[group_order]),
                "clause_no": quota_a111_rule_marker_label(marker),
                "clause_level": level,
                "clause_text": clause_text,
                "applicable_section": source.get("applicable_section", ""),
                "applicable_quota_code_range": source.get("applicable_quota_code_range", ""),
                "rule_scope": rule_scope,
                "requires_manual_scope_review": str(manual_scope).lower(),
                "pdf_page_no": source.get("pdf_page_no", ""),
                "book_page_no": source.get("book_page_no", ""),
                "source_raw_text": raw_text,
                "split_method": f"hierarchy_regex_{level}",
                "split_confidence": "0.72" if level != "subclause" else "0.68",
                "remark": "display-only hierarchy split; scope remains pending manual confirmation",
            }
        )
    return rows or [quota_a111_quantity_fallback_row(source, raw_text)]


@lru_cache(maxsize=1)
def quota_a111_quantity_rule_display_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source in quota_a111_quantity_rule_source_rows():
        rows.extend(quota_a111_split_quantity_rule(source))
    return rows


def quota_a111_quantity_rule_page_sources() -> list[dict[str, str]]:
    rows = artifact_rows(QUOTA_A111_QUANTITY_RULE_PAGE_SOURCE_CSV)
    rows.sort(key=lambda row: int(row.get("pdf_page_no") or 0))
    return rows


def quota_a111_rule_signature(row: dict[str, str]) -> str:
    payload = {
        field: row.get(field, "")
        for field in (
            "rule_group_order",
            "rule_group_no",
            "rule_group_title",
            "clause_order",
            "clause_no",
            "clause_level",
            "clause_text",
        )
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def quota_a111_compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def quota_a111_assign_rule_page(
    rule_row: dict[str, str], page_sources: list[dict[str, str]]
) -> tuple[dict[str, str], str]:
    clause_text = rule_row.get("clause_text", "")
    clause_no = rule_row.get("clause_no", "")
    level = rule_row.get("clause_level", "")
    candidates = [clause_text]
    if level == "section" and clause_no:
        candidates.insert(0, f"{clause_no}、{rule_row.get('rule_group_title', '')}")
    elif level == "subsection" and clause_no:
        candidates.insert(0, f"{clause_no}{clause_text}")
    elif level == "clause" and clause_no:
        candidates = [f"{clause_no}.{clause_text}", f"{clause_no}、{clause_text}", clause_text]
    elif level == "subclause" and clause_no:
        candidates.insert(0, f"{clause_no}{clause_text}")
    page_texts = [
        (page, quota_a111_compact_text(page.get("rule_text_raw") or page.get("rule_text_normalized", "")))
        for page in page_sources
    ]
    for candidate in candidates:
        compact_candidate = quota_a111_compact_text(candidate)
        probes = [compact_candidate[:length] for length in (64, 40, 24, 12, 8, 6) if len(compact_candidate) >= length]
        if compact_candidate and len(compact_candidate) < 6:
            probes.append(compact_candidate)
        for probe in probes:
            for page, page_text in page_texts:
                if probe and probe in page_text:
                    return page, "matched_existing_page_text"
    return page_sources[0], "page_assignment_uncertain"


def quota_a111_rule_title(row: dict[str, str]) -> str:
    if row.get("clause_level") == "raw":
        return "工程量计算规则"
    if row.get("clause_level") == "section":
        return row.get("rule_group_title", "") or row.get("clause_text", "")
    text = re.sub(r"\s+", " ", row.get("clause_text", "")).strip()
    for separator in ("。", "；", "："):
        if separator in text:
            text = text.split(separator, 1)[0] + separator
            break
    return text[:60] + ("..." if len(text) > 60 else "")


def quota_a111_rule_block_type(row: dict[str, str]) -> tuple[str, str]:
    text = row.get("clause_text", "")
    if any(token in text for token in ("换算系数表", "工作面宽度计算表", "放坡系数表")):
        return "mixed_text_table_reference", "pdf_evidence_required_table_columns_not_reconstructed"
    level = row.get("clause_level", "raw")
    block_type = {
        "raw": "source_preamble",
        "section": "section_heading",
        "subsection": "subsection_clause",
        "clause": "numbered_clause",
        "subclause": "numbered_subclause",
    }.get(level, "raw_text_block")
    return block_type, "semantic_display_only_pdf_evidence_required"


@lru_cache(maxsize=1)
def quota_a111_quantity_rule_dual_view_bundle() -> dict[str, list[dict[str, str]]]:
    repeated_rows = quota_a111_quantity_rule_display_rows()
    page_sources = quota_a111_quantity_rule_page_sources()
    source_hash = sha256(QUOTA_A111_PDF_SOURCE)
    duplicate_groups: dict[str, list[dict[str, str]]] = {}
    for row in repeated_rows:
        duplicate_groups.setdefault(quota_a111_rule_signature(row), []).append(row)

    source_blocks: list[dict[str, str]] = []
    scope_links: list[dict[str, str]] = []
    duplicate_audit: list[dict[str, str]] = []
    for source_order, (signature, group) in enumerate(duplicate_groups.items(), start=1):
        representative = group[0]
        page, page_status = quota_a111_assign_rule_page(representative, page_sources)
        pdf_page = int(page.get("pdf_page_no") or 0)
        block_type, parse_status = quota_a111_rule_block_type(representative)
        if page_status == "page_assignment_uncertain":
            parse_status = f"{parse_status};page_assignment_uncertain"
        rule_block_id = f"QRBLOCK-A111-P{pdf_page:03d}-{source_order:03d}-{signature[:8]}"
        visible_rule_no = representative.get("clause_no") or representative.get("rule_group_no") or "总则"
        block = {
            "rule_block_id": rule_block_id,
            "source_file": str(QUOTA_A111_PDF_SOURCE),
            "source_hash": source_hash,
            "pdf_page_no": str(pdf_page),
            "book_page_no": page.get("book_page_no", ""),
            "source_order": str(source_order),
            "block_type": block_type,
            "rule_no": visible_rule_no,
            "rule_level": representative.get("clause_level", "raw"),
            "rule_title": quota_a111_rule_title(representative),
            "raw_text": representative.get("clause_text", ""),
            "table_json": "",
            "source_bbox": "",
            "parse_status": parse_status,
            "remark": f"deduplicated from quota display copies; {page_status}; no bbox; original PDF is evidence",
        }
        source_blocks.append(block)
        scope_link_id = f"QRSCOPE-A111-{source_order:03d}"
        scope_links.append(
            {
                "scope_link_id": scope_link_id,
                "rule_block_id": rule_block_id,
                "scope_type": "uncertain",
                "appendix_code": "A",
                "section_code": "A.1.1",
                "quota_code_start": "A1-1-1",
                "quota_code_end": "A1-1-137",
                "specific_quota_source_code": "",
                "scope_confidence": "0.50",
                "requires_manual_scope_review": "true",
                "remark": "existing source marks section-level range but requires manual confirmation; no per-quota copy",
            }
        )
        duplicate_audit.append(
            {
                "duplicate_group_id": f"QRDUP-A111-{source_order:03d}",
                "source_signature": signature,
                "original_record_count": str(len(group)),
                "distinct_quota_count": str(len({row.get('quota_source_code', '') for row in group})),
                "representative_quota_source_code": representative.get("quota_source_code", ""),
                "rule_group_order": representative.get("rule_group_order", ""),
                "clause_order": representative.get("clause_order", ""),
                "clause_no": representative.get("clause_no", ""),
                "rule_level": representative.get("clause_level", ""),
                "deduplicated_rule_block_id": rule_block_id,
                "duplicate_record_count_removed": str(max(0, len(group) - 1)),
                "status": "deduplicated_readonly_display_model",
                "remark": "original repeated display records remain unchanged",
            }
        )

    block_ids_by_page: dict[str, list[str]] = {}
    for block in source_blocks:
        block_ids_by_page.setdefault(block["pdf_page_no"], []).append(block["rule_block_id"])
    page_index: list[dict[str, str]] = []
    for page in page_sources:
        pdf_page = page.get("pdf_page_no", "")
        block_ids = block_ids_by_page.get(pdf_page, [])
        page_index.append(
            {
                "page_index_id": f"QRPAGE-A111-P{int(pdf_page or 0):03d}",
                "source_file": str(QUOTA_A111_PDF_SOURCE),
                "source_hash": source_hash,
                "pdf_page_no": pdf_page,
                "book_page_no": page.get("book_page_no", ""),
                "source_url": f"/api/quota-a111/quantity-rule/source-pdf#page={pdf_page}&zoom=page-width",
                "block_count": str(len(block_ids)),
                "rule_block_ids": json.dumps(block_ids, ensure_ascii=False, separators=(",", ":")),
                "render_mode": "original_pdf_embed",
                "table_render_mode": "original_pdf_page",
                "watermark_policy": "preserve_original",
                "status": "ready",
                "remark": "table cell structure not reliably available; do not reconstruct HTML table",
            }
        )
    return {
        "source_blocks": source_blocks,
        "scope_links": scope_links,
        "duplicate_audit": duplicate_audit,
        "page_index": page_index,
    }


def quota_a111_code_number(value: str) -> int | None:
    match = re.fullmatch(r"A1-1-(\d+)", value or "")
    return int(match.group(1)) if match else None


def quota_a111_scope_link_applies(link: dict[str, str], quota_source_code: str) -> bool:
    if link.get("specific_quota_source_code"):
        return link.get("specific_quota_source_code") == quota_source_code
    quota_number = quota_a111_code_number(quota_source_code)
    start_number = quota_a111_code_number(link.get("quota_code_start", ""))
    end_number = quota_a111_code_number(link.get("quota_code_end", ""))
    return (
        quota_number is not None
        and start_number is not None
        and end_number is not None
        and start_number <= quota_number <= end_number
    )


def quota_a111_rule_blocks_for_quota(quota_source_code: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    bundle = quota_a111_quantity_rule_dual_view_bundle()
    links = [row for row in bundle["scope_links"] if quota_a111_scope_link_applies(row, quota_source_code)]
    block_ids = {row["rule_block_id"] for row in links}
    blocks = [row for row in bundle["source_blocks"] if row["rule_block_id"] in block_ids]
    return blocks, links


def quota_a111_rule_summary(value: str, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text if len(text) <= limit else text[:limit] + "..."


def quota_a111_generate_quantity_rule_dual_view_artifacts() -> dict[str, Any]:
    bundle = quota_a111_quantity_rule_dual_view_bundle()
    write_csv(QUOTA_A111_RULE_SOURCE_BLOCKS_CSV, bundle["source_blocks"], QUOTA_A111_RULE_SOURCE_BLOCK_FIELDS)
    write_csv(QUOTA_A111_RULE_SCOPE_LINKS_CSV, bundle["scope_links"], QUOTA_A111_RULE_SCOPE_LINK_FIELDS)
    write_csv(QUOTA_A111_RULE_DUPLICATE_AUDIT_CSV, bundle["duplicate_audit"], QUOTA_A111_RULE_DUPLICATE_AUDIT_FIELDS)
    write_csv(QUOTA_A111_RULE_SOURCE_PAGE_INDEX_CSV, bundle["page_index"], QUOTA_A111_RULE_SOURCE_PAGE_INDEX_FIELDS)
    return {
        **bundle,
        "paths": {
            "source_blocks": str(QUOTA_A111_RULE_SOURCE_BLOCKS_CSV),
            "scope_links": str(QUOTA_A111_RULE_SCOPE_LINKS_CSV),
            "duplicate_audit": str(QUOTA_A111_RULE_DUPLICATE_AUDIT_CSV),
            "page_index": str(QUOTA_A111_RULE_SOURCE_PAGE_INDEX_CSV),
        },
    }


def quota_a111_find_detail(quota_source_code: str) -> dict[str, str]:
    detail = next(
        (row for row in quota_a111_detail_rows() if row.get("quota_source_code") == quota_source_code),
        None,
    )
    if not detail:
        raise HTTPException(status_code=404, detail="quota detail not found")
    return detail


def quota_a111_bill_name(bill_code_9: str) -> str:
    return next(
        (
            row.get("bill_name", "")
            for row in quota_a111_tree_rows()
            if row.get("node_type") == "bill" and row.get("bill_code_9") == bill_code_9
        ),
        "",
    )


def quota_a111_base_row_by_id() -> dict[str, dict[str, str]]:
    return {row.get("row_id", ""): row for row in quota_a111_bill_rows() if row.get("row_id")}


def quota_a111_draft_rows(con: sqlite3.Connection, include_reverted: bool = False) -> list[dict[str, Any]]:
    status_filter = "" if include_reverted else "WHERE draft_status <> 'reverted'"
    return fetch_all(
        con,
        f"""
        SELECT {', '.join(QUOTA_A111_DRAFT_EDGE_FIELDS)}
        FROM web_quota_a111_mapping_draft_edges
        {status_filter}
        ORDER BY created_at, rowid
        """,
    )


def quota_a111_tree_draft_stats(con: sqlite3.Connection) -> list[dict[str, Any]]:
    tree_bills = [row for row in quota_a111_tree_rows() if row.get("node_type") == "bill"]
    original_by_bill: dict[str, set[str]] = {
        row.get("bill_code_9", ""): set() for row in tree_bills if row.get("bill_code_9")
    }
    for row in quota_a111_bill_rows():
        bill_code = row.get("bill_code_9", "")
        quota_code = row.get("quota_source_code", "")
        if row.get("row_type") != "gb_bill" and bill_code and quota_code:
            original_by_bill.setdefault(bill_code, set()).add(quota_code)

    all_drafts = quota_a111_draft_rows(con, include_reverted=True)
    active_drafts = [row for row in all_drafts if row.get("draft_status") != "reverted"]
    last_effect_by_relation: dict[tuple[str, str], tuple[str, str]] = {}
    for edge in active_drafts:
        relation_type = str(edge.get("relation_type", ""))
        quota_code = str(edge.get("quota_source_code", ""))
        if relation_type in {"draft_copy", "draft_move_target"}:
            bill_code = str(edge.get("target_bill_code_9", ""))
            effect = "add"
        elif relation_type in {"draft_move_source_excluded", "draft_excluded"}:
            bill_code = str(edge.get("source_bill_code_9", ""))
            effect = "remove"
        else:
            continue
        if bill_code and quota_code:
            last_effect_by_relation[(bill_code, quota_code)] = (effect, relation_type)

    reverted_by_bill: dict[str, set[str]] = {bill_code: set() for bill_code in original_by_bill}
    for edge in all_drafts:
        if edge.get("draft_status") != "reverted":
            continue
        bill_code = str(edge.get("target_bill_code_9", ""))
        if bill_code:
            reverted_by_bill.setdefault(bill_code, set()).add(str(edge.get("draft_edge_id", "")))

    original_risk = {row.get("bill_code_9", ""): row.get("risk_level", "low") for row in tree_bills}
    results: list[dict[str, Any]] = []
    for bill in tree_bills:
        bill_code = bill.get("bill_code_9", "")
        original = original_by_bill.get(bill_code, set())
        copy_in: set[str] = set()
        move_in: set[str] = set()
        move_out: set[str] = set()
        excluded: set[str] = set()
        for (effect_bill, quota_code), (effect, relation_type) in last_effect_by_relation.items():
            if effect_bill != bill_code:
                continue
            if effect == "add" and quota_code not in original:
                (copy_in if relation_type == "draft_copy" else move_in).add(quota_code)
            elif effect == "remove" and quota_code in original:
                (move_out if relation_type == "draft_move_source_excluded" else excluded).add(quota_code)
        effective_count = len(original) + len(copy_in) + len(move_in) - len(move_out) - len(excluded)
        draft_active_count = len(copy_in) + len(move_in) + len(move_out) + len(excluded)
        if move_out or excluded:
            risk_level = "high"
        elif copy_in or move_in:
            risk_level = "medium"
        else:
            risk_level = original_risk.get(bill_code, "low") or "low"
        results.append(
            {
                "bill_code_9": bill_code,
                "bill_name": bill.get("bill_name", ""),
                "original_candidate_count": len(original),
                "copy_in_count": len(copy_in),
                "move_in_count": len(move_in),
                "move_out_count": len(move_out),
                "excluded_count": len(excluded),
                "reverted_count": len(reverted_by_bill.get(bill_code, set())),
                "effective_candidate_count": effective_count,
                "draft_active_count": draft_active_count,
                "has_draft_change": draft_active_count > 0,
                "risk_level": risk_level,
            }
        )
    return results


def quota_a111_draft_stats(con: sqlite3.Connection) -> dict[str, int]:
    rows = quota_a111_draft_rows(con, include_reverted=True)
    active_rows = [row for row in rows if row.get("draft_status") != "reverted"]
    return {
        "total_count": len(active_rows),
        "copy_count": sum(1 for row in active_rows if row.get("relation_type") == "draft_copy"),
        "move_count": sum(1 for row in active_rows if row.get("relation_type") == "draft_move_target"),
        "exclude_count": sum(1 for row in active_rows if row.get("relation_type") == "draft_excluded"),
        "source_excluded_count": sum(1 for row in active_rows if row.get("relation_type") == "draft_move_source_excluded"),
        "reverted_count": sum(1 for row in rows if row.get("draft_status") == "reverted"),
        "approved_count": 0,
    }


def quota_a111_generate_refinement_artifacts() -> dict[str, Any]:
    work_rows = quota_a111_work_content_display_rows()
    rule_rows = quota_a111_quantity_rule_display_rows()
    with connect() as con:
        tree_stats = quota_a111_tree_draft_stats(con)
    write_csv(QUOTA_A111_TREE_DRAFT_STATS_CSV, tree_stats, QUOTA_A111_TREE_DRAFT_STATS_FIELDS)
    write_csv(QUOTA_A111_WORK_CONTENT_DISPLAY_CSV, work_rows, QUOTA_A111_WORK_CONTENT_DISPLAY_FIELDS)
    write_csv(QUOTA_A111_QUANTITY_RULE_DISPLAY_CSV, rule_rows, QUOTA_A111_QUANTITY_RULE_DISPLAY_FIELDS)
    return {
        "tree_stats": tree_stats,
        "work_content_rows": work_rows,
        "quantity_rule_rows": rule_rows,
        "paths": {
            "tree_stats": str(QUOTA_A111_TREE_DRAFT_STATS_CSV),
            "work_content": str(QUOTA_A111_WORK_CONTENT_DISPLAY_CSV),
            "quantity_rule": str(QUOTA_A111_QUANTITY_RULE_DISPLAY_CSV),
        },
    }


def quota_a111_write_draft_audit(
    con: sqlite3.Connection,
    event_type: str,
    draft_edge_id: str,
    quota_source_code: str,
    source_bill_code_9: str,
    target_bill_code_9: str,
    action_type: str,
    payload: dict[str, Any] | list[dict[str, Any]] | None,
    remark: str = "",
) -> None:
    con.execute(
        """
        INSERT INTO web_quota_a111_mapping_draft_audit_log
        (audit_id, event_type, draft_edge_id, quota_source_code, source_bill_code_9,
         target_bill_code_9, action_type, payload_json, created_at, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            event_type,
            draft_edge_id,
            quota_source_code,
            source_bill_code_9,
            target_bill_code_9,
            action_type,
            json.dumps(payload or {}, ensure_ascii=False),
            datetime.now().isoformat(timespec="seconds"),
            remark,
        ),
    )


def quota_a111_insert_draft_edge(
    con: sqlite3.Connection,
    payload: QuotaA111DraftEdgePayload,
    relation_type: str,
    draft_status: str,
    source_edge_id: str | None = None,
    source_bill_code_9: str | None = None,
    target_bill_code_9: str | None = None,
    target_bill_name: str | None = None,
) -> dict[str, Any]:
    if relation_type not in QUOTA_A111_DRAFT_RELATION_TYPES:
        raise HTTPException(status_code=400, detail="invalid relation_type")
    if draft_status not in QUOTA_A111_DRAFT_STATUSES or draft_status == "approved":
        raise HTTPException(status_code=400, detail="invalid draft_status")
    now = datetime.now().isoformat(timespec="seconds")
    draft_edge_id = f"DRAFT-A111-{uuid4().hex[:16]}"
    row = {
        "draft_edge_id": draft_edge_id,
        "source_edge_id": source_edge_id or payload.source_edge_id,
        "source_bill_code_9": source_bill_code_9 or payload.source_bill_code_9,
        "source_bill_name": payload.source_bill_name or quota_a111_bill_name(source_bill_code_9 or payload.source_bill_code_9),
        "target_bill_code_9": target_bill_code_9 or payload.target_bill_code_9 or payload.source_bill_code_9,
        "target_bill_name": target_bill_name or payload.target_bill_name or quota_a111_bill_name(target_bill_code_9 or payload.target_bill_code_9),
        "quota_source_code": payload.quota_source_code,
        "quota_name": payload.quota_name,
        "action_type": payload.action_type,
        "relation_type": relation_type,
        "draft_status": draft_status,
        "operation_reason": payload.operation_reason,
        "created_at": now,
        "updated_at": now,
        "reviewer": payload.reviewer,
        "comment": payload.comment,
    }
    con.execute(
        f"""
        INSERT INTO web_quota_a111_mapping_draft_edges
        ({', '.join(QUOTA_A111_DRAFT_EDGE_FIELDS)})
        VALUES ({', '.join(['?'] * len(QUOTA_A111_DRAFT_EDGE_FIELDS))})
        """,
        tuple(row[field] for field in QUOTA_A111_DRAFT_EDGE_FIELDS),
    )
    quota_a111_write_draft_audit(
        con,
        "draft_edge_created",
        draft_edge_id,
        row["quota_source_code"],
        row["source_bill_code_9"],
        row["target_bill_code_9"],
        row["action_type"],
        row,
        "draft edge created; pending only; no approved",
    )
    return row


def quota_a111_detail_for_display(quota_source_code: str) -> dict[str, str]:
    return next(
        (row for row in quota_a111_detail_rows() if row.get("quota_source_code") == quota_source_code),
        {},
    )


def quota_a111_make_draft_display_row(
    edge: dict[str, Any],
    base_rows_by_id: dict[str, dict[str, str]],
    bill_code_9: str,
) -> dict[str, Any]:
    base = dict(base_rows_by_id.get(str(edge.get("source_edge_id", "")), {}))
    detail = quota_a111_detail_for_display(str(edge.get("quota_source_code", "")))
    row = {
        **base,
        "row_id": f"{edge.get('relation_type')}-{edge.get('draft_edge_id')}",
        "parent_row_id": f"BILL-{bill_code_9}",
        "row_level": "1",
        "row_type": edge.get("relation_type", "draft_copy"),
        "bill_code_9": bill_code_9,
        "bill_name": quota_a111_bill_name(bill_code_9),
        "quota_source_code": edge.get("quota_source_code", ""),
        "quota_name_from_pdf": edge.get("quota_name") or base.get("quota_name_from_pdf") or detail.get("quota_name_from_pdf", ""),
        "quota_unit_normalized": base.get("quota_unit_normalized") or detail.get("quota_unit_normalized", ""),
        "labor_fee": base.get("labor_fee") or detail.get("labor_fee", ""),
        "material_fee": base.get("material_fee") or detail.get("material_fee", ""),
        "machine_fee": base.get("machine_fee") or detail.get("machine_fee", ""),
        "management_fee": base.get("management_fee") or detail.get("management_fee", ""),
        "base_price": base.get("base_price") or detail.get("base_price", ""),
        "mapping_role": edge.get("relation_type", ""),
        "mapping_confidence": "draft",
        "coverage_status": "draft_overlay",
        "risk_level": "manual_review_required",
        "review_status": "pending",
        "display_order": base.get("display_order") or "999999",
        "source_edge_id": edge.get("source_edge_id", ""),
        "draft_edge_id": edge.get("draft_edge_id", ""),
        "relation_type": edge.get("relation_type", ""),
        "draft_status": edge.get("draft_status", ""),
        "action_type": edge.get("action_type", ""),
        "operation_reason": edge.get("operation_reason", ""),
        "is_draft": "true",
        "draft_warning": "草稿关系，未 approved",
    }
    return row


def quota_a111_apply_draft_overlay(
    rows: list[dict[str, str]],
    bill_code_9: str,
    con: sqlite3.Connection,
    include_excluded: bool = False,
) -> list[dict[str, Any]]:
    base_by_id = quota_a111_base_row_by_id()
    draft_rows = quota_a111_draft_rows(con)
    suppressed = {
        str(edge.get("source_edge_id", ""))
        for edge in draft_rows
        if edge.get("source_bill_code_9") == bill_code_9
        and edge.get("relation_type") in {"draft_move_source_excluded", "draft_excluded"}
    }
    result: list[dict[str, Any]] = []
    for row in rows:
        enriched: dict[str, Any] = {
            **row,
            "source_edge_id": row.get("row_id", ""),
            "relation_type": "original_candidate" if row.get("row_type") != "gb_bill" else "gb_bill",
            "draft_status": "active",
            "is_draft": "false",
        }
        if row.get("row_type") != "gb_bill" and row.get("row_id") in suppressed:
            continue
        result.append(enriched)
    target_drafts = [
        edge
        for edge in draft_rows
        if edge.get("target_bill_code_9") == bill_code_9
        and edge.get("relation_type") in {"draft_copy", "draft_move_target"}
    ]
    excluded_drafts = [
        edge
        for edge in draft_rows
        if include_excluded
        and edge.get("source_bill_code_9") == bill_code_9
        and edge.get("relation_type") in {"draft_move_source_excluded", "draft_excluded"}
    ]
    for edge in target_drafts + excluded_drafts:
        result.append(quota_a111_make_draft_display_row(edge, base_by_id, bill_code_9))
    bill_rows = [row for row in result if row.get("row_type") == "gb_bill"]
    other_rows = [row for row in result if row.get("row_type") != "gb_bill"]
    other_rows.sort(key=lambda row: (str(row.get("is_draft") == "true"), int(str(row.get("display_order") or "999999"))))
    return bill_rows + other_rows


@app.get("/api/quota-a111/tree")
def get_quota_a111_tree() -> dict[str, Any]:
    source_rows = quota_a111_tree_rows()
    detail_count = len(quota_a111_detail_rows())
    resource_count = len(quota_a111_resource_rows())
    with connect() as con:
        draft_stats = quota_a111_draft_stats(con)
        bill_draft_stats = quota_a111_tree_draft_stats(con)
    stats_by_bill = {row["bill_code_9"]: row for row in bill_draft_stats}
    rows = [
        {**row, **stats_by_bill.get(row.get("bill_code_9", ""), {})}
        if row.get("node_type") == "bill"
        else dict(row)
        for row in source_rows
    ]
    return {
        "items": rows,
        "count": len(rows),
        "enabled_bill_count": sum(
            1 for row in rows if row.get("node_type") == "bill" and row.get("enabled") == "true"
        ),
        "appendix_a_bill_count": sum(1 for row in rows if row.get("node_type") == "bill"),
        "main_quota_count": detail_count,
        "resource_row_count": resource_count,
        "readonly": True,
        "review_status_policy": "pending_only",
        "source_priority": "GD2018 PDF full review pack for quota details; mapping candidate for bill-to-quota association",
        "draft_stats": draft_stats,
        "bill_draft_stats": bill_draft_stats,
    }


@app.get("/api/quota-a111/bill/{bill_code_9}/rows")
def get_quota_a111_bill_rows(bill_code_9: str, include_excluded: bool = False) -> dict[str, Any]:
    rows = [row for row in quota_a111_bill_rows() if row.get("bill_code_9") == bill_code_9]
    if not rows:
        raise HTTPException(status_code=404, detail="bill rows not found")
    bill_row = next((row for row in rows if row.get("row_type") == "gb_bill"), rows[0])
    with connect() as con:
        overlay_rows = quota_a111_apply_draft_overlay(rows, bill_code_9, con, include_excluded=include_excluded)
        draft_stats = quota_a111_draft_stats(con)
        bill_draft_stats = next(
            (row for row in quota_a111_tree_draft_stats(con) if row.get("bill_code_9") == bill_code_9),
            {},
        )
    return {
        "bill_code_9": bill_code_9,
        "bill": bill_row,
        "rows": overlay_rows,
        "count": len(overlay_rows),
        "candidate_count": sum(1 for row in overlay_rows if row.get("row_type") != "gb_bill"),
        "original_candidate_count": sum(1 for row in rows if row.get("row_type") != "gb_bill"),
        "include_excluded": include_excluded,
        "draft_stats": draft_stats,
        "bill_draft_stats": bill_draft_stats,
        "readonly": True,
        "writes_database": "local_sqlite_draft_only",
        "generates_approved": False,
    }


@app.get("/api/quota-a111/draft/edges")
def get_quota_a111_draft_edges(include_reverted: bool = True) -> dict[str, Any]:
    with connect() as con:
        rows = quota_a111_draft_rows(con, include_reverted=include_reverted)
        stats = quota_a111_draft_stats(con)
    return {
        "items": rows,
        "count": len(rows),
        "stats": stats,
        "local_sqlite_only": True,
        "generates_approved": False,
    }


@app.get("/api/quota-a111/draft/stats")
def get_quota_a111_draft_stats() -> dict[str, Any]:
    with connect() as con:
        stats = quota_a111_draft_stats(con)
        bill_draft_stats = quota_a111_tree_draft_stats(con)
    return {
        "stats": stats,
        "bill_draft_stats": bill_draft_stats,
        "approved_count": 0,
        "local_sqlite_only": True,
    }


@app.post("/api/quota-a111/draft/edge")
def create_quota_a111_draft_edge(payload: QuotaA111DraftEdgePayload) -> dict[str, Any]:
    if payload.action_type not in {"copy_link", "move_link", "exclude_link"}:
        raise HTTPException(status_code=400, detail="action_type must be copy_link, move_link, or exclude_link")
    if not payload.source_edge_id or not payload.source_bill_code_9 or not payload.quota_source_code:
        raise HTTPException(status_code=400, detail="source_edge_id, source_bill_code_9, and quota_source_code are required")
    if payload.action_type in {"copy_link", "move_link"} and not payload.target_bill_code_9:
        raise HTTPException(status_code=400, detail="target_bill_code_9 is required for copy/move")
    if payload.action_type == "exclude_link":
        payload.target_bill_code_9 = payload.source_bill_code_9
        payload.target_bill_name = payload.source_bill_name
    if payload.action_type in {"copy_link", "move_link"} and payload.target_bill_code_9 == payload.source_bill_code_9:
        raise HTTPException(status_code=400, detail="target bill must differ from source bill for copy/move")

    payload_dict = payload.dict()
    created: list[dict[str, Any]] = []
    confirm_event = {
        "copy_link": "confirm_copy",
        "move_link": "confirm_move",
        "exclude_link": "confirm_exclude",
    }[payload.action_type]
    with connect() as con:
        quota_a111_write_draft_audit(
            con,
            confirm_event,
            "",
            payload.quota_source_code,
            payload.source_bill_code_9,
            payload.target_bill_code_9,
            payload.action_type,
            payload_dict,
            "user confirmed draft mapping edge operation",
        )
        if payload.action_type == "copy_link":
            created.append(
                quota_a111_insert_draft_edge(
                    con,
                    payload,
                    relation_type="draft_copy",
                    draft_status="active",
                    target_bill_code_9=payload.target_bill_code_9,
                    target_bill_name=payload.target_bill_name,
                )
            )
        elif payload.action_type == "move_link":
            created.append(
                quota_a111_insert_draft_edge(
                    con,
                    payload,
                    relation_type="draft_move_target",
                    draft_status="active",
                    target_bill_code_9=payload.target_bill_code_9,
                    target_bill_name=payload.target_bill_name,
                )
            )
            created.append(
                quota_a111_insert_draft_edge(
                    con,
                    payload,
                    relation_type="draft_move_source_excluded",
                    draft_status="excluded",
                    target_bill_code_9=payload.source_bill_code_9,
                    target_bill_name=payload.source_bill_name,
                )
            )
        else:
            created.append(
                quota_a111_insert_draft_edge(
                    con,
                    payload,
                    relation_type="draft_excluded",
                    draft_status="excluded",
                    target_bill_code_9=payload.source_bill_code_9,
                    target_bill_name=payload.source_bill_name,
                )
            )
        stats = quota_a111_draft_stats(con)
        bill_draft_stats = quota_a111_tree_draft_stats(con)
        con.commit()
    return {
        "saved": True,
        "created_edges": created,
        "stats": stats,
        "bill_draft_stats": bill_draft_stats,
        "approved_count": 0,
        "local_sqlite_only": True,
    }


@app.post("/api/quota-a111/draft/edge/{draft_edge_id}/revert")
def revert_quota_a111_draft_edge(draft_edge_id: str) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        edge = fetch_one(
            con,
            "SELECT * FROM web_quota_a111_mapping_draft_edges WHERE draft_edge_id = ?",
            (draft_edge_id,),
        )
        if not edge:
            raise HTTPException(status_code=404, detail="draft edge not found")
        peers = fetch_all(
            con,
            """
            SELECT *
            FROM web_quota_a111_mapping_draft_edges
            WHERE source_edge_id = ?
              AND quota_source_code = ?
              AND action_type = ?
              AND draft_status <> 'reverted'
            """,
            (edge.get("source_edge_id"), edge.get("quota_source_code"), edge.get("action_type")),
        )
        con.execute(
            """
            UPDATE web_quota_a111_mapping_draft_edges
            SET relation_type = 'restored', draft_status = 'reverted', updated_at = ?
            WHERE source_edge_id = ?
              AND quota_source_code = ?
              AND action_type = ?
              AND draft_status <> 'reverted'
            """,
            (now, edge.get("source_edge_id"), edge.get("quota_source_code"), edge.get("action_type")),
        )
        quota_a111_write_draft_audit(
            con,
            "draft_edge_reverted",
            draft_edge_id,
            edge.get("quota_source_code", ""),
            edge.get("source_bill_code_9", ""),
            edge.get("target_bill_code_9", ""),
            edge.get("action_type", "restore_original"),
            {"reverted_edges": peers},
            "restore original candidate display; no approved",
        )
        stats = quota_a111_draft_stats(con)
        bill_draft_stats = quota_a111_tree_draft_stats(con)
        con.commit()
    return {
        "reverted": True,
        "draft_edge_id": draft_edge_id,
        "reverted_count": len(peers),
        "stats": stats,
        "bill_draft_stats": bill_draft_stats,
        "approved_count": 0,
    }


@app.get("/api/quota-a111/draft/export")
def export_quota_a111_draft_edges() -> dict[str, Any]:
    QUOTA_A111_MAPPING_DRAFT_RUN_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        rows = quota_a111_draft_rows(con, include_reverted=True)
        write_csv(QUOTA_A111_MAPPING_DRAFT_EXPORT_CSV, rows, QUOTA_A111_DRAFT_EDGE_FIELDS)
        quota_a111_write_draft_audit(
            con,
            "draft_exported",
            "",
            "",
            "",
            "",
            "",
            {"path": str(QUOTA_A111_MAPPING_DRAFT_EXPORT_CSV), "row_count": len(rows)},
            "draft CSV exported",
        )
        con.commit()
    return {
        "exported": True,
        "count": len(rows),
        "path": str(QUOTA_A111_MAPPING_DRAFT_EXPORT_CSV),
        "approved_count": 0,
    }


@app.get("/api/quota-a111/draft/audit/export")
def export_quota_a111_draft_audit() -> dict[str, Any]:
    QUOTA_A111_MAPPING_DRAFT_RUN_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        quota_a111_write_draft_audit(
            con,
            "audit_exported",
            "",
            "",
            "",
            "",
            "",
            {"path": str(QUOTA_A111_MAPPING_DRAFT_AUDIT_EXPORT_CSV)},
            "audit CSV exported",
        )
        con.commit()
        rows = fetch_all(
            con,
            f"""
            SELECT {', '.join(QUOTA_A111_DRAFT_AUDIT_FIELDS)}
            FROM web_quota_a111_mapping_draft_audit_log
            ORDER BY created_at, audit_id
            """,
        )
    write_csv(QUOTA_A111_MAPPING_DRAFT_AUDIT_EXPORT_CSV, rows, QUOTA_A111_DRAFT_AUDIT_FIELDS)
    return {
        "exported": True,
        "count": len(rows),
        "path": str(QUOTA_A111_MAPPING_DRAFT_AUDIT_EXPORT_CSV),
        "approved_count": 0,
    }


@app.post("/api/quota-a111/draft/reset-test-data")
def reset_quota_a111_draft_test_data() -> dict[str, Any]:
    with connect() as con:
        edge_count = fetch_one(con, "SELECT COUNT(*) AS count FROM web_quota_a111_mapping_draft_edges", ())["count"]
        audit_count = fetch_one(con, "SELECT COUNT(*) AS count FROM web_quota_a111_mapping_draft_audit_log", ())["count"]
        con.execute("DELETE FROM web_quota_a111_mapping_draft_edges")
        con.execute("DELETE FROM web_quota_a111_mapping_draft_audit_log")
        con.commit()
    return {
        "reset": True,
        "deleted_edges": edge_count,
        "deleted_audit_rows": audit_count,
        "approved_count": 0,
        "local_sqlite_only": True,
    }


@app.get("/api/quota-a111/quota/{quota_source_code}/detail")
def get_quota_a111_quota_detail(quota_source_code: str) -> dict[str, Any]:
    detail = quota_a111_find_detail(quota_source_code)
    return {"quota_source_code": quota_source_code, "detail": detail, "readonly": True}


@app.get("/api/quota-a111/quota/{quota_source_code}/resources")
def get_quota_a111_quota_resources(quota_source_code: str) -> dict[str, Any]:
    quota_a111_find_detail(quota_source_code)
    all_rows = quota_a111_resource_rows()
    rows = [row for row in all_rows if row.get("quota_source_code") == quota_source_code]
    return {
        "quota_source_code": quota_source_code,
        "items": rows,
        "count": len(rows),
        "total_resource_row_count": len(all_rows),
        "readonly": True,
    }


@app.get("/api/quota-a111/quota/{quota_source_code}/work-content")
def get_quota_a111_work_content(quota_source_code: str) -> dict[str, Any]:
    detail = quota_a111_find_detail(quota_source_code)
    items = [
        row for row in quota_a111_work_content_display_rows() if row.get("quota_source_code") == quota_source_code
    ]
    raw_text = items[0].get("source_raw_text", "") if items else detail.get("work_content_normalized", "")
    return {
        "quota_source_code": quota_source_code,
        "quota_name_from_pdf": detail.get("quota_name_from_pdf", ""),
        "work_content_normalized": detail.get("work_content_normalized", ""),
        "items": items,
        "count": len(items),
        "raw_text": raw_text,
        "raw_fallback_count": sum(1 for row in items if row.get("split_method") == "raw_fallback"),
        "review_status": detail.get("review_status", "pending"),
        "readonly": True,
    }


@app.get("/api/quota-a111/quota/{quota_source_code}/quantity-rule")
def get_quota_a111_quantity_rule(quota_source_code: str) -> dict[str, Any]:
    detail = quota_a111_find_detail(quota_source_code)
    rows = [
        row for row in quota_a111_quantity_rule_display_rows() if row.get("quota_source_code") == quota_source_code
    ]
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row.get("rule_group_order", ""), row.get("rule_group_no", ""), row.get("rule_group_title", ""))
        if key not in grouped:
            grouped[key] = {
                "rule_group_order": row.get("rule_group_order", ""),
                "rule_group_no": row.get("rule_group_no", ""),
                "rule_group_title": row.get("rule_group_title", ""),
                "clauses": [],
            }
        grouped[key]["clauses"].append(
            {field: row.get(field, "") for field in QUOTA_A111_QUANTITY_RULE_DISPLAY_FIELDS if field != "source_raw_text"}
        )
    raw_text = rows[0].get("source_raw_text", "") if rows else detail.get("applicable_rule_text", "")
    return {
        "quota_source_code": quota_source_code,
        "quota_name_from_pdf": detail.get("quota_name_from_pdf", ""),
        "applicable_rule_text": detail.get("applicable_rule_text", ""),
        "rule_groups": list(grouped.values()),
        "clause_count": len(rows),
        "raw_text": raw_text,
        "raw_fallback_count": sum(1 for row in rows if row.get("split_method") == "raw_fallback"),
        "review_status": detail.get("review_status", "pending"),
        "scope_status": "requires_manual_confirmation",
        "readonly": True,
    }


@app.get("/api/quota-a111/quantity-rule/source-pdf")
def get_quota_a111_quantity_rule_source_pdf() -> FileResponse:
    if not QUOTA_A111_PDF_SOURCE.exists():
        raise HTTPException(status_code=404, detail="quantity rule source PDF not found")
    return FileResponse(QUOTA_A111_PDF_SOURCE, media_type="application/pdf")


@app.get("/api/quota-a111/quota/{quota_source_code}/quantity-rule/source-pages")
def get_quota_a111_quantity_rule_source_pages(quota_source_code: str) -> dict[str, Any]:
    quota_a111_find_detail(quota_source_code)
    blocks, links = quota_a111_rule_blocks_for_quota(quota_source_code)
    block_ids = {row["rule_block_id"] for row in blocks}
    bundle = quota_a111_quantity_rule_dual_view_bundle()
    pages: list[dict[str, Any]] = []
    for page in bundle["page_index"]:
        page_block_ids = [item for item in json.loads(page.get("rule_block_ids") or "[]") if item in block_ids]
        if not page_block_ids:
            continue
        pages.append(
            {
                **page,
                "pdf_page_no": int(page.get("pdf_page_no") or 0),
                "book_page_no": int(page.get("book_page_no") or 0),
                "rule_block_ids": page_block_ids,
            }
        )
    return {
        "quota_source_code": quota_source_code,
        "pages": pages,
        "page_count": len(pages),
        "rule_block_count": len(blocks),
        "scope_link_count": len(links),
        "default_view": "original",
        "evidence_mode": "original_pdf_embed",
        "table_render_mode": "original_pdf_page",
        "preserves_watermark": True,
        "readonly": True,
        "generates_approved": False,
    }


@app.get("/api/quota-a111/quantity-rule/block/{rule_block_id}")
def get_quota_a111_quantity_rule_block(rule_block_id: str) -> dict[str, Any]:
    bundle = quota_a111_quantity_rule_dual_view_bundle()
    block = next((row for row in bundle["source_blocks"] if row.get("rule_block_id") == rule_block_id), None)
    if not block:
        raise HTTPException(status_code=404, detail="quantity rule block not found")
    links = [row for row in bundle["scope_links"] if row.get("rule_block_id") == rule_block_id]
    return {
        "block": {
            **block,
            "rule_summary": quota_a111_rule_summary(block.get("raw_text", "")),
            "source_url": f"/api/quota-a111/quantity-rule/source-pdf#page={block.get('pdf_page_no')}&zoom=page-width",
        },
        "scope_links": links,
        "readonly": True,
        "generates_approved": False,
    }


@app.get("/api/quota-a111/quantity-rule/page/{pdf_page_no}")
def get_quota_a111_quantity_rule_page(pdf_page_no: int) -> dict[str, Any]:
    bundle = quota_a111_quantity_rule_dual_view_bundle()
    page = next((row for row in bundle["page_index"] if int(row.get("pdf_page_no") or 0) == pdf_page_no), None)
    if not page:
        raise HTTPException(status_code=404, detail="quantity rule source page not found")
    blocks = [row for row in bundle["source_blocks"] if int(row.get("pdf_page_no") or 0) == pdf_page_no]
    return {
        "page": {
            **page,
            "pdf_page_no": pdf_page_no,
            "book_page_no": int(page.get("book_page_no") or 0),
            "rule_block_ids": json.loads(page.get("rule_block_ids") or "[]"),
        },
        "blocks": blocks,
        "block_count": len(blocks),
        "source_url": f"/api/quota-a111/quantity-rule/source-pdf#page={pdf_page_no}&zoom=page-width",
        "readonly": True,
        "generates_approved": False,
    }


@app.get("/api/quota-a111/quota/{quota_source_code}/quantity-rule/structured")
def get_quota_a111_quantity_rule_structured(quota_source_code: str) -> dict[str, Any]:
    detail = quota_a111_find_detail(quota_source_code)
    blocks, links = quota_a111_rule_blocks_for_quota(quota_source_code)
    link_by_block = {row["rule_block_id"]: row for row in links}
    items: list[dict[str, Any]] = []
    for block in blocks:
        link = link_by_block.get(block["rule_block_id"], {})
        items.append(
            {
                "rule_block_id": block.get("rule_block_id", ""),
                "rule_no": block.get("rule_no", ""),
                "rule_level": block.get("rule_level", ""),
                "rule_title": block.get("rule_title", ""),
                "rule_summary": quota_a111_rule_summary(block.get("raw_text", "")),
                "rule_scope": link.get("scope_type", "uncertain"),
                "applicable_section": link.get("section_code", ""),
                "applicable_quota_code_start": link.get("quota_code_start", ""),
                "applicable_quota_code_end": link.get("quota_code_end", ""),
                "pdf_page_no": int(block.get("pdf_page_no") or 0),
                "book_page_no": int(block.get("book_page_no") or 0),
                "requires_manual_scope_review": link.get("requires_manual_scope_review", "true"),
                "raw_text": block.get("raw_text", ""),
                "source_bbox": block.get("source_bbox", ""),
                "parse_status": block.get("parse_status", ""),
                "source_url": f"/api/quota-a111/quantity-rule/source-pdf#page={block.get('pdf_page_no')}&zoom=page-width",
            }
        )
    return {
        "quota_source_code": quota_source_code,
        "quota_name_from_pdf": detail.get("quota_name_from_pdf", ""),
        "items": items,
        "count": len(items),
        "source_block_model": "deduplicated",
        "scope_link_model": "readonly_uncertain_range_link",
        "raw_repeated_display_records_used_as_source_of_truth": False,
        "readonly": True,
        "generates_approved": False,
    }


@app.get("/api/quota-a111/quota/{quota_source_code}/reconciliation")
def get_quota_a111_reconciliation(quota_source_code: str) -> dict[str, Any]:
    detail = quota_a111_find_detail(quota_source_code)
    return {
        "quota_source_code": quota_source_code,
        "quota_name_from_pdf": detail.get("quota_name_from_pdf", ""),
        "pdf_page_no": detail.get("pdf_page_no", ""),
        "book_page_no": detail.get("book_page_no", ""),
        "match_status": detail.get("match_status", ""),
        "delta_total": detail.get("delta_total", ""),
        "coverage_status": detail.get("coverage_status", ""),
        "has_high_or_blocking_issue": detail.get("has_high_or_blocking_issue", ""),
        "resource_reconciliation_status": detail.get("resource_reconciliation_status", ""),
        "review_status": detail.get("review_status", "pending"),
        "readonly": True,
    }


@app.get("/api/quota-a111/search")
def search_quota_a111(q: str = "") -> dict[str, Any]:
    keyword = q.strip().lower()
    if not keyword:
        return {"bills": [], "quotas": [], "resources": [], "count": 0, "readonly": True}
    first_bill_by_quota: dict[str, dict[str, str]] = {}
    for row in quota_a111_bill_rows():
        code = row.get("quota_source_code", "")
        if code and code not in first_bill_by_quota:
            first_bill_by_quota[code] = {
                "bill_code_9": row.get("bill_code_9", ""),
                "bill_name": row.get("bill_name", ""),
            }
    bills = [
        row
        for row in quota_a111_tree_rows()
        if row.get("node_type") == "bill"
        and keyword in " ".join(
            [
                row.get("bill_code_9", ""),
                row.get("bill_name", ""),
                row.get("section_name", ""),
            ]
        ).lower()
    ]
    quotas = [
        {
            **row,
            **first_bill_by_quota.get(row.get("quota_source_code", ""), {}),
        }
        for row in quota_a111_detail_rows()
        if keyword in " ".join(
            [
                row.get("quota_source_code", ""),
                row.get("quota_name_from_pdf", ""),
                row.get("quota_unit_normalized", ""),
                row.get("coverage_status", ""),
            ]
        ).lower()
    ]
    resources = [
        row
        for row in quota_a111_resource_rows()
        if keyword in " ".join(
            [
                row.get("quota_source_code", ""),
                row.get("resource_code", ""),
                row.get("resource_name", ""),
                row.get("resource_spec", ""),
            ]
        ).lower()
    ][:50]
    return {
        "bills": bills[:50],
        "quotas": quotas[:100],
        "resources": resources[:50],
        "count": min(len(bills), 50) + min(len(quotas), 100) + min(len(resources), 50),
        "readonly": True,
    }


@app.get("/api/bid/tree")
def get_bid_tree() -> dict[str, Any]:
    with connect() as con:
        rows = fetch_all(con, "SELECT * FROM web_bid_tree_nodes ORDER BY CAST(display_order AS INTEGER)")
    return {"items": rows, "count": len(rows)}


def filter_gb_bill_items(
    rows: list[dict[str, str]],
    source_file: str = "",
    section_name: str = "",
    q: str = "",
) -> list[dict[str, str]]:
    filtered = rows
    if source_file:
        filtered = [row for row in filtered if row.get("source_file") == source_file]
    if section_name:
        filtered = [
            row
            for row in filtered
            if section_name in (row.get("source_project_section") or "")
            or row.get("section_name") == section_name
        ]
    if q:
        keyword = q.lower()
        filtered = [
            row
            for row in filtered
            if keyword
            in " ".join(
                [
                    row.get("raw_item_code", ""),
                    row.get("normalized_item_code", ""),
                    row.get("bill_code_9", ""),
                    row.get("bid_item_name", ""),
                    row.get("gb_bill_name", ""),
                    row.get("project_feature_full", ""),
                ]
            ).lower()
        ]
    return filtered


def enriched_composition_row(row: dict[str, str], item: dict[str, str] | None, index: int) -> dict[str, str]:
    row_type = row.get("row_type", "")
    display_code = row.get("bill_code_9", "")
    display_name = row.get("gb_bill_name", "")
    if row_type == "bid_item" and item:
        display_code = item.get("raw_item_code", "") or item.get("normalized_item_code", "")
        display_name = item.get("bid_item_name", "")
    elif row_type == "recommended_quota":
        display_code = row.get("quota_source_code", "")
        display_name = row.get("quota_name_candidate", "")
    elif row_type == "recommended_supplement":
        supplement_code = row.get("supplement_candidate_code", "")
        display_code = f"ENT-{supplement_code}" if supplement_code and not supplement_code.startswith("ENT-") else supplement_code
        display_name = row.get("supplement_name", "")
    elif row_type in {"candidate_pool_marker", "collapsed_candidate_pool_marker"}:
        display_code = "candidate_pool"
        display_name = "候选池已折叠"
    elif row_type == "unmatched_warning":
        display_code = "manual_review"
        display_name = "未匹配 / 需人工处理"

    result = dict(row)
    result.update(
        {
            "row_id": "-".join(
                [
                    row.get("bill_code_9", ""),
                    str(index),
                    row_type,
                    row.get("bid_item_id", ""),
                    display_code,
                ]
            ),
            "display_code": display_code,
            "display_name": display_name,
            "raw_item_code": item.get("raw_item_code", "") if item else "",
            "item_suffix": item.get("item_suffix", "") if item else "",
            "bid_item_name": item.get("bid_item_name", "") if item else "",
            "quantity": item.get("quantity", "") if item else "",
            "project_feature_summary": item.get("project_feature_summary", "") if item else "",
            "project_feature_full": item.get("project_feature_full", "") if item else "",
            "source_file": item.get("source_file", "") if item else "",
            "source_project_section": item.get("source_project_section", "") if item else "",
            "matched_bill_status": item.get("matched_bill_status", "") if item else "",
            "code_name_consistency_status": item.get("code_name_consistency_status", "") if item else "",
            "bid_item_risk_level": item.get("risk_level", "") if item else "",
            "review_status": item.get("review_status", "") if item else "",
        }
    )
    return result


@app.get("/api/bid/gb-standard-tree")
def get_bid_gb_standard_tree() -> dict[str, Any]:
    rows = [
        clean_bid_tree_row(clean_bid_artifact_row(row))
        for row in artifact_rows(GB_STANDARD_TREE_CSV)
    ]
    rows.sort(key=lambda row: int(row.get("display_order") or 0))
    gb_bill_count = sum(
        1
        for row in rows
        if row.get("node_type") == "bill" and row.get("appendix_code") != "UNMATCHED"
    )
    return {
        "items": rows,
        "count": len(rows),
        "gb_bill_count": gb_bill_count,
        "standard_first": True,
        "bid_source_is_filter_only": True,
    }


@app.get("/api/bid/source-filters")
def get_bid_source_filters() -> dict[str, Any]:
    rows = [clean_bid_artifact_row(row) for row in artifact_rows(BID_SOURCE_FILTER_CSV)]
    rows.sort(key=lambda row: int(row.get("display_order") or 0))
    return {
        "items": rows,
        "count": len(rows),
        "filter_only": True,
        "primary_navigation": "gb_standard_tree",
    }


@app.get("/api/bid/gb-bill/{bill_code_9}/items")
def get_bid_gb_bill_items(
    bill_code_9: str,
    source_file: str = "",
    section_name: str = "",
    q: str = "",
) -> dict[str, Any]:
    all_rows = [
        clean_bid_artifact_row(row)
        for row in artifact_rows(GB_BILL_BID_ITEM_CSV)
        if row.get("bill_code_9") == bill_code_9
    ]
    rows = filter_gb_bill_items(all_rows, source_file=source_file, section_name=section_name, q=q)
    rows.sort(key=lambda row: int(row.get("display_order") or 0))
    return {
        "bill_code_9": bill_code_9,
        "items": rows,
        "count": len(rows),
        "unfiltered_count": len(all_rows),
        "filters": {"source_file": source_file, "section_name": section_name, "q": q},
    }


@app.get("/api/bid/gb-bill/{bill_code_9}/composition")
def get_bid_gb_bill_composition(
    bill_code_9: str,
    source_file: str = "",
    section_name: str = "",
    q: str = "",
) -> dict[str, Any]:
    item_rows = [
        clean_bid_artifact_row(row)
        for row in artifact_rows(GB_BILL_BID_ITEM_CSV)
        if row.get("bill_code_9") == bill_code_9
    ]
    filtered_items = filter_gb_bill_items(item_rows, source_file=source_file, section_name=section_name, q=q)
    item_by_id = {row.get("bid_item_id", ""): row for row in filtered_items}
    allowed_ids = set(item_by_id)
    base_rows = [
        clean_bid_artifact_row(row)
        for row in artifact_rows(GB_BILL_COMPOSITION_CSV)
        if row.get("bill_code_9") == bill_code_9
        and (
            row.get("row_type") == "gb_bill"
            or row.get("bid_item_id") in allowed_ids
        )
    ]
    base_rows.sort(key=lambda row: int(row.get("display_order") or 0))
    rows = [
        enriched_composition_row(row, item_by_id.get(row.get("bid_item_id", "")), index)
        for index, row in enumerate(base_rows, start=1)
    ]
    return {
        "bill_code_9": bill_code_9,
        "rows": rows,
        "count": len(rows),
        "bid_item_count": len(filtered_items),
        "unfiltered_bid_item_count": len(item_rows),
        "recommended_row_count": sum(
            1
            for row in rows
            if row.get("row_type") in {"recommended_quota", "recommended_supplement"}
        ),
        "candidate_pool_marker_count": sum(
            1 for row in rows if row.get("row_type") == "candidate_pool_marker"
        ),
        "filters": {"source_file": source_file, "section_name": section_name, "q": q},
    }


@app.get("/api/bid/item/{bid_item_id}")
def get_bid_item(bid_item_id: str) -> dict[str, Any]:
    with connect() as con:
        item = fetch_one(con, "SELECT * FROM web_bid_item_display_rows WHERE bid_item_id = ?", (bid_item_id,))
        if not item:
            raise HTTPException(status_code=404, detail="bid item not found")
        edge = fetch_one(con, "SELECT * FROM web_bid_item_to_bill_edges WHERE bid_item_id = ?", (bid_item_id,))
    return {"item": item, "edge": edge}


@app.get("/api/bid/item/{bid_item_id}/candidates")
def get_bid_item_candidates(bid_item_id: str) -> dict[str, Any]:
    with connect() as con:
        item = fetch_one(con, "SELECT * FROM web_bid_item_display_rows WHERE bid_item_id = ?", (bid_item_id,))
        if not item:
            raise HTTPException(status_code=404, detail="bid item not found")
        candidates = fetch_all(
            con,
            """
            SELECT *
            FROM web_bid_item_quota_candidate_rows
            WHERE bid_item_id = ?
            ORDER BY
                CASE candidate_type
                    WHEN 'province_quota_with_enterprise_price' THEN 0
                    ELSE 1
                END,
                quota_source_code,
                supplement_candidate_code
            """,
            (bid_item_id,),
        )
    return {"item": item, "candidates": candidates, "count": len(candidates)}


@app.get("/api/bid/item/{bid_item_id}/composition_preview")
def get_bid_item_composition_preview(bid_item_id: str) -> dict[str, Any]:
    rows = [
        clean_bid_artifact_row(row)
        for row in artifact_rows(UI_COMPOSITION_CSV)
        if row.get("parent_bid_item_id") == bid_item_id
    ]
    if not rows:
        raise HTTPException(status_code=404, detail="bid item composition preview not found")
    rows.sort(key=lambda row: int(row.get("display_order") or 0))
    return clean_bid_artifact_payload({
        "bid_item_id": bid_item_id,
        "rows": rows,
        "count": len(rows),
        "has_bid_item_row": any(row.get("row_type") == "bid_item" for row in rows),
        "recommended_row_count": sum(
            1
            for row in rows
            if row.get("row_type") in {"recommended_quota", "recommended_supplement"}
        ),
    })


@app.get("/api/bid/item/{bid_item_id}/candidate_pool")
def get_bid_item_candidate_pool(
    bid_item_id: str,
    show_all: bool = False,
    candidate_group: str = "",
    candidate_type: str = "",
    risk: str = "",
) -> dict[str, Any]:
    all_rows = [
        clean_bid_artifact_row(row)
        for row in artifact_rows(UI_CANDIDATE_POOL_CSV)
        if row.get("bid_item_id") == bid_item_id
    ]
    if not all_rows:
        raise HTTPException(status_code=404, detail="bid item candidate pool not found")
    filtered = all_rows
    if candidate_group:
        filtered = [row for row in filtered if row.get("candidate_group") == candidate_group]
    if candidate_type:
        filtered = [row for row in filtered if candidate_type in (row.get("candidate_type") or "")]
    if risk:
        lowered = risk.lower()
        filtered = [row for row in filtered if lowered in (row.get("risk_flags") or "").lower()]
    default_rows = [
        row
        for row in filtered
        if row.get("default_visibility") == "show_in_composition_preview"
    ]
    collapsed_rows = [
        row
        for row in filtered
        if row.get("default_visibility") == "show_in_candidate_pool_collapsed"
    ]
    hidden_rows = [
        row
        for row in filtered
        if row.get("default_visibility") == "hidden_by_default"
    ]
    visible_rows = filtered if show_all else default_rows[:20]
    visible_rows.sort(key=lambda row: int(row.get("candidate_rank") or 999999))
    return clean_bid_artifact_payload({
        "bid_item_id": bid_item_id,
        "items": visible_rows,
        "count": len(visible_rows),
        "total_count": len(all_rows),
        "filtered_count": len(filtered),
        "default_display_count": len(default_rows),
        "collapsed_count": len(collapsed_rows),
        "hidden_count": len(hidden_rows),
        "show_all": show_all,
        "filters": {
            "candidate_group": candidate_group,
            "candidate_type": candidate_type,
            "risk": risk,
        },
    })


@app.get("/api/bid/item/{bid_item_id}/bottom-tabs")
def get_bid_item_bottom_tabs(bid_item_id: str) -> dict[str, Any]:
    item = find_bid_item_from_artifact(bid_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="bid item not found")
    return clean_bid_artifact_payload({
        "bid_item_id": bid_item_id,
        "tabs": bottom_tabs_model(),
        "count": len(bottom_tabs_model()),
        "readonly": True,
        "writes_mapping_result": False,
    })


@app.get("/api/bid/item/{bid_item_id}/feature-content")
def get_bid_item_feature_content(bid_item_id: str) -> dict[str, Any]:
    item = find_bid_item_from_artifact(bid_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="bid item not found")
    return clean_bid_artifact_payload({
        "bid_item_id": bid_item_id,
        "bill_code_9": item.get("bill_code_9", ""),
        "bill_name": item.get("gb_bill_name", ""),
        "bid_item_name": item.get("bid_item_name", ""),
        "bid_project_feature_summary": item.get("project_feature_summary", ""),
        "bid_project_feature_full": item.get("project_feature_full", ""),
        "bid_unit": item.get("unit", ""),
        "gb_project_feature_raw": "",
        "gb_work_content_raw": "",
        "status": "bid_feature_loaded_gb_context_pending",
        "remark": "本轮展示投标清单项目特征；GB/T 清单特征与工作内容后续接入只读标准库字段。",
    })


@app.get("/api/bid/item/{bid_item_id}/quantity-detail")
def get_bid_item_quantity_detail(bid_item_id: str) -> dict[str, Any]:
    item = find_bid_item_from_artifact(bid_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="bid item not found")
    return clean_bid_artifact_payload({
        "bid_item_id": bid_item_id,
        "raw_item_code": item.get("raw_item_code", ""),
        "normalized_item_code": item.get("normalized_item_code", ""),
        "unit": item.get("unit", ""),
        "quantity": item.get("quantity", ""),
        "quantity_expression": "",
        "calculation_process": "暂未接入工程量计算过程来源，本轮仅展示导入工程量。",
        "status": "quantity_imported_calculation_detail_pending",
        "readonly": True,
    })


@app.get("/api/bid/item/{bid_item_id}/price-breakdown")
def get_bid_item_price_breakdown(bid_item_id: str) -> dict[str, Any]:
    item = find_bid_item_from_artifact(bid_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="bid item not found")
    rows = [
        row
        for row in item_composition_rows(bid_item_id)
        if row.get("row_type") in {"recommended_quota", "recommended_supplement"}
    ]
    price_rows = [
        {
            "row_type": row.get("row_type", ""),
            "display_code": (
                f"ENT-{row.get('display_code', '')}"
                if row.get("row_type") == "recommended_supplement"
                and row.get("display_code", "")
                and not row.get("display_code", "").startswith("ENT-")
                else row.get("display_code", "")
            ),
            "display_name": row.get("display_name", ""),
            "unit": row.get("unit", ""),
            "province_total_fee": row.get("province_total_fee", ""),
            "enterprise_total_fee_candidate": row.get("enterprise_total_fee_candidate", ""),
            "governance_role": row.get("governance_role", ""),
            "candidate_rank": row.get("candidate_rank", ""),
            "risk_flags": row.get("risk_flags", ""),
            "row_status": row.get("row_status", ""),
        }
        for row in rows
    ]
    return clean_bid_artifact_payload({
        "bid_item_id": bid_item_id,
        "rows": price_rows,
        "count": len(price_rows),
        "readonly": True,
        "cost_calculation_enabled": False,
        "unit_conversion_status": "pending",
        "unit_conversion_note": "企业内部价常见 m2/m3 与省定额 100m2/100m3 的换算需在后续定价阶段显式处理；本轮不自动测算。",
    })


@app.get("/api/bid/item/{bid_item_id}/candidate-query-panel")
def get_bid_item_candidate_query_panel(bid_item_id: str) -> dict[str, Any]:
    item = find_bid_item_from_artifact(bid_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="bid item not found")
    candidates = [
        clean_bid_artifact_row(row)
        for row in artifact_rows(UI_CANDIDATE_POOL_CSV)
        if row.get("bid_item_id") == bid_item_id
    ]
    candidate_types = sorted({row.get("candidate_type", "") for row in candidates if row.get("candidate_type")})
    candidate_groups = sorted({row.get("candidate_group", "") for row in candidates if row.get("candidate_group")})
    return clean_bid_artifact_payload({
        "bid_item_id": bid_item_id,
        "panels": query_panel_model(),
        "count": len(query_panel_model()),
        "candidate_count": len(candidates),
        "candidate_types": candidate_types,
        "candidate_groups": candidate_groups,
        "readonly": True,
        "insert_enabled": False,
        "writes_mapping_result": False,
    })


@app.get("/api/bid/item/{bid_item_id}/consistency")
def get_bid_item_consistency(bid_item_id: str) -> dict[str, Any]:
    row = next(
        (row for row in artifact_rows(UI_CONSISTENCY_CSV) if row.get("bid_item_id") == bid_item_id),
        None,
    )
    if not row:
        raise HTTPException(status_code=404, detail="bid item consistency result not found")
    return clean_bid_artifact_payload({"bid_item_id": bid_item_id, "consistency": row})


@app.get("/api/bid/search")
def search_bid_items(q: str = "") -> dict[str, Any]:
    keyword = f"%{q.strip()}%"
    with connect() as con:
        if not q.strip():
            rows = fetch_all(
                con,
                "SELECT * FROM web_bid_item_display_rows ORDER BY CAST(source_row_id AS INTEGER) LIMIT 300",
            )
        else:
            rows = fetch_all(
                con,
                """
                SELECT *
                FROM web_bid_item_display_rows
                WHERE raw_item_code LIKE ?
                   OR normalized_item_code LIKE ?
                   OR bill_code_9 LIKE ?
                   OR bid_item_name LIKE ?
                   OR gb_bill_name LIKE ?
                   OR project_feature LIKE ?
                ORDER BY CAST(source_row_id AS INTEGER)
                LIMIT 300
                """,
                (keyword, keyword, keyword, keyword, keyword, keyword),
            )
    return {"items": rows, "count": len(rows)}


@app.get("/api/bid/summary")
def get_bid_summary() -> dict[str, Any]:
    with connect() as con:
        item_count = fetch_one(con, "SELECT COUNT(*) AS count FROM web_bid_item_display_rows", ())["count"]
        tree_count = fetch_one(con, "SELECT COUNT(*) AS count FROM web_bid_tree_nodes", ())["count"]
        candidate_count = fetch_one(con, "SELECT COUNT(*) AS count FROM web_bid_item_quota_candidate_rows", ())["count"]
        matched_count = fetch_one(
            con,
            "SELECT COUNT(*) AS count FROM web_bid_item_display_rows WHERE matched_bill_status = 'matched_gb_bill'",
            (),
        )["count"]
        parse_failed_count = fetch_one(
            con,
            "SELECT COUNT(*) AS count FROM web_bid_item_display_rows WHERE matched_bill_status = 'item_code_parse_failed'",
            (),
        )["count"]
        with_candidates_count = fetch_one(
            con,
            "SELECT COUNT(*) AS count FROM web_bid_item_display_rows WHERE CAST(candidate_quota_count AS INTEGER) > 0",
            (),
        )["count"]
    return {
        "item_count": item_count,
        "tree_node_count": tree_count,
        "candidate_row_count": candidate_count,
        "matched_gb_bill_count": matched_count,
        "unmatched_gb_bill_count": item_count - matched_count,
        "item_code_parse_failed_count": parse_failed_count,
        "bid_item_with_quota_candidates_count": with_candidates_count,
        "readonly": True,
        "writes_mapping_result": False,
        "cost_calculation_enabled": False,
        "generates_approved": False,
    }


@app.get("/api/tree")
def get_tree() -> dict[str, Any]:
    with connect() as con:
        rows = fetch_all(con, "SELECT * FROM web_bill_tree_nodes ORDER BY CAST(display_order AS INTEGER)")
    return {"items": rows, "count": len(rows)}


@app.get("/api/tree/hierarchy")
def get_tree_hierarchy() -> dict[str, Any]:
    with connect() as con:
        rows = fetch_all(con, "SELECT * FROM web_tree_hierarchy ORDER BY CAST(display_order AS INTEGER)")
    return {"items": rows, "count": len(rows)}


@app.get("/api/bill/{bill_code_9}")
def get_bill(bill_code_9: str) -> dict[str, Any]:
    with connect() as con:
        bill = fetch_one(con, "SELECT * FROM web_bill_tree_nodes WHERE bill_code_9 = ?", (bill_code_9,))
        if not bill:
            raise HTTPException(status_code=404, detail="bill not found")
    return {"bill": bill}


@app.get("/api/bill/{bill_code_9}/rows")
def get_bill_rows(bill_code_9: str) -> dict[str, Any]:
    with connect() as con:
        bill = fetch_one(con, "SELECT * FROM web_bill_tree_nodes WHERE bill_code_9 = ?", (bill_code_9,))
        if not bill:
            raise HTTPException(status_code=404, detail="bill not found")
        rows = fetch_all(
            con,
            """
            SELECT
                e.bill_code_9,
                e.quota_source_code,
                e.quota_raw_name,
                e.quota_unit,
                e.mapping_type,
                e.mapping_confidence,
                e.mapping_basis,
                e.governance_role,
                e.issue_types,
                e.risk_level AS edge_risk_level,
                q.quota_name_candidate,
                q.quota_unit AS quota_display_unit,
                q.province_labor_fee,
                q.province_material_fee,
                q.province_machine_fee,
                q.province_management_fee,
                q.province_total_fee,
                q.enterprise_candidate_status,
                q.enterprise_price_unit_candidate,
                q.unit_conversion_factor,
                q.unit_conversion_note,
                q.enterprise_labor_fee_candidate,
                q.enterprise_material_fee_candidate,
                q.enterprise_machine_fee_candidate,
                q.enterprise_management_fee_candidate,
                q.enterprise_total_fee_candidate,
                q.diff_total_rate,
                q.enterprise_price_status,
                q.ai_recommendation_summary,
                q.review_status,
                q.ui_status,
                q.risk_flags,
                d.selected_price_source AS draft_selected_price_source,
                d.draft_labor_fee,
                d.draft_material_fee,
                d.draft_machine_fee,
                d.draft_management_fee,
                d.draft_total_fee,
                d.total_manual_override,
                d.draft_status,
                d.lock_status,
                d.save_status,
                d.draft_version,
                d.last_saved_at,
                d.cost_engineer_comment,
                d.updated_at AS draft_updated_at
            FROM web_bill_quota_edges e
            LEFT JOIN web_quota_display_rows q ON q.quota_source_code = e.quota_source_code
            LEFT JOIN web_price_review_draft d
                ON d.bill_code_9 = e.bill_code_9 AND d.quota_source_code = e.quota_source_code
            WHERE e.bill_code_9 = ?
            ORDER BY CAST(e.display_order AS INTEGER)
            """,
            (bill_code_9,),
        )
        supplements = fetch_all(con, "SELECT * FROM web_supplement_display_rows ORDER BY enterprise_item_id LIMIT 200")
    return {"bill": bill, "rows": rows, "supplements": supplements, "count": len(rows)}


@app.get("/api/bill/{bill_code_9}/quotas")
def get_bill_quotas(bill_code_9: str) -> dict[str, Any]:
    return get_bill_rows(bill_code_9)


@app.get("/api/quota/{quota_source_code}")
def get_quota(quota_source_code: str) -> dict[str, Any]:
    with connect() as con:
        quota = fetch_one(con, "SELECT * FROM web_quota_display_rows WHERE quota_source_code = ?", (quota_source_code,))
        if not quota:
            raise HTTPException(status_code=404, detail="quota not found")
        mappings = fetch_all(
            con,
            """
            SELECT e.*, b.bill_name
            FROM web_bill_quota_edges e
            LEFT JOIN web_bill_tree_nodes b ON b.bill_code_9 = e.bill_code_9
            WHERE e.quota_source_code = ?
            ORDER BY e.bill_code_9
            LIMIT 100
            """,
            (quota_source_code,),
        )
    return {"quota": quota, "mappings": mappings}


@app.get("/api/quota/{quota_source_code}/price")
def get_quota_price(quota_source_code: str) -> dict[str, Any]:
    with connect() as con:
        quota = fetch_one(con, "SELECT * FROM web_quota_display_rows WHERE quota_source_code = ?", (quota_source_code,))
        if not quota:
            raise HTTPException(status_code=404, detail="quota not found")
    return {"price": quota}


@app.get("/api/draft/{bill_code_9}/{quota_source_code}")
def get_draft(bill_code_9: str, quota_source_code: str) -> dict[str, Any]:
    with connect() as con:
        draft = fetch_one(
            con,
            "SELECT * FROM web_price_review_draft WHERE bill_code_9 = ? AND quota_source_code = ?",
            (bill_code_9, quota_source_code),
        )
    return {"draft": draft}


@app.post("/api/draft/save")
def save_draft(payload: DraftPayload) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        before = fetch_one(
            con,
            "SELECT * FROM web_price_review_draft WHERE bill_code_9 = ? AND quota_source_code = ?",
            (payload.bill_code_9, payload.quota_source_code),
        )
        data = normalize_payload(payload, before)
        created_at = before.get("created_at") if before else now
        con.execute(
            """
            INSERT INTO web_price_review_draft
            (draft_id, bill_code_9, quota_source_code, decision_scope, selected_price_source,
             draft_labor_fee, draft_material_fee, draft_machine_fee, draft_management_fee,
             draft_total_fee, total_manual_override, draft_status, cost_engineer_comment,
             created_at, updated_at, draft_version, save_status, last_saved_at,
             local_cache_key, lock_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bill_code_9, quota_source_code) DO UPDATE SET
                decision_scope = excluded.decision_scope,
                selected_price_source = excluded.selected_price_source,
                draft_labor_fee = excluded.draft_labor_fee,
                draft_material_fee = excluded.draft_material_fee,
                draft_machine_fee = excluded.draft_machine_fee,
                draft_management_fee = excluded.draft_management_fee,
                draft_total_fee = excluded.draft_total_fee,
                total_manual_override = excluded.total_manual_override,
                draft_status = excluded.draft_status,
                cost_engineer_comment = excluded.cost_engineer_comment,
                updated_at = excluded.updated_at,
                draft_version = excluded.draft_version,
                save_status = excluded.save_status,
                last_saved_at = excluded.last_saved_at,
                local_cache_key = excluded.local_cache_key,
                lock_status = excluded.lock_status
            """,
            (
                data["draft_id"],
                data["bill_code_9"],
                data["quota_source_code"],
                data["decision_scope"],
                data["selected_price_source"],
                data["draft_labor_fee"],
                data["draft_material_fee"],
                data["draft_machine_fee"],
                data["draft_management_fee"],
                data["draft_total_fee"],
                data["total_manual_override"],
                data["draft_status"],
                data["cost_engineer_comment"],
                created_at,
                now,
                data["draft_version"],
                data["save_status"],
                now,
                data["local_cache_key"],
                data["lock_status"],
            ),
        )
        after = fetch_one(
            con,
            "SELECT * FROM web_price_review_draft WHERE bill_code_9 = ? AND quota_source_code = ?",
            (data["bill_code_9"], data["quota_source_code"]),
        )
        write_audit(con, "save_draft", data["bill_code_9"], data["quota_source_code"], before, after, payload.actor)
        con.commit()
    return {"saved": True, "draft": after}


@app.post("/api/draft/clear")
def clear_draft(payload: ClearDraftPayload) -> dict[str, Any]:
    with connect() as con:
        before = fetch_one(
            con,
            "SELECT * FROM web_price_review_draft WHERE bill_code_9 = ? AND quota_source_code = ?",
            (payload.bill_code_9, payload.quota_source_code),
        )
        if before:
            con.execute(
                "DELETE FROM web_price_review_draft WHERE bill_code_9 = ? AND quota_source_code = ?",
                (payload.bill_code_9, payload.quota_source_code),
            )
        write_audit(con, "clear_draft", payload.bill_code_9, payload.quota_source_code, before, None, payload.actor)
        con.commit()
    return {"cleared": True, "had_draft": bool(before)}


@app.get("/api/draft/export")
def export_draft() -> dict[str, Any]:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        rows = fetch_all(con, f"SELECT {', '.join(DRAFT_EXPORT_FIELDS)} FROM web_price_review_draft ORDER BY updated_at DESC")
    write_csv(CURRENT_EXPORT_PATH, rows, DRAFT_EXPORT_FIELDS)
    return {"exported": True, "count": len(rows), "path": str(CURRENT_EXPORT_PATH)}


@app.get("/api/draft/export_snapshot")
def export_draft_snapshot() -> dict[str, Any]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    exported_at = datetime.now().isoformat(timespec="seconds")
    path = EXPORT_DIR / f"web_price_review_draft_export_{batch_id}.csv"
    with connect() as con:
        rows = fetch_all(con, f"SELECT {', '.join(DRAFT_EXPORT_FIELDS)} FROM web_price_review_draft ORDER BY updated_at DESC")
        for row in rows:
            row["exported_at"] = exported_at
            row["exported_batch_id"] = batch_id
            row["save_status"] = "exported"
        write_csv(path, rows, DRAFT_EXPORT_FIELDS)
        con.execute("UPDATE web_price_review_draft SET exported_at = ?, exported_batch_id = ?, save_status = 'exported'", (exported_at, batch_id))
        write_audit(con, "export_draft_snapshot", "", "", None, {"path": str(path), "row_count": len(rows), "batch_id": batch_id}, "prototype_user")
        con.commit()
    write_snapshot_manifest(DRAFT_SNAPSHOT_MANIFEST, "draft", path, len(rows))
    return {"exported": True, "count": len(rows), "path": str(path), "batch_id": batch_id}


@app.get("/api/audit/export_snapshot")
def export_audit_snapshot() -> dict[str, Any]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = EXPORT_DIR / f"web_audit_log_export_{batch_id}.csv"
    with connect() as con:
        rows = fetch_all(con, f"SELECT {', '.join(AUDIT_EXPORT_FIELDS)} FROM web_audit_log ORDER BY created_at")
    write_csv(path, rows, AUDIT_EXPORT_FIELDS)
    write_snapshot_manifest(AUDIT_SNAPSHOT_MANIFEST, "audit", path, len(rows))
    return {"exported": True, "count": len(rows), "path": str(path), "batch_id": batch_id}


@app.get("/api/search")
def search(q: str = "") -> dict[str, Any]:
    keyword = f"%{q.strip()}%"
    if not q.strip():
        return {"bills": [], "quotas": [], "count": 0}
    with connect() as con:
        bills = fetch_all(
            con,
            """
            SELECT * FROM web_bill_tree_nodes
            WHERE bill_code_9 LIKE ? OR bill_name LIKE ? OR section_name LIKE ?
            ORDER BY CAST(display_order AS INTEGER)
            LIMIT 50
            """,
            (keyword, keyword, keyword),
        )
        quotas = fetch_all(
            con,
            """
            SELECT * FROM web_quota_display_rows
            WHERE quota_source_code LIKE ? OR quota_name_candidate LIKE ?
            ORDER BY quota_source_code
            LIMIT 50
            """,
            (keyword, keyword),
        )
    return {"bills": bills, "quotas": quotas, "count": len(bills) + len(quotas)}


@app.get("/api/supplements")
def supplements() -> dict[str, Any]:
    with connect() as con:
        rows = fetch_all(con, "SELECT * FROM web_supplement_display_rows ORDER BY enterprise_item_id")
    return {"items": rows, "count": len(rows)}
