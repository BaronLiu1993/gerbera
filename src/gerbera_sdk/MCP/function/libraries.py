from gerbera_sdk.MCP.function.configurations import BUILDER_MAPPING
from gerbera_sdk.MCP.function.parser import Parser
from gerbera_sdk.MCP.function.routing import Routing
from gerbera_sdk.hardware.microcontroller import Microcontroller


class Libraries:
    @staticmethod
    def build_includes(microcontroller: Microcontroller) -> str:
        includes = ["#include <Arduino.h>"]

        for connection in microcontroller.connections:
            if connection.component_type not in BUILDER_MAPPING:
                raise ValueError(
                    f"Unsupported component type for firmware generation: "
                    f"{connection.component_type}"
                )

            builder = BUILDER_MAPPING[connection.component_type]()
            for include in builder.build_includes():
                if include not in includes:
                    includes.append(include)

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
        routing_code = Routing.build_loop_code(microcontroller.connections)

        return f"""{includes}

const int BAUD_RATE = {microcontroller.baud_rate};

{parser_code}

{handler_code}

{routing_code}
"""
