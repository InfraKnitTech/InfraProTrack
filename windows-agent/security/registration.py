import time
from typing import Any

from core.config_loader import save_config
from security.agent_auth import has_credentials, save_credentials


def build_identity_payload(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "device_id": config["device_id"],
        "hostname": config["hostname"],
        "os_type": config["os_type"],
        "os_version": config["os_version"],
        "agent_version": config["agent_version"],
        "username": config["username"],
        "master_password": config.get("master_password") or "",
    }


def ensure_registered_once(client, config: dict[str, Any], logger) -> bool:
    if has_credentials(config):
        return True

    pending_id = config.get("pending_request_id")
    if pending_id:
        body = client.registration_status(pending_id)
        if body["status"] == "approved" and body.get("credentials"):
            save_credentials(config, body["credentials"], save_config)
            logger.info("Agent approved and credentials stored")
            return True
        if body["status"] == "rejected":
            config["pending_request_id"] = ""
            save_config(config)
            logger.error("Agent registration rejected")
        return False

    body = client.register_device(build_identity_payload(config))
    if body["status"] == "active" and body.get("credentials"):
        save_credentials(config, body["credentials"], save_config)
        logger.info("Agent auto-registered")
        return True

    if body["status"] == "pending_approval":
        config["pending_request_id"] = body["request_id"]
        save_config(config)
        logger.warning("Agent registration pending admin approval: %s", body["request_id"])
        return False

    return False


def wait_for_registration(client, config: dict[str, Any], logger, sleep_seconds: int = 15) -> bool:
    while not ensure_registered_once(client, config, logger):
        logger.info("Waiting for registration approval...")
        time.sleep(sleep_seconds)
    try:
        client.pull_runtime_config()
    except Exception as exc:
        logger.warning("Could not pull runtime config: %s", exc)
    return True
