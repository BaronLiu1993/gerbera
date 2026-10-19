import argparse
import json
from pathlib import Path

import questionary

from gerbera_harness.configuration import HarnessSettings
from gerbera_harness.models.registry import default_model_registry


def initialise_harness(provider: str | None) -> None:
    path = Path(".gerbera/harness/harness.json")
    secret_path = Path(".gerbera/secrets/harness.env")
    if path.exists() and secret_path.exists():
        return
    if path.exists() or secret_path.exists():
        raise FileExistsError("Harness configuration or secrets already exist; they are not overwritten")
    choices = [f"{kind}/{name}" for kind, name in default_model_registry().factories
               if provider is None or provider == name]
    if not choices:
        raise ValueError(f"Unknown harness model provider: {provider}")
    selection = choices[0] if len(choices) == 1 else questionary.select("Select a model provider:", choices=choices).ask()
    if not selection:
        raise RuntimeError("Harness initialization cancelled")
    kind, name = selection.split("/", 1)
    model = {"type": kind, "provider": name, "name": questionary.text("Model name:").ask()}
    if kind == "local":
        endpoint = "http://host.docker.internal:11434" if name == "ollama" else "http://host.docker.internal:8080/v1"
        model["endpoint"] = questionary.text("Model endpoint (as reached from the harness):", default=endpoint).ask()
    elif name == "openai_compatible":
        model["endpoint"] = questionary.text("Compatible API base URL:").ask()
    api_key = questionary.password("API key:").ask() if kind == "api" else ""
    if kind == "api" and not api_key:
        raise ValueError("API model credentials are required")
    if "\n" in api_key or "\r" in api_key:
        raise ValueError("API key must be a single line")
    HarnessSettings.model_validate({"model": model})
    path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.touch(mode=0o600, exist_ok=False)
    secret_path.write_text(f"API_KEY={api_key}\n")
    path.write_text(json.dumps({
        "schema_version": "1", "model": model,
        "connector": {"mcp_url": "${MCP_URL}"},
        "default_workflow": "simple", "extensions": ["event_recording"],
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider")
    initialise_harness(parser.parse_args().provider)


if __name__ == "__main__":
    main()
