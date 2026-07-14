from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.orm import Session

from platform_db.models import (
    MappingCandidateEdge, MappingRelease, ReferenceBillItem, ReferenceQuotaItem,
    ReferenceQuotaResource, ReferenceRelease, ReferenceRuleBlock, ReferenceScopeLink,
    ReleaseManifest, StandardFamily,
)


class PlatformReadRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _page(statement, page: int, page_size: int, sort_column, descending: bool) -> tuple[Any, int]:
        count = select(func.count()).select_from(statement.order_by(None).subquery())
        total = int(statement.session.scalar(count) or 0) if hasattr(statement, "session") else -1
        order = sort_column.desc() if descending else sort_column.asc()
        return statement.order_by(order).offset((page - 1) * page_size).limit(page_size), total

    def bills(self, *, page: int, page_size: int, sort: str, q: str | None,
              release_id: str | None, source_family: str | None) -> dict[str, Any]:
        columns = {
            "bill_code_9": ReferenceBillItem.bill_code_9,
            "bill_name": ReferenceBillItem.bill_name,
            "appendix_code": ReferenceBillItem.appendix_code,
            "created_at": ReferenceBillItem.created_at,
        }
        descending = sort.startswith("-")
        sort_column = columns.get(sort.lstrip("-"), ReferenceBillItem.bill_code_9)
        statement = select(ReferenceBillItem).join(ReferenceRelease).join(StandardFamily)
        if q:
            pattern = f"%{q}%"
            statement = statement.where(or_(ReferenceBillItem.bill_code_9.ilike(pattern), ReferenceBillItem.bill_name.ilike(pattern)))
        if release_id:
            statement = statement.where(ReferenceBillItem.reference_release_id == release_id)
        if source_family:
            statement = statement.where(StandardFamily.family_code == source_family)
        total = int(self.session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
        rows = self.session.execute(
            statement.order_by(sort_column.desc() if descending else sort_column.asc())
            .offset((page - 1) * page_size).limit(page_size)
        ).scalars().all()
        return {"items": rows, "page": page, "page_size": page_size, "total": total}

    def bill(self, item_id: uuid.UUID):
        return self.session.get(ReferenceBillItem, item_id)

    def quotas(self, *, page: int, page_size: int, sort: str, q: str | None,
               release_id: str | None, source_family: str | None) -> dict[str, Any]:
        columns = {
            "source_code": ReferenceQuotaItem.source_code,
            "quota_name": ReferenceQuotaItem.quota_name,
            "volume_code": ReferenceQuotaItem.volume_code,
            "pdf_page_no": ReferenceQuotaItem.pdf_page_no,
        }
        descending = sort.startswith("-")
        sort_column = columns.get(sort.lstrip("-"), ReferenceQuotaItem.source_code)
        statement = select(ReferenceQuotaItem).join(ReferenceRelease).join(StandardFamily)
        if q:
            pattern = f"%{q}%"
            statement = statement.where(or_(ReferenceQuotaItem.source_code.ilike(pattern), ReferenceQuotaItem.quota_name.ilike(pattern)))
        if release_id:
            statement = statement.where(ReferenceQuotaItem.reference_release_id == release_id)
        if source_family:
            statement = statement.where(StandardFamily.family_code == source_family)
        total = int(self.session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
        rows = self.session.execute(
            statement.order_by(sort_column.desc() if descending else sort_column.asc())
            .offset((page - 1) * page_size).limit(page_size)
        ).scalars().all()
        return {"items": rows, "page": page, "page_size": page_size, "total": total}

    def quota(self, item_id: uuid.UUID):
        return self.session.get(ReferenceQuotaItem, item_id)

    def quota_resources(self, item_id: uuid.UUID, page: int, page_size: int) -> dict[str, Any]:
        base = select(ReferenceQuotaResource).where(ReferenceQuotaResource.reference_quota_item_id == item_id)
        total = int(self.session.scalar(select(func.count()).select_from(base.subquery())) or 0)
        rows = self.session.execute(
            base.order_by(ReferenceQuotaResource.source_row_order, ReferenceQuotaResource.reference_quota_resource_id)
            .offset((page - 1) * page_size).limit(page_size)
        ).scalars().all()
        return {"items": rows, "page": page, "page_size": page_size, "total": total}

    def quota_rules(self, item_id: uuid.UUID) -> list[ReferenceRuleBlock]:
        quota = self.session.get(ReferenceQuotaItem, item_id)
        if quota is None:
            return []
        statement = (
            select(ReferenceRuleBlock).join(ReferenceScopeLink)
            .where(
                ReferenceRuleBlock.source_document_id == quota.source_document_id,
                or_(
                    ReferenceScopeLink.reference_quota_item_id == item_id,
                    and_(
                        ReferenceScopeLink.scope_start_code.is_not(None),
                        ReferenceScopeLink.scope_end_code.is_not(None),
                        quota.source_code >= ReferenceScopeLink.scope_start_code,
                        quota.source_code <= ReferenceScopeLink.scope_end_code,
                    ),
                ),
            ).order_by(ReferenceRuleBlock.pdf_page_no, ReferenceRuleBlock.source_key)
        )
        return list(self.session.execute(statement).scalars().unique().all())

    def mappings(self, *, page: int, page_size: int, sort: str, q: str | None,
                 release_id: str | None, source_family: str | None) -> dict[str, Any]:
        statement = select(
            MappingCandidateEdge.mapping_candidate_edge_id,
            MappingCandidateEdge.mapping_release_id,
            MappingCandidateEdge.source_key,
            MappingCandidateEdge.mapping_role,
            MappingCandidateEdge.routing_class,
            MappingCandidateEdge.semantic_score,
            MappingCandidateEdge.source_evidence_status,
            MappingCandidateEdge.risk_level,
            MappingCandidateEdge.review_status,
            MappingCandidateEdge.candidate_rank,
            ReferenceBillItem.bill_code_9,
            ReferenceBillItem.bill_name,
            ReferenceQuotaItem.quota_uid,
            ReferenceQuotaItem.source_code.label("quota_source_code"),
            ReferenceQuotaItem.quota_name,
        ).join(ReferenceBillItem, MappingCandidateEdge.reference_bill_item_id == ReferenceBillItem.reference_bill_item_id
        ).join(ReferenceQuotaItem, MappingCandidateEdge.reference_quota_item_id == ReferenceQuotaItem.reference_quota_item_id
        ).join(MappingRelease, MappingCandidateEdge.mapping_release_id == MappingRelease.mapping_release_id
        ).join(ReferenceRelease, MappingRelease.reference_release_id == ReferenceRelease.reference_release_id
        ).join(StandardFamily, ReferenceRelease.standard_family_id == StandardFamily.standard_family_id)
        if q:
            pattern = f"%{q}%"
            statement = statement.where(or_(
                ReferenceBillItem.bill_code_9.ilike(pattern), ReferenceBillItem.bill_name.ilike(pattern),
                ReferenceQuotaItem.source_code.ilike(pattern), ReferenceQuotaItem.quota_name.ilike(pattern),
            ))
        if release_id:
            statement = statement.where(MappingCandidateEdge.mapping_release_id == release_id)
        if source_family:
            statement = statement.where(StandardFamily.family_code == source_family)
        total = int(self.session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
        sort_columns = {
            "candidate_rank": MappingCandidateEdge.candidate_rank,
            "semantic_score": MappingCandidateEdge.semantic_score,
            "risk_level": MappingCandidateEdge.risk_level,
            "bill_code_9": ReferenceBillItem.bill_code_9,
        }
        descending = sort.startswith("-")
        column = sort_columns.get(sort.lstrip("-"), ReferenceBillItem.bill_code_9)
        rows = self.session.execute(
            statement.order_by(column.desc() if descending else column.asc(), MappingCandidateEdge.source_key)
            .offset((page - 1) * page_size).limit(page_size)
        ).mappings().all()
        return {"items": list(rows), "page": page, "page_size": page_size, "total": total}

    def releases(self) -> dict[str, list[Any]]:
        return {
            "reference": list(self.session.execute(select(ReferenceRelease)).scalars()),
            "mapping": list(self.session.execute(select(MappingRelease)).scalars()),
            "manifest": list(self.session.execute(select(ReleaseManifest)).scalars()),
        }

