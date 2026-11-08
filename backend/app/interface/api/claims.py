from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from pydantic import BaseModel, Field, StringConstraints

from app.application import claims as service
from app.application.errors import BusinessRuleError
from app.application.notifications import Notifier, notify
from app.infrastructure.db.models import (
    Claim,
    ClaimStatus,
    FoundItem,
    FoundItemStatus,
    User,
)
from app.infrastructure.notifications.gateway import get_notifier
from app.interface.api.deps import CurrentUser, DbSession, DeskAdmin

router = APIRouter(tags=["claims"])

Notifications = Annotated[Notifier, Depends(get_notifier)]
Answer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class AnswerIn(BaseModel):
    question_id: int
    answer: Answer


class ClaimCreate(BaseModel):
    answers: list[AnswerIn] = Field(min_length=1, max_length=5)


class ItemBrief(BaseModel):
    id: int
    title: str
    status: FoundItemStatus


class Pickup(BaseModel):
    """FE-7: где и как забрать вещь по одобренной заявке."""

    storage_desk: str
    instructions: str


class MyClaimOut(BaseModel):
    id: int
    status: ClaimStatus
    created_at: datetime
    decided_at: datetime | None
    item: ItemBrief
    my_answers: dict[int, str]
    pickup: Pickup | None


class ClaimSummary(BaseModel):
    id: int
    status: ClaimStatus
    claimant_id: int
    created_at: datetime
    decided_at: datetime | None
    item: ItemBrief


class ReviewRowOut(BaseModel):
    question_id: int
    question: str
    correct_answer: str
    claimant_answer: str | None


class ClaimDetail(ClaimSummary):
    """Экран разбора заявки: ответы претендента рядом с правильными (FE-10)."""

    claimant_campus_id: str
    storage_desk: str
    storage_cell: str
    answers: list[ReviewRowOut]


def _brief(item: FoundItem) -> ItemBrief:
    return ItemBrief(id=item.id, title=item.title, status=item.status)


def _summary(claim: Claim, item: FoundItem) -> ClaimSummary:
    return ClaimSummary(
        id=claim.id,
        status=claim.status,
        claimant_id=claim.claimant_id,
        created_at=claim.created_at,
        decided_at=claim.decided_at,
        item=_brief(item),
    )


def _mine(claim: Claim, item: FoundItem) -> MyClaimOut:
    pickup = None
    if claim.status == ClaimStatus.approved:
        pickup = Pickup(
            storage_desk=item.storage_desk,
            instructions=(
                f"Come to the lost and found desk {item.storage_desk} with your student ID "
                "card. The desk admin checks it and hands the item over."
            ),
        )
    return MyClaimOut(
        id=claim.id,
        status=claim.status,
        created_at=claim.created_at,
        decided_at=claim.decided_at,
        item=_brief(item),
        my_answers=service.parse_answers(claim),
        pickup=pickup,
    )


def _detail(db: DbSession, claim: Claim) -> ClaimDetail:
    item = db.get(FoundItem, claim.found_item_id)
    claimant = db.get(User, claim.claimant_id)
    return ClaimDetail(
        **_summary(claim, item).model_dump(),
        claimant_campus_id=claimant.campus_id,
        storage_desk=item.storage_desk,
        storage_cell=item.storage_cell,
        answers=[ReviewRowOut(**vars(row)) for row in service.review_rows(db, claim)],
    )


@router.post(
    "/found-items/{item_id}/claims",
    response_model=MyClaimOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_claim(item_id: int, data: ClaimCreate, user: CurrentUser, db: DbSession):
    answers = {a.question_id: a.answer for a in data.answers}
    if len(answers) != len(data.answers):
        raise BusinessRuleError("Each question can be answered only once")
    claim = service.submit_claim(db, user, item_id, answers)
    return _mine(claim, db.get(FoundItem, item_id))


@router.get("/claims/me", response_model=list[MyClaimOut])
def list_my_claims(user: CurrentUser, db: DbSession):
    return [_mine(c, i) for c, i in service.list_my_claims(db, user.id)]


@router.get("/claims", response_model=list[ClaimSummary])
def list_claims(
    admin: DeskAdmin,
    db: DbSession,
    claim_status: Annotated[ClaimStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return [_summary(c, i) for c, i in service.list_claims(db, claim_status, limit, offset)]


@router.get("/claims/{claim_id}", response_model=ClaimDetail)
def read_claim(claim_id: int, admin: DeskAdmin, db: DbSession):
    return _detail(db, service.get_claim(db, claim_id))


@router.post("/claims/{claim_id}/approve", response_model=ClaimDetail)
def approve_claim(
    claim_id: int,
    admin: DeskAdmin,
    db: DbSession,
    background: BackgroundTasks,
    notifier: Notifications,
):
    claim = service.get_claim(db, claim_id)
    auto_rejected = service.approve(db, claim, admin.id)
    item = db.get(FoundItem, claim.found_item_id)
    notify(
        background,
        notifier,
        db.get(User, claim.claimant_id),
        "claim_approved",
        item_title=item.title,
        storage_desk=item.storage_desk,
    )
    for other in auto_rejected:
        notify(
            background,
            notifier,
            db.get(User, other.claimant_id),
            "claim_rejected",
            item_title=item.title,
        )
    return _detail(db, claim)


@router.post("/claims/{claim_id}/reject", response_model=ClaimDetail)
def reject_claim(
    claim_id: int,
    admin: DeskAdmin,
    db: DbSession,
    background: BackgroundTasks,
    notifier: Notifications,
):
    claim = service.get_claim(db, claim_id)
    service.reject(db, claim, admin.id)
    item = db.get(FoundItem, claim.found_item_id)
    notify(
        background,
        notifier,
        db.get(User, claim.claimant_id),
        "claim_rejected",
        item_title=item.title,
    )
    return _detail(db, claim)
