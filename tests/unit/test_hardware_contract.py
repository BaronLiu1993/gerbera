from dataclasses import replace

import pytest

from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import (
    Microcontroller,
    RuntimeWatchdogConfig,
)
from gerbera_sdk.models.hardware.validation import (
    BoardContractIdentity,
    HardwareContractCompiler,
)


def build_system(
    connections: list[Connection],
    watchdog: RuntimeWatchdogConfig | None = None,
) -> HardwareSystem:
    board = Microcontroller(
        name="board",
        port="/dev/board-1",
        fqbn="arduino:avr:uno",
        watchdog=watchdog
        or RuntimeWatchdogConfig(
            heartbeat_interval_ms=100,
            heartbeat_timeout_ms=500,
        ),
        connections=connections,
    )
    system = HardwareSystem(name="robot", microcontrollers=[board])
    board.hardware_system_id = system.id
    for connection in connections:
        connection.microcontroller_id = "board-1"
    return system


def test_contract_compiler_canonicalizes_pin_aliases(device_registry) -> None:
    device_registry({"board-1": "/dev/board-1"})
    system = build_system(
        [Connection("status_led", "led", {"out": "D13"}, "Status LED")]
    )

    plan = HardwareContractCompiler.compile(system)

    connection = plan.connections_by_key[("board-1", "status_led")]
    assert connection.pins == {"out": "13"}


def test_contract_compiler_indexes_event_routes(device_registry) -> None:
    device_registry({"board-1": "/dev/board-1"})
    system = build_system(
        [Connection("status_led", "led", {"out": "13"}, "Status LED")]
    )

    plan = HardwareContractCompiler.compile(system)
    connection = plan.connections_by_key[("board-1", "status_led")]

    assert plan.connections_by_event_route[
        ("board-1", connection.event_name)
    ] is connection


def test_contract_digest_is_independent_of_declaration_order(
    device_registry,
) -> None:
    device_registry({"board-1": "/dev/board-1"})
    first = build_system(
        [
            Connection("sensor", "hw201", {"out": "7"}, "Sensor"),
            Connection("status_led", "led", {"out": "13"}, "LED"),
        ]
    )
    second = build_system(
        [
            Connection("status_led", "led", {"out": "13"}, "LED"),
            Connection("sensor", "hw201", {"out": "7"}, "Sensor"),
        ]
    )

    first_digest = HardwareContractCompiler.compile(first).boards[0].contract_digest
    second_digest = HardwareContractCompiler.compile(second).boards[0].contract_digest

    assert first_digest == second_digest


def test_contract_digest_changes_with_pin_assignment(device_registry) -> None:
    device_registry({"board-1": "/dev/board-1"})
    first = build_system(
        [Connection("sensor", "hw201", {"out": "7"}, "Sensor")]
    )
    second = build_system(
        [Connection("sensor", "hw201", {"out": "8"}, "Sensor")]
    )

    first_digest = HardwareContractCompiler.compile(first).boards[0].contract_digest
    second_digest = HardwareContractCompiler.compile(second).boards[0].contract_digest

    assert first_digest != second_digest


def test_contract_digest_changes_with_watchdog_timing(device_registry) -> None:
    device_registry({"board-1": "/dev/board-1"})
    first = build_system(
        [],
        RuntimeWatchdogConfig(
            heartbeat_interval_ms=100,
            heartbeat_timeout_ms=500,
        ),
    )
    second = build_system(
        [],
        RuntimeWatchdogConfig(
            heartbeat_interval_ms=150,
            heartbeat_timeout_ms=500,
        ),
    )

    first_digest = HardwareContractCompiler.compile(first).boards[0].contract_digest
    second_digest = HardwareContractCompiler.compile(second).boards[0].contract_digest

    assert first_digest != second_digest


def test_contract_digest_changes_with_safe_stop_strategy(
    device_registry,
) -> None:
    device_registry({"board-1": "/dev/board-1"})
    system = build_system(
        [Connection("status_led", "led", {"out": "13"}, "Status LED")]
    )
    board = HardwareContractCompiler.compile(system).boards[0]
    connection = board.connections[0]
    changed_connection = replace(
        connection,
        verification=replace(
            connection.verification,
            safe_stop=connection.verification.safe_stop + "\ndelay(1);",
        ),
    )
    identity = BoardContractIdentity(
        microcontroller_id=board.microcontroller_id,
        baud_rate=board.baud_rate,
        definition=board.definition,
    )

    changed_digest = HardwareContractCompiler.calculate_board_digest(
        identity,
        (changed_connection,),
        board.watchdog,
    )

    assert changed_digest != board.contract_digest


@pytest.mark.parametrize(
    ("watchdog", "error"),
    [
        (
            RuntimeWatchdogConfig(0, 500),
            "heartbeat_interval_ms: must be a positive integer",
        ),
        (
            RuntimeWatchdogConfig(100, 100),
            "timeout must exceed interval",
        ),
        (
            RuntimeWatchdogConfig(100, 150),
            "timeout must allow at least one interval of jitter",
        ),
    ],
)
def test_contract_compiler_rejects_invalid_watchdog(
    watchdog: RuntimeWatchdogConfig,
    error: str,
    device_registry,
) -> None:
    device_registry({"board-1": "/dev/board-1"})

    with pytest.raises(ValueError, match=error):
        HardwareContractCompiler.compile(build_system([], watchdog))


@pytest.mark.parametrize(
    ("connections", "error"),
    [
        (
            [Connection("sensor", "hw201", {}, "Sensor")],
            "missing required logical pin: out",
        ),
        (
            [
                Connection(
                    "sensor",
                    "hw201",
                    {"out": "7", "extra": "8"},
                    "Sensor",
                )
            ],
            "unexpected logical pin",
        ),
        (
            [
                Connection(
                    "motor",
                    "dcmotor",
                    {"in1": "4", "in2": "7", "enable": "8"},
                    "Motor",
                )
            ],
            "missing required capabilities: pwm_output",
        ),
        (
            [Connection("status_led", "led", {"out": "0"}, "LED")],
            "reserved by serial",
        ),
        (
            [
                Connection("first_led", "led", {"out": "13"}, "LED"),
                Connection("second_led", "led", {"out": "D13"}, "LED"),
            ],
            "already assigned",
        ),
    ],
)
def test_contract_compiler_rejects_invalid_pin_assignment(
    connections: list[Connection],
    error: str,
    device_registry,
) -> None:
    device_registry({"board-1": "/dev/board-1"})

    with pytest.raises(ValueError, match=error):
        HardwareContractCompiler.compile(build_system(connections))
