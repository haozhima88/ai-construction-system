from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.db_service import (
    IMPORT_REVIEW_STATUSES,
    bulk_update_import_review_status,
    count_import_review_records,
    get_import_review_stats,
    query_import_review_records,
    update_import_review_status,
)


import_review_router = APIRouter()


class ReviewStatusUpdate(BaseModel):
    review_status: str


class BulkReviewStatusUpdate(BaseModel):
    record_ids: list[int]
    review_status: str


def _validate_review_status(review_status: str) -> None:
    if review_status not in IMPORT_REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail="invalid review_status")


@import_review_router.get("/import-review/records")
def get_import_review_records(
    parse_status: str | None = None,
    review_status: str | None = None,
    keyword: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if review_status is not None:
        _validate_review_status(review_status)

    total = count_import_review_records(
        parse_status=parse_status,
        review_status=review_status,
        keyword=keyword,
    )
    records = query_import_review_records(
        parse_status=parse_status,
        review_status=review_status,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )

    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": records,
    }


@import_review_router.get("/import-review/stats")
def get_import_review_stats_api():
    stats = get_import_review_stats()
    return {
        "success": True,
        **stats,
    }


@import_review_router.patch("/import-review/records/{record_id}/review-status")
def patch_import_review_status(record_id: int, payload: ReviewStatusUpdate):
    _validate_review_status(payload.review_status)

    updated = update_import_review_status(record_id, payload.review_status)
    if updated is None:
        raise HTTPException(status_code=404, detail="record not found")

    return {
        "success": True,
        **updated,
    }


@import_review_router.post("/import-review/records/bulk-review-status")
def post_bulk_import_review_status(payload: BulkReviewStatusUpdate):
    _validate_review_status(payload.review_status)

    if not payload.record_ids:
        raise HTTPException(status_code=400, detail="record_ids cannot be empty")
    if len(payload.record_ids) > 500:
        raise HTTPException(status_code=400, detail="record_ids cannot exceed 500")

    updated_count = bulk_update_import_review_status(
        payload.record_ids,
        payload.review_status,
    )

    return {
        "success": True,
        "updated_count": updated_count,
    }
