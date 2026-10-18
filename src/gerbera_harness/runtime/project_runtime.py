from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class StartupStage(str, Enum):
    DATABASE = "database"
    SERVER = "server"
    HARNESS = "harness"


@dataclass(frozen=True)
class StartupOptions:
    flash_firmware: bool = True
    start_harness: bool = True


class ProjectServices(Protocol):
    def preflight(self) -> None: ...

    def validate_hardware(self) -> None: ...

    def start_database(self) -> bool: ...

    def prepare_database(self) -> None: ...

    def setup_firmware(self) -> None: ...

    def start_server(self) -> bool: ...

    def wait_for_server(self) -> None: ...

    def start_harness(self) -> bool: ...

    def rollback(self, stages: tuple[StartupStage, ...]) -> None: ...

    def stop(self) -> None: ...

    def status(self) -> dict[str, object]: ...

    def logs(self, follow: bool) -> None: ...

    def doctor(self) -> tuple[str, ...]: ...


@dataclass
class ProjectRuntime:
    services: ProjectServices

    def start(self, options: StartupOptions = StartupOptions()) -> None:
        started_stages: list[StartupStage] = []
        try:
            self.services.preflight()
            self.services.validate_hardware()
            if self.services.start_database():
                started_stages.append(StartupStage.DATABASE)
            self.services.prepare_database()
            if options.flash_firmware:
                self.services.setup_firmware()
            if self.services.start_server():
                started_stages.append(StartupStage.SERVER)
            self.services.wait_for_server()
            if options.start_harness and self.services.start_harness():
                started_stages.append(StartupStage.HARNESS)
        except BaseException:
            self.services.rollback(tuple(reversed(started_stages)))
            raise

    def stop(self) -> None:
        self.services.stop()

    def status(self) -> dict[str, object]:
        return self.services.status()

    def logs(self, follow: bool = False) -> None:
        self.services.logs(follow)

    def doctor(self) -> tuple[str, ...]:
        return self.services.doctor()
