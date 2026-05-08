from typing import Any

import requests

from security.agent_auth import auth_headers, clear_credentials
from core.config_loader import save_config
from utils.time_utils import utc_iso


class AgentAPIClient:
    def __init__(self, config: dict[str, Any], logger):
        self.config = config
        self.logger = logger
        self.session = requests.Session()

    @property
    def base_url(self) -> str:
        return self.config["server_url"].rstrip("/")

    def register_device(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(f"{self.base_url}/api/agents/register", json=payload, timeout=15)
        response.raise_for_status()
        return response.json()

    def registration_status(self, request_id: str) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}/api/agents/registration-status/{request_id}", timeout=15)
        response.raise_for_status()
        return response.json()

    def heartbeat(self, payload: dict[str, Any]) -> None:
        response = self.session.post(
            f"{self.base_url}/api/agents/heartbeat",
            headers=auth_headers(self.config),
            json={"status": "online", "captured_at": utc_iso(), "payload": payload},
            timeout=15,
        )
        if response.status_code == 401:
            clear_credentials(self.config, save_config, self.logger)
        response.raise_for_status()

    def send_events(self, events: list[dict[str, Any]]) -> tuple[int, int]:
        response = self.session.post(
            f"{self.base_url}/api/agents/events/batch",
            headers=auth_headers(self.config),
            json={"events": [{k: v for k, v in event.items() if k != "row_id"} for event in events]},
            timeout=30,
        )
        if response.status_code == 401:
            clear_credentials(self.config, save_config, self.logger)
        response.raise_for_status()
        body = response.json()
        return int(body["accepted"]), int(body["duplicates"])

    def pull_runtime_config(self) -> None:
        response = self.session.get(
            f"{self.base_url}/api/agents/config",
            headers=auth_headers(self.config),
            timeout=15,
        )
        if response.status_code == 401:
            clear_credentials(self.config, save_config, self.logger)
        response.raise_for_status()
        body = response.json()
        self.config["idle_threshold_seconds"] = body["idle_threshold_seconds"]
        self.config["check_interval_seconds"] = body["check_interval_seconds"]
        self.config["batch_interval_seconds"] = body["batch_interval_seconds"]
        save_config(self.config)
