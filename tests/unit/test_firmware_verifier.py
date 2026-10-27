import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from gerbera_sdk.firmware.firmware_dependencies import FirmwareDependencies
from gerbera_sdk.firmware.firmware_verifier import FirmwareVerifier
from gerbera_sdk.models.runtime.boards.board_runtime import BoardRuntime, FirmwareContractMismatch


@pytest.fixture
def verification(monkeypatch):
    board = SimpleNamespace(microcontroller_id="board-1")
    transport = Mock()
    runtime = SimpleNamespace(
        hardware_plan=SimpleNamespace(boards=(board,)),
        transport_factory=SimpleNamespace(create=Mock(return_value=transport)),
    )
    handshake = Mock()
    monkeypatch.setattr(BoardRuntime, "verify_contract", handshake)
    return SimpleNamespace(
        board=board, transport=transport, handshake=handshake,
        verifier=FirmwareVerifier(runtime),
    )


def test_matching_firmware_is_verified_and_transport_closed(verification) -> None:
    verification.verifier.verify()

    assert (
        verification.transport.connect.call_count,
        verification.handshake.call_args.args,
        verification.transport.close.call_count,
    ) == (1, (verification.board, verification.transport), 1)


@pytest.mark.parametrize("failure", [
    FirmwareContractMismatch("firmware differs"), TimeoutError("no handshake"),
])
def test_verification_fails_without_compiling_or_uploading(verification, monkeypatch, failure) -> None:
    commands = Mock()
    monkeypatch.setattr("subprocess.run", commands)
    verification.handshake.side_effect = failure

    with pytest.raises(type(failure), match=str(failure)):
        verification.verifier.verify()

    assert (commands.call_count, verification.transport.close.call_count) == (0, 1)


def test_verifier_closes_transport_when_connect_fails(verification) -> None:
    verification.transport.connect.side_effect = OSError("unavailable")

    with pytest.raises(OSError, match="unavailable"):
        verification.verifier.verify()

    assert verification.transport.close.call_count == 1


def test_arduino_inventory_uses_installed_version_not_available_releases(monkeypatch) -> None:
    monkeypatch.setattr("gerbera_sdk.firmware.firmware_dependencies.subprocess.run", lambda *args, **kwargs:
                        SimpleNamespace(stdout=json.dumps({"platforms": [
                            {"id": "arduino:avr", "installed_version": "1.8.6"},
                            {"id": "esp32:esp32", "latest_version": "3.0"},
                            {"id": "legacy", "version": "1.0"},
                        ]})))

    assert FirmwareDependencies.read_inventory("core") == {"arduino:avr"}


def test_arduino_inventory_rejects_retired_list_format(monkeypatch) -> None:
    monkeypatch.setattr(
        "gerbera_sdk.firmware.firmware_dependencies.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="[]"),
    )

    with pytest.raises(ValueError, match="must be an object"):
        FirmwareDependencies.read_inventory("core")
