from dataclasses import dataclass, field

import pytest

from gerbera_harness.runtime import (
    ProjectRuntime,
    StartupOptions,
    StartupStage,
)


@dataclass
class RecordingServices:
    calls: list[str] = field(default_factory=list)
    fail_at: str | None = None

    def record(self, call: str) -> None:
        self.calls.append(call)
        if call == self.fail_at:
            raise RuntimeError(call)

    def preflight(self) -> None:
        self.record("preflight")

    def validate_hardware(self) -> None:
        self.record("validate_hardware")

    def start_database(self) -> bool:
        self.record("start_database")
        return True

    def prepare_database(self) -> None:
        self.record("prepare_database")

    def setup_firmware(self) -> None:
        self.record("setup_firmware")

    def start_server(self) -> bool:
        self.record("start_server")
        return True

    def wait_for_server(self) -> None:
        self.record("wait_for_server")

    def start_harness(self) -> bool:
        self.record("start_harness")
        return True

    def rollback(self, stages: tuple[StartupStage, ...]) -> None:
        values = ",".join(stage.value for stage in stages)
        self.calls.append(f"rollback:{values}")

    def stop(self) -> None:
        self.record("stop")

    def status(self) -> dict[str, object]:
        return {"server": True}

    def logs(self, follow: bool) -> None:
        self.record(f"logs:{follow}")

    def doctor(self) -> tuple[str, ...]:
        return ("PASS test",)


def test_start_runs_complete_lifecycle_in_order() -> None:
    services = RecordingServices()

    ProjectRuntime(services).start()

    assert services.calls == [
        "preflight",
        "validate_hardware",
        "start_database",
        "prepare_database",
        "setup_firmware",
        "start_server",
        "wait_for_server",
        "start_harness",
    ]


def test_start_can_skip_firmware_and_harness() -> None:
    services = RecordingServices()

    ProjectRuntime(services).start(
        StartupOptions(flash_firmware=False, start_harness=False)
    )

    assert services.calls == [
        "preflight",
        "validate_hardware",
        "start_database",
        "prepare_database",
        "start_server",
        "wait_for_server",
    ]


def test_start_rolls_back_only_services_started_by_current_run() -> None:
    services = RecordingServices(fail_at="wait_for_server")

    with pytest.raises(RuntimeError):
        ProjectRuntime(services).start()

    assert services.calls[-1] == "rollback:server,database"
