from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .security_audit import record_security_event


class SeparationOfDutyViolation(ValueError):
    pass


@dataclass(frozen=True)
class DutyActors:
    creator_id: uuid.UUID | None = None
    editor_id: uuid.UUID | None = None
    submitter_id: uuid.UUID | None = None
    reviewer_id: uuid.UUID | None = None
    approver_id: uuid.UUID | None = None


class SeparationOfDutyPolicy:
    @staticmethod
    def validate_quota(actors: DutyActors) -> None:
        if actors.creator_id and actors.reviewer_id == actors.creator_id:
            raise SeparationOfDutyViolation("quota_creator_cannot_review")
        if actors.editor_id and actors.approver_id == actors.editor_id:
            raise SeparationOfDutyViolation("quota_editor_cannot_approve")
        if actors.reviewer_id and actors.approver_id == actors.reviewer_id:
            raise SeparationOfDutyViolation("quota_reviewer_cannot_approve")

    @staticmethod
    def validate_price(actors: DutyActors) -> None:
        if actors.submitter_id and actors.approver_id == actors.submitter_id:
            raise SeparationOfDutyViolation("price_submitter_cannot_approve")

    @classmethod
    def enforce(
        cls,
        policy: str,
        actors: DutyActors,
        *,
        break_glass: bool = False,
        break_glass_reason: str | None = None,
        session: Session | None = None,
        tenant_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
    ) -> None:
        validator = cls.validate_quota if policy == "enterprise_quota" else cls.validate_price
        try:
            validator(actors)
        except SeparationOfDutyViolation:
            if not break_glass:
                raise
            if not break_glass_reason or not break_glass_reason.strip():
                raise SeparationOfDutyViolation("break_glass_reason_required")
            if session is None or tenant_id is None or actor_user_id is None:
                raise SeparationOfDutyViolation("break_glass_audit_context_required")
            record_security_event(
                session,
                tenant_id=tenant_id,
                app_user_id=actor_user_id,
                action="break_glass_used",
                object_type=policy,
                result="override",
                reason=break_glass_reason,
                actor_user_id=actor_user_id,
            )
