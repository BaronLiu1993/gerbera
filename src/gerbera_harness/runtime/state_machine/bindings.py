from copy import deepcopy
import json
import re

from jsonschema import Draft202012Validator
from pydantic import JsonValue


def pointer_tokens(pointer: str) -> tuple[str, ...]:
    if pointer == "":
        return ()
    if not pointer.startswith("/") or re.search(r"~(?![01])", pointer):
        raise ValueError(f"Invalid JSON Pointer: {pointer}")
    return tuple(
        token.replace("~1", "/").replace("~0", "~")
        for token in pointer[1:].split("/")
    )


def read_pointer(document: JsonValue, pointer: str) -> JsonValue:
    value = document
    for token in pointer_tokens(pointer):
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", token):
            index = int(token)
            if index >= len(value):
                raise ValueError(f"Missing JSON Pointer: {pointer}")
            value = value[index]
        else:
            raise ValueError(f"Missing JSON Pointer: {pointer}")
    return deepcopy(value)


def bind_inputs(
    bindings: dict[str, str], document: JsonValue,
) -> dict[str, JsonValue]:
    return {
        name: read_pointer(document, pointer)
        for name, pointer in bindings.items()
    }


def write_value(
    values: dict[str, JsonValue], pointer: str, value: JsonValue,
) -> dict[str, JsonValue]:
    tokens = pointer_tokens(pointer)
    if len(tokens) < 2 or tokens[0] != "values":
        raise ValueError("Node outputs may only write below /values/")
    result = deepcopy(values)
    target = result
    for token in tokens[1:-1]:
        if token not in target:
            target[token] = {}
        child = target[token]
        if not isinstance(child, dict):
            raise ValueError(f"Output binding crosses a scalar: {pointer}")
        target = child
    target[tokens[-1]] = deepcopy(value)
    return result


def validate_json_schema(schema: dict[str, JsonValue]) -> None:
    Draft202012Validator.check_schema(schema)
    inspect_schema_references(schema)


def inspect_schema_references(value: JsonValue) -> None:
    if isinstance(value, list):
        for item in value:
            inspect_schema_references(item)
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$ref", "$dynamicRef"}:
                if not isinstance(child, str) or not child.startswith("#"):
                    raise ValueError("JSON Schema references must be local")
            inspect_schema_references(child)


def validate_document(document: JsonValue, schema: dict[str, JsonValue]) -> None:
    error = next(Draft202012Validator(schema).iter_errors(document), None)
    if error is not None:
        path = "/".join(str(part) for part in error.absolute_path)
        raise ValueError(f"Schema validation failed at /{path}: {error.message}")


def enforce_json_limit(value: JsonValue, maximum_bytes: int) -> None:
    size = len(json.dumps(value, allow_nan=False).encode())
    if size > maximum_bytes:
        raise ValueError(f"JSON payload exceeds {maximum_bytes} bytes")
