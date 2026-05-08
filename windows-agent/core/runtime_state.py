from dataclasses import dataclass, field
from datetime import datetime

from utils.time_utils import utc_now


@dataclass
class RuntimeState:
    current_window: object | None = None
    current_start: datetime = field(default_factory=utc_now)
    idle_started_at: datetime | None = None
    last_heartbeat: float = 0.0
    last_flush: float = 0.0
    running: bool = True
