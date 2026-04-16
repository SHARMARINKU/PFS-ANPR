#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$BASE_DIR/pids"
LOG_DIR="${ANPR_SERVICE_LOG_DIR:-/home/jbmai/PFS/Logs/services}"

mkdir -p "$PID_DIR" "$LOG_DIR"

start_service() {
  local name="$1"
  local pid_file="$PID_DIR/${name}.pid"
  local log_file="$LOG_DIR/${name}.log"

  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file")"
    if kill -0 "$old_pid" 2>/dev/null; then
      echo "$name already running (PID $old_pid)"
      return
    fi
    rm -f "$pid_file"
  fi

  echo "Starting $name..."
  cd "$BASE_DIR"
  case "$name" in
    run)
      nohup python3 run.py >>"$log_file" 2>&1 &
      ;;
    qr_tagging)
      nohup python3 "qr_tagging .py" >>"$log_file" 2>&1 &
      ;;
    db_to_sftp)
      nohup python3 db_to_sftp_service.py >>"$log_file" 2>&1 &
      ;;
    *)
      echo "Unknown service: $name" >&2
      exit 1
      ;;
  esac
  echo $! >"$pid_file"
  echo "$name started (PID $(cat "$pid_file")), log: $log_file"
}

start_service "run"
start_service "qr_tagging"
start_service "db_to_sftp"

echo "All services start command issued."

