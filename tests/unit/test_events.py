import asyncio
import threading
from types import SimpleNamespace

import pytest

from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_worker import EventWorker, WriteJob
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.events.reactions.reaction import Reaction
from gerbera_sdk.events.reactions.reaction_callback import ReactionCallback
from gerbera_sdk.events.reactions.reaction_condition import (
    OperatorEnum,
    ReactionCondition,
)


class FakeDatabase:
    def write_database_table(self, table_name, payload) -> None:
        pass


async def return_value(mcp_url: str, value: float) -> float:
    return value


def register_test_reaction(reaction_bus: ReactionBus) -> None:
    reaction_bus.register_reaction(
        "STREAM",
        "board-1",
        "sensor",
        Reaction(
            condition=ReactionCondition(
                expected=1.0,
                operator=OperatorEnum.EQUAL,
            ),
            callback=ReactionCallback(
                callback=return_value,
                mcp_url="https://hardware.example.com/mcp",
            ),
        ),
    )


def test_event_bus_rejects_duplicate_and_missing_events() -> None:
    event_bus = EventBus()
    event = Event(
        event_type="MCP",
        microcontroller_id="board-1",
        event_name="sensor",
        streamable=False,
        table_name="sensor",
        event_worker=EventWorker(database=FakeDatabase()),
        latest_val=None,
    )
    event_bus.write_event("MCP", "board-1", "sensor", event)

    with pytest.raises(RuntimeError, match="already exists"):
        event_bus.write_event("MCP", "board-1", "sensor", event)

    with pytest.raises(RuntimeError, match="does not exist"):
        event_bus.get_event("MCP", "board-1", "missing")


def test_event_worker_requeues_a_failed_write_until_retry_limit() -> None:
    class FailingDatabase:
        def write_database_table(self, table_name, payload) -> None:
            raise OSError("database unavailable")

    worker = EventWorker(
        database=FailingDatabase(),
        max_retries=1,
        retry_delay_seconds=0,
    )

    worker.process_job(WriteJob("readings", [{"value": "1"}]))
    retry = worker.queue.get_nowait()
    assert retry.retry_count == 1

    with pytest.raises(RuntimeError, match="Failed to Write to Database"):
        worker.process_job(retry)


def test_listener_rejects_duplicate_payload_keys() -> None:
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        serial_pool={},
        threads={},
        event_bus=EventBus(),
        reaction_bus=ReactionBus(),
    )

    assert listener.parse_payload("invalid") is None
    with pytest.raises(ValueError, match="Key already exists"):
        listener.parse_payload("MCP,sensor,value:1,value:2")


def test_listener_updates_registered_reaction_bus_value() -> None:
    reaction_bus = ReactionBus()
    register_test_reaction(reaction_bus)
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        serial_pool={},
        threads={},
        event_bus=EventBus(),
        reaction_bus=reaction_bus,
    )

    reaction_future = listener.dispatch_event_to_reaction_bus(
        "STREAM",
        "board-1",
        "sensor",
        {"value": "1"},
    )
    reaction_future.result(timeout=1)

    assert reaction_bus.latest_values[("STREAM", "board-1", "sensor")] == 1.0
    listener.stop_listeners()


def test_listener_does_not_wait_for_async_reaction_callback() -> None:
    callback_started = threading.Event()
    release_callback = threading.Event()

    async def callback(
        mcp_url: str,
        value: float,
    ) -> float:
        callback_started.set()
        while not release_callback.is_set():
            await asyncio.sleep(0.001)
        return value

    reaction_bus = ReactionBus()
    reaction_bus.register_reaction(
        "STREAM",
        "board-1",
        "sensor",
        Reaction(
            condition=ReactionCondition(
                expected=1.0,
                operator=OperatorEnum.EQUAL,
            ),
            callback=ReactionCallback(
                callback=callback,
                mcp_url="https://hardware.example.com/mcp",
            ),
        ),
    )
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        serial_pool={},
        threads={},
        event_bus=EventBus(),
        reaction_bus=reaction_bus,
    )

    reaction_future = listener.dispatch_event_to_reaction_bus(
        "STREAM",
        "board-1",
        "sensor",
        {"value": "1"},
    )

    assert callback_started.wait(timeout=1)
    assert reaction_future.done() is False

    release_callback.set()
    assert reaction_future.result(timeout=1) == 1.0
    listener.stop_listeners()


def test_listener_logs_async_reaction_callback_failure(caplog) -> None:
    async def callback(mcp_url: str, value: float) -> None:
        raise RuntimeError("servo unavailable")

    reaction_bus = ReactionBus()
    reaction_bus.register_reaction(
        "STREAM",
        "board-1",
        "sensor",
        Reaction(
            condition=ReactionCondition(
                expected=1.0,
                operator=OperatorEnum.EQUAL,
            ),
            callback=ReactionCallback(
                callback=callback,
                mcp_url="https://hardware.example.com/mcp",
            ),
        ),
    )
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        serial_pool={},
        threads={},
        event_bus=EventBus(),
        reaction_bus=reaction_bus,
    )

    reaction_future = listener.dispatch_event_to_reaction_bus(
        "STREAM",
        "board-1",
        "sensor",
        {"value": "1"},
    )

    with pytest.raises(RuntimeError, match="servo unavailable"):
        reaction_future.result(timeout=1)

    listener.stop_listeners()
    assert "Reaction evaluation failed" in caplog.text
    assert "servo unavailable" in caplog.text


def test_listener_fails_when_transport_shutdown_fails() -> None:
    class FailingConnection:
        def destroy(self) -> None:
            raise OSError("close failed")

    class Thread:
        joined = False
        name = "test-listener"

        def join(self, timeout: float) -> None:
            self.joined = True

        def is_alive(self) -> bool:
            return False

    thread = Thread()
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        serial_pool={"board-1": FailingConnection()},
        threads={"board-1": thread},
        event_bus=EventBus(),
        reaction_bus=ReactionBus(),
    )

    with pytest.raises(OSError, match="close failed"):
        listener.stop_listeners()

    assert thread.joined is False
    assert listener.threads == {"board-1": thread}


def test_listener_keeps_a_thread_tracked_when_join_times_out() -> None:
    class Thread:
        name = "stuck-listener"

        def join(self, timeout: float) -> None:
            return None

        def is_alive(self) -> bool:
            return True

    thread = Thread()
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        serial_pool={},
        threads={"board-1": thread},
        event_bus=EventBus(),
        reaction_bus=ReactionBus(),
    )

    with pytest.raises(RuntimeError, match="did not stop"):
        listener.stop_listeners(timeout=0)

    assert listener.threads == {"board-1": thread}
