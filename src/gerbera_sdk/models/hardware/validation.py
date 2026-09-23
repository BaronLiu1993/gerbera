from dataclasses import dataclass

from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.validators import (
    HardwareSystemValidator,
    MovementSystemValidator,
)


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            formatted_errors = "\n".join(
                f"- {error}" for error in self.errors
            )
            raise ValueError(
                f"Hardware system validation failed:\n{formatted_errors}"
            )


class HardwareValidationFacade:
    @staticmethod
    def validate(hardware_system: HardwareSystem) -> ValidationResult:
        errors = HardwareSystemValidator.validate(hardware_system)
        registered_connections = (
            HardwareSystemValidator.registered_connections(hardware_system)
        )

        for movement_system in hardware_system.movement_systems:
            errors.extend(
                MovementSystemValidator.validate(
                    movement_system,
                    registered_connections,
                )
            )

        return ValidationResult(errors=tuple(errors))
