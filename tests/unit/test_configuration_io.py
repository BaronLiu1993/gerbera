import pytest

from gerbera_sdk.configuration_io import decode_json, decode_yaml


@pytest.mark.parametrize('decoder, content', [
    (decode_json, '{"port":8001,"port":9001}'),
    (decode_yaml, 'port: 8001\nport: 9001\n'),
    (decode_json, '{"nested":{"id":1,"id":2}}'),
])
def test_configuration_rejects_duplicate_keys(decoder, content):
    with pytest.raises(ValueError, match='Duplicate configuration key'):
        decoder(content)


def test_json_rejects_nonfinite_literals():
    with pytest.raises(ValueError, match='Non-finite'):
        decode_json('{"value":NaN}')
