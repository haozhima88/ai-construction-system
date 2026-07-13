from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import sqlite3
import subprocess
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTER_ROOT = PROJECT_ROOT.parent
RUN_DIR = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs" / "BID_COLLAB_READONLY_TREE_PROTOTYPE_1"
DB_PATH = PROJECT_ROOT / "web_collab_prototype" / "data" / "web_collab_readonly.sqlite"

IMPORT_SCHEMA_AUDIT_CSV = RUN_DIR / "import_bid_records_schema_audit.csv"
NORMALIZATION_AUDIT_CSV = RUN_DIR / "bid_item_code_normalization_audit.csv"
BID_TREE_NODES_CSV = RUN_DIR / "web_bid_tree_nodes.csv"
BID_ITEM_ROWS_CSV = RUN_DIR / "web_bid_item_display_rows.csv"
BID_EDGES_CSV = RUN_DIR / "web_bid_item_to_bill_edges.csv"
BID_CANDIDATES_CSV = RUN_DIR / "web_bid_item_quota_candidate_rows.csv"

IMPORT_AUDIT_FIELDS = [
    "db_path",
    "table_exists",
    "row_count",
    "detected_columns",
    "item_code_column",
    "item_name_column",
    "unit_column",
    "quantity_column",
    "project_name_column",
    "section_column",
    "amount_column",
    "parse_status",
    "issue",
    "remark",
]
NORMALIZATION_FIELDS = [
    "source_row_id",
    "raw_item_code",
    "normalized_item_code",
    "normalized_item_code_length",
    "bill_code_9",
    "item_suffix",
    "normalization_rule",
    "matched_gb_bill",
    "matched_bill_name",
    "issue",
    "review_status",
]
BID_TREE_FIELDS = [
    "node_id",
    "parent_id",
    "node_type",
    "label",
    "raw_item_code",
    "normalized_item_code",
    "bill_code_9",
    "bill_name",
    "item_suffix",
    "project_name",
    "section_name",
    "child_count",
    "candidate_quota_count",
    "risk_level",
    "display_order",
]
BID_ITEM_FIELDS = [
    "bid_item_id",
    "source_row_id",
    "raw_item_code",
    "normalized_item_code",
    "bill_code_9",
    "item_suffix",
    "bid_item_name",
    "gb_bill_name",
    "unit",
    "quantity",
    "project_feature",
    "description",
    "matched_bill_status",
    "candidate_quota_count",
    "enterprise_template_candidate_count",
    "risk_level",
    "review_status",
]
BID_EDGE_FIELDS = [
    "bid_item_id",
    "normalized_item_code",
    "bill_code_9",
    "bill_name",
    "match_type",
    "match_confidence",
    "issue",
    "review_status",
]
BID_CANDIDATE_FIELDS = [
    "bid_item_id",
    "normalized_item_code",
    "bill_code_9",
    "bill_name",
    "quota_source_code",
    "quota_name_candidate",
    "governance_role",
    "mapping_confidence",
    "enterprise_price_candidate_status",
    "enterprise_total_fee_candidate",
    "supplement_candidate_code",
    "supplement_name",
    "candidate_type",
    "risk_flags",
    "review_status",
]


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def psql_path() -> str:
    candidates = [
        Path(r"C:\Program Files\PostgreSQL\18\bin\psql.exe"),
        Path(r"C:\Program Files\PostgreSQL\17\bin\psql.exe"),
        Path(r"C:\Program Files\PostgreSQL\16\bin\psql.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "psql"


def run_psql_csv(sql: str) -> list[dict[str, str]]:
    env_values = load_env(OUTER_ROOT / ".env")
    env = os.environ.copy()
    env["PGPASSWORD"] = env_values.get("DB_PASSWORD", "")
    cmd = [
        psql_path(),
        "-h",
        env_values.get("DB_HOST", "localhost"),
        "-p",
        env_values.get("DB_PORT", "5432"),
        "-U",
        env_values.get("DB_USER", "postgres"),
        "-d",
        env_values.get("DB_NAME", "ai_system"),
        "--no-psqlrc",
        "-q",
        "-c",
        f"COPY ({sql}) TO STDOUT WITH CSV HEADER",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", env=env)
    return list(csv.DictReader(io.StringIO(result.stdout)))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def value(row: dict[str, Any], *names: str) -> str:
    for name in names:
        raw = row.get(name)
        if raw not in (None, ""):
            return str(raw).strip()
    return ""


def normalize_item_code(raw: str) -> dict[str, str]:
    digits = re.sub(r"\D+", "", raw or "")
    if len(digits) == 12:
        return {
            "normalized_item_code": digits,
            "bill_code_9": digits[:9],
            "item_suffix": digits[9:],
            "normalization_rule": "digits_only_12_split_9_3",
            "issue": "",
        }
    if len(digits) == 11:
        normalized = "0" + digits
        return {
            "normalized_item_code": normalized,
            "bill_code_9": normalized[:9],
            "item_suffix": normalized[9:],
            "normalization_rule": "digits_only_11_add_leading_zero_then_split_9_3",
            "issue": "",
        }
    if len(digits) == 9:
        return {
            "normalized_item_code": digits,
            "bill_code_9": digits,
            "item_suffix": "",
            "normalization_rule": "digits_only_9_as_bill_code",
            "issue": "",
        }
    return {
        "normalized_item_code": digits,
        "bill_code_9": "",
        "item_suffix": "",
        "normalization_rule": "digits_only_unrecognized_length",
        "issue": "item_code_parse_failed",
    }


def risk_level(issue: str, candidate_count: int) -> str:
    if issue or candidate_count == 0:
        return "high"
    if candidate_count >= 50:
        return "medium"
    return "low"


def safe_id(prefix: str, text: str, index: int) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{index:04d}-{digest}"


def load_web_db() -> tuple[
    dict[str, dict[str, str]],
    dict[str, list[dict[str, str]]],
    dict[str, dict[str, str]],
    list[dict[str, str]],
]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        bills = {
            row["bill_code_9"]: dict(row)
            for row in con.execute("SELECT * FROM web_bill_tree_nodes").fetchall()
        }
        edges: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in con.execute("SELECT * FROM web_bill_quota_edges ORDER BY CAST(display_order AS INTEGER)").fetchall():
            edges[row["bill_code_9"]].append(dict(row))
        quotas = {
            row["quota_source_code"]: dict(row)
            for row in con.execute("SELECT * FROM web_quota_display_rows").fetchall()
        }
        supplements = [dict(row) for row in con.execute("SELECT * FROM web_supplement_display_rows").fetchall()]
    finally:
        con.close()
    return bills, edges, quotas, supplements


def cjk_bigrams(text: str) -> set[str]:
    cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", text or "")
    return {cleaned[i : i + 2] for i in range(max(0, len(cleaned) - 1)) if len(cleaned[i : i + 2]) == 2}


def supplement_matches(item: dict[str, str], supplements: list[dict[str, str]]) -> list[dict[str, str]]:
    item_tokens = cjk_bigrams(value(item, "item_name") + value(item, "feature"))
    if not item_tokens:
        return []
    scored: list[tuple[int, dict[str, str]]] = []
    for supplement in supplements:
        sup_tokens = cjk_bigrams(value(supplement, "standard_name_candidate", "raw_name"))
        score = len(item_tokens & sup_tokens)
        if score >= 2:
            scored.append((score, supplement))
    scored.sort(key=lambda pair: (-pair[0], value(pair[1], "enterprise_item_id")))
    return [row for _score, row in scored[:3]]


def build_rows(import_rows: list[dict[str, str]]) -> dict[str, list[dict[str, Any]] | dict[str, int]]:
    bills, edges_by_bill, quotas_by_code, supplements = load_web_db()
    schema_columns = list(import_rows[0].keys()) if import_rows else []
    row_count = len(import_rows)
    write_csv(
        IMPORT_SCHEMA_AUDIT_CSV,
        [
            {
                "db_path": "postgresql://localhost:5432/ai_system public.import_bid_records",
                "table_exists": "true",
                "row_count": row_count,
                "detected_columns": "|".join(schema_columns),
                "item_code_column": "item_code" if "item_code" in schema_columns else "",
                "item_name_column": "item_name" if "item_name" in schema_columns else "",
                "unit_column": "unit" if "unit" in schema_columns else "",
                "quantity_column": "quantity" if "quantity" in schema_columns else "",
                "project_name_column": "project_name" if "project_name" in schema_columns else "",
                "section_column": "category" if "category" in schema_columns else "",
                "amount_column": "total_price" if "total_price" in schema_columns else "",
                "parse_status": "readable",
                "issue": "",
                "remark": "Read-only local PostgreSQL staging table; no import_bid_records SQLite file found.",
            }
        ],
        IMPORT_AUDIT_FIELDS,
    )

    normalization_rows: list[dict[str, Any]] = []
    item_rows: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    project_ids: OrderedDict[str, str] = OrderedDict()
    section_ids: OrderedDict[tuple[str, str], str] = OrderedDict()
    bill_ids: OrderedDict[tuple[str, str, str], str] = OrderedDict()
    project_child_sections: Counter[str] = Counter()
    section_child_bills: Counter[tuple[str, str]] = Counter()
    bill_child_items: Counter[tuple[str, str, str]] = Counter()
    project_candidate_counts: Counter[str] = Counter()
    section_candidate_counts: Counter[tuple[str, str]] = Counter()
    bill_candidate_counts: Counter[tuple[str, str, str]] = Counter()
    bill_names: dict[tuple[str, str, str], str] = {}
    bill_risks: dict[tuple[str, str, str], str] = {}

    matched_count = 0
    parse_failed_count = 0
    candidate_item_count = 0
    display_order = 1

    item_nodes: list[dict[str, Any]] = []
    for idx, row in enumerate(import_rows, start=1):
        source_row_id = value(row, "id") or str(idx)
        raw_code = value(row, "item_code")
        normalized = normalize_item_code(raw_code)
        bill_code = normalized["bill_code_9"]
        bill = bills.get(bill_code)
        candidate_edges = edges_by_bill.get(bill_code, []) if bill else []
        candidate_count = len(candidate_edges)
        enterprise_count = sum(
            1
            for edge in candidate_edges
            if (quotas_by_code.get(edge["quota_source_code"], {}).get("enterprise_total_fee_candidate") not in (None, ""))
            or (quotas_by_code.get(edge["quota_source_code"], {}).get("enterprise_candidate_status") == "matched")
        )
        issue = normalized["issue"]
        if issue:
            parse_failed_count += 1
        elif not bill:
            issue = "gb_bill_not_found"
        else:
            matched_count += 1
        if candidate_count:
            candidate_item_count += 1
        row_risk = risk_level(issue, candidate_count)
        matched_status = "matched_gb_bill" if bill else ("item_code_parse_failed" if normalized["issue"] else "gb_bill_not_found")
        bid_item_id = f"BID-{int(source_row_id):06d}" if source_row_id.isdigit() else safe_id("BID", source_row_id, idx)
        project_name = value(row, "project_name") or value(row, "source_file_name") or "未命名项目"
        section_name = value(row, "category") or value(row, "source_sheet_name") or "未分部"
        project_key = project_name
        if project_key not in project_ids:
            project_ids[project_key] = safe_id("BIDPROJECT", project_key, len(project_ids) + 1)
        section_key = (project_key, section_name)
        if section_key not in section_ids:
            section_ids[section_key] = safe_id("BIDSECTION", f"{project_key}|{section_name}", len(section_ids) + 1)
            project_child_sections[project_key] += 1
        bill_key = (project_key, section_name, bill_code or f"UNMATCHED-{source_row_id}")
        if bill_key not in bill_ids:
            bill_ids[bill_key] = safe_id("BIDBILL", "|".join(bill_key), len(bill_ids) + 1)
            section_child_bills[section_key] += 1
            bill_names[bill_key] = value(bill or {}, "bill_name") or ("未识别清单编码" if normalized["issue"] else "未匹配 GB/T 清单")
            bill_risks[bill_key] = row_risk
        bill_child_items[bill_key] += 1
        project_candidate_counts[project_key] += candidate_count
        section_candidate_counts[section_key] += candidate_count
        bill_candidate_counts[bill_key] += candidate_count
        bill_risks[bill_key] = "high" if row_risk == "high" else bill_risks.get(bill_key, row_risk)

        normalization_rows.append(
            {
                "source_row_id": source_row_id,
                "raw_item_code": raw_code,
                "normalized_item_code": normalized["normalized_item_code"],
                "normalized_item_code_length": len(normalized["normalized_item_code"]),
                "bill_code_9": bill_code,
                "item_suffix": normalized["item_suffix"],
                "normalization_rule": normalized["normalization_rule"],
                "matched_gb_bill": "true" if bill else "false",
                "matched_bill_name": value(bill or {}, "bill_name"),
                "issue": issue,
                "review_status": "readonly_preview" if not issue else "manual_review_required",
            }
        )
        item_row = {
            "bid_item_id": bid_item_id,
            "source_row_id": source_row_id,
            "raw_item_code": raw_code,
            "normalized_item_code": normalized["normalized_item_code"],
            "bill_code_9": bill_code,
            "item_suffix": normalized["item_suffix"],
            "bid_item_name": value(row, "item_name"),
            "gb_bill_name": value(bill or {}, "bill_name"),
            "unit": value(row, "unit"),
            "quantity": value(row, "quantity"),
            "project_feature": value(row, "feature"),
            "description": f"source_file={value(row, 'source_file_name')}; sheet={value(row, 'source_sheet_name')}; source_row_index={value(row, 'source_row_index')}",
            "matched_bill_status": matched_status,
            "candidate_quota_count": candidate_count,
            "enterprise_template_candidate_count": enterprise_count,
            "risk_level": row_risk,
            "review_status": "readonly_preview" if not issue else "manual_review_required",
        }
        item_rows.append(item_row)
        edge_rows.append(
            {
                "bid_item_id": bid_item_id,
                "normalized_item_code": normalized["normalized_item_code"],
                "bill_code_9": bill_code,
                "bill_name": value(bill or {}, "bill_name"),
                "match_type": "item_code_bill_code_9" if bill else "unmatched",
                "match_confidence": "1.00" if bill else "0.00",
                "issue": issue,
                "review_status": "readonly_preview" if not issue else "manual_review_required",
            }
        )
        for edge in candidate_edges:
            quota = quotas_by_code.get(edge["quota_source_code"], {})
            risk_flags = ";".join(
                token
                for token in [
                    value(edge, "issue_types"),
                    value(edge, "risk_level"),
                    value(quota, "risk_flags"),
                ]
                if token
            )
            candidate_rows.append(
                {
                    "bid_item_id": bid_item_id,
                    "normalized_item_code": normalized["normalized_item_code"],
                    "bill_code_9": bill_code,
                    "bill_name": value(bill or {}, "bill_name"),
                    "quota_source_code": value(edge, "quota_source_code"),
                    "quota_name_candidate": value(quota, "quota_name_candidate") or value(edge, "quota_raw_name"),
                    "governance_role": value(edge, "governance_role"),
                    "mapping_confidence": value(edge, "mapping_confidence"),
                    "enterprise_price_candidate_status": value(quota, "enterprise_price_status", "enterprise_candidate_status"),
                    "enterprise_total_fee_candidate": value(quota, "enterprise_total_fee_candidate"),
                    "supplement_candidate_code": "",
                    "supplement_name": "",
                    "candidate_type": "province_quota_with_enterprise_price",
                    "risk_flags": risk_flags,
                    "review_status": "readonly_preview",
                }
            )
        for supplement in supplement_matches(row, supplements):
            candidate_rows.append(
                {
                    "bid_item_id": bid_item_id,
                    "normalized_item_code": normalized["normalized_item_code"],
                    "bill_code_9": bill_code,
                    "bill_name": value(bill or {}, "bill_name"),
                    "quota_source_code": "",
                    "quota_name_candidate": "",
                    "governance_role": "supplement_preview",
                    "mapping_confidence": "text_overlap",
                    "enterprise_price_candidate_status": value(supplement, "match_status") or "candidate",
                    "enterprise_total_fee_candidate": value(supplement, "enterprise_total_fee"),
                    "supplement_candidate_code": value(supplement, "enterprise_item_id", "source_code"),
                    "supplement_name": value(supplement, "standard_name_candidate", "raw_name"),
                    "candidate_type": "supplement_candidate",
                    "risk_flags": "supplement_candidate_requires_manual_review",
                    "review_status": "readonly_preview",
                }
            )
        item_nodes.append(
            {
                "node_id": bid_item_id,
                "parent_id": bill_ids[bill_key],
                "node_type": "bid_item",
                "label": f"{raw_code} {value(row, 'item_name')}",
                "raw_item_code": raw_code,
                "normalized_item_code": normalized["normalized_item_code"],
                "bill_code_9": bill_code,
                "bill_name": value(bill or {}, "bill_name"),
                "item_suffix": normalized["item_suffix"],
                "project_name": project_name,
                "section_name": section_name,
                "child_count": "0",
                "candidate_quota_count": str(candidate_count),
                "risk_level": row_risk,
                "display_order": "0",
            }
        )

    tree_rows: list[dict[str, Any]] = []
    for project_key, project_id in project_ids.items():
        tree_rows.append(
            {
                "node_id": project_id,
                "parent_id": "",
                "node_type": "project",
                "label": project_key,
                "raw_item_code": "",
                "normalized_item_code": "",
                "bill_code_9": "",
                "bill_name": "",
                "item_suffix": "",
                "project_name": project_key,
                "section_name": "",
                "child_count": str(project_child_sections[project_key]),
                "candidate_quota_count": str(project_candidate_counts[project_key]),
                "risk_level": "medium" if project_candidate_counts[project_key] else "high",
                "display_order": str(display_order),
            }
        )
        display_order += 1
        for section_key, section_id in section_ids.items():
            if section_key[0] != project_key:
                continue
            tree_rows.append(
                {
                    "node_id": section_id,
                    "parent_id": project_id,
                    "node_type": "section",
                    "label": section_key[1],
                    "raw_item_code": "",
                    "normalized_item_code": "",
                    "bill_code_9": "",
                    "bill_name": "",
                    "item_suffix": "",
                    "project_name": project_key,
                    "section_name": section_key[1],
                    "child_count": str(section_child_bills[section_key]),
                    "candidate_quota_count": str(section_candidate_counts[section_key]),
                    "risk_level": "medium" if section_candidate_counts[section_key] else "high",
                    "display_order": str(display_order),
                }
            )
            display_order += 1
            for bill_key, bill_id in bill_ids.items():
                if bill_key[0] != project_key or bill_key[1] != section_key[1]:
                    continue
                tree_rows.append(
                    {
                        "node_id": bill_id,
                        "parent_id": section_id,
                        "node_type": "bill",
                        "label": f"{bill_key[2]} {bill_names[bill_key]}",
                        "raw_item_code": "",
                        "normalized_item_code": "",
                        "bill_code_9": bill_key[2] if not bill_key[2].startswith("UNMATCHED-") else "",
                        "bill_name": bill_names[bill_key],
                        "item_suffix": "",
                        "project_name": project_key,
                        "section_name": section_key[1],
                        "child_count": str(bill_child_items[bill_key]),
                        "candidate_quota_count": str(bill_candidate_counts[bill_key]),
                        "risk_level": bill_risks[bill_key],
                        "display_order": str(display_order),
                    }
                )
                display_order += 1
                for node in [n for n in item_nodes if n["parent_id"] == bill_id]:
                    node["display_order"] = str(display_order)
                    tree_rows.append(node)
                    display_order += 1

    write_csv(NORMALIZATION_AUDIT_CSV, normalization_rows, NORMALIZATION_FIELDS)
    write_csv(BID_TREE_NODES_CSV, tree_rows, BID_TREE_FIELDS)
    write_csv(BID_ITEM_ROWS_CSV, item_rows, BID_ITEM_FIELDS)
    write_csv(BID_EDGES_CSV, edge_rows, BID_EDGE_FIELDS)
    write_csv(BID_CANDIDATES_CSV, candidate_rows, BID_CANDIDATE_FIELDS)
    return {
        "tree_rows": tree_rows,
        "item_rows": item_rows,
        "edge_rows": edge_rows,
        "candidate_rows": candidate_rows,
        "metrics": {
            "row_count": row_count,
            "parse_success_count": row_count - parse_failed_count,
            "parse_failed_count": parse_failed_count,
            "matched_gb_bill_count": matched_count,
            "unmatched_gb_bill_count": row_count - matched_count,
            "bid_item_with_quota_candidates_count": candidate_item_count,
            "candidate_row_count": len(candidate_rows),
        },
    }


def create_table(cur: sqlite3.Cursor, table: str, fields: list[str]) -> None:
    columns = ", ".join(f"{field} TEXT" for field in fields)
    cur.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns})")


def replace_rows(cur: sqlite3.Cursor, table: str, fields: list[str], rows: list[dict[str, Any]]) -> None:
    create_table(cur, table, fields)
    cur.execute(f"DELETE FROM {table}")
    if rows:
        placeholders = ", ".join("?" for _ in fields)
        cur.executemany(
            f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders})",
            [[str(row.get(field, "")) for field in fields] for row in rows],
        )


def refresh_sqlite(rows: dict[str, Any]) -> None:
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        replace_rows(cur, "web_bid_tree_nodes", BID_TREE_FIELDS, rows["tree_rows"])
        replace_rows(cur, "web_bid_item_display_rows", BID_ITEM_FIELDS, rows["item_rows"])
        replace_rows(cur, "web_bid_item_to_bill_edges", BID_EDGE_FIELDS, rows["edge_rows"])
        replace_rows(cur, "web_bid_item_quota_candidate_rows", BID_CANDIDATE_FIELDS, rows["candidate_rows"])
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bid_tree_parent ON web_bid_tree_nodes(parent_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bid_tree_bill ON web_bid_tree_nodes(bill_code_9)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bid_item_id ON web_bid_item_display_rows(bid_item_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bid_item_bill ON web_bid_item_display_rows(bill_code_9)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bid_candidate_item ON web_bid_item_quota_candidate_rows(bid_item_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bid_candidate_bill ON web_bid_item_quota_candidate_rows(bill_code_9)")
        con.commit()
    finally:
        con.close()


def import_rows() -> list[dict[str, str]]:
    columns_sql = """
        SELECT
            id::text,
            batch_id::text,
            source_file_name::text,
            source_sheet_name::text,
            COALESCE(source_sheet_index::text, '') AS source_sheet_index,
            COALESCE(source_row_index::text, '') AS source_row_index,
            COALESCE(source_excel_row_no::text, '') AS source_excel_row_no,
            COALESCE(mapping_version::text, '') AS mapping_version,
            COALESCE(parse_status::text, '') AS parse_status,
            COALESCE(parse_warnings::text, '') AS parse_warnings,
            COALESCE(project_name::text, '') AS project_name,
            COALESCE(category::text, '') AS category,
            COALESCE(serial_number::text, '') AS serial_number,
            COALESCE(item_code::text, '') AS item_code,
            COALESCE(item_name::text, '') AS item_name,
            COALESCE(feature::text, '') AS feature,
            COALESCE(unit::text, '') AS unit,
            COALESCE(quantity::text, '') AS quantity,
            COALESCE(unit_price::text, '') AS unit_price,
            COALESCE(total_price::text, '') AS total_price
        FROM public.import_bid_records
        ORDER BY id
    """
    return run_psql_csv(columns_sql)


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows(import_rows())
    refresh_sqlite(rows)
    metrics = rows["metrics"]
    (RUN_DIR / "bid_view_model_metrics.txt").write_text(
        "\n".join(f"{key}={value}" for key, value in metrics.items())
        + f"\ngenerated_at={datetime.now().isoformat(timespec='seconds')}\n",
        encoding="utf-8",
    )
    for key, value_ in metrics.items():
        print(f"{key}={value_}")


if __name__ == "__main__":
    main()
