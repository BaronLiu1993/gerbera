import atexit
from functools import partial
import importlib.util
import json
import signal
import subprocess
from pathlib import Path
import time

import requests
import typer

from gerbera_cli.utils import CONFIG_PATH, _load_config

from gerbera_sdk.main import GerberaRuntime
from gerbera_sdk.models.hardware_system import HardwareSystem


def _load_hardware_system_from_config(
    config_path: Path = CONFIG_PATH,
) -> "HardwareSystem":
    config = _load_config(config_path)
    entry_point = str(config.get("entry_point")).strip()
    hardware_name = str(config.get("hardware_name")).strip()

    if not entry_point:
        raise ValueError("config.json must define 'entry_point'")

    entry_point_path = Path(entry_point)

    if not entry_point_path.is_absolute():
        entry_point_path = config_path.parent / entry_point_path

    if not entry_point_path.exists():
        raise FileNotFoundError(f"Entry point not found: {entry_point_path}")

    spec = importlib.util.spec_from_file_location(
        "gerbera_user_entry_point",
        entry_point_path,
    )

    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {entry_point_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    hardware_system = getattr(module, hardware_name, None)

    if hardware_system is None:
        raise AttributeError(f"{entry_point_path} must define {hardware_name}")

    return hardware_system


def _mutate_config(
    config: dict[str, any],
    port: str,
    local_endpoint: str,
    public_endpoint: str = "",
) -> dict[str, any]:
    config["server"]["port"] = port
    config["server"]["local_endpoint"] = f"{local_endpoint}/mcp"
    config["server"]["public_endpoint"] = f"{public_endpoint}/mcp"
    return config


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _cleanup(_signum, _frame, ngrok_process: subprocess.Popen[str]) -> None:
    _stop_process(ngrok_process)
    raise SystemExit(0)


def _start_ngrok(port: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["ngrok", "http", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _poll_public_endpoint(timeout_seconds: float = 10.0) -> str:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            response = requests.get(
                "http://127.0.0.1:4040/api/tunnels",
                timeout=1,
            )
            response.raise_for_status()
            payload = response.json()
            tunnels = payload.get("tunnels", [])

            if tunnels:
                public_url = str(tunnels[0].get("public_url", "")).strip()
                if public_url:
                    return public_url
        except requests.RequestException:
            pass

        time.sleep(0.25)

    raise RuntimeError("Failed to retrieve ngrok public endpoint")


def setup(port: str = "8000", local_endpoint: str = "127.0.0.1", ) -> None:
    hardware_system = _load_hardware_system_from_config()
    GerberaRuntime.setup(
        hardware_system,
        install_dependencies=True,
        flash_firmware=True,
    )

    config = _load_config()
    new_config = _mutate_config(config, port, local_endpoint)

    try:
        CONFIG_PATH.write_text(json.dumps(new_config, indent=4))
    except OSError as exc:
        typer.secho(f"Failed to write file {exc}", fg=typer.colors.RED)

    ngrok_process = _start_ngrok(port)
    public_endpoint = _poll_public_endpoint()

    config = _load_config()
    new_config = _mutate_config(config, port, local_endpoint, public_endpoint)

    try:
        CONFIG_PATH.write_text(json.dumps(new_config, indent=4))
    except OSError as exc:
        typer.secho(f"Failed to write file {exc}", fg=typer.colors.RED)

    atexit.register(_stop_process, ngrok_process)
    signal.signal(signal.SIGINT, partial(_cleanup, ngrok_process=ngrok_process))
    signal.signal(signal.SIGTERM, partial(_cleanup, ngrok_process=ngrok_process))

    try:
        GerberaRuntime.run(
            hardware_system,
            transport="http",
            host="127.0.0.1",
            port=int(port),
        )
    finally:
        _stop_process(ngrok_process)
