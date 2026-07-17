from gerbera_sdk.firmware.function.configurations import (
    DEVICES_MAPPING,
    MICROCONTROLLER_MAPPING,
)
from gerbera_sdk.firmware.function.parser import Parser
from gerbera_sdk.firmware.function.routing import Routing
from gerbera_sdk.models.hardware.microcontroller import Microcontroller


class Generator:
    @staticmethod
    def build_includes(microcontroller: Microcontroller) -> str:
        includes: list[str] = []
        normalized_includes: set[str] = set()
        board_mapping = MICROCONTROLLER_MAPPING.get(microcontroller.fqbn)
        for include_name in board_mapping.get("includes", ["Arduino.h"]):
            include = f"#include <{include_name}>"
            normalized_include = include.strip().lower()
            if normalized_include not in normalized_includes:
                includes.append(include)
                normalized_includes.add(normalized_include)

        for connection in microcontroller.connections:
            if connection.component_type not in DEVICES_MAPPING:
                raise ValueError(
                    f"Unsupported component type for firmware generation: "
                    f"{connection.component_type}"
                )

            builder = DEVICES_MAPPING[connection.component_type]()
            for library in builder.required_libraries():
                include_name = library.include

                if not include_name:
                    continue

                include = f"#include <{include_name}>"
                normalized_include = include.strip().lower()
                if normalized_include not in normalized_includes:
                    includes.append(include)
                    normalized_includes.add(normalized_include)

        return "\n".join(includes)

    @staticmethod
    def build_definitions(microcontroller: Microcontroller) -> str:
        definitions = []

        for connection in microcontroller.connections:
            if connection.component_type not in DEVICES_MAPPING:
                raise ValueError(
                    f"Unsupported firmware template for definitions: "
                    f"{connection.component_type}"
                )

            builder = DEVICES_MAPPING[connection.component_type]()
            definition = builder.build_definitions(connection).strip()
            if definition:
                definitions.append(definition)

        return "\n\n".join(definitions)

    @staticmethod
    def build_handlers(microcontroller: Microcontroller) -> str:
        handlers = []

        for connection in microcontroller.connections:
            if connection.component_type not in DEVICES_MAPPING:
                raise ValueError(
                    f"Unsupported component type for firmware generation: "
                    f"{connection.component_type}"
                )

            builder = DEVICES_MAPPING[connection.component_type]()
            handlers.append(builder.build_handler(connection))

        return "\n\n".join(handlers)

    @staticmethod
    def build_firmware(microcontroller: Microcontroller) -> str:
        includes = Generator.build_includes(microcontroller)
        parser_code = Parser.parse_command_code()
        definition_code = Generator.build_definitions(microcontroller)
        handler_code = Generator.build_handlers(microcontroller)
        setup_code = Routing.build_setup_code(microcontroller.connections)
        routing_code = Routing.build_loop_code(microcontroller.connections)

        return f"""{includes}

const long BAUD_RATE = {microcontroller.baud_rate};

{parser_code}

{definition_code}

{handler_code}

{setup_code}

{routing_code}
"""
