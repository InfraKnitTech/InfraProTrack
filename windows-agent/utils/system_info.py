import os
import platform
import socket
import uuid


def get_hostname() -> str:
    return socket.gethostname()


def get_username() -> str:
    try:
        return os.environ.get("USERNAME") or os.getlogin()
    except OSError:
        return "unknown"


def get_os_version() -> str:
    return platform.platform()


def build_device_id(hostname: str) -> str:
    raw = f"{hostname}:{uuid.getnode()}:{platform.platform()}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw))
