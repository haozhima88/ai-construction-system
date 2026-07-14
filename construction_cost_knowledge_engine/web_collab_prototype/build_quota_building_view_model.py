from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parents[1]
RUNS = ENGINE_ROOT / "data" / "private" / "reference_extraction" / "runs"
GB_RUN = RUNS / "GB50854_2024_stageB_docx_full"
EVIDENCE_RUN = RUNS / "GB50854_DUAL_SOURCE_EVIDENCE_LOCK_1"
GD_RUN = RUNS / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1"
MAP_RUN = RUNS / "MAP_GB50854_TO_GD2018_BUILDING_A_FULL_1"
DATA_DIR = Path(__file__).resolve().parent / "data"
READONLY_DB = DATA_DIR / "web_quota_building_readonly.sqlite"
DRAFT_DB = DATA_DIR / "web_quota_building_draft.sqlite"


TABLE_FILES = {
    "bill_items": GB_RUN / "bill_item_reference_all_candidate.csv",
    "context_rules": GB_RUN / "bill_context_rules_all.csv",
    "evidence_backlog": EVIDENCE_RUN / "gb50854_evidence_link_backlog.csv",
    "authority_samples": EVIDENCE_RUN / "gb50854_authority_sample_review.csv",
    "bill_matrix": MAP_RUN / "building_bill_to_quota_matrix_472.csv",
    "mapping_edges": MAP_RUN / "building_bill_to_quota_edges.csv",
    "quota_routing": MAP_RUN / "building_quota_to_bill_routing.csv",
    "zero_candidate_bills": MAP_RUN / "building_zero_candidate_bills.csv",
    "unrouted_quotas": MAP_RUN / "building_unrouted_quotas.csv",
    "shared_components": MAP_RUN / "building_shared_components.csv",
    "mapping_issues": MAP_RUN / "building_mapping_issues.csv",
    "mapping_dashboard": MAP_RUN / "building_mapping_dashboard.csv",
    "source_documents": GD_RUN / "gd_building_source_documents.csv",
    "source_pages": GD_RUN / "gd_building_source_pages.csv",
    "sections": GD_RUN / "gd_building_chapter_sections.csv",
    "quota_items": GD_RUN / "gd_building_quota_items.csv",
    "price_snapshots": GD_RUN / "gd_building_quota_price_snapshots.csv",
    "resources": GD_RUN / "gd_building_resource_components.csv",
    "work_blocks": GD_RUN / "gd_building_work_content_blocks.csv",
    "work_scope_links": GD_RUN / "gd_building_work_content_scope_links.csv",
    "quantity_rule_blocks": GD_RUN / "gd_building_quantity_rule_blocks.csv",
    "quantity_rule_scope_links": GD_RUN / "gd_building_quantity_rule_scope_links.csv",
    "conversion_rules": GD_RUN / "gd_building_conversion_rules.csv",
    "note_clauses": GD_RUN / "gd_building_note_clauses.csv",
    "parse_issues": GD_RUN / "gd_building_parse_issues.csv",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def import_csv(con: sqlite3.Connection, table: str, path: Path) -> int:
    fields, rows = read_csv(path)
    con.execute(f"DROP TABLE IF EXISTS {quote(table)}")
    con.execute(f"CREATE TABLE {quote(table)} ({', '.join(f'{quote(field)} TEXT' for field in fields)})")
    if rows:
        placeholders = ", ".join("?" for _ in fields)
        con.executemany(
            f"INSERT INTO {quote(table)} ({', '.join(quote(field) for field in fields)}) VALUES ({placeholders})",
            [tuple(row.get(field, "") for field in fields) for row in rows],
        )
    return len(rows)


def build_readonly() -> dict[str, object]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = READONLY_DB.with_suffix(".sqlite.tmp")
    if temporary.exists():
        temporary.unlink()
    counts: dict[str, int] = {}
    with sqlite3.connect(temporary) as con:
        con.execute("PRAGMA journal_mode=DELETE")
        for table, path in TABLE_FILES.items():
            counts[table] = import_csv(con, table, path)
        con.execute("CREATE INDEX idx_bill_items_code ON bill_items(bill_code_9)")
        con.execute("CREATE INDEX idx_edges_bill ON mapping_edges(bill_code_9)")
        con.execute("CREATE INDEX idx_edges_quota ON mapping_edges(quota_uid)")
        con.execute("CREATE INDEX idx_quota_uid ON quota_items(quota_uid)")
        con.execute("CREATE INDEX idx_quota_source_code ON quota_items(source_code)")
        con.execute("CREATE INDEX idx_resources_quota ON resources(quota_uid)")
        con.execute("CREATE INDEX idx_work_link_quota ON work_scope_links(quota_uid)")
        con.execute("CREATE INDEX idx_rule_link_quota ON quantity_rule_scope_links(quota_uid)")
        con.execute("CREATE INDEX idx_evidence_bill ON evidence_backlog(bill_reference_id)")
        con.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        metadata = {
            "schema_version": "quota_building_readonly_v1",
            "created_at": datetime.now().astimezone().isoformat(),
            "source_role": "authority_source",
            "extraction_proxy_role": "extraction_proxy",
            "baseline_role": "derived_reference_candidate",
            "authority_conflict_rule": "official_pdf_wins",
            "bill_count": str(counts["bill_items"]),
            "quota_count": str(counts["quota_items"]),
            "mapping_edge_count": str(counts["mapping_edges"]),
            "approved_count": "0",
        }
        for table, path in TABLE_FILES.items():
            metadata[f"hash:{table}"] = sha256(path)
            metadata[f"path:{table}"] = str(path)
        con.executemany("INSERT INTO metadata(key, value) VALUES (?, ?)", metadata.items())
        con.execute(
            "CREATE TABLE v1_v2_registry (version_id TEXT PRIMARY KEY, artifact_path TEXT, artifact_status TEXT, quota_count TEXT, resource_count TEXT, promotion_status TEXT, remark TEXT)"
        )
        con.executemany(
            "INSERT INTO v1_v2_registry VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "GOLDEN_SLICE_GD2018_A111_V1",
                    str(RUNS / "GD2018_stage2R_A111_full"),
                    "registered_existing_golden_slice_no_mutation",
                    "137", "629", "not_applicable_readonly",
                    "Historical V1 remains read-only and is represented by the protected A1.1 full run.",
                ),
                (
                    "GOLDEN_SLICE_GD2018_A111_V2_CANDIDATE",
                    str(RUNS / "GOLDEN_SLICE_GD2018_A111_V2_CANDIDATE"),
                    "candidate",
                    "137", "629", "pending_human_confirmation",
                    "V2 parser correction candidate; no automatic promotion or approval.",
                ),
            ],
        )
        con.commit()
    con.close()
    os.replace(temporary, READONLY_DB)
    return {"path": str(READONLY_DB), "sha256": sha256(READONLY_DB), "counts": counts}


def ensure_draft() -> dict[str, object]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DRAFT_DB) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mapping_drafts (
                draft_id TEXT PRIMARY KEY,
                source_edge_id TEXT NOT NULL,
                source_bill_code_9 TEXT NOT NULL,
                target_bill_code_9 TEXT,
                quota_uid TEXT NOT NULL,
                action_type TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                draft_status TEXT NOT NULL,
                review_status TEXT NOT NULL DEFAULT 'not_reviewed',
                operation_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS review_states (
                review_key TEXT PRIMARY KEY,
                bill_code_9 TEXT NOT NULL,
                quota_uid TEXT,
                review_status TEXT NOT NULL,
                comment TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                audit_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                draft_id TEXT,
                bill_code_9 TEXT,
                quota_uid TEXT,
                before_json TEXT,
                after_json TEXT,
                created_at TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT 'quota_building_user'
            )
            """
        )
        con.commit()
        draft_count = con.execute("SELECT COUNT(*) FROM mapping_drafts").fetchone()[0]
        audit_count = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    return {"path": str(DRAFT_DB), "draft_count": draft_count, "audit_count": audit_count}


def main() -> None:
    result = {"readonly": build_readonly(), "draft": ensure_draft()}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
