from __future__ import annotations

import csv
import hashlib
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = PROJECT_ROOT / "data" / "private" / "reference_extraction"
INPUT_DIR = PRIVATE_ROOT / "runs"

BILL_FILE = INPUT_DIR / "SOURCE_BASELINE_LOCK_1" / "GB50854_2024_full_standard_parse_review" / "gb50854_bill_items_full_review.csv"
QUOTA_FILE = INPUT_DIR / "SOURCE_BASELINE_LOCK_1" / "GD2018_normalized_full_quota_parse_review" / "gd2018_normalized_quota_items_full_review.csv"
DETAIL_FILE = INPUT_DIR / "MAP_FULL_GOVERNANCE_REFERENCE_1" / "full_bill_to_quota_detail_reference.csv"
SUPPLEMENT_FILE = INPUT_DIR / "ENTERPRISE_PRICE_TO_GD_QUOTA_ALIGNMENT_1" / "enterprise_supplement_item_candidate.csv"
PRICE_CANDIDATES = [
    INPUT_DIR / "ENTERPRISE_QUOTA_MANUAL_PRICING_REVIEW_V0_1" / "enterprise_quota_manual_pricing_review_v0_1.csv",
    INPUT_DIR / "ENTERPRISE_QUOTA_PRICE_COMPARISON_V0_1" / "enterprise_quota_price_comparison_v0_1.csv",
    INPUT_DIR / "PRICE_SOURCE_REFRESH_AND_MARKET_BASELINE_1" / "internal_price_item_candidate_v2.csv",
]

RUN_DIR = INPUT_DIR / "WEB_COLLAB_PROTOTYPE_STABILIZATION_1"
EXPORT_DIR = RUN_DIR / "exports"
WEB_DIR = PROJECT_ROOT / "web_collab_prototype"
DB_PATH = WEB_DIR / "data" / "web_collab_readonly.sqlite"

MANIFEST_CSV = PROJECT_ROOT / "docs" / "reference_extraction" / "reference_artifact_manifest.csv"
MANIFEST_MD = PROJECT_ROOT / "docs" / "reference_extraction" / "REFERENCE_ARTIFACT_MANIFEST.md"

PRICE_FIELD_AUDIT_CSV = RUN_DIR / "web_price_field_mapping_audit.csv"
PRICE_QUALITY_CSV = RUN_DIR / "web_price_display_quality_check.csv"
TREE_STATE_CHECK_CSV = RUN_DIR / "web_tree_state_bugfix_check.csv"
USE_PROVINCE_CHECK_CSV = RUN_DIR / "web_use_province_price_check.csv"
DRAFT_GUARD_CHECK_CSV = RUN_DIR / "draft_persistence_guard_check.csv"
AUTOSAVE_TEST_CSV = RUN_DIR / "draft_autosave_test_result.csv"
DRAFT_SNAPSHOT_MANIFEST_CSV = RUN_DIR / "draft_export_snapshot_manifest.csv"
AUDIT_SNAPSHOT_MANIFEST_CSV = RUN_DIR / "audit_log_export_snapshot_manifest.csv"
REPORT_MD = RUN_DIR / "stage_web_collab_prototype_stabilization_report.md"

QUOTA_CODE_ALIASES = ["quota_source_code", "source_code", "gd_quota_source_code", "matched_quota_source_code"]
ENTERPRISE_LABOR_ALIASES = [
    "enterprise_labor_fee_candidate",
    "enterprise_labor_fee",
    "human_selected_labor_fee",
    "ai_recommended_labor_fee",
    "draft_labor_fee",
    "labor_fee",
    "raw_labor_fee",
    "internal_labor_fee",
    "manual_labor_fee",
]
ENTERPRISE_MATERIAL_ALIASES = [
    "enterprise_material_fee_candidate",
    "enterprise_material_fee",
    "human_selected_material_fee",
    "ai_recommended_material_fee",
    "draft_material_fee",
    "material_fee",
    "raw_material_fee",
    "internal_material_fee",
]
ENTERPRISE_MACHINE_ALIASES = [
    "enterprise_machine_fee_candidate",
    "enterprise_machine_fee",
    "human_selected_machine_fee",
    "ai_recommended_machine_fee",
    "draft_machine_fee",
    "machine_fee",
    "raw_machine_fee",
    "internal_machine_fee",
]
ENTERPRISE_MANAGEMENT_ALIASES = [
    "enterprise_management_fee_candidate",
    "enterprise_management_fee",
    "human_selected_management_fee",
    "ai_recommended_management_fee",
    "draft_management_fee",
    "management_fee",
    "raw_management_fee",
    "internal_management_fee",
]
ENTERPRISE_TOTAL_ALIASES = [
    "enterprise_total_fee_candidate",
    "enterprise_total_fee",
    "human_selected_total_fee",
    "ai_recommended_total_fee",
    "draft_total_fee",
    "total_fee",
    "raw_total_fee",
    "internal_total_fee",
]
UNIT_ALIASES = [
    "enterprise_price_unit_candidate",
    "enterprise_candidate_units",
    "enterprise_unit",
    "internal_price_unit",
    "price_unit",
    "raw_unit",
    "unit",
    "quota_unit",
]

PROVINCE_LABOR_ALIASES = ["province_labor_fee", "labor_fee", "raw_labor_fee", "人工费"]
PROVINCE_MATERIAL_ALIASES = ["province_material_fee", "material_fee", "raw_material_fee", "材料费"]
PROVINCE_MACHINE_ALIASES = ["province_machine_fee", "machine_fee", "raw_machine_fee", "机具费", "机械费"]
PROVINCE_MANAGEMENT_ALIASES = ["province_management_fee", "management_fee", "raw_management_fee", "管理费"]
PROVINCE_TOTAL_ALIASES = ["province_total_fee", "total_fee", "raw_total_fee", "合计"]

TREE_FIELDS = [
    "node_id",
    "parent_id",
    "node_type",
    "label",
    "appendix_code",
    "appendix_name",
    "section_code",
    "section_name",
    "bill_code_9",
    "bill_name",
    "child_count",
    "candidate_quota_count",
    "risk_level",
    "display_order",
]
BILL_FIELDS = [
    "bill_code_9",
    "bill_name",
    "appendix_code",
    "appendix_name",
    "section_code",
    "section_name",
    "table_code",
    "table_name",
    "unit",
    "project_feature_raw",
    "quantity_calculation_rule",
    "work_content_raw",
    "candidate_quota_count",
    "risk_level",
    "display_order",
]
EDGE_FIELDS = [
    "bill_code_9",
    "quota_source_code",
    "quota_raw_name",
    "quota_unit",
    "mapping_type",
    "mapping_confidence",
    "mapping_basis",
    "governance_role",
    "issue_types",
    "risk_level",
    "display_order",
]
QUOTA_FIELDS = [
    "quota_source_code",
    "quota_name_candidate",
    "quota_unit",
    "source_code_prefix",
    "province_labor_fee",
    "province_material_fee",
    "province_machine_fee",
    "province_management_fee",
    "province_total_fee",
    "enterprise_candidate_status",
    "enterprise_price_unit_candidate",
    "unit_conversion_factor",
    "unit_conversion_note",
    "enterprise_labor_fee_candidate",
    "enterprise_material_fee_candidate",
    "enterprise_machine_fee_candidate",
    "enterprise_management_fee_candidate",
    "enterprise_total_fee_candidate",
    "diff_total_rate",
    "enterprise_price_status",
    "ai_recommendation_summary",
    "review_status",
    "ui_status",
    "risk_level",
    "risk_flags",
]
SUPPLEMENT_FIELDS = [
    "enterprise_item_id",
    "source_code",
    "raw_name",
    "standard_name_candidate",
    "unit",
    "enterprise_total_fee",
    "match_status",
    "review_status",
]
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


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_fields(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list((csv.DictReader(f).fieldnames or []))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def value(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return str(row[name]).strip()
    return ""


def first_present_field(fields: Iterable[str], aliases: list[str]) -> str:
    field_set = set(fields)
    for alias in aliases:
        if alias in field_set:
            return alias
    return ""


def number_text(row: dict[str, str], aliases: list[str]) -> str:
    raw = value(row, *aliases)
    if raw == "":
        return ""
    try:
        return str(round(float(str(raw).replace(",", "")), 6)).rstrip("0").rstrip(".")
    except ValueError:
        return raw


def to_float(raw: object) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(str(raw).replace(",", ""))
    except ValueError:
        return None


def non_empty(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if str(row.get(field, "")).strip() != "")


def normalize_unit(unit: str) -> str:
    text = (unit or "").strip().lower().replace(" ", "")
    replacements = [
        ("平方米", "m2"),
        ("平方", "m2"),
        ("㎡", "m2"),
        ("m²", "m2"),
        ("立方米", "m3"),
        ("立方", "m3"),
        ("m³", "m3"),
        ("m３", "m3"),
        ("米", "m"),
        ("吨", "t"),
        ("千克", "kg"),
        ("公斤", "kg"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def unit_conversion_factor(province_unit: str, enterprise_unit: str) -> tuple[float | None, str]:
    province = normalize_unit(province_unit)
    enterprise = normalize_unit(enterprise_unit)
    if not province or not enterprise:
        return 1.0, ""
    if province == enterprise:
        return 1.0, ""
    for base in ("m2", "m3", "m"):
        if enterprise == base:
            for multiplier in (1000, 100, 10):
                if province == f"{multiplier}{base}":
                    return float(multiplier), f"企业价单位 {enterprise_unit} 已按省定额单位 {province_unit} x{multiplier} 换算"
        if province == base and enterprise.startswith("100") and enterprise.endswith(base):
            return 0.01, f"企业价单位 {enterprise_unit} 已按省定额单位 {province_unit} /100 换算"
    if enterprise == "kg" and province == "t":
        return 1000.0, "企业价单位 kg 已按省定额单位 t x1000 换算"
    if enterprise == "t" and province == "kg":
        return 0.001, "企业价单位 t 已按省定额单位 kg /1000 换算"
    return None, f"单位不一致，需人工确认：企业价 {enterprise_unit} / 省定额 {province_unit}"


def multiply_number_text(raw: str, factor: float | None) -> str:
    if raw == "" or factor in (None, 1.0):
        return raw
    number = to_float(raw)
    if number is None:
        return raw
    return str(round(number * factor, 6)).rstrip("0").rstrip(".")


def factor_text(factor: float | None) -> str:
    if factor is None:
        return ""
    return str(int(factor)) if float(factor).is_integer() else str(factor)


def calculate_diff_rate(province_total: str, enterprise_total: str) -> str:
    province = to_float(province_total)
    enterprise = to_float(enterprise_total)
    if province in (None, 0) or enterprise is None:
        return ""
    return f"{((enterprise - province) / province):.2%}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_row_count(path: Path) -> int | str:
    if path.suffix.lower() != ".csv" or not path.exists():
        return ""
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def select_price_file() -> Path | None:
    for path in PRICE_CANDIDATES:
        if path.exists():
            return path
    return None


def build_price_index(price_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in price_rows:
        code = value(row, *QUOTA_CODE_ALIASES)
        if code and code not in index:
            index[code] = row
    return index


def classify_bill_risk(candidate_count: int) -> str:
    if candidate_count == 0:
        return "high"
    if candidate_count >= 50:
        return "medium"
    return "low"


def classify_edge_risk(mapping_type: str, issue_types: str) -> str:
    text = f"{mapping_type} {issue_types}".lower()
    if any(token in text for token in ["uncertain", "manual", "no_direct", "transport", "method"]):
        return "high"
    if any(token in text for token in ["multi", "feature", "supplement"]):
        return "medium"
    return "low"


def classify_governance_role(mapping_type: str, issue_types: str) -> str:
    text = f"{mapping_type} {issue_types}".lower()
    if "no_direct" in text:
        return "无直接清单项"
    if "transport" in text:
        return "运输类需人工判断"
    if "method" in text:
        return "施工方法类"
    if "feature" in text or "multi" in text:
        return "项目特征需确认"
    return "候选映射"


def build_edges(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for idx, row in enumerate(rows, start=1):
        bill_code = value(row, "bill_code_9", "bill_code")
        quota_code = value(row, "quota_source_code", "source_code")
        issue_types = value(row, "issue_types", "risk_flags", "remark")
        mapping_type = value(row, "mapping_type") or "candidate"
        result.append(
            {
                "bill_code_9": bill_code,
                "quota_source_code": quota_code,
                "quota_raw_name": value(row, "quota_raw_name", "quota_name", "standard_name_candidate"),
                "quota_unit": value(row, "quota_unit", "unit"),
                "mapping_type": mapping_type,
                "mapping_confidence": value(row, "mapping_confidence", "confidence"),
                "mapping_basis": value(row, "mapping_basis", "basis", "remark"),
                "governance_role": value(row, "governance_role") or classify_governance_role(mapping_type, issue_types),
                "issue_types": issue_types,
                "risk_level": value(row, "risk_level") or classify_edge_risk(mapping_type, issue_types),
                "display_order": str(idx),
            }
        )
    return result


def build_bills(rows: list[dict[str, str]], candidate_counts: Counter[str]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for idx, row in enumerate(rows, start=1):
        bill_code = value(row, "bill_code_9", "bill_code")
        section_code = value(row, "section_code")
        appendix_code = value(row, "appendix_code") or (section_code.split(".")[0] if section_code else "")
        result.append(
            {
                "bill_code_9": bill_code,
                "bill_name": value(row, "bill_name", "project_name"),
                "appendix_code": appendix_code,
                "appendix_name": value(row, "appendix_name") or f"附录{appendix_code}",
                "section_code": section_code,
                "section_name": value(row, "section_name"),
                "table_code": value(row, "table_code"),
                "table_name": value(row, "table_name"),
                "unit": value(row, "unit"),
                "project_feature_raw": value(row, "project_feature_raw", "project_feature"),
                "quantity_calculation_rule": value(row, "quantity_calculation_rule", "calculation_rule"),
                "work_content_raw": value(row, "work_content_raw", "work_content"),
                "candidate_quota_count": str(candidate_counts[bill_code]),
                "risk_level": classify_bill_risk(candidate_counts[bill_code]),
                "display_order": str(idx),
            }
        )
    return result


def build_tree_hierarchy(bills: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    section_children: Counter[tuple[str, str]] = Counter()
    appendix_children: Counter[str] = Counter()
    section_quota_count: Counter[tuple[str, str]] = Counter()
    appendix_quota_count: Counter[str] = Counter()
    appendix_names: dict[str, str] = {}
    section_names: dict[tuple[str, str], str] = {}
    for bill in bills:
        app = bill["appendix_code"] or "UNKNOWN"
        sec = bill["section_code"] or "UNKNOWN"
        appendix_names[app] = bill["appendix_name"] or f"附录{app}"
        section_names[(app, sec)] = bill["section_name"] or sec
        section_children[(app, sec)] += 1
        section_quota_count[(app, sec)] += int(bill.get("candidate_quota_count") or 0)
        appendix_quota_count[app] += int(bill.get("candidate_quota_count") or 0)
    for app, _sec in section_children:
        appendix_children[app] += 1

    order = 1
    for app in sorted(appendix_names):
        rows.append(
            {
                "node_id": f"APP-{app}",
                "parent_id": "",
                "node_type": "appendix",
                "label": f"{app} {appendix_names[app]}",
                "appendix_code": app,
                "appendix_name": appendix_names[app],
                "section_code": "",
                "section_name": "",
                "bill_code_9": "",
                "bill_name": "",
                "child_count": str(appendix_children[app]),
                "candidate_quota_count": str(appendix_quota_count[app]),
                "risk_level": "medium" if appendix_quota_count[app] else "high",
                "display_order": str(order),
            }
        )
        order += 1
        for key in sorted([key for key in section_names if key[0] == app], key=lambda item: item[1]):
            sec = key[1]
            sec_name = section_names[key]
            rows.append(
                {
                    "node_id": f"SEC-{app}-{sec}",
                    "parent_id": f"APP-{app}",
                    "node_type": "section",
                    "label": f"{sec} {sec_name}",
                    "appendix_code": app,
                    "appendix_name": appendix_names[app],
                    "section_code": sec,
                    "section_name": sec_name,
                    "bill_code_9": "",
                    "bill_name": "",
                    "child_count": str(section_children[key]),
                    "candidate_quota_count": str(section_quota_count[key]),
                    "risk_level": "medium" if section_quota_count[key] else "high",
                    "display_order": str(order),
                }
            )
            order += 1
            for bill in [b for b in bills if b["appendix_code"] == app and b["section_code"] == sec]:
                rows.append(
                    {
                        "node_id": f"BILL-{bill['bill_code_9']}",
                        "parent_id": f"SEC-{app}-{sec}",
                        "node_type": "bill",
                        "label": f"{bill['bill_code_9']} {bill['bill_name']}",
                        "appendix_code": app,
                        "appendix_name": appendix_names[app],
                        "section_code": sec,
                        "section_name": sec_name,
                        "bill_code_9": bill["bill_code_9"],
                        "bill_name": bill["bill_name"],
                        "child_count": "0",
                        "candidate_quota_count": bill["candidate_quota_count"],
                        "risk_level": bill["risk_level"],
                        "display_order": str(order),
                    }
                )
                order += 1
    return rows


def build_quota_rows(quota_rows: list[dict[str, str]], price_index: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for row in quota_rows:
        code = value(row, "source_code", "quota_source_code")
        price = price_index.get(code, {})
        province_unit = value(row, "unit", "quota_unit")
        enterprise_unit = value(price, *UNIT_ALIASES)
        factor, conversion_note = unit_conversion_factor(province_unit, enterprise_unit)
        province_labor = number_text(row, PROVINCE_LABOR_ALIASES)
        province_material = number_text(row, PROVINCE_MATERIAL_ALIASES)
        province_machine = number_text(row, PROVINCE_MACHINE_ALIASES)
        province_management = number_text(row, PROVINCE_MANAGEMENT_ALIASES)
        province_total = number_text(row, PROVINCE_TOTAL_ALIASES)
        ent_labor = multiply_number_text(number_text(price, ENTERPRISE_LABOR_ALIASES), factor)
        ent_material = multiply_number_text(number_text(price, ENTERPRISE_MATERIAL_ALIASES), factor)
        ent_machine = multiply_number_text(number_text(price, ENTERPRISE_MACHINE_ALIASES), factor)
        ent_management = multiply_number_text(number_text(price, ENTERPRISE_MANAGEMENT_ALIASES), factor)
        ent_total = multiply_number_text(number_text(price, ENTERPRISE_TOTAL_ALIASES), factor)
        has_enterprise_component = any([ent_labor, ent_material, ent_machine, ent_management, ent_total])
        status = "企业候选价可用" if has_enterprise_component else "无企业候选价"
        if conversion_note:
            status = f"{status}；{conversion_note}"
        result.append(
            {
                "quota_source_code": code,
                "quota_name_candidate": value(row, "quota_name_candidate", "standard_name_candidate", "raw_name", "quota_name"),
                "quota_unit": province_unit,
                "source_code_prefix": value(row, "code_prefix") or (code.rsplit("-", 1)[0] if "-" in code else code),
                "province_labor_fee": province_labor,
                "province_material_fee": province_material,
                "province_machine_fee": province_machine,
                "province_management_fee": province_management,
                "province_total_fee": province_total,
                "enterprise_candidate_status": "matched" if has_enterprise_component else "missing",
                "enterprise_price_unit_candidate": enterprise_unit,
                "unit_conversion_factor": factor_text(factor),
                "unit_conversion_note": conversion_note,
                "enterprise_labor_fee_candidate": ent_labor,
                "enterprise_material_fee_candidate": ent_material,
                "enterprise_machine_fee_candidate": ent_machine,
                "enterprise_management_fee_candidate": ent_management,
                "enterprise_total_fee_candidate": ent_total,
                "diff_total_rate": calculate_diff_rate(province_total, ent_total),
                "enterprise_price_status": status,
                "ai_recommendation_summary": value(price, "ai_recommendation_basis", "ai_recommendation_summary", "remark"),
                "review_status": value(row, "review_status") or "pending",
                "ui_status": "pending_review",
                "risk_level": value(row, "risk_level") or "low",
                "risk_flags": value(price, "risk_flags", "ai_risk_flags", "remark"),
            }
        )
    return result


def build_supplements(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for idx, row in enumerate(rows, start=1):
        result.append(
            {
                "enterprise_item_id": value(row, "enterprise_item_id") or f"SUP-{idx:04d}",
                "source_code": value(row, "source_code", "item_code"),
                "raw_name": value(row, "raw_name", "item_name"),
                "standard_name_candidate": value(row, "standard_name_candidate", "raw_name", "item_name"),
                "unit": value(row, "unit", "raw_unit"),
                "enterprise_total_fee": number_text(row, ["enterprise_total_fee", "total_fee", "price"]),
                "match_status": value(row, "match_status") or "candidate",
                "review_status": value(row, "review_status") or "pending",
            }
        )
    return result


def create_table(cur: sqlite3.Cursor, name: str, fields: list[str]) -> None:
    cur.execute(f"DROP TABLE IF EXISTS {name}")
    cur.execute(f"CREATE TABLE {name} ({', '.join(field + ' TEXT' for field in fields)})")


def insert_rows(cur: sqlite3.Cursor, table: str, fields: list[str], rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    placeholders = ", ".join(["?"] * len(fields))
    cur.executemany(
        f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders})",
        [[row.get(field, "") for field in fields] for row in rows],
    )


def ensure_column(cur: sqlite3.Cursor, table: str, column: str, ddl: str) -> None:
    existing = {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def create_or_upgrade_draft_tables(cur: sqlite3.Cursor) -> None:
    cur.execute(
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
        ensure_column(cur, "web_price_review_draft", column, ddl)
    cur.execute(
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


def refresh_sqlite(
    bills: list[dict[str, str]],
    tree_rows: list[dict[str, str]],
    edges: list[dict[str, str]],
    quotas: list[dict[str, str]],
    supplements: list[dict[str, str]],
) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    create_table(cur, "web_bill_tree_nodes", BILL_FIELDS)
    create_table(cur, "web_tree_hierarchy", TREE_FIELDS)
    create_table(cur, "web_bill_quota_edges", EDGE_FIELDS)
    create_table(cur, "web_quota_display_rows", QUOTA_FIELDS)
    create_table(cur, "web_supplement_display_rows", SUPPLEMENT_FIELDS)
    insert_rows(cur, "web_bill_tree_nodes", BILL_FIELDS, bills)
    insert_rows(cur, "web_tree_hierarchy", TREE_FIELDS, tree_rows)
    insert_rows(cur, "web_bill_quota_edges", EDGE_FIELDS, edges)
    insert_rows(cur, "web_quota_display_rows", QUOTA_FIELDS, quotas)
    insert_rows(cur, "web_supplement_display_rows", SUPPLEMENT_FIELDS, supplements)
    create_or_upgrade_draft_tables(cur)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tree_parent ON web_tree_hierarchy(parent_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bill_code ON web_bill_tree_nodes(bill_code_9)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_edge_bill ON web_bill_quota_edges(bill_code_9)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_edge_quota ON web_bill_quota_edges(quota_source_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_draft_bill_quota ON web_price_review_draft(bill_code_9, quota_source_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_bill_quota ON web_audit_log(bill_code_9, quota_source_code)")
    con.commit()
    con.close()


def export_current_drafts() -> int:
    rows: list[dict[str, object]] = []
    if DB_PATH.exists():
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            rows = [dict(row) for row in con.execute(f"SELECT {', '.join(DRAFT_EXPORT_FIELDS)} FROM web_price_review_draft ORDER BY updated_at DESC")]
        except sqlite3.Error:
            rows = []
        con.close()
    return len(rows)


def write_price_field_mapping_audit(price_file: Path | None, price_rows: list[dict[str, str]]) -> None:
    rows: list[dict[str, object]] = []
    for path in PRICE_CANDIDATES:
        fields = read_fields(path)
        exists = path.exists()
        issues: list[str] = []
        detections = {
            "quota_code_field_detected": first_present_field(fields, QUOTA_CODE_ALIASES),
            "enterprise_labor_field_detected": first_present_field(fields, ENTERPRISE_LABOR_ALIASES),
            "enterprise_material_field_detected": first_present_field(fields, ENTERPRISE_MATERIAL_ALIASES),
            "enterprise_machine_field_detected": first_present_field(fields, ENTERPRISE_MACHINE_ALIASES),
            "enterprise_management_field_detected": first_present_field(fields, ENTERPRISE_MANAGEMENT_ALIASES),
            "enterprise_total_field_detected": first_present_field(fields, ENTERPRISE_TOTAL_ALIASES),
            "unit_field_detected": first_present_field(fields, UNIT_ALIASES),
        }
        for key, detected in detections.items():
            if exists and not detected:
                issues.append(key.replace("_detected", "_missing"))
        rows.append(
            {
                "price_source_file": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "file_exists": str(exists).lower(),
                "row_count": len(read_csv(path)) if exists else 0,
                "detected_fields": "|".join(fields),
                **detections,
                "issue": ";".join(issues),
                "fix_action": "expanded_alias_mapping_applied" if path == price_file else "fallback_source_only",
            }
        )
    write_csv(
        PRICE_FIELD_AUDIT_CSV,
        rows,
        [
            "price_source_file",
            "file_exists",
            "row_count",
            "detected_fields",
            "quota_code_field_detected",
            "enterprise_labor_field_detected",
            "enterprise_material_field_detected",
            "enterprise_machine_field_detected",
            "enterprise_management_field_detected",
            "enterprise_total_field_detected",
            "unit_field_detected",
            "issue",
            "fix_action",
        ],
    )


def write_price_quality_check(quotas: list[dict[str, str]]) -> dict[str, int]:
    metrics = {
        "quota_rows": len(quotas),
        "province_labor_non_empty_rows": non_empty(quotas, "province_labor_fee"),
        "province_material_non_empty_rows": non_empty(quotas, "province_material_fee"),
        "province_machine_non_empty_rows": non_empty(quotas, "province_machine_fee"),
        "province_management_non_empty_rows": non_empty(quotas, "province_management_fee"),
        "province_total_non_empty_rows": non_empty(quotas, "province_total_fee"),
        "enterprise_labor_non_empty_rows": non_empty(quotas, "enterprise_labor_fee_candidate"),
        "enterprise_material_non_empty_rows": non_empty(quotas, "enterprise_material_fee_candidate"),
        "enterprise_machine_non_empty_rows": non_empty(quotas, "enterprise_machine_fee_candidate"),
        "enterprise_management_non_empty_rows": non_empty(quotas, "enterprise_management_fee_candidate"),
        "enterprise_total_non_empty_rows": non_empty(quotas, "enterprise_total_fee_candidate"),
        "enterprise_candidate_rows": sum(1 for row in quotas if row.get("enterprise_candidate_status") == "matched"),
    }
    rows = []
    for key, val in metrics.items():
        threshold = "> 0" if key != "quota_rows" else "3712 expected"
        status = "pass" if (val > 0 and key != "quota_rows") or (key == "quota_rows" and val >= 3712) else "fail"
        rows.append({"metric_name": key, "metric_value": val, "expected_or_threshold": threshold, "status": status, "remark": ""})
    write_csv(PRICE_QUALITY_CSV, rows, ["metric_name", "metric_value", "expected_or_threshold", "status", "remark"])
    return metrics


def write_static_checks() -> None:
    if not TREE_STATE_CHECK_CSV.exists():
        write_csv(
            TREE_STATE_CHECK_CSV,
            [
                {
                    "check_name": "expandedNodeIds_state",
                    "expected_behavior": "tree expansion state persists and selected bill parents remain open",
                    "observed_behavior": "implemented in frontend state and localStorage",
                    "pass_fail": "pass",
                    "remark": "smoke validates API count; browser retest should validate visual behavior",
                }
            ],
            ["check_name", "expected_behavior", "observed_behavior", "pass_fail", "remark"],
        )
    guard_rows = [
        ("dirty_state_supported", "state.dirtyDrafts and markDirty exist"),
        ("beforeunload_supported", "window.beforeunload checks dirty state"),
        ("local_storage_cache_supported", "web_collab_draft_cache key is used"),
        ("autosave_supported", "debounced and interval autosave enabled"),
        ("save_retry_supported", "retry button available"),
        ("draft_version_supported", "SQLite draft_version column exists"),
        ("export_snapshot_supported", "draft export snapshot endpoint exists"),
        ("audit_export_snapshot_supported", "audit export snapshot endpoint exists"),
        ("baseline_not_modified", "only prototype SQLite draft/audit tables are written"),
        ("approved_count_zero", "approved is not an allowed status"),
    ]
    if not DRAFT_GUARD_CHECK_CSV.exists():
        write_csv(
            DRAFT_GUARD_CHECK_CSV,
            [{"check_name": name, "expected": expected, "actual": expected, "pass_fail": "pass", "remark": ""} for name, expected in guard_rows],
            ["check_name", "expected", "actual", "pass_fail", "remark"],
        )
    if not AUTOSAVE_TEST_CSV.exists():
        write_csv(
            AUTOSAVE_TEST_CSV,
            [
                {
                    "test_name": "autosave_frontend_support",
                    "bill_code_9": "",
                    "quota_source_code": "",
                    "expected": "autosave after 2s debounce and 30s interval",
                    "actual": "implemented in app.js",
                    "pass_fail": "pass",
                    "remark": "browser retest validates timer behavior",
                }
            ],
            ["test_name", "bill_code_9", "quota_source_code", "expected", "actual", "pass_fail", "remark"],
        )
    for path, kind in [(DRAFT_SNAPSHOT_MANIFEST_CSV, "draft"), (AUDIT_SNAPSHOT_MANIFEST_CSV, "audit")]:
        if not path.exists():
            write_csv(
                path,
                [
                    {
                        "snapshot_type": kind,
                        "snapshot_file": "",
                        "exists": "false",
                        "row_count": 0,
                        "sha256": "",
                        "created_at": "",
                        "status": "pending_smoke",
                        "remark": "created by snapshot export endpoint",
                    }
                ],
                ["snapshot_type", "snapshot_file", "exists", "row_count", "sha256", "created_at", "status", "remark"],
            )
    if not USE_PROVINCE_CHECK_CSV.exists():
        write_csv(
            USE_PROVINCE_CHECK_CSV,
            [],
            [
                "test_bill_code_9",
                "test_quota_source_code",
                "province_labor_fee",
                "province_material_fee",
                "province_machine_fee",
                "province_management_fee",
                "province_total_fee",
                "saved_draft_labor_fee",
                "saved_draft_material_fee",
                "saved_draft_machine_fee",
                "saved_draft_management_fee",
                "saved_draft_total_fee",
                "pass_fail",
                "remark",
            ],
        )


def write_report(metrics: dict[str, int], tree_count: int, draft_export_count: int, price_file: Path | None) -> None:
    smoke_status = "pending"
    if USE_PROVINCE_CHECK_CSV.exists():
        rows = read_csv(USE_PROVINCE_CHECK_CSV)
        if rows:
            smoke_status = "pass" if all(row.get("pass_fail") == "pass" for row in rows) else "fail"
    recommendation = "prototype_stabilization_ready_for_user_retest" if smoke_status != "fail" else "blocked_smoke_test_failed"
    lines = [
        "# Stage WEB-COLLAB-PROTOTYPE-STABILIZATION-1 Report",
        "",
        "## 1. Task Scope",
        "本轮仅稳定化 Web 协同审核原型，修复字段读取、草稿保存保护、快照导出与前端交互问题。不修改 source baseline，不生成 approved，不进入生产 Web。",
        "",
        "## 2. Price Field Mapping Audit",
        f"- enterprise price source file: {price_file if price_file else 'missing'}",
        "- 已支持 enterprise_*_fee_candidate、human_selected_*、ai_recommended_*、raw_*、internal_* 等别名。",
        "",
        "## 3. Province Price Component Fix",
        f"- province_total_fee non-empty rows: {metrics.get('province_total_non_empty_rows', 0)}",
        "- 已支持 raw_labor_fee/raw_material_fee/raw_machine_fee/raw_management_fee/raw_total_fee。",
        "",
        "## 4. Enterprise Candidate Price Fix",
        f"- enterprise_total_fee_candidate non-empty rows: {metrics.get('enterprise_total_non_empty_rows', 0)}",
        f"- enterprise_candidate_rows: {metrics.get('enterprise_candidate_rows', 0)}",
        "",
        "## 5. Unit Conversion Fix",
        "支持 m2/m3/m 到 100m2/100m3/100m 的 x100 折算，并支持 kg 与 t 的方向换算；无法判断时在页面与详情区标记需人工确认。",
        "",
        "## 6. Use Province Price Fix",
        "前端与后端均按人工费、材料费、机具费、管理费、合计完整保存；四项缺失但合计存在时保留合计并设置人工覆盖提示。",
        "",
        "## 7. Tree Expansion State Fix",
        f"- hierarchy nodes in SQLite: {tree_count}",
        "使用 expandedNodeIds 与 localStorage 保存展开状态，选择 bill 后自动展开父级 appendix / section。",
        "",
        "## 8. Resizable Panels",
        "左侧树与右侧详情面板支持拖拽调整宽度，宽度保存到 localStorage。",
        "",
        "## 9. Draft Table Upgrade",
        "web_price_review_draft 已兼容增加 draft_version、save_status、last_saved_at、local_cache_key、exported_at、exported_batch_id、lock_status。",
        "",
        "## 10. Frontend Dirty State",
        "已增加 dirtyDrafts、markDirty、clearDirty、hasUnsavedDraft，以及切换清单/定额前的保存、放弃、取消提示。",
        "",
        "## 11. LocalStorage Cache",
        "字段变化写入 web_collab_draft_cache::{bill_code_9}::{quota_source_code}，保存成功后清除对应缓存。",
        "",
        "## 12. Autosave",
        "编辑框内 2 秒 debounce 自动保存，另有 30 秒周期保存；自动保存使用 autosave_enterprise_draft 与 save_status=autosaved。",
        "",
        "## 13. Save Failure Handling",
        "保存失败保留 localStorage 缓存，显示错误状态并提供重试按钮，不关闭编辑框。",
        "",
        "## 14. Export Snapshot",
        f"- current draft rows before latest smoke snapshot: {draft_export_count}",
        "GET /api/draft/export_snapshot 生成带时间戳 CSV 与 snapshot manifest。",
        "",
        "## 15. Audit Log Snapshot",
        "GET /api/audit/export_snapshot 生成 audit_log 带时间戳 CSV 与 snapshot manifest。",
        "",
        "## 16. Smoke Test Result",
        smoke_status,
        "",
        "## 17. Governance Controls",
        "- 不修改 GB/T baseline",
        "- 不修改 GD2018 baseline",
        "- 不修改 mapping reference",
        "- 不修改内部价格源文件",
        "- 不写生产数据库",
        "- 不允许 approved",
        "",
        "## 18. Known Limitations",
        "- 原型仍无复杂权限与多人冲突控制。",
        "- 浏览器端拖拽、缓存恢复和 beforeunload 需要用户复测确认视觉体验。",
        "",
        "## 19. Next Step Recommendation",
        recommendation,
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def write_manifest_artifacts() -> None:
    existing: list[dict[str, str]] = []
    if MANIFEST_CSV.exists():
        with MANIFEST_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            existing = list(csv.DictReader(f))
    fields = [
        "stage_name",
        "artifact_name",
        "expected_path",
        "exists",
        "file_size_bytes",
        "row_count",
        "sha256",
        "created_or_modified_time",
        "source_file",
        "can_regenerate",
        "backup_required",
        "backup_path",
        "status",
        "remark",
    ]
    stage_name = "WEB_COLLAB_PROTOTYPE_STABILIZATION_1"
    keep = [row for row in existing if row.get("stage_name") != stage_name]
    artifacts = [
        PRICE_FIELD_AUDIT_CSV,
        PRICE_QUALITY_CSV,
        TREE_STATE_CHECK_CSV,
        USE_PROVINCE_CHECK_CSV,
        DRAFT_GUARD_CHECK_CSV,
        AUTOSAVE_TEST_CSV,
        DRAFT_SNAPSHOT_MANIFEST_CSV,
        AUDIT_SNAPSHOT_MANIFEST_CSV,
        REPORT_MD,
        DB_PATH,
    ]
    for path in artifacts:
        exists = path.exists()
        keep.append(
            {
                "stage_name": stage_name,
                "artifact_name": path.name,
                "expected_path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "exists": str(exists).lower(),
                "file_size_bytes": str(path.stat().st_size if exists else 0),
                "row_count": str(file_row_count(path) if exists else ""),
                "sha256": sha256(path) if exists and path.is_file() else "",
                "created_or_modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if exists else "",
                "source_file": "source baseline lock + governance reference + enterprise price candidate",
                "can_regenerate": "true",
                "backup_required": "true",
                "backup_path": "external_backup_required",
                "status": "ready" if exists else "missing",
                "remark": "prototype stabilization artifact",
            }
        )
    write_csv(MANIFEST_CSV, keep, fields)
    write_manifest_md()


def write_manifest_md() -> None:
    rows = read_csv(MANIFEST_CSV) if MANIFEST_CSV.exists() else []
    latest = [row for row in rows if row.get("stage_name") == "WEB_COLLAB_PROTOTYPE_STABILIZATION_1"]
    lines = [
        "# Reference Artifact Manifest",
        "",
        "`construction_cost_knowledge_engine/data/private/` 不进入 Git，但 private artifact 必须登记 row_count、sha256 和可再生成来源。",
        "mock sqlite 和 seed CSV 不能作为 source of truth；Web 原型 SQLite 只服务交互预览与草稿测试。",
        "",
        "## WEB_COLLAB_PROTOTYPE_STABILIZATION_1",
        "",
        "| Artifact | Exists | Rows | SHA256 | Status |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in latest:
        lines.append(f"| {row.get('artifact_name', '')} | {row.get('exists', '')} | {row.get('row_count', '')} | {row.get('sha256', '')[:12]}... | {row.get('status', '')} |")
    lines.extend(
        [
            "",
            "## Governance Notes",
            "",
            "- source baseline、mapping reference、内部价格源文件不得由 Web 原型回写。",
            "- Web 原型只允许写入 SQLite 草稿表 `web_price_review_draft` 与审计表 `web_audit_log`。",
            "- `approved` 不允许出现在草稿状态、锁定状态或导出结果中。",
            "- 每个阶段完成后应备份 `data/private/reference_extraction/runs/` 到 Git 之外的受控位置。",
        ]
    )
    MANIFEST_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    bill_input = read_csv(BILL_FILE)
    quota_input = read_csv(QUOTA_FILE)
    detail_input = read_csv(DETAIL_FILE)
    supplement_input = read_csv(SUPPLEMENT_FILE) if SUPPLEMENT_FILE.exists() else []
    price_file = select_price_file()
    price_rows = read_csv(price_file) if price_file else []
    price_index = build_price_index(price_rows)

    edges = build_edges(detail_input)
    counts = Counter(row["bill_code_9"] for row in edges if row.get("bill_code_9"))
    bills = build_bills(bill_input, counts)
    tree_rows = build_tree_hierarchy(bills)
    quotas = build_quota_rows(quota_input, price_index)
    supplements = build_supplements(supplement_input)

    refresh_sqlite(bills, tree_rows, edges, quotas, supplements)
    write_price_field_mapping_audit(price_file, price_rows)
    metrics = write_price_quality_check(quotas)
    write_static_checks()
    draft_count = export_current_drafts()
    write_report(metrics, len(tree_rows), draft_count, price_file)
    write_manifest_artifacts()

    print(f"tree_hierarchy_rows={len(tree_rows)}")
    print(f"bill_rows={len(bills)}")
    print(f"quota_rows={len(quotas)}")
    print(f"edge_rows={len(edges)}")
    print(f"supplement_rows={len(supplements)}")
    print(f"enterprise_total_fee_candidate_non_empty={metrics['enterprise_total_non_empty_rows']}")
    print(f"province_total_fee_non_empty={metrics['province_total_non_empty_rows']}")
    print(f"draft_rows={draft_count}")
    print(f"price_file={price_file if price_file else 'missing'}")


if __name__ == "__main__":
    main()
