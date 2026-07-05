from gerbera_sdk import ConnectionMode, Pin


def test_pin_to_dict_for_read_mode_includes_read_schemas() -> None:
    pin = Pin(
        pin_val="A0",
        mode=ConnectionMode.READ,
        output_properties={
            "value": {
                "type": "number",
            },
            "unit": {
                "type": "string",
            },
        },
    )

    assert pin.to_dict() == {
        "pin": "A0",
        "mode": "read",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                },
                "unit": {
                    "type": "string",
                },
            },
            "required": ["value", "unit"],
        },
    }


def test_pin_to_dict_for_write_mode_includes_write_schemas() -> None:
    pin = Pin(
        pin_val="13",
        mode=ConnectionMode.WRITE,
        input_properties={
            "value": {
                "type": "boolean",
            }
        },
    )

    assert pin.to_dict() == {
        "pin": "13",
        "mode": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "boolean",
                }
            },
            "required": ["value"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }


def test_pin_to_dict_for_both_mode_includes_bidirectional_schemas() -> None:
    pin = Pin(
        pin_val="4",
        mode=ConnectionMode.BOTH,
        input_properties={
            "value": {
                "type": "string",
            }
        },
        output_properties={
            "value": {
                "type": "string",
            },
            "success": {
                "type": "boolean",
            },
        },
    )

    assert pin.to_dict() == {
        "pin": "4",
        "mode": "both",
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                }
            },
            "required": ["value"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                },
                "success": {
                    "type": "boolean",
                },
            },
            "required": ["value", "success"],
        },
    }
