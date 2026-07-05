from enum import Enum


class RoleEnum(Enum):
    READ = "read"
    WRITE = "write"


class ConnectionsConfig:
    def __init__(self, library):
        self.library = library
        self.pins = []  # [{"id": "...", "role": "...", "pin": 12}, ...]

    def get_functionality(self, id: str):
        for pin_config in self.pins:
            if pin_config["id"] == id:
                return pin_config
        return None

    def add_functionality(self, id: str, role: RoleEnum, pin: int) -> bool:
        if self.get_functionality(id) is not None:
            return False

        self.pins.append(
            {
                "id": id,
                "role": role.value,
                "pin": pin,
            }
        )
        return True

    def to_dict(self) -> dict:
        return {
            "library": self.library,
            "pins": self.pins,
        }

    @classmethod
    def from_dict(cls, payload: dict):
        config = cls(payload["library"])
        config.pins = payload.get("pins", [])
        return config
