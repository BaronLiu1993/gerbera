from dataclasses import dataclass, field
import json
from gerbera_harness.memory.event import Event


# No need for sqlite we can use postgres
@dataclass
class Memory:
    pass