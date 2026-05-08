import sys

from core.config_loader import load_config
from core.logger import setup_logging
from executor.agent_runner import AgentRunner, InfraProTrackAgentService, handle_service_commands


def main() -> None:
    if handle_service_commands(sys.argv):
        return

    config = load_config()
    logger = setup_logging(config)
    logger.info("Using config: %s", config.get("_config_path"))
    logger.info("Using server URL: %s", config["server_url"])
    AgentRunner(config, logger).run_from_argv(sys.argv[1:])


if __name__ == "__main__":
    main()
