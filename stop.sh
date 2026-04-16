#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$BASE_DIR/pids"

stop_service() {
  local name="$1"
  local pid_file="$PID_DIR/${name}.pid"

  if [[ ! -f "$pid_file" ]]; then
    echo "$name is not running (no PID file)."
    return
  fi

  local pid
  pid="$(cat "$pid_file")"

  if kill -0 "$pid" 2>/dev/null; then
    echo "Stopping $name (PID $pid)..."
    kill "$pid" 2>/dev/null || true

    for _ in {1..20}; do
      if kill -0 "$pid" 2>/dev/null; then
        sleep 0.5
      else
        break
      fi
    done

    if kill -0 "$pid" 2>/dev/null; then
      echo "Force killing $name (PID $pid)..."
      kill -9 "$pid" 2>/dev/null || true
    fi
  else
    echo "$name process not found, cleaning stale PID file."
  fi

  rm -f "$pid_file"
  echo "$name stopped."
}

stop_service "run"
stop_service "qr_tagging"
stop_service "db_to_sftp"

# Fallback: kill any python processes still using this project dir as cwd (orphans from old start.sh).
for pid in $(pgrep -x python3 2>/dev/null || true); do
  cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || true)"
  [[ "$cwd" == "$BASE_DIR" ]] || continue
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  case "$cmdline" in
    *run.py*|*"qr_tagging .py"*|*db_to_sftp_service.py*)
      echo "Stopping orphan PID $pid ($cmdline)"
      kill "$pid" 2>/dev/null || true
      sleep 0.3
      kill -9 "$pid" 2>/dev/null || true
      ;;
  esac
done

echo "Stop command completed."

