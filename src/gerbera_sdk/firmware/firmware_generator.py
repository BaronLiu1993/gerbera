from dataclasses import dataclass
from importlib.resources import files
import json
from pathlib import Path
from string import Template
from textwrap import indent
from typing import TYPE_CHECKING

from gerbera_sdk.config.firmware_config import load_firmware_config
from gerbera_sdk.firmware.firmware_schema import MAX_SERIAL_MESSAGE_BYTES
from gerbera_sdk.paths import FIRMWARE_PATH

if TYPE_CHECKING:
    from gerbera_sdk.models.hardware.microcontroller import Microcontroller


@dataclass(frozen=True)
class FirmwareGenerator:
    board: "Microcontroller"

    def generate(self) -> str:
        firmware = files("gerbera_sdk.firmware")
        includes = {}
        definitions = []
        setup = []
        handlers = []
        dispatch = []
        streams = []
        max_message_fields = 1

        for index, connection in enumerate(self.board.connections):
            config = load_firmware_config(connection.component_type)
            symbol = f"device_{index}"
            target = json.dumps(connection.connection_id, ensure_ascii=False)
            values = {"symbol": symbol, "target": target}

            if connection.include is not None:
                includes[connection.include] = None
            for pin_name, mode in config["pin_modes"].items():
                pin = getattr(connection, pin_name)
                values[pin_name] = pin
                setup.append(f"pinMode({pin}, {mode});")

            definitions.append(Template(config.get("definitions", "")).substitute(values))
            setup.append(Template(config.get("setup", "")).substitute(values))

            routes = []
            stream = config.get("stream")
            if connection.supports_streaming and stream is not None:
                definitions.append(f"bool {symbol}_streaming = false;")
                body = Template(stream["body"]).substitute(
                    values, response_field=json.dumps(stream["field"])
                ).strip()
                streams.append(f"if ({symbol}_streaming) {{\n{indent(body, '  ')}\n}}")
                routes.append(
                    'if (command.field("stream_enabled").length() > 0) {\n'
                    f"  setStreamEnabled(command, {symbol}_streaming);\n  return;\n}}"
                )

            write = config.get("write")
            if write is not None:
                name = f"{symbol}_write"
                max_message_fields = max(max_message_fields, len(write["params"]))
                body = Template(write["body"]).substitute(
                    values, response_field=json.dumps(write["response_field"])
                ).strip()
                handlers.append(
                    f"void {name}(const SerialMessage& command) {{\n{indent(body, '  ')}\n}}"
                )
                routes.append(f"{name}(command);\nreturn;")

            if routes:
                route = indent("\n".join(routes), "  ")
                dispatch.append(f"if (command.target == {target}) {{\n{route}\n}}")

        sketch = firmware.joinpath("sketch.ino.template")
        return Template(sketch.read_text(encoding="utf-8")).substitute(
            includes="\n".join(f"#include <{name}>" for name in includes),
            definitions="\n".join(definitions),
            setup=indent("\n".join(setup), "  "),
            handlers="\n\n".join(handlers),
            dispatch=indent("\n".join(dispatch), "    "),
            streams=indent("\n".join(streams), "  "),
            baud_rate=self.board.baud_rate,
            max_message_fields=max_message_fields,
            max_message_bytes=MAX_SERIAL_MESSAGE_BYTES,
        )

    def write_files(self) -> Path:
        board_id = self.board.microcontroller_id
        path = FIRMWARE_PATH / board_id / f"{board_id}.ino"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.generate(), encoding="utf-8")
        return path
