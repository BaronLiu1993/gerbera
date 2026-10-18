from gerbera_harness.tools.base import LocalTool, ToolSpec
from gerbera_harness.tools.registry import LocalToolRegistry

__all__ = [
    "LocalToolRegistry",
    "LocalTool",
    "ToolClient",
    "ToolSpec",
]


def __getattr__(name: str):
    if name == "ToolClient":
        from gerbera_harness.tools.client import ToolClient

        return ToolClient
    raise AttributeError(name)
