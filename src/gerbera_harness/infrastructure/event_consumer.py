from dataclasses import dataclass, field

from gerbera_harness.memory import Memory


@dataclass
class EventConsumer:
    memory_bus: dict[str, Memory] = field(default_factory=dict)

    def register_memory(self, memory: Memory) -> None:
        self.memory_bus[memory.session_id] = memory
