import json
from pathlib import Path
import subprocess

import questionary
import typer

from gerbera_cli.configuration import (
    DeviceConfig,
    HarnessConfig,
    ProjectConfig,
    ProjectSecrets,
    ProjectSettings,
    find_project_config,
)
from gerbera_cli.initialise import load_board_data
from gerbera_cli.setup import (
    LocalProjectServices,
    generate_secret,
    load_hardware_system,
    run_forced_firmware_setup,
    run_firmware_setup,
    run_local_server,
)
from gerbera_harness.runtime import ProjectRuntime, StartupOptions
from gerbera_sdk.firmware.boards import BOARD_REGISTRY

app = typer.Typer(no_args_is_help=True)
firmware_app = typer.Typer(no_args_is_help=True)
app.add_typer(firmware_app, name="firmware")


@app.command(name="init")
def initialise_project(
    with_harness: bool = typer.Option(False, "--with-harness"),
    provider: str | None = typer.Option(None, "--provider"),
) -> None:
    """Create a Gerbera project from connected boards."""
    if Path("gerbera.yaml").exists() or Path("config.json").exists():
        raise typer.BadParameter("Gerbera project configuration already exists")

    typer.echo("Detecting connected boards...")
    result = subprocess.run(
        ["arduino-cli", "board", "list", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    detected_devices = load_board_data(result)
    selected_devices = select_devices(detected_devices)
    configured_devices = configure_devices(selected_devices)
    harness = build_harness_config(with_harness, provider)
    secrets = build_secrets(harness)
    config = ProjectConfig(
        project=ProjectSettings(),
        harness=harness,
        devices=configured_devices,
    )

    create_workspace()
    config.save()
    secrets.save()
    create_entry_point(config)
    create_harness_config(harness)
    typer.secho(
        f"Project ready with {len(configured_devices)} board(s). "
        "Run: gerbera up",
        fg=typer.colors.GREEN,
        bold=True,
    )


@app.command(name="up")
def up(
    skip_flash: bool = typer.Option(False, "--skip-flash"),
    no_harness: bool = typer.Option(False, "--no-harness"),
) -> None:
    """Start the complete local Gerbera stack."""
    runtime = build_project_runtime()
    runtime.start(
        StartupOptions(
            flash_firmware=not skip_flash,
            start_harness=not no_harness,
        )
    )
    typer.secho("Gerbera is ready.", fg=typer.colors.GREEN, bold=True)
    print_status(runtime.status())


@firmware_app.command(name="flash")
def flash_firmware(
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Validate and flash configured boards."""
    config_path = find_project_config()
    config = ProjectConfig.load(config_path)
    hardware = load_hardware_system(config, config_path)
    if force:
        run_forced_firmware_setup(hardware)
        return
    run_firmware_setup(hardware)


@app.command(name="server")
def server() -> None:
    """Run only the MCP server in the foreground."""
    config_path = find_project_config()
    config = ProjectConfig.load(config_path)
    secrets = ProjectSecrets.load()
    hardware = load_hardware_system(config, config_path)
    run_local_server(config, secrets, hardware)


@app.command(name="status")
def status() -> None:
    """Show local service and project status."""
    print_status(build_project_runtime().status())


@app.command(name="logs")
def logs(
    follow: bool = typer.Option(False, "--follow", "-f"),
) -> None:
    """Show logs from Gerbera-managed services."""
    build_project_runtime().logs(follow)


@app.command(name="doctor")
def doctor() -> None:
    """Check whether the project can start."""
    checks = build_project_runtime().doctor()
    for check in checks:
        typer.echo(check)
    if any(check.startswith("FAIL") for check in checks):
        raise typer.Exit(code=1)


@app.command(name="down")
def down() -> None:
    """Stop services started by Gerbera."""
    build_project_runtime().stop()
    typer.secho("Gerbera is stopped.", fg=typer.colors.GREEN)


def build_project_runtime() -> ProjectRuntime:
    config_path = find_project_config()
    config = ProjectConfig.load(config_path)
    secrets = ProjectSecrets.load()
    services = LocalProjectServices(config, secrets, config_path)
    return ProjectRuntime(services)


def select_devices(
    detected_devices: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    if not detected_devices:
        raise typer.BadParameter(
            "No boards detected. Connect a board and retry."
        )
    if len(detected_devices) == 1:
        return detected_devices
    selected_addresses = questionary.checkbox(
        "Select boards:",
        choices=list(detected_devices),
    ).ask()
    if not selected_addresses:
        raise typer.Abort()
    return {
        address: detected_devices[address]
        for address in selected_addresses
    }


def configure_devices(
    selected_devices: dict[str, dict[str, object]],
) -> dict[str, DeviceConfig]:
    return {
        address: DeviceConfig.model_validate(
            {
                key: value
                for key, value in device.items()
                if key != "name"
            }
            | {"fqbn": resolve_fqbn(device)}
        )
        for address, device in selected_devices.items()
    }


def resolve_fqbn(device: dict[str, object]) -> str:
    detected_fqbn = device.get("fqbn")
    supported_fqbns = tuple(
        definition.fqbn for definition in BOARD_REGISTRY.definitions
    )
    if detected_fqbn in supported_fqbns:
        return str(detected_fqbn)
    selected_fqbn = questionary.select(
        f"Select the board type for {device['address']}:",
        choices=list(supported_fqbns),
    ).ask()
    if not selected_fqbn:
        raise typer.Abort()
    return selected_fqbn


def build_harness_config(
    enabled: bool,
    provider: str | None,
) -> HarnessConfig:
    selected_provider = provider
    if enabled and selected_provider is None:
        selected_provider = questionary.select(
            "Select an AI provider:",
            choices=["openai", "anthropic", "google", "ollama", "openai_compatible"],
        ).ask()
    if enabled and selected_provider is None:
        raise typer.Abort()
    model = None
    if enabled:
        model = questionary.text("Model name:").ask()
        if not model:
            raise typer.Abort()
    model_type = "local" if selected_provider in {"ollama", "openai_compatible"} else "api"
    return HarnessConfig(
        enabled=enabled, provider=selected_provider,
        model=model, model_type=model_type,
    )


def build_secrets(
    harness: HarnessConfig,
) -> ProjectSecrets:
    selected_api_key = None
    if harness.enabled and harness.model_type == "api":
        selected_api_key = questionary.password("AI provider API key:").ask()
    if harness.enabled and harness.model_type == "api" and not selected_api_key:
        raise typer.Abort()
    return ProjectSecrets(
        gerbera_admin_password=generate_secret(),
        gerbera_schema_password=generate_secret(),
        gerbera_writer_password=generate_secret(),
        gerbera_reader_password=generate_secret(),
        api_key=selected_api_key,
    )


def create_harness_config(harness: HarnessConfig) -> None:
    if not harness.enabled:
        return
    path = Path(".gerbera/harness/harness.json")
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    model_config = {
        "type": harness.model_type,
        "provider": harness.provider,
        "name": harness.model,
    }
    if harness.model_type == "local":
        endpoint = "http://host.docker.internal:11434"
        if harness.provider == "openai_compatible":
            endpoint = "http://host.docker.internal:8080/v1"
        model_config["endpoint"] = harness.model_endpoint or endpoint
    path.write_text(json.dumps({
        "schema_version": "1",
        "model": model_config,
        "connector": {"mcp_url": "http://host.docker.internal:8001/mcp"},
        "default_workflow": "simple",
        "extensions": ["event_recording"],
    }, indent=2))


def create_workspace() -> None:
    for path in (
        Path(".gerbera/firmware"),
        Path(".gerbera/logs"),
        Path(".gerbera/models"),
        Path(".gerbera/reactions"),
        Path(".gerbera/runtime"),
        Path(".gerbera/secrets"),
    ):
        path.mkdir(parents=True, exist_ok=True)


def create_entry_point(config: ProjectConfig) -> None:
    entry_point = config.project.entry_point
    if entry_point.exists():
        return
    controllers = ",\n    ".join(
        controller_source(index, device)
        for index, device in enumerate(config.devices.values(), start=1)
    )
    source = (
        "from gerbera_sdk.models.hardware.hardware_system import HardwareSystem\n"
        "from gerbera_sdk.models.hardware.microcontroller import (\n"
        "    Microcontroller,\n"
        "    RuntimeWatchdogConfig,\n"
        ")\n\n\n"
        f"{config.project.hardware_variable} = HardwareSystem(\n"
        '    name="gerbera-project",\n'
        "    microcontrollers=[\n"
        f"    {controllers}\n"
        "    ],\n"
        ")\n"
    )
    entry_point.write_text(source)


def controller_source(index: int, device: DeviceConfig) -> str:
    return (
        "Microcontroller(\n"
        f'        name="controller_{index}",\n'
        f"        port={device.address!r},\n"
        f"        fqbn={device.fqbn!r},\n"
        "        watchdog=RuntimeWatchdogConfig(\n"
        "            heartbeat_interval_ms=500,\n"
        "            heartbeat_timeout_ms=2500,\n"
        "        ),\n"
        "    )"
    )


def print_status(service_status: dict[str, object]) -> None:
    typer.echo(json.dumps(service_status, indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
