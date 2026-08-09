import asyncio
import threading
from types import SimpleNamespace

import pytest

from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_store import EventStore
from gerbera_sdk.events.event_worker import EventWorker, WriteJob
from gerbera_sdk.events.rules.rule_buffer import RuleBuffer
from gerbera_sdk.events.rules.rule_bus import RuleBus
from gerbera_sdk.events.rules.rule import Rule
from gerbera_sdk.events.rules.rule_callback import RuleCallback
from gerbera_sdk.events.rules.rule_condition import (
    OperatorEnum,
    RuleCondition,
)


class FakeDatabase:
    def write_database_table(self, table_name, payload) -> None:
        pass


def test_event_bus_rejects_duplicate_and_missing_events() -> None:
    event_bus = EventBus()
    event = Event(
        event_type="MCP",
        microcontroller_id="board-1",
        event_name="sensor",
        streamable=False,
        table_name="sensor",
        event_worker=EventWorker(database=FakeDatabase()),
        event_store=EventStore(),
    )
    event_bus.add_event("MCP", "board-1", "sensor", event)

    with pytest.raises(RuntimeError, match="already exists"):
        event_bus.add_event("MCP", "board-1", "sensor", event)

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

    worker._process_job(WriteJob("readings", [{"value": "1"}]))
    retry = worker._queue.get_nowait()
    assert retry.retry_count == 1

    with pytest.raises(OSError, match="database unavailable"):
        worker._process_job(retry)


def test_listener_rejects_duplicate_payload_keys() -> None:
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        serial_pool={},
        threads={},
        event_bus=EventBus(),
        rule_buffer=RuleBuffer(RuleBus()),
    )

    assert listener.parse_payload("invalid") is None
    with pytest.raises(ValueError, match="Key already exists"):
        listener.parse_payload("MCP,sensor,value:1,value:2")


def test_listener_updates_registered_rule_buffer_value() -> None:
    rule_buffer = RuleBuffer(RuleBus())
    rule_buffer.register_event_in_buffer("STREAM", "board-1", "sensor")
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        serial_pool={},
        threads={},
        event_bus=EventBus(),
        rule_buffer=rule_buffer,
    )

    rule_future = listener.dispatch_event_to_rule_buffer(
        "STREAM",
        "board-1",
        "sensor",
        {"value": "1"},
    )
    rule_future.result(timeout=1)

    assert rule_buffer.buffer[("STREAM", "board-1", "sensor")] == 1.0
    listener.stop_listeners()


def test_listener_does_not_wait_for_async_rule_callback() -> None:
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

    rule_bus = RuleBus()
    rule_bus.register_rule(
        "STREAM",
        "board-1",
        "sensor",
        Rule(
            condition=RuleCondition(
                expected=1.0,
                operator=OperatorEnum.EQUAL,
            ),
            callback=RuleCallback(
                callback=callback,
                mcp_url="https://hardware.example.com/mcp",
            ),
        ),
    )
    rule_buffer = RuleBuffer(rule_bus)
    rule_buffer.register_event_in_buffer("STREAM", "board-1", "sensor")
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        serial_pool={},
        threads={},
        event_bus=EventBus(),
        rule_buffer=rule_buffer,
    )

    rule_future = listener.dispatch_event_to_rule_buffer(
        "STREAM",
        "board-1",
        "sensor",
        {"value": "1"},
    )

    assert callback_started.wait(timeout=1)
    assert rule_future.done() is False

    release_callback.set()
    assert rule_future.result(timeout=1) == 1.0
    listener.stop_listeners()


def test_listener_logs_async_rule_callback_failure(caplog) -> None:
    async def callback(mcp_url: str, value: float) -> None:
        raise RuntimeError("servo unavailable")

    rule_bus = RuleBus()
    rule_bus.register_rule(
        "STREAM",
        "board-1",
        "sensor",
        Rule(
            condition=RuleCondition(
                expected=1.0,
                operator=OperatorEnum.EQUAL,
            ),
            callback=RuleCallback(
                callback=callback,
                mcp_url="https://hardware.example.com/mcp",
            ),
        ),
    )
    rule_buffer = RuleBuffer(rule_bus)
    rule_buffer.register_event_in_buffer("STREAM", "board-1", "sensor")
    listener = EventListener(
        hardware_system=SimpleNamespace(microcontrollers=[]),
        serial_pool={},
        threads={},
        event_bus=EventBus(),
        rule_buffer=rule_buffer,
    )

    rule_future = listener.dispatch_event_to_rule_buffer(
        "STREAM",
        "board-1",
        "sensor",
        {"value": "1"},
    )

    with pytest.raises(RuntimeError, match="servo unavailable"):
        rule_future.result(timeout=1)

    listener.stop_listeners()
    assert "Rule evaluation failed" in caplog.text
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
        rule_buffer=RuleBuffer(RuleBus()),
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
        rule_buffer=RuleBuffer(RuleBus()),
    )

    with pytest.raises(RuntimeError, match="did not stop"):
        listener.stop_listeners(timeout=0)

    assert listener.threads == {"board-1": thread}
