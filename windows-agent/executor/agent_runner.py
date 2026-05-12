import argparse
import sys
import time
from typing import Any

from core.config_loader import agent_data_path, save_config
from core.runtime_state import RuntimeState
from collectors.app_usage_collector import AppUsageCollector
from collectors.idle_collector import WindowsIdleCollector
from ingest.api_client import AgentAPIClient
from ingest.event_queue import EventQueue
from ingest.event_sender import EventSender
from security.agent_auth import reset_auth_state
from security.registration import wait_for_registration, ensure_registered_once
from utils.time_utils import utc_now


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
            from core.config_loader import load_config
            from core.logger import setup_logging
            from core.runtime_state import RuntimeState
            from core.config_loader import agent_data_path

            config = load_config()
            logger = setup_logging(config)
            runner = AgentRunner(config, logger)
            supervisor = runner.build_supervisor()
            wait_for_registration(supervisor.client, config, logger)
            supervisor.queue.enqueue("login", supervisor.base_payload())
            supervisor.sender.flush_if_due(force=True)
            while self.running:
                try:
                    supervisor.tick()
                except Exception as exc:
                    logger.exception("Service tick failed: %s", exc)
                rc = win32event.WaitForSingleObject(
                    self.stop_event,
                    int(config.get("check_interval_seconds", 5)) * 1000,
                )
                if rc == win32event.WAIT_OBJECT_0:
                    break
            supervisor.shutdown()
            servicemanager.LogInfoMsg("InfraProTrack Agent service stopped")

except ImportError:
    InfraProTrackAgentService = None


def handle_service_commands(argv: list[str]) -> bool:
    if len(argv) > 1 and argv[1] in {"install", "update", "remove", "start", "stop", "restart", "debug"}:
        if InfraProTrackAgentService is None:
            print("Windows service commands require pywin32. Install dependencies from requirements.txt.")
            sys.exit(1)
        win32serviceutil.HandleCommandLine(InfraProTrackAgentService)
        return True
    return False


class Supervisor:
    def __init__(self, config: dict[str, Any], logger):
        self.config = config
        self.logger = logger
        self.state = RuntimeState()
        self.client = AgentAPIClient(config, logger)
        self.queue = EventQueue(agent_data_path(config, config.get("queue_db_path", "agent_queue.sqlite3")))
        self.app_collector = AppUsageCollector(config, self.queue, self.state)
        self.idle_collector = WindowsIdleCollector()
        self.sender = EventSender(config, logger, self.client, self.queue, self.state)

    def base_payload(self) -> dict[str, Any]:
        return {
            "device_id": self.config["device_id"],
            "hostname": self.config["hostname"],
            "username": self.config["username"],
            "os_type": self.config["os_type"],
            "agent_version": self.config["agent_version"],
        }

    def ensure_ready(self, wait: bool = True) -> bool:
        if ensure_registered_once(self.client, self.config, self.logger):
            return True
        if wait:
            return wait_for_registration(self.client, self.config, self.logger)
        return False

    def heartbeat_if_due(self) -> None:
        now = time.time()
        if now - self.state.last_heartbeat < int(self.config.get("heartbeat_interval_seconds", 30)):
            return
        self.client.heartbeat({
            **self.base_payload(),
            "idle": self.state.idle_started_at is not None,
            "active_window": self.state.current_window.window_title if self.state.current_window else None,
        })
        self.state.last_heartbeat = now

    def tick(self) -> None:
        self.ensure_ready(wait=True)
        idle_seconds = self.idle_collector.idle_seconds()
        self.app_collector.process_tick(idle_seconds)
        self.heartbeat_if_due()
        self.sender.flush_if_due()

    def run_foreground(self) -> None:
        self.logger.info("Starting InfraProTrack Windows agent")
        self.ensure_ready(wait=True)
        self.queue.enqueue("login", self.base_payload())
        self.sender.flush_if_due(force=True)
        while self.state.running:
            try:
                self.tick()
            except KeyboardInterrupt:
                self.shutdown()
                raise
            except Exception as exc:
                self.logger.exception("Agent tick failed: %s", exc)
            time.sleep(int(self.config.get("check_interval_seconds", 5)))

    def run_once(self) -> None:
        self.ensure_ready(wait=True)
        self.tick()
        self.sender.flush_if_due(force=True)

    def shutdown(self) -> None:
        self.app_collector.shutdown()
        self.sender.flush_if_due(force=True)
        self.logger.info("InfraProTrack Windows agent stopped")


class AgentRunner:
    def __init__(self, config: dict[str, Any], logger):
        self.config = config
        self.logger = logger
        self.client = AgentAPIClient(config, logger)

    def build_supervisor(self) -> Supervisor:
        return Supervisor(self.config, self.logger)

    def run_from_argv(self, argv: list[str]) -> None:
        parser = argparse.ArgumentParser(description="InfraProTrack Windows Agent")
        parser.add_argument("--register", action="store_true", help="Register the agent and store credentials")
        parser.add_argument("--heartbeat", action="store_true", help="Send one heartbeat and exit")
        parser.add_argument("--once", action="store_true", help="Run one collection cycle and exit")
        parser.add_argument("--run", action="store_true", help="Run foreground agent loop")
        args = parser.parse_args(argv)

        if args.register:
            self.register_once()
        elif args.heartbeat:
            self.heartbeat_once()
        elif args.once:
            self.collect_once()
        else:
            self.run_foreground()

    def register_once(self) -> None:
        reset_auth_state(self.config, save_config)
        if ensure_registered_once(self.client, self.config, self.logger):
            print("Agent registered and credentials are stored in config.json")
        else:
            print(f"Agent pending approval: {self.config.get('pending_request_id')}")

    def heartbeat_once(self) -> None:
        if not ensure_registered_once(self.client, self.config, self.logger):
            print(f"Agent pending approval: {self.config.get('pending_request_id')}")
            return
        self.client.heartbeat({"manual": True, "hostname": self.config["hostname"]})
        print("Heartbeat accepted")

    def collect_once(self) -> None:
        supervisor = self.build_supervisor()
        supervisor.run_once()
        print("One collection cycle completed")

    def run_foreground(self) -> None:
        supervisor = self.build_supervisor()
        supervisor.run_foreground()
