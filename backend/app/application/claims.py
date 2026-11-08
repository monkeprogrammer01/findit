"""FR-04: заявки на найденные вещи. Переходы статусов решает domain/claim_states.py."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.errors import BusinessRuleError, NotFoundError
from app.application.found_items import get_item, get_questions
from app.domain.claim_states import InvalidTransition, Transition, can_submit_claim, state_for
from app.infrastructure.db.models import (
    Claim,
    ClaimStatus,
    FoundItem,
    FoundItemStatus,
    User,
)


@dataclass
class ReviewRow:
    """Строка для экрана разбора: вопрос, правильный ответ и ответ претендента рядом."""

    question_id: int
    question: str
    correct_answer: str
    claimant_answer: str | None


def submit_claim(db: Session, user: User, item_id: int, answers: dict[int, str]) -> Claim:
    item = get_item(db, item_id)
    if not can_submit_claim(item.status):
        raise BusinessRuleError(f"Item is {item.status.value} and cannot be claimed")

    previous = db.scalars(
        select(Claim).where(Claim.found_item_id == item_id, Claim.claimant_id == user.id)
    ).all()
    if any(c.status == ClaimStatus.pending for c in previous):
        raise BusinessRuleError("You already have a pending claim for this item")
    # после отказа повторно не подать: иначе ответы можно подбирать перебором
    if any(c.status == ClaimStatus.rejected for c in previous):
        raise BusinessRuleError("Your claim for this item was already rejected")

    question_ids = {q.id for q in get_questions(db, item_id)}
    if set(answers) != question_ids:
        raise BusinessRuleError("Answer every verification question of this item exactly once")

    claim = Claim(
        found_item_id=item_id,
        claimant_id=user.id,
        # ключи JSON — строки, поэтому id вопроса храним как строку
        answers=json.dumps({str(k): v for k, v in answers.items()}, ensure_ascii=False),
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def get_claim(db: Session, claim_id: int) -> Claim:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise NotFoundError("Claim not found")
    return claim


def list_my_claims(db: Session, user_id: int) -> list[tuple[Claim, FoundItem]]:
    rows = db.execute(
        select(Claim, FoundItem)
        .join(FoundItem, FoundItem.id == Claim.found_item_id)
        .where(Claim.claimant_id == user_id)
        .order_by(Claim.created_at.desc(), Claim.id.desc())
    )
    return [(c, i) for c, i in rows]


def list_claims(
    db: Session, status: ClaimStatus | None, limit: int, offset: int
) -> list[tuple[Claim, FoundItem]]:
    """Очередь заявок для стойки: старые сначала, чтобы их разбирали по порядку."""
    stmt = select(Claim, FoundItem).join(FoundItem, FoundItem.id == Claim.found_item_id)
    if status is not None:
        stmt = stmt.where(Claim.status == status)
    stmt = stmt.order_by(Claim.created_at, Claim.id).limit(limit).offset(offset)
    return [(c, i) for c, i in db.execute(stmt)]


def parse_answers(claim: Claim) -> dict[int, str]:
    return {int(k): v for k, v in json.loads(claim.answers).items()}


def review_rows(db: Session, claim: Claim) -> list[ReviewRow]:
    answers = parse_answers(claim)
    return [
        ReviewRow(q.id, q.question, q.correct_answer, answers.get(q.id))
        for q in get_questions(db, claim.found_item_id)
    ]


def _apply(db: Session, claim: Claim, transition: Transition, admin_id: int) -> list[Claim]:
    """Применяет переход к заявке и вещи. Возвращает автоматически отклонённые заявки."""
    item = db.get(FoundItem, claim.found_item_id)
    claim.status = ClaimStatus(transition.claim_status)
    if transition.claim_status in ("approved", "rejected"):
        claim.decided_by_id = admin_id
        claim.decided_at = datetime.now(UTC)
    if transition.item_status is not None:
        item.status = FoundItemStatus(transition.item_status)

    auto_rejected = []
    if transition.reject_other_pending:
        others = db.scalars(
            select(Claim).where(
                Claim.found_item_id == claim.found_item_id,
                Claim.id != claim.id,
                Claim.status == ClaimStatus.pending,
            )
        )
        for other in others:
            other_transition = state_for(other.status).reject()
            other.status = ClaimStatus(other_transition.claim_status)
            other.decided_by_id = admin_id
            other.decided_at = datetime.now(UTC)
            auto_rejected.append(other)
    return auto_rejected


def _transition(claim: Claim, action: str) -> Transition:
    try:
        return getattr(state_for(claim.status), action)()
    except InvalidTransition as exc:
        raise BusinessRuleError(str(exc)) from exc


def approve(db: Session, claim: Claim, admin_id: int) -> list[Claim]:
    auto_rejected = _apply(db, claim, _transition(claim, "approve"), admin_id)
    db.commit()
    return auto_rejected


def reject(db: Session, claim: Claim, admin_id: int) -> None:
    _apply(db, claim, _transition(claim, "reject"), admin_id)
    db.commit()
