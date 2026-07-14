from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from .common import file_sha256, read_csv


EXPECTED_COUNTS = {"bill": 472, "quota": 3700, "resource": 24981, "edge": 1882}


def csv_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def validate_rc1_manifest(project_root: Path, manifest_path: Path) -> dict[str, object]:
    manifest = read_csv(manifest_path)
    file_rows = [row for row in manifest if not row["artifact_path"].startswith("manifest://")]
    failures: list[str] = []
    for row in file_rows:
        path = project_root / Path(row["artifact_path"])
        if not path.is_file():
            failures.append(f"missing:{row['artifact_path']}")
        elif file_sha256(path) != row["sha256"]:
            failures.append(f"hash:{row['artifact_path']}")

    groups: dict[str, str] = {}
    for group in sorted({row["artifact_group"] for row in manifest}):
        details = sorted(
            (row for row in file_rows if row["artifact_group"] == group),
            key=lambda row: row["artifact_path"],
        )
        digest = hashlib.sha256()
        for row in details:
            digest.update(row["artifact_path"].encode("utf-8"))
            digest.update(b"\0")
            digest.update(row["sha256"].encode("ascii"))
            digest.update(b"\n")
        actual = digest.hexdigest()
        expected = next(
            row["sha256"] for row in manifest
            if row["artifact_group"] == group and row["artifact_path"].startswith("manifest://")
        )
        groups[group] = actual
        if actual != expected:
            failures.append(f"aggregate:{group}")

    engine = project_root / "construction_cost_knowledge_engine"
    runs = engine / "data/private/reference_extraction/runs"
    counts = {
        "bill": csv_count(runs / "GB50854_2024_stageB_docx_full/bill_item_reference_all_candidate.csv"),
        "quota": csv_count(runs / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1/gd_building_quota_items.csv"),
        "resource": csv_count(runs / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1/gd_building_resource_components.csv"),
        "edge": csv_count(runs / "MAP_GB50854_TO_GD2018_BUILDING_A_FULL_1/building_bill_to_quota_edges.csv"),
    }
    for name, expected in EXPECTED_COUNTS.items():
        if counts[name] != expected:
            failures.append(f"count:{name}:{counts[name]}!={expected}")
    return {"ok": not failures, "failures": failures, "groups": groups, "counts": counts, "manifest_rows": len(manifest)}

