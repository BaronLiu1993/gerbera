from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from gerbera_sdk.firmware.firmware_schema import MAX_SERIAL_MESSAGE_BYTES


@dataclass(frozen=True)
class SerialMessage:
    message_type: str
    target: str
    fields: Mapping[str, str]


class SerialMessageCodec:
    @staticmethod
    def encode(message: SerialMessage) -> str:
        SerialMessageCodec.validate_token(message.message_type, "message type")
        SerialMessageCodec.validate_token(message.target, "target")
        parts = [message.message_type, message.target]
        for key, value in message.fields.items():
            SerialMessageCodec.validate_field(key, value)
            parts.append(f"{key}:{value}")

        encoded = ",".join(parts)
        if len(encoded.encode()) > MAX_SERIAL_MESSAGE_BYTES:
            raise ValueError("Serial message exceeds maximum size")
        return encoded

    @staticmethod
    def decode(raw_message: bytes | str) -> SerialMessage:
        if isinstance(raw_message, bytes):
            if len(raw_message) > MAX_SERIAL_MESSAGE_BYTES:
                raise ValueError("Serial message exceeds maximum size")
            message = raw_message.decode("utf-8")
        else:
            if len(raw_message.encode()) > MAX_SERIAL_MESSAGE_BYTES:
                raise ValueError("Serial message exceeds maximum size")
            message = raw_message

        tokens = message.rstrip("\r\n").split(",")
        if len(tokens) < 2:
            raise ValueError("Serial message requires a type and target")

        message_type, target = tokens[:2]
        SerialMessageCodec.validate_token(message_type, "message type")
        SerialMessageCodec.validate_token(target, "target")

        fields: dict[str, str] = {}
        for field_token in tokens[2:]:
            if ":" not in field_token:
                raise ValueError(f"Malformed serial field: {field_token}")
            key, value = field_token.split(":", 1)
            SerialMessageCodec.validate_field(key, value)
            if key in fields:
                raise ValueError(f"Duplicate serial field: {key}")
            fields[key] = value

        return SerialMessage(
            message_type=message_type,
            target=target,
            fields=MappingProxyType(fields),
        )

    @staticmethod
    def validate_token(value: str, label: str) -> None:
        if not value or value != value.strip():
            raise ValueError(f"Serial {label} must be a non-empty token")
        if "," in value or ":" in value:
            raise ValueError(f"Serial {label} contains a reserved delimiter")

    @staticmethod
    def validate_field(key: str, value: str) -> None:
        SerialMessageCodec.validate_token(key, "field name")
        if not value or value != value.strip():
            raise ValueError(f"Serial field {key} must have a value")
        if "," in value:
            raise ValueError(f"Serial field {key} contains a reserved delimiter")
