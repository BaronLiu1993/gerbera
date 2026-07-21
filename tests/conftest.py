import json

import pytest


@pytest.fixture
def device_registry(tmp_path, monkeypatch):
    def configure(devices: dict[str, str]) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "devices": {
                        device_id: {
                            "id": device_id,
                            "address": port,
                        }
                        for device_id, port in devices.items()
                    }
                }
            )
        )
        monkeypatch.setattr(
            "gerbera_sdk.models.hardware.microcontroller.CONFIG_PATH",
            config_path,
        )

    return configure
