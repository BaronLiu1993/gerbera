import json

from typer.testing import CliRunner

from gerbera_cli.main import app


runner = CliRunner()


def test_set_connection_writes_config(tmp_path) -> None:
    output_path = tmp_path / "connections.json"

    result = runner.invoke(
        app,
        [
            "connections",
            "set",
            "arduino_led",
            "led_1",
            "read",
            "12",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert json.loads(output_path.read_text()) == {
        "libraries": [
            {
                "library": "arduino_led",
                "pins": [
                    {
                        "id": "led_1",
                        "role": "read",
                        "pin": 12,
                    }
                ],
            }
        ]
    }


def test_set_connection_rejects_duplicate_id(tmp_path) -> None:
    output_path = tmp_path / "connections.json"
    output_path.write_text(
        json.dumps(
            {
                "libraries": [
                    {
                        "library": "arduino_led",
                        "pins": [
                            {
                                "id": "led_1",
                                "role": "read",
                                "pin": 12,
                            }
                        ],
                    }
                ]
            }
        )
    )

    result = runner.invoke(
        app,
        [
            "connections",
            "set",
            "arduino_led",
            "led_1",
            "write",
            "13",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 1
    assert "already exists" in result.stdout
