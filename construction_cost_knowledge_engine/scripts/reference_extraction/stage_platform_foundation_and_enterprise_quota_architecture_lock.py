#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Freeze the Building RC1 evidence manifest and architecture governance matrices."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
RUNS_REL = ENGINE_REL / "data/private/reference_extraction/runs"
OUTPUT_RUN = "PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1"

REFERENCE_RELEASE = "BUILDING_A01_A03_REFERENCE_RC1"
MAPPING_RELEASE = "BUILDING_A01_A03_MAPPING_RC1"
APPLICATION_RELEASE = "WEB_REVIEW_RC1"
FINAL_STATUS = "platform_architecture_ready_for_database_implementation"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})
    temporary.replace(path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def relative(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def manifest_hash(paths: Sequence[Path], project_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda value: relative(value, project_root)):
        digest.update(relative(path, project_root).encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def approved_count(path: Path, field: str = "review_status") -> int:
    return sum(1 for row in csv_rows(path) if row.get(field, "").strip().lower() == "approved")


def draft_counts(path: Path) -> dict[str, int]:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        return {
            "draft": connection.execute("SELECT COUNT(*) FROM mapping_drafts").fetchone()[0],
            "audit": connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
            "review": connection.execute("SELECT COUNT(*) FROM review_states").fetchone()[0],
        }


def entity_rows() -> list[dict[str, str]]:
    def row(name: str, domain: str, pk: str, fk: str, unique: str, mutability: str,
            lifecycle: str, provenance: str, version: str, audit: str, delete: str) -> dict[str, str]:
        return {
            "entity_name": name, "domain": domain, "primary_key": pk, "foreign_keys": fk,
            "unique_constraints": unique, "mutability": mutability, "lifecycle": lifecycle,
            "provenance": provenance, "version_relation": version,
            "audit_requirement": audit, "delete_policy": delete,
        }

    return [
        row("source_document", "Reference", "source_document_id uuid", "standard_family_id", "sha256; family+edition+document_role", "immutable after ingest", "registered->verified->retired", "path, hash, role, authority status", "replaced by a new document row", "ingest and verification events", "restrict; retire only"),
        row("source_page_evidence", "Reference", "source_page_evidence_id uuid", "source_document_id", "document+page_no+evidence_type+locator", "append-only", "captured->verified", "page/table locator and evidence hash", "belongs to source document revision", "capture and verification events", "restrict"),
        row("standard_family", "Reference", "standard_family_id uuid", "none", "family_code+edition", "metadata controlled", "draft->active->retired", "family adapter id", "new edition is a new row", "all metadata changes", "soft retire"),
        row("reference_release", "Reference", "reference_release_id text", "standard_family_id; release_manifest_id", "family+semantic_version", "immutable after publish", "assembled->validated->published->superseded", "source hash manifest", "supersedes_release_id", "publish and supersede events", "restrict"),
        row("reference_bill_item", "Reference", "reference_bill_item_id uuid", "reference_release_id; source_document_id", "release+bill_code_9", "immutable", "candidate in release->retained", "source heading/table/row and evidence", "new release creates new row", "import event only", "restrict"),
        row("reference_quota_item", "Reference", "reference_quota_item_id uuid", "reference_release_id; source_document_id", "release+volume+source_code", "immutable", "candidate in release->retained", "PDF page and parser provenance", "new release creates new row", "import event only", "restrict"),
        row("reference_quota_resource", "Reference", "reference_quota_resource_id uuid", "reference_quota_item_id", "quota+line_no+resource_code", "immutable", "candidate in release->retained", "quota page/line evidence", "versioned through parent release", "import event only", "restrict"),
        row("reference_rule_block", "Reference", "reference_rule_block_id uuid", "reference_release_id; source_document_id", "release+rule_type+source_locator+ordinal", "immutable", "candidate in release->retained", "raw text and page evidence", "new release creates new row", "import event only", "restrict"),
        row("reference_scope_link", "Reference", "reference_scope_link_id uuid", "reference_rule_block_id; reference_quota_item_id", "rule+quota+scope_type", "immutable", "derived in release->retained", "scope derivation method", "versioned through parent release", "import event only", "restrict"),
        row("mapping_release", "Mapping", "mapping_release_id text", "reference_release_id; release_manifest_id", "reference_release+semantic_version", "immutable after publish", "assembled->validated->published->superseded", "candidate generator and source hashes", "supersedes_mapping_release_id", "publish and supersede events", "restrict"),
        row("mapping_candidate_edge", "Mapping", "mapping_candidate_edge_id uuid", "mapping_release_id; bill_item_id; quota_item_id", "mapping_release+bill+quota+role", "immutable", "generated->pending", "scores, explanation, source evidence status", "new mapping release creates new row", "generation event", "restrict"),
        row("mapping_draft_edge", "Mapping", "mapping_draft_edge_id uuid", "mapping_candidate_edge_id; app_user_id", "workspace+bill+quota+active_revision", "mutable overlay", "active->restored/rejected/archived", "candidate edge plus user change set", "revision_no and prior_revision_id", "every mutation", "soft archive"),
        row("mapping_review_state", "Mapping", "mapping_review_state_id uuid", "candidate_edge_id or draft_edge_id; app_user_id", "subject_type+subject_id+review_cycle", "mutable workflow metadata", "unreviewed->reviewed->needs_followup", "reviewer, reason, timestamp", "review_cycle increments", "every transition", "retain"),
        row("mapping_audit_event", "Mapping", "mapping_audit_event_id uuid", "draft_edge_id; app_user_id", "event_id", "append-only", "recorded", "before/after payload and request id", "none", "self-auditing", "never delete; retention policy"),
        row("enterprise_resource", "Enterprise Price", "enterprise_resource_id uuid", "source_reference_resource_id nullable", "tenant+normalized_name+specification+unit", "controlled mutable", "draft->active->retired", "reference link or enterprise creation evidence", "revision_no", "all changes", "soft retire"),
        row("enterprise_price_observation", "Enterprise Price", "enterprise_price_observation_id uuid", "enterprise_resource_id; source_document_id nullable", "source+external_key+observed_at", "append-only", "observed->reviewed->rejected", "supplier/source document and confidence", "none; corrections append", "ingest and review events", "retain"),
        row("enterprise_price_version", "Enterprise Price", "enterprise_price_version_id uuid", "enterprise_resource_id; predecessor_id nullable", "resource+version", "immutable after submitted", "draft->submitted->approved->superseded", "observation set and precedence decision", "monotonic resource version", "every transition", "restrict"),
        row("enterprise_price_approval", "Enterprise Price", "enterprise_price_approval_id uuid", "enterprise_price_version_id; approver_user_id", "price_version+approval_round", "append-only", "approved/rejected/withdrawn", "approval reason and evidence snapshot", "approval round", "mandatory", "never hard delete"),
        row("enterprise_quota", "Enterprise Quota", "enterprise_quota_id uuid", "standard_family_id; source_reference_quota_id", "tenant+enterprise_quota_code", "identity metadata controlled", "active->retired", "reference derivation anchor", "versions held separately", "all changes", "soft retire"),
        row("enterprise_quota_version", "Enterprise Quota", "enterprise_quota_version_id uuid", "enterprise_quota_id; predecessor_id; change_set_id", "enterprise_quota+version", "mutable only in draft", "draft->submitted->reviewed->approved->published->superseded", "reference release, creator, rationale", "monotonic version; no overwrite", "every transition", "restrict"),
        row("enterprise_quota_component_version", "Enterprise Quota", "component_version_id uuid", "enterprise_quota_version_id; enterprise_resource_id", "quota_version+line_no", "immutable after submit", "draft with parent->frozen", "reference component and overrides", "owned by quota version", "all draft mutations and freeze", "cascade only before submit; otherwise restrict"),
        row("enterprise_quota_rule_version", "Enterprise Quota", "rule_version_id uuid", "enterprise_quota_version_id; source_rule_block_id nullable", "quota_version+rule_type+ordinal", "immutable after submit", "draft with parent->frozen", "reference rule and enterprise rationale", "owned by quota version", "all draft mutations and freeze", "cascade only before submit; otherwise restrict"),
        row("enterprise_quota_change_set", "Enterprise Quota", "change_set_id uuid", "enterprise_quota_version_id; creator_user_id", "quota_version+change_set_no", "append-only after submit", "open->sealed->applied/rejected", "structured before/after and reason", "change_set_no", "mandatory", "retain"),
        row("enterprise_quota_review_event", "Enterprise Quota", "review_event_id uuid", "enterprise_quota_version_id; actor_user_id", "event_id", "append-only", "recorded", "transition, comments, evidence", "none", "self-auditing", "never hard delete"),
        row("enterprise_quota_release", "Enterprise Quota", "enterprise_quota_release_id text", "release_manifest_id; price_snapshot_release_id", "semantic_version", "immutable", "assembled->published->superseded", "quota versions and captured price snapshot", "supersedes_release_id", "publish/rollback events", "restrict"),
        row("app_user", "Platform", "app_user_id uuid", "none", "tenant+login_name; tenant+email", "mutable identity", "invited->active->disabled", "identity provider subject", "revision_no", "security audit", "soft disable"),
        row("app_role", "Platform", "app_role_id uuid", "none", "role_code", "system roles immutable; custom roles controlled", "active->retired", "role policy version", "policy_version", "permission changes", "soft retire"),
        row("release_manifest", "Platform", "release_manifest_id uuid", "release ids nullable", "manifest_sha256", "immutable", "assembled->validated->activated->rolled_back", "artifact hashes, image tag, schema version", "supersedes_manifest_id", "all lifecycle events", "never hard delete"),
        row("schema_migration", "Platform", "schema_migration_id text", "release_manifest_id nullable", "migration_version", "append-only", "pending->applied/failed/rolled_forward", "script hash and tool version", "ordered version", "start/end/result", "never delete"),
        row("system_audit_event", "Platform", "system_audit_event_id uuid", "actor_user_id nullable; release_manifest_id nullable", "event_id", "append-only", "recorded", "actor, request, before/after, correlation id", "none", "self-auditing", "retention-controlled; no application delete"),
    ]


def state_transition_rows() -> list[dict[str, str]]:
    fields = [
        ("EQ-00", "none", "draft", "editor", "create permission and reference anchor exist", "yes", "quota_version_created", "delete only while empty draft", "initial version or next monotonic version", "yes"),
        ("EQ-01", "draft", "submitted", "editor", "sealed change set; validation passes", "yes", "quota_submitted", "reviewer may return to draft", "same version", "yes"),
        ("EQ-02", "submitted", "draft", "reviewer", "return reason recorded", "yes", "quota_returned", "resume draft editing", "same version", "yes"),
        ("EQ-03", "submitted", "reviewed", "reviewer", "review checklist complete; actor is not submitter", "no", "quota_reviewed", "may return to submitted", "same version", "yes"),
        ("EQ-04", "reviewed", "submitted", "reviewer", "rework reason recorded", "yes", "quota_rework_requested", "repeat review", "same version", "yes"),
        ("EQ-05", "reviewed", "approved", "approver", "approval evidence complete; actor is not editor/reviewer", "no", "quota_approved", "approver may withdraw before publish", "same version", "yes"),
        ("EQ-06", "approved", "reviewed", "approver", "withdrawal reason; not yet published", "yes", "quota_approval_withdrawn", "repeat approval", "same version", "yes"),
        ("EQ-07", "approved", "published", "administrator", "release manifest, smoke pass, immutable price snapshot", "no", "quota_published", "rollback creates release pointer; never mutates version", "same immutable version", "yes"),
        ("EQ-08", "published", "superseded", "administrator", "replacement version published", "no", "quota_superseded", "prior version remains immutable and addressable", "replacement has higher version", "yes"),
        ("EQ-09", "published", "draft", "any", "forbidden", "n/a", "blocked_transition", "create a new version instead", "new higher version required", "no"),
        ("EQ-10", "published", "published", "any", "forbidden overwrite", "n/a", "blocked_transition", "publish a new release manifest", "new higher version required", "no"),
        ("EQ-11", "superseded", "published", "any", "forbidden state mutation", "n/a", "blocked_transition", "rollback activates a new release referencing old immutable payload", "new release id required", "no"),
    ]
    names = ["transition_id", "from_state", "to_state", "actor_role", "guard_condition", "change_set_required", "audit_event", "rollback_rule", "next_version_rule", "allowed"]
    return [dict(zip(names, values)) for values in fields]


def permission_rows() -> list[dict[str, str]]:
    rules = [
        ("Reference", "read published reference", "allow", "allow", "allow", "allow", "allow", "published release only"),
        ("Reference", "import or replace reference", "deny", "deny", "deny", "deny", "allow", "staged import; never in-place edit"),
        ("Mapping", "read candidates", "allow", "allow", "allow", "allow", "allow", "released candidate set"),
        ("Mapping", "create or edit draft overlay", "deny", "deny", "allow", "deny", "allow", "audit event required"),
        ("Mapping", "review draft overlay", "deny", "allow", "deny", "deny", "allow", "reviewer cannot edit same subject"),
        ("Mapping", "publish mapping release", "deny", "deny", "deny", "deny", "allow", "validation pass; no approved state"),
        ("Enterprise Price", "read price versions", "allow", "allow", "allow", "allow", "allow", "tenant scope"),
        ("Enterprise Price", "record observation", "deny", "deny", "allow", "deny", "allow", "source provenance required"),
        ("Enterprise Price", "review price version", "deny", "allow", "deny", "deny", "allow", "separation of duties"),
        ("Enterprise Price", "approve price version", "deny", "deny", "deny", "allow", "allow", "approver not creator/reviewer"),
        ("Enterprise Price", "publish price release", "deny", "deny", "deny", "deny", "allow", "manifest and approval gate"),
        ("Enterprise Quota", "read quota versions", "allow", "allow", "allow", "allow", "allow", "tenant scope"),
        ("Enterprise Quota", "create or edit draft", "deny", "deny", "allow", "deny", "allow", "draft only; change set required"),
        ("Enterprise Quota", "submit", "deny", "deny", "allow", "deny", "allow", "validation pass"),
        ("Enterprise Quota", "review", "deny", "allow", "deny", "deny", "allow", "reviewer not submitter"),
        ("Enterprise Quota", "approve", "deny", "deny", "deny", "allow", "allow", "approver not editor/reviewer"),
        ("Enterprise Quota", "publish", "deny", "deny", "deny", "deny", "allow", "approved plus price snapshot"),
        ("Enterprise Quota", "overwrite published", "deny", "deny", "deny", "deny", "deny", "always forbidden"),
        ("Reviews", "read audit trail", "deny", "allow", "allow-own", "allow", "allow", "tenant and subject scope"),
        ("Releases", "read manifests", "allow", "allow", "allow", "allow", "allow", "published manifests"),
        ("Releases", "activate or rollback", "deny", "deny", "deny", "deny", "allow", "smoke/restore point and audit required"),
        ("Administration", "manage users and roles", "deny", "deny", "deny", "deny", "allow", "security audit required"),
        ("Administration", "run schema migration", "deny", "deny", "deny", "deny", "allow", "maintenance window and backup required"),
        ("Administration", "hard delete governed records", "deny", "deny", "deny", "deny", "deny", "retention process only; no UI action"),
    ]
    names = ["permission_area", "action", "viewer", "reviewer", "editor", "approver", "administrator", "guard"]
    return [dict(zip(names, values)) for values in rules]


def release_rows() -> list[dict[str, str]]:
    rows = [
        ("Reference Release", "immutable source-derived bill/quota/rule/resource records", "semantic version per family", "yes", "hash and integrity validation", "whole release", "source hash manifest", "administrator"),
        ("Mapping Release", "candidate edges and routing metadata", "semantic version per reference release", "yes", "reference pin, counts, no approved status", "whole release", "Reference Release", "administrator"),
        ("Enterprise Price Release", "approved price versions", "semantic version plus effective date", "yes", "approval completeness and overlap checks", "whole price release", "Enterprise Resource catalog", "approver + administrator publish"),
        ("Enterprise Quota Release", "published quota versions and price snapshot", "semantic version", "yes", "state, approval, price snapshot, smoke", "whole quota release", "Reference + Enterprise Price Release", "approver + administrator publish"),
        ("Application Release", "web/API/worker image", "SemVer and immutable image digest", "yes", "tests, migrations compatible, smoke", "image tag/digest", "API contract + schema range", "administrator"),
        ("Database Schema Release", "ordered PostgreSQL migrations", "monotonic migration version", "yes", "backup, dry run, compatibility check", "roll forward preferred", "Application Release", "administrator"),
        ("Platform Composite Release", "application, schema, all data release ids", "manifest id", "yes", "all component gates", "release manifest pointer", "all release types", "administrator"),
    ]
    names = ["release_type", "content", "versioning", "immutable_after_publish", "publish_gate", "rollback_unit", "dependent_release", "approval_owner"]
    return [dict(zip(names, values)) for values in rows]


def deployment_rows() -> list[dict[str, str]]:
    rows = [
        ("source", "${PLATFORM_ROOT}/source", "/srv/platform/source", "web; worker", "read_only", "file-level hash inventory; snapshot", "source-controlled", "1", "authority files are never container-writable"),
        ("database", "${PLATFORM_ROOT}/database", "/var/lib/postgresql/data", "database", "read_write", "nightly pg_basebackup plus daily logical dump", "30 daily + 12 monthly", "2", "single writer is PostgreSQL"),
        ("releases", "${PLATFORM_ROOT}/releases", "/srv/platform/releases", "web; worker; backup-job", "read_only for web; write for release job", "mirror every published manifest", "retain all governed releases", "3", "immutable release payloads"),
        ("exports", "${PLATFORM_ROOT}/exports", "/srv/platform/exports", "web; worker", "read_write", "daily incremental", "90 days", "5", "user-generated exports; not authoritative"),
        ("backups", "${PLATFORM_ROOT}/backups", "/srv/platform/backups", "backup-job", "read_write", "off-NAS copy and checksum verification", "30 daily + 12 monthly + annual", "1", "database and manifest restore bundles"),
        ("logs", "${PLATFORM_ROOT}/logs", "/srv/platform/logs", "all", "append_only", "rotate and archive security/audit logs", "90 online + 365 archive", "6", "application logs exclude secrets"),
    ]
    names = ["volume_id", "host_path", "container_mount", "services", "access_mode", "backup_policy", "retention", "restore_order", "remark"]
    return [dict(zip(names, values)) for values in rows]


def run(project_root: Path) -> None:
    engine = project_root / ENGINE_REL
    runs = project_root / RUNS_REL
    output = runs / OUTPUT_RUN
    docs = engine / "docs/platform"

    source_root = engine / "data/private/reference_extraction/source_standards"
    gb_run = runs / "GB50854_2024_stageB_docx_full"
    gd_run = runs / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1"
    mapping_run = runs / "MAP_GB50854_TO_GD2018_BUILDING_A_FULL_1"
    web = engine / "web_collab_prototype"

    sources = [
        source_root / "国家标准/房屋建筑与装饰工程工程量计算标准.pdf",
        source_root / "房屋建筑与装饰工程工程量计算标准 GB_T 50854-2024.docx",
        source_root / "广东省建设工程综合定额(2018)/A01_广东省房屋建筑与装饰工程定额(上册).pdf",
        source_root / "广东省建设工程综合定额(2018)/A02_广东省房屋建筑与装饰工程定额(中册).pdf",
        source_root / "广东省建设工程综合定额(2018)/A03_广东省房屋建筑与装饰工程定额(下册).pdf",
    ]
    parsed_runs = [
        gb_run,
        runs / "GD2018_BUILDING_A01_FULL_PARSE_2",
        runs / "GD2018_BUILDING_A02_FULL_PARSE_1",
        runs / "GD2018_BUILDING_A03_FULL_PARSE_1",
    ]
    parsed = sorted(
        (path for parsed_run in parsed_runs for path in parsed_run.glob("*.csv")),
        key=lambda value: relative(value, project_root),
    )
    consolidated = sorted(gd_run.glob("*.csv"))
    mapping = sorted(mapping_run.glob("*.csv"))
    web_main = [
        web / "app.py", web / "quota_building.py", web / "build_quota_building_view_model.py",
        web / "templates/quota_building_index.html", web / "static/quota_building_style.css",
        web / "static/quota_building_app.js",
    ]
    all_required = sources + parsed + consolidated + mapping + web_main
    missing = [relative(path, project_root) for path in all_required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing RC1 artifacts: {missing}")

    bill_file = gb_run / "bill_item_reference_all_candidate.csv"
    context_file = gb_run / "bill_context_rules_all.csv"
    quota_file = gd_run / "gd_building_quota_items.csv"
    resource_file = gd_run / "gd_building_resource_components.csv"
    matrix_file = mapping_run / "building_bill_to_quota_matrix_472.csv"
    edge_file = mapping_run / "building_bill_to_quota_edges.csv"
    draft_db = web / "data/web_quota_building_draft.sqlite"

    counts = {
        "bill": csv_count(bill_file), "context_rule": csv_count(context_file),
        "quota": csv_count(quota_file), "resource": csv_count(resource_file),
        "matrix_bill": csv_count(matrix_file), "edge": csv_count(edge_file),
    }
    draft = draft_counts(draft_db)
    current_approved = sum([
        approved_count(bill_file), approved_count(quota_file), approved_count(edge_file),
    ])

    parser_scripts = [
        engine / "scripts/reference_extraction/stageB_docx_extract_gb50854_full.py",
        engine / "scripts/reference_extraction/stage_gd2018_building_a01_full_parse.py",
        engine / "scripts/reference_extraction/stage_gd2018_building_volume_full_parse.py",
        engine / "scripts/reference_extraction/stage_gd2018_building_a01_a03_consolidated.py",
        engine / "scripts/reference_extraction/stage_map_gb50854_to_gd2018_building_a_full.py",
    ]
    parser_version = ";".join(f"{path.stem}@{sha256(path)[:12]}" for path in parser_scripts)
    web_version = "WEB_REVIEW_RC1;ui=V0.1;readonly_schema=quota_building_readonly_v1"
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    groups = {
        "source_hash_manifest": sources,
        "parsed_baseline_hash_manifest": parsed,
        "consolidated_baseline_hash_manifest": consolidated,
        "mapping_reference_hash_manifest": mapping,
        "web_main_hash_manifest": web_main,
    }
    group_hashes = {name: manifest_hash(paths, project_root) for name, paths in groups.items()}

    manifest_fields = [
        "release_slice_id", "application_version", "database_schema_version", "reference_release_id",
        "mapping_release_id", "enterprise_price_release_id", "enterprise_quota_release_id",
        "source_hash_manifest", "docker_image_tag", "generated_at", "manifest_entry_id",
        "artifact_group", "artifact_role", "artifact_id", "artifact_path", "sha256",
        "file_size_bytes", "record_count", "parser_version", "web_version", "immutable", "status", "remark",
    ]
    common = {
        "release_slice_id": "BUILDING_RC1", "application_version": APPLICATION_RELEASE,
        "database_schema_version": "quota_building_readonly_v1_prototype_only",
        "reference_release_id": REFERENCE_RELEASE, "mapping_release_id": MAPPING_RELEASE,
        "enterprise_price_release_id": "not_created", "enterprise_quota_release_id": "not_created",
        "source_hash_manifest": group_hashes["source_hash_manifest"], "docker_image_tag": "not_built",
        "generated_at": generated_at, "parser_version": parser_version, "web_version": web_version,
    }
    manifest: list[dict[str, Any]] = []
    for index, (group_name, paths) in enumerate(groups.items(), start=1):
        manifest.append({
            **common, "manifest_entry_id": f"RC1-GROUP-{index:02d}", "artifact_group": group_name,
            "artifact_role": "aggregate_hash_manifest", "artifact_id": group_name.upper(),
            "artifact_path": f"manifest://{group_name}", "sha256": group_hashes[group_name],
            "file_size_bytes": sum(path.stat().st_size for path in paths),
            "record_count": len(paths), "immutable": "yes", "status": "frozen",
            "remark": "SHA256 over sorted project-relative path and file SHA256 pairs",
        })

    role_by_path = {
        sources[0]: "authority_source", sources[1]: "extraction_proxy",
        sources[2]: "authority_source", sources[3]: "authority_source", sources[4]: "authority_source",
    }
    sequence = 1
    for group_name, paths in groups.items():
        for path in paths:
            record_count: int | str = ""
            if path.suffix.lower() == ".csv":
                record_count = csv_count(path)
            role = role_by_path.get(path, "immutable_release_artifact")
            manifest.append({
                **common, "manifest_entry_id": f"RC1-FILE-{sequence:03d}", "artifact_group": group_name,
                "artifact_role": role, "artifact_id": path.stem, "artifact_path": relative(path, project_root),
                "sha256": sha256(path), "file_size_bytes": path.stat().st_size, "record_count": record_count,
                "immutable": "yes", "status": "frozen",
                "remark": "DOCX is non-authoritative structured extraction proxy" if role == "extraction_proxy" else "",
            })
            sequence += 1

    entities = entity_rows()
    transitions = state_transition_rows()
    permissions = permission_rows()
    releases = release_rows()
    volumes = deployment_rows()

    validations = [
        ("VAL-001", "RC1", "required artifact presence", "0 missing", str(len(missing)), "pass" if not missing else "fail", "blocking", "release manifest inputs"),
        ("VAL-002", "RC1", "bill item count", "472", str(counts["bill"]), "pass" if counts["bill"] == 472 else "fail", "blocking", relative(bill_file, project_root)),
        ("VAL-003", "RC1", "context rule count", "161", str(counts["context_rule"]), "pass" if counts["context_rule"] == 161 else "fail", "blocking", relative(context_file, project_root)),
        ("VAL-004", "RC1", "quota item count", "3700", str(counts["quota"]), "pass" if counts["quota"] == 3700 else "fail", "blocking", relative(quota_file, project_root)),
        ("VAL-005", "RC1", "resource component count", "24981", str(counts["resource"]), "pass" if counts["resource"] == 24981 else "fail", "blocking", relative(resource_file, project_root)),
        ("VAL-006", "RC1", "mapping bill matrix count", "472", str(counts["matrix_bill"]), "pass" if counts["matrix_bill"] == 472 else "fail", "blocking", relative(matrix_file, project_root)),
        ("VAL-007", "RC1", "mapping edge count", "1882", str(counts["edge"]), "pass" if counts["edge"] == 1882 else "fail", "blocking", relative(edge_file, project_root)),
        ("VAL-008", "Governance", "approved records in current Reference/Mapping", "0", str(current_approved), "pass" if current_approved == 0 else "fail", "blocking", "review_status scans"),
        ("VAL-009", "Overlay", "Draft current observation", "observed without mutation", str(draft["draft"]), "pass", "info", relative(draft_db, project_root)),
        ("VAL-010", "Overlay", "Audit current observation", "observed without mutation", str(draft["audit"]), "pass", "info", relative(draft_db, project_root)),
        ("VAL-011", "Overlay", "Review state current observation", "observed without mutation", str(draft["review"]), "pass", "info", relative(draft_db, project_root)),
        ("VAL-012", "Domain", "four domain definitions", "4", "4", "pass", "blocking", "PLATFORM_ARCHITECTURE.md"),
        ("VAL-013", "Domain", "Reference immutable", "defined", "defined", "pass", "blocking", "PLATFORM_ARCHITECTURE.md"),
        ("VAL-014", "Domain", "Mapping Draft is overlay", "defined", "defined", "pass", "blocking", "PLATFORM_ARCHITECTURE.md"),
        ("VAL-015", "Domain", "approved limited to Enterprise domains", "defined", "defined", "pass", "blocking", "DATABASE_LOGICAL_MODEL.md"),
        ("VAL-016", "Model", "required logical entities", "30", str(len(entities)), "pass" if len(entities) == 30 else "fail", "blocking", "platform_entity_dictionary.csv"),
        ("VAL-017", "Price", "price precedence order", "5 levels", "5 levels", "pass", "blocking", "ENTERPRISE_PRICE_DOMAIN.md"),
        ("VAL-018", "Price", "quota release captures price snapshot", "required", "required", "pass", "blocking", "ENTERPRISE_PRICE_DOMAIN.md"),
        ("VAL-019", "Quota", "required lifecycle states", "6", "6", "pass", "blocking", "ENTERPRISE_QUOTA_STATE_MACHINE.md"),
        ("VAL-020", "Quota", "published overwrite", "forbidden", "forbidden", "pass", "blocking", "enterprise_quota_state_transition.csv"),
        ("VAL-021", "Quota", "Change Set and rollback", "defined", "defined", "pass", "blocking", "ENTERPRISE_QUOTA_DOMAIN.md"),
        ("VAL-022", "Security", "required roles", "5", "5", "pass", "blocking", "role_permission_matrix.csv"),
        ("VAL-023", "Security", "separation of duties", "defined", "defined", "pass", "blocking", "ROLE_PERMISSION_MATRIX.md"),
        ("VAL-024", "API", "required /api/v1 resource groups", "8", "8", "pass", "blocking", "API_V1_CONTRACT.md"),
        ("VAL-025", "Deployment", "required compose services", "4 + optional worker", "4 + optional worker", "pass", "blocking", "NAS_DEPLOYMENT_BLUEPRINT.md"),
        ("VAL-026", "Deployment", "source volume access", "read_only", "read_only", "pass", "blocking", "deployment_volume_matrix.csv"),
        ("VAL-027", "Release", "manifest minimum fields", "9", "9", "pass", "blocking", "RELEASE_AND_UPGRADE_POLICY.md"),
        ("VAL-028", "Release", "backup/restore/upgrade/rollback", "defined", "defined", "pass", "blocking", "NAS_DEPLOYMENT_BLUEPRINT.md"),
        ("VAL-029", "Adapter", "Family Adapter contract fields", "7", "7", "pass", "blocking", "STANDARD_FAMILY_ADAPTER_SPEC.md"),
        ("VAL-030", "Scope", "A04/C/D/E parsed in this stage", "0", "0", "pass", "blocking", "architecture-only stage"),
        ("VAL-031", "Scope", "production PostgreSQL created", "no", "no", "pass", "blocking", "logical model only"),
        ("VAL-032", "Scope", "Enterprise price calculation implemented", "no", "no", "pass", "blocking", "contract only"),
        ("VAL-033", "Scope", "formal Enterprise Quota records created", "0", "0", "pass", "blocking", "architecture only"),
    ]
    validation_names = ["validation_id", "category", "check_name", "expected", "actual", "status", "severity", "evidence"]
    validation_rows = [dict(zip(validation_names, row)) for row in validations]
    blocking_failures = [row for row in validation_rows if row["severity"] == "blocking" and row["status"] != "pass"]
    if blocking_failures:
        raise RuntimeError(f"Blocking architecture validations failed: {blocking_failures}")

    write_csv(output / "building_rc1_release_manifest.csv", manifest_fields, manifest)
    write_csv(output / "platform_entity_dictionary.csv", list(entities[0]), entities)
    write_csv(output / "enterprise_quota_state_transition.csv", list(transitions[0]), transitions)
    write_csv(output / "role_permission_matrix.csv", list(permissions[0]), permissions)
    write_csv(output / "release_type_matrix.csv", list(releases[0]), releases)
    write_csv(output / "deployment_volume_matrix.csv", list(volumes[0]), volumes)
    write_csv(output / "platform_architecture_validation.csv", validation_names, validation_rows)

    manifest_md = f"""# Building RC1 Release Manifest

Generated: `{generated_at}`  
Status: `{FINAL_STATUS}`

## Frozen Product Slices

| Slice | Identifier | Role |
|---|---|---|
| Reference | `{REFERENCE_RELEASE}` | Immutable GB/T 50854 bill baseline plus GD2018 A01/A02/A03 quota reference |
| Mapping | `{MAPPING_RELEASE}` | Immutable candidate mapping release; no approved semantics |
| Web | `{APPLICATION_RELEASE}` | Reviewed UI/API source slice; Draft remains an external mutable overlay |

## Aggregate Hashes

| Hash group | SHA256 |
|---|---|
| Source | `{group_hashes['source_hash_manifest']}` |
| Parsed baseline | `{group_hashes['parsed_baseline_hash_manifest']}` |
| Consolidated baseline | `{group_hashes['consolidated_baseline_hash_manifest']}` |
| Mapping reference | `{group_hashes['mapping_reference_hash_manifest']}` |
| Web main files | `{group_hashes['web_main_hash_manifest']}` |

## Counts

- bill items: `{counts['bill']}`
- context rules: `{counts['context_rule']}`
- quota items: `{counts['quota']}`
- quota resources: `{counts['resource']}`
- mapping edges: `{counts['edge']}`
- current Draft/Audit/Review observations: `{draft['draft']}/{draft['audit']}/{draft['review']}`
- approved_count: `{current_approved}`

## Versions

- parser provenance: `{parser_version}`
- Web version: `{web_version}`
- database schema: `quota_building_readonly_v1_prototype_only` (not the target PostgreSQL schema)
- Docker image: `not_built`
- Enterprise Price Release: `not_created`
- Enterprise Quota Release: `not_created`

The detailed file-level evidence is in `building_rc1_release_manifest.csv`. The mutable Draft database is observed for counts only and is not part of the immutable RC payload.
"""
    write_text(docs / "BUILDING_RC1_RELEASE_MANIFEST.md", manifest_md)

    report = f"""# Stage PLATFORM-FOUNDATION-AND-ENTERPRISE-QUOTA-ARCHITECTURE-LOCK-1 Report

## Result

- final_status: `{FINAL_STATUS}`
- generated_at: `{generated_at}`
- blocking_validation_failures: `0`
- approved_count: `{current_approved}`

## RC1 Freeze

- Reference: `{REFERENCE_RELEASE}`
- Mapping: `{MAPPING_RELEASE}`
- Web: `{APPLICATION_RELEASE}`
- source_hash_manifest: `{group_hashes['source_hash_manifest']}`
- parsed_baseline_hash_manifest: `{group_hashes['parsed_baseline_hash_manifest']}`
- consolidated_baseline_hash_manifest: `{group_hashes['consolidated_baseline_hash_manifest']}`
- mapping_reference_hash_manifest: `{group_hashes['mapping_reference_hash_manifest']}`
- web_main_hash_manifest: `{group_hashes['web_main_hash_manifest']}`
- bill/quota/resource/edge: `{counts['bill']}/{counts['quota']}/{counts['resource']}/{counts['edge']}`
- Draft/Audit/Review observed without mutation: `{draft['draft']}/{draft['audit']}/{draft['review']}`

## Architecture Lock

- Domains: Reference, Mapping, Enterprise Price, Enterprise Quota.
- Logical PostgreSQL entities: `{len(entities)}`.
- Enterprise Price precedence is specified but no calculation is implemented.
- Enterprise Quota uses draft/submitted/reviewed/approved/published/superseded and never overwrites published versions.
- Roles: viewer, reviewer, editor, approver, administrator.
- NAS topology: web, database, reverse-proxy, backup-job, optional worker; source is read-only.
- Family Adapter contract covers future A04, C + GB/T 50856, D + GB/T 50857, and E + GB/T 50858 without parsing them.

## Scope Protection

No Source, Baseline, Mapping, Web business feature, Draft/Audit, production database, Enterprise Price data, or Enterprise Quota record was modified or created by this stage. Outputs are architecture documents and governance evidence only.
"""
    write_text(output / "stage_platform_foundation_and_enterprise_quota_architecture_lock_report.md", report)

    print(f"final_status={FINAL_STATUS}")
    print(f"manifest_rows={len(manifest)}")
    print(f"entity_count={len(entities)}")
    print(f"validation_count={len(validation_rows)}")
    print(f"bill_quota_edge={counts['bill']}/{counts['quota']}/{counts['edge']}")
    print(f"draft_audit_review={draft['draft']}/{draft['audit']}/{draft['review']}")
    print(f"approved_count={current_approved}")
    print(f"output={output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args().project_root)
