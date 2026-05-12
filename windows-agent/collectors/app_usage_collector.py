from dataclasses import dataclass
from datetime import datetime
from typing import Any
import ctypes

import psutil

from collectors.browser_url_collector import BrowserUrlResolver
from collectors.idle_reason_prompt import IdleReasonPrompt
from core.runtime_state import RuntimeState
from ingest.event_queue import EventQueue
from utils.time_utils import utc_now


@dataclass
class WindowSnapshot:
    app_name: str
    process_name: str
    window_title: str
    pid: int | None
    file_path: str | None
    url: str | None = None
    domain: str | None = None


class WindowsCollector:
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


class AppUsageCollector:
    def __init__(self, config: dict[str, Any], queue: EventQueue, state: RuntimeState):
        self.config = config
        self.queue = queue
        self.state = state
        self.collector = WindowsCollector()
        self.url_resolver = BrowserUrlResolver(config)
        self.idle_reason_prompt = IdleReasonPrompt(config.get("idle_reason_categories") or [])

    def base_payload(self) -> dict[str, Any]:
        return {
            "device_id": self.config["device_id"],
            "hostname": self.config["hostname"],
            "username": self.config["username"],
            "os_type": self.config["os_type"],
            "agent_version": self.config["agent_version"],
        }

    def enrich_url(self, snapshot: WindowSnapshot) -> WindowSnapshot:
        browser_url = self.url_resolver.resolve(snapshot.process_name, snapshot.window_title)
        if not browser_url:
            return snapshot
        snapshot.url = browser_url.url
        snapshot.domain = browser_url.domain
        return snapshot

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
        if event_type == "app_session_end":
            payload["app_usage_already_sampled"] = True
        self.queue.enqueue(event_type, payload, ended_at.isoformat())

    def enqueue_active_sample(self, snapshot: WindowSnapshot, started_at: datetime, ended_at: datetime, idle_seconds: float) -> None:
        duration = max(0, int((ended_at - started_at).total_seconds()))
        if duration <= 0:
            return
        self.queue.enqueue(
            "active_window",
            {
                **self.base_payload(),
                **snapshot.__dict__,
                "idle_seconds": int(idle_seconds),
                "start_time": started_at.isoformat(),
                "end_time": ended_at.isoformat(),
                "duration": duration,
            },
            ended_at.isoformat(),
        )
        if snapshot.url:
            self.queue.enqueue(
                "url_active",
                {
                    **self.base_payload(),
                    "app_name": snapshot.app_name,
                    "process_name": snapshot.process_name,
                    "window_title": snapshot.window_title,
                    "url": snapshot.url,
                    "domain": snapshot.domain,
                    "start_time": started_at.isoformat(),
                    "end_time": ended_at.isoformat(),
                    "duration": duration,
                    "usage_only": True,
                },
                ended_at.isoformat(),
            )

    def process_tick(self, idle_seconds: float) -> None:
        now = utc_now()
        idle_threshold = int(self.config.get("idle_threshold_seconds", 60))

        if idle_seconds >= idle_threshold:
            if self.state.idle_started_at is None:
                if self.state.current_window:
                    sample_start = self.state.last_active_sample_at or self.state.current_start
                    self.enqueue_active_sample(self.state.current_window, sample_start, now, idle_seconds)
                    self.enqueue_window_event("app_session_end", self.state.current_window, self.state.current_start, now)
                self.state.idle_started_at = now
                self.state.last_active_sample_at = None
                self.queue.enqueue("idle_start", {**self.base_payload(), "idle_seconds": int(idle_seconds)}, now.isoformat())
            return

        if self.state.idle_started_at is not None:
            idle_duration = int((now - self.state.idle_started_at).total_seconds())
            idle_reason = self.idle_reason_prompt.ask(idle_duration)
            self.queue.enqueue(
                "idle_end",
                {
                    **self.base_payload(),
                    "start_time": self.state.idle_started_at.isoformat(),
                    "end_time": now.isoformat(),
                    "duration": idle_duration,
                    "reason_category": idle_reason.category,
                    "reason": idle_reason.reason,
                },
                now.isoformat(),
            )
            self.state.idle_started_at = None
            self.state.current_window = None

        snapshot = self.enrich_url(self.collector.active_window())
        if not self.state.current_window:
            self.state.current_window = snapshot
            self.state.current_start = now
            self.state.last_active_sample_at = now
            self.queue.enqueue("app_session_start", {**self.base_payload(), **snapshot.__dict__}, now.isoformat())
        elif (
            snapshot.process_name != self.state.current_window.process_name
        ):
            sample_start = self.state.last_active_sample_at or self.state.current_start
            self.enqueue_active_sample(self.state.current_window, sample_start, now, idle_seconds)
            self.enqueue_window_event("app_session_end", self.state.current_window, self.state.current_start, now)
            self.state.current_window = snapshot
            self.state.current_start = now
            self.state.last_active_sample_at = now
            self.queue.enqueue("app_session_start", {**self.base_payload(), **snapshot.__dict__}, now.isoformat())
        else:
            sample_start = self.state.last_active_sample_at or self.state.current_start
            self.enqueue_active_sample(snapshot, sample_start, now, idle_seconds)
            self.state.current_window = snapshot
            self.state.last_active_sample_at = now

        if snapshot.file_path:
            self.queue.enqueue("file_active", {**self.base_payload(), **snapshot.__dict__}, now.isoformat())

    def shutdown(self) -> None:
        now = utc_now()
        if self.state.current_window:
            sample_start = self.state.last_active_sample_at or self.state.current_start
            self.enqueue_active_sample(self.state.current_window, sample_start, now, 0)
            self.enqueue_window_event("app_session_end", self.state.current_window, self.state.current_start, now)
        self.queue.enqueue("logout", self.base_payload(), now.isoformat())
