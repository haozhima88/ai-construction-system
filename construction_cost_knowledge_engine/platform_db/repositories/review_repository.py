from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import String, and_, cast, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from platform_db.config import get_settings
from platform_db.models import (
    MappingAuditEvent, MappingCandidateEdge, MappingDraftEdge, MappingRelease,
    MappingReviewState, MappingWorkspace, ReferenceBillItem, ReferenceQuotaItem,
    ReferenceQuotaResource, ReferenceRuleBlock, ReferenceScopeLink, SourceDocument,
    SourcePageEvidence,
)


ALLOWED_DRAFT_ACTIONS = {"copy", "move", "exclude"}
ALLOWED_REVIEW_STATES = {"reviewed_candidate", "needs_followup", "reviewed_mismatch"}


class ReviewNotFoundError(LookupError):
    pass


class ReviewConflictError(RuntimeError):
    pass


class ReviewValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ReviewScope:
    tenant_id: uuid.UUID
    reference_release_id: str
    mapping_release_id: str
    workspace_id: uuid.UUID
    workspace_name: str


def enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="microseconds")


def page_meta(page: int, page_size: int, total: int) -> dict[str, int]:
    return {"page": page, "page_size": page_size, "total": total}


class ScopedReviewRepository:
    def __init__(
        self, session: Session, tenant_id: uuid.UUID, workspace_name: str | None = None
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.workspace_name = (
            get_settings().mapping_workspace_name if workspace_name is None else workspace_name
        ).strip()
        self.scope = self._resolve_scope()

    def _resolve_scope(self) -> ReviewScope:
        release = self.session.execute(
            select(MappingRelease.mapping_release_id, MappingRelease.reference_release_id)
            .where(cast(MappingRelease.release_status, String) == "published")
            .order_by(MappingRelease.created_at.desc()).limit(1)
        ).first()
        if release is None:
            raise ReviewNotFoundError("Published Mapping release is unavailable")
        workspace_statement = select(
            MappingWorkspace.mapping_workspace_id, MappingWorkspace.workspace_name
        ).where(
                MappingWorkspace.tenant_id == self.tenant_id,
                MappingWorkspace.mapping_release_id == release.mapping_release_id,
                cast(MappingWorkspace.workspace_status, String) == "active",
            )
        if self.workspace_name:
            workspace_statement = workspace_statement.where(
                MappingWorkspace.workspace_name == self.workspace_name
            )
        workspace = self.session.execute(
            workspace_statement.order_by(MappingWorkspace.created_at).limit(1)
        ).first()
        if workspace is None:
            raise ReviewNotFoundError("Tenant Mapping workspace is unavailable")
        return ReviewScope(
            self.tenant_id, release.reference_release_id, release.mapping_release_id,
            workspace.mapping_workspace_id, workspace.workspace_name,
        )


class BillReviewRepository(ScopedReviewRepository):
    def tree(
        self, *, page: int, page_size: int, q: str | None = None,
        appendix_code: str | None = None,
    ) -> dict[str, Any]:
        statement = select(ReferenceBillItem).where(
            ReferenceBillItem.reference_release_id == self.scope.reference_release_id
        )
        if q:
            pattern = f"%{q.strip()}%"
            quota_bill_ids = select(MappingCandidateEdge.reference_bill_item_id).join(
                ReferenceQuotaItem,
                ReferenceQuotaItem.reference_quota_item_id == MappingCandidateEdge.reference_quota_item_id,
            ).where(
                MappingCandidateEdge.mapping_release_id == self.scope.mapping_release_id,
                or_(
                    ReferenceQuotaItem.source_code.ilike(pattern),
                    ReferenceQuotaItem.quota_name.ilike(pattern),
                    ReferenceQuotaItem.reference_quota_item_id.in_(
                        select(ReferenceQuotaResource.reference_quota_item_id).where(
                            or_(
                                ReferenceQuotaResource.resource_code.ilike(pattern),
                                ReferenceQuotaResource.resource_name.ilike(pattern),
                            )
                        )
                    ),
                ),
            )
            statement = statement.where(or_(
                ReferenceBillItem.bill_code_9.ilike(pattern),
                ReferenceBillItem.bill_name.ilike(pattern),
                ReferenceBillItem.project_feature_raw.ilike(pattern),
                ReferenceBillItem.reference_bill_item_id.in_(quota_bill_ids),
            ))
        if appendix_code:
            statement = statement.where(ReferenceBillItem.appendix_code == appendix_code)
        total = int(self.session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        ) or 0)
        bills = list(self.session.scalars(
            statement.order_by(
                ReferenceBillItem.appendix_code, ReferenceBillItem.section_code,
                ReferenceBillItem.bill_code_9,
            ).offset((page - 1) * page_size).limit(page_size)
        ))
        bill_ids = [bill.reference_bill_item_id for bill in bills]
        if not bill_ids:
            return {"items": [], **page_meta(page, page_size, total)}

        candidate_stats = {
            row["reference_bill_item_id"]: dict(row)
            for row in self.session.execute(select(
                MappingCandidateEdge.reference_bill_item_id,
                func.count().label("candidate_count"),
                func.count().filter(MappingCandidateEdge.risk_level == "high").label("high_count"),
                func.count().filter(
                    MappingCandidateEdge.routing_class == "manual_review_required"
                ).label("manual_count"),
            ).where(
                MappingCandidateEdge.mapping_release_id == self.scope.mapping_release_id,
                MappingCandidateEdge.reference_bill_item_id.in_(bill_ids),
            ).group_by(MappingCandidateEdge.reference_bill_item_id)).mappings()
        }
        outbound: dict[uuid.UUID, dict[str, int]] = {}
        for bill_id, action, count in self.session.execute(select(
            MappingCandidateEdge.reference_bill_item_id, MappingDraftEdge.action_type,
            func.count().label("count"),
        ).join(
            MappingCandidateEdge,
            MappingCandidateEdge.mapping_candidate_edge_id == MappingDraftEdge.mapping_candidate_edge_id,
        ).where(
            MappingDraftEdge.tenant_id == self.tenant_id,
            MappingDraftEdge.mapping_workspace_id == self.scope.workspace_id,
            MappingDraftEdge.draft_status != "reverted",
            MappingCandidateEdge.reference_bill_item_id.in_(bill_ids),
        ).group_by(MappingCandidateEdge.reference_bill_item_id, MappingDraftEdge.action_type)):
            outbound.setdefault(bill_id, {})[action] = int(count)
        incoming: dict[uuid.UUID, dict[str, int]] = {}
        for bill_id, action, count in self.session.execute(select(
            MappingDraftEdge.target_bill_item_id, MappingDraftEdge.action_type,
            func.count().label("count"),
        ).where(
            MappingDraftEdge.tenant_id == self.tenant_id,
            MappingDraftEdge.mapping_workspace_id == self.scope.workspace_id,
            MappingDraftEdge.draft_status != "reverted",
            MappingDraftEdge.target_bill_item_id.in_(bill_ids),
        ).group_by(MappingDraftEdge.target_bill_item_id, MappingDraftEdge.action_type)):
            incoming.setdefault(bill_id, {})[action] = int(count)
        reviews: dict[uuid.UUID, dict[str, int]] = {}
        for bill_id, status, count in self.session.execute(select(
            MappingCandidateEdge.reference_bill_item_id,
            cast(MappingReviewState.review_status, String), func.count().label("count"),
        ).join(
            MappingCandidateEdge,
            MappingCandidateEdge.mapping_candidate_edge_id == MappingReviewState.mapping_candidate_edge_id,
        ).where(
            MappingReviewState.tenant_id == self.tenant_id,
            MappingCandidateEdge.reference_bill_item_id.in_(bill_ids),
        ).group_by(MappingCandidateEdge.reference_bill_item_id, MappingReviewState.review_status)):
            reviews.setdefault(bill_id, {})[status] = int(count)

        output = []
        for bill in bills:
            stats = candidate_stats.get(bill.reference_bill_item_id, {})
            out = outbound.get(bill.reference_bill_item_id, {})
            inc = incoming.get(bill.reference_bill_item_id, {})
            original = int(stats.get("candidate_count") or 0)
            hidden = int(out.get("move", 0)) + int(out.get("exclude", 0))
            effective = original + int(inc.get("copy", 0)) + int(inc.get("move", 0)) - hidden
            if original == 0:
                priority, reason = "P0", "zero_candidate_bill"
            elif int(stats.get("high_count") or 0) or int(stats.get("manual_count") or 0):
                priority, reason = "P0", "high_risk_or_manual_review"
            elif original >= 5:
                priority, reason = "P1", "candidate_count>=5"
            else:
                priority, reason = "P2", "low_risk_candidate"
            review_counts = reviews.get(bill.reference_bill_item_id, {})
            review_state = next((value for value in (
                "reviewed_mismatch", "needs_followup", "reviewed_candidate"
            ) if review_counts.get(value)), "not_reviewed")
            output.append({
                "bill_id": str(bill.reference_bill_item_id),
                "bill_code_9": bill.bill_code_9, "bill_name": bill.bill_name,
                "appendix_code": bill.appendix_code, "appendix_name": bill.appendix_name,
                "section_code": bill.section_code, "section_name": bill.section_name,
                "unit": bill.unit, "project_feature_raw": bill.project_feature_raw,
                "original_count": original, "copy_count": int(out.get("copy", 0)),
                "copy_in_count": int(inc.get("copy", 0)),
                "move_in_count": int(inc.get("move", 0)),
                "move_out_count": int(out.get("move", 0)),
                "exclude_count": int(out.get("exclude", 0)),
                "effective_count": effective, "review_state": review_state,
                "review_counts": review_counts, "review_priority": priority,
                "priority_reason": reason,
                "manual_review_count": int(stats.get("manual_count") or 0),
                "has_issue": priority == "P0",
            })
        return {"items": output, **page_meta(page, page_size, total)}

    def bill(self, bill_identifier: str) -> ReferenceBillItem:
        filters = [ReferenceBillItem.bill_code_9 == bill_identifier]
        try:
            filters.append(ReferenceBillItem.reference_bill_item_id == uuid.UUID(bill_identifier))
        except ValueError:
            pass
        bill = self.session.scalar(select(ReferenceBillItem).where(
            ReferenceBillItem.reference_release_id == self.scope.reference_release_id,
            or_(*filters),
        ))
        if bill is None:
            raise ReviewNotFoundError("Bill item not found")
        return bill

    def bill_payload(self, bill_identifier: str) -> dict[str, Any]:
        bill = self.bill(bill_identifier)
        return {
            "bill_id": str(bill.reference_bill_item_id), "bill_code_9": bill.bill_code_9,
            "bill_name": bill.bill_name, "appendix_code": bill.appendix_code,
            "appendix_name": bill.appendix_name, "section_code": bill.section_code,
            "section_name": bill.section_name, "unit": bill.unit,
            "project_feature_raw": bill.project_feature_raw,
            "quantity_calculation_rule": bill.quantity_calculation_rule,
            "work_content_raw": bill.work_content_raw,
            "source_heading_path": bill.source_heading_path,
            "source_table_index": bill.source_table_index,
            "review_status": enum_value(bill.review_status), "row_version": bill.row_version,
        }

    def authority_evidence(self, bill_identifier: str) -> dict[str, Any]:
        bill = self.bill(bill_identifier)
        document = self.session.scalar(select(SourceDocument).where(
            cast(SourceDocument.source_role, String) == "authority_source",
            SourceDocument.source_key.like("GB50854_AUTHORITY%"),
        ).order_by(SourceDocument.created_at).limit(1))
        if document is None:
            raise ReviewNotFoundError("Authority PDF not found")
        evidence = None
        candidates = self.session.scalars(select(SourcePageEvidence).where(
            SourcePageEvidence.source_document_id == document.source_document_id,
            SourcePageEvidence.evidence_type == "bill_authority_evidence",
        ).order_by(SourcePageEvidence.source_key))
        for item in candidates:
            payload = item.evidence_payload or {}
            backlog = payload.get("backlog") or {}
            if (
                backlog.get("bill_reference_id") == bill.source_key
                or backlog.get("bill_code_9") == bill.bill_code_9
            ):
                evidence = item
                break
        return {
            "bill_id": str(bill.reference_bill_item_id),
            "bill_reference_id": bill.source_key,
            "bill_code_9": bill.bill_code_9,
            "authority_document": {
                "source_document_id": str(document.source_document_id),
                "document_name": document.document_name,
                "source_role": enum_value(document.source_role),
                "authority_status": document.authority_status,
                "sha256": document.sha256,
                "source_available": bool(document.actual_path),
            },
            "official_pdf_page_no": evidence.page_no if evidence else None,
            "authority_verification_status": (
                evidence.evidence_status if evidence else "pending_evidence_link"
            ),
            "evidence_type": evidence.evidence_type if evidence else "bill_authority_evidence",
            "source_locator": evidence.source_locator if evidence else bill.source_heading_path,
            "evidence_link_status": (
                "located" if evidence and evidence.page_no else "pending_evidence_link"
            ),
        }


class MappingReviewRepository(BillReviewRepository):
    @staticmethod
    def _priority(edge: MappingCandidateEdge, candidate_count: int) -> tuple[str, str]:
        if edge.risk_level == "high" or edge.routing_class == "manual_review_required":
            return "P0", "high_risk_or_manual_review"
        if candidate_count >= 5:
            return "P1", "candidate_count>=5"
        return "P2", "low_risk_candidate"

    def mappings_for_bill(self, bill_identifier: str) -> dict[str, Any]:
        bill = self.bill(bill_identifier)
        original = list(self.session.execute(select(
            MappingCandidateEdge, ReferenceQuotaItem
        ).join(
            ReferenceQuotaItem,
            ReferenceQuotaItem.reference_quota_item_id == MappingCandidateEdge.reference_quota_item_id,
        ).where(
            MappingCandidateEdge.mapping_release_id == self.scope.mapping_release_id,
            MappingCandidateEdge.reference_bill_item_id == bill.reference_bill_item_id,
        ).order_by(MappingCandidateEdge.candidate_rank, MappingCandidateEdge.source_key)).all())
        edge_ids = [edge.mapping_candidate_edge_id for edge, _ in original]
        outbound = list(self.session.scalars(select(MappingDraftEdge).where(
            MappingDraftEdge.tenant_id == self.tenant_id,
            MappingDraftEdge.mapping_workspace_id == self.scope.workspace_id,
            MappingDraftEdge.mapping_candidate_edge_id.in_(edge_ids),
            MappingDraftEdge.draft_status != "reverted",
        ).order_by(MappingDraftEdge.created_at))) if edge_ids else []
        incoming = list(self.session.execute(select(
            MappingDraftEdge, MappingCandidateEdge, ReferenceQuotaItem
        ).join(
            MappingCandidateEdge,
            MappingCandidateEdge.mapping_candidate_edge_id == MappingDraftEdge.mapping_candidate_edge_id,
        ).join(
            ReferenceQuotaItem,
            ReferenceQuotaItem.reference_quota_item_id == MappingCandidateEdge.reference_quota_item_id,
        ).where(
            MappingDraftEdge.tenant_id == self.tenant_id,
            MappingDraftEdge.mapping_workspace_id == self.scope.workspace_id,
            MappingDraftEdge.target_bill_item_id == bill.reference_bill_item_id,
            MappingDraftEdge.action_type.in_(("copy", "move")),
            MappingDraftEdge.draft_status != "reverted",
        ).order_by(MappingDraftEdge.created_at)).all())
        all_edge_ids = list({*edge_ids, *(edge.mapping_candidate_edge_id for _, edge, _ in incoming)})
        review_states = list(self.session.scalars(select(MappingReviewState).where(
            MappingReviewState.tenant_id == self.tenant_id,
            MappingReviewState.mapping_candidate_edge_id.in_(all_edge_ids),
        ).order_by(MappingReviewState.review_cycle.desc()))) if all_edge_ids else []
        review_by_edge: dict[uuid.UUID, MappingReviewState] = {}
        for review in review_states:
            if review.mapping_candidate_edge_id is not None:
                review_by_edge.setdefault(review.mapping_candidate_edge_id, review)
        drafts_by_edge: dict[uuid.UUID, list[MappingDraftEdge]] = {}
        for draft in outbound:
            drafts_by_edge.setdefault(draft.mapping_candidate_edge_id, []).append(draft)
        rows: list[dict[str, Any]] = []
        for edge, quota in original:
            drafts = drafts_by_edge.get(edge.mapping_candidate_edge_id, [])
            hiding = next((d for d in reversed(drafts) if d.action_type in {"move", "exclude"}), None)
            priority, reason = self._priority(edge, len(original))
            rows.append(self._mapping_payload(
                edge, quota, bill, review_by_edge.get(edge.mapping_candidate_edge_id),
                row_origin="original_candidate", effective=hiding is None, draft=hiding,
                priority=priority, priority_reason=reason,
            ))
        for draft, edge, quota in incoming:
            priority, reason = self._priority(edge, len(original))
            rows.append(self._mapping_payload(
                edge, quota, bill, review_by_edge.get(edge.mapping_candidate_edge_id),
                row_origin=f"draft_{draft.action_type}", effective=True, draft=draft,
                priority=priority, priority_reason=reason,
            ))
        return {"bill": self.bill_payload(bill_identifier), "items": rows, "count": len(rows)}

    @staticmethod
    def _mapping_payload(
        edge: MappingCandidateEdge, quota: ReferenceQuotaItem, display_bill: ReferenceBillItem,
        review: MappingReviewState | None, *, row_origin: str, effective: bool,
        draft: MappingDraftEdge | None, priority: str, priority_reason: str,
    ) -> dict[str, Any]:
        return {
            "edge_id": str(edge.mapping_candidate_edge_id),
            "mapping_edge_id": str(edge.mapping_candidate_edge_id), "source_key": edge.source_key,
            "bill_id": str(display_bill.reference_bill_item_id),
            "bill_code_9": display_bill.bill_code_9,
            "quota_id": str(quota.reference_quota_item_id), "quota_uid": quota.quota_uid,
            "source_code": quota.source_code, "quota_name": quota.quota_name,
            "quota_unit": quota.unit, "volume_code": quota.volume_code,
            "quota_pdf_page_no": quota.pdf_page_no, "labor_fee": quota.labor_fee,
            "material_fee": quota.material_fee, "machine_fee": quota.machine_fee,
            "management_fee": quota.management_fee, "total_fee": quota.total_fee,
            "mapping_role": edge.mapping_role, "routing_class": edge.routing_class,
            "semantic_score": edge.semantic_score, "risk_level": edge.risk_level,
            "risk_reason": edge.risk_reason, "ai_mapping_explanation": edge.ai_mapping_explanation,
            "candidate_rank": edge.candidate_rank,
            "source_evidence_status": edge.source_evidence_status,
            "review_status": enum_value(review.review_status) if review else "not_reviewed",
            "review_row_version": review.row_version if review else 0,
            "row_version": edge.row_version, "row_origin": row_origin, "effective": effective,
            "draft_id": str(draft.mapping_draft_edge_id) if draft else None,
            "draft_action": draft.action_type if draft else None,
            "draft_status": draft.draft_status if draft else None,
            "draft_state": draft.draft_status if draft else "none",
            "relationship_type": draft.relation_type if draft else edge.mapping_role,
            "draft_row_version": draft.row_version if draft else None,
            "review_priority": priority, "priority_reason": priority_reason,
        }


class QuotaDetailRepository(ScopedReviewRepository):
    def quota(self, quota_identifier: str) -> ReferenceQuotaItem:
        filters = [ReferenceQuotaItem.quota_uid == quota_identifier]
        try:
            filters.append(ReferenceQuotaItem.reference_quota_item_id == uuid.UUID(quota_identifier))
        except ValueError:
            pass
        quota = self.session.scalar(select(ReferenceQuotaItem).where(
            ReferenceQuotaItem.reference_release_id == self.scope.reference_release_id,
            or_(*filters),
        ))
        if quota is None:
            raise ReviewNotFoundError("Quota item not found")
        return quota

    def detail(self, quota_identifier: str) -> dict[str, Any]:
        quota = self.quota(quota_identifier)
        document = self.session.get(SourceDocument, quota.source_document_id)
        return {
            "quota_id": str(quota.reference_quota_item_id), "quota_uid": quota.quota_uid,
            "source_code": quota.source_code, "quota_name": quota.quota_name,
            "specification": quota.specification, "unit": quota.unit,
            "volume_code": quota.volume_code, "chapter_code": quota.chapter_code,
            "section_code": quota.section_code, "pdf_page_no": quota.pdf_page_no,
            "labor_fee": quota.labor_fee, "material_fee": quota.material_fee,
            "machine_fee": quota.machine_fee, "management_fee": quota.management_fee,
            "total_fee": quota.total_fee, "source_role": enum_value(quota.source_role),
            "review_status": enum_value(quota.review_status),
            "source_document": {
                "source_document_id": str(document.source_document_id) if document else None,
                "document_name": document.document_name if document else None,
                "source_role": enum_value(document.source_role) if document else None,
                "authority_status": document.authority_status if document else None,
                "sha256": document.sha256 if document else None,
                "readable_status": document.readable_status if document else None,
            },
        }

    def resources(self, quota_identifier: str, *, page: int, page_size: int) -> dict[str, Any]:
        quota = self.quota(quota_identifier)
        statement = select(ReferenceQuotaResource).where(
            ReferenceQuotaResource.reference_release_id == self.scope.reference_release_id,
            ReferenceQuotaResource.reference_quota_item_id == quota.reference_quota_item_id,
        )
        total = int(self.session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        ) or 0)
        rows = list(self.session.scalars(statement.order_by(
            ReferenceQuotaResource.source_row_order,
            ReferenceQuotaResource.reference_quota_resource_id,
        ).offset((page - 1) * page_size).limit(page_size)))
        return {"quota": quota, "rows": rows, **page_meta(page, page_size, total)}

    def rules(self, quota_identifier: str, rule_type: str) -> dict[str, Any]:
        quota = self.quota(quota_identifier)
        if rule_type in {"conversion", "note"}:
            rules = list(self.session.scalars(select(ReferenceRuleBlock).where(
                ReferenceRuleBlock.reference_release_id == self.scope.reference_release_id,
                ReferenceRuleBlock.source_document_id == quota.source_document_id,
                ReferenceRuleBlock.rule_type == rule_type,
            ).order_by(ReferenceRuleBlock.pdf_page_no, ReferenceRuleBlock.source_key)))
            hierarchy = tuple(filter(None, (quota.section_code, quota.chapter_code)))
            rows = [
                (rule, None) for rule in rules
                if any(
                    locator == scope or scope.startswith(f"{locator}.")
                    for locator in (rule.source_locator or "",)
                    for scope in hierarchy
                    if locator
                )
            ]
        else:
            rows = self.session.execute(select(
                ReferenceRuleBlock, ReferenceScopeLink
            ).join(
                ReferenceScopeLink,
                ReferenceScopeLink.reference_rule_block_id == ReferenceRuleBlock.reference_rule_block_id,
            ).where(
                ReferenceRuleBlock.reference_release_id == self.scope.reference_release_id,
                ReferenceRuleBlock.source_document_id == quota.source_document_id,
                ReferenceRuleBlock.rule_type == rule_type,
                or_(
                    ReferenceScopeLink.reference_quota_item_id == quota.reference_quota_item_id,
                    and_(
                        ReferenceScopeLink.scope_start_code.is_not(None),
                        ReferenceScopeLink.scope_end_code.is_not(None),
                        quota.source_code >= ReferenceScopeLink.scope_start_code,
                        quota.source_code <= ReferenceScopeLink.scope_end_code,
                    ),
                ),
            ).order_by(ReferenceRuleBlock.pdf_page_no, ReferenceRuleBlock.source_key)).unique().all()
        items = [{
            "rule_id": str(rule.reference_rule_block_id), "rule_type": rule.rule_type,
            "rule_code": rule.rule_code, "rule_title": rule.rule_title,
            "rule_text": rule.rule_text, "pdf_page_no": rule.pdf_page_no,
            "source_locator": rule.source_locator,
            "scope_type": scope.scope_type if scope else "section_hierarchy",
            "scope_start_code": scope.scope_start_code if scope else rule.source_locator,
            "scope_end_code": scope.scope_end_code if scope else rule.source_locator,
            "scope_status": scope.scope_status if scope else "resolved_from_frozen_section_locator",
        } for rule, scope in rows]
        return {"items": items, "count": len(items)}

    def evidence(self, quota_identifier: str) -> dict[str, Any]:
        quota = self.quota(quota_identifier)
        document = self.session.get(SourceDocument, quota.source_document_id)
        evidence = list(self.session.scalars(select(SourcePageEvidence).where(
            SourcePageEvidence.source_document_id == quota.source_document_id,
            or_(SourcePageEvidence.page_no == quota.pdf_page_no, SourcePageEvidence.page_no.is_(None)),
        ).order_by(SourcePageEvidence.page_no, SourcePageEvidence.source_key).limit(100)))
        return {
            "quota_id": str(quota.reference_quota_item_id), "page_no": quota.pdf_page_no,
            "document": {
                "source_document_id": str(document.source_document_id) if document else None,
                "document_name": document.document_name if document else None,
                "source_role": enum_value(document.source_role) if document else None,
                "authority_status": document.authority_status if document else None,
                "sha256": document.sha256 if document else None,
                "page_count": document.page_count if document else None,
                "source_available": bool(document and document.actual_path),
            },
            "items": [{
                "evidence_id": str(item.source_page_evidence_id), "page_no": item.page_no,
                "printed_page_no": item.printed_page_no, "evidence_type": item.evidence_type,
                "source_locator": item.source_locator, "evidence_status": item.evidence_status,
            } for item in evidence], "count": len(evidence),
        }

    def document_path(self, quota_identifier: str) -> tuple[ReferenceQuotaItem, SourceDocument]:
        quota = self.quota(quota_identifier)
        document = self.session.get(SourceDocument, quota.source_document_id)
        if document is None:
            raise ReviewNotFoundError("Quota source document not found")
        return quota, document

    def authority_document(self) -> SourceDocument:
        document = self.session.scalar(select(SourceDocument).where(
            cast(SourceDocument.source_role, String) == "authority_source",
            SourceDocument.source_key.like("GB50854_AUTHORITY%"),
        ).order_by(SourceDocument.created_at).limit(1))
        if document is None:
            raise ReviewNotFoundError("Authority PDF not found")
        return document


class MappingAuditRepository(ScopedReviewRepository):
    def list(self, *, page: int, page_size: int) -> dict[str, Any]:
        statement = select(MappingAuditEvent).where(
            MappingAuditEvent.tenant_id == self.tenant_id,
            MappingAuditEvent.mapping_workspace_id == self.scope.workspace_id,
        )
        total = int(self.session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        ) or 0)
        rows = list(self.session.scalars(statement.order_by(
            MappingAuditEvent.created_at.desc(), MappingAuditEvent.source_audit_key,
        ).offset((page - 1) * page_size).limit(page_size)))
        return {"items": [{
            "audit_id": str(item.mapping_audit_event_id), "event_type": item.event_type,
            "event_at": item.event_at, "source_audit_key": item.source_audit_key,
            "draft_id": str(item.mapping_draft_edge_id) if item.mapping_draft_edge_id else None,
            "actor_user_id": str(item.actor_user_id), "before": item.before_payload,
            "after": item.after_payload, "created_at": item.created_at,
            "request_id": str(item.correlation_id) if item.correlation_id else None,
        } for item in rows], **page_meta(page, page_size, total)}


class MappingDraftRepository(ScopedReviewRepository):
    def _existing_idempotency(self, key: str) -> MappingAuditEvent | None:
        return self.session.scalar(select(MappingAuditEvent).where(
            MappingAuditEvent.tenant_id == self.tenant_id,
            MappingAuditEvent.source_audit_key == f"web:{key}",
        ))

    def _claim(
        self, *, key: str, actor_user_id: uuid.UUID, event_type: str,
        before_payload: dict[str, Any] | None, request_id: uuid.UUID | None,
    ) -> tuple[MappingAuditEvent, bool]:
        existing = self._existing_idempotency(key)
        if existing is not None:
            return existing, True
        event_id = uuid.uuid4()
        inserted = self.session.scalar(pg_insert(MappingAuditEvent).values(
            mapping_audit_event_id=event_id, tenant_id=self.tenant_id,
            mapping_workspace_id=self.scope.workspace_id, actor_user_id=actor_user_id,
            source_audit_key=f"web:{key}", event_type=event_type, event_at=now_iso(),
            before_payload=before_payload, after_payload={"status": "pending"},
            correlation_id=request_id, created_by=actor_user_id,
        ).on_conflict_do_nothing(
            constraint="uq_mapping_audit_event_tenant_id"
        ).returning(MappingAuditEvent.mapping_audit_event_id))
        if inserted is None:
            event = self._existing_idempotency(key)
            if event is None:
                raise ReviewConflictError("Idempotency claim failed")
            return event, True
        event = self.session.get(MappingAuditEvent, inserted)
        if event is None:
            raise ReviewConflictError("Idempotency audit event was not created")
        return event, False

    @staticmethod
    def _replay(event: MappingAuditEvent) -> dict[str, Any]:
        payload = dict(event.after_payload or {})
        payload["idempotent_replay"] = True
        return payload

    def create_draft(
        self, *, action: str, edge_id: uuid.UUID, target_bill_code_9: str | None,
        operation_reason: str, expected_row_version: int, idempotency_key: str,
        actor_user_id: uuid.UUID, request_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        if action not in ALLOWED_DRAFT_ACTIONS:
            raise ReviewValidationError("Unsupported Draft action")
        replay = self._existing_idempotency(idempotency_key)
        if replay is not None:
            return self._replay(replay)
        edge = self.session.scalar(select(MappingCandidateEdge).where(
            MappingCandidateEdge.mapping_candidate_edge_id == edge_id,
            MappingCandidateEdge.mapping_release_id == self.scope.mapping_release_id,
        ))
        if edge is None:
            raise ReviewNotFoundError("Mapping Candidate Edge not found")
        if edge.row_version != expected_row_version:
            raise ReviewConflictError("Mapping Candidate Edge row_version conflict")
        source_bill = self.session.get(ReferenceBillItem, edge.reference_bill_item_id)
        quota = self.session.get(ReferenceQuotaItem, edge.reference_quota_item_id)
        if source_bill is None or quota is None:
            raise ReviewNotFoundError("Mapping source entities not found")
        target_bill = None
        if action in {"copy", "move"}:
            if not target_bill_code_9:
                raise ReviewValidationError("Target bill is required")
            target_bill = self.session.scalar(select(ReferenceBillItem).where(
                ReferenceBillItem.reference_release_id == self.scope.reference_release_id,
                ReferenceBillItem.bill_code_9 == target_bill_code_9,
            ))
            if target_bill is None:
                raise ReviewValidationError("Target bill not found")
            if target_bill.reference_bill_item_id == source_bill.reference_bill_item_id:
                raise ReviewValidationError("Target bill must differ from source bill")
        event, duplicate = self._claim(
            key=idempotency_key, actor_user_id=actor_user_id, event_type=f"draft_{action}",
            before_payload={"edge_id": str(edge_id),
                            "source_bill_code_9": source_bill.bill_code_9,
                            "quota_uid": quota.quota_uid, "candidate_row_version": edge.row_version},
            request_id=request_id,
        )
        if duplicate:
            return self._replay(event)
        draft = MappingDraftEdge(
            mapping_draft_edge_id=uuid.uuid4(), tenant_id=self.tenant_id,
            mapping_workspace_id=self.scope.workspace_id,
            mapping_release_id=self.scope.mapping_release_id,
            mapping_candidate_edge_id=edge.mapping_candidate_edge_id,
            target_bill_item_id=target_bill.reference_bill_item_id if target_bill else None,
            source_draft_key=f"WEB-{uuid.uuid4().hex}", action_type=action,
            relation_type={"copy": "draft_copy", "move": "draft_move", "exclude": "draft_excluded"}[action],
            draft_status="active", review_status="not_reviewed",
            operation_reason=operation_reason.strip() or None, revision_no=1,
            source_payload={
                "origin": "postgres_web", "idempotency_key": idempotency_key,
                "edge_id": str(edge_id), "source_bill_code_9": source_bill.bill_code_9,
                "target_bill_code_9": target_bill.bill_code_9 if target_bill else "",
                "quota_uid": quota.quota_uid, "action_type": action,
            }, created_by=actor_user_id,
        )
        self.session.add(draft)
        self.session.flush()
        result = {"status": "created", "approved": False, "idempotent_replay": False,
                  "draft": {"draft_id": str(draft.mapping_draft_edge_id),
                            "edge_id": str(edge_id),
                            "source_bill_code_9": source_bill.bill_code_9,
                            "target_bill_code_9": target_bill.bill_code_9 if target_bill else "",
                            "quota_uid": quota.quota_uid, "action_type": action,
                            "relation_type": draft.relation_type,
                            "draft_status": draft.draft_status, "row_version": draft.row_version}}
        event.mapping_draft_edge_id = draft.mapping_draft_edge_id
        event.after_payload = result
        return result

    def restore(
        self, *, draft_id: uuid.UUID, expected_row_version: int, idempotency_key: str,
        actor_user_id: uuid.UUID, request_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        replay = self._existing_idempotency(idempotency_key)
        if replay is not None:
            return self._replay(replay)
        draft = self.session.scalar(select(MappingDraftEdge).where(
            MappingDraftEdge.mapping_draft_edge_id == draft_id,
            MappingDraftEdge.tenant_id == self.tenant_id,
            MappingDraftEdge.mapping_workspace_id == self.scope.workspace_id,
        ))
        if draft is None:
            raise ReviewNotFoundError("Mapping Draft not found")
        if draft.row_version != expected_row_version:
            raise ReviewConflictError("Mapping Draft row_version conflict")
        event, duplicate = self._claim(
            key=idempotency_key, actor_user_id=actor_user_id, event_type="draft_restore",
            before_payload={"draft_id": str(draft_id), "draft_status": draft.draft_status,
                            "row_version": draft.row_version},
            request_id=request_id,
        )
        if duplicate:
            return self._replay(event)
        changed = self.session.execute(update(MappingDraftEdge).where(
            MappingDraftEdge.mapping_draft_edge_id == draft_id,
            MappingDraftEdge.tenant_id == self.tenant_id,
            MappingDraftEdge.row_version == expected_row_version,
        ).values(draft_status="reverted", updated_by=actor_user_id))
        if changed.rowcount != 1:
            raise ReviewConflictError("Mapping Draft row_version conflict")
        self.session.flush()
        self.session.refresh(draft)
        payload = {"status": "restored", "approved": False, "idempotent_replay": False,
                   "draft": {"draft_id": str(draft_id), "draft_status": draft.draft_status,
                             "row_version": draft.row_version}}
        event.mapping_draft_edge_id = draft.mapping_draft_edge_id
        event.after_payload = payload
        return payload


class MappingReviewWriteRepository(MappingDraftRepository):
    def update_review(
        self, *, edge_id: uuid.UUID, review_status: str, comment: str,
        expected_row_version: int, idempotency_key: str, actor_user_id: uuid.UUID,
        request_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        if review_status not in ALLOWED_REVIEW_STATES:
            raise ReviewValidationError("Unsupported review status")
        replay = self._existing_idempotency(idempotency_key)
        if replay is not None:
            return self._replay(replay)
        edge = self.session.scalar(select(MappingCandidateEdge).where(
            MappingCandidateEdge.mapping_candidate_edge_id == edge_id,
            MappingCandidateEdge.mapping_release_id == self.scope.mapping_release_id,
        ))
        if edge is None:
            raise ReviewNotFoundError("Mapping Candidate Edge not found")
        review = self.session.scalar(select(MappingReviewState).where(
            MappingReviewState.tenant_id == self.tenant_id,
            MappingReviewState.mapping_candidate_edge_id == edge_id,
        ).order_by(MappingReviewState.review_cycle.desc()).limit(1))
        actual_version = review.row_version if review else 0
        if actual_version != expected_row_version:
            raise ReviewConflictError("Mapping Review row_version conflict")
        event, duplicate = self._claim(
            key=idempotency_key, actor_user_id=actor_user_id, event_type="review_state",
            before_payload={"edge_id": str(edge_id),
                            "review_status": enum_value(review.review_status) if review else "not_reviewed",
                            "row_version": actual_version},
            request_id=request_id,
        )
        if duplicate:
            return self._replay(event)
        if review is None:
            review = MappingReviewState(
                mapping_review_state_id=uuid.uuid4(), tenant_id=self.tenant_id,
                mapping_candidate_edge_id=edge_id, subject_type="mapping_candidate_edge",
                subject_id=str(edge_id), review_cycle=1, review_status=review_status,
                reviewer_user_id=actor_user_id, comment=comment.strip() or None,
                created_by=actor_user_id,
            )
            self.session.add(review)
        else:
            changed = self.session.execute(update(MappingReviewState).where(
                MappingReviewState.mapping_review_state_id == review.mapping_review_state_id,
                MappingReviewState.tenant_id == self.tenant_id,
                MappingReviewState.row_version == expected_row_version,
            ).values(review_status=review_status, reviewer_user_id=actor_user_id,
                     comment=comment.strip() or None, updated_by=actor_user_id))
            if changed.rowcount != 1:
                raise ReviewConflictError("Mapping Review row_version conflict")
        self.session.flush()
        self.session.refresh(review)
        payload = {"status": "review_updated", "approved": False,
                   "idempotent_replay": False,
                   "review": {"review_id": str(review.mapping_review_state_id),
                              "edge_id": str(edge_id),
                              "review_status": enum_value(review.review_status),
                              "comment": review.comment, "row_version": review.row_version}}
        event.after_payload = payload
        return payload
