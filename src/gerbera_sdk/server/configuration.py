import importlib.util
import json
from pathlib import Path

from pydantic import Field
import yaml

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import RuntimeTransportConfig
from gerbera_sdk.utils import StrictSchema


class RegisteredDevice(StrictSchema):
    id: str = Field(min_length=1)
    address: str = Field(min_length=1)
    protocol: str = Field(default="serial", min_length=1)
    fqbn: str = Field(min_length=1)
    runtime_transport: dict | None = None


class SdkSettings(StrictSchema):
    project_root: Path = Path("../..")
    entry_point: Path = Path("index.py")
    hardware_variable: str = Field(default="hardware_system", min_length=1)
    host: str = Field(default="0.0.0.0", min_length=1)
    port: int = Field(default=8001, ge=1, le=65535)
    database_host: str = Field(default="127.0.0.1", min_length=1)
    database_port: int = Field(default=6432, ge=1, le=65535)
    secrets_file: Path = Path(".gerbera/secrets/sdk.json")
    devices: dict[str, RegisteredDevice] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "SdkSettings":
        payload = json.loads(path.read_text()) if path.suffix == ".json" else yaml.safe_load(path.read_text())
        if not isinstance(payload, dict):
            raise ValueError("SDK configuration must be an object")
        if "project" in payload or "entry_point" in payload and "project_root" not in payload:
            project = payload.get("project", {})
            runtime = payload.get("runtime", {})
            payload = {
                "project_root": ".", "entry_point": project.get("entry_point", payload.get("entry_point", "index.py")),
                "hardware_variable": project.get("hardware_variable", payload.get("hardware_name", "hardware_system")),
                "secrets_file": ".gerbera/secrets/secrets.json",
                "devices": payload.get("devices", {}), **runtime,
            }
        return cls.model_validate(payload)

    def load_hardware(self, config_path: Path) -> HardwareSystem:
        root = (config_path.parent / self.project_root).resolve()
        entry_point = root / self.entry_point
        specification = importlib.util.spec_from_file_location("gerbera_user_app", entry_point)
        if specification is None or specification.loader is None:
            raise ImportError(f"Could not load SDK hardware entry point: {entry_point}")
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        hardware = getattr(module, self.hardware_variable)
        if not isinstance(hardware, HardwareSystem):
            raise TypeError(f"{self.hardware_variable} must be a HardwareSystem")
        for controller in hardware.microcontrollers:
            controller.config_path = config_path
            registered = next((device for device in self.devices.values()
                               if device.id == controller.device_id or device.address == controller.firmware_upload_port), None)
            if registered is not None:
                controller.device_id = registered.id
                if controller.runtime_transport is None and registered.runtime_transport is not None:
                    controller.runtime_transport = RuntimeTransportConfig.from_data(registered.runtime_transport)
        return hardware

    def load_secrets(self, config_path: Path) -> "SdkSecrets":
        root = (config_path.parent / self.project_root).resolve()
        payload = json.loads((root / self.secrets_file).read_text())
        return SdkSecrets.model_validate({name: payload.get(name) for name in SdkSecrets.model_fields})


class SdkSecrets(StrictSchema):
    gerbera_writer_password: str = Field(min_length=1, repr=False)
    gerbera_schema_password: str = Field(min_length=1, repr=False)

