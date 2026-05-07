import argparse
import getpass
import json
import logging
import os
import platform
import re
import signal
import socket
import sqlite3
import subprocess
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
DATA_DIR = Path(os.environ.get("INFRAPROTRACK_AGENT_HOME", str(Path.home() / ".local" / "share" / "infraprotrack-agent")))
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
    "os_type": "linux",
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


def current_username() -> str:
    for env_name in ("USER", "LOGNAME", "USERNAME"):
        username = os.environ.get(env_name)
        if username:
            return username
    return getpass.getuser() or "unknown"


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
        config["username"] = current_username()
        changed = True
    if config.get("os_type") != "linux":
        config["os_type"] = "linux"
        changed = True
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
    machine_id = ""
    for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        path = Path(candidate)
        if path.exists():
            machine_id = path.read_text(encoding="utf-8").strip()
            break
    raw = f"{hostname}:{machine_id}:{uuid.getnode()}:{platform.platform()}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw))


def setup_logging(config: dict[str, Any]) -> logging.Logger:
    logger = logging.getLogger("InfraProTrackLinuxAgent")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_path = agent_data_path(config.get("log_path", "agent.log"))
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
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
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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


class LinuxCollector:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._warned_active_window = False
        self._warned_idle = False

    def _run(self, command: list[str]) -> str | None:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=True,
                text=True,
                timeout=2,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        return result.stdout.strip()

    def idle_seconds(self) -> float:
        xprintidle = self._run(["xprintidle"])
        if xprintidle and xprintidle.isdigit():
            return int(xprintidle) / 1000.0

        gnome_idle = self._run([
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.gnome.Mutter.IdleMonitor",
            "--object-path",
            "/org/gnome/Mutter/IdleMonitor/Core",
            "--method",
            "org.gnome.Mutter.IdleMonitor.GetIdletime",
        ])
        if gnome_idle:
            match = re.search(r"(\d+)", gnome_idle)
            if match:
                return int(match.group(1)) / 1000.0

        if not self._warned_idle:
            self.logger.warning("Linux idle detection needs xprintidle or GNOME IdleMonitor access")
            self._warned_idle = True
        return 0.0

    def active_window(self) -> WindowSnapshot:
        snapshot = self._active_window_from_xdotool()
        if snapshot:
            return snapshot

        snapshot = self._active_window_from_xprop()
        if snapshot:
            return snapshot

        if not self._warned_active_window:
            self.logger.warning("Linux active-window tracking needs xdotool or xprop in the user's graphical session")
            self._warned_active_window = True
        return WindowSnapshot("Unknown", "unknown", "Unknown Linux Window", None, None)

    def _active_window_from_xdotool(self) -> WindowSnapshot | None:
        window_id = self._run(["xdotool", "getactivewindow"])
        if not window_id:
            return None

        title = self._run(["xdotool", "getwindowname", window_id]) or "Unknown Window"
        pid_text = self._run(["xdotool", "getwindowpid", window_id])
        pid = int(pid_text) if pid_text and pid_text.isdigit() else None
        return self._snapshot_from_pid(pid, title)

    def _active_window_from_xprop(self) -> WindowSnapshot | None:
        active = self._run(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
        if not active:
            return None
        match = re.search(r"window id # (0x[0-9a-fA-F]+)", active)
        if not match:
            return None

        window_id = match.group(1)
        title_output = self._run(["xprop", "-id", window_id, "WM_NAME"])
        title = "Unknown Window"
        if title_output:
            title_match = re.search(r'=\s+"(.*)"', title_output)
            if title_match:
                title = title_match.group(1)

        pid_output = self._run(["xprop", "-id", window_id, "_NET_WM_PID"])
        pid = None
        if pid_output:
            pid_match = re.search(r"=\s+(\d+)", pid_output)
            if pid_match:
                pid = int(pid_match.group(1))
        return self._snapshot_from_pid(pid, title)

    def _snapshot_from_pid(self, pid: int | None, title: str) -> WindowSnapshot:
        process_name = "unknown"
        app_name = "Unknown"
        file_path = None

        if pid:
            try:
                process = psutil.Process(pid)
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
            window_title=title,
            pid=pid,
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
            "os_type": "linux",
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
            self.logger.info("Linux agent auto-registered")
            return True

        if body["status"] == "pending_approval":
            self.config["pending_request_id"] = body["request_id"]
            save_config(self.config)
            self.logger.warning("Linux agent registration pending admin approval: %s", body["request_id"])
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
            self.logger.info("Linux agent approved and credentials stored")
            return True
        if body["status"] == "rejected":
            self.config["pending_request_id"] = ""
            save_config(self.config)
            self.logger.error("Linux agent registration rejected")
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
        self.logger.warning("Linux agent credentials rejected by backend; registration required")
        self.config["agent_id"] = None
        self.config["agent_token_id"] = ""
        self.config["agent_token"] = ""
        self.config["security_key"] = ""
        save_config(self.config)


class ProductivityLinuxAgent:
    def __init__(self, config: dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.client = AgentClient(config, logger)
        self.queue = EventQueue(agent_data_path(config.get("queue_db_path", "agent_queue.sqlite3")))
        self.collector = LinuxCollector(logger)
        self.current_window: WindowSnapshot | None = None
        self.current_start = utc_now()
        self.idle_started_at: datetime | None = None
        self.last_heartbeat = 0.0
        self.last_flush = 0.0
        self.running = True

    def stop(self, *_args) -> None:
        self.running = False

    def base_payload(self) -> dict[str, Any]:
        return {
            "device_id": self.config["device_id"],
            "hostname": self.config["hostname"],
            "username": self.config["username"],
            "os_type": "linux",
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
        while self.running and not self.client.ensure_registered():
            self.logger.info("Waiting for registration approval...")
            time.sleep(15)
        if not self.running:
            return
        try:
            self.client.pull_runtime_config()
        except Exception as exc:
            self.logger.warning("Could not pull runtime config: %s", exc)

    def run(self) -> None:
        self.logger.info("Starting InfraProTrack Linux agent")
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        self.register_loop()
        if not self.running:
            return

        self.queue.enqueue("login", self.base_payload())
        while self.running:
            try:
                self.tick()
            except Exception as exc:
                self.logger.exception("Linux agent tick failed: %s", exc)
            time.sleep(int(self.config.get("check_interval_seconds", 5)))
        self.shutdown()

    def tick(self) -> None:
        self.register_loop()
        if not self.running:
            return

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
        self.logger.info("InfraProTrack Linux agent stopped")


def run_foreground() -> None:
    config = load_config()
    logger = setup_logging(config)
    ProductivityLinuxAgent(config, logger).run()


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
        print("Linux agent registered and credentials are stored in config.json")
    else:
        print(f"Linux agent pending approval: {config.get('pending_request_id')}")


def heartbeat_once() -> None:
    config = load_config()
    logger = setup_logging(config)
    client = AgentClient(config, logger)
    if not client.ensure_registered():
        print(f"Linux agent pending approval: {config.get('pending_request_id')}")
        return
    client.heartbeat({"manual": True, "hostname": config["hostname"], "os_type": "linux"})
    print("Heartbeat accepted")


def collect_once() -> None:
    config = load_config()
    logger = setup_logging(config)
    agent = ProductivityLinuxAgent(config, logger)
    agent.register_loop()
    agent.tick()
    agent.flush_if_due(force=True)
    print("One Linux collection cycle completed")


def main() -> None:
    parser = argparse.ArgumentParser(description="InfraProTrack Linux Agent")
    parser.add_argument("--register", action="store_true", help="Register the agent and store credentials")
    parser.add_argument("--heartbeat", action="store_true", help="Send one heartbeat and exit")
    parser.add_argument("--once", action="store_true", help="Run one collection cycle and exit")
    parser.add_argument("--run", action="store_true", help="Run foreground agent loop")
    args = parser.parse_args()

    if platform.system().lower() != "linux":
        print("This agent is for Linux only. Use the Windows agent from the agent folder on Windows.")
        sys.exit(1)

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
