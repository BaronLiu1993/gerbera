from gerbera_sdk.MCP.function.configurations import (
    BUILDER_MAPPING,
    MICROCONTROLLER_MAPPING,
)
from gerbera_sdk.MCP.function.parser import Parser
from gerbera_sdk.MCP.function.routing import Routing
from gerbera_sdk.hardware.microcontroller import Microcontroller


class Libraries:
    @staticmethod
    def build_includes(microcontroller: Microcontroller) -> str:
        includes: list[str] = []
        normalized_includes: set[str] = set()
        board_mapping = MICROCONTROLLER_MAPPING.get(microcontroller.fqbn, {})
        for include_name in board_mapping.get("includes", ["Arduino.h"]):
            include = f"#include <{include_name}>"
            normalized_include = include.strip().lower()
            if normalized_include not in normalized_includes:
                includes.append(include)
                normalized_includes.add(normalized_include)

        import_overrides = board_mapping.get("library_import_overrides", {})

        for connection in microcontroller.connections:
            if connection.component_type not in BUILDER_MAPPING:
                raise ValueError(
                    f"Unsupported component type for firmware generation: "
                    f"{connection.component_type}"
                )

            builder = BUILDER_MAPPING[connection.component_type]()
            for library in builder.required_libraries():
                install_name = library.get("install", "")
                include_name = library.get("include")

                if install_name in import_overrides:
                    include_name = import_overrides[install_name]

                if not include_name:
                    continue

                include = f"#include <{include_name}>"
                normalized_include = include.strip().lower()
                if normalized_include not in normalized_includes:
                    includes.append(include)
                    normalized_includes.add(normalized_include)

        return "\n".join(includes)

    @staticmethod
    def build_handlers(microcontroller: Microcontroller) -> str:
        handlers = []

        for connection in microcontroller.connections:
            if connection.component_type not in BUILDER_MAPPING:
                raise ValueError(
                    f"Unsupported component type for firmware generation: "
                    f"{connection.component_type}"
                )

            builder = BUILDER_MAPPING[connection.component_type]()
            handlers.append(builder.build_handler(connection))

        return "\n\n".join(handlers)

    @staticmethod
    def build_firmware(microcontroller: Microcontroller) -> str:
        includes = Libraries.build_includes(microcontroller)
        parser_code = Parser.parse_command_code()
        handler_code = Libraries.build_handlers(microcontroller)
        setup_code = Routing.build_setup_code()
        routing_code = Routing.build_loop_code(microcontroller.connections)

        return f"""{includes}

const int BAUD_RATE = {microcontroller.baud_rate};

{parser_code}

{handler_code}

{setup_code}

{routing_code}
"""
