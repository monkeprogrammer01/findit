"""State pattern: жизненный цикл заявки на найденную вещь (FR-04, FR-05).

    pending --approve--> approved --hand_over--> returned
       |
       +--reject--> rejected

Каждое состояние отвечает на одни и те же вопросы: можно ли одобрить, отклонить,
выдать. Базовый класс по умолчанию запрещает всё, поэтому состояние описывает
только то, что в нём разрешено. Например, вторую выдачу или одобрение уже
отклонённой заявки не нужно отдельно проверять в каждом эндпоинте: их запрещает
сам класс состояния.

Слой domain не знает про базу данных: состояние возвращает Transition, а прикладной
слой (application/claims.py) применяет его к записям в базе.
"""

from dataclasses import dataclass

# Пока вещь на хранении, на неё можно подать заявку
CLAIMABLE_ITEM_STATUSES = frozenset({"stored", "eligible_for_disposal"})


class InvalidTransition(Exception):
    def __init__(self, action: str, status: str):
        super().__init__(f"Cannot {action} a claim that is {status}")
        self.action = action
        self.status = status


@dataclass(frozen=True)
class Transition:
    claim_status: str
    item_status: str | None = None  # None: статус вещи не меняется
    reject_other_pending: bool = False


class ClaimState:
    status: str

    def approve(self) -> Transition:
        raise InvalidTransition("approve", self.status)

    def reject(self) -> Transition:
        raise InvalidTransition("reject", self.status)

    def hand_over(self) -> Transition:
        raise InvalidTransition("hand over", self.status)


class PendingState(ClaimState):
    status = "pending"

    def approve(self) -> Transition:
        # У вещи один владелец: остальные ожидающие заявки отклоняются, вещь резервируется
        return Transition("approved", item_status="claimed", reject_other_pending=True)

    def reject(self) -> Transition:
        return Transition("rejected")


class ApprovedState(ClaimState):
    status = "approved"

    def hand_over(self) -> Transition:
        return Transition("returned", item_status="returned")


class RejectedState(ClaimState):
    status = "rejected"  # конечное состояние


class ReturnedState(ClaimState):
    status = "returned"  # конечное состояние


_STATES = {s.status: s for s in (PendingState(), ApprovedState(), RejectedState(), ReturnedState())}


def state_for(status: str) -> ClaimState:
    return _STATES[str(status)]


def can_submit_claim(item_status: str) -> bool:
    return str(item_status) in CLAIMABLE_ITEM_STATUSES
