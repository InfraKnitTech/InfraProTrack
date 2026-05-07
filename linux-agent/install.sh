#!/usr/bin/env bash
set -euo pipefail

APP_NAME="infraprotrack-agent"
INSTALL_SCOPE="${INSTALL_SCOPE:-user}"
SERVER_URL="${SERVER_URL:-http://127.0.0.1:5000}"
MASTER_PASSWORD="${MASTER_PASSWORD:-InfraAgent@2026}"

if [[ "${INSTALL_SCOPE}" != "user" && "${INSTALL_SCOPE}" != "system" ]]; then
  echo "INSTALL_SCOPE must be user or system."
  exit 1
fi

if [[ "${INSTALL_SCOPE}" == "system" ]]; then
  if [[ "${EUID}" -ne 0 ]]; then
    echo "System install requires sudo/root."
    exit 1
  fi
  INSTALL_DIR="${INSTALL_DIR:-/opt/infraprotrack-agent}"
  DATA_DIR="${INFRAPROTRACK_AGENT_HOME:-/var/lib/infraprotrack-agent}"
  LOG_DIR="${LOG_DIR:-/var/log/infraprotrack-agent}"
  SERVICE_DIR="/etc/systemd/system"
  SERVICE_FILE="${SERVICE_DIR}/${APP_NAME}.service"
  RUN_USER="${RUN_USER:-root}"
  SYSTEMCTL=(systemctl)
else
  if [[ "${EUID}" -eq 0 ]]; then
    echo "User install must be run as the target desktop user, not with sudo."
    exit 1
  fi
  INSTALL_DIR="${INSTALL_DIR:-${HOME}/.local/share/infraprotrack-agent/app}"
  DATA_DIR="${INFRAPROTRACK_AGENT_HOME:-${HOME}/.local/share/infraprotrack-agent}"
  LOG_DIR="${LOG_DIR:-${HOME}/.local/state/infraprotrack-agent}"
  SERVICE_DIR="${HOME}/.config/systemd/user"
  SERVICE_FILE="${SERVICE_DIR}/${APP_NAME}.service"
  SYSTEMCTL=(systemctl --user)
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "${INSTALL_DIR}" "${DATA_DIR}" "${LOG_DIR}" "${SERVICE_DIR}"
cp "${SCRIPT_DIR}/agent.py" "${INSTALL_DIR}/agent.py"
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/requirements.txt"

python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

if [[ "${INSTALL_DESKTOP_HELPERS:-1}" == "1" ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    if [[ "${EUID}" -eq 0 ]]; then
      apt-get update
      apt-get install -y xdotool xprintidle
    elif command -v sudo >/dev/null 2>&1; then
      sudo apt-get update
      sudo apt-get install -y xdotool xprintidle
    else
      echo "Install xdotool and xprintidle manually for desktop tracking."
    fi
  else
    echo "Install xdotool and xprintidle manually for desktop tracking."
  fi
fi

if [[ ! -f "${DATA_DIR}/config.json" ]]; then
  cp "${SCRIPT_DIR}/config.json" "${DATA_DIR}/config.json"
fi

export SERVER_URL MASTER_PASSWORD LOG_DIR
python3 - "${DATA_DIR}/config.json" <<'PY'
import json
import os
from pathlib import Path
import sys

path = Path(sys.argv[1])
config = json.loads(path.read_text(encoding="utf-8"))
config["server_url"] = os.environ["SERVER_URL"]
config["master_password"] = os.environ["MASTER_PASSWORD"]
config["os_type"] = "linux"
config["log_path"] = str(Path(os.environ["LOG_DIR"]) / "agent.log")
path.write_text(json.dumps(config, indent=2), encoding="utf-8")
PY

if [[ "${INSTALL_SCOPE}" == "system" ]]; then
  chown -R "${RUN_USER}:${RUN_USER}" "${DATA_DIR}" "${LOG_DIR}" || true
fi
chmod 750 "${DATA_DIR}" "${LOG_DIR}"
chmod 640 "${DATA_DIR}/config.json"

if [[ "${INSTALL_SCOPE}" == "system" ]]; then
  cat > "${SERVICE_FILE}" <<SERVICE
[Unit]
Description=InfraProTrack Linux Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Environment=INFRAPROTRACK_AGENT_HOME=${DATA_DIR}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/agent.py --run
Restart=always
RestartSec=10
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
SERVICE
else
  cat > "${SERVICE_FILE}" <<SERVICE
[Unit]
Description=InfraProTrack Linux Agent
After=graphical-session.target network-online.target
Wants=network-online.target
PartOf=graphical-session.target

[Service]
Type=simple
Environment=INFRAPROTRACK_AGENT_HOME=${DATA_DIR}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/agent.py --run
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
SERVICE
fi

if command -v systemctl >/dev/null 2>&1; then
  if [[ "${INSTALL_SCOPE}" == "user" ]]; then
    "${SYSTEMCTL[@]}" import-environment DISPLAY XAUTHORITY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS || true
  fi
  "${SYSTEMCTL[@]}" daemon-reload
  "${SYSTEMCTL[@]}" enable --now "${APP_NAME}.service"
  "${SYSTEMCTL[@]}" status "${APP_NAME}.service" --no-pager || true
else
  echo "systemctl not found. Run manually with:"
  echo "INFRAPROTRACK_AGENT_HOME=${DATA_DIR} ${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/agent.py --run"
fi

echo "InfraProTrack Linux agent installed (${INSTALL_SCOPE} scope)."
echo "Config: ${DATA_DIR}/config.json"
echo "Logs:   ${LOG_DIR}/agent.log"
echo "For full active-window capture, Ubuntu should run an X11 desktop session with xdotool installed."
