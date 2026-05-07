#!/usr/bin/env bash
set -euo pipefail

APP_NAME="infraprotrack-agent"
INSTALL_SCOPE="${INSTALL_SCOPE:-user}"

if [[ "${INSTALL_SCOPE}" != "user" && "${INSTALL_SCOPE}" != "system" ]]; then
  echo "INSTALL_SCOPE must be user or system."
  exit 1
fi

if [[ "${INSTALL_SCOPE}" == "system" ]]; then
  if [[ "${EUID}" -ne 0 ]]; then
    echo "System removal requires sudo/root."
    exit 1
  fi
  INSTALL_DIR="${INSTALL_DIR:-/opt/infraprotrack-agent}"
  DATA_DIR="${INFRAPROTRACK_AGENT_HOME:-/var/lib/infraprotrack-agent}"
  LOG_DIR="${LOG_DIR:-/var/log/infraprotrack-agent}"
  SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
  SYSTEMCTL=(systemctl)
else
  if [[ "${EUID}" -eq 0 ]]; then
    echo "User removal must be run as the target desktop user, not with sudo."
    exit 1
  fi
  INSTALL_DIR="${INSTALL_DIR:-${HOME}/.local/share/infraprotrack-agent/app}"
  DATA_DIR="${INFRAPROTRACK_AGENT_HOME:-${HOME}/.local/share/infraprotrack-agent}"
  LOG_DIR="${LOG_DIR:-${HOME}/.local/state/infraprotrack-agent}"
  SERVICE_FILE="${HOME}/.config/systemd/user/${APP_NAME}.service"
  SYSTEMCTL=(systemctl --user)
fi

if command -v systemctl >/dev/null 2>&1; then
  "${SYSTEMCTL[@]}" disable --now "${APP_NAME}.service" || true
fi

rm -f "${SERVICE_FILE}"

if command -v systemctl >/dev/null 2>&1; then
  "${SYSTEMCTL[@]}" daemon-reload
fi

if [[ -n "${INSTALL_DIR}" && "${INSTALL_DIR}" != "/" ]]; then
  rm -rf "${INSTALL_DIR}"
fi

if [[ "${REMOVE_DATA:-0}" == "1" ]]; then
  if [[ -n "${DATA_DIR}" && "${DATA_DIR}" != "/" ]]; then
    rm -rf "${DATA_DIR}"
  fi
  if [[ -n "${LOG_DIR}" && "${LOG_DIR}" != "/" ]]; then
    rm -rf "${LOG_DIR}"
  fi
  echo "InfraProTrack Linux agent removed with data (${INSTALL_SCOPE} scope)."
else
  echo "InfraProTrack Linux agent removed (${INSTALL_SCOPE} scope). Data kept at ${DATA_DIR}; logs kept at ${LOG_DIR}."
fi
