import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ItemReturned:
    event_id: str
    occurred_at: datetime
    found_item_id: int
    claim_id: int
    category: str

    @classmethod
    def new(cls, *, found_item_id: int, claim_id: int, category: str) -> "ItemReturned":
        return cls(
            event_id=str(uuid.uuid4()),
            occurred_at=datetime.now(UTC),
            found_item_id=found_item_id,
            claim_id=claim_id,
            category=category,
        )
