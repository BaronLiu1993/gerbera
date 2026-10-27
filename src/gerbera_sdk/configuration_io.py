import json
from pathlib import Path

import yaml


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate configuration key: {key}')
        result[key] = value
    return result


def reject_nonfinite(value: str):
    raise ValueError(f'Non-finite configuration value: {value}')


def require_object(value) -> dict:
    if not isinstance(value, dict):
        raise ValueError('Configuration must be an object')
    return value


class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        pairs = []
        for key_node, value_node in node.value:
            if key_node.tag == 'tag:yaml.org,2002:merge':
                raise ValueError('YAML configuration merges are not supported')
            pairs.append((self.construct_object(key_node, deep=deep), self.construct_object(value_node, deep=deep)))
        return unique_object(pairs)


def decode_json(content: str) -> dict:
    return require_object(json.loads(content, object_pairs_hook=unique_object, parse_constant=reject_nonfinite))


def decode_yaml(content: str) -> dict:
    return require_object(yaml.load(content, Loader=UniqueKeyLoader))


def read_configuration(path: Path) -> dict:
    if path.suffix == '.json':
        return decode_json(path.read_text())
    if path.suffix in {'.yaml', '.yml'}:
        return decode_yaml(path.read_text())
    raise ValueError(f'Unsupported configuration format: {path.suffix}')
