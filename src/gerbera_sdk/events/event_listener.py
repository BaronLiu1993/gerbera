from dataclasses import dataclass, field
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.utils import build_event_key
from gerbera_sdk.models.hardware_system import HardwareSystem
from serial import Serial
import threading
import uuid
from serial import SerialException


@dataclass
class EventListener:
    hardware_system: HardwareSystem
    _serial_pool: dict[str, Serial]
    _threads: dict[str, threading.Thread]
    _event_bus: EventBus
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _stop_event: threading.Event = field(default_factory=threading.Event)

    def create_listeners(self):
        self._stop_event.clear()
        for microcontroller in self.hardware_system.microcontrollers:
            microcontroller_id = microcontroller.id

            thread = threading.Thread(
                target=self._listen_loop,
                args=(microcontroller_id,),
                daemon=True,
                name=f"serial-listener-{microcontroller_id}",
            )

            self._threads[microcontroller_id] = thread
            thread.start()

    def stop_listeners(self):
        self._stop_event.set()

        for serial_connection in self._serial_pool.values():
            close = getattr(serial_connection, "close", None)
            if callable(close):
                close()

        for thread in self._threads.values():
            thread.join(timeout=1)

        self._threads.clear()

    def _parse_payload(self, line: str):
        res_payload = {}

        tokens = line.split(",")
        if len(tokens) < 2:
            return None

        event_type, event_name, payload_tokens = tokens[0], tokens[1], tokens[2:]

        for payload_token in payload_tokens:
            if ":" not in payload_token:
                continue

            key, val = payload_token.split(":", 1)
            if key in res_payload:
                raise ValueError("Key already exists")
            res_payload[key] = val

        return event_type, event_name, res_payload


    def _dispatch_event_to_event_bus(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: dict[str, str],
    ) -> None:
        event_key = build_event_key(event_type, microcontroller_id, event_name)
        handler = self._event_bus.get_handler(event_key)
        handler.perform_work(payload)
    
    def _dispatch_event_to_rule_engine(self):
        pass

    def _listen_loop(self, microcontroller_id):
        serial_connection = self._serial_pool[microcontroller_id]
        while not self._stop_event.is_set():
            try:
                line = serial_connection.readline()
            except (OSError, SerialException):
                if self._stop_event.is_set():
                    return
                raise

            if isinstance(line, bytes):
                line = line.decode(errors="ignore")
            line = line.strip()
            if not line:
                continue

            parsed_payload = self._parse_payload(line)
            if parsed_payload is None:
                continue

            event_type, event_name, payload = parsed_payload

            self._dispatch_event_to_rule_engine(
                
            )

            self._dispatch_event_to_event_bus(
                event_type,
                microcontroller_id,
                event_name,
                payload,
            )
