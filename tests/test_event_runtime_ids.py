from uuid import UUID

from gerbera_sdk.events.buffer import Buffer
from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker


def test_event_runtime_ids_default_to_uuid4() -> None:
    event_bus = EventBus()
    event = Event(
        event_type="MCP",
        microcontroller_id="board-1",
        event_name="led_fbc1de23_f928a260",
    )
    event_worker = EventWorker()
    buffer = Buffer(
        table_name="hw201_fbc1de23_e8f75c2b",
        event_worker=event_worker,
    )

    assert UUID(event_bus.id).version == 4
    assert UUID(event.id).version == 4
    assert UUID(buffer.id).version == 4
    assert UUID(event_worker.id).version == 4
