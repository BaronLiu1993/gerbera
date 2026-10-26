import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from gerbera_sdk.firmware.reconciliation import FirmwareDependencies, FirmwareReconciler, InitialProvisioning
from gerbera_sdk.firmware.flash import Flash
from gerbera_sdk.models.runtime.boards.board_runtime import FirmwareContractMismatch


@pytest.fixture
def reconciliation(monkeypatch, tmp_path):
    board = SimpleNamespace(
        microcontroller_id="board-1", fqbn="arduino:avr:uno",
        firmware_upload_port="/dev/board-1",
    )
    runtime = SimpleNamespace(hardware_plan=SimpleNamespace(boards=(board,)))
    reconciler = FirmwareReconciler(runtime)
    inspect = Mock()
    install = Mock()
    flash = Mock()
    monkeypatch.setattr(FirmwareReconciler, "inspect", inspect)
    monkeypatch.setattr(FirmwareDependencies, "install", install)
    monkeypatch.setattr("gerbera_sdk.firmware.reconciliation.Flash.flash_boards", flash)
    monkeypatch.setattr("gerbera_sdk.firmware.reconciliation.FIRMWARE_PATH", tmp_path)
    return SimpleNamespace(
        board=board, reconciler=reconciler, inspect=inspect, install=install,
        flash=flash, authorization=InitialProvisioning(board),
    )


def authorize(target) -> None:
    target.authorization.path.parent.mkdir(parents=True)
    target.authorization.path.write_text(json.dumps({
        "microcontroller_id": "board-1", "fqbn": "arduino:avr:uno", "upload_port": "/dev/board-1",
    }))


def test_matching_live_handshake_does_not_install_or_flash(reconciliation) -> None:
    reconciliation.reconciler.reconcile()

    assert (reconciliation.inspect.call_count, reconciliation.install.call_count,
            reconciliation.flash.call_count) == (1, 0, 0)


def test_confirmed_mismatch_flashes_then_reverifies(reconciliation) -> None:
    reconciliation.inspect.side_effect = [FirmwareContractMismatch("changed"), None]

    reconciliation.reconciler.reconcile()

    assert (reconciliation.inspect.call_count, reconciliation.install.call_count,
            reconciliation.flash.call_count) == (2, 1, 1)


@pytest.mark.parametrize("failure", [OSError("disconnected"), ValueError("malformed"),
                                     RuntimeError("board identity mismatch")])
def test_unconfirmed_failure_never_flashes(reconciliation, failure) -> None:
    reconciliation.inspect.side_effect = failure

    with pytest.raises(type(failure)):
        reconciliation.reconciler.reconcile()

    assert reconciliation.flash.call_count == 0


def test_handshake_timeout_without_first_provisioning_permission_never_flashes(reconciliation) -> None:
    reconciliation.inspect.side_effect = TimeoutError()

    with pytest.raises(RuntimeError, match="automatic flashing is unsafe"):
        reconciliation.reconciler.reconcile()

    assert reconciliation.flash.call_count == 0


def test_first_provisioning_requires_exact_upload_target(reconciliation) -> None:
    authorize(reconciliation)
    reconciliation.authorization.path.write_text("{}")
    reconciliation.inspect.side_effect = TimeoutError()

    with pytest.raises(RuntimeError, match="target does not match"):
        reconciliation.reconciler.reconcile()

    assert reconciliation.flash.call_count == 0


def test_dependency_failure_preserves_first_provisioning_permission(reconciliation) -> None:
    authorize(reconciliation)
    reconciliation.inspect.side_effect = TimeoutError()
    reconciliation.install.side_effect = RuntimeError("download failed")

    with pytest.raises(RuntimeError, match="download failed"):
        reconciliation.reconciler.reconcile()

    assert reconciliation.authorization.path.is_file()


def test_first_provisioning_permission_is_consumed_by_upload_callback(reconciliation) -> None:
    authorize(reconciliation)
    reconciliation.inspect.side_effect = [TimeoutError(), None]
    reconciliation.flash.side_effect = lambda *args, **kwargs: kwargs["before_upload"]()

    reconciliation.reconciler.reconcile()

    assert not reconciliation.authorization.path.exists()


def test_compile_failure_preserves_first_provisioning_permission(reconciliation) -> None:
    authorize(reconciliation)
    reconciliation.inspect.side_effect = TimeoutError()
    reconciliation.flash.side_effect = RuntimeError("compile failed")

    with pytest.raises(RuntimeError, match="compile failed"):
        reconciliation.reconciler.reconcile()

    assert reconciliation.authorization.path.is_file()


def test_flashed_board_must_pass_post_upload_handshake(reconciliation) -> None:
    reconciliation.inspect.side_effect = [
        FirmwareContractMismatch("changed"), FirmwareContractMismatch("still wrong"),
    ]

    with pytest.raises(FirmwareContractMismatch, match="still wrong"):
        reconciliation.reconciler.reconcile()


def test_arduino_inventory_uses_installed_version_not_available_releases(monkeypatch) -> None:
    monkeypatch.setattr("gerbera_sdk.firmware.reconciliation.subprocess.run", lambda *args, **kwargs:
                        SimpleNamespace(stdout=json.dumps({"platforms": [
                            {"id": "arduino:avr", "installed_version": "1.8.6"},
                            {"id": "esp32:esp32", "latest_version": "3.0"},
                        ]})))

    assert FirmwareDependencies.read_inventory("core") == {"arduino:avr"}


def test_upload_authorization_runs_after_compile_before_upload(monkeypatch, tmp_path) -> None:
    calls = []
    board = SimpleNamespace(
        microcontroller_id="board", firmware_upload_port="/dev/board", fqbn="arduino:avr:uno",
    )
    plan = SimpleNamespace(hardware_system_id="robot")
    monkeypatch.setattr(Flash, "generate_files", lambda hardware: {"board": tmp_path / "board.ino"})
    monkeypatch.setattr(Flash, "record_firmware_digest", lambda board: calls.append("record"))
    monkeypatch.setattr("gerbera_sdk.firmware.flash.subprocess.run", lambda command, **kwargs: calls.append(command[1]))

    Flash.flash_boards(plan, (board,), before_upload=lambda: calls.append("authorize"))

    assert calls == ["compile", "authorize", "upload", "record"]


def test_compile_failure_does_not_consume_upload_authorization(monkeypatch, tmp_path) -> None:
    board = SimpleNamespace(
        microcontroller_id="board", firmware_upload_port="/dev/board", fqbn="arduino:avr:uno",
    )
    plan = SimpleNamespace(hardware_system_id="robot")
    permission = Mock()
    monkeypatch.setattr(Flash, "generate_files", lambda hardware: {"board": tmp_path / "board.ino"})
    monkeypatch.setattr("gerbera_sdk.firmware.flash.subprocess.run", Mock(side_effect=RuntimeError("compile")))

    with pytest.raises(RuntimeError, match="Failed to flash"):
        Flash.flash_boards(plan, (board,), before_upload=permission)

    assert permission.call_count == 0
