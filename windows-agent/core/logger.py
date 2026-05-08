import logging
from logging.handlers import RotatingFileHandler
from typing import Any

from core.config_loader import agent_data_path


def setup_logging(config: dict[str, Any]) -> logging.Logger:
    logger = logging.getLogger("InfraProTrackAgent")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    log_path = agent_data_path(config, config.get("log_path", "agent.log"))
    try:
        handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    except PermissionError:
        pass

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(console)
    return logger
