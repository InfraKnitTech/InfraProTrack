import argparse
import ctypes
import json
import logging
import os
import platform
import socket
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import psutil
import requests

AGENT_VERSION = "0.1.0"
BASE_DIR = Path(__file__).resolve().parent
CONFIG_TEMPLATE_PATH = BASE_DIR / "config.json"
DATA_DIR = Path(
    os.environ.get(
        "INFRAPROTRACK_AGENT_HOME",
        str(Path(os.environ.get("ProgramData", str(BASE_DIR))) / "InfraProTrack" / "Agent"),
    )
)
CONFIG_PATH = DATA_DIR / "config.json"


DEFAULT_CONFIG = {
    "server_url": "http://127.0.0.1:5000",
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
    "check_interval_seconds": 5,
    "idle_threshold_seconds": 60,
    "heartbeat_interval_seconds": 30,
    "batch_interval_seconds": 15,
    "queue_db_path": "agent_queue.sqlite3",
    "log_path": "agent.log",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    return utc_now().isoformat()


def load_config() -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    if CONFIG_TEMPLATE_PATH.exists():
        with CONFIG_TEMPLATE_PATH.open("r", encoding="utf-8") as f:
            config.update(json.load(f))
    config_exists = CONFIG_PATH.exists()
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            config.update(json.load(f))

    changed = not config_exists
    if not config.get("hostname"):
        config["hostname"] = socket.gethostname()
        changed = True
    if not config.get("username"):
        try:
            username = os.environ.get("USERNAME") or os.getlogin()
        except OSError:
            username = "unknown"
        config["username"] = username
        changed = True
    config["os_type"] = "windows"
    if not config.get("os_version"):
        config["os_version"] = platform.platform()
        changed = True
    if config.get("agent_version") != AGENT_VERSION:
        config["agent_version"] = AGENT_VERSION
        changed = True
    if not config.get("device_id"):
        config["device_id"] = build_device_id(config["hostname"])
        changed = True
    if changed:
        save_config(config)
    return config


def save_config(config: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def agent_data_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else DATA_DIR / path


def build_device_id(hostname: str) -> str:
    raw = f"{hostname}:{uuid.getnode()}:{platform.platform()}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw))


def setup_logging(config: dict[str, Any]) -> logging.Logger:
    logger = logging.getLogger("InfraProTrackAgent")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_path = agent_data_path(config.get("log_path", "agent.log"))
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


class EventQueue:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                )
                """
            )

    def enqueue(self, event_type: str, payload: dict[str, Any], captured_at: str | None = None) -> None:
        event_id = str(uuid.uuid4())
        captured = captured_at or utc_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO events(event_id, event_type, captured_at, payload) VALUES (?, ?, ?, ?)",
                (event_id, event_type, captured, json.dumps(payload)),
            )

    def pending(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, event_id, event_type, captured_at, payload
                FROM events
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "row_id": row[0],
                "event_id": row[1],
                "event_type": row[2],
                "captured_at": row[3],
                "payload": json.loads(row[4]),
            }
            for row in rows
        ]

    def delete(self, row_ids: list[int]) -> None:
        if not row_ids:
            return
        placeholders = ",".join("?" for _ in row_ids)
        with self._connect() as conn:
            conn.execute(f"DELETE FROM events WHERE id IN ({placeholders})", row_ids)

    def mark_failed(self, row_ids: list[int], error: str) -> None:
        if not row_ids:
            return
        placeholders = ",".join("?" for _ in row_ids)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE events SET attempts = attempts + 1, last_error = ? WHERE id IN ({placeholders})",
                [error, *row_ids],
            )


@dataclass
class WindowSnapshot:
    app_name: str
    process_name: str
    window_title: str
    pid: int | None
    file_path: str | None


class WindowsCollector:
    def idle_seconds(self) -> float:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return millis / 1000.0
        return 0.0

    def active_window(self) -> WindowSnapshot:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        title = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(hwnd, title, 512)

        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_name = "unknown"
        app_name = "Unknown"
        file_path = None

        try:
            process = psutil.Process(pid.value)
            process_name = process.name()
            app_name = process_name.rsplit(".", 1)[0]
            open_files = process.open_files()
            if open_files:
                file_path = open_files[0].path
        except Exception:
            pass

        return WindowSnapshot(
            app_name=app_name,
            process_name=process_name,
            window_title=title.value or "Unknown Window",
            pid=pid.value or None,
            file_path=file_path,
        )


class AgentClient:
    def __init__(self, config: dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.session = requests.Session()

    @property
    def base_url(self) -> str:
        return self.config["server_url"].rstrip("/")

    def has_credentials(self) -> bool:
        return all([
            self.config.get("agent_token_id"),
            self.config.get("agent_token"),
            self.config.get("security_key"),
        ])

    def auth_headers(self) -> dict[str, str]:
        return {
            "X-Agent-Token-Id": self.config["agent_token_id"],
            "X-Agent-Token": self.config["agent_token"],
            "X-Agent-Security-Key": self.config["security_key"],
        }

    def identity_payload(self) -> dict[str, Any]:
        return {
            "device_id": self.config["device_id"],
            "hostname": self.config["hostname"],
            "os_type": self.config["os_type"],
            "os_version": self.config["os_version"],
            "agent_version": self.config["agent_version"],
            "username": self.config["username"],
            "master_password": self.config.get("master_password") or "",
        }

    def save_credentials(self, credentials: dict[str, Any]) -> None:
        self.config["agent_id"] = credentials["agent_id"]
        self.config["agent_token_id"] = credentials["agent_token_id"]
        self.config["agent_token"] = credentials["agent_token"]
        self.config["security_key"] = credentials["security_key"]
        self.config["pending_request_id"] = ""
        save_config(self.config)

    def ensure_registered(self) -> bool:
        if self.has_credentials():
            return True

        pending_id = self.config.get("pending_request_id")
        if pending_id:
            return self.poll_registration(pending_id)

        response = self.session.post(
            f"{self.base_url}/api/agents/register",
            json=self.identity_payload(),
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        if body["status"] == "active" and body.get("credentials"):
            self.save_credentials(body["credentials"])
            self.logger.info("Agent auto-registered")
            return True

        if body["status"] == "pending_approval":
            self.config["pending_request_id"] = body["request_id"]
            save_config(self.config)
            self.logger.warning("Agent registration pending admin approval: %s", body["request_id"])
            return False

        return False

    def poll_registration(self, request_id: str) -> bool:
        response = self.session.get(
            f"{self.base_url}/api/agents/registration-status/{request_id}",
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        if body["status"] == "approved" and body.get("credentials"):
            self.save_credentials(body["credentials"])
            self.logger.info("Agent approved and credentials stored")
            return True
        if body["status"] == "rejected":
            self.config["pending_request_id"] = ""
            save_config(self.config)
            self.logger.error("Agent registration rejected")
        return False

    def heartbeat(self, payload: dict[str, Any]) -> None:
        response = self.session.post(
            f"{self.base_url}/api/agents/heartbeat",
            headers=self.auth_headers(),
            json={"status": "online", "captured_at": utc_iso(), "payload": payload},
            timeout=15,
        )
        if response.status_code == 401:
            self.clear_credentials()
        response.raise_for_status()

    def send_events(self, events: list[dict[str, Any]]) -> tuple[int, int]:
        response = self.session.post(
            f"{self.base_url}/api/agents/events/batch",
            headers=self.auth_headers(),
            json={"events": [{k: v for k, v in event.items() if k != "row_id"} for event in events]},
            timeout=30,
        )
        if response.status_code == 401:
            self.clear_credentials()
        response.raise_for_status()
        body = response.json()
        return int(body["accepted"]), int(body["duplicates"])

    def pull_runtime_config(self) -> None:
        response = self.session.get(
            f"{self.base_url}/api/agents/config",
            headers=self.auth_headers(),
            timeout=15,
        )
        if response.status_code == 401:
            self.clear_credentials()
        response.raise_for_status()
        body = response.json()
        self.config["idle_threshold_seconds"] = body["idle_threshold_seconds"]
        self.config["check_interval_seconds"] = body["check_interval_seconds"]
        self.config["batch_interval_seconds"] = body["batch_interval_seconds"]
        save_config(self.config)

    def clear_credentials(self) -> None:
        self.logger.warning("Agent credentials rejected by backend; registration required")
        self.config["agent_id"] = None
        self.config["agent_token_id"] = ""
        self.config["agent_token"] = ""
        self.config["security_key"] = ""
        save_config(self.config)


class ProductivityAgent:
    def __init__(self, config: dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.client = AgentClient(config, logger)
        self.queue = EventQueue(agent_data_path(config.get("queue_db_path", "agent_queue.sqlite3")))
        self.collector = WindowsCollector()
        self.current_window: WindowSnapshot | None = None
        self.current_start = utc_now()
        self.idle_started_at: datetime | None = None
        self.last_heartbeat = 0.0
        self.last_flush = 0.0

    def base_payload(self) -> dict[str, Any]:
        return {
            "device_id": self.config["device_id"],
            "hostname": self.config["hostname"],
            "username": self.config["username"],
            "os_type": self.config["os_type"],
            "agent_version": self.config["agent_version"],
        }

    def enqueue_window_event(self, event_type: str, snapshot: WindowSnapshot, started_at: datetime, ended_at: datetime) -> None:
        duration = max(0, int((ended_at - started_at).total_seconds()))
        payload = {
            **self.base_payload(),
            "app_name": snapshot.app_name,
            "process_name": snapshot.process_name,
            "window_title": snapshot.window_title,
            "pid": snapshot.pid,
            "file_path": snapshot.file_path,
            "start_time": started_at.isoformat(),
            "end_time": ended_at.isoformat(),
            "duration": duration,
        }
        self.queue.enqueue(event_type, payload, ended_at.isoformat())

    def heartbeat_if_due(self) -> None:
        now = time.time()
        if now - self.last_heartbeat < int(self.config.get("heartbeat_interval_seconds", 30)):
            return
        self.client.heartbeat({
            **self.base_payload(),
            "idle": self.idle_started_at is not None,
            "active_window": self.current_window.window_title if self.current_window else None,
        })
        self.last_heartbeat = now

    def flush_if_due(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self.last_flush < int(self.config.get("batch_interval_seconds", 15)):
            return
        events = self.queue.pending(limit=100)
        if not events:
            self.last_flush = now
            return
        try:
            accepted, duplicates = self.client.send_events(events)
            self.queue.delete([event["row_id"] for event in events])
            self.logger.info("Flushed events accepted=%s duplicates=%s", accepted, duplicates)
        except Exception as exc:
            self.queue.mark_failed([event["row_id"] for event in events], str(exc))
            self.logger.warning("Failed to flush events: %s", exc)
        self.last_flush = now

    def register_loop(self) -> None:
        while not self.client.ensure_registered():
            self.logger.info("Waiting for registration approval...")
            time.sleep(15)
        try:
            self.client.pull_runtime_config()
        except Exception as exc:
            self.logger.warning("Could not pull runtime config: %s", exc)

    def run(self) -> None:
        self.logger.info("Starting InfraProTrack Windows agent")
        self.register_loop()
        self.queue.enqueue("login", self.base_payload())

        while True:
            try:
                self.tick()
            except KeyboardInterrupt:
                self.shutdown()
                raise
            except Exception as exc:
                self.logger.exception("Agent tick failed: %s", exc)
            time.sleep(int(self.config.get("check_interval_seconds", 5)))

    def tick(self) -> None:
        self.register_loop()
        now = utc_now()
        idle_seconds = self.collector.idle_seconds()
        idle_threshold = int(self.config.get("idle_threshold_seconds", 60))

        if idle_seconds >= idle_threshold:
            if self.idle_started_at is None:
                if self.current_window:
                    self.enqueue_window_event("app_session_end", self.current_window, self.current_start, now)
                self.idle_started_at = now
                self.queue.enqueue("idle_start", {**self.base_payload(), "idle_seconds": int(idle_seconds)}, now.isoformat())
            self.heartbeat_if_due()
            self.flush_if_due()
            return

        if self.idle_started_at is not None:
            self.queue.enqueue(
                "idle_end",
                {
                    **self.base_payload(),
                    "start_time": self.idle_started_at.isoformat(),
                    "end_time": now.isoformat(),
                    "duration": int((now - self.idle_started_at).total_seconds()),
                },
                now.isoformat(),
            )
            self.idle_started_at = None
            self.current_window = None

        snapshot = self.collector.active_window()
        if not self.current_window:
            self.current_window = snapshot
            self.current_start = now
            self.queue.enqueue("app_session_start", {**self.base_payload(), **snapshot.__dict__}, now.isoformat())
        elif snapshot.window_title != self.current_window.window_title or snapshot.process_name != self.current_window.process_name:
            self.enqueue_window_event("app_session_end", self.current_window, self.current_start, now)
            self.current_window = snapshot
            self.current_start = now
            self.queue.enqueue("app_session_start", {**self.base_payload(), **snapshot.__dict__}, now.isoformat())
        else:
            self.queue.enqueue(
                "active_window",
                {**self.base_payload(), **snapshot.__dict__, "idle_seconds": int(idle_seconds)},
                now.isoformat(),
            )

        if snapshot.file_path:
            self.queue.enqueue("file_active", {**self.base_payload(), **snapshot.__dict__}, now.isoformat())

        self.heartbeat_if_due()
        self.flush_if_due()

    def shutdown(self) -> None:
        now = utc_now()
        if self.current_window:
            self.enqueue_window_event("app_session_end", self.current_window, self.current_start, now)
        self.queue.enqueue("logout", self.base_payload(), now.isoformat())
        self.flush_if_due(force=True)
        self.logger.info("InfraProTrack Windows agent stopped")


def run_foreground() -> None:
    config = load_config()
    logger = setup_logging(config)
    ProductivityAgent(config, logger).run()


def register_once() -> None:
    config = load_config()
    logger = setup_logging(config)
    config["agent_id"] = None
    config["agent_token_id"] = ""
    config["agent_token"] = ""
    config["security_key"] = ""
    config["pending_request_id"] = ""
    save_config(config)
    client = AgentClient(config, logger)
    if client.ensure_registered():
        print("Agent registered and credentials are stored in config.json")
    else:
        print(f"Agent pending approval: {config.get('pending_request_id')}")


def heartbeat_once() -> None:
    config = load_config()
    logger = setup_logging(config)
    client = AgentClient(config, logger)
    if not client.ensure_registered():
        print(f"Agent pending approval: {config.get('pending_request_id')}")
        return
    client.heartbeat({"manual": True, "hostname": config["hostname"]})
    print("Heartbeat accepted")


def collect_once() -> None:
    config = load_config()
    logger = setup_logging(config)
    agent = ProductivityAgent(config, logger)
    agent.register_loop()
    agent.tick()
    agent.flush_if_due(force=True)
    print("One collection cycle completed")


try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    class InfraProTrackAgentService(win32serviceutil.ServiceFramework):
        _svc_name_ = "InfraProTrackAgent"
        _svc_display_name_ = "InfraProTrack Agent"
        _svc_description_ = "Collects endpoint productivity telemetry for InfraProTrack."

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.running = True

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.running = False
            win32event.SetEvent(self.stop_event)

        def SvcDoRun(self):
            servicemanager.LogInfoMsg("InfraProTrack Agent service starting")
            config = load_config()
            logger = setup_logging(config)
            agent = ProductivityAgent(config, logger)
            agent.register_loop()
            while self.running:
                try:
                    agent.tick()
                except Exception as exc:
                    logger.exception("Service tick failed: %s", exc)
                rc = win32event.WaitForSingleObject(
                    self.stop_event,
                    int(config.get("check_interval_seconds", 5)) * 1000,
                )
                if rc == win32event.WAIT_OBJECT_0:
                    break
            agent.shutdown()
            servicemanager.LogInfoMsg("InfraProTrack Agent service stopped")

except ImportError:
    InfraProTrackAgentService = None


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in {"install", "update", "remove", "start", "stop", "restart", "debug"}:
        if InfraProTrackAgentService is None:
            print("Windows service commands require pywin32. Install dependencies from requirements.txt.")
            sys.exit(1)
        win32serviceutil.HandleCommandLine(InfraProTrackAgentService)
        return

    parser = argparse.ArgumentParser(description="InfraProTrack Windows Agent")
    parser.add_argument("--register", action="store_true", help="Register the agent and store credentials")
    parser.add_argument("--heartbeat", action="store_true", help="Send one heartbeat and exit")
    parser.add_argument("--once", action="store_true", help="Run one collection cycle and exit")
    parser.add_argument("--run", action="store_true", help="Run foreground agent loop")
    args = parser.parse_args()

    if args.register:
        register_once()
    elif args.heartbeat:
        heartbeat_once()
    elif args.once:
        collect_once()
    else:
        run_foreground()


if __name__ == "__main__":
    main()
