from dataclasses import dataclass


@dataclass
class Settings:
    app_name: str = "gerbera-cli"
    debug: bool = False


def get_settings() -> Settings:
    return Settings()
