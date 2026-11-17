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
    @classmethod
    def encode(cls, message: SerialMessage) -> str:
        cls.validate_token(message.message_type, "message type")
        cls.validate_token(message.target, "target")
        parts = [message.message_type, message.target]
        for key, value in message.fields.items():
            cls.validate_field(key, value)
            parts.append(f"{key}:{value}")

        encoded = ",".join(parts)
        if len(encoded.encode()) > MAX_SERIAL_MESSAGE_BYTES:
            raise ValueError("Serial message exceeds maximum size")
        return encoded

    @classmethod
    def decode(cls, raw_message: bytes | str) -> SerialMessage:
        data = raw_message.encode("utf-8") if isinstance(raw_message, str) else raw_message
        if len(data) > MAX_SERIAL_MESSAGE_BYTES:
            raise ValueError("Serial message exceeds maximum size")
        message = data.decode("utf-8")

        tokens = message.rstrip("\r\n").split(",")
        if len(tokens) < 2:
            raise ValueError("Serial message requires a type and target")

        message_type, target = tokens[:2]
        cls.validate_token(message_type, "message type")
        cls.validate_token(target, "target")

        fields: dict[str, str] = {}
        for field_token in tokens[2:]:
            if ":" not in field_token:
                raise ValueError(f"Malformed serial field: {field_token}")
            key, value = field_token.split(":", 1)
            cls.validate_field(key, value)
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

    @classmethod
    def validate_field(cls, key: str, value: str) -> None:
        cls.validate_token(key, "field name")
        if not value or value != value.strip():
            raise ValueError(f"Serial field {key} must have a value")
        if "," in value:
            raise ValueError(f"Serial field {key} contains a reserved delimiter")
