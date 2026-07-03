import json
from types import SimpleNamespace

from typer.testing import CliRunner

from gerbera_cli.commands import detect_devices
from gerbera_cli.main import app


runner = CliRunner()


def test_available_devices_collects_serial_metadata(monkeypatch) -> None:
    fake_ports = [
        SimpleNamespace(
            device="/dev/cu.debug-console",
            description="n/a",
            hwid="n/a",
        ),
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

    devices = detect_devices._available_devices()

    assert devices == [
        {
            "index": 0,
            "device": "/dev/cu.usbserial-1140",
            "description": "USB Serial",
            "hwid": "USB VID:PID=1A86:7523 LOCATION=1-1.4",
        },
        {
            "index": 1,
            "device": "/dev/cu.other",
            "description": "Other Device",
            "hwid": "OTHER HWID",
        },
    ]


def test_candidate_device_requires_real_hwid() -> None:
    assert (
        detect_devices._is_candidate_device(
            SimpleNamespace(
                device="/dev/cu.usbserial-1140",
                description="USB Serial",
                hwid="USB VID:PID=1A86:7523 LOCATION=1-1.4",
            )
        )
        is True
    )
    assert (
        detect_devices._is_candidate_device(
            SimpleNamespace(
                device="/dev/cu.debug-console",
                description="n/a",
                hwid="n/a",
            )
        )
        is False
    )


def test_available_devices_keeps_duplicate_descriptions(monkeypatch) -> None:
    fake_ports = [
        SimpleNamespace(
            device="/dev/cu.usbserial-1140",
            description="USB Serial",
            hwid="USB VID:PID=1A86:7523 LOCATION=1-1.4",
        ),
        SimpleNamespace(
            device="/dev/cu.usbserial-1150",
            description="USB Serial",
            hwid="USB VID:PID=1A86:7523 LOCATION=1-1.8",
        ),
    ]
    monkeypatch.setattr(detect_devices.list_ports, "comports", lambda: fake_ports)

    devices = detect_devices._available_devices()

    assert devices[0]["description"] == "USB Serial"
    assert devices[1]["description"] == "USB Serial"


def test_select_devices_interactively_adds_selection_once(monkeypatch) -> None:
    devices = [
        {
            "index": 0,
            "device": "/dev/cu.usbserial-1140",
            "description": "USB Serial",
            "hwid": "USB VID:PID=1A86:7523 LOCATION=1-1.4",
        }
    ]
    key_presses = iter(["enter", "enter", "down", "enter"])
    uuid_values = iter(["generated-uuid"])

    monkeypatch.setattr(detect_devices, "_render_selection_menu", lambda *args: None)
    monkeypatch.setattr(detect_devices, "_read_menu_key", lambda: next(key_presses))
    monkeypatch.setattr(detect_devices, "uuid4", lambda: next(uuid_values))
    monkeypatch.setattr(detect_devices.typer, "echo", lambda *args, **kwargs: None)

    selected = detect_devices._select_devices_interactively(devices)

    assert selected == {
        "generated-uuid": {
            "id": "generated-uuid",
            "device": "/dev/cu.usbserial-1140",
            "description": "USB Serial",
            "hwid": "USB VID:PID=1A86:7523 LOCATION=1-1.4",
        }
    }


def test_select_command_writes_device_mapping_json(monkeypatch, tmp_path) -> None:
    devices = [
        {
            "index": 0,
            "device": "/dev/cu.usbserial-1140",
            "description": "USB Serial",
            "hwid": "USB VID:PID=1A86:7523 LOCATION=1-1.4",
        }
    ]
    selected_devices = {
        "generated-uuid": {
            "id": "generated-uuid",
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
    assert "[gerbera-cli] no serial devices detected" in result.stdout
    assert not output_path.exists()
