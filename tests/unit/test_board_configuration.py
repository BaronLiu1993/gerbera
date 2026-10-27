from pathlib import Path

import pytest
from pydantic import ValidationError
import yaml

from gerbera_sdk.firmware.boards.config_schema import BoardConfigurations


@pytest.fixture
def configuration():
    path = Path(__file__).resolve().parents[2] / 'src/gerbera_sdk/firmware/boards/config.yaml'
    return yaml.safe_load(path.read_text())


@pytest.mark.parametrize('field, value', [
    ('digital_pin_count', True), ('includes', 'Arduino.h'), ('unknown', 123),
])
def test_board_configuration_rejects_coercions_and_unknown_fields(configuration, field, value):
    configuration['boards'][0][field] = value

    with pytest.raises(ValidationError, match=field):
        BoardConfigurations.from_data(configuration)


def test_board_configuration_rejects_duplicate_identity(configuration):
    configuration['boards'].append(configuration['boards'][0])

    with pytest.raises(ValidationError, match='Duplicate board FQBN'):
        BoardConfigurations.from_data(configuration)
