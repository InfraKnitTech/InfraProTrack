import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

from utils.system_info import build_device_id, get_os_version, get_username


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"

AGENT_VERSION = "0.1.0"

DEFAULT_CONFIG: dict[str, Any] = {
    "server_url": "http://127.0.0.1:5002",
    "master_password": "InfraAgent@2026",
    "agent_id": None,
    "agent_token_id": "",
    "agent_token": "",
    "security_key": "",
    "pending_request_id": "",
    "device_id": "",
    "hostname": "",
    "os_type": "windows",
    "os_version": "",
    "agent_version": AGENT_VERSION,
    "username": "",
    "check_interval_seconds": 1,
    "idle_threshold_seconds": 60,
    "heartbeat_interval_seconds": 30,
    "batch_interval_seconds": 15,
    "queue_db_path": "agent_queue.sqlite3",
    "log_path": "agent.log",
    "idle_reason_categories": [
        "Lunch / meal break",
        "Meeting",
        "Phone call",
        "Personal break",
        "System issue",
        "Other",
    ],
}


def load_config() -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    template_config: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            template_config = json.load(f)
            config.update(template_config)
    config_exists = CONFIG_PATH.exists()
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            config.update(json.load(f))

    changed = not config_exists
    if not config.get("hostname"):
        config["hostname"] = socket.gethostname()
        changed = True
    if not config.get("username"):
        config["username"] = get_username()
        changed = True
    config["os_type"] = "windows"
    if not config.get("os_version"):
        config["os_version"] = get_os_version()
        changed = True
    if config.get("agent_version") != AGENT_VERSION:
        config["agent_version"] = AGENT_VERSION
        changed = True
    if not config.get("device_id"):
        config["device_id"] = build_device_id(config["hostname"])
        changed = True

    for field in ("server_url", "master_password"):
        template_value = template_config.get(field)
        if template_value and config.get(field) != template_value:
            config[field] = template_value
            changed = True

    config["_config_path"] = str(CONFIG_PATH)
    config["_base_dir"] = str(BASE_DIR)
    if changed:
        save_config(config)
    return config


def save_config(config: dict[str, Any]) -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in config.items() if not k.startswith("_")}
    try:
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except PermissionError:
        print(
            f"Warning: could not persist runtime config to {CONFIG_PATH}; using in-memory values for this run.",
            file=sys.stderr,
        )


def agent_data_path(config: dict[str, Any], path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else BASE_DIR / path
