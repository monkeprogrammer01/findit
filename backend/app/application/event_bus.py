from collections import defaultdict
from collections.abc import Callable
from typing import Any, Protocol

Handler = Callable[[Any], None]


class EventPublisher(Protocol):
    def publish(self, event: object) -> None: ...


class InProcessEventBus:
    def __init__(self) -> None:
        self._handlers: dict[type, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: object) -> None:
        for handler in self._handlers[type(event)]:
            handler(event)
