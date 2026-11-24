from typing import Annotated

from fastapi import Depends

from app.application.event_bus import InProcessEventBus
from app.application.return_statistics import ReturnStatisticsConsumer
from app.domain.events import ItemReturned
from app.interface.api.deps import DbSession


def get_event_bus(db: DbSession) -> InProcessEventBus:
    bus = InProcessEventBus()
    bus.subscribe(ItemReturned, ReturnStatisticsConsumer(db).handle)
    return bus


Events = Annotated[InProcessEventBus, Depends(get_event_bus)]
