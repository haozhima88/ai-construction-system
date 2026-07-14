#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage MAP-A111-QA1 manual QA pack generation.

This script samples pending A.1.1 quota-to-bill mapping candidates for human
review. It does not modify source mapping candidates, write databases, create
approved records, generate internal_price_library, or write bill_code values
back into quota references.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


PROJECT_ROOT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE = PROJECT_ROOT / "construction_cost_knowledge_engine"
RUN_DIR = ENGINE / "data" / "private" / "reference_extraction" / "runs"
INPUT_DIR = RUN_DIR / "MAP_A111_quota_to_bill_trial"
OUTPUT_DIR = RUN_DIR / "MAP_A111_manual_QA_pack"
DOCS_REF = ENGINE / "docs" / "reference_extraction"
BACKUP_PATH = ENGINE / "data" / "private" / "reference_extraction" / "backups" / "runs_backup_after_MAP_A111_QA1"

MAPPING_PATH = INPUT_DIR / "quota_to_bill_mapping_A111_candidate.csv"
ISSUE_PATH = INPUT_DIR / "quota_to_bill_mapping_A111_issues.csv"
QUOTA_SNAPSHOT_PATH = INPUT_DIR / "quota_reference_A111_input_snapshot.csv"
BILL_SNAPSHOT_PATH = INPUT_DIR / "bill_reference_appendix_A_input_snapshot.csv"

SAMPLE_PATH = OUTPUT_DIR / "manual_qa_sample_A111.csv"
CHECKLIST_PATH = OUTPUT_DIR / "manual_qa_checklist_A111.md"
SUMMARY_PATH = OUTPUT_DIR / "manual_qa_summary_A111.md"
MANIFEST_CSV = DOCS_REF / "reference_artifact_manifest.csv"
MANIFEST_MD = DOCS_REF / "REFERENCE_ARTIFACT_MANIFEST.md"

QA_FIELDS = [
    "qa_sample_id",
    "qa_category",
    "qa_reason",
    "quota_source_code",
    "quota_raw_name",
    "quota_unit",
    "bill_code_9",
    "bill_name",
    "bill_unit",
    "bill_project_feature_raw",
    "bill_quantity_calculation_rule",
    "bill_work_content_raw",
    "mapping_type",
    "mapping_confidence",
    "mapping_basis",
    "issue_types",
    "suggested_human_questions",
    "human_decision",
    "human_decision_level",
    "human_comment",
]

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

SAMPLE_RULES = [
    ("high_confidence_direct_candidate", 8),
    ("feature_required", 8),
    ("one_quota_to_multi_bill", 8),
    ("transport_item_uncertain", 8),
    ("construction_method_only", 6),
    ("no_direct_bill_item", None),
    ("supplemental_quota_code", None),
]

QUESTION_LIBRARY = {
    "high_confidence_direct_candidate": "抽查工程对象、单位、项目特征和工作内容是否真的一致；确认是否只是表面高置信。",
    "feature_required": "需要人工判断哪些项目特征才能决定清单项；不能直接确认。",
    "one_quota_to_multi_bill": "判断一个定额子目是否可能拆到多个清单项，或需要企业模板承接。",
    "transport_item_uncertain": "运输类定额是否只是工作内容，是否不应直接映射为清单项目本体。",
    "construction_method_only": "施工方法类子目是否只是清单工作内容或措施，不应强行映射。",
    "no_direct_bill_item": "没有直接清单项时，不得强行挂接附录 A；确认是否保留为未映射。",
    "supplemental_quota_code": "补充编号必须单独核验来源和适用场景，不能混同普通编号。",
}


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def row_count(path: Path) -> str:
    if path.exists() and path.suffix.lower() == ".csv":
        return str(len(read_csv(path)))
    return ""


def natural_quota_key(code: str) -> tuple[int, int]:
    match = re.fullmatch(r"A1-1-(\d+)(?:-(\d+))?", code or "")
    if not match:
        return (10_000, 10_000)
    return (int(match.group(1)), int(match.group(2) or 0))


def mapping_sort_key(row: Dict[str, str]) -> tuple[Any, ...]:
    try:
        confidence_key = -float(row.get("mapping_confidence") or 0)
    except ValueError:
        confidence_key = 0
    return (
        natural_quota_key(row.get("quota_source_code", "")),
        confidence_key,
        row.get("bill_code_9", ""),
        row.get("mapping_id", ""),
    )


def issue_index(issues: Sequence[Dict[str, str]]) -> tuple[dict[str, set[str]], dict[str, list[Dict[str, str]]]]:
    issue_types_by_code: dict[str, set[str]] = defaultdict(set)
    issues_by_code: dict[str, list[Dict[str, str]]] = defaultdict(list)
    for issue in issues:
        code = issue.get("quota_source_code", "")
        issue_type = issue.get("issue_type", "")
        if code and issue_type:
            issue_types_by_code[code].add(issue_type)
            issues_by_code[code].append(issue)
    return issue_types_by_code, issues_by_code


def row_matches_category(row: Dict[str, str], category: str, issue_types: set[str]) -> bool:
    mapping_type = row.get("mapping_type", "")
    confidence = float(row.get("mapping_confidence") or 0)
    if category == "high_confidence_direct_candidate":
        return mapping_type == "direct_candidate" and confidence >= 0.90
    if category == "feature_required":
        return mapping_type == "feature_required" or "feature_required" in issue_types
    if category == "one_quota_to_multi_bill":
        return mapping_type == "one_quota_to_multi_bill"
    if category == "transport_item_uncertain":
        return "transport_item_uncertain" in issue_types
    if category == "construction_method_only":
        return "construction_method_only" in issue_types
    if category == "no_direct_bill_item":
        return mapping_type == "no_direct_bill_item" or "no_candidate_bill_item" in issue_types
    if category == "supplemental_quota_code":
        return "supplemental_quota_code" in issue_types
    return False


def add_sample(
    selected: dict[str, dict[str, Any]],
    row: Dict[str, str],
    category: str,
    reason: str,
    issue_types: Iterable[str],
) -> None:
    key = row.get("mapping_id") or "|".join(
        [row.get("quota_source_code", ""), row.get("bill_code_9", ""), row.get("mapping_type", "")]
    )
    if key not in selected:
        selected[key] = {
            **row,
            "_categories": [],
            "_reasons": [],
            "_issue_types": set(issue_types),
        }
    selected[key]["_issue_types"].update(issue_types)
    if category not in selected[key]["_categories"]:
        selected[key]["_categories"].append(category)
    if reason and reason not in selected[key]["_reasons"]:
        selected[key]["_reasons"].append(reason)


def build_samples(mappings: Sequence[Dict[str, str]], issues: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    issue_types_by_code, _ = issue_index(issues)
    selected: dict[str, dict[str, Any]] = {}
    sorted_rows = sorted(mappings, key=mapping_sort_key)

    for category, limit in SAMPLE_RULES:
        matches = [
            row
            for row in sorted_rows
            if row_matches_category(row, category, issue_types_by_code.get(row.get("quota_source_code", ""), set()))
        ]
        if category == "high_confidence_direct_candidate":
            matches = sorted(matches, key=lambda row: (-float(row.get("mapping_confidence") or 0), natural_quota_key(row.get("quota_source_code", "")), row.get("bill_code_9", "")))
        if limit is not None:
            matches = matches[:limit]
        for row in matches:
            issue_types = issue_types_by_code.get(row.get("quota_source_code", ""), set())
            add_sample(selected, row, category, QUESTION_LIBRARY[category], issue_types)

    output: List[Dict[str, Any]] = []
    for idx, row in enumerate(sorted(selected.values(), key=mapping_sort_key), start=1):
        categories = row["_categories"]
        reasons = row["_reasons"]
        issue_types = sorted(row["_issue_types"])
        questions = [QUESTION_LIBRARY[category] for category in categories if category in QUESTION_LIBRARY]
        output.append(
            {
                "qa_sample_id": f"MAP_A111_QA_{idx:03d}",
                "qa_category": ";".join(categories),
                "qa_reason": "; ".join(reasons),
                "quota_source_code": row.get("quota_source_code", ""),
                "quota_raw_name": row.get("quota_raw_name", ""),
                "quota_unit": row.get("quota_unit", ""),
                "bill_code_9": row.get("bill_code_9", ""),
                "bill_name": row.get("bill_name", ""),
                "bill_unit": row.get("bill_unit", ""),
                "bill_project_feature_raw": row.get("bill_project_feature_raw", ""),
                "bill_quantity_calculation_rule": row.get("bill_quantity_calculation_rule", ""),
                "bill_work_content_raw": row.get("bill_work_content_raw", ""),
                "mapping_type": row.get("mapping_type", ""),
                "mapping_confidence": row.get("mapping_confidence", ""),
                "mapping_basis": row.get("mapping_basis", ""),
                "issue_types": ";".join(issue_types),
                "suggested_human_questions": "; ".join(dict.fromkeys(questions)),
                "human_decision": "",
                "human_decision_level": "",
                "human_comment": "",
            }
        )
    return output


def category_counts(samples: Sequence[Dict[str, Any]]) -> Counter:
    counts: Counter = Counter()
    for sample in samples:
        for category in str(sample.get("qa_category", "")).split(";"):
            if category:
                counts[category] += 1
    return counts


def write_checklist() -> None:
    lines = [
        "# MAP-A111-QA1 Manual QA Checklist",
        "",
        "## 人工判断问题",
        "",
        "1. 省级定额子目的工程对象是什么？",
        "2. 国标清单项的工程对象是否一致？",
        "3. 是否需要区分单独土方、基坑、沟槽？",
        "4. 定额子目是清单项目本体，还是清单项目下的工作内容？",
        "5. 单位是否兼容？",
        "6. 是否可以进入企业组价模板草案？",
        "7. 是否存在强行映射？",
        "8. 是否需要成本部最终判断？",
        "",
        "## 填写要求",
        "",
        "- `human_decision`、`human_decision_level`、`human_comment` 由人工填写。",
        "- 不允许在本阶段写入 approved。",
        "- 不允许将 bill_code 回写到定额候选表。",
        "- 对运输类、施工方法类、补充编号、no_direct_bill_item 必须保留人工判断痕迹。",
        "",
        "## human_decision_level 可选值",
        "",
        "- `P0_not_mapping`",
        "- `P1_work_content_only`",
        "- `P2_candidate_feature_required`",
        "- `P3_enterprise_template_candidate`",
        "- `P4_confirmed_by_cost_department`",
    ]
    CHECKLIST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(mappings: Sequence[Dict[str, str]], issues: Sequence[Dict[str, str]], samples: Sequence[Dict[str, Any]]) -> None:
    counts = category_counts(samples)
    issue_counts = Counter(issue.get("issue_type", "") for issue in issues)
    lines = [
        "# Stage MAP-A111-QA1 Manual QA Pack",
        "",
        "## 1. Task Scope",
        "",
        "Generate an A.1.1 quota-to-bill mapping manual QA pack from pending mapping candidates. This pack is for human review only and does not approve, delete, rewrite, or write back any mapping.",
        "",
        "## 2. Input Files",
        "",
        f"- `{rel(MAPPING_PATH)}`",
        f"- `{rel(ISSUE_PATH)}`",
        f"- `{rel(QUOTA_SNAPSHOT_PATH)}`",
        f"- `{rel(BILL_SNAPSHOT_PATH)}`",
        "",
        "## 3. Sampling Strategy",
        "",
        "- high-confidence direct_candidate: 8 rows",
        "- feature_required: 8 rows",
        "- one_quota_to_multi_bill: 8 rows",
        "- transport_item_uncertain: 8 rows",
        "- construction_method_only: 6 rows",
        "- no_direct_bill_item: all matched rows",
        "- supplemental_quota_code: all matched rows",
        "- If one candidate hits multiple categories, it is kept once and reasons are merged.",
        "",
        "## 4. Sample Count by Category",
        "",
    ]
    for category, _ in SAMPLE_RULES:
        lines.append(f"- {category}: {counts.get(category, 0)}")
    lines.extend(
        [
            f"- unique_sample_rows: {len(samples)}",
            "",
            "## 5. Key Risk Groups",
            "",
            f"- transport_item_uncertain issues: {issue_counts.get('transport_item_uncertain', 0)}",
            f"- construction_method_only issues: {issue_counts.get('construction_method_only', 0)}",
            f"- no_candidate_bill_item issues: {issue_counts.get('no_candidate_bill_item', 0)}",
            f"- supplemental_quota_code issues: {issue_counts.get('supplemental_quota_code', 0)}",
            f"- feature_required issues: {issue_counts.get('feature_required', 0)}",
            "",
            "## 6. Suggested Acceptance Criteria",
            "",
            "- high-confidence direct_candidate 抽查正确率 >= 90%",
            "- 运输类不得被错误认定为无需人工判断",
            "- no_direct_bill_item 不应强行映射到附录 A",
            "- supplemental quota codes 必须被识别并单独标注",
            "- 所有结果仍保持 pending",
            "- 不得生成 approved",
            "",
            "## 7. Human Decision Levels",
            "",
            "- `P0_not_mapping`: 不构成映射",
            "- `P1_work_content_only`: 仅属于清单工作内容",
            "- `P2_candidate_feature_required`: 可作为候选，但必须补项目特征或适用条件",
            "- `P3_enterprise_template_candidate`: 可进入企业组价模板草案",
            "- `P4_confirmed_by_cost_department`: 成本部最终确认",
            "",
            "## 8. Next Step Recommendation",
            "",
            "Proceed to human manual QA using `manual_qa_sample_A111.csv`. Do not approve or write back mappings until cost department review decisions are recorded.",
            "",
            f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
            f"Total mapping candidates in source: {len(mappings)}",
            f"Total mapping issues in source: {len(issues)}",
        ]
    )
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def manifest_row(stage_name: str, artifact_name: str, path: Path, source_file: str) -> Dict[str, str]:
    exists = path.exists()
    return {
        "stage_name": stage_name,
        "artifact_name": artifact_name,
        "expected_path": rel(path),
        "exists": str(exists).lower(),
        "file_size_bytes": str(path.stat().st_size) if exists else "",
        "row_count": row_count(path),
        "sha256": sha256(path) if exists else "",
        "created_or_modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if exists else "",
        "source_file": source_file,
        "can_regenerate": "true",
        "backup_required": "true",
        "backup_path": rel(BACKUP_PATH),
        "status": "manual_qa_pack_generated" if exists else "missing",
        "remark": "manual QA artifact; pending human review; no approved output",
    }


def update_manifest() -> None:
    rows = read_csv(MANIFEST_CSV) if MANIFEST_CSV.exists() else []
    new_rows = [
        manifest_row("MAP_A111_manual_QA_pack", "manual_qa_sample_A111.csv", SAMPLE_PATH, MAPPING_PATH.name),
        manifest_row("MAP_A111_manual_QA_pack", "manual_qa_checklist_A111.md", CHECKLIST_PATH, MAPPING_PATH.name),
        manifest_row("MAP_A111_manual_QA_pack", "manual_qa_summary_A111.md", SUMMARY_PATH, MAPPING_PATH.name),
    ]
    by_key = {(row.get("stage_name", ""), row.get("artifact_name", "")): row for row in rows}
    for row in new_rows:
        by_key[(row["stage_name"], row["artifact_name"])] = row
    ordered = list(by_key.values())
    write_csv(MANIFEST_CSV, MANIFEST_FIELDS, ordered)
    existing = [row for row in ordered if row.get("exists") == "true"]
    lines = [
        "# Reference Artifact Manifest",
        "",
        "## Governance",
        "",
        "- `construction_cost_knowledge_engine/data/private/` is intentionally not tracked by Git.",
        "- Every private artifact must be registered with `row_count` and `sha256` after generation.",
        "- Each completed stage must back up its `runs` output directory after validation.",
        "- Mock SQLite and seed CSV artifacts must not be used as source of truth.",
        "- MAP-A111-QA1 outputs are manual QA artifacts only; they do not approve mappings.",
        "",
        "## Current Manifest Summary",
        "",
        f"- registered_artifacts: {len(ordered)}",
        f"- existing_artifacts: {len(existing)}",
        f"- missing_artifacts: {len(ordered) - len(existing)}",
        "",
        "## Manifest CSV",
        "",
        "`construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv`",
        "",
        "## Latest Manual QA Pack",
        "",
        "`construction_cost_knowledge_engine/data/private/reference_extraction/runs/MAP_A111_manual_QA_pack/`",
        "",
        "## Backup Requirement",
        "",
        "`construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_MAP_A111_QA1/`",
    ]
    MANIFEST_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    mappings = read_csv(MAPPING_PATH)
    issues = read_csv(ISSUE_PATH)
    samples = build_samples(mappings, issues)
    write_csv(SAMPLE_PATH, QA_FIELDS, samples)
    write_checklist()
    write_summary(mappings, issues, samples)
    update_manifest()
    counts = category_counts(samples)
    print(f"mapping_rows={len(mappings)}")
    print(f"issue_rows={len(issues)}")
    print(f"manual_qa_sample_rows={len(samples)}")
    print("sample_category_counts=" + dict(counts).__repr__())
    print(f"output_dir={OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
