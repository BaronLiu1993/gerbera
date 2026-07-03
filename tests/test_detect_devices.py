import json
from types import SimpleNamespace

from typer.testing import CliRunner

from cli_app.commands import detect_devices
from cli_app.main import app


runner = CliRunner()


def test_available_devices_collects_serial_metadata(monkeypatch) -> None:
    fake_ports = [
        SimpleNamespace(
            device="/dev/cu.usbserial-1140",
            description="USB Serial",
            hwid="USB VID:PID=1A86:7523 LOCATION=1-1.4",
        ),
        SimpleNamespace(
            device="/dev/cu.other",
            description="Other Device",
            hwid="OTHER HWID",
        ),
    ]
    monkeypatch.setattr(detect_devices.list_ports, "comports", lambda: fake_ports)
    monkeypatch.setattr(
        detect_devices,
        "uuid4",
        lambda: "00000000-0000-0000-0000-000000000000",
    )

    devices = detect_devices._available_devices()

    assert devices == [
        {
            "index": 0,
            "id": "00000000-0000-0000-0000-000000000000",
            "device": "/dev/cu.usbserial-1140",
            "description": "USB Serial",
            "hwid": "USB VID:PID=1A86:7523 LOCATION=1-1.4",
        },
        {
            "index": 1,
            "id": "00000000-0000-0000-0000-000000000000",
            "device": "/dev/cu.other",
            "description": "Other Device",
            "hwid": "OTHER HWID",
        },
    ]


def test_select_devices_interactively_adds_and_removes_selection(monkeypatch) -> None:
    devices = [
        {
            "index": 0,
            "id": "device-1",
            "device": "/dev/cu.usbserial-1140",
            "description": "USB Serial",
            "hwid": "USB VID:PID=1A86:7523 LOCATION=1-1.4",
        }
    ]
    key_presses = iter(["enter", "enter", "down", "enter"])
    aliases = iter(["arduino"])

    monkeypatch.setattr(detect_devices, "_render_selection_menu", lambda *args: None)
    monkeypatch.setattr(detect_devices, "_read_menu_key", lambda: next(key_presses))
    monkeypatch.setattr(detect_devices.typer, "prompt", lambda _: next(aliases))
    monkeypatch.setattr(detect_devices.typer, "echo", lambda *args, **kwargs: None)

    selected = detect_devices._select_devices_interactively(devices)

    assert selected == {}


def test_select_command_writes_device_mapping_json(monkeypatch, tmp_path) -> None:
    devices = [
        {
            "index": 0,
            "id": "device-1",
            "device": "/dev/cu.usbserial-1140",
            "description": "USB Serial",
            "hwid": "USB VID:PID=1A86:7523 LOCATION=1-1.4",
        }
    ]
    selected_devices = {
        "kitchen-light": {
            "id": "device-1",
            "device": "/dev/cu.usbserial-1140",
            "description": "USB Serial",
            "hwid": "USB VID:PID=1A86:7523 LOCATION=1-1.4",
        }
    }
    output_path = tmp_path / "devices.json"

    monkeypatch.setattr(detect_devices, "_available_devices", lambda: devices)
    monkeypatch.setattr(
        detect_devices,
        "_select_devices_interactively",
        lambda incoming: selected_devices if incoming == devices else {},
    )

    result = runner.invoke(app, ["devices", "select", "--output", str(output_path)])

    assert result.exit_code == 0
    assert output_path.exists()
    assert json.loads(output_path.read_text()) == selected_devices
    assert f"Wrote 1 device mapping(s) to {output_path}" in result.stdout


def test_select_command_handles_no_devices(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "devices.json"
    monkeypatch.setattr(detect_devices, "_available_devices", lambda: [])

    result = runner.invoke(app, ["devices", "select", "--output", str(output_path)])

    assert result.exit_code == 0
    assert "[cli-app] no serial devices detected" in result.stdout
    assert not output_path.exists()
