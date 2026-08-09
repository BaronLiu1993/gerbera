import threading

import pytest

from gerbera_sdk.events.event_store import EventStore


def test_event_store_returns_latest_value() -> None:
    store = EventStore()
    key = ("MCP", "board-1", "led")

    store.set(key, {"state": "1"})

    assert store.latest(key) == {"state": "1"}


def test_event_store_waits_for_value() -> None:
    store = EventStore()
    key = ("MCP", "board-1", "led")

    thread = threading.Thread(target=lambda: store.set(key, {"state": "1"}))
    thread.start()

    assert store.wait_for(key) == {"state": "1"}
    thread.join(timeout=1)


def test_event_store_times_out() -> None:
    store = EventStore()

    with pytest.raises(TimeoutError, match="Timed out waiting for event"):
        store.wait_for(("MCP", "board-1", "missing"), timeout=0.01)
