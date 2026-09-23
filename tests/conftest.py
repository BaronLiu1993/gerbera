import json

import pytest


@pytest.fixture
def device_registry(tmp_path, monkeypatch):
    def configure(devices: dict[str, str]):
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
        device_ids_by_port = {
            port: device_id for device_id, port in devices.items()
        }

        def resolve_device_id(microcontroller) -> str:
            try:
                return device_ids_by_port[microcontroller.port]
            except KeyError as exc:
                raise ValueError(
                    "No device in config.json['devices'] matched port "
                    f"{microcontroller.port}"
                ) from exc

        monkeypatch.setattr(
            "gerbera_sdk.models.hardware.microcontroller.Microcontroller."
            "get_microcontroller_id_from_config",
            resolve_device_id,
        )
        return config_path

    return configure
