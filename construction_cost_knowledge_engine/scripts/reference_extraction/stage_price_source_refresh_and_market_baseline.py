from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
SOURCE_REL = (
    ENGINE_REL
    / "data"
    / "private"
    / "reference_extraction"
    / "source_excels"
    / "内部价格表.xls"
)
MARKET_SOURCE_DIR_REL = (
    ENGINE_REL
    / "data"
    / "private"
    / "reference_extraction"
    / "source_excels"
    / "market_price_sources"
)
RUNS_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs"
OUTPUT_DIR_REL = RUNS_REL / "PRICE_SOURCE_REFRESH_AND_MARKET_BASELINE_1"
DOCS_REF_REL = ENGINE_REL / "docs" / "reference_extraction"

NODE_EXE_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
)
NODE_MODULES_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
)

STAGE_NAME = "PRICE_SOURCE_REFRESH_AND_MARKET_BASELINE_1"
REVIEW_STATUS = "pending"

SOURCE_PROFILE_FIELDS = [
    "source_file",
    "source_file_hash",
    "file_size_bytes",
    "sheet_count",
    "sheet_name",
    "visible",
    "row_count",
    "column_count",
    "detected_header_row",
    "detected_columns",
    "formula_cell_count",
    "parse_status",
    "remark",
]

INTERNAL_CANDIDATE_FIELDS = [
    "internal_price_id",
    "source_file",
    "source_file_hash",
    "source_sheet",
    "source_excel_row",
    "category",
    "subcategory",
    "raw_name",
    "name_candidate",
    "feature_text_candidate",
    "raw_unit",
    "unit_normalized",
    "unit_dimension",
    "unit_parse_status",
    "conversion_target_unit",
    "quantity_factor_from_raw_to_target",
    "price_factor_from_raw_to_target",
    "conversion_direction",
    "conversion_rule_status",
    "labor_fee",
    "material_fee",
    "machine_fee",
    "management_fee",
    "total_fee",
    "labor_fee_target_unit",
    "material_fee_target_unit",
    "machine_fee_target_unit",
    "management_fee_target_unit",
    "total_fee_target_unit",
    "price_structure_status",
    "price_source_type",
    "price_source_name",
    "effective_date",
    "confidence_level",
    "review_status",
    "reviewer",
    "remark",
]

UNIT_FIELDS = [
    "raw_unit",
    "unit_normalized",
    "unit_dimension",
    "parse_status",
    "conversion_target_unit",
    "quantity_factor_from_raw_to_target",
    "price_factor_from_raw_to_target",
    "conversion_direction",
    "conversion_rule_status",
    "row_count",
    "candidate_count",
    "sample_source_rows",
    "sample_names",
    "review_status",
    "remark",
]

DASHBOARD_FIELDS = [
    "metric_name",
    "metric_value",
    "expected_or_threshold",
    "status",
    "severity",
    "remark",
]

MARKET_SOURCE_FIELDS = [
    "source_id",
    "source_name",
    "source_region",
    "source_period",
    "source_date",
    "tax_status",
    "source_file_or_url",
    "fetched_or_loaded_at",
    "source_trust_level",
    "access_status",
    "parse_status",
    "remark",
]

MARKET_RAW_FIELDS = [
    "market_raw_id",
    "source_id",
    "source_name",
    "source_region",
    "source_period",
    "source_date",
    "raw_item_name",
    "raw_spec_model",
    "raw_unit",
    "raw_labor_fee",
    "raw_material_fee",
    "raw_machine_fee",
    "raw_management_fee",
    "raw_total_fee",
    "tax_status",
    "source_file_or_url",
    "fetched_or_loaded_at",
    "raw_row_ref",
    "review_status",
    "remark",
]

MARKET_NORMALIZED_FIELDS = [
    "market_price_id",
    "source_name",
    "source_region",
    "source_period",
    "source_date",
    "item_name",
    "spec_model",
    "unit",
    "labor_fee",
    "material_fee",
    "machine_fee",
    "management_fee",
    "total_fee",
    "tax_status",
    "confidence_level",
    "source_file_or_url",
    "remark",
]

MARKET_ISSUE_FIELDS = [
    "issue_id",
    "issue_type",
    "severity",
    "source_id",
    "source_name",
    "source_file_or_url",
    "description",
    "recommended_action",
    "review_status",
]

SUMMARY_FIELDS = ["metric_name", "metric_value", "remark"]

MANIFEST_FIELDS = [
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

OUTPUT_ARTIFACTS = [
    "internal_price_source_profile_v2.csv",
    "internal_price_item_candidate_v2.csv",
    "internal_price_unit_normalized_v2.csv",
    "internal_price_quality_dashboard_v2.csv",
    "market_price_source_catalog.csv",
    "market_price_raw_items.csv",
    "market_price_normalized_items.csv",
    "market_price_parse_issues.csv",
    "Price_Source_Refresh_And_Market_Baseline_Review.xlsx",
    "stage_price_source_refresh_and_market_baseline_report.md",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh enterprise internal price source V2 and build market price source baseline."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    parser.add_argument("--node-exe", type=Path, default=NODE_EXE_DEFAULT)
    parser.add_argument("--node-modules", type=Path, default=NODE_MODULES_DEFAULT)
    return parser.parse_args()


def norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\ufeff", "").strip()


def compact(value: Any) -> str:
    return re.sub(r"\s+", "", norm(value))


def rel(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def csv_row_count(path: Path) -> str:
    if path.suffix.lower() != ".csv" or not path.exists():
        return ""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return str(sum(1 for _ in csv.DictReader(fh)))


def sha256_normal(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_shared_read(path: Path) -> str:
    ps = r'''
param([string]$Path)
$ErrorActionPreference = "Stop"
$fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
try {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $hash = $sha.ComputeHash($fs)
  ([BitConverter]::ToString($hash)).Replace("-", "").ToLowerInvariant()
} finally {
  $fs.Dispose()
}
'''
    with tempfile.TemporaryDirectory(prefix="price_source_hash_") as tmp:
        script = Path(tmp) / "hash_shared.ps1"
        script.write_text(ps, encoding="utf-8")
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(path)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    return proc.stdout.strip()


def sha256_file(path: Path) -> str:
    try:
        return sha256_normal(path)
    except OSError:
        return sha256_shared_read(path)


def parse_decimal(value: Any) -> Optional[Decimal]:
    text = norm(value)
    if not text or text in {"-", "--", "/", "—"}:
        return None
    cleaned = (
        text.replace(",", "")
        .replace("￥", "")
        .replace("元", "")
        .replace("¥", "")
        .replace(" ", "")
    )
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def format_decimal(value: Optional[Decimal]) -> str:
    if value is None:
        return ""
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def has_non_numeric_price_text(*values: str) -> bool:
    for value in values:
        text = norm(value)
        if not text or text in {"-", "--", "/", "—"}:
            continue
        if parse_decimal(text) is None:
            return True
    return False


def extract_xls_with_excel_com(path: Path) -> List[Dict[str, Any]]:
    ps = r'''
param([string]$InputPath, [string]$OutputPath)
$ErrorActionPreference = "Stop"
$excel = $null
$wb = $null
try {
  $excel = New-Object -ComObject Excel.Application
  $excel.Visible = $false
  $excel.DisplayAlerts = $false
  $wb = $excel.Workbooks.Open($InputPath, 0, $true)
  $sheets = @()
  foreach ($ws in $wb.Worksheets) {
    $used = $ws.UsedRange
    $rowCount = [int]$used.Rows.Count
    $colCount = [int]$used.Columns.Count
    $startRow = [int]$used.Row
    $startCol = [int]$used.Column
    $formulaCount = 0
    $rows = @()
    for ($r = 1; $r -le $rowCount; $r++) {
      $cells = @()
      for ($c = 1; $c -le $colCount; $c++) {
        $cell = $used.Cells.Item($r, $c)
        $text = [string]$cell.Text
        $value = $cell.Value2
        $formula = [string]$cell.Formula
        $hasFormula = $formula -like "=*"
        if ($hasFormula) { $formulaCount += 1 }
        $cells += [PSCustomObject]@{
          text = $text
          value = $(if ($null -eq $value) { "" } else { [string]$value })
          has_formula = $hasFormula
        }
      }
      $rows += ,@($cells)
    }
    $sheets += [PSCustomObject]@{
      name = [string]$ws.Name
      visible = [bool]($ws.Visible -eq -1)
      row_count = $rowCount
      column_count = $colCount
      start_row = $startRow
      start_col = $startCol
      formula_cell_count = $formulaCount
      rows = $rows
    }
  }
  $json = $sheets | ConvertTo-Json -Depth 20 -Compress
  [System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.UTF8Encoding]::new($false))
  $wb.Close($false)
} finally {
  if ($wb -ne $null) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb) }
  if ($excel -ne $null) {
    $excel.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
  }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}
'''
    with tempfile.TemporaryDirectory(prefix="price_source_xls_") as tmp:
        tmp_path = Path(tmp)
        script = tmp_path / "extract_xls.ps1"
        out_json = tmp_path / "workbook.json"
        script.write_text(ps, encoding="utf-8")
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(path), str(out_json)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout).strip())
        data = json.loads(out_json.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else [data]


def detect_header(sheet: Dict[str, Any]) -> Tuple[int, Dict[int, Dict[str, str]]]:
    header_terms = ["分类", "名称", "人", "材", "机", "单位", "备注", "综合", "合价"]
    best_idx = 0
    best_score = -1
    for idx, row in enumerate(sheet.get("rows", [])[:20]):
        texts = [compact(cell.get("text")) for cell in row]
        score = sum(1 for text in texts for term in header_terms if text == term or term in text)
        if score > best_score:
            best_score = score
            best_idx = idx
    header_cells = sheet["rows"][best_idx] if sheet.get("rows") else []
    category_seen = 0
    detected: Dict[int, Dict[str, str]] = {}
    for idx, cell in enumerate(header_cells, start=1):
        header = norm(cell.get("text")) or f"column_{idx}"
        key = compact(header).lower()
        role = f"extra_{idx}"
        if "分类" in key:
            category_seen += 1
            role = "raw_category" if category_seen == 1 else "raw_subcategory"
        elif "名称" in key or "项目" in key or "子目" in key:
            role = "raw_name"
        elif key in {"人", "人工", "人工费"} or "人工" in key:
            role = "raw_labor_fee"
        elif key in {"材", "材料", "材料费"} or "材料" in key:
            role = "raw_material_fee"
        elif key in {"机", "机械", "机械费"} or "机械" in key:
            role = "raw_machine_fee"
        elif "综合" in key or "合价" in key or "总价" in key:
            role = "raw_total_fee"
        elif "单位" in key:
            role = "raw_unit"
        elif "备注" in key or "说明" in key:
            role = "raw_remark"
        detected[idx] = {"header": header, "role": role}
    return int(sheet.get("start_row", 1)) + best_idx, detected


def get_role_value(cells: Sequence[Dict[str, Any]], detected: Dict[int, Dict[str, str]], role: str) -> str:
    for idx, meta in detected.items():
        if meta["role"] == role and idx <= len(cells):
            return norm(cells[idx - 1].get("text"))
    return ""


def normalize_unit_text(raw_unit: str) -> str:
    value = compact(raw_unit).lower()
    replacements = {
        "m³": "m3",
        "m^3": "m3",
        "㎥": "m3",
        "立方米": "m3",
        "m²": "m2",
        "m^2": "m2",
        "㎡": "m2",
        "平方米": "m2",
        "米": "m",
        "吨": "t",
        "千克": "kg",
        "公斤": "kg",
    }
    for src, dst in replacements.items():
        value = value.replace(src, dst)
    return value


def unit_conversion(raw_unit: str) -> Dict[str, str]:
    value = normalize_unit_text(raw_unit)
    if not value:
        return {
            "unit_normalized": "unparsed",
            "unit_dimension": "unknown",
            "parse_status": "missing",
            "conversion_target_unit": "",
            "quantity_factor_from_raw_to_target": "",
            "price_factor_from_raw_to_target": "",
            "conversion_direction": "",
            "conversion_rule_status": "missing_unit",
        }
    rules = {
        "m2": ("m2", "area", "parsed", "100m2", "0.01", "100", "m2_to_100m2_price_multiply_100"),
        "100m2": ("100m2", "area", "parsed", "100m2", "1", "1", "already_100m2"),
        "m3": ("m3", "volume", "parsed", "100m3", "0.01", "100", "m3_to_100m3_price_multiply_100"),
        "100m3": ("100m3", "volume", "parsed", "100m3", "1", "1", "already_100m3"),
        "m": ("m", "length", "parsed", "100m", "0.01", "100", "m_to_100m_price_multiply_100"),
        "100m": ("100m", "length", "parsed", "100m", "1", "1", "already_100m"),
        "kg": ("kg", "weight", "parsed", "t", "0.001", "1000", "kg_to_t_price_multiply_1000_quantity_multiply_0.001"),
        "t": ("t", "weight", "parsed", "t", "1", "1", "already_t"),
        "台班": ("台班", "machine_shift", "parsed", "台班", "1", "1", "already_same_unit"),
        "工日": ("工日", "labor_day", "parsed", "工日", "1", "1", "already_same_unit"),
        "项": ("项", "item", "parsed", "项", "1", "1", "already_same_unit"),
    }
    if value in rules:
        unit, dimension, status, target, quantity_factor, price_factor, direction = rules[value]
        return {
            "unit_normalized": unit,
            "unit_dimension": dimension,
            "parse_status": status,
            "conversion_target_unit": target,
            "quantity_factor_from_raw_to_target": quantity_factor,
            "price_factor_from_raw_to_target": price_factor,
            "conversion_direction": direction,
            "conversion_rule_status": "supported",
        }
    return {
        "unit_normalized": "unparsed",
        "unit_dimension": "unknown",
        "parse_status": "unparsed",
        "conversion_target_unit": "",
        "quantity_factor_from_raw_to_target": "",
        "price_factor_from_raw_to_target": "",
        "conversion_direction": "",
        "conversion_rule_status": "manual_rule_required",
    }


def classify_row(row: Dict[str, str], header_row: int, excel_row: int, any_price: bool) -> Tuple[str, List[str]]:
    issues: List[str] = []
    values = [
        row.get(field, "")
        for field in [
            "raw_category",
            "raw_subcategory",
            "raw_name",
            "raw_unit",
            "raw_labor_fee",
            "raw_material_fee",
            "raw_machine_fee",
            "raw_total_fee",
            "raw_remark",
        ]
    ]
    if not any(norm(value) for value in values):
        return "empty", []
    if excel_row == header_row:
        return "category_header", ["header_row"]
    name = norm(row.get("raw_name"))
    category = norm(row.get("raw_category"))
    if re.search(r"小计|合计|subtotal|total", name + category, flags=re.IGNORECASE):
        return "subtotal", ["subtotal_or_header_row"]
    if name and any_price:
        return "price_item", issues
    if category and not name and not any_price:
        return "category_header", ["category_header_row"]
    if not name and norm(row.get("raw_remark")) and not any_price:
        return "note", ["possible_non_price_row"]
    return "unknown", ["possible_non_price_row"]


def confidence_for(name: str, unit_status: str, any_price: bool, ambiguous: bool) -> str:
    if not name or not any_price or ambiguous:
        return "low"
    if unit_status == "parsed":
        return "high"
    return "medium"


def derive_feature_text(name: str, remark: str) -> str:
    parts: List[str] = []
    text = f"{name} {remark}"
    patterns = [
        r"C\d+",
        r"\d+(?:\.\d+)?mm",
        r"\d+(?:\.\d+)?m\b",
        r"\d+%",
        r"厚\d+",
        r"深度[:：]?[^\s；;，,]+",
        r"含[^；;，,]+",
        r"根据[^；;，,]+",
        r"专票",
        r"外运",
        r"消纳费",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if match and match not in parts:
                parts.append(match)
    if remark and remark not in parts:
        parts.append(remark)
    return ";".join(parts[:8])


def build_internal_rows(
    source_file: str,
    source_hash: str,
    file_size: int,
    sheets: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    profile: List[Dict[str, Any]] = []
    raw_rows: List[Dict[str, Any]] = []
    row_seq = 1
    for sheet in sheets:
        header_row, detected = detect_header(sheet)
        detected_columns = [
            {"column_index": idx, "header": meta["header"], "role": meta["role"]}
            for idx, meta in detected.items()
        ]
        profile.append(
            {
                "source_file": source_file,
                "source_file_hash": source_hash,
                "file_size_bytes": file_size,
                "sheet_count": len(sheets),
                "sheet_name": sheet["name"],
                "visible": str(bool(sheet.get("visible", True))).lower(),
                "row_count": sheet.get("row_count", 0),
                "column_count": sheet.get("column_count", 0),
                "detected_header_row": header_row,
                "detected_columns": json.dumps(detected_columns, ensure_ascii=False, separators=(",", ":")),
                "formula_cell_count": sheet.get("formula_cell_count", 0),
                "parse_status": "ok",
                "remark": "Parsed from updated .xls via read-only Excel COM because bundled Python lacks xlrd.",
            }
        )
        for idx, cells in enumerate(sheet.get("rows", []), start=int(sheet.get("start_row", 1))):
            row = {
                "source_row_id": f"IPRAW2-{row_seq:06d}",
                "source_file": source_file,
                "source_file_hash": source_hash,
                "source_sheet": sheet["name"],
                "source_excel_row": idx,
                "raw_category": get_role_value(cells, detected, "raw_category"),
                "raw_subcategory": get_role_value(cells, detected, "raw_subcategory"),
                "raw_name": get_role_value(cells, detected, "raw_name"),
                "raw_unit": get_role_value(cells, detected, "raw_unit"),
                "raw_labor_fee": get_role_value(cells, detected, "raw_labor_fee"),
                "raw_material_fee": get_role_value(cells, detected, "raw_material_fee"),
                "raw_machine_fee": get_role_value(cells, detected, "raw_machine_fee"),
                "raw_total_fee": get_role_value(cells, detected, "raw_total_fee"),
                "raw_remark": get_role_value(cells, detected, "raw_remark"),
                "row_type": "",
                "parse_issue": "",
            }
            prices = [
                parse_decimal(row[field])
                for field in ["raw_labor_fee", "raw_material_fee", "raw_machine_fee", "raw_total_fee"]
            ]
            row_type, issues = classify_row(row, header_row, idx, any(price is not None for price in prices))
            if row_type == "price_item" and not row["raw_unit"]:
                issues.append("missing_unit")
            if row_type == "price_item" and all(price is None for price in prices):
                issues.append("missing_all_price_fields")
            if row_type == "price_item" and has_non_numeric_price_text(
                row["raw_labor_fee"],
                row["raw_material_fee"],
                row["raw_machine_fee"],
                row["raw_total_fee"],
            ):
                issues.append("ambiguous_price_fields")
            row["row_type"] = row_type
            row["parse_issue"] = ";".join(dict.fromkeys(issues))
            raw_rows.append(row)
            row_seq += 1
    return profile, raw_rows


def duplicate_keys_for(raw_rows: Sequence[Dict[str, Any]]) -> set[Tuple[str, str]]:
    counter: Counter[Tuple[str, str]] = Counter()
    for row in raw_rows:
        if row["row_type"] != "price_item":
            continue
        conv = unit_conversion(row["raw_unit"])
        unit_key = conv["unit_normalized"] if conv["parse_status"] == "parsed" else compact(row["raw_unit"])
        key = (compact(row["raw_name"]), unit_key)
        if key[0]:
            counter[key] += 1
    return {key for key, count in counter.items() if count > 1}


def multiply_price(value: Optional[Decimal], price_factor: str) -> str:
    if value is None:
        return ""
    factor = parse_decimal(price_factor)
    if factor is None:
        return ""
    return format_decimal(value * factor)


def build_candidates(raw_rows: Sequence[Dict[str, Any]], duplicate_keys: set[Tuple[str, str]]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for row in raw_rows:
        if row["row_type"] != "price_item":
            continue
        labor = parse_decimal(row["raw_labor_fee"])
        material = parse_decimal(row["raw_material_fee"])
        machine = parse_decimal(row["raw_machine_fee"])
        raw_total = parse_decimal(row["raw_total_fee"])
        component_sum = sum((value or Decimal("0")) for value in [labor, material, machine])
        total = raw_total if raw_total is not None else (
            component_sum if any(value is not None for value in [labor, material, machine]) else None
        )
        any_price = any(value is not None for value in [labor, material, machine, raw_total])
        ambiguous = has_non_numeric_price_text(
            row["raw_labor_fee"], row["raw_material_fee"], row["raw_machine_fee"], row["raw_total_fee"]
        )
        conv = unit_conversion(row["raw_unit"])
        price_factor = conv["price_factor_from_raw_to_target"]
        if raw_total is not None:
            price_structure = "raw_total_present"
        elif any_price:
            price_structure = "component_sum_derived_total"
        else:
            price_structure = "missing_all_price_fields"
        key = (
            compact(row["raw_name"]),
            conv["unit_normalized"] if conv["parse_status"] == "parsed" else compact(row["raw_unit"]),
        )
        remarks = [issue for issue in row["parse_issue"].split(";") if issue]
        if key in duplicate_keys:
            remarks.append("duplicate_name_unit")
        if not row["raw_remark"]:
            remarks.append("effective_date_missing")
        candidates.append(
            {
                "internal_price_id": f"IP2-{len(candidates) + 1:06d}",
                "source_file": row["source_file"],
                "source_file_hash": row["source_file_hash"],
                "source_sheet": row["source_sheet"],
                "source_excel_row": row["source_excel_row"],
                "category": row["raw_category"],
                "subcategory": row["raw_subcategory"],
                "raw_name": row["raw_name"],
                "name_candidate": row["raw_name"],
                "feature_text_candidate": derive_feature_text(row["raw_name"], row["raw_remark"]),
                "raw_unit": row["raw_unit"],
                "unit_normalized": conv["unit_normalized"],
                "unit_dimension": conv["unit_dimension"],
                "unit_parse_status": conv["parse_status"],
                "conversion_target_unit": conv["conversion_target_unit"],
                "quantity_factor_from_raw_to_target": conv["quantity_factor_from_raw_to_target"],
                "price_factor_from_raw_to_target": conv["price_factor_from_raw_to_target"],
                "conversion_direction": conv["conversion_direction"],
                "conversion_rule_status": conv["conversion_rule_status"],
                "labor_fee": format_decimal(labor),
                "material_fee": format_decimal(material),
                "machine_fee": format_decimal(machine),
                "management_fee": "",
                "total_fee": format_decimal(total),
                "labor_fee_target_unit": multiply_price(labor, price_factor),
                "material_fee_target_unit": multiply_price(material, price_factor),
                "machine_fee_target_unit": multiply_price(machine, price_factor),
                "management_fee_target_unit": "",
                "total_fee_target_unit": multiply_price(total, price_factor),
                "price_structure_status": price_structure,
                "price_source_type": "enterprise_internal_price_table",
                "price_source_name": "内部价格表.xls",
                "effective_date": "",
                "confidence_level": confidence_for(row["raw_name"], conv["parse_status"], any_price, ambiguous),
                "review_status": REVIEW_STATUS,
                "reviewer": "",
                "remark": ";".join(dict.fromkeys(remarks)),
            }
        )
    return candidates


def build_unit_rows(raw_rows: Sequence[Dict[str, Any]], candidates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cand_by_unit: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        cand_by_unit[row["raw_unit"]].append(row)
    rows: List[Dict[str, Any]] = []
    for raw_unit in sorted(cand_by_unit.keys(), key=lambda value: (unit_conversion(value)["unit_normalized"], value)):
        conv = unit_conversion(raw_unit)
        cand_rows = cand_by_unit.get(raw_unit, [])
        rows.append(
            {
                "raw_unit": raw_unit,
                "unit_normalized": conv["unit_normalized"],
                "unit_dimension": conv["unit_dimension"],
                "parse_status": conv["parse_status"],
                "conversion_target_unit": conv["conversion_target_unit"],
                "quantity_factor_from_raw_to_target": conv["quantity_factor_from_raw_to_target"],
                "price_factor_from_raw_to_target": conv["price_factor_from_raw_to_target"],
                "conversion_direction": conv["conversion_direction"],
                "conversion_rule_status": conv["conversion_rule_status"],
                "row_count": len(cand_rows),
                "candidate_count": len(cand_rows),
                "sample_source_rows": ";".join(str(row["source_excel_row"]) for row in cand_rows[:8]),
                "sample_names": ";".join(row.get("raw_name", "") for row in cand_rows[:5] if row.get("raw_name")),
                "review_status": REVIEW_STATUS,
                "remark": "" if conv["parse_status"] == "parsed" else "unit requires manual normalization",
            }
        )
    return rows


def metric_row(
    name: str,
    value: Any,
    expected: str,
    status: str,
    severity: str,
    remark: str,
) -> Dict[str, Any]:
    return {
        "metric_name": name,
        "metric_value": value,
        "expected_or_threshold": expected,
        "status": status,
        "severity": severity,
        "remark": remark,
    }


def build_internal_dashboard(raw_rows: Sequence[Dict[str, Any]], candidates: Sequence[Dict[str, Any]], unit_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidate_count = len(candidates)
    missing_unit = sum(1 for row in candidates if not norm(row.get("raw_unit")))
    unit_parsed = sum(1 for row in candidates if row.get("unit_parse_status") == "parsed")
    unit_unparsed = sum(1 for row in candidates if row.get("unit_parse_status") in {"missing", "unparsed"})
    rows_with_any_price = sum(
        1
        for row in candidates
        if any(norm(row.get(field)) for field in ["labor_fee", "material_fee", "machine_fee", "total_fee"])
    )
    high = sum(1 for row in candidates if row.get("confidence_level") == "high")
    medium = sum(1 for row in candidates if row.get("confidence_level") == "medium")
    low = sum(1 for row in candidates if row.get("confidence_level") == "low")
    duplicate_name_unit = sum(1 for row in candidates if "duplicate_name_unit" in row.get("remark", ""))
    supported_conversion = sum(1 for row in candidates if row.get("conversion_rule_status") == "supported")
    approved = sum(1 for row in candidates if row.get("review_status") == "approved")
    non_pending = sum(1 for row in candidates if row.get("review_status") != REVIEW_STATUS)
    return [
        metric_row("total_rows", len(raw_rows), "source used range rows", "info", "low", "All rows read from source workbook used ranges, including header/non-price rows."),
        metric_row("price_item_candidate_rows", candidate_count, ">0", "pass" if candidate_count else "fail", "critical", "Rows classified as price item candidates."),
        metric_row("missing_unit_count", missing_unit, "0 preferred", "pass" if missing_unit == 0 else "warn", "medium", "Candidate rows with blank source unit."),
        metric_row("unit_parsed_count", unit_parsed, "informational", "info", "medium", "Candidate rows with parsed unit."),
        metric_row("unit_unparsed_count", unit_unparsed, "0 preferred", "pass" if unit_unparsed == 0 else "warn", "medium", "Candidate rows with missing or unparsed unit."),
        metric_row("rows_with_any_price", rows_with_any_price, str(candidate_count), "pass" if rows_with_any_price == candidate_count else "warn", "high", "Candidate rows with at least one price field."),
        metric_row("high_confidence_price_rows", high, "informational", "info", "low", "Name, price, and unit parsed."),
        metric_row("medium_confidence_price_rows", medium, "informational", "info", "low", "Candidate usable but unit missing/unparsed."),
        metric_row("low_confidence_price_rows", low, "0 preferred", "pass" if low == 0 else "warn", "medium", "Rows with weak parse quality."),
        metric_row("duplicate_name_unit_count", duplicate_name_unit, "0 preferred", "pass" if duplicate_name_unit == 0 else "warn", "medium", "Candidate duplicate name+unit rows."),
        metric_row("unit_conversion_rule_rows", len(unit_rows), "informational", "info", "low", "Unique raw units with conversion governance."),
        metric_row("supported_conversion_candidate_rows", supported_conversion, "informational", "info", "low", "Candidate rows covered by conversion rules, including m2/m3/m/kg/t."),
        metric_row("approved_count", approved, "0", "pass" if approved == 0 else "fail", "critical", "No approved rows generated."),
        metric_row("non_pending_review_status_count", non_pending, "0", "pass" if non_pending == 0 else "fail", "critical", "All candidate rows remain pending."),
        metric_row("database_write_detected", 0, "0", "pass", "critical", "This stage writes files only."),
    ]


def market_source_catalog(project_root: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    loaded_at = datetime.now().isoformat(timespec="seconds")
    candidate_sources = [
        ("MKT-SRC-001", "广东省工程造价信息化平台", "广东省", "L2", "manual_download_required"),
        ("MKT-SRC-002", "佛山市工程造价信息价", "佛山市", "L2", "manual_download_required"),
        ("MKT-SRC-003", "广州市材料价平台", "广州市", "L2", "manual_download_required"),
    ]
    rows: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    for source_id, name, region, trust, status in candidate_sources:
        rows.append(
            {
                "source_id": source_id,
                "source_name": name,
                "source_region": region,
                "source_period": "",
                "source_date": "",
                "tax_status": "pending",
                "source_file_or_url": "",
                "fetched_or_loaded_at": loaded_at,
                "source_trust_level": trust,
                "access_status": "not_loaded_no_web_in_this_stage",
                "parse_status": "not_parsed",
                "remark": "candidate source only; no web fetch; user must provide downloadable evidence file",
            }
        )
        issues.append(
            {
                "issue_id": f"MKT_ISSUE_{len(issues) + 1:06d}",
                "issue_type": "market_source_manual_file_required",
                "severity": "high",
                "source_id": source_id,
                "source_name": name,
                "source_file_or_url": "",
                "description": "No local source file was loaded and this stage is prohibited from entering Web or fabricating prices.",
                "recommended_action": "Download official information-price Excel/PDF and place it under construction_cost_knowledge_engine/data/private/reference_extraction/source_excels/market_price_sources/.",
                "review_status": REVIEW_STATUS,
            }
        )
    market_dir = project_root / MARKET_SOURCE_DIR_REL
    local_files = sorted([path for path in market_dir.rglob("*") if path.is_file()]) if market_dir.exists() else []
    rows.append(
        {
            "source_id": "MKT-SRC-LOCAL",
            "source_name": "用户本地市场价来源文件目录",
            "source_region": "",
            "source_period": "",
            "source_date": "",
            "tax_status": "pending",
            "source_file_or_url": rel(market_dir, project_root),
            "fetched_or_loaded_at": loaded_at,
            "source_trust_level": "pending",
            "access_status": "no_local_files_found" if not local_files else "local_files_found_not_parsed",
            "parse_status": "not_parsed",
            "remark": f"local_file_count={len(local_files)}; parser for official market source files not activated in this stage",
        }
    )
    if not local_files:
        issues.append(
            {
                "issue_id": f"MKT_ISSUE_{len(issues) + 1:06d}",
                "issue_type": "local_market_source_files_missing",
                "severity": "high",
                "source_id": "MKT-SRC-LOCAL",
                "source_name": "用户本地市场价来源文件目录",
                "source_file_or_url": rel(market_dir, project_root),
                "description": "No local market price source files were found.",
                "recommended_action": "Create the market_price_sources folder and place official information-price Excel/PDF files there.",
                "review_status": REVIEW_STATUS,
            }
        )
    return rows, issues


def build_summary(
    dashboard: Sequence[Dict[str, Any]],
    market_sources: Sequence[Dict[str, Any]],
    market_normalized_count: int,
    rec: str,
) -> List[Dict[str, Any]]:
    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    return [
        {"metric_name": "stage_name", "metric_value": STAGE_NAME, "remark": "Internal price V2 refresh and market baseline attempt."},
        {"metric_name": "recommendation", "metric_value": rec, "remark": "No approved price output."},
        {"metric_name": "price_item_candidate_rows", "metric_value": metrics.get("price_item_candidate_rows", 0), "remark": "Internal price candidates from updated XLS."},
        {"metric_name": "missing_unit_count", "metric_value": metrics.get("missing_unit_count", 0), "remark": "Requires manual correction if non-zero."},
        {"metric_name": "unit_parsed_count", "metric_value": metrics.get("unit_parsed_count", 0), "remark": "Parsed candidate units."},
        {"metric_name": "unit_unparsed_count", "metric_value": metrics.get("unit_unparsed_count", 0), "remark": "Missing or unparsed candidate units."},
        {"metric_name": "market_source_count", "metric_value": len(market_sources), "remark": "Catalog entries only unless local source files are loaded."},
        {"metric_name": "market_normalized_item_count", "metric_value": market_normalized_count, "remark": "No fabricated market prices."},
    ]


def recommendation(
    dashboard: Sequence[Dict[str, Any]],
    market_normalized_count: int,
    xlsx_ok: bool,
) -> str:
    if not xlsx_ok:
        return "blocked_xlsx_generation_failed"
    metrics = {row["metric_name"]: str(row["metric_value"]) for row in dashboard}
    if metrics.get("price_item_candidate_rows") in {"0", "None", ""}:
        return "blocked_xls_read_failed"
    if market_normalized_count == 0:
        return "market_source_manual_file_required"
    if metrics.get("unit_unparsed_count") not in {"0", None}:
        return "internal_price_v2_partial_manual_intervention_required"
    return "price_sources_ready_for_enterprise_quota_price_comparison_v0_2"


def create_xlsx(output_dir: Path, node_exe: Path, node_modules: Path) -> None:
    specs = [
        ["internal_price_candidate_v2", "internal_price_item_candidate_v2.csv", len(INTERNAL_CANDIDATE_FIELDS)],
        ["internal_price_unit_normalized_v2", "internal_price_unit_normalized_v2.csv", len(UNIT_FIELDS)],
        ["internal_price_quality_dashboard_v2", "internal_price_quality_dashboard_v2.csv", len(DASHBOARD_FIELDS)],
        ["market_price_source_catalog", "market_price_source_catalog.csv", len(MARKET_SOURCE_FIELDS)],
        ["market_price_raw_items", "market_price_raw_items.csv", len(MARKET_RAW_FIELDS)],
        ["market_price_normalized_items", "market_price_normalized_items.csv", len(MARKET_NORMALIZED_FIELDS)],
        ["market_price_parse_issues", "market_price_parse_issues.csv", len(MARKET_ISSUE_FIELDS)],
        ["summary", "summary_for_xlsx.csv", len(SUMMARY_FIELDS)],
    ]
    builder = r'''
import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = process.argv[2];
const specs = JSON.parse(process.argv[3]);
let workbook = null;
const actualSheets = [];
for (const spec of specs) {
  const [sheetName, fileName, colCount] = spec;
  const csvText = await fs.readFile(`${outputDir}/${fileName}`, "utf8");
  if (!workbook) {
    workbook = await Workbook.fromCSV(csvText, { sheetName });
  } else {
    await workbook.fromCSV(csvText, { sheetName });
  }
  const effectiveSheetName = sheetName.slice(0, 31);
  actualSheets.push(effectiveSheetName);
  const sheet = workbook.worksheets.getItem(effectiveSheetName);
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const header = sheet.getRangeByIndexes(0, 0, 1, colCount);
  header.format = { fill: "#1F4E79", font: { bold: true, color: "#FFFFFF" }, wrapText: true };
  header.format.borders = { preset: "bottom", style: "thin", color: "#9FBAD0" };
  const used = sheet.getUsedRange();
  used.format = { wrapText: true, verticalAlignment: "top" };
  used.format.font = { name: "Aptos", size: 10 };
  sheet.getRangeByIndexes(0, 0, 1, colCount).format.columnWidth =
    effectiveSheetName === "summary" || effectiveSheetName.includes("dashboard") ? 26 : 18;
}
for (const sheetName of actualSheets) {
  await workbook.render({ sheetName, range: "A1:H20", scale: 1, format: "png" });
}
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(`${outputDir}/Price_Source_Refresh_And_Market_Baseline_Review.xlsx`);
console.log(`xlsx=${outputDir}/Price_Source_Refresh_And_Market_Baseline_Review.xlsx`);
'''
    with tempfile.TemporaryDirectory(prefix="price_source_xlsx_") as tmp:
        tmp_path = Path(tmp)
        link = tmp_path / "node_modules"
        try:
            os.symlink(node_modules, link, target_is_directory=True)
        except OSError:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(node_modules)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        builder_path = tmp_path / "build_price_source_review.mjs"
        builder_path.write_text(builder, encoding="utf-8")
        subprocess.run(
            [str(node_exe), str(builder_path), str(output_dir), json.dumps(specs)],
            cwd=tmp_path,
            check=True,
        )
    sidecar = output_dir / "Price_Source_Refresh_And_Market_Baseline_Review.xlsx.inspect.ndjson"
    if sidecar.exists():
        sidecar.unlink()


def write_report(
    path: Path,
    dashboard: Sequence[Dict[str, Any]],
    unit_rows: Sequence[Dict[str, Any]],
    market_sources: Sequence[Dict[str, Any]],
    market_issues: Sequence[Dict[str, Any]],
    market_normalized_count: int,
    rec: str,
) -> None:
    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    conversion_samples = [
        f"{row['raw_unit']} -> {row['conversion_target_unit']} price_factor={row['price_factor_from_raw_to_target']} ({row['conversion_direction']})"
        for row in unit_rows
        if row.get("conversion_rule_status") == "supported"
    ][:12]
    lines = [
        "# Stage PRICE-SOURCE-REFRESH-AND-MARKET-BASELINE-1 Report",
        "",
        "## 1. Task Scope",
        "",
        "Refresh the updated enterprise internal price XLS into V2 candidate artifacts, record unit normalization/conversion governance, and establish a traceable market price source baseline without fabricating market prices.",
        "",
        "## 2. Internal Price V2 Refresh Result",
        "",
        f"- total_rows: {metrics.get('total_rows', 0)}",
        f"- price_item_candidate_rows: {metrics.get('price_item_candidate_rows', 0)}",
        f"- rows_with_any_price: {metrics.get('rows_with_any_price', 0)}",
        f"- high_confidence_price_rows: {metrics.get('high_confidence_price_rows', 0)}",
        f"- medium_confidence_price_rows: {metrics.get('medium_confidence_price_rows', 0)}",
        f"- low_confidence_price_rows: {metrics.get('low_confidence_price_rows', 0)}",
        "",
        "## 3. Unit Completeness Improvement",
        "",
        f"- missing_unit_count: {metrics.get('missing_unit_count', 0)}",
        f"- unit_parsed_count: {metrics.get('unit_parsed_count', 0)}",
        f"- unit_unparsed_count: {metrics.get('unit_unparsed_count', 0)}",
        f"- duplicate_name_unit_count: {metrics.get('duplicate_name_unit_count', 0)}",
        "",
        "Recorded conversion rules:",
    ]
    lines.extend(f"- {item}" for item in conversion_samples)
    lines.extend(
        [
            "",
            "## 4. Market Price Source Attempt",
            "",
            f"- market_source_count: {len(market_sources)}",
            f"- market_normalized_item_count: {market_normalized_count}",
            f"- market_issue_count: {len(market_issues)}",
            "- No Web fetch was performed in this stage.",
            "",
            "## 5. Market Price Source Governance",
            "",
            "- Market prices require source_name, source_region, source_period/source_date, tax_status, source_file_or_url, fetched_or_loaded_at, and source_trust_level.",
            "- Material-only prices must remain material-only or total-only and must not be presented as complete labor/material/machine/management composite prices.",
            "- Management fee remains blank unless a reliable source/rule is provided.",
            "",
            "## 6. What Was Not Filled",
            "",
            "- market_price_raw_items.csv is header-only because no local market price source file was found.",
            "- market_price_normalized_items.csv is header-only; no market prices were fabricated.",
            "- No approved, locked, or formal enterprise quota table was generated.",
            "",
            "## 7. Not Approved / Not Final Statement",
            "",
            "All outputs are pending review artifacts. This stage does not write the database, generate internal_price_library, lock internal_price_id, or create a formal enterprise quota.",
            "",
            "## 8. Next Step Recommendation",
            "",
            rec,
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def artifact_row_count(path: Path, workbook_total_rows: int) -> str:
    if path.suffix.lower() == ".csv":
        return csv_row_count(path)
    if path.suffix.lower() == ".xlsx":
        return str(workbook_total_rows)
    return ""


def manifest_row(project_root: Path, output_dir: Path, artifact_name: str, workbook_total_rows: int) -> Dict[str, Any]:
    path = output_dir / artifact_name
    exists = path.exists()
    source_files = [
        rel(project_root / SOURCE_REL, project_root),
        rel(project_root / MARKET_SOURCE_DIR_REL, project_root),
    ]
    return {
        "stage_name": STAGE_NAME,
        "artifact_name": artifact_name,
        "expected_path": rel(path, project_root),
        "exists": str(exists).lower(),
        "file_size_bytes": path.stat().st_size if exists else 0,
        "row_count": artifact_row_count(path, workbook_total_rows) if exists else "",
        "sha256": sha256_file(path) if exists else "",
        "created_or_modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if exists else "",
        "source_file": ";".join(source_files),
        "can_regenerate": "true",
        "backup_required": "true",
        "backup_path": "construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_PRICE_SOURCE_REFRESH_AND_MARKET_BASELINE_1",
        "status": "generated_pending_review" if exists else "missing",
        "remark": "pending price source refresh artifact; not approved; no database write; no market price fabrication",
    }


def update_manifest(project_root: Path, output_dir: Path, workbook_total_rows: int) -> None:
    manifest_path = project_root / DOCS_REF_REL / "reference_artifact_manifest.csv"
    existing = read_csv(manifest_path)
    kept = [row for row in existing if norm(row.get("stage_name")) != STAGE_NAME]
    new_rows = [manifest_row(project_root, output_dir, artifact, workbook_total_rows) for artifact in OUTPUT_ARTIFACTS]
    all_rows = kept + new_rows
    write_csv(manifest_path, MANIFEST_FIELDS, all_rows)
    write_manifest_md(project_root, all_rows, new_rows)


def write_manifest_md(project_root: Path, all_rows: Sequence[Dict[str, Any]], latest: Sequence[Dict[str, Any]]) -> None:
    registered = len(all_rows)
    existing_count = sum(1 for row in all_rows if norm(row.get("exists")).lower() == "true")
    lines = [
        "# Reference Artifact Manifest",
        "",
        "## Governance",
        "",
        "- `construction_cost_knowledge_engine/data/private/` is intentionally not tracked by Git.",
        "- Every private artifact must be registered with `row_count` and `sha256` after generation.",
        "- Each completed stage must back up its `runs` output directory after validation.",
        "- Mock SQLite and seed CSV artifacts must not be used as source of truth.",
        "- Internal price V2 outputs are pending review artifacts only and do not approve prices.",
        "- Market price baseline outputs must include source evidence; blank market rows must not be treated as prices.",
        "- Material-only market prices must not be promoted to complete composite costs.",
        "",
        "## Current Manifest Summary",
        "",
        f"- registered_artifacts: {registered}",
        f"- existing_artifacts: {existing_count}",
        f"- missing_artifacts: {registered - existing_count}",
        "",
        "## Manifest CSV",
        "",
        "`construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv`",
        "",
        "## Latest Price Source Refresh And Market Baseline Outputs",
        "",
    ]
    for row in latest:
        lines.append(f"- `{row.get('expected_path')}` ({row.get('row_count') or 'n/a'} rows)")
    lines.extend(
        [
            "",
            "## Backup Requirement",
            "",
            "`construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_PRICE_SOURCE_REFRESH_AND_MARKET_BASELINE_1/`",
            "",
        ]
    )
    (project_root / DOCS_REF_REL / "REFERENCE_ARTIFACT_MANIFEST.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_blocked_report(output_dir: Path, rec: str, message: str) -> None:
    lines = [
        "# Stage PRICE-SOURCE-REFRESH-AND-MARKET-BASELINE-1 Report",
        "",
        "## 1. Task Scope",
        "",
        "Refresh internal price V2 and market source baseline.",
        "",
        "## 2. Internal Price V2 Refresh Result",
        "",
        message,
        "",
        "## 3. Unit Completeness Improvement",
        "",
        "Skipped.",
        "",
        "## 4. Market Price Source Attempt",
        "",
        "Skipped.",
        "",
        "## 5. Market Price Source Governance",
        "",
        "Skipped.",
        "",
        "## 6. What Was Not Filled",
        "",
        "No generated price data.",
        "",
        "## 7. Not Approved / Not Final Statement",
        "",
        "No approved output generated.",
        "",
        "## 8. Next Step Recommendation",
        "",
        rec,
        "",
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "stage_price_source_refresh_and_market_baseline_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    project_root = args.project_root
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = project_root / SOURCE_REL

    if not source_path.exists():
        write_blocked_report(output_dir, "blocked_missing_inputs", f"Missing input: {rel(source_path, project_root)}")
        print("recommendation=blocked_missing_inputs")
        print(f"missing_input={source_path}")
        return 2

    source_file = rel(source_path, project_root)
    source_hash = sha256_file(source_path)
    file_size = source_path.stat().st_size
    try:
        sheets = extract_xls_with_excel_com(source_path)
    except Exception as exc:  # noqa: BLE001
        write_blocked_report(output_dir, "blocked_xls_read_failed", f"XLS read failed: {exc}")
        print("recommendation=blocked_xls_read_failed")
        print(f"xls_error={exc}")
        return 3

    profile, raw_rows = build_internal_rows(source_file, source_hash, file_size, sheets)
    duplicate_keys = duplicate_keys_for(raw_rows)
    candidates = build_candidates(raw_rows, duplicate_keys)
    unit_rows = build_unit_rows(raw_rows, candidates)
    dashboard = build_internal_dashboard(raw_rows, candidates, unit_rows)
    market_sources, market_issues = market_source_catalog(project_root)
    market_raw_rows: List[Dict[str, Any]] = []
    market_normalized_rows: List[Dict[str, Any]] = []

    rec_before_xlsx = recommendation(dashboard, len(market_normalized_rows), xlsx_ok=True)
    summary = build_summary(dashboard, market_sources, len(market_normalized_rows), rec_before_xlsx)

    write_csv(output_dir / "internal_price_source_profile_v2.csv", SOURCE_PROFILE_FIELDS, profile)
    write_csv(output_dir / "internal_price_item_candidate_v2.csv", INTERNAL_CANDIDATE_FIELDS, candidates)
    write_csv(output_dir / "internal_price_unit_normalized_v2.csv", UNIT_FIELDS, unit_rows)
    write_csv(output_dir / "internal_price_quality_dashboard_v2.csv", DASHBOARD_FIELDS, dashboard)
    write_csv(output_dir / "market_price_source_catalog.csv", MARKET_SOURCE_FIELDS, market_sources)
    write_csv(output_dir / "market_price_raw_items.csv", MARKET_RAW_FIELDS, market_raw_rows)
    write_csv(output_dir / "market_price_normalized_items.csv", MARKET_NORMALIZED_FIELDS, market_normalized_rows)
    write_csv(output_dir / "market_price_parse_issues.csv", MARKET_ISSUE_FIELDS, market_issues)
    write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary)

    xlsx_ok = True
    try:
        create_xlsx(output_dir, args.node_exe, args.node_modules)
    except Exception as exc:  # noqa: BLE001
        xlsx_ok = False
        print(f"xlsx_error={exc}")

    rec = recommendation(dashboard, len(market_normalized_rows), xlsx_ok=xlsx_ok)
    if rec != rec_before_xlsx:
        summary = build_summary(dashboard, market_sources, len(market_normalized_rows), rec)
        write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary)

    write_report(
        output_dir / "stage_price_source_refresh_and_market_baseline_report.md",
        dashboard,
        unit_rows,
        market_sources,
        market_issues,
        len(market_normalized_rows),
        rec,
    )

    workbook_total_rows = (
        len(candidates)
        + len(unit_rows)
        + len(dashboard)
        + len(market_sources)
        + len(market_raw_rows)
        + len(market_normalized_rows)
        + len(market_issues)
        + len(summary)
    )
    update_manifest(project_root, output_dir, workbook_total_rows)
    (output_dir / "summary_for_xlsx.csv").unlink(missing_ok=True)

    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    print(f"recommendation={rec}")
    print(f"internal_price_candidate_rows={len(candidates)}")
    print(f"missing_unit_count={metrics.get('missing_unit_count', 0)}")
    print(f"unit_parsed_count={metrics.get('unit_parsed_count', 0)}")
    print(f"unit_unparsed_count={metrics.get('unit_unparsed_count', 0)}")
    print(f"rows_with_any_price={metrics.get('rows_with_any_price', 0)}")
    print(f"high_confidence_price_rows={metrics.get('high_confidence_price_rows', 0)}")
    print(f"medium_confidence_price_rows={metrics.get('medium_confidence_price_rows', 0)}")
    print(f"low_confidence_price_rows={metrics.get('low_confidence_price_rows', 0)}")
    print(f"duplicate_name_unit_count={metrics.get('duplicate_name_unit_count', 0)}")
    print(f"market_source_count={len(market_sources)}")
    print(f"market_normalized_item_count={len(market_normalized_rows)}")
    print(f"approved_count={metrics.get('approved_count', 0)}")
    print(f"database_write_detected={metrics.get('database_write_detected', 0)}")
    print(f"xlsx_exists={(output_dir / 'Price_Source_Refresh_And_Market_Baseline_Review.xlsx').exists()}")
    print(f"output_dir={output_dir}")
    return 0 if xlsx_ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
