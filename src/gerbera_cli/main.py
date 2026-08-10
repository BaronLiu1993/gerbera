import json
from pathlib import Path
import subprocess
import questionary
import typer

from gerbera_cli.initialise import load_board_data
from gerbera_cli.setup import (
    create_stream_tables,
    generate_secret,
    load_hardware_system,
    run_harness_container,
    setup_local_container,
)

app = typer.Typer()


@app.command(name="init")
def init():
    # New Config File Each Time
    config = {}

    typer.echo("Fetching supported microcontrollers from arduino-cli...")

    result = subprocess.run(
        ["arduino-cli", "board", "list", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )

    # Select Microcontrollers
    microcontroller_choices = load_board_data(result)
    print(microcontroller_choices)
    selected_choices = questionary.checkbox(
        "Select microcontrollers to configure (Space to select, Enter to confirm):",
        choices=[choice for choice in microcontroller_choices.keys()],
    ).ask()

    if not selected_choices:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    # Define which file in root the CLI should read from
    entry_point = questionary.text(
        "Define the app entry point:",
        default="index.py",
    ).ask()

    if not entry_point:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    # Define within the entry point, where the hardware system variable is
    hardware_name = questionary.text(
        "Define the hardware variable name:",
        default="hardware_system",
    ).ask()

    # Define which provider you want to use for reasoning

    providers = ["openai", "anthropic", "google"]  # For now
    selection = questionary.select("Select AI Provider", providers).ask()
    if not selection:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    api_key = questionary.text("Add Your API Key").ask()

    if not api_key:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    gerbera_admin_password = generate_secret()
    gerbera_schema_password = generate_secret()
    gerbera_writer_password = generate_secret()
    gerbera_reader_password = generate_secret()

    secrets_json = {
        "provider": selection,
        "api_key": api_key,
        "gerbera_admin_password": gerbera_admin_password,
        "gerbera_schema_password": gerbera_schema_password,
        "gerbera_writer_password": gerbera_writer_password,
        "gerbera_reader_password": gerbera_reader_password,
    }

    device_json = {}
    for key, val in microcontroller_choices.items():
        if key not in device_json and key in selected_choices:
            device_json[key] = val

    config["devices"] = device_json
    config["entry_point"] = entry_point
    config["hardware_name"] = hardware_name
    Path(".gerbera/firmware").mkdir(parents=True, exist_ok=True)
    Path(".gerbera/models").mkdir(parents=True, exist_ok=True)
    Path(".gerbera/reactions").mkdir(parents=True, exist_ok=True)

    

    Path(".gerbera/secrets").mkdir(parents=True, exist_ok=True)
    Path(".gerbera/secrets/secrets.json").write_text(json.dumps(secrets_json, indent=4))
    Path("config.json").write_text(json.dumps(config, indent=4))
    typer.secho(
        "Successfully updated config and .gerbera workspace. "
        f"Currently managing {len(device_json)} device(s) in config.json.",
        fg=typer.colors.GREEN,
        bold=True,
    )


# Perform a check for a config file first before doing this
@app.command(name="up")
def up():
    choices = ["local", "cloud"]
    selection = questionary.select("Select Harness Deployment", choices).ask()
    if not selection:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    config = json.loads(Path("config.json").read_text())
    secrets = json.loads(Path(".gerbera/secrets/secrets.json").read_text())
    hardware = load_hardware_system(config)

    if selection == "local":
        gerbera_admin_password = secrets["gerbera_admin_password"]
        gerbera_schema_password = secrets["gerbera_schema_password"]
        gerbera_writer_password = secrets["gerbera_writer_password"]
        gerbera_reader_password = secrets["gerbera_reader_password"]

        setup_local_container(
            gerbera_admin_password=gerbera_admin_password,
            gerbera_schema_password=gerbera_schema_password,
            gerbera_writer_password=gerbera_writer_password,
            gerbera_reader_password=gerbera_reader_password,
        )

        create_stream_tables(
            hardware_system=hardware,
            host="127.0.0.1",
            port=6432,
            dbname="gerbera",
            user="gerbera_schema_owner",
            password=gerbera_schema_password,
        )

        run_harness_container(
            gerbera_schema_password=gerbera_schema_password,
            gerbera_writer_password=gerbera_writer_password,
            gerbera_reader_password=gerbera_reader_password,
            provider=secrets["provider"],
            mcp_url="http://127.0.0.1:8000/mcp",
            api_key=secrets["api_key"],
        )

    else:
        pass

@app.command(name="down")
def down():
    pass


def main():
    app()


if __name__ == "__main__":
    main()
