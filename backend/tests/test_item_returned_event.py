from sqlalchemy import func, select

from app.application.event_bus import InProcessEventBus
from app.application.return_statistics import ReturnStatisticsConsumer, returned_count
from app.domain.events import ItemReturned
from app.infrastructure.db.models import ItemCategory, ProcessedEvent
from app.interface.api.deps import DbSession
from app.interface.api.events import get_event_bus
from app.main import app
from tests.helpers import ADMIN, create_found_item
from tests.test_claims import submit


def test_handover_publishes_item_returned_and_updates_statistics(client, session_factory):
    published = []

    def bus_with_spy(db: DbSession) -> InProcessEventBus:
        bus = InProcessEventBus()
        bus.subscribe(ItemReturned, published.append)
        bus.subscribe(ItemReturned, ReturnStatisticsConsumer(db).handle)
        return bus

    app.dependency_overrides[get_event_bus] = bus_with_spy
    item = create_found_item(client)
    claim = submit(client, item["id"]).json()
    client.post(f"/claims/{claim['id']}/approve", headers=ADMIN)

    response = client.post(
        f"/claims/{claim['id']}/handover",
        json={
            "verification_method": "student_id_in_person",
            "recipient_name": "Yerkebulan Kenzhegali",
            "recipient_student_id": "student001",
        },
        headers=ADMIN,
    )
    assert response.status_code == 201

    assert len(published) == 1
    event = published[0]
    assert event.found_item_id == item["id"]
    assert event.claim_id == claim["id"]
    assert event.category == "electronics"

    with session_factory() as session:
        assert returned_count(session, ItemCategory.electronics) == 1


def test_same_event_delivered_twice_is_counted_once(session_factory):
    event = ItemReturned.new(found_item_id=1, claim_id=1, category="keys")

    with session_factory() as session:
        bus = InProcessEventBus()
        bus.subscribe(ItemReturned, ReturnStatisticsConsumer(session).handle)
        bus.publish(event)
        bus.publish(event)

    with session_factory() as session:
        assert returned_count(session, ItemCategory.keys) == 1
        processed = session.scalar(select(func.count()).select_from(ProcessedEvent))
        assert processed == 1
