from collections.abc import Mapping

from gerbera_sdk.firmware.devices.config_schema import StateFieldConfig


def validate_payload(payload: Mapping[str, str], fields: Mapping[str, StateFieldConfig]) -> None:
    if set(payload) != set(fields):
        raise ValueError(f'Payload fields must be exactly {sorted(fields)}')
    for name, raw in payload.items():
        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError(f'Invalid numeric wire value for {name}') from exc
        fields[name].domain.validate_value(value)
