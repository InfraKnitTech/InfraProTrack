import json
import os

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

with open(_config_path, "r") as f:
    _cfg = json.load(f)

class ServerConfig:
    PORT: int = _cfg["server"]["port"]
    JWT_SECRET: str = _cfg["server"]["jwtSecret"]
    JWT_EXPIRES_IN: str = _cfg["server"]["jwtExpiresIn"]

class MySQLConfig:
    HOST: str = _cfg["mysql"]["host"]
    PORT: int = _cfg["mysql"]["port"]
    DATABASE: str = _cfg["mysql"]["database"]
    USERNAME: str = _cfg["mysql"]["username"]
    PASSWORD: str = _cfg["mysql"]["password"]
    POOL_MAX: int = _cfg["mysql"]["pool"]["max"]
    POOL_MIN: int = _cfg["mysql"]["pool"]["min"]

    @property
    def URL(self) -> str:
        return (
            f"mysql+pymysql://{self.USERNAME}:{self.PASSWORD}"
            f"@{self.HOST}:{self.PORT}/{self.DATABASE}"
        )

class EmailConfig:
    HOST: str = _cfg["email"]["host"]
    PORT: int = _cfg["email"]["port"]
    FROM: str = _cfg["email"]["from"]

class AgentConfig:
    MASTER_PASSWORD: str = _cfg["agent"]["masterAgentPassword"]
    IDLE_THRESHOLD: int = _cfg["agent"]["idleThresholdSeconds"]
    CHECK_INTERVAL: int = _cfg["agent"]["checkIntervalSeconds"]
    BATCH_INTERVAL: int = _cfg["agent"]["batchIntervalSeconds"]
    SCREENSHOT_TRIGGER: float = _cfg["agent"]["screenshotTriggerProductivityBelow"]

server = ServerConfig()
mysql = MySQLConfig()
email = EmailConfig()
agent = AgentConfig()
