import time
from typing import Any

from core.runtime_state import RuntimeState
from ingest.api_client import AgentAPIClient
from ingest.event_queue import EventQueue


class EventSender:
    def __init__(self, config: dict[str, Any], logger, client: AgentAPIClient, queue: EventQueue, state: RuntimeState):
        self.config = config
        self.logger = logger
        self.client = client
        self.queue = queue
        self.state = state

    def flush_if_due(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self.state.last_flush < int(self.config.get("batch_interval_seconds", 15)):
            return
        events = self.queue.pending(limit=100)
        if not events:
            self.state.last_flush = now
            return
        try:
            accepted, duplicates = self.client.send_events(events)
            self.queue.delete([event["row_id"] for event in events])
            self.logger.info("Flushed events accepted=%s duplicates=%s", accepted, duplicates)
        except Exception as exc:
            self.queue.mark_failed([event["row_id"] for event in events], str(exc))
            self.logger.warning("Failed to flush events: %s", exc)
        self.state.last_flush = now
