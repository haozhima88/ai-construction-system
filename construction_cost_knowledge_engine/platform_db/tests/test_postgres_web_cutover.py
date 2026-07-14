from __future__ import annotations

import hashlib
import secrets
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, cast, func, select, text

from platform_db.api import app
from platform_db.importers.hash_guard import validate_rc1_manifest
from platform_db.models import (
    AppTenant, AppUser, MappingAuditEvent, MappingCandidateEdge, MappingDraftEdge,
    MappingRelease, MappingReviewState, MappingWorkspace, ReferenceBillItem,
    ReferenceQuotaItem, ReferenceQuotaResource,
)
from platform_db.repositories import BillReviewRepository, ReviewNotFoundError
from platform_db.services.quota_cost_summary import QuotaCostSummaryService
from platform_db.tests.test_authentication_rbac import auth_harness


SQLITE_PATH = Path(__file__).resolve().parents[2] / "web_collab_prototype/data/web_quota_building_draft.sqlite"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csrf(response) -> dict[str, str]:
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def login(harness, label: str) -> tuple[TestClient, object]:
    client = TestClient(app)
    response = harness.login(label, client)
    assert response.status_code == 200
    return client, response


@pytest.fixture(scope="module")
def pg_web(auth_harness):
    h = auth_harness
    release = h.session.scalar(select(MappingRelease).where(
        cast(MappingRelease.release_status, String) == "published"
    ).order_by(MappingRelease.created_at.desc()))
    workspace = MappingWorkspace(
        mapping_workspace_id=uuid.uuid4(), tenant_id=h.tenant.tenant_id,
        mapping_release_id=release.mapping_release_id,
        workspace_name=f"web-cutover-test-{uuid.uuid4().hex[:8]}",
        workspace_status="active", created_by=h.system_user.app_user_id,
    )
    h.session.add(workspace)
    h.session.flush()
    edge = h.session.scalar(select(MappingCandidateEdge).where(
        MappingCandidateEdge.mapping_release_id == release.mapping_release_id
    ).order_by(MappingCandidateEdge.candidate_rank, MappingCandidateEdge.source_key))
    source_bill = h.session.get(ReferenceBillItem, edge.reference_bill_item_id)
    target_bill = h.session.scalar(select(ReferenceBillItem).where(
        ReferenceBillItem.reference_release_id == release.reference_release_id,
        ReferenceBillItem.reference_bill_item_id != source_bill.reference_bill_item_id,
    ).order_by(ReferenceBillItem.bill_code_9))
    quota = h.session.get(ReferenceQuotaItem, edge.reference_quota_item_id)
    data = {
        "h": h, "release": release, "workspace": workspace, "edge": edge,
        "source_bill": source_bill, "target_bill": target_bill, "quota": quota,
        "sqlite_hash": sha256(SQLITE_PATH), "drafts": {},
    }
    yield data
    assert sha256(SQLITE_PATH) == data["sqlite_hash"]


def test_pg_01_migration_is_cutover_head(pg_web):
    assert pg_web["h"].session.scalar(text("SELECT version_num FROM alembic_version")) == "0003_postgres_review_cutover"


def test_pg_02_anonymous_postgres_page_redirects(pg_web):
    client = TestClient(app)
    response = client.get("/quota-building-pg", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].startswith("/login?next=/quota-building-pg")
    client.close()


def test_pg_03_anonymous_switched_page_redirects(pg_web):
    client = TestClient(app)
    response = client.get("/quota-building", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].startswith("/login?next=/quota-building")
    client.close()


def test_pg_04_account_and_admin_pages_are_protected(pg_web):
    client = TestClient(app)
    assert client.get("/platform-account", follow_redirects=False).status_code == 303
    assert client.get("/platform-admin/users", follow_redirects=False).status_code == 303
    client.close()


def test_pg_05_sqlite_fallback_pages_are_explicitly_read_only(pg_web):
    client = TestClient(app)
    for path in ("/quota-building-sqlite", "/quota-building-legacy"):
        response = client.get(path)
        assert response.status_code == 200
        assert "SQLite read-only" in response.text
    summary = client.get("/api/v1/review-sqlite/summary").json()
    assert summary["backend"] == "sqlite_readonly_fallback" and summary["readonly"] is True
    client.close()


def test_pg_06_sqlite_fallback_exposes_no_write_route(pg_web):
    client = TestClient(app)
    assert client.post("/api/v1/review-sqlite/mapping-drafts/copy", json={}).status_code == 404
    client.close()


def test_pg_07_authenticated_viewer_opens_postgres_workbench(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    response = client.get("/quota-building-pg")
    assert response.status_code == 200 and 'data-mode="postgres"' in response.text
    client.close()


def test_pg_07a_forced_password_change_preserves_workbench_next(pg_web):
    client, _ = login(pg_web["h"], "forced")
    response = client.get("/quota-building", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/change-password?next=/quota-building"
    change_page = client.get("/change-password?next=/quota-building")
    assert change_page.status_code == 200 and "change-password.js" in change_page.text
    client.close()


def test_pg_08_summary_matches_rc1_entity_counts(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    payload = client.get("/api/v1/review/summary").json()
    assert (payload["bill_count"], payload["quota_count"], payload["resource_count"], payload["mapping_edge_count"]) == (472, 3700, 24981, 1882)
    assert payload["backend"] == "postgres" and payload["approved_count"] == 0
    client.close()


def test_pg_09_tree_returns_all_bills_and_review_fields(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    payload = client.get("/api/v1/review/tree", params={"page_size": 500}).json()
    assert payload["total"] == 472 and len(payload["items"]) == 472
    assert {"original_count", "effective_count", "review_priority", "review_state"} <= set(payload["items"][0])
    client.close()


def test_pg_10_tree_search_reaches_quota_codes(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    payload = client.get("/api/v1/review/tree", params={"page_size": 500, "q": pg_web["quota"].source_code}).json()
    assert payload["total"] >= 1
    client.close()


def test_pg_11_bill_detail_contract(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    bill = client.get(f"/api/v1/review/bills/{pg_web['source_bill'].bill_code_9}").json()["bill"]
    assert bill["bill_code_9"] == pg_web["source_bill"].bill_code_9
    assert {"project_feature_raw", "quantity_calculation_rule", "work_content_raw", "row_version"} <= set(bill)
    client.close()


def test_pg_12_mapping_overlay_contract(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    payload = client.get(f"/api/v1/review/bills/{pg_web['source_bill'].bill_code_9}/mappings").json()
    assert payload["count"] >= 1
    assert {
        "edge_id", "mapping_edge_id", "bill_id", "bill_code_9", "quota_id", "quota_uid",
        "row_version", "row_origin", "effective", "draft_state", "relationship_type",
        "review_priority", "review_row_version",
    } <= set(payload["items"][0])
    client.close()


def test_pg_13_quota_detail_contract(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    quota = client.get(f"/api/v1/review/quotas/{pg_web['quota'].reference_quota_item_id}").json()["quota"]
    assert quota["source_code"] == pg_web["quota"].source_code
    assert {"labor_fee", "material_fee", "machine_fee", "management_fee", "total_fee", "pdf_page_no"} <= set(quota)
    client.close()


def test_pg_14_resource_amount_contract(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    payload = client.get(f"/api/v1/review/quotas/{pg_web['quota'].reference_quota_item_id}/resources", params={"page_size": 500}).json()
    assert payload["total"] >= 1
    required = {"source_component_amount", "calculated_component_amount", "display_component_amount", "amount_source"}
    assert all(required <= set(row) for row in payload["items"])
    client.close()


def test_pg_15_decimal_priority_fallback_and_blank_preservation(pg_web):
    service = QuotaCostSummaryService()
    base = dict(reference_quota_resource_id=uuid.uuid4(), resource_code="R", resource_name="Resource", resource_category="material", specification=None, unit="kg", source_page_no=1, source_row_order=1)
    source = service.resource_amount(SimpleNamespace(**base, component_amount="2.345678", consumption="3.1", unit_price="9.9"))
    fallback = service.resource_amount(SimpleNamespace(**base, component_amount=None, consumption="3.1", unit_price="9.9"))
    blank = service.resource_amount(SimpleNamespace(**base, component_amount=None, consumption=None, unit_price="9.9"))
    assert source["display_component_amount"] == "2.345678" and source["amount_source"] == "source"
    assert fallback["display_component_amount"] == "30.69" and fallback["amount_source"] == "calculated_fallback"
    assert blank["display_component_amount"] is None and blank["amount_source"] == "unavailable"


def test_pg_16_cost_summary_contract_and_status(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    payload = client.get(f"/api/v1/review/quotas/{pg_web['quota'].reference_quota_item_id}/cost-summary").json()
    required = {f"{category}_{kind}_total" for category in ("labor", "material", "machine", "other", "resource") for kind in ("source", "calculated")}
    required |= {"management_fee", "provincial_base_price", "reconciliation_delta", "reconciliation_status", "reconciliation_reason"}
    assert required <= set(payload)
    assert payload["reconciliation_status"] in {"matched", "rounding_only", "category_boundary_explained", "unpriced_material_excluded", "partial_resource_rows_missing", "source_blank_preserved", "mismatch_requires_review"}
    client.close()


def test_pg_17_work_content_is_structured(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    payload = client.get(f"/api/v1/review/quotas/{pg_web['quota'].reference_quota_item_id}/work-content").json()
    assert payload["count"] >= 0 and all("rule_text" in row for row in payload["items"])
    client.close()


def test_pg_18_quantity_rules_are_structured(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    payload = client.get(f"/api/v1/review/quotas/{pg_web['quota'].reference_quota_item_id}/quantity-rules").json()
    assert payload["count"] >= 0 and all("source_locator" in row for row in payload["items"])
    client.close()


def test_pg_19_conversion_and_notes_endpoints(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    for suffix in ("conversion-rules", "notes"):
        payload = client.get(f"/api/v1/review/quotas/{pg_web['quota'].reference_quota_item_id}/{suffix}").json()
        assert set(payload) == {"items", "count"}
    client.close()


def test_pg_20_evidence_contains_document_role_and_page(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    payload = client.get(f"/api/v1/review/quotas/{pg_web['quota'].reference_quota_item_id}/evidence").json()
    assert payload["document"]["source_available"] is True
    assert payload["document"]["source_role"] in {"authority_source", "extraction_proxy"}
    assert payload["page_no"] == pg_web["quota"].pdf_page_no
    client.close()


def test_pg_21_province_pdf_is_streamable(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    with client.stream("GET", f"/api/v1/review/quotas/{pg_web['quota'].reference_quota_item_id}/pdf") as response:
        assert response.status_code == 200 and response.headers["content-type"].startswith("application/pdf")
        assert response.headers["x-frame-options"] == "SAMEORIGIN"
    client.close()


def test_pg_22_authority_pdf_is_streamable(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    with client.stream("GET", "/api/v1/review/authority/pdf") as response:
        assert response.status_code == 200 and response.headers["content-type"].startswith("application/pdf")
        assert "frame-ancestors 'self'" in response.headers["content-security-policy"]
    client.close()


def test_pg_23_audit_endpoint_is_tenant_scoped(pg_web):
    client, _ = login(pg_web["h"], "viewer")
    payload = client.get("/api/v1/review/audit", params={"page_size": 500}).json()
    assert payload["total"] == 0
    client.close()


def test_pg_24_viewer_cannot_create_draft(pg_web):
    client, response = login(pg_web["h"], "viewer")
    payload = {"edge_id": str(pg_web["edge"].mapping_candidate_edge_id), "target_bill_code_9": pg_web["target_bill"].bill_code_9, "operation_reason": "viewer denied", "row_version": pg_web["edge"].row_version, "idempotency_key": f"viewer-{uuid.uuid4()}"}
    assert client.post("/api/v1/review/mapping-drafts/copy", headers=csrf(response), json=payload).status_code == 403
    client.close()


def test_pg_25_editor_write_requires_csrf(pg_web):
    client, _ = login(pg_web["h"], "editor")
    payload = {"edge_id": str(pg_web["edge"].mapping_candidate_edge_id), "target_bill_code_9": pg_web["target_bill"].bill_code_9, "operation_reason": "csrf denied", "row_version": pg_web["edge"].row_version, "idempotency_key": f"csrf-{uuid.uuid4()}"}
    assert client.post("/api/v1/review/mapping-drafts/copy", json=payload).status_code == 403
    client.close()


def test_pg_26_editor_copy_is_atomic_with_audit(pg_web):
    h = pg_web["h"]
    client, response = login(h, "editor")
    before_drafts = h.session.scalar(select(func.count()).select_from(MappingDraftEdge).where(MappingDraftEdge.tenant_id == h.tenant.tenant_id))
    before_audits = h.session.scalar(select(func.count()).select_from(MappingAuditEvent).where(MappingAuditEvent.tenant_id == h.tenant.tenant_id))
    key = f"copy-{uuid.uuid4()}"
    payload = {"edge_id": str(pg_web["edge"].mapping_candidate_edge_id), "target_bill_code_9": pg_web["target_bill"].bill_code_9, "operation_reason": "copy test", "row_version": pg_web["edge"].row_version, "idempotency_key": key}
    result = client.post("/api/v1/review/mapping-drafts/copy", headers=csrf(response), json=payload)
    assert result.status_code == 200 and result.json()["approved"] is False
    pg_web["drafts"]["copy"] = result.json()["draft"]
    assert h.session.scalar(select(func.count()).select_from(MappingDraftEdge).where(MappingDraftEdge.tenant_id == h.tenant.tenant_id)) == before_drafts + 1
    assert h.session.scalar(select(func.count()).select_from(MappingAuditEvent).where(MappingAuditEvent.tenant_id == h.tenant.tenant_id)) == before_audits + 1
    pg_web["copy_payload"] = payload
    client.close()


def test_pg_27_idempotency_replays_without_duplicate(pg_web):
    h = pg_web["h"]
    client, response = login(h, "editor")
    before = h.session.scalar(select(func.count()).select_from(MappingDraftEdge).where(MappingDraftEdge.tenant_id == h.tenant.tenant_id))
    result = client.post("/api/v1/review/mapping-drafts/copy", headers=csrf(response), json=pg_web["copy_payload"])
    assert result.status_code == 200 and result.json()["idempotent_replay"] is True
    assert h.session.scalar(select(func.count()).select_from(MappingDraftEdge).where(MappingDraftEdge.tenant_id == h.tenant.tenant_id)) == before
    client.close()


def test_pg_28_stale_row_version_returns_conflict(pg_web):
    client, response = login(pg_web["h"], "editor")
    payload = {"edge_id": str(pg_web["edge"].mapping_candidate_edge_id), "target_bill_code_9": pg_web["target_bill"].bill_code_9, "operation_reason": "stale", "row_version": pg_web["edge"].row_version + 99, "idempotency_key": f"stale-{uuid.uuid4()}"}
    assert client.post("/api/v1/review/mapping-drafts/copy", headers=csrf(response), json=payload).status_code == 409
    client.close()


@pytest.mark.parametrize("action", ["move", "exclude"])
def test_pg_29_editor_move_and_exclude_remain_drafts(pg_web, action):
    client, response = login(pg_web["h"], "editor")
    payload = {"edge_id": str(pg_web["edge"].mapping_candidate_edge_id), "target_bill_code_9": pg_web["target_bill"].bill_code_9 if action == "move" else None, "operation_reason": f"{action} test", "row_version": pg_web["edge"].row_version, "idempotency_key": f"{action}-{uuid.uuid4()}"}
    result = client.post(f"/api/v1/review/mapping-drafts/{action}", headers=csrf(response), json=payload)
    assert result.status_code == 200 and result.json()["draft"]["draft_status"] == "active" and result.json()["approved"] is False
    pg_web["drafts"][action] = result.json()["draft"]
    client.close()


def test_pg_30_editor_can_restore_draft(pg_web):
    client, response = login(pg_web["h"], "editor")
    draft = pg_web["drafts"]["copy"]
    payload = {"draft_id": draft["draft_id"], "row_version": draft["row_version"], "idempotency_key": f"restore-{uuid.uuid4()}"}
    result = client.post("/api/v1/review/mapping-drafts/restore", headers=csrf(response), json=payload)
    assert result.status_code == 200 and result.json()["draft"]["draft_status"] == "reverted" and result.json()["approved"] is False
    client.close()


def test_pg_31_reviewer_updates_nonapproved_review_state(pg_web):
    client, response = login(pg_web["h"], "reviewer")
    payload = {"review_status": "reviewed_candidate", "comment": "review test", "row_version": 0, "idempotency_key": f"review-{uuid.uuid4()}"}
    result = client.patch(f"/api/v1/review/mappings/{pg_web['edge'].mapping_candidate_edge_id}/review-state", headers=csrf(response), json=payload)
    assert result.status_code == 200 and result.json()["review"]["review_status"] == "reviewed_candidate" and result.json()["approved"] is False
    client.close()


def test_pg_32_editor_and_approver_cannot_review_or_write(pg_web):
    edge_id = pg_web["edge"].mapping_candidate_edge_id
    editor, editor_login = login(pg_web["h"], "editor")
    review = {"review_status": "needs_followup", "comment": "denied", "row_version": 1, "idempotency_key": f"editor-review-{uuid.uuid4()}"}
    assert editor.patch(f"/api/v1/review/mappings/{edge_id}/review-state", headers=csrf(editor_login), json=review).status_code == 403
    editor.close()
    approver, approver_login = login(pg_web["h"], "approver")
    draft = {"edge_id": str(edge_id), "target_bill_code_9": pg_web["target_bill"].bill_code_9, "operation_reason": "denied", "row_version": pg_web["edge"].row_version, "idempotency_key": f"approver-{uuid.uuid4()}"}
    assert approver.post("/api/v1/review/mapping-drafts/copy", headers=csrf(approver_login), json=draft).status_code == 403
    approver.close()


def test_pg_33_other_tenant_audit_is_not_visible(pg_web):
    h = pg_web["h"]
    other_tenant = AppTenant(tenant_id=uuid.uuid4(), tenant_code=f"other-web-{uuid.uuid4().hex[:8]}", tenant_name="Other Web Tenant", status="active")
    other_actor = AppUser(app_user_id=uuid.uuid4(), tenant_id=other_tenant.tenant_id, login_name=f"other-service-{uuid.uuid4().hex[:6]}", login_name_normalized="", display_name="Other Service", status="active", is_service_account=True, must_change_password=False, auth_version=1)
    other_actor.login_name_normalized = other_actor.login_name.casefold()
    other_workspace = MappingWorkspace(mapping_workspace_id=uuid.uuid4(), tenant_id=other_tenant.tenant_id, mapping_release_id=pg_web["release"].mapping_release_id, workspace_name="other-workspace", workspace_status="active", created_by=other_actor.app_user_id)
    h.session.add_all([other_tenant, other_actor]); h.session.flush(); h.session.add(other_workspace); h.session.flush()
    marker = f"other:{uuid.uuid4()}"
    h.session.add(MappingAuditEvent(mapping_audit_event_id=uuid.uuid4(), tenant_id=other_tenant.tenant_id, mapping_workspace_id=other_workspace.mapping_workspace_id, actor_user_id=other_actor.app_user_id, source_audit_key=marker, event_type="tenant_isolation_probe", event_at="2026-07-13T00:00:00+00:00", before_payload=None, after_payload={"probe": True}, created_by=other_actor.app_user_id))
    h.session.flush()
    client, _ = login(h, "viewer")
    payload = client.get("/api/v1/review/audit", params={"page_size": 500}).json()
    assert marker not in {row["source_audit_key"] for row in payload["items"]}
    client.close()


def test_pg_34_frozen_sources_counts_hashes_and_approved_zero(pg_web):
    h = pg_web["h"]
    assert sha256(SQLITE_PATH) == pg_web["sqlite_hash"]
    assert validate_rc1_manifest(Path(__file__).resolve().parents[3], h.settings.rc1_manifest_path)["ok"] is True
    counts = tuple(h.session.scalar(select(func.count()).select_from(table)) for table in (ReferenceBillItem, ReferenceQuotaItem, ReferenceQuotaResource, MappingCandidateEdge))
    assert counts == (472, 3700, 24981, 1882)
    approved = sum(int(h.session.scalar(select(func.count()).select_from(table).where(cast(table.review_status, String) == "approved")) or 0) for table in (ReferenceBillItem, ReferenceQuotaItem, ReferenceQuotaResource, MappingCandidateEdge, MappingDraftEdge, MappingReviewState))
    assert approved == 0


def test_pg_35_explicit_workspace_selection_is_exact(pg_web):
    repository = BillReviewRepository(
        pg_web["h"].session,
        pg_web["h"].tenant.tenant_id,
        workspace_name=pg_web["workspace"].workspace_name,
    )
    assert repository.scope.workspace_id == pg_web["workspace"].mapping_workspace_id
    assert repository.scope.workspace_name == pg_web["workspace"].workspace_name


def test_pg_36_missing_explicit_workspace_is_rejected(pg_web):
    with pytest.raises(ReviewNotFoundError, match="workspace is unavailable"):
        BillReviewRepository(
            pg_web["h"].session,
            pg_web["h"].tenant.tenant_id,
            workspace_name=f"missing-{uuid.uuid4()}",
        )


def test_pg_37_mapping_audit_carries_generated_request_id(pg_web):
    key = pg_web["copy_payload"]["idempotency_key"]
    event = pg_web["h"].session.scalar(select(MappingAuditEvent).where(
        MappingAuditEvent.tenant_id == pg_web["h"].tenant.tenant_id,
        MappingAuditEvent.source_audit_key == f"web:{key}",
    ))
    assert event is not None and event.correlation_id is not None


def test_pg_38_response_and_audit_request_ids_match(pg_web):
    client, response = login(pg_web["h"], "editor")
    request_id = uuid.uuid4()
    headers = {**csrf(response), "X-Request-ID": str(request_id)}
    payload = {
        "edge_id": str(pg_web["edge"].mapping_candidate_edge_id),
        "target_bill_code_9": None,
        "operation_reason": "request id audit test",
        "row_version": pg_web["edge"].row_version,
        "idempotency_key": f"request-id-{uuid.uuid4()}",
    }
    result = client.post(
        "/api/v1/review/mapping-drafts/exclude", headers=headers, json=payload
    )
    assert result.status_code == 200
    assert result.headers["x-request-id"] == str(request_id)
    event = pg_web["h"].session.scalar(select(MappingAuditEvent).where(
        MappingAuditEvent.tenant_id == pg_web["h"].tenant.tenant_id,
        MappingAuditEvent.source_audit_key == f"web:{payload['idempotency_key']}",
    ))
    assert event is not None and event.correlation_id == request_id
    client.close()


def test_pg_39_section_scoped_rules_and_bill_authority_evidence_are_exposed(pg_web):
    quota = pg_web["h"].session.scalar(select(ReferenceQuotaItem).where(
        ReferenceQuotaItem.source_code == "A1-1-1"
    ))
    client, _ = login(pg_web["h"], "viewer")
    conversion = client.get(
        f"/api/v1/review/quotas/{quota.reference_quota_item_id}/conversion-rules"
    ).json()
    notes = client.get(
        f"/api/v1/review/quotas/{quota.reference_quota_item_id}/notes"
    ).json()
    evidence = client.get(
        "/api/v1/review/bills/010101001/authority-evidence"
    ).json()
    assert conversion["count"] > 0 and notes["count"] > 0
    assert all(row["scope_type"] == "section_hierarchy" for row in conversion["items"])
    assert evidence["official_pdf_page_no"] is None
    assert evidence["evidence_link_status"] == "pending_evidence_link"
    client.close()
