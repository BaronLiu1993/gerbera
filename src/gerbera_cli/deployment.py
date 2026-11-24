from dataclasses import dataclass
from enum import Enum
from typing import Protocol

@dataclass
class ProjectRuntime:
    services: ProjectServices

    def start(self) -> None:
        started = []
        try:
            if self.services.start_database():
                started.append(StartupStage.DATABASE)
            if self.services.start_server():
                started.append(StartupStage.SERVER)
            self.services.wait_for_server()
        except BaseException as error:
            try:
                self.services.rollback(tuple(reversed(started)))
            except Exception as cleanup_error:
                error.add_note(f"Deployment rollback also failed: {cleanup_error}")
            raise

    def stop(self) -> None:
        self.services.stop()

    def status(self) -> dict[str, object]:
        return self.services.status()

    def logs(self, follow: bool = False) -> None:
        self.services.logs(follow)

    def doctor(self) -> dict[str, object]:
        return self.services.doctor()
