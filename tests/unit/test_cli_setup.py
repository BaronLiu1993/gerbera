import json
from pathlib import Path

import pytest

from gerbera_cli.configuration import ProjectConfig, ServiceSpec
from gerbera_cli.initialise import initialise_database_credentials
from gerbera_cli.setup import LocalProjectServices, readiness_report


def test_database_credentials_are_scoped_and_private(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    initialise_database_credentials()
    path = Path(".gerbera/secrets/sdk.json")

    assert (set(json.loads(path.read_text())), path.stat().st_mode & 0o777) == (
        {"gerbera_schema_password", "gerbera_writer_password"}, 0o600,
    )


def test_repeated_initialization_does_not_rotate_database_credentials(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    initialise_database_credentials()
    original = Path(".gerbera/secrets/database.env").read_text()

    initialise_database_credentials()

    assert Path(".gerbera/secrets/database.env").read_text() == original


def test_sdk_receives_database_endpoint_without_loading_hardware() -> None:
    services = LocalProjectServices(ProjectConfig(services={
        "sdk": ServiceSpec(config="missing.json", url="http://localhost:8001"),
        "database": ServiceSpec(url="postgresql://db.example:6543"),
    }))

    assert {name: value for name, value in services.sdk_environment().items()
            if name in {"GERBERA_DATABASE_HOST", "GERBERA_DATABASE_PORT"}} == {
        "GERBERA_DATABASE_HOST": "db.example", "GERBERA_DATABASE_PORT": "6543",
    }


def test_externally_managed_services_are_not_started() -> None:
    services = LocalProjectServices(ProjectConfig(services={
        "sdk": ServiceSpec(managed=False), "database": ServiceSpec(managed=False),
    }))

    assert (services.start_server(), services.start_database()) == (False, False)


def test_container_ownership_is_checked_before_reuse(monkeypatch) -> None:
    from types import SimpleNamespace

    services = LocalProjectServices(ProjectConfig(services={}), project_id="ours")
    monkeypatch.setattr("gerbera_cli.setup.subprocess.run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=json.dumps([{
                            "Config": {"Labels": {"gerbera.project": "someone-else"}},
                        }])))

    with pytest.raises(RuntimeError, match="another deployment"):
        services.container_status("database")


def test_readiness_requires_a_service_report_not_an_open_port(monkeypatch) -> None:
    import httpx

    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    client = httpx.Client(transport=transport)
    monkeypatch.setattr("gerbera_cli.setup.httpx.Client", lambda **kwargs: client)

    assert readiness_report("http://sdk.example")["ready"] is False


def test_cli_waits_for_ready_not_merely_a_successful_http_request(monkeypatch) -> None:
    from unittest.mock import Mock

    services = LocalProjectServices(ProjectConfig(services={
        "sdk": ServiceSpec(managed=False, url="http://sdk.example"),
    }))
    reports = Mock(side_effect=[{"service": "sdk", "ready": False}, {"service": "sdk", "ready": True}])
    monkeypatch.setattr("gerbera_cli.setup.readiness_report", reports)
    monkeypatch.setattr("gerbera_cli.setup.time.sleep", lambda interval: None)

    services.wait_for_server()

    assert reports.call_count == 2


def test_cli_stops_waiting_when_managed_sdk_exits(monkeypatch) -> None:
    services = LocalProjectServices(ProjectConfig(services={"sdk": ServiceSpec(url="http://sdk.example")}))
    monkeypatch.setattr(LocalProjectServices, "server_running", lambda self: False)

    with pytest.raises(RuntimeError, match="sdk exited"):
        services.wait_for_server()


def test_cli_readiness_timeout_preserves_service_report(monkeypatch) -> None:
    from unittest.mock import Mock

    services = LocalProjectServices(ProjectConfig(
        services={"sdk": ServiceSpec(managed=False, url="http://sdk.example")},
        startup_timeout_seconds=1,
    ))
    monkeypatch.setattr("gerbera_cli.setup.time.monotonic", Mock(side_effect=[0, 0, 2]))
    monkeypatch.setattr("gerbera_cli.setup.time.sleep", lambda interval: None)
    monkeypatch.setattr("gerbera_cli.setup.readiness_report", lambda url: {"ready": False, "phase": "failed"})

    with pytest.raises(TimeoutError, match="failed"):
        services.wait_for_server()


def test_cli_accepts_current_ready_phase_contract(monkeypatch) -> None:
    import httpx
    from gerbera_protocol import ReadinessReport

    payload = ReadinessReport(service="sdk", phase="ready").model_dump(mode="json")
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    monkeypatch.setattr("gerbera_cli.setup.httpx.Client", lambda **kwargs: client)
    services = LocalProjectServices(ProjectConfig(services={
        "sdk": ServiceSpec(managed=False, url="http://sdk.example"),
    }))
    monkeypatch.setattr("gerbera_cli.setup.time.sleep", lambda interval: pytest.fail("Ready SDK must not be polled again"))

    services.wait_for_server()


@pytest.mark.parametrize("payload", [{"phase": "ready"}, {"ready": True}, [], {"service": "sdk", "phase": "unknown"}])
def test_cli_rejects_invalid_readiness_contract(monkeypatch, payload) -> None:
    import httpx

    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    monkeypatch.setattr("gerbera_cli.setup.httpx.Client", lambda **kwargs: client)

    assert readiness_report("http://sdk.example") == {"ready": False, "phase": "invalid_response"}


def test_cli_does_not_accept_readiness_from_another_service(monkeypatch) -> None:
    from unittest.mock import Mock

    services = LocalProjectServices(ProjectConfig(
        services={"sdk": ServiceSpec(managed=False, url="http://sdk.example")}, startup_timeout_seconds=1,
    ))
    monkeypatch.setattr("gerbera_cli.setup.time.monotonic", Mock(side_effect=[0, 0, 2]))
    monkeypatch.setattr("gerbera_cli.setup.time.sleep", lambda interval: None)
    monkeypatch.setattr("gerbera_cli.setup.readiness_report", lambda url: {"service": "harness", "ready": True})

    with pytest.raises(TimeoutError):
        services.wait_for_server()
