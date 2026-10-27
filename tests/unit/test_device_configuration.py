from pathlib import Path

import pytest
from pydantic import ValidationError
import yaml

from gerbera_sdk.firmware.devices.config_schema import DeviceConfig


@pytest.fixture
def definition():
    path = Path(__file__).resolve().parents[2] / "src/gerbera_sdk/firmware/devices/configs/hw201.yaml"
    return yaml.safe_load(path.read_text())


def test_device_configuration_requires_explicit_firmware_fields(definition) -> None:
    del definition["firmware"]["setup"]

    with pytest.raises(ValidationError, match="setup"):
        DeviceConfig.from_data(definition)


@pytest.mark.parametrize("path, value", [
    (("firmware", "definitions"), None),
    (("stream", "schema", "value", "idx"), "false"),
    (("commands", 0, "annotations", "readOnlyHint"), True),
])
def test_device_configuration_rejects_coercions_and_retired_fields(definition, path, value) -> None:
    target = definition
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValidationError, match=str(path[-1])):
        DeviceConfig.from_data(definition)
