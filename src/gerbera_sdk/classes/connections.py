from dataclasses import dataclass
from enum import Enum
from typing import List


class ConnectionMode(str, Enum):
    READ = "read"
    WRITE = "write"
    BOTH = "both"


@dataclass
class Connection:
    micro_controller_id: str
    name: str
    pins: List[str]
    mode: ConnectionMode
    component_type: str

    

    
