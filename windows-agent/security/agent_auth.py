from typing import Any


def has_credentials(config: dict[str, Any]) -> bool:
    return all([
        config.get("agent_token_id"),
        config.get("agent_token"),
        config.get("security_key"),
    ])


def auth_headers(config: dict[str, Any]) -> dict[str, str]:
    return {
        "X-Agent-Token-Id": config["agent_token_id"],
        "X-Agent-Token": config["agent_token"],
        "X-Agent-Security-Key": config["security_key"],
    }


def save_credentials(config: dict[str, Any], credentials: dict[str, Any], save_config) -> None:
    config["agent_id"] = credentials["agent_id"]
    config["agent_token_id"] = credentials["agent_token_id"]
    config["agent_token"] = credentials["agent_token"]
    config["security_key"] = credentials["security_key"]
    config["pending_request_id"] = ""
    save_config(config)


def clear_credentials(config: dict[str, Any], save_config, logger=None) -> None:
    if logger is not None:
        logger.warning("Agent credentials rejected by backend; registration required")
    config["agent_id"] = None
    config["agent_token_id"] = ""
    config["agent_token"] = ""
    config["security_key"] = ""
    save_config(config)


def reset_auth_state(config: dict[str, Any], save_config) -> None:
    config["agent_id"] = None
    config["agent_token_id"] = ""
    config["agent_token"] = ""
    config["security_key"] = ""
    config["pending_request_id"] = ""
    save_config(config)
