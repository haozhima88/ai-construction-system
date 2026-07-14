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
from typing import Any, Dict, Iterable, List, Sequence, Tuple


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
SOURCE_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "source_excels" / "内部价格表.xls"
RUNS_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs"
OUTPUT_DIR_REL = RUNS_REL / "ENTERPRISE_PRICE_BASELINE_LOCK_1"
DOCS_REF_REL = ENGINE_REL / "docs" / "reference_extraction"

NODE_EXE_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
)
NODE_MODULES_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
)

STAGE_NAME = "ENTERPRISE_PRICE_BASELINE_LOCK_1"
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
    "parse_status",
    "remark",
]

ALL_ROWS_FIELDS = [
    "source_row_id",
    "source_file",
    "source_file_hash",
    "source_sheet",
    "source_excel_row",
    "raw_category",
    "raw_subcategory",
    "raw_name",
    "raw_unit",
    "raw_labor_fee",
    "raw_material_fee",
    "raw_machine_fee",
    "raw_total_fee",
    "raw_remark",
    "raw_extra_fields_json",
    "row_type",
    "parse_issue",
    "review_status",
    "human_comment",
]

CANDIDATE_FIELDS = [
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
    "unit_factor_to_normalized",
    "unit_dimension",
    "labor_fee",
    "material_fee",
    "machine_fee",
    "total_fee",
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
    "unit_factor_to_normalized",
    "unit_dimension",
    "parse_status",
    "row_count",
    "candidate_count",
    "sample_source_rows",
    "sample_names",
    "review_status",
    "remark",
]

ISSUE_FIELDS = [
    "issue_id",
    "issue_type",
    "severity",
    "source_row_id",
    "internal_price_id",
    "source_sheet",
    "source_excel_row",
    "raw_name",
    "raw_unit",
    "description",
    "recommended_action",
    "review_status",
]

DASHBOARD_FIELDS = [
    "metric_name",
    "metric_value",
    "expected_or_threshold",
    "status",
    "severity",
    "remark",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lock enterprise internal price table baseline.")
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


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


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
    # Handles workbooks currently open in Excel by using FileShare.ReadWrite.
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
    with tempfile.TemporaryDirectory(prefix="internal_price_hash_") as tmp:
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
    $rows = @()
    for ($r = 1; $r -le $rowCount; $r++) {
      $cells = @()
      for ($c = 1; $c -le $colCount; $c++) {
        $cell = $used.Cells.Item($r, $c)
        $text = [string]$cell.Text
        $value = $cell.Value2
        $formula = [string]$cell.Formula
        $cells += [PSCustomObject]@{
          text = $text
          value = $(if ($null -eq $value) { "" } else { [string]$value })
          has_formula = $($formula -like "=*")
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
    with tempfile.TemporaryDirectory(prefix="internal_price_xls_") as tmp:
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


def extra_fields_json(cells: Sequence[Dict[str, Any]], detected: Dict[int, Dict[str, str]]) -> str:
    fields: Dict[str, Any] = {}
    for idx, cell in enumerate(cells, start=1):
        meta = detected.get(idx, {"header": f"column_{idx}", "role": f"extra_{idx}"})
        fields[f"col_{idx}"] = {
            "header": meta["header"],
            "role": meta["role"],
            "text": norm(cell.get("text")),
            "value": norm(cell.get("value")),
            "has_formula": bool(cell.get("has_formula")),
        }
    return json.dumps(fields, ensure_ascii=False, separators=(",", ":"))


def parse_decimal(value: Any) -> Decimal | None:
    text = norm(value)
    if not text or text in {"-", "—", "--", "/"}:
        return None
    cleaned = (
        text.replace(",", "")
        .replace("￥", "")
        .replace("¥", "")
        .replace("元", "")
        .replace(" ", "")
    )
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def has_non_numeric_price_text(*values: str) -> bool:
    for value in values:
        text = norm(value)
        if not text or text in {"-", "—", "--", "/"}:
            continue
        if parse_decimal(text) is None:
            return True
    return False


def normalize_unit(raw_unit: str) -> Tuple[str, str, str, str]:
    original = norm(raw_unit)
    value = compact(original).lower().replace("³", "3").replace("²", "2")
    value = value.replace("立方米", "m3").replace("平方米", "m2")
    if not value:
        return "unparsed", "", "unknown", "missing"

    rules = [
        (r"^(100)?m3$", "m3", "100" if value.startswith("100") else "1", "volume"),
        (r"^(100)?m2$", "m2", "100" if value.startswith("100") else "1", "area"),
        (r"^(100)?立方$", "m3", "100" if value.startswith("100") else "1", "volume"),
        (r"^(100)?平方$", "m2", "100" if value.startswith("100") else "1", "area"),
        (r"^米$|^m$", "m", "1", "length"),
        (r"^t$|^吨$", "t", "1", "weight"),
        (r"^kg$|^千克$|^公斤$", "kg", "1", "weight"),
        (r"^台班$", "台班", "1", "machine_shift"),
        (r"^工日$", "工日", "1", "labor_day"),
        (r"^项$", "项", "1", "item"),
    ]
    for pattern, unit, factor, dimension in rules:
        if re.match(pattern, value):
            return unit, factor, dimension, "parsed"
    if value in {"㎡"}:
        return "m2", "1", "area", "parsed"
    if value in {"m³"}:
        return "m3", "1", "volume", "parsed"
    return "unparsed", "", "unknown", "unparsed"


def derive_feature_text(name: str, remark: str) -> str:
    parts: List[str] = []
    text = f"{name} {remark}"
    patterns = [
        r"C\d+",
        r"\d+(?:\.\d+)?mm",
        r"\d+(?:\.\d+)?m\b",
        r"\d+%",
        r"厚\d+",
        r"深度[:：]?[^\s，,；;]+",
        r"含[^，,；;]+",
        r"根据[^，,；;]+",
        r"综合考虑",
        r"专票",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if match and match not in parts:
                parts.append(match)
    if remark and remark not in parts:
        parts.append(remark)
    return ";".join(parts[:8])


def classify_row(row: Dict[str, str], header_row: int, excel_row: int, any_price: bool) -> Tuple[str, List[str]]:
    issues: List[str] = []
    values = [row.get(field, "") for field in ["raw_category", "raw_subcategory", "raw_name", "raw_unit", "raw_labor_fee", "raw_material_fee", "raw_machine_fee", "raw_total_fee", "raw_remark"]]
    if not any(norm(value) for value in values):
        return "empty", []
    if excel_row == header_row:
        return "category_header", ["subtotal_or_header_row"]
    name = norm(row.get("raw_name"))
    category = norm(row.get("raw_category"))
    if re.search(r"小计|合计|subtotal|total", name + category, flags=re.IGNORECASE):
        return "subtotal", ["subtotal_or_header_row"]
    if not name and norm(row.get("raw_remark")) and not any_price:
        return "note", ["possible_non_price_row"]
    if name and any_price:
        return "price_item", issues
    if category and not name and not any_price:
        return "category_header", ["subtotal_or_header_row"]
    return "unknown", ["possible_non_price_row"]


def build_rows(source_file: str, source_hash: str, sheets: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    profile: List[Dict[str, Any]] = []
    all_rows: List[Dict[str, Any]] = []
    sheet_meta: Dict[str, Any] = {}
    row_seq = 1
    for sheet in sheets:
        header_row, detected = detect_header(sheet)
        sheet_meta[sheet["name"]] = {"header_row": header_row, "detected": detected}
        detected_columns = [
            {"column_index": idx, "header": meta["header"], "role": meta["role"]}
            for idx, meta in detected.items()
        ]
        profile.append(
            {
                "source_file": source_file,
                "source_file_hash": source_hash,
                "file_size_bytes": "",
                "sheet_count": len(sheets),
                "sheet_name": sheet["name"],
                "visible": str(bool(sheet.get("visible", True))).lower(),
                "row_count": sheet.get("row_count", 0),
                "column_count": sheet.get("column_count", 0),
                "detected_header_row": header_row,
                "detected_columns": json.dumps(detected_columns, ensure_ascii=False, separators=(",", ":")),
                "parse_status": "ok",
                "remark": "Parsed from .xls via read-only Excel COM because bundled Python lacks xlrd.",
            }
        )
        for idx, cells in enumerate(sheet.get("rows", []), start=int(sheet.get("start_row", 1))):
            row = {
                "source_row_id": f"IPRAW-{row_seq:06d}",
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
                "raw_extra_fields_json": extra_fields_json(cells, detected),
                "row_type": "",
                "parse_issue": "",
                "review_status": REVIEW_STATUS,
                "human_comment": "",
            }
            prices = [parse_decimal(row[field]) for field in ["raw_labor_fee", "raw_material_fee", "raw_machine_fee", "raw_total_fee"]]
            row_type, issues = classify_row(row, header_row, idx, any(price is not None for price in prices))
            if not row["raw_name"] and row_type not in {"empty", "category_header", "subtotal", "note"}:
                issues.append("missing_name")
            if row_type == "price_item" and not row["raw_unit"]:
                issues.append("missing_unit")
            if row_type == "price_item" and all(price is None for price in prices):
                issues.append("missing_all_price_fields")
            if row_type == "price_item" and has_non_numeric_price_text(row["raw_labor_fee"], row["raw_material_fee"], row["raw_machine_fee"], row["raw_total_fee"]):
                issues.append("ambiguous_price_fields")
            row["row_type"] = row_type
            row["parse_issue"] = ";".join(dict.fromkeys(issues))
            all_rows.append(row)
            row_seq += 1
    return profile, all_rows, sheet_meta


def confidence_for(name: str, unit_status: str, any_price: bool, ambiguous: bool) -> str:
    if not name or not any_price or ambiguous:
        return "low"
    if unit_status == "parsed":
        return "high"
    return "medium"


def build_candidates(all_rows: Sequence[Dict[str, Any]], duplicate_keys: set[Tuple[str, str]]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for row in all_rows:
        if row["row_type"] != "price_item":
            continue
        labor = parse_decimal(row["raw_labor_fee"])
        material = parse_decimal(row["raw_material_fee"])
        machine = parse_decimal(row["raw_machine_fee"])
        raw_total = parse_decimal(row["raw_total_fee"])
        component_sum = sum((value or Decimal("0")) for value in [labor, material, machine])
        total = raw_total if raw_total is not None else (component_sum if any(value is not None for value in [labor, material, machine]) else None)
        unit_normalized, factor, dimension, unit_status = normalize_unit(row["raw_unit"])
        any_price = any(value is not None for value in [labor, material, machine, raw_total])
        ambiguous = has_non_numeric_price_text(row["raw_labor_fee"], row["raw_material_fee"], row["raw_machine_fee"], row["raw_total_fee"])
        if raw_total is not None:
            price_structure = "raw_total_present"
        elif any_price:
            price_structure = "component_sum_derived_total"
        else:
            price_structure = "missing_all_price_fields"
        key = (compact(row["raw_name"]), unit_normalized if unit_status == "parsed" else compact(row["raw_unit"]))
        remarks = [issue for issue in row["parse_issue"].split(";") if issue]
        if key in duplicate_keys:
            remarks.append("duplicate_name_unit")
        if not row["raw_remark"]:
            remarks.append("effective_date_missing")
        candidates.append(
            {
                "internal_price_id": f"IP-{len(candidates) + 1:06d}",
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
                "unit_normalized": unit_normalized,
                "unit_factor_to_normalized": factor,
                "unit_dimension": dimension,
                "labor_fee": format_decimal(labor),
                "material_fee": format_decimal(material),
                "machine_fee": format_decimal(machine),
                "total_fee": format_decimal(total),
                "price_structure_status": price_structure,
                "price_source_type": "enterprise_internal_price_table",
                "price_source_name": "内部价格表.xls",
                "effective_date": "",
                "confidence_level": confidence_for(row["raw_name"], unit_status, any_price, ambiguous),
                "review_status": REVIEW_STATUS,
                "reviewer": "",
                "remark": ";".join(dict.fromkeys(remarks)),
            }
        )
    return candidates


def duplicate_keys_for(all_rows: Sequence[Dict[str, Any]]) -> set[Tuple[str, str]]:
    counter: Counter[Tuple[str, str]] = Counter()
    for row in all_rows:
        if row["row_type"] != "price_item":
            continue
        unit_normalized, _factor, _dimension, status = normalize_unit(row["raw_unit"])
        key = (compact(row["raw_name"]), unit_normalized if status == "parsed" else compact(row["raw_unit"]))
        if key[0]:
            counter[key] += 1
    return {key for key, count in counter.items() if count > 1}


def build_unit_rows(all_rows: Sequence[Dict[str, Any]], candidates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    all_by_unit: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    cand_by_unit: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        if row["raw_unit"]:
            all_by_unit[row["raw_unit"]].append(row)
    for row in candidates:
        cand_by_unit[row["raw_unit"]].append(row)
    out: List[Dict[str, Any]] = []
    for raw_unit in sorted(all_by_unit.keys(), key=lambda value: (normalize_unit(value)[0], value)):
        unit, factor, dimension, status = normalize_unit(raw_unit)
        rows = all_by_unit[raw_unit]
        cands = cand_by_unit.get(raw_unit, [])
        out.append(
            {
                "raw_unit": raw_unit,
                "unit_normalized": unit,
                "unit_factor_to_normalized": factor,
                "unit_dimension": dimension,
                "parse_status": status,
                "row_count": len(rows),
                "candidate_count": len(cands),
                "sample_source_rows": ";".join(str(row["source_excel_row"]) for row in rows[:8]),
                "sample_names": ";".join(row.get("raw_name", "") for row in rows[:5] if row.get("raw_name")),
                "review_status": REVIEW_STATUS,
                "remark": "" if status == "parsed" else "unit requires manual normalization",
            }
        )
    if not out:
        out.append(
            {
                "raw_unit": "",
                "unit_normalized": "unparsed",
                "unit_factor_to_normalized": "",
                "unit_dimension": "unknown",
                "parse_status": "missing",
                "row_count": 0,
                "candidate_count": 0,
                "sample_source_rows": "",
                "sample_names": "",
                "review_status": REVIEW_STATUS,
                "remark": "no unit values found",
            }
        )
    return out


def add_issue(
    issues: List[Dict[str, Any]],
    issue_type: str,
    severity: str,
    description: str,
    recommended_action: str,
    source_row: Dict[str, Any] | None = None,
    candidate: Dict[str, Any] | None = None,
) -> None:
    issues.append(
        {
            "issue_id": f"IP_ISSUE_{len(issues) + 1:06d}",
            "issue_type": issue_type,
            "severity": severity,
            "source_row_id": (source_row or {}).get("source_row_id", ""),
            "internal_price_id": (candidate or {}).get("internal_price_id", ""),
            "source_sheet": (source_row or candidate or {}).get("source_sheet", ""),
            "source_excel_row": (source_row or candidate or {}).get("source_excel_row", ""),
            "raw_name": (source_row or candidate or {}).get("raw_name", ""),
            "raw_unit": (source_row or candidate or {}).get("raw_unit", ""),
            "description": description,
            "recommended_action": recommended_action,
            "review_status": REVIEW_STATUS,
        }
    )


def build_issues(all_rows: Sequence[Dict[str, Any]], candidates: Sequence[Dict[str, Any]], unit_rows: Sequence[Dict[str, Any]], duplicate_keys: set[Tuple[str, str]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for row in all_rows:
        row_issues = [issue for issue in row.get("parse_issue", "").split(";") if issue]
        if row["row_type"] in {"category_header", "subtotal"}:
            add_issue(issues, "subtotal_or_header_row", "low", "Header/subtotal/category row retained in all_rows_review but excluded from candidates.", "No candidate action required.", row)
        if row["row_type"] in {"note", "unknown"}:
            add_issue(issues, "possible_non_price_row", "medium", "Row is not a clear price item.", "Manual review if the row carries usable pricing context.", row)
        for issue_type in row_issues:
            if issue_type == "subtotal_or_header_row":
                continue
            severity = "high" if issue_type in {"missing_name", "missing_all_price_fields", "ambiguous_price_fields"} else "medium"
            add_issue(issues, issue_type, severity, f"{issue_type} detected in source row.", "Cost department should correct or confirm before alignment.", row)
    for cand in candidates:
        unit, _factor, _dimension, status = normalize_unit(cand["raw_unit"])
        if not cand["raw_unit"]:
            add_issue(issues, "missing_unit", "medium", "Candidate lacks source unit.", "Confirm unit before quota alignment.", None, cand)
        elif status != "parsed":
            add_issue(issues, "unit_unparsed", "medium", "Candidate unit could not be normalized.", "Add unit normalization rule or manual unit.", None, cand)
        if not any([cand["labor_fee"], cand["material_fee"], cand["machine_fee"], cand["total_fee"]]):
            add_issue(issues, "missing_all_price_fields", "high", "Candidate has no usable price fields.", "Do not align until price field is confirmed.", None, cand)
        key = (compact(cand["raw_name"]), unit if status == "parsed" else compact(cand["raw_unit"]))
        if key in duplicate_keys:
            add_issue(issues, "duplicate_name_unit", "medium", "Duplicate name+unit candidate detected.", "Review whether rows represent different features or duplicate entries.", None, cand)
        if cand["feature_text_candidate"]:
            add_issue(issues, "remark_contains_condition", "low", "Remark/name contains condition text that may affect matching.", "Preserve as feature text during alignment.", None, cand)
    add_issue(
        issues,
        "effective_date_missing",
        "medium",
        "No effective date was detected from the source workbook.",
        "Confirm price effective date before enterprise template pricing.",
    )
    return issues


def build_dashboard(all_rows: Sequence[Dict[str, Any]], candidates: Sequence[Dict[str, Any]], unit_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    price_rows = [
        row
        for row in all_rows
        if any(parse_decimal(row[field]) is not None for field in ["raw_labor_fee", "raw_material_fee", "raw_machine_fee", "raw_total_fee"])
    ]
    rows_without_price = [row for row in all_rows if row["row_type"] != "empty" and row not in price_rows]
    unit_parsed = sum(1 for row in candidates if row["unit_normalized"] != "unparsed")
    unit_unparsed = sum(1 for row in candidates if row["unit_normalized"] == "unparsed")
    duplicate_count = sum(1 for row in candidates if "duplicate_name_unit" in row.get("remark", ""))
    confidence = Counter(row["confidence_level"] for row in candidates)
    metrics = [
        ("total_rows", len(all_rows), "> 0", len(all_rows) > 0, "high", ""),
        ("price_item_candidate_rows", len(candidates), "> 0", len(candidates) > 0, "high", ""),
        ("category_header_rows", sum(1 for row in all_rows if row["row_type"] == "category_header"), "review only", True, "low", ""),
        ("missing_name_count", sum(1 for row in all_rows if "missing_name" in row.get("parse_issue", "")), "manual review", True, "medium", ""),
        ("missing_unit_count", sum(1 for row in candidates if not row["raw_unit"]), "manual review", True, "medium", ""),
        ("rows_with_any_price", len(price_rows), "> 0", len(price_rows) > 0, "high", ""),
        ("rows_without_any_price", len(rows_without_price), "review only", True, "medium", ""),
        ("unit_parsed_count", unit_parsed, "> 0", unit_parsed > 0, "medium", ""),
        ("unit_unparsed_count", unit_unparsed, "manual review", True, "medium", ""),
        ("duplicate_name_unit_count", duplicate_count, "manual review", True, "medium", ""),
        ("high_confidence_price_rows", confidence.get("high", 0), "reference only", True, "medium", ""),
        ("medium_confidence_price_rows", confidence.get("medium", 0), "reference only", True, "medium", ""),
        ("low_confidence_price_rows", confidence.get("low", 0), "manual review", True, "high", ""),
        ("approved_count", 0, "0", True, "high", "No approved rows generated."),
        ("non_pending_review_status_count", sum(1 for row in list(all_rows) + list(candidates) + list(unit_rows) if row.get("review_status") != REVIEW_STATUS), "0", True, "high", ""),
    ]
    return [
        {
            "metric_name": name,
            "metric_value": value,
            "expected_or_threshold": expected,
            "status": "pass" if ok else "fail",
            "severity": severity,
            "remark": remark,
        }
        for name, value, expected, ok, severity, remark in metrics
    ]


def recommendation(candidates: Sequence[Dict[str, Any]], xlsx_ok: bool) -> str:
    if not xlsx_ok:
        return "blocked_xlsx_generation_failed"
    if not candidates:
        return "internal_price_baseline_partial_manual_intervention_required"
    if any(row["confidence_level"] in {"high", "medium"} for row in candidates):
        return "internal_price_baseline_ready_for_quota_alignment"
    return "internal_price_baseline_partial_manual_intervention_required"


def build_summary(dashboard: Sequence[Dict[str, Any]], issues: Sequence[Dict[str, Any]], rec: str) -> List[Dict[str, Any]]:
    out = [{"metric_name": row["metric_name"], "metric_value": row["metric_value"], "remark": row["remark"]} for row in dashboard]
    out.append({"metric_name": "issue_count", "metric_value": len(issues), "remark": ""})
    out.append({"metric_name": "recommendation", "metric_value": rec, "remark": ""})
    return out


def write_report(
    path: Path,
    profile: Sequence[Dict[str, Any]],
    all_rows: Sequence[Dict[str, Any]],
    candidates: Sequence[Dict[str, Any]],
    unit_rows: Sequence[Dict[str, Any]],
    issues: Sequence[Dict[str, Any]],
    dashboard: Sequence[Dict[str, Any]],
    rec: str,
) -> None:
    row_types = Counter(row["row_type"] for row in all_rows)
    confidence = Counter(row["confidence_level"] for row in candidates)
    issue_counts = Counter(row["issue_type"] for row in issues)
    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    lines = [
        "# Stage ENTERPRISE-PRICE-BASELINE-LOCK-1 Report",
        "",
        "## 1. Task Scope",
        "",
        "Parse and lock the enterprise internal price workbook as a pending baseline. This stage preserves source rows and derives review candidates only.",
        "",
        "## 2. Source File Profile",
        "",
        f"- source_file: {profile[0]['source_file'] if profile else ''}",
        f"- source_file_hash: {profile[0]['source_file_hash'] if profile else ''}",
        f"- sheet_count: {profile[0]['sheet_count'] if profile else 0}",
        f"- sheets: {';'.join(row['sheet_name'] for row in profile)}",
        "",
        "## 3. Header / Column Detection",
        "",
        f"- detected_header_rows: {';'.join(str(row['sheet_name']) + '=' + str(row['detected_header_row']) for row in profile)}",
        f"- detected_columns: {profile[0]['detected_columns'] if profile else ''}",
        "",
        "## 4. All Rows Review Summary",
        "",
        f"- total_rows: {len(all_rows)}",
        f"- row_type_counts: {json.dumps(dict(row_types), ensure_ascii=False, sort_keys=True)}",
        "",
        "## 5. Price Item Candidate Summary",
        "",
        f"- price_item_candidate_rows: {len(candidates)}",
        f"- confidence_counts: {json.dumps(dict(confidence), ensure_ascii=False, sort_keys=True)}",
        "",
        "## 6. Unit Normalization Result",
        "",
        f"- unit_parsed_count: {metrics.get('unit_parsed_count', 0)}",
        f"- unit_unparsed_count: {metrics.get('unit_unparsed_count', 0)}",
        f"- distinct_raw_unit_count: {len(unit_rows)}",
        "",
        "## 7. Price Field Completeness",
        "",
        f"- rows_with_any_price: {metrics.get('rows_with_any_price', 0)}",
        f"- rows_without_any_price: {metrics.get('rows_without_any_price', 0)}",
        "",
        "## 8. Quality Issues",
        "",
        f"- issue_count: {len(issues)}",
        f"- issue_type_counts: {json.dumps(dict(issue_counts), ensure_ascii=False, sort_keys=True)}",
        "",
        "## 9. Governance Notes",
        "",
        "- Internal price names are candidate descriptions only and must not be treated as final enterprise standard names.",
        "- This baseline can support later internal_price_to_quota_alignment, but missing units, duplicate name+unit rows, and remark-based conditions require manual review.",
        "",
        "## 10. Not Approved / Not Final Statement",
        "",
        "All rows remain pending. This stage does not write databases, approve records, generate internal_price_library, write bill_code or quota_source_code back to candidates, create enterprise quota templates, enter Web development, or parse real bid lists.",
        "",
        "## 11. Next Step Recommendation",
        "",
        rec,
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def build_xlsx(output_dir: Path, node_exe: Path, node_modules: Path) -> None:
    if not node_exe.exists() or not node_modules.exists():
        raise RuntimeError(f"Bundled node runtime unavailable: node={node_exe}, node_modules={node_modules}")
    specs = [
        ("source_profile", "internal_price_source_profile.csv", len(SOURCE_PROFILE_FIELDS)),
        ("all_rows_review", "internal_price_all_rows_review.csv", len(ALL_ROWS_FIELDS)),
        ("price_item_candidate", "internal_price_item_candidate.csv", len(CANDIDATE_FIELDS)),
        ("unit_normalized", "internal_price_unit_normalized.csv", len(UNIT_FIELDS)),
        ("parse_issues", "internal_price_parse_issues.csv", len(ISSUE_FIELDS)),
        ("quality_dashboard", "internal_price_quality_dashboard.csv", len(DASHBOARD_FIELDS)),
        ("summary", "summary_for_xlsx.csv", len(SUMMARY_FIELDS)),
    ]
    builder = r'''
import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = process.argv[2];
const specs = JSON.parse(process.argv[3]);
let workbook = null;
for (const spec of specs) {
  const [sheetName, fileName, colCount] = spec;
  const csvText = await fs.readFile(`${outputDir}/${fileName}`, "utf8");
  if (!workbook) {
    workbook = await Workbook.fromCSV(csvText, { sheetName });
  } else {
    await workbook.fromCSV(csvText, { sheetName });
  }
  const sheet = workbook.worksheets.getItem(sheetName);
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const header = sheet.getRangeByIndexes(0, 0, 1, colCount);
  header.format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  header.format.borders = { preset: "bottom", style: "thin", color: "#9FBAD0" };
  sheet.getRangeByIndexes(0, 0, 1, colCount).format.columnWidth = sheetName === "summary" || sheetName === "quality_dashboard" ? 24 : 18;
}
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);
await workbook.render({ sheetName: "summary", autoCrop: "all", scale: 1, format: "png" });
await workbook.render({ sheetName: "quality_dashboard", autoCrop: "all", scale: 1, format: "png" });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(`${outputDir}/Internal_Price_Baseline_Review.xlsx`);
console.log(`xlsx=${outputDir}/Internal_Price_Baseline_Review.xlsx`);
'''
    with tempfile.TemporaryDirectory(prefix="internal_price_xlsx_") as tmp:
        tmp_path = Path(tmp)
        link = tmp_path / "node_modules"
        try:
            os.symlink(node_modules, link, target_is_directory=True)
        except OSError:
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(node_modules)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        builder_path = tmp_path / "build_internal_price_review.mjs"
        builder_path.write_text(builder, encoding="utf-8")
        subprocess.run([str(node_exe), str(builder_path), str(output_dir), json.dumps(specs)], cwd=tmp_path, check=True)
    sidecar = output_dir / "Internal_Price_Baseline_Review.xlsx.inspect.ndjson"
    if sidecar.exists():
        sidecar.unlink()


def artifact_row_count(path: Path, workbook_total_rows: int) -> str:
    if path.suffix.lower() == ".csv":
        return csv_row_count(path)
    if path.suffix.lower() == ".xlsx":
        return str(workbook_total_rows)
    return ""


def manifest_row(stage_name: str, artifact_name: str, path: Path, source_file: str, project_root: Path, workbook_total_rows: int) -> Dict[str, str]:
    exists = path.exists()
    return {
        "stage_name": stage_name,
        "artifact_name": artifact_name,
        "expected_path": rel(path, project_root),
        "exists": "true" if exists else "false",
        "file_size_bytes": str(path.stat().st_size) if exists else "",
        "row_count": artifact_row_count(path, workbook_total_rows) if exists else "",
        "sha256": sha256_file(path) if exists else "",
        "created_or_modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if exists else "",
        "source_file": source_file,
        "can_regenerate": "true",
        "backup_required": "true",
        "backup_path": rel(project_root / ENGINE_REL / "data" / "private" / "reference_extraction" / "backups" / "runs_backup_after_ENTERPRISE_PRICE_BASELINE_LOCK_1", project_root),
        "status": "generated" if exists else "missing",
        "remark": "pending internal price baseline only; not approved and not enterprise quota table",
    }


def update_manifest(project_root: Path, output_dir: Path, artifacts: Sequence[str], workbook_total_rows: int) -> None:
    manifest_path = project_root / DOCS_REF_REL / "reference_artifact_manifest.csv"
    existing = read_csv(manifest_path)
    source_file = rel(project_root / SOURCE_REL, project_root)
    replacement = {
        (STAGE_NAME, artifact): manifest_row(STAGE_NAME, artifact, output_dir / artifact, source_file, project_root, workbook_total_rows)
        for artifact in artifacts
    }
    filtered = [row for row in existing if (row.get("stage_name"), row.get("artifact_name")) not in replacement]
    filtered.extend(replacement.values())
    write_csv(manifest_path, MANIFEST_FIELDS, filtered)
    write_manifest_md(project_root, filtered)


def write_manifest_md(project_root: Path, rows: Sequence[Dict[str, str]]) -> None:
    latest = [row for row in rows if row.get("stage_name") == STAGE_NAME]
    registered = len(rows)
    existing = sum(1 for row in rows if row.get("exists") == "true")
    lines = [
        "# Reference Artifact Manifest",
        "",
        "## Governance",
        "",
        "- `construction_cost_knowledge_engine/data/private/` is intentionally not tracked by Git.",
        "- Every private artifact must be registered with `row_count` and `sha256` after generation.",
        "- Each completed stage must back up its `runs` output directory after validation.",
        "- Mock SQLite and seed CSV artifacts must not be used as source of truth.",
        "- Internal price baseline outputs are pending review artifacts only and do not approve mappings.",
        "- Internal price baseline outputs must not be used as enterprise quota tables or enterprise price source of truth until reviewed.",
        "",
        "## Current Manifest Summary",
        "",
        f"- registered_artifacts: {registered}",
        f"- existing_artifacts: {existing}",
        f"- missing_artifacts: {registered - existing}",
        "",
        "## Manifest CSV",
        "",
        "`construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv`",
        "",
        "## Latest Enterprise Internal Price Baseline Outputs",
        "",
    ]
    for row in latest:
        lines.append(f"- `{row.get('expected_path')}` ({row.get('row_count') or 'n/a'} rows)")
    lines.extend(
        [
            "",
            "## Backup Requirement",
            "",
            "`construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_ENTERPRISE_PRICE_BASELINE_LOCK_1/`",
            "",
        ]
    )
    (project_root / DOCS_REF_REL / "REFERENCE_ARTIFACT_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_root = args.project_root
    source_path = project_root / SOURCE_REL
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        print("recommendation=blocked_missing_input")
        print(f"missing_input={source_path}")
        return 2

    source_file = rel(source_path, project_root)
    source_hash = sha256_file(source_path)
    file_size = source_path.stat().st_size
    try:
        sheets = extract_xls_with_excel_com(source_path)
    except Exception as exc:
        print("recommendation=blocked_xls_read_failed")
        print(f"xls_error={exc}")
        return 3

    profile, all_rows, _sheet_meta = build_rows(source_file, source_hash, sheets)
    for row in profile:
        row["file_size_bytes"] = file_size
    duplicate_keys = duplicate_keys_for(all_rows)
    candidates = build_candidates(all_rows, duplicate_keys)
    unit_rows = build_unit_rows(all_rows, candidates)
    issues = build_issues(all_rows, candidates, unit_rows, duplicate_keys)
    dashboard = build_dashboard(all_rows, candidates, unit_rows)
    rec = recommendation(candidates, xlsx_ok=True)
    summary = build_summary(dashboard, issues, rec)

    write_csv(output_dir / "internal_price_source_profile.csv", SOURCE_PROFILE_FIELDS, profile)
    write_csv(output_dir / "internal_price_all_rows_review.csv", ALL_ROWS_FIELDS, all_rows)
    write_csv(output_dir / "internal_price_item_candidate.csv", CANDIDATE_FIELDS, candidates)
    write_csv(output_dir / "internal_price_unit_normalized.csv", UNIT_FIELDS, unit_rows)
    write_csv(output_dir / "internal_price_parse_issues.csv", ISSUE_FIELDS, issues)
    write_csv(output_dir / "internal_price_quality_dashboard.csv", DASHBOARD_FIELDS, dashboard)
    write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary)

    try:
        build_xlsx(output_dir, args.node_exe, args.node_modules)
    except Exception as exc:
        write_report(output_dir / "stage_enterprise_price_baseline_lock_report.md", profile, all_rows, candidates, unit_rows, issues, dashboard, "blocked_xlsx_generation_failed")
        print("recommendation=blocked_xlsx_generation_failed")
        print(f"xlsx_error={exc}")
        return 4

    rec = recommendation(candidates, xlsx_ok=True)
    summary = build_summary(dashboard, issues, rec)
    write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary)
    write_report(output_dir / "stage_enterprise_price_baseline_lock_report.md", profile, all_rows, candidates, unit_rows, issues, dashboard, rec)

    artifacts = [
        "internal_price_source_profile.csv",
        "internal_price_all_rows_review.csv",
        "internal_price_item_candidate.csv",
        "internal_price_unit_normalized.csv",
        "internal_price_parse_issues.csv",
        "internal_price_quality_dashboard.csv",
        "Internal_Price_Baseline_Review.xlsx",
        "stage_enterprise_price_baseline_lock_report.md",
    ]
    workbook_total_rows = len(profile) + len(all_rows) + len(candidates) + len(unit_rows) + len(issues) + len(dashboard) + len(summary)
    update_manifest(project_root, output_dir, artifacts, workbook_total_rows)
    (output_dir / "summary_for_xlsx.csv").unlink(missing_ok=True)

    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    print(f"recommendation={rec}")
    print(f"total_rows={len(all_rows)}")
    print(f"price_item_candidate_rows={len(candidates)}")
    print(f"unit_parsed_count={metrics.get('unit_parsed_count', 0)}")
    print(f"unit_unparsed_count={metrics.get('unit_unparsed_count', 0)}")
    print(f"rows_with_any_price={metrics.get('rows_with_any_price', 0)}")
    print(f"high_confidence_price_rows={metrics.get('high_confidence_price_rows', 0)}")
    print(f"medium_confidence_price_rows={metrics.get('medium_confidence_price_rows', 0)}")
    print(f"low_confidence_price_rows={metrics.get('low_confidence_price_rows', 0)}")
    print(f"issue_count={len(issues)}")
    print("approved_count=0")
    print(f"non_pending_review_status_count={metrics.get('non_pending_review_status_count', 0)}")
    print(f"xlsx_exists={(output_dir / 'Internal_Price_Baseline_Review.xlsx').exists()}")
    print(f"output_dir={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
