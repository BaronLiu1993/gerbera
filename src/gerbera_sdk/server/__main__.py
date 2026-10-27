import argparse
import json
import os
import sys
from pathlib import Path

from gerbera_sdk.server.configuration import SdkSettings
from gerbera_sdk.models.runtime.storage.database_settings import DatabaseSettings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="serve", choices=("serve", "initialise", "credentials", "discover", "check"))
    parser.add_argument("--config", type=Path, default=Path(".gerbera/sdk/runtime.json"))
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--database-env", type=Path, default=Path(".gerbera/secrets/sdk-database.env"))
    arguments = parser.parse_args()
    if arguments.command == "initialise":
        from gerbera_sdk.server.initialise import initialise_sdk

        initialise_sdk(arguments.config)
        return
    if arguments.command == "credentials":
        from gerbera_sdk.server.credentials import initialise_credentials

        initialise_credentials(arguments.config.resolve(), arguments.database_env.resolve())
        return
    if arguments.command == "discover":
        from gerbera_sdk.server.initialise import discover_boards

        print(json.dumps(discover_boards()))
        return
    from gerbera_sdk.gerbera_runtime import GerberaRuntime

    config_path = arguments.config.resolve()
    settings = SdkSettings.load(config_path)
    database_port = os.getenv("GERBERA_DATABASE_PORT")
    overrides = {
        "host": arguments.host,
        "port": arguments.port,
        "database_host": os.getenv("GERBERA_DATABASE_HOST"),
        "database_port": int(database_port) if database_port is not None else None,
    }
    settings = SdkSettings.model_validate_json(json.dumps(settings.model_dump(mode="json") | {
        name: value for name, value in overrides.items() if value is not None
    }))
    project_root = (config_path.parent / settings.project_root).resolve()
    os.chdir(project_root)
    sys.path.insert(0, str(project_root))
    hardware = settings.load_hardware(config_path)
    if arguments.command == "check":
        GerberaRuntime.validate_hardware(hardware)
        settings.load_secrets(config_path)
        print(json.dumps({"service": "sdk", "configuration_valid": True}))
        return
    secrets = settings.load_secrets(config_path)
    GerberaRuntime.run(
        hardware,
        DatabaseSettings(
            host=settings.database_host, port=settings.database_port,
            writer_password=secrets.gerbera_writer_password,
            schema_password=secrets.gerbera_schema_password,
        ),
        transport="http", host=settings.host, port=settings.port,
    )


if __name__ == "__main__":
    main()
