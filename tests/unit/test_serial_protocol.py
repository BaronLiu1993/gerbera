import pytest

from gerbera_sdk.models.runtime.serial_protocol import (
    MAX_SERIAL_MESSAGE_BYTES,
    SerialMessage,
    SerialMessageCodec,
)


def test_serial_message_round_trip() -> None:
    message = SerialMessage(
        message_type="MCP",
        target="sensor",
        fields={"distance": "12.5"},
    )

    decoded = SerialMessageCodec.decode(SerialMessageCodec.encode(message))

    assert decoded == message


@pytest.mark.parametrize(
    "raw_message",
    [
        "MCP",
        "MCP,sensor,distance",
        "MCP,sensor,distance:1,distance:2",
        "MCP,sensor,:1",
        "MCP,sensor,distance:",
    ],
)
def test_serial_message_rejects_malformed_input(raw_message: str) -> None:
    with pytest.raises(ValueError):
        SerialMessageCodec.decode(raw_message)


def test_serial_message_rejects_invalid_utf8() -> None:
    with pytest.raises(UnicodeDecodeError):
        SerialMessageCodec.decode(b"\xff")


def test_serial_message_rejects_oversized_input() -> None:
    raw_message = b"MCP,sensor,value:" + b"1" * MAX_SERIAL_MESSAGE_BYTES

    with pytest.raises(ValueError, match="maximum size"):
        SerialMessageCodec.decode(raw_message)
